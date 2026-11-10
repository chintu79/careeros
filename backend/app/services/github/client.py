import base64
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"


class GitHubAPIError(Exception):
    """Base exception for GitHub API errors."""
    def __init__(self, message: str, status_code: Optional[int] = None, response_headers: Optional[Dict[str, str]] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_headers = response_headers or {}

GitHubApiError = GitHubAPIError


class GitHubNotFoundError(GitHubAPIError):
    """Raised when repository or user is not found (404)."""
    pass


class GitHubRateLimitError(GitHubAPIError):
    """Raised when rate limit is exceeded (403/429)."""
    def __init__(self, message: str, reset_timestamp: Optional[int] = None, remaining: int = 0):
        super().__init__(message, status_code=403)
        self.reset_timestamp = reset_timestamp
        self.remaining = remaining


class GitHubTokenRevokedError(GitHubAPIError):
    """Raised when GitHub returns HTTP 401 Bad Credentials or token is expired/revoked."""
    def __init__(self, message: str = "GitHub access token is invalid, expired, or revoked (HTTP 401 Bad Credentials). Reconnection required.", status_code: int = 401):
        super().__init__(message, status_code=401)


class GitHubApiClient:
    """
    Asynchronous GitHub REST API client with:
    - Conditional requests (ETag / If-None-Match)
    - Rate-limit inspection (X-RateLimit headers)
    - Bounded retries with exponential backoff
    - Authenticated or unauthenticated access modes
    - Safe content capping
    """
    def __init__(
        self,
        token: Optional[str] = None,
        timeout: float = 15.0,
        max_retries: int = 2
    ):
        self.token = token.strip() if token else None
        self.timeout = timeout
        self.max_retries = max_retries
        self.etag_cache: Dict[str, str] = {}
        self.last_rate_limit = {
            "limit": 60 if not self.token else 5000,
            "remaining": 60 if not self.token else 5000,
            "reset": 0
        }

    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Returns rate limit tracking details including calculated used count."""
        info = dict(self.last_rate_limit)
        limit = info.get("limit", 60 if not self.token else 5000)
        remaining = info.get("remaining", limit)
        info["limit"] = limit
        info["remaining"] = remaining
        info["used"] = max(0, limit - remaining)
        return info

    def _get_headers(self, etag: Optional[str] = None) -> Dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CareerOS-GitHub-Intelligence/1.0"
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if etag:
            headers["If-None-Match"] = etag
        return headers

    def _update_rate_limit(self, response_headers: Any):
        if not response_headers:
            return
        headers_lower = {str(k).lower(): str(v) for k, v in response_headers.items()}
        if "x-ratelimit-remaining" in headers_lower:
            try:
                self.last_rate_limit["remaining"] = int(headers_lower.get("x-ratelimit-remaining", "0"))
                self.last_rate_limit["limit"] = int(headers_lower.get("x-ratelimit-limit", "60"))
                self.last_rate_limit["reset"] = int(headers_lower.get("x-ratelimit-reset", "0"))
            except (ValueError, TypeError):
                pass

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        etag: Optional[str] = None,
        raise_for_status: bool = True
    ) -> Tuple[int, Any, Dict[str, str]]:
        """
        Executes HTTP request with bounded exponential backoff and rate limit tracking.
        Returns: (status_code, json_or_text_data, headers_dict)
        """
        if path.startswith("http://") or path.startswith("https://"):
            url = path
        else:
            url = f"{GITHUB_API_BASE}/{path.lstrip('/')}"

        headers = self._get_headers(etag=etag)

        delay = 0.5
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.request(method, url, headers=headers, params=params)
                    self._update_rate_limit(resp.headers)
                    headers_dict = dict(resp.headers)

                    if resp.status_code == 304:
                        return 304, None, headers_dict

                    etag_val = resp.headers.get("etag")
                    if etag_val:
                        self.etag_cache[url] = etag_val

                    if resp.status_code == 401:
                        raise GitHubTokenRevokedError()

                    if resp.status_code == 404:
                        if raise_for_status:
                            raise GitHubNotFoundError(f"Resource not found on GitHub: {path}", status_code=404)
                        return 404, None, headers_dict

                    if resp.status_code in (403, 429):
                        resp_text = resp.text.lower()
                        if "rate limit" in resp_text or resp.status_code == 429:
                            remaining = self.last_rate_limit.get("remaining", 0)
                            reset_ts = self.last_rate_limit.get("reset", 0)
                            raise GitHubRateLimitError(
                                f"GitHub API rate limit exceeded ({remaining} remaining, reset at {reset_ts}).",
                                reset_timestamp=reset_ts,
                                remaining=remaining
                            )
                        if raise_for_status:
                            raise GitHubAPIError(f"GitHub access forbidden (403): {resp.text[:200]}", status_code=403)

                    # Transient server errors: retry with backoff
                    if resp.status_code in (502, 503, 504) and attempt < self.max_retries:
                        logger.warning(f"GitHub server error {resp.status_code} on {path}. Retrying in {delay}s...")
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue

                    if raise_for_status and resp.status_code >= 400:
                        raise GitHubAPIError(f"GitHub API error {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

                    try:
                        data = resp.json()
                    except Exception:
                        data = resp.text

                    return resp.status_code, data, headers_dict

            except httpx.RequestError as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(f"Network error on {path}: {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= 2
                else:
                    raise GitHubAPIError(f"GitHub network communication failed: {str(e)}") from e

        if last_exception:
            raise GitHubAPIError(f"GitHub request failed after retries: {str(last_exception)}")

        return 500, None, {}

    # --- High-Level Methods ---

    async def get_user(self, username: str) -> Dict[str, Any]:
        """Fetches public user profile metadata."""
        clean_user = username.strip().lstrip("@").replace("https://github.com/", "").rstrip("/")
        _, data, _ = await self._request("GET", f"users/{clean_user}")
        return data or {}

    async def get_user_repos(self, username: str, per_page: int = 30, max_pages: int = 5) -> List[Dict[str, Any]]:
        """Fetches public repositories sorted by updated, following pagination links."""
        clean_user = username.strip().lstrip("@").replace("https://github.com/", "").rstrip("/")
        all_repos = []
        page = 1
        while page <= max_pages:
            params = {"sort": "updated", "per_page": min(per_page, 100), "page": page}
            _, data, headers = await self._request("GET", f"users/{clean_user}/repos", params=params)
            if not isinstance(data, list) or not data:
                break
            all_repos.extend(data)
            link_header = headers.get("link", "")
            if 'rel="next"' not in link_header or len(data) < per_page:
                break
            page += 1
        return all_repos

    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetches full repository metadata."""
        _, data, _ = await self._request("GET", f"repos/{owner}/{repo}")
        return data or {}

    async def get_repo_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Fetches byte distribution across programming languages."""
        _, data, _ = await self._request("GET", f"repos/{owner}/{repo}/languages")
        return data if isinstance(data, dict) else {}

    async def get_repo_readme(self, owner: str, repo: str) -> Optional[str]:
        """
        Fetches and decodes the default README file.
        Content is strictly size-capped to 30,000 characters to prevent memory abuse.
        """
        status, data, _ = await self._request("GET", f"repos/{owner}/{repo}/readme", raise_for_status=False)
        if status != 200 or not isinstance(data, dict):
            return None

        raw_b64 = data.get("content", "")
        if not raw_b64:
            return None

        try:
            decoded_bytes = base64.b64decode(raw_b64.replace("\n", "").strip())
            decoded_text = decoded_bytes.decode("utf-8", errors="replace")
            # Cap text size safely
            return decoded_text[:30000]
        except Exception as e:
            logger.warning(f"Failed to decode README for {owner}/{repo}: {e}")
            return None

    async def get_repo_tree(self, owner: str, repo: str, default_branch: str = "main") -> List[Dict[str, Any]]:
        """
        Discovers the repository file tree in a single API call via the Git Trees API.
        Capped at 500 files to protect processing time and memory.
        """
        status, data, _ = await self._request(
            "GET",
            f"repos/{owner}/{repo}/git/trees/{default_branch}",
            params={"recursive": "1"},
            raise_for_status=False
        )
        if status != 200 or not isinstance(data, dict):
            return []

        tree = data.get("tree", [])
        return tree[:500] if isinstance(tree, list) else []

    async def get_file_content(self, owner: str, repo: str, path: str, ref: Optional[str] = None) -> Optional[str]:
        """
        Fetches the contents of an individual manifest or config file.
        Content is capped at 25,000 characters.
        """
        params = {"ref": ref} if ref else None
        status, data, _ = await self._request(
            "GET",
            f"repos/{owner}/{repo}/contents/{path.lstrip('/')}",
            params=params,
            raise_for_status=False
        )
        if status != 200 or not isinstance(data, dict):
            return None

        raw_b64 = data.get("content", "")
        if not raw_b64:
            return None

        try:
            decoded_bytes = base64.b64decode(raw_b64.replace("\n", "").strip())
            decoded_text = decoded_bytes.decode("utf-8", errors="replace")
            return decoded_text[:25000]
        except Exception as e:
            logger.warning(f"Failed to decode file {path} for {owner}/{repo}: {e}")
            return None

    async def get_repo_commits(self, owner: str, repo: str, author: Optional[str] = None, per_page: int = 5) -> List[Dict[str, Any]]:
        """Fetches recent commits."""
        params: Dict[str, Any] = {"per_page": min(per_page, 20)}
        if author:
            params["author"] = author

        status, data, _ = await self._request(
            "GET",
            f"repos/{owner}/{repo}/commits",
            params=params,
            raise_for_status=False
        )
        if status != 200 or not isinstance(data, list):
            return []
        return data

    # High-level aliases
    get_commits = get_repo_commits
    get_tree = get_repo_tree
    get_languages = get_repo_languages
    get_readme = get_repo_readme
    list_user_repos = get_user_repos
    _request_with_retry = _request
