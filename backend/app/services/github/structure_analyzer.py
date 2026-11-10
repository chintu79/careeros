"""
Repository structure analyzer for GitHub intelligence.
Deterministically inspects git tree paths and directory topology to detect architectural patterns,
distinguishing observed concrete evidence from inferred interpretations.
"""
import re
from typing import List, Dict, Set
from backend.app.schemas.github_intelligence import StructureEvidence


def analyze_repository_structure(tree_paths: List[str]) -> List[StructureEvidence]:
    """
    Analyzes repository file/directory paths and identifies key architectural patterns.
    Returns structured evidence list for detected architectural signals.
    """
    if not tree_paths:
        return []

    signals: List[StructureEvidence] = []
    
    # Normalize paths
    normalized_paths = [p.strip().replace("\\", "/") for p in tree_paths if p.strip()]
    path_set = set(normalized_paths)
    
    # 1. Frontend / Backend Separation
    frontend_patterns = [
        r"^frontend(/|$)", r"^client(/|$)", r"^web(/|$)", r"^ui(/|$)",
        r".*/(frontend|client|web|ui)/"
    ]
    backend_patterns = [
        r"^backend(/|$)", r"^server(/|$)", r"^api(/|$)", r"^service(/|$)",
        r".*/(backend|server|api|service)/"
    ]
    
    frontend_matches = _match_paths(normalized_paths, frontend_patterns)
    backend_matches = _match_paths(normalized_paths, backend_patterns)
    
    if frontend_matches and backend_matches:
        signals.append(StructureEvidence(
            signal_name="Fullstack Multi-Tier Separation",
            detected=True,
            evidence_paths=frontend_matches[:5] + backend_matches[:5],
            observed_description=f"Distinct frontend ({frontend_matches[0].split('/')[0]}) and backend ({backend_matches[0].split('/')[0]}) directory structures observed."
        ))
    elif frontend_matches:
        signals.append(StructureEvidence(
            signal_name="Frontend Client Architecture",
            detected=True,
            evidence_paths=frontend_matches[:5],
            observed_description="Frontend directory structure observed without distinct top-level backend separation."
        ))
    elif backend_matches:
        signals.append(StructureEvidence(
            signal_name="Backend Service Architecture",
            detected=True,
            evidence_paths=backend_matches[:5],
            observed_description="Backend/server directory structure observed."
        ))
        
    # 2. API Layer
    api_patterns = [
        r"(^|/)(routes?|controllers?|endpoints?|handlers?|routers?|graphql)/",
        r"(^|/)(api|routes?|controllers?|endpoints?|handlers?)\.[a-zA-Z0-9]+$"
    ]
    api_matches = _match_paths(normalized_paths, api_patterns)
    if api_matches:
        signals.append(StructureEvidence(
            signal_name="API Routing & Controller Layer",
            detected=True,
            evidence_paths=api_matches[:6],
            observed_description=f"Structured API routes/controllers detected across {len(api_matches)} file(s)."
        ))

    # 3. Database & Migrations
    db_patterns = [
        r"(^|/)(migrations?|alembic|prisma|schema\.sql|flyway|liquibase)(/|$)",
        r"(^|/)(models?|entities|schemas?)/",
        r".*\.(sql|prisma)$"
    ]
    db_matches = _match_paths(normalized_paths, db_patterns)
    if db_matches:
        migration_files = [p for p in db_matches if "migration" in p.lower() or "alembic" in p.lower() or "prisma" in p.lower()]
        desc = f"Database models/schemas detected across {len(db_matches)} file(s)."
        if migration_files:
            desc += f" Versioned migration history observed ({len(migration_files)} migration files/configs)."
        signals.append(StructureEvidence(
            signal_name="Database Models & Migrations",
            detected=True,
            evidence_paths=db_matches[:6],
            observed_description=desc
        ))

    # 4. Test Suite
    test_patterns = [
        r"(^|/)(tests?|__tests__|specs?|cypress|e2e|playwright)(/|$)",
        r".*(test|spec)\.[a-zA-Z0-9]+$",
        r"(^|/)(jest\.config|pytest\.ini|\.coveragerc|vitest\.config)"
    ]
    test_matches = _match_paths(normalized_paths, test_patterns)
    if test_matches:
        signals.append(StructureEvidence(
            signal_name="Automated Test Suite",
            detected=True,
            evidence_paths=test_matches[:6],
            observed_description=f"Automated test suite detected with {len(test_matches)} test file(s) or test configuration(s)."
        ))

    # 5. Documentation
    doc_patterns = [
        r"^README(\.[a-zA-Z0-9]+)?$",
        r"(^|/)(docs?|documentation|architecture|adr)(/|$)",
        r"^CONTRIBUTING(\.[a-zA-Z0-9]+)?$",
        r"^CHANGELOG(\.[a-zA-Z0-9]+)?$"
    ]
    doc_matches = _match_paths(normalized_paths, doc_patterns)
    if doc_matches:
        signals.append(StructureEvidence(
            signal_name="Project Documentation",
            detected=True,
            evidence_paths=doc_matches[:5],
            observed_description=f"Project documentation present: {', '.join([p.split('/')[-1] for p in doc_matches[:3]])}."
        ))

    # 6. CI/CD Automation
    cicd_patterns = [
        r"^\.github/workflows/.*",
        r"^\.gitlab-ci\.ya?ml$",
        r"^Jenkinsfile",
        r"^\.circleci/.*",
        r"^azure-pipelines\.ya?ml$",
        r"^bitbucket-pipelines\.ya?ml$"
    ]
    cicd_matches = _match_paths(normalized_paths, cicd_patterns)
    if cicd_matches:
        signals.append(StructureEvidence(
            signal_name="CI/CD Pipeline Automation",
            detected=True,
            evidence_paths=cicd_matches[:5],
            observed_description=f"CI/CD workflow definitions detected ({len(cicd_matches)} automation configuration(s))."
        ))

    # 7. Containerization & Deployment
    container_patterns = [
        r"(^|/)(Dockerfile.*|Containerfile.*|docker-compose.*\.ya?ml|compose\.ya?ml)$",
        r"(^|/)(helm|k8s|kubernetes|terraform)/"
    ]
    container_matches = _match_paths(normalized_paths, container_patterns)
    if container_matches:
        signals.append(StructureEvidence(
            signal_name="Containerization & Infrastructure",
            detected=True,
            evidence_paths=container_matches[:5],
            observed_description=f"Container/IaC infrastructure files detected: {', '.join([p.split('/')[-1] for p in container_matches[:3]])}."
        ))

    # 8. Monorepo Architecture
    monorepo_patterns = [
        r"(^|/)(packages|apps|services|modules)/",
        r"^(pnpm-workspace\.yaml|lerna\.json|nx\.json|turbo\.json|workspace\.json)$"
    ]
    monorepo_matches = _match_paths(normalized_paths, monorepo_patterns)
    # Require workspace file or multiple distinct package directories
    has_workspace_file = any(re.search(r"^(pnpm-workspace\.yaml|lerna\.json|nx\.json|turbo\.json|workspace\.json)$", p, re.IGNORECASE) for p in normalized_paths)
    package_dirs = [p for p in monorepo_matches if p.startswith("packages/") or p.startswith("apps/")]
    
    if has_workspace_file or len(package_dirs) >= 2:
        signals.append(StructureEvidence(
            signal_name="Monorepo Architecture",
            detected=True,
            evidence_paths=monorepo_matches[:6],
            observed_description="Monorepo configuration and multi-package directory topology detected."
        ))

    for s in signals:
        if not s.evidence_id:
            slug = re.sub(r'[^a-zA-Z0-9_]', '_', s.signal_name.lower()).strip('_')
            s.evidence_id = f"struct_{slug}"

    return signals


def _match_paths(paths: List[str], regex_patterns: List[str]) -> List[str]:
    """Matches list of paths against regex patterns in a case-insensitive manner."""
    matches: List[str] = []
    compiled = [re.compile(p, re.IGNORECASE) for p in regex_patterns]
    for p in paths:
        if any(regex.search(p) for regex in compiled):
            matches.append(p)
    return matches
