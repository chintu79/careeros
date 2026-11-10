from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.core.auth import get_current_user_id
from backend.app.database import get_db
from backend.app.services.rate_limit import rate_limited
from backend.app.models.chat import ChatConversation, ChatMessage
from backend.app.services.ai_assistant import process_user_chat_message
from backend.app.services.intelligence_engine import (
    run_job_matching_intelligence,
    run_resume_intelligence,
    run_interview_intelligence,
    run_career_growth_intelligence,
    run_application_intelligence
)

router = APIRouter(prefix="/chat", tags=["CareerOS AI Assistant"])

class ConversationCreate(BaseModel):
    title: Optional[str] = "Career Assistant Chat"

class MessageSend(BaseModel):
    content: str
    opportunity_id: Optional[int] = None
    workflow: Optional[str] = None

class JobMatchingRequest(BaseModel):
    opportunity_id: int

class ResumeIntelligenceRequest(BaseModel):
    opportunity_id: int

class InterviewPrepRequest(BaseModel):
    opportunity_id: int
    interview_id: Optional[int] = None

@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """List persistent conversations ordered by recency."""
    convs = db.query(ChatConversation).order_by(desc(ChatConversation.updated_at)).all()
    if not convs:
        # Create default initial conversation
        conv = ChatConversation(title="Career Assistant Chat")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        convs = [conv]
    return convs

@router.post("/conversations")
def create_conversation(data: ConversationCreate, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Create a new chat conversation session."""
    conv = ChatConversation(title=data.title or "New Conversation")
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv

@router.get("/conversations/{id}")
def get_conversation(id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Get conversation and all message history."""
    conv = db.query(ChatConversation).filter(ChatConversation.id == id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    messages = db.query(ChatMessage).filter(ChatMessage.conversation_id == id).order_by(ChatMessage.created_at.asc()).all()
    return {
        "conversation": conv,
        "messages": messages
    }

@router.delete("/conversations/{id}")
def delete_conversation(id: int, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Delete a conversation and all its messages."""
    conv = db.query(ChatConversation).filter(ChatConversation.id == id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted"}

@router.post("/conversations/{id}/messages", dependencies=[Depends(rate_limited("ai"))])
async def send_message(id: int, data: MessageSend, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Send user message, execute database tools or workflows if needed, and receive grounded AI response."""
    conv = db.query(ChatConversation).filter(ChatConversation.id == id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
        
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Message content cannot be empty")
        
    response = await process_user_chat_message(
        conversation_id=id,
        user_prompt=data.content,
        db=db,
        opportunity_id=data.opportunity_id,
        workflow=data.workflow,
        user_id=user_id
    )
    return response

# --- Dedicated Intelligence Workflow Endpoints ---

@router.post("/workflows/job-matching", dependencies=[Depends(rate_limited("ai"))])
async def get_job_matching_workflow(data: JobMatchingRequest, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Run Workflow 1: Job Matching Intelligence."""
    res = await run_job_matching_intelligence(opportunity_id=data.opportunity_id, db=db, user_id=user_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@router.post("/workflows/resume-intelligence", dependencies=[Depends(rate_limited("ai"))])
async def get_resume_intelligence_workflow(data: ResumeIntelligenceRequest, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Run Workflow 2: Resume Intelligence."""
    res = await run_resume_intelligence(opportunity_id=data.opportunity_id, db=db, user_id=user_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@router.post("/workflows/interview-prep", dependencies=[Depends(rate_limited("ai"))])
async def get_interview_prep_workflow(data: InterviewPrepRequest, db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Run Workflow 3: Interview Intelligence."""
    res = await run_interview_intelligence(opportunity_id=data.opportunity_id, interview_id=data.interview_id, db=db, user_id=user_id)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@router.post("/workflows/career-growth", dependencies=[Depends(rate_limited("ai"))])
async def get_career_growth_workflow(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Run Workflow 4: Career Growth Intelligence."""
    return await run_career_growth_intelligence(db=db, user_id=user_id)

@router.post("/workflows/application-intelligence", dependencies=[Depends(rate_limited("ai"))])
async def get_application_intelligence_workflow(db: Session = Depends(get_db), user_id: int = Depends(get_current_user_id)):
    """Run Workflow 5: Application Intelligence."""
    return await run_application_intelligence(db=db, user_id=user_id)
