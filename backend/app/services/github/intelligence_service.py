import re
import hashlib
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from backend.app.config import settings
from backend.app.models.candidate import CandidateProfile
from backend.app.models.integration import IntegrationConnection
from backend.app.services.token_vault import encrypt_token, decrypt_token
from backend.app.schemas.github_intelligence import (
    GitHubProjectIntelligence,
    TechnologyEvidence,
    StructureEvidence,
    RepositoryCommitMetadata,
    RepositoryAnalysisState,
    GitHubProjectAnalysisOutput,
    EvidenceCategory,
    GroundedClaim
)
from backend.app.services.github.client import GitHubApiClient, GitHubApiError, GitHubTokenRevokedError
from backend.app.services.github.manifest_parser import parse_manifests, KNOWN_MANIFESTS
from backend.app.services.github.structure_analyzer import analyze_repository_structure
from backend.app.services.ai.service import ai_service
from backend.app.services.discovery_snapshot_manager import snapshot_manager

logger = logging.getLogger(__name__)


def canonicalize_github_url(url: str) -> str:
    """Normalizes GitHub repository URLs to https://github.com/owner/repo format."""
    if not url:
        return ""
    clean = url.strip().rstrip("/")
    if clean.endswith(".git"):
        clean = clean[:-4]
    clean = clean.lower()
    
    # Handle ssh or short formats
    if "github.com/" in clean:
        parts = clean.split("github.com/")[-1].split("/")
        if len(parts) >= 2:
            return f"https://github.com/{parts[0]}/{parts[1]}"
    return clean


def get_github_token_for_user(user_id: int, db: Session) -> Optional[str]:
    """
    Retrieves candidate's decrypted GitHub token from secure token vault.
    Strictly isolated per user_id to prevent cross-user IDOR / token leakage.
    Falls back to settings.GITHUB_TOKEN if configured, or None.
    """
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    email = cand.email if cand and cand.email else f"user_{user_id}@github.local"
    
    conns = db.query(IntegrationConnection).filter(
        IntegrationConnection.provider == "github"
    ).all()
    
    conn = None
    for c in conns:
        if c.sync_cursor and isinstance(c.sync_cursor, dict) and c.sync_cursor.get("user_id") == user_id:
            conn = c
            break
        elif c.account_email == email:
            conn = c
            break

    if conn and conn.encrypted_access_token:
        try:
            decrypted = decrypt_token(conn.encrypted_access_token)
            if decrypted:
                return decrypted
        except Exception as e:
            logger.warning(f"Failed to decrypt GitHub token for user {user_id}: {e}")
            
    return settings.GITHUB_TOKEN or None


def save_github_token_for_user(user_id: int, token: str, db: Session) -> bool:
    """Securely encrypts and stores GitHub token in IntegrationConnection, strictly scoped to user_id."""
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    email = cand.email if cand and cand.email else f"user_{user_id}@github.local"
    
    encrypted = encrypt_token(token.strip())
    
    conns = db.query(IntegrationConnection).filter(
        IntegrationConnection.provider == "github"
    ).all()
    
    conn = None
    for c in conns:
        if c.sync_cursor and isinstance(c.sync_cursor, dict) and c.sync_cursor.get("user_id") == user_id:
            conn = c
            break
        elif c.account_email == email:
            conn = c
            break
    
    if not conn:
        conn = IntegrationConnection(
            provider="github",
            account_email=email,
            account_name=cand.name if cand else f"User {user_id}",
            connection_status="connected",
            encrypted_access_token=encrypted,
            sync_cursor={"user_id": user_id},
            last_sync_at=datetime.utcnow()
        )
        db.add(conn)
    else:
        conn.encrypted_access_token = encrypted
        conn.connection_status = "connected"
        conn.sync_cursor = {"user_id": user_id}
        conn.updated_at = datetime.utcnow()
        
    db.commit()
    db.refresh(conn)
    return True


def delete_github_token_for_user(user_id: int, db: Session) -> bool:
    """Removes stored GitHub token strictly for the authenticated user."""
    cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).first()
    email = cand.email if cand and cand.email else f"user_{user_id}@github.local"
    
    conns = db.query(IntegrationConnection).filter(
        IntegrationConnection.provider == "github"
    ).all()
    
    deleted = False
    for conn in conns:
        is_user_conn = False
        if conn.sync_cursor and isinstance(conn.sync_cursor, dict) and conn.sync_cursor.get("user_id") == user_id:
            is_user_conn = True
        elif conn.account_email == email:
            is_user_conn = True
            
        if is_user_conn:
            db.delete(conn)
            deleted = True
            
    if deleted:
        db.commit()
    return True


METRIC_HALLUCINATION_PATTERN = re.compile(
    r'(\b\d+%\s*(faster|reduction|increase|improvement|speedup|latency|growth|boost)\b)|'
    r'(\b\d+[\d,]*\+?\s*(users|active users|requests|rps|qps|stars|downloads|dau|mau|clients)\b)|'
    r'(\$\d+[\d,]*(\.\d+)?\s*(k|m|b|million|billion|revenue|arr|mrr)?\b)',
    re.IGNORECASE
)


def validate_and_ground_project_analysis(
    ai_output: Dict[str, Any],
    deterministic_evidence: Dict[str, Any],
    repo_metadata: Dict[str, Any],
    candidate_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Hardens AI output by cross-referencing claims against deterministically collected evidence:
    1. Validates referenced evidence IDs against collected evidence (prunes invalid IDs).
    2. Deterministic technology primacy (manifests & languages take precedence over AI guesses).
    3. Candidate attribution guard (requires verified commit author/owner evidence for contributions).
    4. Anti-metric hallucination filter (flags/downgrades uncorroborated performance and scale claims).
    5. Categorizes claims into DIRECTLY_OBSERVED, AI_DERIVED, CANDIDATE_ATTRIBUTED, and UNVERIFIED.
    """
    detected_technologies = deterministic_evidence.get("detected_technologies") or []
    structure_signals = deterministic_evidence.get("structure_signals") or []
    recent_commits = repo_metadata.get("recent_commits") or []
    raw_readme = repo_metadata.get("readme_content") or ""
    languages = repo_metadata.get("languages") or {}
    full_name = repo_metadata.get("full_name") or repo_metadata.get("repo_name") or ""
    
    # 1. Build authoritative valid evidence IDs set and path map
    valid_evidence_ids = set()
    evidence_id_to_paths: Dict[str, List[str]] = {}

    for t in detected_technologies:
        t_dict = t if isinstance(t, dict) else t.model_dump()
        eid = t_dict.get("evidence_id")
        if eid:
            valid_evidence_ids.add(eid)
            src = t_dict.get("source_file")
            if src:
                evidence_id_to_paths[eid] = [src]

    for s in structure_signals:
        s_dict = s if isinstance(s, dict) else s.model_dump()
        eid = s_dict.get("evidence_id")
        if eid:
            valid_evidence_ids.add(eid)
            paths = s_dict.get("evidence_paths") or []
            evidence_id_to_paths[eid] = paths

    for c in recent_commits:
        c_dict = c if isinstance(c, dict) else c.model_dump()
        eid = c_dict.get("evidence_id") or f"commit_{c_dict.get('sha', '')[:7]}"
        if eid:
            valid_evidence_ids.add(eid)
            evidence_id_to_paths[eid] = [f"commit/{c_dict.get('sha', '')[:7]}"]

    if raw_readme.strip():
        valid_evidence_ids.add("doc_readme")
        evidence_id_to_paths["doc_readme"] = ["README.md"]

    if languages:
        valid_evidence_ids.add("lang_stats")
        evidence_id_to_paths["lang_stats"] = ["languages"]
        for lang in languages.keys():
            lid = f"lang_{lang.lower()}"
            valid_evidence_ids.add(lid)
            evidence_id_to_paths[lid] = ["languages"]

    # 2. Candidate authorship verification
    candidate_contribution_verified = False
    if candidate_name and candidate_name.strip():
        cand_clean = candidate_name.strip().lower()
        cand_tokens = [tok for tok in cand_clean.split() if len(tok) >= 3]
        
        for c in recent_commits:
            c_dict = c if isinstance(c, dict) else c.model_dump()
            c_author = (c_dict.get("author_name") or "").lower()
            c_email = (c_dict.get("author_email") or "").lower()
            if (cand_clean in c_author) or (any(tok in c_author for tok in cand_tokens)) or (c_email and (cand_clean in c_email or any(tok in c_email for tok in cand_tokens))):
                candidate_contribution_verified = True
                break

    if candidate_contribution_verified:
        attribution_note = (
            "Observed commit metadata associated with the candidate's configured GitHub identity. "
            "Note: Git commit author metadata is not definitive proof of human identity."
        )
    else:
        attribution_note = (
            "No commit metadata matching the candidate's configured GitHub identity was observed in recent commits. "
            "Repository ownership or contribution remains unverified."
        )

    # 3. Deterministic Technology Primacy
    manifest_tech_names = []
    for t in detected_technologies:
        t_dict = t if isinstance(t, dict) else t.model_dump()
        name = t_dict.get("name")
        if name and name not in manifest_tech_names:
            manifest_tech_names.append(name)

    grounded_tech = list(manifest_tech_names)
    for l in languages.keys():
        if not any(l.lower() == gt.lower() for gt in grounded_tech):
            grounded_tech.append(l)

    # Strip HTML comments from raw_readme to prevent hidden prompt injections in comments from corroborating technologies
    clean_readme = re.sub(r'<!--.*?-->', '', raw_readme, flags=re.DOTALL)
    readme_lower = clean_readme.lower()
    desc_lower = (repo_metadata.get("description") or "").lower()
    proposed_tech = ai_output.get("technology_stack") or []
    for pt in proposed_tech:
        pt_clean = pt.strip()
        if not pt_clean or any(pt_clean.lower() == gt.lower() for gt in grounded_tech):
            continue
        # Only accept AI guessed technology if explicitly confirmed in README or description
        if pt_clean.lower() in readme_lower or pt_clean.lower() in desc_lower:
            grounded_tech.append(pt_clean)
        else:
            logger.info(f"Filtered uncorroborated AI technology guess: {pt_clean}")

    # 4. Anti-Metric Hallucination Checker
    def has_uncorroborated_metric(text: str) -> bool:
        if not text:
            return False
        matches = METRIC_HALLUCINATION_PATTERN.findall(text)
        if not matches:
            return False
        for m in matches:
            full_match = next((g for g in m if g), "")
            nums = re.findall(r'\d+', full_match)
            for n in nums:
                if n not in raw_readme and not any(n in (c.get("message") if isinstance(c, dict) else getattr(c, "message", "")) for c in recent_commits):
                    return True
        return False

    # 5. Filter referenced evidence IDs
    raw_referenced = ai_output.get("referenced_evidence_ids") or []
    valid_referenced = [eid for eid in raw_referenced if eid in valid_evidence_ids]

    # 6. Process and Ground Claims
    raw_claims = ai_output.get("grounded_claims") or []
    processed_claims: List[Dict[str, Any]] = []

    for c in raw_claims:
        c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else dict(c))
        claim_text = c_dict.get("claim_text", "")
        claim_cat = c_dict.get("category", EvidenceCategory.AI_DERIVED.value)
        claim_eids = [eid for eid in (c_dict.get("evidence_ids") or []) if eid in valid_evidence_ids]
        
        is_metric_hallucinated = has_uncorroborated_metric(claim_text)
        
        if is_metric_hallucinated:
            claim_cat = EvidenceCategory.UNVERIFIED.value
            is_verified = False
            confidence = "unverified"
        elif claim_cat == EvidenceCategory.CANDIDATE_ATTRIBUTED.value or "candidate" in claim_text.lower():
            if not candidate_contribution_verified or not any(eid.startswith("commit_") for eid in claim_eids):
                claim_cat = EvidenceCategory.UNVERIFIED.value
                is_verified = False
                confidence = "unverified"
            else:
                claim_cat = EvidenceCategory.CANDIDATE_ATTRIBUTED.value
                is_verified = True
                confidence = "medium"
        elif claim_cat == EvidenceCategory.DIRECTLY_OBSERVED.value:
            if claim_eids:
                is_verified = True
                confidence = "high"
            else:
                claim_cat = EvidenceCategory.UNVERIFIED.value
                is_verified = False
                confidence = "unverified"
        else: # AI_DERIVED
            is_verified = bool(claim_eids)
            confidence = "medium" if claim_eids else "low"

        supporting_paths = list(c_dict.get("supporting_paths") or [])
        for eid in claim_eids:
            for p in evidence_id_to_paths.get(eid, []):
                if p not in supporting_paths:
                    supporting_paths.append(p)

        processed_claims.append({
            "claim_text": claim_text,
            "category": claim_cat,
            "evidence_ids": claim_eids,
            "supporting_paths": supporting_paths,
            "is_verified": is_verified,
            "confidence": confidence
        })

    # Ensure baseline grounded claims if AI provided none
    if not processed_claims:
        for t in detected_technologies[:5]:
            t_dict = t if isinstance(t, dict) else t.model_dump()
            eid = t_dict.get("evidence_id", "")
            processed_claims.append({
                "claim_text": f"Uses {t_dict.get('name')} for {t_dict.get('category')}.",
                "category": EvidenceCategory.DIRECTLY_OBSERVED.value,
                "evidence_ids": [eid] if eid else [],
                "supporting_paths": [t_dict.get("source_file")] if t_dict.get("source_file") else [],
                "is_verified": True,
                "confidence": "high"
            })

    result = dict(ai_output)
    result["technology_stack"] = grounded_tech
    result["candidate_contribution_verified"] = candidate_contribution_verified
    result["candidate_contribution_evidence"] = attribution_note if not candidate_contribution_verified else f"{ai_output.get('candidate_contribution_evidence', '')}\n\n{attribution_note}".strip()
    result["referenced_evidence_ids"] = valid_referenced
    result["grounded_claims"] = processed_claims
    return result


class GitHubIntelligenceService:
    """
    Coordinates deep repository intelligence collection, manifest parsing,
    tree topology analysis, Groq AI interpretation, and profile integration.
    """

    async def collect_repository_intelligence(
        self,
        owner: str,
        repo: str,
        client: GitHubApiClient,
        candidate_name: Optional[str] = None,
        cached_intelligence: Optional[Dict[str, Any]] = None,
        force_refresh: bool = False
    ) -> GitHubProjectIntelligence:
        """
        Collects comprehensive engineering intelligence for a single repository.
        Uses cached data if commit SHA / content hash is unchanged.
        """
        # 1. Fetch core repository metadata
        repo_data = await client.get_repo(owner, repo)
        default_branch = repo_data.get("default_branch") or "main"
        
        # 2. Fetch languages breakdown
        languages = await client.get_languages(owner, repo)
        
        # 3. Fetch recent commits (up to 10)
        raw_commits = await client.get_commits(owner, repo, per_page=10)
        commit_models: List[RepositoryCommitMetadata] = []
        top_sha = ""
        for rc in raw_commits:
            sha = rc.get("sha", "")
            if not top_sha and sha:
                top_sha = sha
            commit_info = rc.get("commit", {})
            author_info = commit_info.get("author", {})
            c_sha_short = sha[:7]
            commit_models.append(RepositoryCommitMetadata(
                sha=c_sha_short,
                message=commit_info.get("message", "").split("\n")[0][:120],
                author_name=author_info.get("name", "Unknown"),
                author_email=author_info.get("email"),
                author_date=author_info.get("date"),
                evidence_id=f"commit_{c_sha_short}"
            ))

        # Compute content hash
        hash_input = f"{top_sha}:{repo_data.get('pushed_at')}:{repo_data.get('size')}"
        content_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()

        # Check cache validity
        if not force_refresh and cached_intelligence:
            if cached_intelligence.get("content_hash") == content_hash and cached_intelligence.get("status") == RepositoryAnalysisState.COMPLETED.value:
                logger.info(f"Using cached intelligence for {owner}/{repo} (SHA {top_sha[:7]})")
                cached_data = dict(cached_intelligence)
                cached_data["is_cached"] = True
                return GitHubProjectIntelligence(**cached_data)

        # 4. Fetch Git Tree to locate manifests and inspect directory topology
        tree_items = await client.get_tree(owner, repo, branch=default_branch, recursive=True)
        tree_paths = [item.get("path") for item in tree_items if item.get("path")]

        # 5. Extract structural topology signals
        structure_signals = analyze_repository_structure(tree_paths)

        # 6. Locate and fetch manifest files
        manifest_files: Dict[str, str] = {}
        candidate_manifest_paths = []
        for path in tree_paths:
            basename = path.split("/")[-1].lower()
            if basename in KNOWN_MANIFESTS or path.startswith(".github/workflows/"):
                candidate_manifest_paths.append(path)

        # Limit to top 15 manifests to keep API calls bounded
        for manifest_path in candidate_manifest_paths[:15]:
            content = await client.get_file_content(owner, repo, manifest_path)
            if content:
                manifest_files[manifest_path] = content

        # 7. Deterministic Manifest Parsing
        detected_technologies = parse_manifests(manifest_files)

        # 8. Fetch README
        readme_content = await client.get_readme(owner, repo)
        readme_summary = readme_content[:500] if readme_content else None

        # Build partial intelligence
        full_name = repo_data.get("full_name") or f"{owner}/{repo}"
        html_url = repo_data.get("html_url") or f"https://github.com/{owner}/{repo}"
        
        intel = GitHubProjectIntelligence(
            repo_name=repo_data.get("name") or repo,
            full_name=full_name,
            html_url=html_url,
            description=repo_data.get("description") or "",
            default_branch=default_branch,
            is_fork=repo_data.get("fork", False),
            is_archived=repo_data.get("archived", False),
            visibility=repo_data.get("visibility", "public"),
            primary_language=repo_data.get("language"),
            languages=languages,
            topics=repo_data.get("topics", []),
            stars=repo_data.get("stargazers_count", 0),
            forks=repo_data.get("forks_count", 0),
            open_issues=repo_data.get("open_issues_count", 0),
            license=repo_data.get("license", {}).get("spdx_id") if repo_data.get("license") else None,
            created_at=repo_data.get("created_at"),
            updated_at=repo_data.get("updated_at"),
            pushed_at=repo_data.get("pushed_at"),
            detected_technologies=detected_technologies,
            structure_signals=structure_signals,
            recent_commits=commit_models,
            readme_summary=readme_summary,
            content_hash=content_hash,
            last_synced_at=datetime.utcnow().isoformat(),
            status=RepositoryAnalysisState.COMPLETED,
            is_cached=False
        )

        # 9. AI-Powered Project Understanding via Groq
        ai_repo_payload = {
            "repo_name": intel.repo_name,
            "full_name": intel.full_name,
            "description": intel.description,
            "primary_language": intel.primary_language,
            "languages": intel.languages,
            "stars": intel.stars,
            "forks": intel.forks,
            "readme_content": readme_content,
            "recent_commits": [c.model_dump() for c in commit_models]
        }
        deterministic_payload = {
            "detected_technologies": [t.model_dump() for t in detected_technologies],
            "structure_signals": [s.model_dump() for s in structure_signals]
        }

        try:
            ai_res = await ai_service.analyze_github_repository(
                repo_data=ai_repo_payload,
                deterministic_evidence=deterministic_payload,
                candidate_name=candidate_name
            )
            if ai_res.get("success"):
                raw_data = ai_res.get("data") or {}
                grounded_data = validate_and_ground_project_analysis(
                    ai_output=raw_data,
                    deterministic_evidence=deterministic_payload,
                    repo_metadata=ai_repo_payload,
                    candidate_name=candidate_name
                )
                intel.ai_insights = grounded_data
                intel.status = RepositoryAnalysisState.COMPLETED
                intel.is_stale = False
            else:
                # Groq returned failure
                if cached_intelligence and cached_intelligence.get("ai_insights"):
                    logger.info(f"Groq failed for {full_name}, preserving previous valid analysis as stale")
                    intel.ai_insights = cached_intelligence.get("ai_insights")
                    intel.is_stale = True
                    intel.status = RepositoryAnalysisState.COMPLETED
                    intel.error_message = f"AI reasoning unavailable, using previous analysis: {ai_res.get('error')}"
                else:
                    intel.status = RepositoryAnalysisState.ANALYSIS_UNAVAILABLE
                    intel.error_message = ai_res.get("error", "AI reasoning unavailable")
        except Exception as e:
            logger.warning(f"Groq project analysis failed for {full_name}: {e}")
            if cached_intelligence and cached_intelligence.get("ai_insights"):
                logger.info(f"Groq exception for {full_name}, preserving previous valid analysis as stale")
                intel.ai_insights = cached_intelligence.get("ai_insights")
                intel.is_stale = True
                intel.status = RepositoryAnalysisState.COMPLETED
                intel.error_message = f"AI reasoning failed, using previous analysis: {str(e)}"
            else:
                intel.status = RepositoryAnalysisState.ANALYSIS_UNAVAILABLE
                intel.error_message = str(e)

        return intel

    async def sync_candidate_repositories(
        self,
        user_id: int,
        username: str,
        db: Session,
        token: Optional[str] = None,
        force_refresh: bool = False
    ) -> List[GitHubProjectIntelligence]:
        """
        Synchronizes candidate's public repositories, extracts deep intelligence,
        and saves cache to candidate profile.
        Uses PostgreSQL row-level lock (with_for_update) to prevent concurrency races.
        Handles token revocation (401) with reconnect_required state.
        Preserves existing data on partial failures.
        """
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).with_for_update().first()
        if not cand:
            raise ValueError(f"Candidate profile for user {user_id} not found")

        resolved_token = token or get_github_token_for_user(user_id, db)
        client = GitHubApiClient(token=resolved_token)

        # Existing cached intelligence map
        github_data = dict(cand.github_data or {})
        cached_intel_map = dict(github_data.get("intelligence", {}))

        # List candidate repositories
        clean_user = username.strip().lstrip("@").replace("https://github.com/", "").rstrip("/")
        
        try:
            repos = await client.list_user_repos(clean_user, per_page=30)
        except GitHubTokenRevokedError as tre:
            logger.warning(f"GitHub token revoked for user {user_id}: {tre}")
            github_data["token_status"] = "reconnect_required"
            cand.github_data = github_data
            flag_modified(cand, "github_data")
            
            # Update connection status
            conns = db.query(IntegrationConnection).filter(
                IntegrationConnection.provider == "github"
            ).all()
            for c in conns:
                if (c.sync_cursor and c.sync_cursor.get("user_id") == user_id) or c.account_email == cand.email:
                    c.connection_status = "reconnect_required"
            db.commit()
            raise tre
            
        analyzed_list: List[GitHubProjectIntelligence] = []
        updated_intel_map: Dict[str, Any] = dict(cached_intel_map)

        for r in repos:
            if r.get("fork"):
                continue # Focus primarily on non-forked original work
                
            owner = r.get("owner", {}).get("login", clean_user)
            repo_name = r.get("name")
            full_name = r.get("full_name") or f"{owner}/{repo_name}"

            cached_item = cached_intel_map.get(full_name)
            
            try:
                intel = await self.collect_repository_intelligence(
                    owner=owner,
                    repo=repo_name,
                    client=client,
                    candidate_name=cand.name,
                    cached_intelligence=cached_item,
                    force_refresh=force_refresh
                )
                analyzed_list.append(intel)
                updated_intel_map[full_name] = intel.model_dump()
            except GitHubTokenRevokedError as tre:
                # Token revoked during repo collection halts sync immediately
                github_data["token_status"] = "reconnect_required"
                cand.github_data = github_data
                flag_modified(cand, "github_data")
                db.commit()
                raise tre
            except Exception as e:
                logger.error(f"Failed to analyze repository {full_name}: {e}")
                # Partial failure resilience: preserve previous cached intelligence if present
                if cached_item and cached_item.get("status") == RepositoryAnalysisState.COMPLETED.value:
                    logger.info(f"Preserving previous cached intelligence for {full_name} as stale")
                    stale_data = dict(cached_item)
                    stale_data["is_stale"] = True
                    stale_data["error_message"] = f"Fetch failed, preserved cached data: {str(e)}"
                    stale_intel = GitHubProjectIntelligence(**stale_data)
                    analyzed_list.append(stale_intel)
                    updated_intel_map[full_name] = stale_intel.model_dump()
                else:
                    fallback = GitHubProjectIntelligence(
                        repo_name=repo_name,
                        full_name=full_name,
                        html_url=r.get("html_url", f"https://github.com/{full_name}"),
                        description=r.get("description", ""),
                        primary_language=r.get("language"),
                        stars=r.get("stargazers_count", 0),
                        forks=r.get("forks_count", 0),
                        status=RepositoryAnalysisState.FAILED,
                        error_message=str(e),
                        last_synced_at=datetime.utcnow().isoformat()
                    )
                    analyzed_list.append(fallback)
                    updated_intel_map[full_name] = fallback.model_dump()

        # Update candidate profile github_data
        github_data["username"] = clean_user
        github_data["last_synced_at"] = datetime.utcnow().isoformat()
        github_data["intelligence"] = updated_intel_map
        github_data["has_custom_token"] = bool(resolved_token)
        github_data["rate_limit"] = client.get_rate_limit_info()
        github_data["token_status"] = "active" if resolved_token else None

        cand.github_username = clean_user
        cand.github_url = f"https://github.com/{clean_user}"
        cand.github_data = dict(github_data)
        flag_modified(cand, "github_data")
        cand.evidence_version = (cand.evidence_version or 1) + 1
        cand.updated_at = datetime.utcnow()
        db.commit()
        snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
        db.refresh(cand)

        return analyzed_list

    def import_repository_to_candidate_profile(
        self,
        user_id: int,
        repo_urls: List[str],
        db: Session,
        overwrite_curated: bool = False
    ) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Imports analyzed repositories into CandidateProfile.projects.
        Uses PostgreSQL row-level lock (with_for_update) to prevent race conditions.
        Strictly preserves curated descriptions, bullets, and project IDs
        unless overwrite_curated=True is explicitly set.
        """
        cand = db.query(CandidateProfile).filter(CandidateProfile.user_id == user_id).with_for_update().first()
        if not cand:
            raise ValueError(f"Candidate profile for user {user_id} not found")

        curr_projects = list(cand.projects or [])
        github_data = cand.github_data or {}
        intel_map = github_data.get("intelligence", {})

        # Build lookup of existing projects by canonical URL
        existing_by_url: Dict[str, Dict[str, Any]] = {}
        for p in curr_projects:
            url = canonicalize_github_url(p.get("url", ""))
            if url:
                existing_by_url[url] = p

        imported_count = 0
        updated_projects = list(curr_projects)

        for raw_url in repo_urls:
            canonical_url = canonicalize_github_url(raw_url)
            if not canonical_url:
                continue

            # Find matching intelligence by URL or repo path
            intel_dict = None
            for fname, item in intel_map.items():
                if canonicalize_github_url(item.get("html_url", "")) == canonical_url:
                    intel_dict = item
                    break

            # Extract detected tech
            detected_techs = []
            if intel_dict:
                for t in intel_dict.get("detected_technologies", []):
                    t_name = t.get("name") if isinstance(t, dict) else getattr(t, "name", str(t))
                    if t_name and t_name not in detected_techs:
                        detected_techs.append(t_name)
                if not detected_techs and intel_dict.get("primary_language"):
                    detected_techs.append(intel_dict.get("primary_language"))

            # Case A: Pre-existing project
            if canonical_url in existing_by_url:
                # Locate project index in updated_projects
                idx = None
                for i, p in enumerate(updated_projects):
                    if canonicalize_github_url(p.get("url", "")) == canonical_url:
                        idx = i
                        break

                target_p = dict(updated_projects[idx]) if idx is not None else dict(existing_by_url[canonical_url])
                # Merge technologies safely without duplicates
                curr_tech = list(target_p.get("tech_stack", []))
                curr_tech_lower = {t.lower() for t in curr_tech}
                for dt in detected_techs:
                    if dt.lower() not in curr_tech_lower:
                        curr_tech.append(dt)
                        curr_tech_lower.add(dt.lower())
                target_p["tech_stack"] = curr_tech
                target_p["is_manually_verified"] = True

                # Curated fields strictly preserved unless overwrite_curated=True
                if overwrite_curated and intel_dict:
                    ai_ins = intel_dict.get("ai_insights") or {}
                    if ai_ins.get("project_purpose"):
                        target_p["description"] = ai_ins.get("project_purpose")
                    elif intel_dict.get("description"):
                        target_p["description"] = intel_dict.get("description")
                    if ai_ins.get("key_features"):
                        target_p["bullets"] = ai_ins.get("key_features")[:4]

                if idx is not None:
                    updated_projects[idx] = target_p
                existing_by_url[canonical_url] = target_p
                imported_count += 1
            else:
                # Case B: New project
                repo_name = canonical_url.split("/")[-1]
                title = repo_name.replace("-", " ").replace("_", " ").title()
                desc = f"Open source software project {repo_name}."
                bullets = []

                if intel_dict:
                    title = intel_dict.get("repo_name", repo_name).replace("-", " ").replace("_", " ").title()
                    ai_ins = intel_dict.get("ai_insights") or {}
                    desc = ai_ins.get("project_purpose") or intel_dict.get("description") or desc
                    bullets = ai_ins.get("key_features", [])[:4]

                new_proj = {
                    "id": f"proj_{uuid.uuid4().hex[:8]}",
                    "title": title,
                    "description": desc,
                    "tech_stack": detected_techs or ["Software Engineering"],
                    "url": canonical_url,
                    "bullets": bullets,
                    "source": "github_intelligence",
                    "is_manually_verified": False
                }
                updated_projects.append(new_proj)
                existing_by_url[canonical_url] = new_proj
                imported_count += 1

        cand.projects = [dict(p) for p in updated_projects]
        flag_modified(cand, "projects")
        cand.evidence_version = (cand.evidence_version or 1) + 1
        cand.updated_at = datetime.utcnow()
        db.commit()
        snapshot_manager.invalidate_candidate_snapshots(user_id=cand.user_id, db=db)
        db.refresh(cand)

        return imported_count, cand.projects


github_intelligence_service = GitHubIntelligenceService()
