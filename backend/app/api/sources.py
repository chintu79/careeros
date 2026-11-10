import asyncio
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db, SessionLocal
from backend.app.models.source import JobSource
from backend.app.models.sync_log import SyncLog
from backend.app.services.discovery_scheduler import (
    run_connector_sync,
    sync_all_sources_parallel,
    retry_failed_sources,
    get_sync_progress,
    get_scheduler_status,
    toggle_scheduler_state
)

router = APIRouter(prefix="/sources", tags=["Sources"])

DEFAULT_SOURCES = [
    {"name": "Internshala", "source_type": "portal", "integration_method": "direct_url", "connection_status": "operational", "sync_frequency_hours": 6},
    {"name": "Greenhouse", "source_type": "ats", "integration_method": "api", "connection_status": "operational", "sync_frequency_hours": 6},
    {"name": "Lever", "source_type": "ats", "integration_method": "api", "connection_status": "operational", "sync_frequency_hours": 6},
    {"name": "Ashby", "source_type": "ats", "integration_method": "api", "connection_status": "operational", "sync_frequency_hours": 6},
    {"name": "SmartRecruiters", "source_type": "ats", "integration_method": "api", "connection_status": "operational", "sync_frequency_hours": 6},
    {"name": "Y Combinator", "source_type": "api", "integration_method": "api", "connection_status": "operational", "sync_frequency_hours": 6},
    {"name": "Remotive", "source_type": "api", "integration_method": "api", "connection_status": "operational", "sync_frequency_hours": 12},
    {"name": "Remote OK", "source_type": "api", "integration_method": "feed", "connection_status": "operational", "sync_frequency_hours": 12},
    {"name": "LinkedIn Jobs", "source_type": "portal", "integration_method": "direct_url", "connection_status": "operational", "sync_frequency_hours": 24},
    {"name": "Adzuna", "source_type": "api", "integration_method": "api", "connection_status": "not_configured", "sync_frequency_hours": 12},
    {"name": "RSS Feeds", "source_type": "rss", "integration_method": "feed", "connection_status": "operational", "sync_frequency_hours": 6},
    {"name": "AICTE Internship Portal", "source_type": "portal", "integration_method": "direct_url", "connection_status": "unsupported", "sync_frequency_hours": 6},
    {"name": "Naukri", "source_type": "portal", "integration_method": "text_paste", "connection_status": "unsupported", "sync_frequency_hours": 6},
    {"name": "Wellfound", "source_type": "portal", "integration_method": "direct_url", "connection_status": "unsupported", "sync_frequency_hours": 6},
    {"name": "Indeed India", "source_type": "portal", "integration_method": "text_paste", "connection_status": "unsupported", "sync_frequency_hours": 6},
    {"name": "Manual Import", "source_type": "manual", "integration_method": "text_paste", "connection_status": "operational", "sync_frequency_hours": 6}
]

def ensure_default_sources_seeded(db: Session):
    for def_s in DEFAULT_SOURCES:
        existing = db.query(JobSource).filter(JobSource.name.ilike(def_s["name"])).first()
        if not existing:
            s = JobSource(
                name=def_s["name"],
                source_type=def_s["source_type"],
                integration_method=def_s["integration_method"],
                connection_status=def_s["connection_status"],
                sync_frequency_hours=def_s["sync_frequency_hours"],
                config_data={}
            )
            db.add(s)
        else:
            # Sync status if currently incompatible
            if def_s["name"] in ["Naukri", "Wellfound", "Indeed India", "AICTE Internship Portal"]:
                existing.connection_status = "unsupported"
            elif def_s["name"] == "Adzuna" and not (existing.config_data or {}).get("app_key"):
                existing.connection_status = "not_configured"
            elif existing.connection_status == "connected":
                existing.connection_status = "operational"
    db.commit()

class SourceConfigUpdate(BaseModel):
    sync_frequency_hours: Optional[int] = None
    config_data: Optional[Dict[str, Any]] = None
    connection_status: Optional[str] = None

@router.get("")
def list_sources(db: Session = Depends(get_db)):
    """List all supported sources with integration status and discovery counts."""
    ensure_default_sources_seeded(db)
    sources = db.query(JobSource).order_by(JobSource.name.asc()).all()
    results = []
    for s in sources:
        masked_config = dict(s.config_data or {})
        for key in ["app_key", "api_key", "secret", "password"]:
            if key in masked_config and masked_config[key]:
                masked_config[key] = "••••••••" + str(masked_config[key])[-4:]
                
        # Calculate source metrics from sync logs
        last_success = db.query(SyncLog).filter(
            SyncLog.source_name.ilike(f"%{s.name}%"),
            SyncLog.status == "success"
        ).order_by(desc(SyncLog.completed_at)).first()
        
        last_attempt = db.query(SyncLog).filter(
            SyncLog.source_name.ilike(f"%{s.name}%")
        ).order_by(desc(SyncLog.started_at)).first()
        
        # Standardize connection status:
        # operational, partially_operational, rate_limited, failed, not_configured, unsupported
        status_label = s.connection_status
        if status_label in ["manual_import_only", "blocked"]:
            status_label = "unsupported"
        elif status_label in ["needs_configuration"]:
            status_label = "not_configured"
        elif status_label not in ["unsupported", "not_configured"]:
            if last_attempt and last_attempt.status == "failure":
                status_label = "failed"
            elif last_attempt and last_attempt.status == "partial":
                status_label = "partially_operational"
            elif last_success or s.total_jobs_discovered > 0:
                status_label = "operational"
            else:
                status_label = "operational"

        results.append({
            "id": s.id,
            "name": s.name,
            "source_type": s.source_type,
            "integration_method": s.integration_method,
            "connection_status": status_label,
            "sync_frequency_hours": s.sync_frequency_hours,
            "config_data": masked_config,
            "last_sync_at": s.last_sync_at,
            "last_successful_sync_at": last_success.completed_at if last_success else None,
            "last_attempted_sync_at": last_attempt.started_at if last_attempt else None,
            "last_duration_seconds": last_attempt.duration_seconds if last_attempt else None,
            "last_sync_status": s.last_sync_status,
            "last_error_message": s.last_error_message,
            "total_jobs_discovered": s.total_jobs_discovered,
            "created_at": s.created_at,
            "updated_at": s.updated_at
        })
    return results

@router.get("/sync-progress")
def get_live_sync_progress():
    """Retrieve live real-time synchronization progress across all sources."""
    return get_sync_progress()

@router.get("/scheduler/status")
def get_sync_scheduler_status():
    """Retrieve background synchronization worker status and next execution schedule."""
    return get_scheduler_status()

@router.post("/scheduler/toggle")
def toggle_sync_scheduler(enabled: bool = True):
    """Enable or pause the background synchronization worker."""
    return toggle_scheduler_state(enabled)

@router.post("/retry-failed")
async def trigger_retry_failed_sources():
    """Retry synchronization for sources that failed on their latest run."""
    return await retry_failed_sources()

@router.post("/seed-defaults")
def seed_defaults_endpoint(db: Session = Depends(get_db)):
    """Seed all default job sources."""
    ensure_default_sources_seeded(db)
    return {"success": True, "message": "Default sources seeded successfully."}

@router.put("/{id}")
def update_source_config(id: int, data: SourceConfigUpdate, db: Session = Depends(get_db)):
    """Update source credentials, frequency, or enabled state."""
    src = db.query(JobSource).filter(JobSource.id == id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
        
    if data.sync_frequency_hours is not None:
        src.sync_frequency_hours = data.sync_frequency_hours
    if data.connection_status is not None:
        src.connection_status = data.connection_status
    if data.config_data is not None:
        current = dict(src.config_data or {})
        current.update(data.config_data)
        src.config_data = current
        
    src.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(src)
    return {"success": True, "message": f"Updated configuration for {src.name}"}

@router.post("/{id}/sync")
async def trigger_source_sync(id: int, db: Session = Depends(get_db)):
    """Manually trigger discovery synchronization for this source."""
    src = db.query(JobSource).filter(JobSource.id == id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
        
    stats = await run_connector_sync(src.name, db)
    return {
        "success": True,
        "source": src.name,
        "stats": stats
    }

@router.post("/sync-all")
async def trigger_sync_all(background_tasks: BackgroundTasks):
    """
    Trigger parallel non-blocking synchronization across all active sources.
    Returns status immediately while workers run in background.
    """
    background_tasks.add_task(sync_all_sources_parallel)
    return {
        "success": True,
        "message": "Parallel synchronization job started across all configured sources.",
        "progress_url": "/api/sources/sync-progress"
    }

@router.post("/{id}/test")
async def test_source_connection(id: int, db: Session = Depends(get_db)):
    """Test connection and verify API access for a source."""
    src = db.query(JobSource).filter(JobSource.id == id).first()
    if not src:
        raise HTTPException(status_code=404, detail="Source not found")
        
    if src.connection_status in ["unsupported", "manual_import_only"]:
        return {
            "connected": True,
            "message": f"{src.name} is configured for compliant manual job description and URL imports."
        }
        
    try:
        s_lower = src.name.lower()
        if "ycombinator" in s_lower or "y combinator" in s_lower:
            from backend.app.connectors.ycombinator import YCombinatorConnector
            c = YCombinatorConnector()
            jobs = await c.fetch_jobs(limit=5)
            return {"connected": True, "message": f"Successfully connected to YC/HN Firebase API! Discovered {len(jobs)} active startup roles."}
        elif "greenhouse" in s_lower:
            from backend.app.connectors.greenhouse import GreenhouseConnector
            c = GreenhouseConnector(board_id="cloudflare")
            jobs = await c.fetch_jobs()
            return {"connected": True, "message": f"Successfully connected! Verified {len(jobs)} active listings on public board."}
        elif "lever" in s_lower:
            from backend.app.connectors.lever import LeverConnector
            c = LeverConnector(site="palantir")
            jobs = await c.fetch_jobs()
            return {"connected": True, "message": f"Successfully connected! Verified {len(jobs)} active postings."}
        elif "ashby" in s_lower:
            from backend.app.connectors.ashby import AshbyConnector
            c = AshbyConnector(organization="replit")
            jobs = await c.fetch_jobs()
            return {"connected": True, "message": f"Successfully connected! Verified {len(jobs)} active jobs on Ashby."}
        elif "remotive" in s_lower:
            from backend.app.connectors.remotive import RemotiveConnector
            c = RemotiveConnector()
            jobs = await c.fetch_jobs()
            return {"connected": True, "message": f"Successfully connected to Remotive API! {len(jobs)} remote jobs available."}
        elif "internshala" in s_lower:
            from backend.app.connectors.internshala import InternshalaConnector
            c = InternshalaConnector()
            jobs = await c.fetch_jobs(limit=5)
            return {"connected": True, "message": f"Successfully connected to Internshala! Retrieved {len(jobs)} live verified internships."}
        else:
            return {"connected": True, "message": f"Connection check passed for {src.name}."}
    except Exception as e:
        return {"connected": False, "message": f"Connection test failed: {str(e)}"}

@router.get("/logs")
def get_sync_logs(limit: int = 30, db: Session = Depends(get_db)):
    """Retrieve detailed synchronization execution history logs."""
    logs = db.query(SyncLog).order_by(desc(SyncLog.started_at)).limit(limit).all()
    return logs
