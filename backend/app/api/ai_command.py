from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.chat import ChatConversation, ChatMessage
from backend.app.models.ai_audit import AIActionAuditLog
from backend.app.services.global_ai_command_service import (
    process_global_ai_command,
    generate_ai_command_stream,
    execute_consequential_action,
    reject_consequential_action,
    generate_context_suggestions,
    PERMITTED_TOOLS
)

router = APIRouter(prefix="/command", tags=["Global AI Command Center"])


class AICommandRequest(BaseModel):
    content: str
    conversation_id: Optional[int] = None
    opportunity_id: Optional[int] = None


class ActionRejectRequest(BaseModel):
    reason: Optional[str] = "Declined by user"


@router.get("/tools")
def get_permitted_tools():
    """Returns the strict registry of permitted structured tools."""
    return {
        "count": len(PERMITTED_TOOLS),
        "tools": [
            {
                "name": name,
                "description": info["description"],
                "consequential": info["consequential"]
            }
            for name, info in PERMITTED_TOOLS.items()
        ]
    }


@router.get("/suggestions")
def get_suggestions(db: Session = Depends(get_db)):
    """Returns context-aware prompt suggestions based on user career data."""
    return {"suggestions": generate_context_suggestions(db)}


@router.post("/message")
async def execute_command(req: AICommandRequest, db: Session = Depends(get_db)):
    """
    Executes a global AI command synchronously.
    Dispatches to structured tools, produces grounded markdown, and prepares action proposals if consequential.
    """
    if not req.content.strip():
        raise HTTPException(status_code=400, detail="Command content cannot be empty")

    conv_id = req.conversation_id
    if not conv_id:
        conv = db.query(ChatConversation).order_by(desc(ChatConversation.updated_at)).first()
        if not conv:
            conv = ChatConversation(title="AI Command Center Session")
            db.add(conv)
            db.commit()
            db.refresh(conv)
        conv_id = conv.id

    # Record user message
    user_msg = ChatMessage(
        conversation_id=conv_id,
        sender="user",
        content=req.content
    )
    db.add(user_msg)
    db.commit()

    # Process command via structured service
    result = await process_global_ai_command(
        prompt=req.content,
        db=db,
        conversation_id=conv_id,
        opportunity_id=req.opportunity_id
    )

    # Record assistant message
    asst_msg = ChatMessage(
        conversation_id=conv_id,
        sender="assistant",
        content=result["response_markdown"],
        tool_calls=[{"tool": result["tool_name"], "is_consequential": result["is_consequential"]}]
    )
    db.add(asst_msg)
    db.commit()
    db.refresh(asst_msg)

    return {
        "id": asst_msg.id,
        "conversation_id": conv_id,
        "sender": "assistant",
        "content": result["response_markdown"],
        "tool_executed": result["tool_name"],
        "is_consequential": result["is_consequential"],
        "action_proposal": result.get("action_proposal"),
        "suggested_actions": result.get("suggested_actions", []),
        "created_at": asst_msg.created_at.isoformat()
    }


@router.get("/stream")
async def stream_command(
    prompt: str = Query(..., min_length=1),
    conversation_id: Optional[int] = None,
    opportunity_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Server-Sent Events (SSE) streaming endpoint for real-time thought streaming,
    tool execution, and chunked Markdown responses.
    """
    return StreamingResponse(
        generate_ai_command_stream(
            prompt=prompt,
            db=db,
            conversation_id=conversation_id,
            opportunity_id=opportunity_id
        ),
        media_type="text/event-stream"
    )


@router.get("/actions/pending")
def list_pending_actions(db: Session = Depends(get_db)):
    """Returns all consequential actions currently waiting for explicit user confirmation."""
    pending = db.query(AIActionAuditLog).filter(
        AIActionAuditLog.status == "pending_approval"
    ).order_by(desc(AIActionAuditLog.created_at)).all()

    return {
        "count": len(pending),
        "actions": [
            {
                "id": a.id,
                "action_type": a.action_type,
                "tool_name": a.tool_name,
                "description": a.description,
                "data_payload": a.data_payload,
                "status": a.status,
                "requires_approval": a.requires_approval,
                "created_at": a.created_at.isoformat()
            }
            for a in pending
        ]
    }


@router.post("/actions/{action_id}/execute")
def approve_and_execute_action(action_id: int, db: Session = Depends(get_db)):
    """
    User approval endpoint for consequential operations.
    Validates confirmation and performs actual database mutation with audit logging.
    """
    result = execute_consequential_action(action_id=action_id, db=db)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@router.post("/actions/{action_id}/reject")
def reject_action(action_id: int, req: ActionRejectRequest, db: Session = Depends(get_db)):
    """
    User rejection endpoint for consequential operations.
    Records cancellation in audit log.
    """
    result = reject_consequential_action(action_id=action_id, reason=req.reason, db=db)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/audit-log")
def get_action_audit_log(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Returns comprehensive chronological audit log of all AI tool executions and approval outcomes."""
    logs = db.query(AIActionAuditLog).order_by(
        desc(AIActionAuditLog.created_at)
    ).limit(limit).all()

    return {
        "count": len(logs),
        "logs": [
            {
                "id": l.id,
                "action_type": l.action_type,
                "tool_name": l.tool_name,
                "description": l.description,
                "data_payload": l.data_payload,
                "status": l.status,
                "user_confirmed": l.user_confirmed,
                "rejection_reason": l.rejection_reason,
                "result_summary": l.result_summary,
                "created_at": l.created_at.isoformat(),
                "executed_at": l.executed_at.isoformat() if l.executed_at else None
            }
            for l in logs
        ]
    }
