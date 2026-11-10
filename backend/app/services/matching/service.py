"""
Core Matching Service for CareerOS Matching Intelligence.
Coordinates deterministic job description parsing, unified candidate evidence gathering,
requirement matching, explainable scoring, skill gap analysis, and Groq semantic synthesis.
Handles content-hash caching, PostgreSQL row locking, and stale cache preservation.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.candidate_opportunity_match import CandidateOpportunityMatch
from backend.app.schemas.matching import (
    ProfileMatchResult,
    ParsedJobDescription,
    UnifiedCandidateEvidence
)
from backend.app.services.matching.release_registry import (
    MATCHING_ENGINE_RELEASES,
    DEFAULT_ACTIVE_ENGINE_VERSION,
    DEFAULT_ACTIVE_ENGINE_GENERATION,
    get_canonical_engine_generation,
    validate_deployment_engine_release,
)
from backend.app.services.matching.jd_parser import (
    parse_job_description_deterministic,
    compute_job_description_hash
)
from backend.app.services.matching.evidence_builder import (
    build_unified_candidate_evidence,
    compute_candidate_evidence_hash
)
from backend.app.services.matching.matching_engine import calculate_profile_match
from backend.app.services.matching.gap_analyzer import analyze_skill_gaps
from backend.app.services.ai.service import ai_service
from backend.app.services.ai.types import TaskType

logger = logging.getLogger(__name__)


MATCHING_ENGINE_VERSION = DEFAULT_ACTIVE_ENGINE_VERSION
MATCHING_ENGINE_GENERATION = DEFAULT_ACTIVE_ENGINE_GENERATION
ENGINE_VERSION_GENERATION_MAP = MATCHING_ENGINE_RELEASES

def get_engine_generation(version: str) -> int:
    return get_canonical_engine_generation(version)


class MatchingService:
    """
    Evidence-based job-to-candidate matching service.
    Guarantees deterministic scoring, candidate-scoped isolation, and zero-fabrication safety.
    """
    MATCHING_ENGINE_VERSION = MATCHING_ENGINE_VERSION
    MATCHING_ENGINE_GENERATION = MATCHING_ENGINE_GENERATION

    async def evaluate_match(
        self,
        candidate: CandidateProfile,
        opportunity: Opportunity,
        db: Session,
        force_refresh: bool = False,
        use_ai: bool = True
    ) -> ProfileMatchResult:
        """
        Calculates or retrieves candidate-scoped Profile Match Score and evidence-based analysis.
        Uses PostgreSQL row-level locking on candidate profile and CandidateOpportunityMatch
        to guarantee multi-candidate isolation and prevent race conditions.
        """
        caller_cand_ev = getattr(candidate, "evidence_version", None)
        caller_opp_cv = getattr(opportunity, "content_version", None)

        cand = db.query(CandidateProfile).filter(CandidateProfile.id == candidate.id).with_for_update().first()
        if not cand:
            raise ValueError(f"Candidate {candidate.id} not found")

        # For private opportunities, lock opportunity row; for public opportunities, fetch record
        if opportunity.user_id is not None and opportunity.user_id == cand.user_id:
            opp = db.query(Opportunity).filter(Opportunity.id == opportunity.id).with_for_update().first()
        else:
            opp = db.query(Opportunity).filter(Opportunity.id == opportunity.id).first()
        if not opp:
            raise ValueError(f"Opportunity {opportunity.id} not found")

        # Query candidate-scoped persistent match record with row lock
        match_rec = (
            db.query(CandidateOpportunityMatch)
            .filter(
                CandidateOpportunityMatch.user_id == cand.user_id,
                CandidateOpportunityMatch.opportunity_id == opp.id
            )
            .with_for_update()
            .first()
        )

        existing_analysis = match_rec.match_analysis if match_rec else {}
        has_cached_score = match_rec is not None and "profile_match_score" in existing_analysis

        current_cand_ev = getattr(cand, "evidence_version", 1) or 1
        current_opp_cv = getattr(opp, "content_version", 1) or 1

        cand_evidence_version = caller_cand_ev if caller_cand_ev is not None else current_cand_ev
        opp_content_version = caller_opp_cv if caller_opp_cv is not None else current_opp_cv

        # Target candidate and opportunity content for evaluation (using caller snapshot if provided)
        target_cand = candidate if hasattr(candidate, "skills") and candidate.skills is not None else cand
        target_opp = opportunity if hasattr(opportunity, "description") and opportunity.description is not None else opp

        # Pre-computation check: If caller's evaluation snapshot is already stale vs canonical DB state, do NOT persist
        is_stale_input = (cand_evidence_version != current_cand_ev) or (opp_content_version != current_opp_cv)
        if is_stale_input:
            logger.info(
                f"Stale evaluation rejected for user {cand.user_id} and opp {opp.id}: "
                f"input version mismatch (cand_ev: {cand_evidence_version} vs current {current_cand_ev}, "
                f"opp_cv: {opp_content_version} vs current {current_opp_cv})."
            )
            if match_rec and match_rec.match_analysis:
                prior_data = dict(match_rec.match_analysis)
                prior_data["is_stale"] = True
                return ProfileMatchResult(**prior_data)

            # Compute in-memory for caller but NEVER persist obsolete snapshot to database
            candidate_evidence = build_unified_candidate_evidence(target_cand)
            parsed_jd = parse_job_description_deterministic(
                title=target_opp.title or opp.title,
                description=target_opp.description or opp.description or "",
                company=target_opp.company_name or opp.company_name,
                location=target_opp.normalized_location or target_opp.location or opp.normalized_location or opp.location
            )
            match_result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)
            match_result.engine_version = MATCHING_ENGINE_VERSION
            match_result.user_id = cand.user_id
            match_result.skill_gaps = analyze_skill_gaps(req_matches)
            match_result.is_stale = True
            return match_result

        try:
            # 1. Build unified candidate evidence and content hash
            candidate_evidence = build_unified_candidate_evidence(target_cand)
            cand_hash = candidate_evidence.content_hash

            # 2. Parse job description and content hash
            parsed_jd = parse_job_description_deterministic(
                title=target_opp.title or opp.title,
                description=target_opp.description or opp.description or "",
                company=target_opp.company_name or opp.company_name,
                location=target_opp.normalized_location or target_opp.location or opp.normalized_location or opp.location
            )
            opp_hash = parsed_jd.content_hash

            # 3. Check Candidate-Scoped Caching Validity
            if match_rec and not force_refresh and has_cached_score:
                cached_cand_hash = match_rec.candidate_content_hash
                cached_opp_hash = match_rec.opportunity_content_hash
                cached_engine_version = match_rec.engine_version

                # If private opportunity has an outdated engine_version in match_analysis, treat as mismatched
                if opp.user_id == cand.user_id and opp.match_analysis:
                    opp_cached_ver = opp.match_analysis.get("engine_version")
                    if opp_cached_ver and opp_cached_ver != MATCHING_ENGINE_VERSION:
                        cached_engine_version = opp_cached_ver

                if (
                    cached_cand_hash == cand_hash
                    and cached_opp_hash == opp_hash
                    and cached_engine_version == MATCHING_ENGINE_VERSION
                ):
                    logger.info(f"Serving candidate-scoped cached match for user {cand.user_id} and opp {opp.id}")
                    cached_data = dict(existing_analysis)
                    cached_data["is_cached"] = True
                    cached_data["is_stale"] = False
                    return ProfileMatchResult(**cached_data)

            # 4. Deterministic Requirement Matching and Scoring
            match_result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)
            match_result.engine_version = MATCHING_ENGINE_VERSION
            match_result.user_id = cand.user_id

            # 5. Skill Gap Analysis
            skill_gaps = analyze_skill_gaps(req_matches)
            match_result.skill_gaps = skill_gaps

            # 6. Optional Qualitative AI Synthesis (Groq)
            # CRITICAL RULE: AI NEVER calculates or modifies the Profile Match Score!
            if use_ai:
                try:
                    ai_prompt = (
                        f"Job Title: {opp.title} at {opp.company_name}\n"
                        f"Deterministic Profile Match Score: {match_result.profile_match_score}/100\n"
                        f"Category Scores: {match_result.category_scores}\n"
                        f"Top Gaps: {[g.skill_name for g in skill_gaps[:3]]}\n\n"
                        f"Provide a 2-3 sentence strategic executive summary of why this candidate aligns "
                        f"and what their single highest-leverage interview talking point should be."
                    )
                    ai_resp = await ai_service.router.execute(
                        task_type=TaskType.COMPATIBILITY_EXPLANATION,
                        prompt=ai_prompt,
                        temperature=0.2
                    )
                    if ai_resp and ai_resp.content.strip():
                        synthesis_text = ai_resp.content.strip()
                        match_result.scoring_explanation = f"{match_result.scoring_explanation}\n\nAI Strategic Synthesis:\n{synthesis_text}"
                except Exception as ai_err:
                    logger.warning(f"Groq strategic explanation unavailable ({ai_err}); using deterministic explanation.")

            # 7. Persist Candidate-Scoped Match Record using atomic PostgreSQL upsert with stale-write protection
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            result_dict = match_result.model_dump()
            current_eng_gen = get_engine_generation(MATCHING_ENGINE_VERSION)

            # Revalidate current canonical database state before persistence
            latest_cand_ev = db.query(CandidateProfile.evidence_version).filter(CandidateProfile.id == cand.id).scalar()
            latest_opp_cv = db.query(Opportunity.content_version).filter(Opportunity.id == opp.id).scalar()
            latest_cand_ev = 1 if latest_cand_ev is None else latest_cand_ev
            latest_opp_cv = 1 if latest_opp_cv is None else latest_opp_cv

            if (latest_cand_ev != cand_evidence_version) or (latest_opp_cv != opp_content_version):
                logger.info(
                    f"Stale evaluation rejected for user {cand.user_id} and opp {opp.id}: "
                    f"database state mutated during evaluation (cand_ev: {cand_evidence_version} vs latest {latest_cand_ev}, "
                    f"opp_cv: {opp_content_version} vs latest {latest_opp_cv})."
                )
                match_rec = db.query(CandidateOpportunityMatch).filter(
                    CandidateOpportunityMatch.user_id == cand.user_id,
                    CandidateOpportunityMatch.opportunity_id == opp.id
                ).first()
                if match_rec and match_rec.match_analysis:
                    prior_data = dict(match_rec.match_analysis)
                    prior_data["is_stale"] = True
                    return ProfileMatchResult(**prior_data)
                match_result.is_stale = True
                return match_result

            # Atomic conditional upsert enforcing canonical input state and monotonic engine generation
            upsert_sql = text("""
                INSERT INTO candidate_opportunity_matches (
                    user_id, candidate_id, opportunity_id, match_score, eligibility_status,
                    match_analysis, candidate_content_hash, opportunity_content_hash,
                    candidate_evidence_version, opportunity_content_version,
                    engine_version, engine_generation, created_at, updated_at
                )
                SELECT
                    c.user_id, c.id, o.id, :match_score, :eligibility_status,
                    CAST(:match_analysis AS json), :cand_hash, :opp_hash,
                    :cand_ev, :opp_cv,
                    :engine_version, :engine_generation, :now, :now
                FROM candidate_profiles c, opportunities o
                WHERE c.id = :cid AND o.id = :oid
                  AND COALESCE(c.evidence_version, 1) = :cand_ev
                  AND COALESCE(o.content_version, 1) = :opp_cv
                ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
                DO UPDATE SET
                    candidate_id = EXCLUDED.candidate_id,
                    match_score = EXCLUDED.match_score,
                    eligibility_status = EXCLUDED.eligibility_status,
                    match_analysis = EXCLUDED.match_analysis,
                    candidate_content_hash = EXCLUDED.candidate_content_hash,
                    opportunity_content_hash = EXCLUDED.opportunity_content_hash,
                    candidate_evidence_version = EXCLUDED.candidate_evidence_version,
                    opportunity_content_version = EXCLUDED.opportunity_content_version,
                    engine_version = EXCLUDED.engine_version,
                    engine_generation = EXCLUDED.engine_generation,
                    updated_at = EXCLUDED.updated_at
                WHERE
                    EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
                    AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
                    AND EXCLUDED.engine_generation >= candidate_opportunity_matches.engine_generation
                RETURNING candidate_opportunity_matches.id;
            """)

            res = db.execute(upsert_sql, {
                "match_score": match_result.profile_match_score,
                "eligibility_status": match_result.eligibility_status,
                "match_analysis": json.dumps(result_dict),
                "cand_hash": cand_hash,
                "opp_hash": opp_hash,
                "cand_ev": cand_evidence_version,
                "opp_cv": opp_content_version,
                "engine_version": MATCHING_ENGINE_VERSION,
                "engine_generation": current_eng_gen,
                "now": now,
                "cid": cand.id,
                "oid": opp.id
            }).first()

            if res is None:
                # Stale write rejected by conditional upsert (a newer version is already in DB)
                logger.info(f"Stale evaluation rejected by conditional upsert for user {cand.user_id} and opp {opp.id}.")
                match_rec = db.query(CandidateOpportunityMatch).filter(
                    CandidateOpportunityMatch.user_id == cand.user_id,
                    CandidateOpportunityMatch.opportunity_id == opp.id
                ).first()
                if match_rec and match_rec.match_analysis:
                    prior_data = dict(match_rec.match_analysis)
                    prior_data["is_stale"] = True
                    return ProfileMatchResult(**prior_data)
                match_result.is_stale = True
                return match_result

            match_rec = db.query(CandidateOpportunityMatch).filter(
                CandidateOpportunityMatch.id == res[0]
            ).first()

            # Candidate-agnostic extracted requirements stored on opportunity
            opp.extracted_data = parsed_jd.model_dump()

            # Backward compatibility: For private opportunities owned by this candidate, update opp
            if opp.user_id is not None and opp.user_id == cand.user_id:
                opp.match_score = match_result.profile_match_score
                opp.eligibility_status = match_result.eligibility_status
                opp.match_analysis = result_dict
                opp.updated_at = now

            db.commit()
            if match_rec:
                db.refresh(match_rec)

            return match_result

        except Exception as e:
            logger.error(f"Failed to calculate match for opportunity {opp.id} (user {cand.user_id}): {e}")
            try:
                db.rollback()
            except Exception:
                pass
            # Partial Failure Resilience: Preserve prior valid completed analysis as stale
            if has_cached_score and match_rec:
                logger.info(f"Preserving prior match analysis as stale for user {cand.user_id} and opp {opp.id}")
                stale_data = dict(existing_analysis)
                stale_data["is_stale"] = True
                stale_data["is_cached"] = True
                return ProfileMatchResult(**stale_data)
            raise

    async def evaluate_matches_batch(
        self,
        candidate: CandidateProfile,
        opportunities: List[Opportunity],
        db: Session,
        force_refresh: bool = False,
        use_ai: bool = False
    ) -> Dict[int, Tuple[ProfileMatchResult, CandidateOpportunityMatch]]:
        """
        Batched deterministic evaluation of multiple opportunities for a single candidate.
        Optimized for high-throughput query efficiency:
        - Locks and loads CandidateProfile once
        - Builds UnifiedCandidateEvidence once
        - Fetches existing CandidateOpportunityMatch records in a single IN query
        - Reuses valid cached records and computes deterministic matches for stale/new
        - Commits all updates in a single atomic database transaction
        """
        if not opportunities:
            return {}

        cand = db.query(CandidateProfile).filter(CandidateProfile.id == candidate.id).with_for_update().first()
        if not cand:
            raise ValueError(f"Candidate {candidate.id} not found")

        opp_ids = [o.id for o in opportunities]

        # Batch load existing match records with row-level locks
        existing_matches = (
            db.query(CandidateOpportunityMatch)
            .filter(
                CandidateOpportunityMatch.user_id == cand.user_id,
                CandidateOpportunityMatch.opportunity_id.in_(opp_ids)
            )
            .with_for_update()
            .all()
        )
        match_by_opp_id = {m.opportunity_id: m for m in existing_matches}

        candidate_evidence = build_unified_candidate_evidence(cand)
        cand_hash = candidate_evidence.content_hash
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        results: Dict[int, Tuple[ProfileMatchResult, CandidateOpportunityMatch]] = {}
        upsert_values: List[Dict[str, Any]] = []
        computed_results: Dict[int, ProfileMatchResult] = {}

        for opp in opportunities:
            match_rec = match_by_opp_id.get(opp.id)
            existing_analysis = match_rec.match_analysis if match_rec else {}
            has_cached_score = match_rec is not None and "profile_match_score" in existing_analysis

            # Parse job description
            parsed_jd = parse_job_description_deterministic(
                title=opp.title,
                description=opp.description or "",
                company=opp.company_name,
                location=opp.normalized_location or opp.location
            )
            opp_hash = parsed_jd.content_hash

            # Cache validation
            if match_rec and not force_refresh and has_cached_score:
                cached_cand_hash = match_rec.candidate_content_hash
                cached_opp_hash = match_rec.opportunity_content_hash
                cached_engine_version = match_rec.engine_version

                if (
                    cached_cand_hash == cand_hash
                    and cached_opp_hash == opp_hash
                    and cached_engine_version == MATCHING_ENGINE_VERSION
                ):
                    cached_data = dict(existing_analysis)
                    cached_data["is_cached"] = True
                    cached_data["is_stale"] = False
                    match_result = ProfileMatchResult(**cached_data)
                    results[opp.id] = (match_result, match_rec)
                    continue

            # Deterministic requirement matching and scoring
            match_result, req_matches = calculate_profile_match(parsed_jd, candidate_evidence)
            match_result.engine_version = MATCHING_ENGINE_VERSION
            match_result.user_id = cand.user_id

            # Skill gap analysis
            skill_gaps = analyze_skill_gaps(req_matches)
            match_result.skill_gaps = skill_gaps

            result_dict = match_result.model_dump()

            caller_cand_ev = getattr(candidate, "evidence_version", None)
            caller_opp_cv = getattr(opp, "content_version", None)
            cand_evidence_version = caller_cand_ev if caller_cand_ev is not None else (getattr(cand, "evidence_version", 1) or 1)
            opp_content_version = caller_opp_cv if caller_opp_cv is not None else (getattr(opp, "content_version", 1) or 1)

            upsert_values.append({
                "user_id": cand.user_id,
                "candidate_id": cand.id,
                "opportunity_id": opp.id,
                "match_score": match_result.profile_match_score,
                "eligibility_status": match_result.eligibility_status,
                "match_analysis": result_dict,
                "candidate_content_hash": cand_hash,
                "opportunity_content_hash": opp_hash,
                "candidate_evidence_version": cand_evidence_version,
                "opportunity_content_version": opp_content_version,
                "engine_version": MATCHING_ENGINE_VERSION,
                "engine_generation": get_engine_generation(MATCHING_ENGINE_VERSION),
                "created_at": now,
                "updated_at": now,
                "extracted_data": parsed_jd.model_dump()
            })
            computed_results[opp.id] = match_result

        # Revalidate candidate profile before batch persistence
        initial_cand_ev = getattr(cand, "evidence_version", 1) or 1
        current_cand_ev = db.query(CandidateProfile.evidence_version).filter(CandidateProfile.id == cand.id).scalar()
        current_cand_ev = 1 if current_cand_ev is None else current_cand_ev

        if current_cand_ev != initial_cand_ev:
            logger.info(
                f"Stale batch evaluation rejected for user {cand.user_id}: "
                f"candidate profile mutated during evaluation (cand_ev: {initial_cand_ev} vs current {current_cand_ev})."
            )
            for opp in opportunities:
                if opp.id not in results:
                    existing = match_by_opp_id.get(opp.id)
                    match_res = computed_results.get(opp.id)
                    if existing and existing.match_analysis:
                        stale_res = ProfileMatchResult(**existing.match_analysis)
                        stale_res.is_stale = True
                        results[opp.id] = (stale_res, existing)
                    elif match_res:
                        match_res.is_stale = True
            db.commit()
            return results

        if upsert_values:
            # Revalidate opportunities: filter out any opp whose content_version changed in DB
            opp_ids_to_check = [it["opportunity_id"] for it in upsert_values]
            current_opp_rows = db.query(Opportunity.id, Opportunity.content_version).filter(
                Opportunity.id.in_(opp_ids_to_check)
            ).all()
            current_opp_cv_map = {row[0]: (1 if row[1] is None else row[1]) for row in current_opp_rows}

            valid_upserts = []
            for it in upsert_values:
                opp_id = it["opportunity_id"]
                cur_cv = current_opp_cv_map.get(opp_id, 1)
                if cur_cv == it["opportunity_content_version"]:
                    valid_upserts.append(it)
                else:
                    logger.info(
                        f"Stale evaluation rejected in batch for opp {opp_id}: "
                        f"content mutated during evaluation ({it['opportunity_content_version']} vs {cur_cv})."
                    )

            upsert_sql = text("""
                INSERT INTO candidate_opportunity_matches (
                    user_id, candidate_id, opportunity_id, match_score, eligibility_status,
                    match_analysis, candidate_content_hash, opportunity_content_hash,
                    candidate_evidence_version, opportunity_content_version,
                    engine_version, engine_generation, created_at, updated_at
                )
                SELECT
                    c.user_id, c.id, o.id, :match_score, :eligibility_status,
                    CAST(:match_analysis AS json), :cand_hash, :opp_hash,
                    :cand_ev, :opp_cv,
                    :engine_version, :engine_generation, :now, :now
                FROM candidate_profiles c, opportunities o
                WHERE c.id = :cid AND o.id = :oid
                  AND COALESCE(c.evidence_version, 1) = :cand_ev
                  AND COALESCE(o.content_version, 1) = :opp_cv
                ON CONFLICT ON CONSTRAINT uq_candidate_opportunity_match_user_opp
                DO UPDATE SET
                    candidate_id = EXCLUDED.candidate_id,
                    match_score = EXCLUDED.match_score,
                    eligibility_status = EXCLUDED.eligibility_status,
                    match_analysis = EXCLUDED.match_analysis,
                    candidate_content_hash = EXCLUDED.candidate_content_hash,
                    opportunity_content_hash = EXCLUDED.opportunity_content_hash,
                    candidate_evidence_version = EXCLUDED.candidate_evidence_version,
                    opportunity_content_version = EXCLUDED.opportunity_content_version,
                    engine_version = EXCLUDED.engine_version,
                    engine_generation = EXCLUDED.engine_generation,
                    updated_at = EXCLUDED.updated_at
                WHERE
                    EXCLUDED.candidate_evidence_version >= candidate_opportunity_matches.candidate_evidence_version
                    AND EXCLUDED.opportunity_content_version >= candidate_opportunity_matches.opportunity_content_version
                    AND EXCLUDED.engine_generation >= candidate_opportunity_matches.engine_generation
                RETURNING candidate_opportunity_matches.id, candidate_opportunity_matches.opportunity_id;
            """)

            successful_opp_ids = set()
            for it in valid_upserts:
                res = db.execute(upsert_sql, {
                    "match_score": it["match_score"],
                    "eligibility_status": it["eligibility_status"],
                    "match_analysis": json.dumps(it["match_analysis"]),
                    "cand_hash": it["candidate_content_hash"],
                    "opp_hash": it["opportunity_content_hash"],
                    "cand_ev": it["candidate_evidence_version"],
                    "opp_cv": it["opportunity_content_version"],
                    "engine_version": it["engine_version"],
                    "engine_generation": it["engine_generation"],
                    "now": now,
                    "cid": it["candidate_id"],
                    "oid": it["opportunity_id"]
                }).first()
                if res:
                    successful_opp_ids.add(res[1])

            if successful_opp_ids:
                recs = db.query(CandidateOpportunityMatch).filter(
                    CandidateOpportunityMatch.user_id == cand.user_id,
                    CandidateOpportunityMatch.opportunity_id.in_(list(successful_opp_ids))
                ).all()
                for r in recs:
                    results[r.opportunity_id] = (computed_results[r.opportunity_id], r)

            # Update opportunity extracted data and private opp fields for successful writes
            valid_by_id = {it["opportunity_id"]: it for it in valid_upserts}
            for opp in opportunities:
                if opp.id in successful_opp_ids and opp.id in valid_by_id:
                    opp.extracted_data = valid_by_id[opp.id]["extracted_data"]
                    if opp.user_id is not None and opp.user_id == cand.user_id:
                        opp.match_score = computed_results[opp.id].profile_match_score
                        opp.eligibility_status = computed_results[opp.id].eligibility_status
                        opp.match_analysis = computed_results[opp.id].model_dump()
                        opp.updated_at = now

            for opp_id, match_res in computed_results.items():
                if opp_id not in results:
                    existing = match_by_opp_id.get(opp_id)
                    if existing and existing.match_analysis:
                        stale_res = ProfileMatchResult(**existing.match_analysis)
                        stale_res.is_stale = True
                        results[opp_id] = (stale_res, existing)
                    elif match_res:
                        match_res.is_stale = True

        db.commit()
        return results


matching_service = MatchingService()
