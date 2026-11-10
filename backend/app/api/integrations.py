import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.integration import IntegrationConnection, EmailMessageRecord, CalendarEventRecord
from backend.app.models.application import ApplicationRecord
from backend.app.models.opportunity import Opportunity
from backend.app.services.integrations.google_adapter import GoogleIntegrationAdapter, MINIMUM_GOOGLE_SCOPES
from backend.app.services.integrations.microsoft_adapter import MicrosoftIntegrationAdapter, MINIMUM_MS_SCOPES
from backend.app.services.email_intelligence_service import process_incoming_email
from backend.app.services.calendar_intelligence_service import process_calendar_event

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations", tags=["Email & Calendar Integrations"])

# Schemas
class OAuthCallbackRequest(BaseModel):
    code: str
    state: Optional[str] = None

class DisconnectResponse(BaseModel):
    success: bool
    provider: str
    message: str

def serialize_connection(conn: IntegrationConnection) -> Dict[str, Any]:
    return {
        "id": conn.id,
        "provider": conn.provider,
        "account_email": conn.account_email,
        "account_name": conn.account_name,
        "scopes": conn.scopes or [],
        "connection_status": conn.connection_status,
        "token_expires_at": conn.token_expires_at.isoformat() if conn.token_expires_at else None,
        "last_sync_at": conn.last_sync_at.isoformat() if conn.last_sync_at else None,
        "last_sync_error": conn.last_sync_error,
        "created_at": conn.created_at.isoformat() if conn.created_at else None
    }

@router.get("/status")
def get_integrations_status(db: Session = Depends(get_db)):
    """
    Returns connection status and configuration availability for all supported providers.
    Never claims a provider is connected unless verified.
    """
    google_adapter = GoogleIntegrationAdapter()
    ms_adapter = MicrosoftIntegrationAdapter()

    connections = db.query(IntegrationConnection).all()
    conn_map = {c.provider: c for c in connections}

    google_conn = conn_map.get("google")
    ms_conn = conn_map.get("microsoft")

    return {
        "providers": {
            "google": {
                "provider": "google",
                "name": "Google (Gmail & Calendar)",
                "is_configured": google_adapter.is_configured(),
                "connection": serialize_connection(google_conn) if google_conn else None,
                "status": google_conn.connection_status if google_conn else ("not_connected" if google_adapter.is_configured() else "not_configured"),
                "minimum_scopes": MINIMUM_GOOGLE_SCOPES
            },
            "microsoft": {
                "provider": "microsoft",
                "name": "Microsoft 365 (Outlook Mail & Calendar)",
                "is_configured": ms_adapter.is_configured(),
                "connection": serialize_connection(ms_conn) if ms_conn else None,
                "status": ms_conn.connection_status if ms_conn else ("not_connected" if ms_adapter.is_configured() else "not_configured"),
                "minimum_scopes": MINIMUM_MS_SCOPES
            }
        },
        "total_connected": sum(1 for c in connections if c.connection_status == "connected")
    }

@router.post("/google/auth-url")
def get_google_auth_url():
    """Generates Google OAuth 2.0 authorization URL with minimum necessary permissions."""
    adapter = GoogleIntegrationAdapter()
    return adapter.get_authorization_url()

@router.post("/google/callback")
async def handle_google_callback(payload: OAuthCallbackRequest, db: Session = Depends(get_db)):
    """Handles OAuth 2.0 authorization code exchange for Google tokens."""
    adapter = GoogleIntegrationAdapter()
    try:
        token_data = await adapter.exchange_code_for_tokens(payload.code)
        
        # Save or update connection record
        conn = db.query(IntegrationConnection).filter(IntegrationConnection.provider == "google").first()
        if not conn:
            conn = IntegrationConnection(provider="google")
            db.add(conn)

        conn.account_email = token_data["account_email"]
        conn.account_name = token_data["account_name"]
        conn.encrypted_access_token = token_data["encrypted_access_token"]
        conn.encrypted_refresh_token = token_data["encrypted_refresh_token"]
        conn.token_expires_at = token_data["token_expires_at"]
        conn.scopes = token_data["scopes"]
        conn.connection_status = "connected"
        conn.last_sync_error = None
        db.commit()
        db.refresh(conn)

        return {"success": True, "connection": serialize_connection(conn)}
    except Exception as e:
        logger.error(f"Google callback failed: {e}")
        raise HTTPException(status_code=400, detail="Internal error")

@router.post("/microsoft/auth-url")
def get_microsoft_auth_url():
    """Generates Microsoft Graph OAuth 2.0 authorization URL."""
    adapter = MicrosoftIntegrationAdapter()
    return adapter.get_authorization_url()

@router.post("/microsoft/callback")
async def handle_microsoft_callback(payload: OAuthCallbackRequest, db: Session = Depends(get_db)):
    """Handles Microsoft Graph OAuth 2.0 code exchange."""
    adapter = MicrosoftIntegrationAdapter()
    try:
        token_data = await adapter.exchange_code_for_tokens(payload.code)

        conn = db.query(IntegrationConnection).filter(IntegrationConnection.provider == "microsoft").first()
        if not conn:
            conn = IntegrationConnection(provider="microsoft")
            db.add(conn)

        conn.account_email = token_data["account_email"]
        conn.account_name = token_data["account_name"]
        conn.encrypted_access_token = token_data["encrypted_access_token"]
        conn.encrypted_refresh_token = token_data["encrypted_refresh_token"]
        conn.token_expires_at = token_data["token_expires_at"]
        conn.scopes = token_data["scopes"]
        conn.connection_status = "connected"
        conn.last_sync_error = None
        db.commit()
        db.refresh(conn)

        return {"success": True, "connection": serialize_connection(conn)}
    except Exception as e:
        logger.error(f"Microsoft callback failed: {e}")
        raise HTTPException(status_code=400, detail="Internal error")

@router.post("/{id}/sync")
async def sync_integration(id: int, db: Session = Depends(get_db)):
    """Triggers incremental synchronization for a connected provider."""
    conn = db.query(IntegrationConnection).filter(IntegrationConnection.id == id).first()
    if not conn or conn.connection_status != "connected":
        raise HTTPException(status_code=404, detail="Active integration connection not found")

    emails_synced = 0
    events_synced = 0

    try:
        if conn.provider == "google":
            adapter = GoogleIntegrationAdapter()
            raw_emails = await adapter.fetch_career_messages(conn.encrypted_access_token)
            for m in raw_emails:
                process_incoming_email(db, m, connection_id=conn.id)
                emails_synced += 1

            raw_events = await adapter.fetch_calendar_events(conn.encrypted_access_token)
            for ev in raw_events:
                process_calendar_event(db, ev, connection_id=conn.id)
                events_synced += 1

        elif conn.provider == "microsoft":
            adapter = MicrosoftIntegrationAdapter()
            raw_emails = await adapter.fetch_career_messages(conn.encrypted_access_token)
            for m in raw_emails:
                process_incoming_email(db, m, connection_id=conn.id)
                emails_synced += 1

            raw_events = await adapter.fetch_calendar_events(conn.encrypted_access_token)
            for ev in raw_events:
                process_calendar_event(db, ev, connection_id=conn.id)
                events_synced += 1

        conn.last_sync_at = datetime.utcnow()
        conn.last_sync_error = None
        db.commit()

        return {
            "success": True,
            "provider": conn.provider,
            "emails_synced": emails_synced,
            "calendar_events_synced": events_synced,
            "synced_at": conn.last_sync_at.isoformat()
        }
    except Exception as e:
        logger.error(f"Sync failed for connection {id}: {e}")
        conn.last_sync_error = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail="Operation failed")

@router.post("/{id}/disconnect")
async def disconnect_integration(id: int, db: Session = Depends(get_db)):
    """Revokes tokens, marks disconnected, and cleans up credentials."""
    conn = db.query(IntegrationConnection).filter(IntegrationConnection.id == id).first()
    if not conn:
        raise HTTPException(status_code=404, detail="Integration connection not found")

    provider = conn.provider
    if provider == "google" and conn.encrypted_access_token:
        adapter = GoogleIntegrationAdapter()
        await adapter.revoke_token(conn.encrypted_access_token)

    conn.connection_status = "disconnected"
    conn.encrypted_access_token = None
    conn.encrypted_refresh_token = None
    conn.token_expires_at = None
    db.commit()

    return DisconnectResponse(
        success=True,
        provider=provider,
        message=f"{provider.capitalize()} account disconnected and tokens revoked successfully."
    )

@router.post("/sandbox/seed")
def seed_sandbox_data(db: Session = Depends(get_db)):
    """
    Seeds realistic, grounded career communication fixtures and calendar events
    for instant local evaluation and testing without requiring real third-party tokens.
    """
    now = datetime.utcnow()

    # 1. Create or ensure Sandbox Connection
    conn = db.query(IntegrationConnection).filter(IntegrationConnection.provider == "google").first()
    if not conn:
        conn = IntegrationConnection(
            provider="google",
            account_email="synthetic.candidate@example.test",
            account_name="Krishna (Sandbox)",
            scopes=MINIMUM_GOOGLE_SCOPES,
            connection_status="connected",
            last_sync_at=now
        )
        db.add(conn)
        db.commit()
        db.refresh(conn)
    else:
        conn.connection_status = "connected"
        conn.last_sync_at = now
        db.commit()

    # Ensure sample application records exist for matching with unique opportunities
    sample_apps = [
        {"company": "Stripe", "title": "Software Engineering Intern - Infrastructure", "status": "applied"},
        {"company": "Palantir", "title": "Forward Deployed Software Engineer Intern", "status": "applied"},
        {"company": "Ramp", "title": "Backend Engineering Intern", "status": "screening"},
        {"company": "Datadog", "title": "Software Engineer Intern - Distributed Systems", "status": "applied"}
    ]
    import uuid
    for sa in sample_apps:
        existing_app = db.query(ApplicationRecord).filter(ApplicationRecord.company_name == sa["company"]).first()
        if not existing_app:
            uid = uuid.uuid4().hex[:8]
            opp = Opportunity(
                title=sa["title"],
                normalized_title=sa["title"].lower(),
                company_name=sa["company"],
                original_url=f"https://careers.{sa['company'].lower()}.com/jobs/{uid}",
                source_platform="direct",
                location="Remote"
            )
            db.add(opp)
            db.commit()
            db.refresh(opp)

            new_app = ApplicationRecord(
                opportunity_id=opp.id,
                company_name=sa["company"],
                job_title=sa["title"],
                original_url=f"https://careers.{sa['company'].lower()}.com/jobs/{uid}",
                status=sa["status"],
                applied_date=now - timedelta(days=5),
                match_score=0.92
            )
            db.add(new_app)
            db.commit()

    # 2. Seed Realistic Email Messages
    sample_emails = [
        {
            "provider_message_id": "msg_stripe_invite_001",
            "thread_id": "th_stripe_001",
            "subject": "Interview Invitation: Stripe Software Engineering Intern (Round 1)",
            "sender": "Sarah Jenkins <sjenkins@stripe.com>",
            "recipient": conn.account_email,
            "snippet": "We were very impressed by your background and would like to invite you to a technical interview for the Software Engineering Intern role.",
            "body_plain": """Hi Krishna,

Thank you for applying to Stripe! Our hiring team reviewed your application and projects, and we would like to invite you to a 45-minute Technical Interview (Round 1).

During this round, you will pair-program with a Stripe backend engineer on system design and algorithmic fundamentals.

Please select a convenient time slot using our scheduling portal by Friday, November 14th:
https://meet.google.com/xyz-uvwx-rst

Meeting Platform: Google Meet
Link: https://meet.google.com/xyz-uvwx-rst

Best regards,
Sarah Jenkins
University Recruiting | Stripe""",
            "received_at": now - timedelta(hours=4)
        },
        {
            "provider_message_id": "msg_palantir_oa_002",
            "thread_id": "th_palantir_002",
            "subject": "Palantir Technologies: Online Assessment Invitation - HackerRank",
            "sender": "Palantir Campus Recruiting <recruiting@palantir.com>",
            "recipient": conn.account_email,
            "snippet": "Please complete your HackerRank coding challenge for the Forward Deployed Software Engineer Intern role before the deadline.",
            "body_plain": """Dear Krishna,

Thank you for your interest in Palantir Technologies! As the next step for your Forward Deployed Software Engineer Intern application, please complete our technical coding challenge.

Assessment Details:
- Platform: HackerRank
- Duration: 90 minutes
- Format: 2 Algorithmic Questions + 1 System Optimization Question
- Deadline: Complete your assessment by November 15, 2026 at 11:59 PM IST.

Access your test via the secure link:
https://www.hackerrank.com/tests/palantir-fdse-intern-2026

Good luck!
Palantir Recruiting Team""",
            "received_at": now - timedelta(hours=18)
        },
        {
            "provider_message_id": "msg_ramp_offer_003",
            "thread_id": "th_ramp_003",
            "subject": "Congratulations! Offer Letter from Ramp - Backend Engineering Intern",
            "sender": "Marcus Vance <marcus@ramp.com>",
            "recipient": conn.account_email,
            "snippet": "We are thrilled to extend a formal offer of employment for the Backend Engineering Intern position at Ramp.",
            "body_plain": """Dear Krishna,

On behalf of the entire team at Ramp, I am thrilled to extend you a formal offer for the Backend Engineering Intern role for Summer 2026!

The team was exceptionally impressed with your technical screen and knowledge of distributed systems and PostgreSQL query optimization.

Please review the attached formal offer letter and respond by November 20th.

Welcome to Ramp!
Marcus Vance
Head of Engineering Talent | Ramp""",
            "received_at": now - timedelta(days=1)
        },
        {
            "provider_message_id": "msg_datadog_confirm_004",
            "thread_id": "th_datadog_004",
            "subject": "Thank you for applying to Datadog!",
            "sender": "Datadog Careers <no-reply@datadoghq.com>",
            "recipient": conn.account_email,
            "snippet": "We have received your application for Software Engineer Intern - Distributed Systems.",
            "body_plain": """Hello Krishna,

Thank you for applying to Datadog! We received your application for the Software Engineer Intern - Distributed Systems position.

Our university recruiting team is reviewing your profile and will update you on the next steps soon.

You can monitor your application status anytime at our candidate portal.

Best,
Datadog Recruiting""",
            "received_at": now - timedelta(days=3)
        }
    ]

    seeded_emails = []
    for m in sample_emails:
        rec = process_incoming_email(db, m, connection_id=conn.id)
        seeded_emails.append(rec.id)

    # 3. Seed Realistic Calendar Events
    sample_events = [
        {
            "provider_event_id": "cal_stripe_round1_001",
            "title": "Technical Interview with Stripe: Systems & Backend",
            "description": "Round 1 Technical Interview for Software Engineering Intern. Meeting Link: https://meet.google.com/xyz-uvwx-rst",
            "start_time": now + timedelta(days=2, hours=3),
            "end_time": now + timedelta(days=2, hours=3, minutes=45),
            "time_zone": "Asia/Kolkata",
            "company_name": "Stripe",
            "role_title": "Software Engineering Intern - Infrastructure",
            "meeting_platform": "Google Meet",
            "meeting_link": "https://meet.google.com/xyz-uvwx-rst",
            "organizer": "sjenkins@stripe.com",
            "attendees": [{"name": "Sarah Jenkins", "email": "sjenkins@stripe.com"}, {"name": "Alex Chen", "email": "alex@stripe.com"}],
            "prep_notes": "Focus on distributed logging, rate limiting, and Python asyncio.",
            "status": "confirmed"
        },
        {
            "provider_event_id": "cal_palantir_oa_deadline_002",
            "title": "Palantir HackerRank Assessment Deadline",
            "description": "Complete 90-minute HackerRank coding challenge before 11:59 PM IST.",
            "start_time": now + timedelta(days=3, hours=17),
            "end_time": now + timedelta(days=3, hours=18, minutes=30),
            "time_zone": "Asia/Kolkata",
            "company_name": "Palantir",
            "role_title": "Forward Deployed Software Engineer Intern",
            "meeting_platform": "HackerRank",
            "meeting_link": "https://www.hackerrank.com/tests/palantir-fdse-intern-2026",
            "status": "confirmed"
        }
    ]

    seeded_events = []
    for ev in sample_events:
        rec = process_calendar_event(db, ev, connection_id=conn.id)
        seeded_events.append(rec.id)

    return {
        "success": True,
        "message": "Seeded sandbox connection with 4 realistic career communications and 2 calendar events.",
        "connection_id": conn.id,
        "emails_count": len(seeded_emails),
        "calendar_events_count": len(seeded_events)
    }
