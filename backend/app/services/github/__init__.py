"""
GitHub Intelligence package for CareerOS.
"""
from backend.app.services.github.client import GitHubApiClient, GitHubApiError, GitHubTokenRevokedError
from backend.app.services.github.manifest_parser import parse_manifests, extract_file_content_manifests
from backend.app.services.github.structure_analyzer import analyze_repository_structure
from backend.app.services.github.intelligence_service import (
    GitHubIntelligenceService,
    github_intelligence_service,
    canonicalize_github_url,
    get_github_token_for_user,
    save_github_token_for_user,
    delete_github_token_for_user
)

__all__ = [
    "GitHubApiClient",
    "GitHubApiError",
    "GitHubTokenRevokedError",
    "parse_manifests",
    "extract_file_content_manifests",
    "analyze_repository_structure",
    "GitHubIntelligenceService",
    "github_intelligence_service",
    "canonicalize_github_url",
    "get_github_token_for_user",
    "save_github_token_for_user",
    "delete_github_token_for_user"
]
