import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import SessionLocal
from backend.app.observability.metrics import metrics as _metrics
from backend.app.models.source import JobSource
from backend.app.models.company import Company
from backend.app.models.sync_log import SyncLog
from backend.app.services.notification_service import create_notification

from backend.app.connectors.greenhouse import GreenhouseConnector, DEFAULT_GREENHOUSE_BOARDS
from backend.app.connectors.lever import LeverConnector, DEFAULT_LEVER_SITES
from backend.app.connectors.ashby import AshbyConnector, DEFAULT_ASHBY_ORGS
from backend.app.connectors.smartrecruiters import SmartRecruitersConnector
from backend.app.connectors.remotive import RemotiveConnector
from backend.app.connectors.remoteok import RemoteOKConnector
from backend.app.connectors.rss_feed import RSSFeedConnector
from backend.app.connectors.internshala import InternshalaConnector
from backend.app.connectors.linkedin import LinkedInJobsConnector
from backend.app.connectors.ycombinator import YCombinatorConnector
from backend.app.connectors.india_platforms import INDIA_PLATFORMS

logger = logging.getLogger(__name__)

ACTIVE_SYNC_LOCKS = set()
SYNC_MUTEX = asyncio.Lock()

# Live synchronization progress monitor
GLOBAL_SYNC_PROGRESS = {
    "is_running": False,
    "started_at": None,
    "completed_at": None,
    "active_sources": {},
    "summary": {
        "retrieved": 0, "new": 0, "updated": 0, "duplicate": 0, "expired": 0, "relevant": 0, "errors": 0
    }
}

async def fetch_with_retry(fetch_fn, max_retries: int = 3, base_delay: float = 1.0) -> List[Dict[str, Any]]:
    """Execute fetching coroutine with exponential backoff on transient network failures."""
    last_err = None
    for attempt in range(1, max_retries + 1):
        try:
            return await fetch_fn()
        except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as e:
            last_err = e
            if attempt < max_retries:
                backoff = base_delay * (2 ** (attempt - 1))
                SCHEDULER_STATE["retry_count"] += 1
                logger.warning(f"Transient error on fetch attempt {attempt}/{max_retries}: {e}. Retrying in {backoff:.1f}s...")
                await asyncio.sleep(backoff)
            else:
                logger.error(f"Fetch failed after {max_retries} attempts: {e}")
                raise
        except Exception as e:
            logger.error(f"Non-transient error during fetch: {e}")
            raise
    return []

async def run_connector_sync(source_name: str, db: Session = None, timeout: float = 30.0) -> Dict[str, Any]:
    """Instrumented wrapper: duration + ingestion outcome counters. Business logic unchanged."""
    started = time.perf_counter()
    try:
        result = await _run_connector_sync_impl(source_name, db=db, timeout=timeout)
    except Exception:
        now_iso = datetime.utcnow().isoformat()
        SCHEDULER_STATE["last_failure_at"] = now_iso
        SCHEDULER_STATE["failure_count"] += 1
        _metrics.inc("scheduler_job_failures_total", {"job": "connector_sync"})
        _metrics.inc("opportunity_ingestion_runs_total", {"outcome": "failure"})
        _metrics.observe(
            "opportunity_ingestion_duration_seconds",
            time.perf_counter() - started,
            {"outcome": "failure"},
        )
        raise
    SCHEDULER_STATE["last_success_at"] = datetime.utcnow().isoformat()
    _metrics.inc("scheduler_job_runs_total", {"job": "connector_sync", "outcome": "success"})
    _metrics.inc("opportunity_ingestion_runs_total", {"outcome": "success"})
    _metrics.observe(
        "opportunity_ingestion_duration_seconds",
        time.perf_counter() - started,
        {"outcome": "success"},
    )
    _metrics.set_gauge("scheduler_last_success_timestamp_seconds", time.time())
    return result


async def _run_connector_sync_impl(source_name: str, db: Session = None, timeout: float = 30.0) -> Dict[str, Any]:
    """Execute isolated synchronization for a specific source with timeout protection and granular state updates."""
    s_lower = source_name.lower().strip()
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
        
    async with SYNC_MUTEX:
        if s_lower in ACTIVE_SYNC_LOCKS:
            logger.warning(f"Sync for '{source_name}' is already in progress.")
            return {
                "source": source_name, "retrieved": 0, "new": 0, "updated": 0, "duplicate": 0,
                "expired": 0, "relevant": 0, "errors": 0, "status": "already_running",
                "message": f"Sync for '{source_name}' is already active."
            }
        ACTIVE_SYNC_LOCKS.add(s_lower)
        GLOBAL_SYNC_PROGRESS["active_sources"][source_name] = {
            "status": "syncing", "started_at": datetime.utcnow().isoformat(),
            "retrieved": 0, "new": 0, "updated": 0, "errors": 0
        }

    start_time = datetime.utcnow()
    log = SyncLog(source_name=source_name, started_at=start_time, status="running")
    db.add(log)
    db.commit()
    db.refresh(log)
    
    source = db.query(JobSource).filter(JobSource.name.ilike(f"%{source_name}%")).first()

    try:
        async def do_fetch():
            raw_jobs = []
            if "internshala" in s_lower:
                connector = InternshalaConnector()
                raw_jobs = await connector.fetch_jobs(query="computer-science", location="India", limit=25)
            elif "linkedin" in s_lower:
                connector = LinkedInJobsConnector()
                raw_jobs = await connector.fetch_jobs(query="Software Engineer Intern", location="India", limit=20)
            elif "ycombinator" in s_lower or "y combinator" in s_lower or "yc" in s_lower:
                connector = YCombinatorConnector()
                raw_jobs = await connector.fetch_jobs(limit=25)
            elif "greenhouse" in s_lower:
                connector = GreenhouseConnector()
                raw_jobs = await connector.fetch_jobs(boards=DEFAULT_GREENHOUSE_BOARDS)
            elif "ashby" in s_lower:
                connector = AshbyConnector()
                raw_jobs = await connector.fetch_jobs(orgs=DEFAULT_ASHBY_ORGS)
            elif "lever" in s_lower:
                connector = LeverConnector()
                raw_jobs = await connector.fetch_jobs(sites=DEFAULT_LEVER_SITES)
            elif "smartrecruiters" in s_lower:
                connector = SmartRecruitersConnector()
                raw_jobs = await connector.fetch_jobs()
            elif "remotive" in s_lower:
                connector = RemotiveConnector()
                raw_jobs = await connector.fetch_jobs()
            elif "remote ok" in s_lower or "remoteok" in s_lower:
                connector = RemoteOKConnector()
                raw_jobs = await connector.fetch_jobs()
            elif "adzuna" in s_lower:
                # Retired in v3.1.0; keep a truthful state for pre-existing rows.
                if source:
                    source.connection_status = "unsupported"
                    source.last_error_message = "Adzuna integration retired in v3.1.0"
                    db.commit()
                return {"retrieved": 0, "new": 0, "updated": 0, "duplicate": 0, "expired": 0, "relevant": 0, "errors": 0, "message": "Adzuna integration retired in v3.1.0"}
            elif "rss" in s_lower:
                custom_feed = source.config_data.get("feed_url") if source and source.config_data else None
                connector = RSSFeedConnector(feed_url=custom_feed)
                raw_jobs = await connector.fetch_jobs()
            elif any(portal in s_lower for portal in ["naukri", "wellfound", "indeed", "aicte"]):
                platform_info = INDIA_PLATFORMS.get(s_lower, {})
                fail_reason = platform_info.get("failure_reason", "Automated sync requires session credentials or anti-bot firewall. Manual import active.")
                if source:
                    source.connection_status = "unsupported"
                    source.last_error_message = fail_reason
                    db.commit()
                return connector_stub_india(log, source, db, fail_reason)
            else:
                connector = RemotiveConnector()
                raw_jobs = []
                
            return connector, raw_jobs

        # Apply per-source timeout
        fetch_res = await asyncio.wait_for(do_fetch(), timeout=timeout)
        if isinstance(fetch_res, dict): # Stub return
            stats = fetch_res
        else:
            connector, raw_jobs = fetch_res
            stats = await connector.process_and_save_jobs(db, raw_jobs)

        end_time = datetime.utcnow()
        duration = round((end_time - start_time).total_seconds(), 2)
        log.completed_at = end_time
        log.duration_seconds = duration
        log.retrieved_count = stats.get("retrieved", 0)
        log.new_count = stats.get("new", 0)
        log.duplicate_count = stats.get("duplicate", 0)
        log.expired_count = stats.get("expired", 0)
        log.relevant_count = stats.get("relevant", 0)
        log.error_count = stats.get("errors", 0)
        log.status = "success" if stats.get("errors", 0) == 0 else "partial"

        if source:
            source.last_sync_at = end_time
            source.last_sync_status = log.status
            source.total_jobs_discovered += stats.get("new", 0)
            if source.connection_status not in ["unsupported", "manual_import_only", "not_configured"]:
                source.connection_status = "operational" if log.status == "success" else "partially_operational"

        db.commit()

        if stats.get("relevant", 0) > 0:
            create_notification(
                db,
                title=f"New Opportunities: {source_name}",
                message=f"Discovered {stats['new']} new listings ({stats['relevant']} high-relevance matches).",
                notification_type="high_match"
            )

        GLOBAL_SYNC_PROGRESS["active_sources"][source_name] = {
            "status": "completed",
            "completed_at": end_time.isoformat(),
            "duration_seconds": duration,
            "retrieved": stats.get("retrieved", 0),
            "new": stats.get("new", 0),
            "updated": stats.get("updated", 0),
            "duplicate": stats.get("duplicate", 0),
            "errors": stats.get("errors", 0)
        }
        stats["duration_seconds"] = duration
        return stats

    except asyncio.TimeoutError:
        end_time = datetime.utcnow()
        duration = round((end_time - start_time).total_seconds(), 2)
        logger.error(f"Sync for source {source_name} timed out after {timeout}s.")
        db.rollback()
        log.completed_at = end_time
        log.duration_seconds = duration
        log.status = "failure"
        log.error_details = f"Timeout after {timeout} seconds"
        log.error_count += 1
        if source:
            source.last_sync_at = end_time
            source.last_sync_status = "error"
            source.last_error_message = f"Timeout after {timeout}s"
            if source.connection_status not in ["unsupported", "manual_import_only"]:
                source.connection_status = "failed"
        db.commit()
        GLOBAL_SYNC_PROGRESS["active_sources"][source_name] = {
            "status": "failed", "error": f"Timeout after {timeout}s", "duration_seconds": duration
        }
        return {"source": source_name, "retrieved": 0, "new": 0, "updated": 0, "duplicate": 0, "expired": 0, "relevant": 0, "errors": 1, "duration_seconds": duration}

    except Exception as e:
        end_time = datetime.utcnow()
        duration = round((end_time - start_time).total_seconds(), 2)
        logger.error(f"Sync failed for source {source_name}: {e}", exc_info=True)
        db.rollback()
        log.completed_at = end_time
        log.duration_seconds = duration
        log.status = "failure"
        log.error_details = str(e)
        log.error_count += 1
        if source:
            source.last_sync_at = end_time
            source.last_sync_status = "error"
            source.last_error_message = str(e)
            if source.connection_status not in ["unsupported", "manual_import_only"]:
                source.connection_status = "failed"
        db.commit()
        GLOBAL_SYNC_PROGRESS["active_sources"][source_name] = {
            "status": "failed", "error": str(e), "duration_seconds": duration
        }
        return {"source": source_name, "retrieved": 0, "new": 0, "updated": 0, "duplicate": 0, "expired": 0, "relevant": 0, "errors": 1, "duration_seconds": duration}

    finally:
        async with SYNC_MUTEX:
            ACTIVE_SYNC_LOCKS.discard(s_lower)
        if close_db:
            db.close()

def connector_stub_india(log, source, db, fail_reason):
    log.completed_at = datetime.utcnow()
    log.duration_seconds = 0.05
    log.status = "success"
    log.error_details = fail_reason
    db.commit()
    return {"retrieved": 0, "new": 0, "updated": 0, "duplicate": 0, "expired": 0, "relevant": 0, "errors": 0, "duration_seconds": 0.05}

async def sync_all_sources_parallel(db: Session = None) -> Dict[str, Any]:
    """
    Executes parallel background synchronization across all active independent sources
    including Y Combinator, Internshala, ATS connectors, and active monitored companies.
    """
    GLOBAL_SYNC_PROGRESS["is_running"] = True
    GLOBAL_SYNC_PROGRESS["started_at"] = datetime.utcnow().isoformat()
    GLOBAL_SYNC_PROGRESS["completed_at"] = None
    GLOBAL_SYNC_PROGRESS["summary"] = {
        "retrieved": 0, "new": 0, "updated": 0, "duplicate": 0, "expired": 0, "relevant": 0, "errors": 0
    }
    
    sources = [
        "Internshala", "LinkedIn Jobs", "Y Combinator", "Greenhouse", "Lever", "Ashby",
        "SmartRecruiters", "Remotive", "Remote OK"
    ]
    
    # Run all independent sources concurrently with separate sessions
    async def worker(src):
        worker_db = SessionLocal()
        try:
            return await run_connector_sync(src, db=worker_db, timeout=30.0)
        finally:
            worker_db.close()

    results = await asyncio.gather(*[worker(s) for s in sources], return_exceptions=True)
    
    total_stats = {
        "retrieved": 0, "new": 0, "updated": 0, "duplicate": 0, "expired": 0, "relevant": 0, "errors": 0, "sources_synced": 0
    }
    
    for res in results:
        if isinstance(res, dict):
            for k in ["retrieved", "new", "updated", "duplicate", "expired", "relevant", "errors"]:
                total_stats[k] += res.get(k, 0)
            total_stats["sources_synced"] += 1
        elif isinstance(res, Exception):
            total_stats["errors"] += 1

    GLOBAL_SYNC_PROGRESS["is_running"] = False
    GLOBAL_SYNC_PROGRESS["completed_at"] = datetime.utcnow().isoformat()
    GLOBAL_SYNC_PROGRESS["summary"] = total_stats
    return total_stats

async def retry_failed_sources() -> Dict[str, Any]:
    """Find sources that failed on their most recent sync run and re-trigger synchronization."""
    db = SessionLocal()
    failed_names = []
    try:
        sources = db.query(JobSource).filter(
            JobSource.connection_status.notin_(["disabled", "unsupported", "manual_import_only", "not_configured"])
        ).all()
        for s in sources:
            last_log = db.query(SyncLog).filter(
                SyncLog.source_name.ilike(f"%{s.name}%")
            ).order_by(desc(SyncLog.started_at)).first()
            if (last_log and last_log.status in ["failure", "partial"]) or s.last_sync_status in ["error", "failure"] or s.connection_status == "failed":
                failed_names.append(s.name)
    finally:
        db.close()

    if not failed_names:
        return {"retried": 0, "sources": [], "message": "No failed sources found to retry."}

    results = []
    for name in failed_names:
        res = await run_connector_sync(name)
        results.append({"source": name, "stats": res})
        
    return {"retried": len(failed_names), "sources": failed_names, "results": results}

def get_sync_progress() -> Dict[str, Any]:
    """Returns real-time synchronization progress of all configured sources."""
    return GLOBAL_SYNC_PROGRESS

SCHEDULER_STATE = {
    "is_enabled": True,
    "last_check_at": None,
    "next_check_at": None,
    "check_interval_seconds": 60,
    "default_sync_interval_hours": 6,
    "jobs_executed": 0,
    "is_running_cycle": False,
    "last_success_at": None,
    "last_failure_at": None,
    "failure_count": 0,
    "retry_count": 0,
}

async def background_scheduler_worker(check_interval_seconds: int = 60):
    """
    Continuous background synchronization worker running inside FastAPI event loop.
    Periodically checks all active JobSource records and triggers synchronization
    for sources whose (now - last_sync_at) exceeds their configured sync_frequency_hours.
    Protects against overlapping runs via ACTIVE_SYNC_LOCKS and SYNC_MUTEX.
    """
    logger.info("Background discovery synchronization worker started.")
    SCHEDULER_STATE["check_interval_seconds"] = check_interval_seconds
    while True:
        try:
            if not SCHEDULER_STATE["is_enabled"]:
                await asyncio.sleep(check_interval_seconds)
                continue

            now = datetime.utcnow()
            SCHEDULER_STATE["last_check_at"] = now.isoformat()
            SCHEDULER_STATE["next_check_at"] = (now + timedelta(seconds=check_interval_seconds)).isoformat()
            SCHEDULER_STATE["is_running_cycle"] = True

            db = SessionLocal()
            due_sources = []
            try:
                sources = db.query(JobSource).filter(
                    JobSource.connection_status.notin_(["disabled", "manual_import_only", "unsupported", "not_configured"])
                ).all()

                for s in sources:
                    freq_hours = s.sync_frequency_hours or SCHEDULER_STATE["default_sync_interval_hours"]
                    if not s.last_sync_at:
                        due_sources.append(s.name)
                    else:
                        elapsed = (now - s.last_sync_at).total_seconds()
                        if elapsed >= (freq_hours * 3600):
                            due_sources.append(s.name)
            finally:
                db.close()

            # Execute due sources independently without blocking
            for src_name in due_sources:
                if src_name.lower().strip() not in ACTIVE_SYNC_LOCKS:
                    logger.info(f"[Scheduled Sync] Source '{src_name}' is due for background sync.")
                    asyncio.create_task(run_connector_sync(src_name))
                    SCHEDULER_STATE["jobs_executed"] += 1

            SCHEDULER_STATE["last_success_at"] = datetime.utcnow().isoformat()
            SCHEDULER_STATE["is_running_cycle"] = False
            _metrics.inc("scheduler_cycles_total", {"outcome": "success"})
            _metrics.set_gauge("scheduler_last_success_timestamp_seconds", time.time())
        except asyncio.CancelledError:
            logger.info("Background discovery synchronization worker stopped gracefully.")
            break
        except Exception as e:
            logger.error(f"Error in background scheduler cycle: {e}", exc_info=True)
            SCHEDULER_STATE["is_running_cycle"] = False
            SCHEDULER_STATE["failure_count"] += 1
            SCHEDULER_STATE["last_failure_at"] = datetime.utcnow().isoformat()
            _metrics.inc("scheduler_cycles_total", {"outcome": "error"})

        await asyncio.sleep(check_interval_seconds)

def get_scheduler_status() -> Dict[str, Any]:
    """Retrieve status of the scheduled synchronization worker."""
    return {
        **SCHEDULER_STATE,
        "active_locks": list(ACTIVE_SYNC_LOCKS),
        "live_progress": GLOBAL_SYNC_PROGRESS
    }

def toggle_scheduler_state(enabled: bool) -> Dict[str, Any]:
    """Enable or pause the background synchronization worker."""
    SCHEDULER_STATE["is_enabled"] = enabled
    return {"is_enabled": SCHEDULER_STATE["is_enabled"]}
