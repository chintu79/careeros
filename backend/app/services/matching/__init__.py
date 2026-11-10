"""
Matching Service Package for CareerOS Matching Intelligence.
"""
from backend.app.services.matching.service import matching_service, MatchingService
from backend.app.services.matching.jd_parser import parse_job_description_deterministic
from backend.app.services.matching.evidence_builder import build_unified_candidate_evidence
from backend.app.services.matching.matching_engine import calculate_profile_match
from backend.app.services.matching.gap_analyzer import analyze_skill_gaps
from backend.app.services.matching.taxonomy import (
    canonicalize_tech_name,
    get_technology_relationship
)

__all__ = [
    "matching_service",
    "MatchingService",
    "parse_job_description_deterministic",
    "build_unified_candidate_evidence",
    "calculate_profile_match",
    "analyze_skill_gaps",
    "canonicalize_tech_name",
    "get_technology_relationship"
]
