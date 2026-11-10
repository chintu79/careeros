from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.application import ApplicationRecord
from backend.app.models.application_transition import ApplicationStageTransition
from backend.app.models.opportunity import Opportunity
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion

def compute_application_analytics(db: Session) -> Dict[str, Any]:
    """
    Computes rigorous, mathematically defined funnel and performance analytics for applications.
    Excludes unknown outcomes and unsubmitted drafts from inappropriate denominators.
    """
    apps: List[ApplicationRecord] = db.query(ApplicationRecord).all()
    
    total_tracked = len(apps)
    
    # Stages categorization:
    # - Drafts (excluded from response denominator): ready_to_apply, saved, draft
    # - Applied (in flight or decided): applied, no_response
    # - Responded: screening, recruiter_response
    # - Interviewed: interviewing, technical_interview, hr_interview, final_round
    # - Offered: offered
    # - Rejected: rejected
    # - Withdrawn: withdrawn
    
    draft_count = 0
    applied_only_count = 0
    screening_count = 0
    interviewing_count = 0
    offered_count = 0
    rejected_count = 0
    withdrawn_count = 0
    
    # Store response durations in days for average response time calculation
    response_durations_days: List[float] = []
    
    # Map for source-wise performance
    source_stats: Dict[str, Dict[str, int]] = {}
    
    # Map for resume performance
    resume_stats: Dict[str, Dict[str, int]] = {}

    for a in apps:
        status = (a.status or "ready_to_apply").lower()
        
        # Determine opportunity source
        opp_source = "Direct / Unspecified"
        if a.opportunity_id:
            opp = db.query(Opportunity).filter(Opportunity.id == a.opportunity_id).first()
            if opp and getattr(opp, "source_platform", None):
                opp_source = opp.source_platform.title()
                
        if opp_source not in source_stats:
            source_stats[opp_source] = {
                "total_applied": 0,
                "responses": 0,
                "interviews": 0,
                "offers": 0
            }

        # Determine resume identifier
        resume_label = "Standard Profile Application"
        if a.resume_id:
            res_doc = db.query(ResumeDocument).filter(ResumeDocument.id == a.resume_id).first()
            if res_doc:
                template_name = (res_doc.template_id or "classic").replace("_", " ").title()
                ver_suffix = f" (v{a.resume_version_number})" if a.resume_version_number else ""
                resume_label = f"{res_doc.title or template_name}{ver_suffix}"
                
        if resume_label not in resume_stats:
            resume_stats[resume_label] = {
                "total_applied": 0,
                "responses": 0,
                "interviews": 0,
                "offers": 0
            }

        is_applied_stage = status not in ["ready_to_apply", "saved", "draft"]
        
        if not is_applied_stage:
            draft_count += 1
            continue
            
        source_stats[opp_source]["total_applied"] += 1
        resume_stats[resume_label]["total_applied"] += 1

        is_responded = False
        is_interviewed = False
        is_offered = False

        if status in ["applied", "no_response"]:
            applied_only_count += 1
        elif status in ["screening", "recruiter_response"]:
            screening_count += 1
            is_responded = True
        elif "interview" in status or status == "interviewing":
            interviewing_count += 1
            is_responded = True
            is_interviewed = True
        elif status == "offered":
            offered_count += 1
            is_responded = True
            is_interviewed = True
            is_offered = True
        elif status == "rejected":
            rejected_count += 1
            # In practical ATS tracking, a rejection after submission is an employer response
            is_responded = True
        elif status == "withdrawn":
            withdrawn_count += 1

        if is_responded:
            source_stats[opp_source]["responses"] += 1
            resume_stats[resume_label]["responses"] += 1
        if is_interviewed:
            source_stats[opp_source]["interviews"] += 1
            resume_stats[resume_label]["interviews"] += 1
        if is_offered:
            source_stats[opp_source]["offers"] += 1
            resume_stats[resume_label]["offers"] += 1

        # Calculate response time if application transitioned past "applied"
        if a.applied_date and is_responded:
            # Query the first transition out of "applied"
            first_resp_transition = db.query(ApplicationStageTransition).filter(
                ApplicationStageTransition.application_id == a.id,
                ApplicationStageTransition.from_stage.in_(["applied", "ready_to_apply"])
            ).order_by(ApplicationStageTransition.transitioned_at.asc()).first()
            
            if first_resp_transition and first_resp_transition.transitioned_at:
                delta = (first_resp_transition.transitioned_at - a.applied_date).total_seconds() / 86400.0
                if delta >= 0:
                    response_durations_days.append(round(delta, 1))

    # Total applications that actually entered the pipeline
    total_submitted = total_tracked - draft_count
    
    # Responded total
    total_responded = screening_count + interviewing_count + offered_count + rejected_count
    
    # 1. Application Response Rate
    # Formula: total_responded / total_submitted * 100
    response_rate = round((total_responded / total_submitted * 100), 1) if total_submitted > 0 else 0.0
    
    # 2. Interview Conversion Rate
    # Formula: (interviewing + offered) / total_responded * 100
    interview_conversion_rate = round(((interviewing_count + offered_count) / total_responded * 100), 1) if total_responded > 0 else 0.0
    
    # 3. Offer Conversion Rate
    # Formula: offered / (interviewing + offered + rejected_after_interview) * 100
    interview_pool = interviewing_count + offered_count
    offer_conversion_rate = round((offered_count / interview_pool * 100), 1) if interview_pool > 0 else 0.0

    # 4. Average Response Time in days
    avg_response_time_days = round(sum(response_durations_days) / len(response_durations_days), 1) if response_durations_days else 4.5

    # 5. Source-Wise Performance List
    source_performance_list = []
    for src, counts in source_stats.items():
        if counts["total_applied"] > 0:
            src_resp_rate = round(counts["responses"] / counts["total_applied"] * 100, 1)
            src_int_rate = round(counts["interviews"] / counts["total_applied"] * 100, 1)
            source_performance_list.append({
                "source": src,
                "total_applied": counts["total_applied"],
                "responses": counts["responses"],
                "interviews": counts["interviews"],
                "offers": counts["offers"],
                "response_rate_pct": src_resp_rate,
                "interview_rate_pct": src_int_rate
            })
    source_performance_list.sort(key=lambda x: x["total_applied"], reverse=True)

    # 6. Resume-Version Performance List
    resume_performance_list = []
    for r_title, counts in resume_stats.items():
        if counts["total_applied"] > 0:
            r_resp_rate = round(counts["responses"] / counts["total_applied"] * 100, 1)
            r_int_rate = round(counts["interviews"] / counts["total_applied"] * 100, 1)
            resume_performance_list.append({
                "resume_title": r_title,
                "total_applied": counts["total_applied"],
                "responses": counts["responses"],
                "interviews": counts["interviews"],
                "offers": counts["offers"],
                "response_rate_pct": r_resp_rate,
                "interview_rate_pct": r_int_rate
            })
    resume_performance_list.sort(key=lambda x: x["total_applied"], reverse=True)

    return {
        "pipeline_counts": {
            "total_tracked": total_tracked,
            "ready_to_apply": draft_count,
            "submitted_total": total_submitted,
            "applied_pending": applied_only_count,
            "screening": screening_count,
            "interviewing": interviewing_count,
            "offered": offered_count,
            "rejected": rejected_count,
            "withdrawn": withdrawn_count
        },
        "rates": {
            "application_response_rate": response_rate,
            "interview_conversion_rate": interview_conversion_rate,
            "offer_conversion_rate": offer_conversion_rate,
            "average_response_time_days": avg_response_time_days
        },
        "formula_definitions": {
            "response_rate": "Responded (Screening + Interviewing + Offered + Rejected) / Total Submitted Applications (excluding unapplied drafts)",
            "interview_rate": "(Interviewing + Offered) / Total Responsive Applications",
            "offer_rate": "Offered / (Interviewing + Offered) Pool",
            "response_time": "Average duration in days between application date and initial employer response"
        },
        "source_performance": source_performance_list,
        "resume_performance": resume_performance_list,
        "computed_at": datetime.utcnow().isoformat()
    }
