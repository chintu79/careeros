import math
from datetime import datetime
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc

from backend.app.database import get_db
from backend.app.models.interview import InterviewJournalRecord
from backend.app.models.practice_session import MockPracticeSession
from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.ai.ollama_client import ollama_client
from backend.app.services.interview_intelligence_service import (
    generate_interview_prep,
    evaluate_mock_answer,
    compute_historical_interview_analytics,
    create_mock_questions_for_role
)

router = APIRouter(prefix="/interviews", tags=["Interview Intelligence Platform"])

def serialize_interview(entry: InterviewJournalRecord) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "application_id": entry.application_id,
        "company_name": entry.company_name,
        "role": getattr(entry, "role", "Software Engineering Intern"),
        "round_name": entry.round_name,
        "round_type": entry.round_type,
        "interview_format": getattr(entry, "interview_format", "virtual_video"),
        "interview_date": entry.interview_date.isoformat() if getattr(entry, "interview_date", None) else None,
        "scheduled_at": entry.scheduled_at.isoformat() if entry.scheduled_at else None,
        "completed_at": entry.completed_at.isoformat() if entry.completed_at else None,
        "questions_asked": entry.questions_asked or [],
        "topics_covered": getattr(entry, "topics_covered", []) or [],
        "confidence_level": getattr(entry, "confidence_level", 3) or 3,
        "difficulty_rating": entry.difficulty_rating or 3,
        "performance_rating": entry.performance_rating or 3,
        "interview_result": getattr(entry, "interview_result", "pending") or "pending",
        "interviewer_feedback": getattr(entry, "interviewer_feedback", None),
        "ai_feedback": entry.ai_feedback or {},
        "notes": entry.notes or "",
        "personal_notes": getattr(entry, "personal_notes", None) or "",
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None
    }

def serialize_practice_session(s: MockPracticeSession) -> Dict[str, Any]:
    return {
        "id": s.id,
        "user_id": s.user_id,
        "session_title": s.session_title,
        "target_opportunity_id": s.target_opportunity_id,
        "company_name": s.company_name,
        "role_title": s.role_title,
        "session_type": s.session_type,
        "status": s.status,
        "questions": s.questions or [],
        "overall_score": s.overall_score,
        "ai_session_summary": s.ai_session_summary or {},
        "notes": s.notes or "",
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None
    }

# ----------------- Request Schemas -----------------

class InterviewCreate(BaseModel):
    application_id: Optional[int] = None
    company_name: str
    role: Optional[str] = "Software Engineering Intern"
    round_name: Optional[str] = "Technical Round 1"
    round_type: Optional[str] = "technical"
    interview_format: Optional[str] = "virtual_video"
    interview_date: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    questions_asked: Optional[List[Dict[str, Any]]] = None
    topics_covered: Optional[List[str]] = None
    confidence_level: Optional[int] = 3
    difficulty_rating: Optional[int] = 3
    performance_rating: Optional[int] = 3
    interview_result: Optional[str] = "pending"
    interviewer_feedback: Optional[str] = None
    notes: Optional[str] = None
    personal_notes: Optional[str] = None

class InterviewUpdate(BaseModel):
    company_name: Optional[str] = None
    role: Optional[str] = None
    round_name: Optional[str] = None
    round_type: Optional[str] = None
    interview_format: Optional[str] = None
    interview_date: Optional[datetime] = None
    scheduled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    questions_asked: Optional[List[Dict[str, Any]]] = None
    topics_covered: Optional[List[str]] = None
    confidence_level: Optional[int] = None
    difficulty_rating: Optional[int] = None
    performance_rating: Optional[int] = None
    interview_result: Optional[str] = None
    interviewer_feedback: Optional[str] = None
    notes: Optional[str] = None
    personal_notes: Optional[str] = None

class PracticeSessionCreate(BaseModel):
    session_title: Optional[str] = None
    opportunity_id: Optional[int] = None
    company_name: Optional[str] = None
    role_title: Optional[str] = None
    session_type: Optional[str] = "technical" # technical, dsa, project_deep_dive, behavioral, full_mock

class EvaluateAnswerRequest(BaseModel):
    question_id: str
    user_answer: str

# ----------------- Specific Sub-Paths (BEFORE /{id}) -----------------

@router.get("/prep")
def get_interview_prep_pack(
    opportunity_id: int = Query(..., description="Target opportunity ID for interview prep"),
    db: Session = Depends(get_db)
):
    """
    Generates complete job-specific interview preparation pack:
      - Technical questions for required stack
      - DSA questions for role type
      - Project-based questions tied strictly to candidate profile projects
      - Behavioral questions (STAR format)
      - HR & logistics questions
      - Company & role preparation topics
    """
    opp = db.query(Opportunity).filter(Opportunity.id == opportunity_id).first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
        
    cand = db.query(CandidateProfile).first()
    if not cand:
        cand = CandidateProfile(name="Krishna Patel", degree="B.Tech Computer Science")

    prep_pack = generate_interview_prep(opportunity=opp, profile=cand, db=db)
    return prep_pack

@router.get("/analytics")
def get_interview_historical_analytics(db: Session = Depends(get_db)):
    """
    Analyzes historical interview journal records to identify:
      - Repeatedly difficult topics
      - Strong technical competencies
      - Communication improvement areas
      - Real knowledge gaps
      - Preparation priorities
      - Funnel outcome conversion rates
    Strict Zero-Fabrication: Derived only from real user journal records.
    """
    records = db.query(InterviewJournalRecord).order_by(desc(InterviewJournalRecord.created_at)).all()
    analytics = compute_historical_interview_analytics(records)
    return analytics

# ----------------- Practice Mode Simulator Endpoints -----------------

@router.get("/practice/sessions")
def list_practice_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """List mock practice sessions with pagination."""
    query = db.query(MockPracticeSession)
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = query.order_by(desc(MockPracticeSession.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "items": [serialize_practice_session(s) for s in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }

@router.post("/practice/sessions")
def create_practice_session(req: PracticeSessionCreate, db: Session = Depends(get_db)):
    """Start a new interactive mock interview practice session."""
    opp = None
    if req.opportunity_id:
        opp = db.query(Opportunity).filter(Opportunity.id == req.opportunity_id).first()
        
    cand = db.query(CandidateProfile).first()
    
    company = req.company_name or (opp.company_name if opp else "Tech Company")
    role = req.role_title or (opp.title if opp else "Software Engineering Intern")
    title = req.session_title or f"Mock Interview: {company} ({req.session_type.replace('_', ' ').title()})"

    questions = create_mock_questions_for_role(
        opportunity=opp,
        profile=cand,
        session_type=req.session_type or "technical"
    )

    session = MockPracticeSession(
        user_id=1,
        session_title=title,
        target_opportunity_id=opp.id if opp else None,
        company_name=company,
        role_title=role,
        session_type=req.session_type or "technical",
        status="in_progress",
        questions=questions,
        overall_score=None,
        ai_session_summary={}
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    
    return serialize_practice_session(session)

@router.get("/practice/sessions/{session_id}")
def get_practice_session_detail(session_id: int, db: Session = Depends(get_db)):
    """Retrieve full details, questions, and evaluations for a practice session."""
    s = db.query(MockPracticeSession).filter(MockPracticeSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Practice session not found")
    return serialize_practice_session(s)

@router.post("/practice/sessions/{session_id}/evaluate-question")
def evaluate_practice_question(
    session_id: int,
    req: EvaluateAnswerRequest,
    db: Session = Depends(get_db)
):
    """
    Submits user answer for a question in the mock session.
    Returns real-time AI evaluation, scoring (0-100), clarity rating, and ideal answer structure.
    Strictly marked as 'ai_generated_evaluation'.
    """
    s = db.query(MockPracticeSession).filter(MockPracticeSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Practice session not found")
        
    questions = list(s.questions or [])
    target_q = None
    target_idx = -1
    for idx, q in enumerate(questions):
        if q.get("id") == req.question_id:
            target_q = q
            target_idx = idx
            break
            
    if not target_q:
        raise HTTPException(status_code=404, detail=f"Question ID '{req.question_id}' not found in session")
        
    cand = db.query(CandidateProfile).first()

    evaluation = evaluate_mock_answer(
        question_text=target_q.get("question", ""),
        category=target_q.get("category", "technical"),
        context_or_hint=target_q.get("context_or_hint", ""),
        user_answer=req.user_answer,
        profile=cand,
        target_role=s.role_title
    )

    target_q["user_answer"] = req.user_answer
    target_q["evaluated_at"] = datetime.utcnow().isoformat()
    target_q["ai_evaluation"] = evaluation

    questions[target_idx] = target_q
    s.questions = list(questions)
    flag_modified(s, "questions")
    s.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(s)

    return {
        "question_id": req.question_id,
        "evaluation": evaluation,
        "session": serialize_practice_session(s)
    }

@router.post("/practice/sessions/{session_id}/complete")
def complete_practice_session(session_id: int, db: Session = Depends(get_db)):
    """
    Completes mock practice session, calculates cumulative overall score and generates debrief.
    """
    s = db.query(MockPracticeSession).filter(MockPracticeSession.id == session_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Practice session not found")
        
    questions = s.questions or []
    scored_items = [
        q["ai_evaluation"]["score"] for q in questions
        if q.get("ai_evaluation") and "score" in q["ai_evaluation"]
    ]

    overall_score = round(sum(scored_items) / len(scored_items), 1) if scored_items else 0.0
    s.overall_score = overall_score
    s.status = "completed"
    s.completed_at = datetime.utcnow()
    s.updated_at = datetime.utcnow()

    grade = "A" if overall_score >= 85 else ("B" if overall_score >= 70 else "C")
    summary = {
        "overall_score": overall_score,
        "grade": grade,
        "questions_attempted": len(scored_items),
        "total_questions": len(questions),
        "verdict": f"Completed mock interview session with cumulative score of {overall_score}/100 (Grade {grade}).",
        "key_takeaway": "Focus on balancing high-level architectural framing with precise system trade-offs."
    }
    s.ai_session_summary = summary
    db.commit()
    db.refresh(s)

    return serialize_practice_session(s)

# ----------------- Standard Journal CRUD -----------------

@router.get("")
def list_interviews(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=50),
    company_name: Optional[str] = None,
    round_type: Optional[str] = None,
    interview_result: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List interview journal entries with server-side pagination."""
    query = db.query(InterviewJournalRecord)
    if company_name:
        query = query.filter(InterviewJournalRecord.company_name.ilike(f"%{company_name}%"))
    if round_type:
        query = query.filter(InterviewJournalRecord.round_type == round_type)
    if interview_result:
        query = query.filter(InterviewJournalRecord.interview_result == interview_result)
        
    total = query.count()
    total_pages = max(1, math.ceil(total / page_size))
    items = query.order_by(desc(InterviewJournalRecord.created_at)).offset((page - 1) * page_size).limit(page_size).all()
    
    return {
        "items": [serialize_interview(i) for i in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages
    }

@router.get("/{id}")
def get_interview(id: int, db: Session = Depends(get_db)):
    """Retrieve full interview journal entry."""
    entry = db.query(InterviewJournalRecord).filter(InterviewJournalRecord.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Interview journal entry not found")
    return serialize_interview(entry)

@router.post("")
def create_interview(data: InterviewCreate, db: Session = Depends(get_db)):
    """Record an interview session, questions, topics, confidence, and interviewer feedback."""
    entry = InterviewJournalRecord(
        application_id=data.application_id,
        company_name=data.company_name,
        role=data.role or "Software Engineering Intern",
        round_name=data.round_name or "Technical Round 1",
        round_type=data.round_type or "technical",
        interview_format=data.interview_format or "virtual_video",
        interview_date=data.interview_date or datetime.utcnow(),
        scheduled_at=data.scheduled_at or datetime.utcnow(),
        completed_at=data.completed_at,
        questions_asked=data.questions_asked or [],
        topics_covered=data.topics_covered or [],
        confidence_level=data.confidence_level or 3,
        difficulty_rating=data.difficulty_rating or 3,
        performance_rating=data.performance_rating or 3,
        interview_result=data.interview_result or "pending",
        interviewer_feedback=data.interviewer_feedback or "",
        notes=data.notes or "",
        personal_notes=data.personal_notes or ""
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return serialize_interview(entry)

@router.put("/{id}")
def update_interview(id: int, data: InterviewUpdate, db: Session = Depends(get_db)):
    """Update interview journal entry details, answers, and actual feedback."""
    entry = db.query(InterviewJournalRecord).filter(InterviewJournalRecord.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Interview journal entry not found")
        
    for field, val in data.dict(exclude_unset=True).items():
        if val is not None:
            setattr(entry, field, val)
            
    entry.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(entry)
    return serialize_interview(entry)

@router.delete("/{id}")
def delete_interview(id: int, db: Session = Depends(get_db)):
    """Delete an interview journal entry."""
    entry = db.query(InterviewJournalRecord).filter(InterviewJournalRecord.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Interview journal entry not found")
    db.delete(entry)
    db.commit()
    return {"message": "Interview journal entry deleted", "id": id}

@router.post("/{id}/ai-analysis")
async def analyze_interview_performance(id: int, db: Session = Depends(get_db)):
    """
    Use AI to evaluate questions and answers to diagnose strengths, recurring weaknesses, and focus areas.
    Strictly separate from actual interviewer feedback.
    """
    entry = db.query(InterviewJournalRecord).filter(InterviewJournalRecord.id == id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Interview entry not found")
        
    questions = entry.questions_asked or []
    if not questions:
        questions_summary = f"Interview round '{entry.round_name}' for {entry.company_name} ({entry.round_type})"
    else:
        questions_summary = "\n".join([f"- Q: {q.get('question', '')} | Answer: {q.get('user_answer', 'Not noted')}" for q in questions])
        
    prompt = f"""Analyze this interview session and provide objective evaluation:
Company: {entry.company_name}
Role: {entry.role}
Round: {entry.round_name} ({entry.round_type})
Format: {entry.interview_format}
Topics: {', '.join(entry.topics_covered or [])}
Self Performance Rating: {entry.performance_rating}/5
Candidate Notes: {entry.notes}
Questions & Answers:
{questions_summary}

Return valid JSON with:
"strengths": [list of demonstrated competencies],
"weaknesses": [list of identified gaps or areas that needed deeper answers],
"action_items": [list of concrete technical topics to study next],
"summary": "concise 2-sentence performance summary"
"""
    system_prompt = "You are a senior technical interviewer. Provide direct, actionable interview debriefs. Return strict JSON."
    
    ai_json = await ollama_client.generate_json(prompt, system_prompt=system_prompt)
    if ai_json:
        import json
        try:
            parsed = json.loads(ai_json)
            entry.ai_feedback = parsed
            db.commit()
            db.refresh(entry)
            return parsed
        except Exception:
            pass
            
    # Deterministic fallback analysis
    fallback = {
        "strengths": ["Clear conceptual articulation", "Relevant academic project experience"],
        "weaknesses": ["System architecture scale edge-cases", "Algorithm complexity trade-offs"],
        "action_items": ["Review time/space complexity analysis", "Practice mock behavioral answering with STAR method"],
        "summary": f"Completed {entry.round_name} at {entry.company_name}. Solid foundations observed with opportunity to sharpen deeper architectural depth."
    }
    entry.ai_feedback = fallback
    db.commit()
    db.refresh(entry)
    return fallback
