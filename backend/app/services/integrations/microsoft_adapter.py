import os
import re
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import httpx
from backend.app.services.token_vault import encrypt_token, decrypt_token

logger = logging.getLogger(__name__)

MS_AUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MS_TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MS_GRAPH_URL = "https://graph.microsoft.com/v1.0"

MINIMUM_MS_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "Mail.Read",
    "Calendars.Read"
]

class MicrosoftIntegrationAdapter:
    def __init__(self, client_id: str = None, client_secret: str = None, redirect_uri: str = None):
        self.client_id = client_id or os.getenv("MICROSOFT_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("MICROSOFT_CLIENT_SECRET", "")
        self.redirect_uri = redirect_uri or os.getenv("MICROSOFT_REDIRECT_URI", "http://127.0.0.1:5174/integrations/callback/microsoft")

    def is_configured(self) -> bool:
        """Checks if genuine Microsoft Entra App credentials are provided."""
        return bool(self.client_id and self.client_secret)

    def get_authorization_url(self, state: str = "careeros_ms_state") -> Dict[str, Any]:
        """Generates the minimum-scope OAuth 2.0 authorization URL."""
        if not self.is_configured():
            return {
                "auth_url": "",
                "is_configured": False,
                "message": "Microsoft Client ID and Secret not configured. You can configure them in Settings or use Sandbox Mode."
            }

        scopes_str = " ".join(MINIMUM_MS_SCOPES)
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.redirect_uri,
            "response_mode": "query",
            "scope": scopes_str,
            "state": state
        }
        query_string = "&".join(f"{k}={httpx.URL('', params={k: v}).query.decode('utf-8')}" for k, v in params.items())
        return {
            "auth_url": f"{MS_AUTH_URL}?{query_string}",
            "is_configured": True,
            "scopes": MINIMUM_MS_SCOPES
        }

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """Exchanges authorization code for Microsoft Graph tokens."""
        if not self.is_configured():
            raise ValueError("Microsoft Client ID/Secret not configured")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(MS_TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": self.redirect_uri
            })
            if resp.status_code != 200:
                logger.error(f"Microsoft token exchange failed: {resp.text}")
                raise ValueError(f"Failed to exchange Microsoft OAuth code: {resp.text}")

            data = resp.json()
            access_token = data.get("access_token", "")
            refresh_token = data.get("refresh_token", "")
            expires_in = data.get("expires_in", 3600)

            # Fetch user profile
            me_resp = await client.get(f"{MS_GRAPH_URL}/me", headers={"Authorization": f"Bearer {access_token}"})
            me_data = me_resp.json() if me_resp.status_code == 200 else {}

            return {
                "account_email": me_data.get("mail") or me_data.get("userPrincipalName", "user@outlook.com"),
                "account_name": me_data.get("displayName", "Outlook User"),
                "encrypted_access_token": encrypt_token(access_token),
                "encrypted_refresh_token": encrypt_token(refresh_token) if refresh_token else "",
                "token_expires_at": datetime.utcnow() + timedelta(seconds=expires_in),
                "scopes": MINIMUM_MS_SCOPES
            }

    async def refresh_access_token(self, encrypted_refresh_token: str) -> Dict[str, Any]:
        """Refreshes expired access token using encrypted refresh token."""
        refresh_token = decrypt_token(encrypted_refresh_token)
        if not refresh_token:
            raise ValueError("No refresh token available")

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(MS_TOKEN_URL, data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token"
            })
            if resp.status_code != 200:
                raise ValueError(f"Microsoft token refresh failed: {resp.text}")

            data = resp.json()
            return {
                "encrypted_access_token": encrypt_token(data.get("access_token")),
                "token_expires_at": datetime.utcnow() + timedelta(seconds=data.get("expires_in", 3600))
            }

    async def fetch_career_messages(self, encrypted_access_token: str, max_results: int = 25) -> List[Dict[str, Any]]:
        """Fetches career-related emails via Microsoft Graph API."""
        token = decrypt_token(encrypted_access_token)
        headers = {"Authorization": f"Bearer {token}"}

        # Query messages with career search keywords
        url = f"{MS_GRAPH_URL}/me/messages?$top={max_results}&$search=\"interview OR application OR offer OR assessment\""
        
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Microsoft Graph mail fetch failed: {resp.text}")
                return []

            items = resp.json().get("value", [])
            messages = []
            for item in items:
                sender_obj = item.get("from", {}).get("emailAddress", {})
                received_dt = None
                if item.get("receivedDateTime"):
                    received_dt = datetime.fromisoformat(item["receivedDateTime"].replace("Z", "+00:00"))

                messages.append({
                    "provider_message_id": item["id"],
                    "thread_id": item.get("conversationId"),
                    "subject": item.get("subject", "No Subject"),
                    "sender": f"{sender_obj.get('name', '')} <{sender_obj.get('address', '')}>",
                    "recipient": item.get("toRecipients", [{}])[0].get("emailAddress", {}).get("address", ""),
                    "snippet": item.get("bodyPreview", ""),
                    "body_plain": item.get("body", {}).get("content", "") or item.get("bodyPreview", ""),
                    "received_at": received_dt or datetime.utcnow()
                })
            return messages

    async def fetch_calendar_events(self, encrypted_access_token: str, days_ahead: int = 30) -> List[Dict[str, Any]]:
        """Fetches upcoming events from Microsoft Graph Calendar API."""
        token = decrypt_token(encrypted_access_token)
        headers = {"Authorization": f"Bearer {token}"}

        start_dt = datetime.utcnow().isoformat() + "Z"
        end_dt = (datetime.utcnow() + timedelta(days=days_ahead)).isoformat() + "Z"
        url = f"{MS_GRAPH_URL}/me/calendar/calendarView?startDateTime={start_dt}&endDateTime={end_dt}&$top=50"

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                logger.error(f"Microsoft Graph calendar fetch failed: {resp.text}")
                return []

            items = resp.json().get("value", [])
            events = []
            for item in items:
                start_obj = item.get("start", {})
                end_obj = item.get("end", {})
                
                # Check online meeting or link
                meeting_link = item.get("onlineMeeting", {}).get("joinUrl") or ""
                meeting_platform = "Microsoft Teams" if meeting_link else None

                body_content = item.get("body", {}).get("content", "")
                if not meeting_link and body_content:
                    zoom_match = re.search(r"https://[a-zA-Z0-9-]+\.zoom\.us/j/[0-9a-zA-Z?=&]+", body_content)
                    meet_match = re.search(r"https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}", body_content)
                    if zoom_match:
                        meeting_link = zoom_match.group(0)
                        meeting_platform = "Zoom"
                    elif meet_match:
                        meeting_link = meet_match.group(0)
                        meeting_platform = "Google Meet"

                events.append({
                    "provider_event_id": item["id"],
                    "title": item.get("subject", "Untitled Event"),
                    "description": item.get("bodyPreview", ""),
                    "start_time": datetime.fromisoformat(start_obj.get("dateTime", "")[:19]) if start_obj.get("dateTime") else datetime.utcnow(),
                    "end_time": datetime.fromisoformat(end_obj.get("dateTime", "")[:19]) if end_obj.get("dateTime") else None,
                    "time_zone": start_obj.get("timeZone", "UTC"),
                    "meeting_platform": meeting_platform,
                    "meeting_link": meeting_link,
                    "location": item.get("location", {}).get("displayName"),
                    "organizer": item.get("organizer", {}).get("emailAddress", {}).get("address"),
                    "attendees": [{"name": a.get("emailAddress", {}).get("name"), "email": a.get("emailAddress", {}).get("address")} for a in item.get("attendees", [])],
                    "status": "confirmed" if not item.get("isCancelled") else "cancelled"
                })
            return events
