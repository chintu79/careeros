from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.opportunity import Opportunity
from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.sync_log import SyncLog
from backend.app.models.source import JobSource

def get_discovery_analytics(db: Session) -> Dict[str, Any]:
    """Calculate real analytics metrics directly from database tables."""
    total_discovered = db.query(Opportunity).count()
    total_saved = db.query(Opportunity).filter(Opportunity.is_saved == True).count()
    total_dismissed = db.query(Opportunity).filter(Opportunity.is_dismissed == True).count()
    total_applied = db.query(ApplicationRecord).count()
    
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)
    
    new_today = db.query(Opportunity).filter(Opportunity.discovered_at >= today_start).count()
    new_this_week = db.query(Opportunity).filter(Opportunity.discovered_at >= week_start).count()
    
    high_match_count = db.query(Opportunity).filter(
        Opportunity.match_score >= 70.0,
        Opportunity.eligibility_status != "disqualified"
    ).count()
    
    expiring_soon_count = db.query(Opportunity).filter(
        Opportunity.deadline_at != None,
        Opportunity.deadline_at >= now,
        Opportunity.deadline_at <= now + timedelta(days=7)
    ).count()
    
    # By source
    sources_data = db.query(
        Opportunity.source_platform, 
        func.count(Opportunity.id)
    ).group_by(Opportunity.source_platform).all()
    by_source = [{"source": s[0] or "Direct", "count": s[1]} for s in sources_data]
    
    # By normalized location
    locations_data = db.query(
        Opportunity.normalized_location, 
        func.count(Opportunity.id)
    ).group_by(Opportunity.normalized_location).order_by(func.count(Opportunity.id).desc()).limit(7).all()
    by_location = [{"location": l[0] or "India", "count": l[1]} for l in locations_data]
    
    # By category (internship_category or normalized title)
    category_data = db.query(
        Opportunity.internship_category, 
        func.count(Opportunity.id)
    ).group_by(Opportunity.internship_category).order_by(func.count(Opportunity.id).desc()).limit(8).all()
    by_category = [{"category": c[0] or "software_engineering", "count": c[1]} for c in category_data]
    
    # Duplicates & expired from sync logs
    dup_sum = db.query(func.sum(SyncLog.duplicate_count)).scalar() or 0
    expired_sum = db.query(func.sum(SyncLog.expired_count)).scalar() or 0
    
    total_syncs = db.query(SyncLog).count()
    success_syncs = db.query(SyncLog).filter(SyncLog.status == "success").count()
    reliability_pct = round((success_syncs / total_syncs * 100), 1) if total_syncs > 0 else 100.0
    conversion_rate = round((total_applied / total_discovered * 100), 1) if total_discovered > 0 else 0.0

    return {
        "summary": {
            "total_discovered": total_discovered,
            "new_today": new_today,
            "new_this_week": new_this_week,
            "high_match_count": high_match_count,
            "saved_count": total_saved,
            "dismissed_count": total_dismissed,
            "applied_count": total_applied,
            "expiring_soon_count": expiring_soon_count,
            "duplicates_prevented": int(dup_sum),
            "expired_detected": int(expired_sum),
            "sync_reliability_pct": reliability_pct,
            "application_conversion_pct": conversion_rate
        },
        "by_source": by_source,
        "by_location": by_location,
        "by_category": by_category
    }

def get_source_efficacy_metrics(db: Session) -> List[Dict[str, Any]]:
    """
    Computes transparent per-source efficacy and quality statistics:
    - total retrieved / discovered
    - active opportunities
    - duplicates detected & prevented
    - expired listings detected
    - duplicate rate (%)
    - expired rate (%)
    - applied count & conversion rate (%)
    - has_sufficient_sample (sample size >= 5)
    """
    sources = db.query(JobSource).order_by(JobSource.name.asc()).all()
    results = []
    
    for s in sources:
        s_name_lower = s.name.lower()
        
        opps = db.query(Opportunity).filter(
            Opportunity.source_platform.ilike(f"%{s_name_lower}%")
        ).all()
        
        total_discovered = len(opps)
        active_count = sum(1 for o in opps if o.status in ["verified", "active_verified", "newly_discovered"])
        expired_count = sum(1 for o in opps if o.status in ["expired", "closed", "removed_from_source"])
        
        sync_stats = db.query(
            func.sum(SyncLog.retrieved_count),
            func.sum(SyncLog.duplicate_count),
            func.sum(SyncLog.error_count)
        ).filter(SyncLog.source_name.ilike(f"%{s.name}%")).first()
        
        retrieved_sum = (sync_stats[0] or 0) if sync_stats else 0
        dup_sum = (sync_stats[1] or 0) if sync_stats else 0
        
        total_records = max(total_discovered + dup_sum, retrieved_sum)
        duplicate_rate = round((dup_sum / total_records * 100), 1) if total_records > 0 else 0.0
        expired_rate = round((expired_count / total_discovered * 100), 1) if total_discovered > 0 else 0.0
        
        app_count = db.query(ApplicationRecord).join(
            Opportunity, ApplicationRecord.opportunity_id == Opportunity.id
        ).filter(Opportunity.source_platform.ilike(f"%{s_name_lower}%")).count()
        
        conversion_rate = round((app_count / total_discovered * 100), 1) if total_discovered > 0 else 0.0
        has_sufficient_sample = total_discovered >= 5
        
        results.append({
            "source_id": s.id,
            "source_name": s.name,
            "source_type": s.source_type,
            "connection_status": s.connection_status,
            "total_discovered": total_discovered,
            "active_count": active_count,
            "expired_count": expired_count,
            "duplicates_prevented": int(dup_sum),
            "duplicate_rate": duplicate_rate,
            "expired_rate": expired_rate,
            "application_count": app_count,
            "conversion_rate": conversion_rate,
            "has_sufficient_sample": has_sufficient_sample,
            "last_sync_at": s.last_sync_at
        })
        
    return results

def get_application_sankey_data(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    source_platform: Optional[str] = None,
    category: Optional[str] = None
) -> Dict[str, Any]:
    """
    Computes genuine application pipeline flow for interactive Sankey visualization.
    Reflects actual historical status transitions and current application movement.
    NEVER generates fake synthetic flow percentages.
    """
    query = db.query(
        ApplicationStageTransition, 
        ApplicationRecord, 
        Opportunity
    ).join(
        ApplicationRecord, ApplicationStageTransition.application_id == ApplicationRecord.id
    ).outerjoin(
        Opportunity, ApplicationRecord.opportunity_id == Opportunity.id
    )
    
    if date_from:
        query = query.filter(ApplicationStageTransition.transitioned_at >= date_from)
    if date_to:
        query = query.filter(ApplicationStageTransition.transitioned_at <= date_to)
    if source_platform and source_platform != "all":
        query = query.filter(Opportunity.source_platform.ilike(f"%{source_platform}%"))
    if category and category != "all":
        query = query.filter(Opportunity.internship_category == category)
        
    records = query.all()
    
    flows = {}
    node_apps = {}
    
    for trans, app, opp in records:
        f_stage = trans.from_stage.lower().strip()
        t_stage = trans.to_stage.lower().strip()
        
        flow_key = (f_stage, t_stage)
        flows[flow_key] = flows.get(flow_key, 0) + 1
        
        app_info = {
            "application_id": app.id,
            "company_name": app.company_name,
            "job_title": app.job_title,
            "match_score": app.match_score,
            "source": opp.source_platform if opp else "Direct"
        }
        node_apps.setdefault(f_stage, []).append(app_info)
        node_apps.setdefault(t_stage, []).append(app_info)
        
    if not flows:
        app_query = db.query(ApplicationRecord, Opportunity).outerjoin(
            Opportunity, ApplicationRecord.opportunity_id == Opportunity.id
        )
        if source_platform and source_platform != "all":
            app_query = app_query.filter(Opportunity.source_platform.ilike(f"%{source_platform}%"))
        if category and category != "all":
            app_query = app_query.filter(Opportunity.internship_category == category)
            
        existing_apps = app_query.all()
        for app, opp in existing_apps:
            f_stage = "discovered"
            t_stage = app.status.lower().strip()
            flow_key = (f_stage, t_stage)
            flows[flow_key] = flows.get(flow_key, 0) + 1
            app_info = {
                "application_id": app.id,
                "company_name": app.company_name,
                "job_title": app.job_title,
                "match_score": app.match_score,
                "source": opp.source_platform if opp else "Direct"
            }
            node_apps.setdefault(f_stage, []).append(app_info)
            node_apps.setdefault(t_stage, []).append(app_info)
            
    if not flows:
        return {
            "empty": True,
            "nodes": [],
            "links": [],
            "total_transitions": 0,
            "message": "No application movement recorded yet. Hand off opportunities to track real pipeline flow."
        }
        
    STAGE_LABELS = {
        "discovered": "Discovered",
        "saved": "Saved",
        "ready_to_apply": "Ready to Apply",
        "applied": "Applied",
        "recruiter_response": "Recruiter Response",
        "screening": "Screening",
        "technical_interview": "Technical Interview",
        "hr_interview": "HR Interview",
        "interviewing": "Interviewing",
        "final_round": "Final Round",
        "offer": "Offer Received",
        "offered": "Offer Received",
        "rejected": "Rejected",
        "withdrawn": "Withdrawn",
        "no_response": "No Response"
    }

    distinct_stages = sorted(list(set([src for src, _ in flows.keys()] + [tgt for _, tgt in flows.keys()])))
    node_map = {stage: i for i, stage in enumerate(distinct_stages)}
    
    nodes = []
    for stage in distinct_stages:
        nodes.append({
            "id": node_map[stage],
            "name": STAGE_LABELS.get(stage, stage.replace("_", " ").title()),
            "stage_key": stage,
            "applications": node_apps.get(stage, [])[:15],
            "count": len(node_apps.get(stage, []))
        })
        
    links = []
    for (src, tgt), count in flows.items():
        links.append({
            "source": node_map[src],
            "target": node_map[tgt],
            "source_name": STAGE_LABELS.get(src, src.title()),
            "target_name": STAGE_LABELS.get(tgt, tgt.title()),
            "value": count
        })
        
    return {
        "empty": False,
        "nodes": nodes,
        "links": links,
        "total_transitions": sum(flows.values())
    }
