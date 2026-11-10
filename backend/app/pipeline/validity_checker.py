from datetime import datetime, timedelta
from typing import Dict, Any

def check_opportunity_validity(job_data: Dict[str, Any]) -> str:
    """
    Stage 4: Expiration & Validity Checking.
    Returns: 'active', 'possibly_expired', 'expired', 'closed', or 'unable_to_verify'
    """
    now = datetime.utcnow()
    deadline = job_data.get("deadline_at")
    
    if deadline:
        if isinstance(deadline, str):
            try:
                deadline = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
            except Exception:
                deadline = None
                
    if deadline:
        if deadline < now:
            return "expired"
        elif deadline - now < timedelta(days=3):
            return "possibly_expired"
            
    posted_at = job_data.get("posted_at")
    if posted_at:
        if isinstance(posted_at, str):
            try:
                posted_at = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            except Exception:
                posted_at = None
                
    if posted_at and (now - posted_at > timedelta(days=90)):
        return "possibly_expired"
        
    return "active"
