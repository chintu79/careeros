import re
import socket
import ipaddress
import logging
import httpx
from urllib.parse import urlparse
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Content cues indicating the application is closed or filled even if HTTP 200 is returned
CLOSED_PAGE_PATTERNS = [
    r'no longer accepting applications',
    r'job (?:has been |is )closed',
    r'this job (?:has )?expired',
    r'position has been filled',
    r'job is no longer available',
    r'opening has been taken down',
    r'this listing has expired',
    r'this posting has expired',
    r'applications are now closed',
    r'this position is closed',
    r'not accepting applications at this time',
    r'job not found'
]
CLOSED_REGEX = re.compile('|'.join(CLOSED_PAGE_PATTERNS), re.IGNORECASE)

BLOCKED_HOSTNAMES = {
    "localhost", "127.0.0.1", "0.0.0.0", "::1", "metadata.google.internal",
    "instance-data", "169.254.169.254"
}

def is_safe_external_url(url: str) -> Tuple_Safe:
    """
    Validate that target URL does not point to internal network, loopback, link-local,
    cloud metadata, or reserved private IP addresses (SSRF Protection).
    """
    if not url or not isinstance(url, str):
        return False, "Empty or invalid URL"
        
    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Malformed URL: {e}"

    if parsed.scheme.lower() not in ("http", "https"):
        return False, f"Unsupported URL scheme: {parsed.scheme} (must be http/https)"

    hostname = (parsed.hostname or "").lower().strip()
    if not hostname:
        return False, "Missing hostname in URL"

    if hostname in BLOCKED_HOSTNAMES:
        return False, f"SSRF Protection: Hostname '{hostname}' is prohibited"

    # Check for direct IP address
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False, f"SSRF Protection: IP {ip} is private/reserved/loopback"
    except ValueError:
        # Not a raw IP literal; resolve via DNS
        try:
            addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
            for family, socktype, proto, canonname, sockaddr in addr_info:
                resolved_ip_str = sockaddr[0]
                resolved_ip = ipaddress.ip_address(resolved_ip_str)
                if resolved_ip.is_private or resolved_ip.is_loopback or resolved_ip.is_link_local or resolved_ip.is_reserved or resolved_ip.is_multicast:
                    return False, f"SSRF Protection: Resolved IP {resolved_ip} is private/reserved/loopback"
        except socket.gaierror:
            return False, f"DNS resolution failed for hostname '{hostname}'"
        except Exception as e:
            return False, f"SSRF resolution check error: {e}"

    return True, "Safe external URL"

Tuple_Safe = tuple[bool, str]

async def verify_url_live(url: str, timeout: float = 8.0) -> Dict[str, Any]:
    """
    Perform active, SSRF-protected HTTP probe to verify whether an internship application/source link is active.
    Returns structured verification details with 6-status taxonomy:
      - 'verified': HTTP 200, valid application page, active form/posting
      - 'closed': HTTP 200, but text explicitly notes closed/filled
      - 'expired': HTTP 404 or 410 (page removed)
      - 'unverified': HTTP 403 / 429 (bot challenge or rate limited)
      - 'failed_verification': Connection refused, DNS failure, timeout, or SSRF prohibited
    """
    checked_time = datetime.utcnow().isoformat()
    if not url or not url.strip():
        return {
            "listing_status": "unverified",
            "http_status": None,
            "final_url": url,
            "redirected": False,
            "checked_at": checked_time,
            "verification_notes": "Missing application or source URL"
        }

    # 1. SSRF Protection validation
    is_safe, ssrf_reason = is_safe_external_url(url)
    if not is_safe:
        return {
            "listing_status": "failed_verification",
            "http_status": None,
            "final_url": url,
            "redirected": False,
            "checked_at": checked_time,
            "verification_notes": ssrf_reason
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9"
    }

    try:
        # Custom redirect handling with SSRF check on each redirect hop
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False, headers=headers) as client:
            current_url = url
            redirect_count = 0
            max_redirects = 5
            resp = None

            while redirect_count < max_redirects:
                # Validate current hop
                safe_hop, hop_reason = is_safe_external_url(current_url)
                if not safe_hop:
                    return {
                        "listing_status": "failed_verification",
                        "http_status": None,
                        "final_url": current_url,
                        "redirected": redirect_count > 0,
                        "checked_at": checked_time,
                        "verification_notes": f"SSRF blocked redirect target: {hop_reason}"
                    }

                resp = await client.get(current_url)
                
                # If redirect status, check Location header
                if resp.status_code in (301, 302, 303, 307, 308):
                    loc = resp.headers.get("location")
                    if not loc:
                        break
                    # Handle relative redirects
                    from urllib.parse import urljoin
                    current_url = urljoin(current_url, loc)
                    redirect_count += 1
                else:
                    break

            if resp is None:
                return {
                    "listing_status": "failed_verification",
                    "http_status": None,
                    "final_url": url,
                    "redirected": False,
                    "checked_at": checked_time,
                    "verification_notes": "Failed to receive response from host"
                }

            status_code = resp.status_code
            final_url = str(resp.url)
            redirected = redirect_count > 0

            # 404 Not Found or 410 Gone -> Expired
            if status_code in [404, 410]:
                return {
                    "listing_status": "expired",
                    "http_status": status_code,
                    "final_url": final_url,
                    "redirected": redirected,
                    "checked_at": checked_time,
                    "verification_notes": f"HTTP {status_code} - Page removed or not found"
                }

            # 200 OK -> Check content for closure cues
            if status_code == 200:
                text_sample = resp.text[:12000] # Check first 12KB
                if CLOSED_REGEX.search(text_sample):
                    return {
                        "listing_status": "closed",
                        "http_status": 200,
                        "final_url": final_url,
                        "redirected": redirected,
                        "checked_at": checked_time,
                        "verification_notes": "Page content indicates job is closed / no longer accepting applications"
                    }
                
                return {
                    "listing_status": "verified",
                    "http_status": 200,
                    "final_url": final_url,
                    "redirected": redirected,
                    "checked_at": checked_time,
                    "verification_notes": "HTTP 200 verified - active application page"
                }

            # 403 Forbidden or 429 Too Many Requests -> Unverified (bot challenge / rate limit)
            if status_code in [403, 429]:
                return {
                    "listing_status": "unverified",
                    "http_status": status_code,
                    "final_url": final_url,
                    "redirected": redirected,
                    "checked_at": checked_time,
                    "verification_notes": f"HTTP {status_code} - Protected by bot firewall or rate limited"
                }

            # 500 / 502 / 503 Server Errors
            if status_code >= 500:
                return {
                    "listing_status": "failed_verification",
                    "http_status": status_code,
                    "final_url": final_url,
                    "redirected": redirected,
                    "checked_at": checked_time,
                    "verification_notes": f"HTTP {status_code} - Target server error"
                }

            return {
                "listing_status": "unverified",
                "http_status": status_code,
                "final_url": final_url,
                "redirected": redirected,
                "checked_at": checked_time,
                "verification_notes": f"HTTP status {status_code}"
            }

    except httpx.TimeoutException:
        return {
            "listing_status": "failed_verification",
            "http_status": None,
            "final_url": url,
            "redirected": False,
            "checked_at": checked_time,
            "verification_notes": "Connection timed out during verification"
        }
    except (httpx.ConnectError, httpx.NetworkError) as e:
        return {
            "listing_status": "failed_verification",
            "http_status": None,
            "final_url": url,
            "redirected": False,
            "checked_at": checked_time,
            "verification_notes": f"Network / connection failed: {str(e)}"
        }
    except Exception as e:
        return {
            "listing_status": "failed_verification",
            "http_status": None,
            "final_url": url,
            "redirected": False,
            "checked_at": checked_time,
            "verification_notes": f"Verification exception: {str(e)}"
        }

def classify_staleness(opportunity_data: Dict[str, Any]) -> str:
    """
    Check if a listing is stale based on last verification timestamp and posting date.
    Returns: 'stale' or existing status
    """
    now = datetime.utcnow()
    last_verified = opportunity_data.get("last_verified_at")
    if last_verified:
        if isinstance(last_verified, str):
            try:
                last_verified = datetime.fromisoformat(last_verified.replace("Z", "+00:00"))
            except Exception:
                last_verified = None
        if last_verified and hasattr(last_verified, "tzinfo") and last_verified.tzinfo:
            last_verified = last_verified.replace(tzinfo=None)
            
        if last_verified and (now - last_verified > timedelta(days=30)):
            return "stale"
            
    posted_at = opportunity_data.get("posted_at")
    if posted_at:
        if isinstance(posted_at, str):
            try:
                posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            except Exception:
                posted_at = None
        if posted_at and hasattr(posted_at, "tzinfo") and posted_at.tzinfo:
            posted_at = posted_at.replace(tzinfo=None)
        if posted_at and (now - posted_at > timedelta(days=60)):
            return "stale"
            
    return opportunity_data.get("status", "verified")
