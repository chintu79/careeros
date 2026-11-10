from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models.notification import Notification

def create_notification(
    db: Session, 
    title: str, 
    message: str, 
    notification_type: str = "high_match", 
    opportunity_id: Optional[int] = None
) -> Notification:
    """Create in-app notification alert."""
    notif = Notification(
        title=title,
        message=message,
        notification_type=notification_type,
        opportunity_id=opportunity_id
    )
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif
