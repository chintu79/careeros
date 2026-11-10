import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx
from backend.app.services.token_vault import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
GMAIL_MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
CALENDAR_EVENTS_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"

MINIMUM_GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile"
]

class GoogleIntegrationAdapter:
    def __init__(self, client_id: str = None, client_secret: str = None, redirect_uri: str = None):
        self.client_id = client_id or os.getenv("GOOGLE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("GOOGLE_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv("GOOGLE_REDIRECT_URI", "http://127.0.0.1:5174/integrations/callback/google")

    def is_configured(self) -> bool:
        """Checks if genuine Google OAuth credentials are provided."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self, state: str = "careeros_google_state") -> Dict[str, Any]:
        """Generates the minimum-scope OAuth 2.0 authorization URL."""
        if not self.is_configured():
            return {
                "auth_url": "",
                "is_configured": False,
                "message": "Google Client ID and Secret not configured. You can configure them in Settings or use Sandbox Mode."
            }
        
        scopes_str = " ".join(MINIMUM_GOOGLE_SCOPES)
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": scopes_str,
            "access_type": "offline",
            "prompt": "consent",
            "state": state
        }
        query_string = "&".join(f"{k}={httpx.URL('', params={k: v}).query.decode('utf-8')}" for k, v in params.items())
        return {
            "auth_url": f"{GOOGLE_AUTH_URL}?{query_string}",
            "is_configured": True,
            "scopes": MINIMUM_GOOGLE_SCOPES
        }

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchanges authorization code for access and refresh tokens, returning encrypted credentials."""
        if not self.is_configured():
            raise ValueError("Google Client ID/Secret not configured")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri
            })
            if resp.status_code != 200:
                logger.error(f"Google token exchange failed: {resp.text}")
                raise ValueError(f"Failed to exchange Google OAuth code: {resp.text}")
            
            data = resp.json()
            access_token = data.get("access_token", "")
            refresh_token = data.get("refresh_token", "")
            expires_in = data.get("expires_in", 3600)
            
            # Fetch user email
            user_resp = await client.get(GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"})
            user_data = user_resp.json() if user_resp.status_code == 200 else {}
            
            return {
                "account_email": user_data.get("email", "unknown@gmail.com"),
                "account_name": user_data.get("name", "Google User"),
                "encrypted_access_token": encrypt_token(access_token),
                "encrypted_refresh_token": encrypt_token(refresh_token) if refresh_token else "",
                "token_expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
                "scopes": MINIMUM_GOOGLE_SCOPES
            }

    async def refresh_access_token(self, encrypted_refresh_token: str) -> Dict[str, Any]:
        """Refreshes expired access token using encrypted refresh token."""
        refresh_token = decrypt_token(encrypted_refresh_token)
        if not refresh_token:
            raise ValueError("No refresh token available")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(GOOGLE_TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            })
            if resp.status_code != 200:
                raise ValueError(f"Token refresh failed: {resp.text}")
            
            data = resp.json()
            return {
                "encrypted_access_token": encrypt_token(data.get("access_token")),
                "token_expires_at": datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
            }

    async def revoke_token(self, encrypted_token: str) -> bool:
        """Revokes token access at Google."""
        token = decrypt_token(encrypted_token)
        if not token:
            return True
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(GOOGLE_REVOKE_URL, params={"token": token})
            return True
        except Exception as e:
            logger.warning(f"Google token revoke request failed: {e}")
            return False

    async def fetch_career_messages(self, encrypted_access_token: str, max_results: int = 25) -> List[Dict[str, Any]]:
        """
        Fetches career-related emails via Gmail API with targeted query filters.
        Avoids processing unrelated personal emails.
        """
        token = decrypt_token(encrypted_access_token)
        headers = {"Authorization": f"Bearer {token}"}
        
        # Scoped query targeting career communications
        query = "category:primary (subject:interview OR subject:application OR subject:offer OR subject:internship OR subject:assessment OR subject:recruiter OR subject:rejection)"
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            list_resp = await client.get(
                GMAIL_MESSAGES_URL,
                headers=headers,
                params={"q": query, "maxResults": max_results}
            )
            if list_resp.status_code != 200:
                logger.error(f"Gmail message list failed: {list_resp.text}")
                return []
            
            message_stubs = list_resp.json().get("messages", [])
            messages = []
            
            for stub in message_stubs[:max_results]:
                msg_id = stub["id"]
                msg_resp = await client.get(f"{GMAIL_MESSAGES_URL}/{msg_id}", headers=headers, params={"format": "full"})
                if msg_resp.status_code == 200:
                    data = msg_resp.json()
                    headers_list = data.get("payload", {}).get("headers", [])
                    header_map = {h["name"].lower(): h["value"] for h in headers_list}
                    
                    # Extract plain text body safely
                    body = self._extract_plain_body(data.get("payload", {})) or data.get("snippet", "")
                    
                    messages.append({
                        "provider_message_id": msg_id,
                        "thread_id": data.get("threadId"),
                        "subject": header_map.get("subject", "No Subject"),
                        "sender": header_map.get("from", "Unknown Sender"),
                        "recipient": header_map.get("to", ""),
                        "snippet": data.get("snippet", ""),
                        "body_plain": body,
                        "received_at": datetime.fromtimestamp(int(data.get("internalDate", "0")) / 1000.0) if data.get("internalDate") else datetime.utcnow()
                    })
                    
            return messages

    async def fetch_calendar_events(self, encrypted_access_token: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """
        Fetches calendar events from Google Calendar API.
        """
        token = decrypt_token(encrypted_access_token)
        headers = {"Authorization": f"Bearer {token}"}
        
        time_min = datetime.utcnow().isoformat() + "Z"
        time_max = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                CALENDAR_EVENTS_URL,
                headers=headers,
                params={
                    "timeMin": time_min,
                    "timeMax": time_max,
                    "singleEvents": "true",
                    "orderBy": "startTime"
                }
            )
            if resp.status_code != 200:
                logger.error(f"Google calendar fetch failed: {resp.text}")
                return []
            
            items = resp.json().get("items", [])
            events = []
            
            for item in items:
                start_raw = item.get("start", {})
                start_dt_str = start_raw.get("dateTime") or start_raw.get("date")
                end_raw = item.get("end", {})
                end_dt_str = end_raw.get("dateTime") or end_raw.get("date")
                
                # Detect video meeting links
                meeting_link = item.get("hangoutLink") or ""
                meeting_platform = "Google Meet" if meeting_link else None
                
                desc = item.get("description", "")
                if not meeting_link and desc:
                    import re
                    zoom_match = re.search(r"https://[a-zA-Z0-9-]+\.zoom\.us/j/[0-9a-zA-Z?=&]+", desc)
                    teams_match = re.search(r"https://teams\.microsoft\.com/l/meetup-join/[0-9a-zA-Z%?=&_-]+", desc)
                    if zoom_match:
                        meeting_link = zoom_match.group(0)
                        meeting_platform = "Zoom"
                    elif teams_match:
                        meeting_link = teams_match.group(0)
                        meeting_platform = "Microsoft Teams"
                
                events.append({
                    "provider_event_id": item["id"],
                    "title": item.get("summary", "Untitled Event"),
                    "description": desc,
                    "start_time": datetime.fromisoformat(start_dt_str.replace("Z", "+00:00")) if start_dt_str else datetime.utcnow(),
                    "end_time": datetime.fromisoformat(end_dt_str.replace("Z", "+00:00")) if end_dt_str else None,
                    "time_zone": start_raw.get("timeZone", "UTC"),
                    "meeting_platform": meeting_platform,
                    "meeting_link": meeting_link,
                    "location": item.get("location"),
                    "organizer": item.get("organizer", {}).get("email"),
                    "attendees": [{"email": a.get("email"), "name": a.get("displayName")} for a in item.get("attendees", [])],
                    "status": item.get("status", "confirmed")
                })
                
            return events

    def _extract_plain_body(self, payload: Dict[str, Any]) -> str:
        """Safely extracts plain text parts from multi-part Gmail payloads."""
        import base64
        mime_type = payload.get("mimeType", "")
        parts = payload.get("parts", [])
        
        if mime_type == "text/plain" and "data" in payload.get("body", {}):
            try:
                return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
            except Exception:
                pass
                
        for part in parts:
            if part.get("mimeType") == "text/plain" and "data" in part.get("body", {}):
                try:
                    return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                except Exception:
                    pass
            elif "parts" in part:
                nested = self._extract_plain_body(part)
                if nested:
                    return nested
        return ""
