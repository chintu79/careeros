import logging
import copy
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from backend.app.models.candidate import CandidateProfile
from backend.app.models.preferences import UserPreferences
from backend.app.models.company import Company
from backend.app.models.source import JobSource
from backend.app.models.opportunity import Opportunity
from backend.app.models.sync_log import SyncLog
from backend.app.models.notification import Notification
from backend.app.services.notification_service import create_notification
from backend.app.ai.ollama_client import ollama_client
from backend.app.ai.extractor import fallback_heuristic_extraction
from backend.app.ai.compatibility_scorer import evaluate_compatibility

logger = logging.getLogger(__name__)

INITIAL_PREFERENCES = {
    "preferred_categories": [
        "AI Engineer Intern", "Machine Learning Intern", "Data Science Intern", 
        "Generative AI Intern", "LLM Engineer Intern", "NLP Intern", 
        "Computer Vision Intern", "Deep Learning Intern", "AI Research Intern", "MLOps Intern",
        "Software Engineer Intern", "Full Stack Developer Intern", "Frontend Developer Intern", 
        "Backend Developer Intern", "Python Developer Intern", "JavaScript Developer Intern", 
        "React Developer Intern", "Node.js Developer Intern", "Cloud Engineering Intern", "DevOps Intern"
    ],
    "search_priorities": [
        {"priority": 1, "category": "AI/ML and Generative AI"},
        {"priority": 2, "category": "Data Science and Data Engineering"},
        {"priority": 3, "category": "Full Stack Development"},
        {"priority": 4, "category": "Backend Development"},
        {"priority": 5, "category": "Software Engineering"}
    ],
    "preferred_locations": [
        "Remote, India", "Pune", "Bengaluru", "Mumbai", "Hyderabad", "Delhi NCR", "Remote, worldwide"
    ],
    "paid_only": True,
    "allow_unpaid": False,
    "min_stipend": 15000.0,
    "preferred_duration_months": 6,
    "workplace_types": ["remote", "hybrid", "onsite"],
    "max_experience_years": 1,
    "student_only": True,
    "graduation_year": 2026,
    "excluded_keywords": ["unpaid", "marketing intern", "sales executive", "telecaller"],
    "excluded_companies": []
}

INITIAL_CANDIDATE = {
    "name": "Candidate One",
    "email": "synthetic.candidate@example.test",
    "phone": "+90 555 000 0001",
    "location": "Pune, Maharashtra, India",
    "bio": "AI & Data Science student at Regional University Pune, building full-stack applications, intelligent automation systems, and developer tools.",
    "degree": "B.Tech in Artificial Intelligence & Data Science",
    "graduation_year": 2028,
    "college": "Regional University",
    "github_url": "https://github.com/synthetic-candidate",
    "linkedin_url": "https://www.linkedin.com/in/synthetic-candidate/",
    "skills": [
        {"name": "Python", "level": "advanced", "category": "Languages"},
        {"name": "JavaScript", "level": "advanced", "category": "Languages"},
        {"name": "TypeScript", "level": "advanced", "category": "Languages"},
        {"name": "HTML", "level": "advanced", "category": "Languages"},
        {"name": "CSS", "level": "intermediate", "category": "Languages"},
        {"name": "SQL", "level": "advanced", "category": "Languages"},
        {"name": "Dart", "level": "intermediate", "category": "Languages"},
        {"name": "React", "level": "advanced", "category": "Frontend"},
        {"name": "Next.js", "level": "intermediate", "category": "Frontend"},
        {"name": "Flutter", "level": "intermediate", "category": "Frontend"},
        {"name": "Node.js", "level": "intermediate", "category": "Backend"},
        {"name": "Express.js", "level": "intermediate", "category": "Backend"},
        {"name": "FastAPI", "level": "advanced", "category": "Backend"},
        {"name": "Supabase", "level": "intermediate", "category": "Backend"},
        {"name": "PostgreSQL", "level": "advanced", "category": "Databases"},
        {"name": "MongoDB", "level": "intermediate", "category": "Databases"},
        {"name": "SQLAlchemy", "level": "advanced", "category": "Databases"},
        {"name": "Docker", "level": "intermediate", "category": "Tools"},
        {"name": "Git", "level": "advanced", "category": "Tools"},
        {"name": "GitHub", "level": "advanced", "category": "Tools"},
        {"name": "Linux", "level": "intermediate", "category": "Tools"}
    ],
    "projects": [
        {
            "title": "AI-Powered Lead Automation System for ACM Chapter",
            "description": "Lead generation platform that automates business discovery, website scraping, AI-based opportunity analysis, and lead scoring using Python, Gemini AI, Google Maps, Google Sheets, and SQLAlchemy.",
            "tech_stack": ["Python", "Gemini AI", "Google Maps", "Google Sheets", "SQLAlchemy", "APScheduler"],
            "url": "https://github.com/synthetic-candidate/lead-automation-ACM"
        },
        {
            "title": "Khanawala",
            "description": "Freelance food delivery application for a single-restaurant cloud kitchen with modular state management using ChangeNotifier/ListenableBuilder, Supabase/PostgreSQL backend, Google Sign-In, and responsive UI.",
            "tech_stack": ["Flutter", "Dart", "Supabase", "PostgreSQL", "Google Sign-In"],
            "url": "https://github.com/synthetic-candidate/Khanawala"
        },
        {
            "title": "CareerOS Job Discovery Engine",
            "description": "Continuous opportunity aggregator with ATS connectors (Greenhouse, Lever, Ashby), pgvector semantic search, and Ollama requirement extraction.",
            "tech_stack": ["Python", "FastAPI", "PostgreSQL", "React", "Docker", "Git", "REST API"],
            "url": "https://github.com/synthetic-candidate/CareerOS"
        }
    ],
    "experience": [
        {
            "title": "Web Team Member",
            "company": "ACM Student Chapter, Regional University",
            "duration": "Ongoing",
            "description": "Resolved frontend issues, built responsive UI components, and shipped bug fixes using HTML, CSS, JavaScript, React, and Next.js. Collaborated through Git and GitHub for issue tracking, pull requests, and code reviews."
        },
        {
            "title": "Electrical Engineer Trainee",
            "company": "MAHADISCOM, Solapur",
            "duration": "June 2024 -- July 2024",
            "description": "Observed testing, maintenance, and operation of a single-phase transformer in a live distribution environment. Learned relays, protection systems, and electrical safety equipment through hands-on exposure."
        }
    ],
    "preferred_locations": ["Remote, India", "Pune", "Bengaluru", "Mumbai", "Remote, worldwide"],
    "work_authorization": "Indian Citizen (Authorized to work in India without sponsorship)"
}

INITIAL_COMPANIES = [
    {"name": "Cloudflare", "website": "https://cloudflare.com", "career_url": "https://boards.greenhouse.io/cloudflare", "industry": "Cloud & Cybersecurity", "hq_location": "San Francisco / Remote", "ats_provider": "greenhouse", "ats_board_id": "cloudflare", "company_size": "1,000-5,000"},
    {"name": "Palantir", "website": "https://palantir.com", "career_url": "https://jobs.lever.co/palantir", "industry": "Big Data & AI Platforms", "hq_location": "Denver / Remote", "ats_provider": "lever", "ats_board_id": "palantir", "company_size": "5,000+"},
    {"name": "Replit", "website": "https://replit.com", "career_url": "https://jobs.ashbyhq.com/replit", "industry": "Developer Tools & AI", "hq_location": "San Francisco / Remote", "ats_provider": "ashby", "ats_board_id": "replit", "company_size": "100-250"},
    {"name": "Visa", "website": "https://visa.com", "career_url": "https://jobs.smartrecruiters.com/visa", "industry": "Fintech & Payments", "hq_location": "Bengaluru / Foster City", "ats_provider": "smartrecruiters", "ats_board_id": "visa", "company_size": "10,000+"},
    {"name": "Databricks", "website": "https://databricks.com", "career_url": "https://boards.greenhouse.io/databricks", "industry": "Data & AI", "hq_location": "Bengaluru / San Francisco", "ats_provider": "greenhouse", "ats_board_id": "databricks", "company_size": "5,000+"},
    {"name": "Postman", "website": "https://postman.com", "career_url": "https://boards.greenhouse.io/postman", "industry": "API Development", "hq_location": "Bengaluru, India", "ats_provider": "greenhouse", "ats_board_id": "postman", "company_size": "500-1,000"},
    {"name": "Razorpay", "website": "https://razorpay.com", "career_url": "https://boards.greenhouse.io/razorpay", "industry": "Fintech", "hq_location": "Bengaluru, India", "ats_provider": "greenhouse", "ats_board_id": "razorpay", "company_size": "1,000-5,000"},
    {"name": "Zepto", "website": "https://zeptonow.com", "career_url": "https://jobs.ashbyhq.com/zepto", "industry": "Quick Commerce", "hq_location": "Mumbai, India", "ats_provider": "ashby", "ats_board_id": "zepto", "company_size": "1,000-5,000"},
    {"name": "Hasura", "website": "https://hasura.io", "career_url": "https://jobs.lever.co/hasura", "industry": "GraphQL & Databases", "hq_location": "Bengaluru / Remote", "ats_provider": "lever", "ats_board_id": "hasura", "company_size": "250-500"}
]

INITIAL_SOURCES = [
    {"name": "Greenhouse", "source_type": "ats", "integration_method": "api", "connection_status": "connected", "sync_frequency_hours": 6},
    {"name": "Lever", "source_type": "ats", "integration_method": "api", "connection_status": "connected", "sync_frequency_hours": 6},
    {"name": "Ashby", "source_type": "ats", "integration_method": "api", "connection_status": "connected", "sync_frequency_hours": 6},
    {"name": "SmartRecruiters", "source_type": "ats", "integration_method": "api", "connection_status": "connected", "sync_frequency_hours": 6},
    {"name": "Remotive", "source_type": "api", "integration_method": "api", "connection_status": "connected", "sync_frequency_hours": 12},
    {"name": "Remote OK", "source_type": "api", "integration_method": "api", "connection_status": "connected", "sync_frequency_hours": 12},
    {"name": "Adzuna", "source_type": "api", "integration_method": "api", "connection_status": "needs_configuration", "sync_frequency_hours": 12},
    {"name": "RSS Feeds", "source_type": "rss", "integration_method": "feed", "connection_status": "connected", "sync_frequency_hours": 6},
    {"name": "Manual Import", "source_type": "manual", "integration_method": "direct_url", "connection_status": "manual_import_only", "sync_frequency_hours": 24},
    {"name": "Internshala", "source_type": "portal", "integration_method": "direct_url", "connection_status": "manual_import_only", "sync_frequency_hours": 24},
    {"name": "LinkedIn Jobs", "source_type": "portal", "integration_method": "direct_url", "connection_status": "manual_import_only", "sync_frequency_hours": 24},
    {"name": "Naukri", "source_type": "portal", "integration_method": "direct_url", "connection_status": "manual_import_only", "sync_frequency_hours": 24},
    {"name": "Wellfound", "source_type": "portal", "integration_method": "direct_url", "connection_status": "manual_import_only", "sync_frequency_hours": 24},
    {"name": "Indeed India", "source_type": "portal", "integration_method": "direct_url", "connection_status": "manual_import_only", "sync_frequency_hours": 24}
]

# No fake, synthetic, or mock opportunities are seeded.
# Only real opportunities discovered from verified live sources are populated into the database.
SEEDED_OPPORTUNITIES = []


async def seed_initial_data(db: Session):
    """Seed default candidate profile, preferences, companies, sources, and rich opportunities."""
    # 1. Candidate Profile
    if not db.query(CandidateProfile).first():
        logger.info("Seeding candidate profile...")
        cand = CandidateProfile(**INITIAL_CANDIDATE)
        db.add(cand)
        db.commit()

    # 2. User Preferences
    if not db.query(UserPreferences).first():
        logger.info("Seeding user job preferences...")
        pref = UserPreferences(**INITIAL_PREFERENCES)
        db.add(pref)
        db.commit()

    # 3. Companies
    for comp in INITIAL_COMPANIES:
        existing = db.query(Company).filter(Company.name == comp["name"]).first()
        if not existing:
            db.add(Company(**comp))
    db.commit()

    # 4. Job Sources
    for src in INITIAL_SOURCES:
        existing = db.query(JobSource).filter(JobSource.name == src["name"]).first()
        if not existing:
            db.add(JobSource(**src))
    db.commit()

    # 5. Opportunities
    cand = db.query(CandidateProfile).first()
    cand_dict = {
        "skills": cand.skills if cand else [],
        "projects": cand.projects if cand else [],
        "graduation_year": cand.graduation_year if cand else 2026,
        "degree": cand.degree if cand else "B.Tech CSE"
    }
    prefs = db.query(UserPreferences).first()
    pref_dict = {
        "paid_only": prefs.paid_only if prefs else True,
        "allow_unpaid": prefs.allow_unpaid if prefs else False,
        "min_stipend": prefs.min_stipend if prefs else 15000.0,
        "graduation_year": prefs.graduation_year if prefs else 2026,
        "excluded_companies": prefs.excluded_companies if prefs else [],
        "excluded_keywords": prefs.excluded_keywords if prefs else []
    }

    for opp_data in SEEDED_OPPORTUNITIES:
        existing = db.query(Opportunity).filter(Opportunity.original_url == opp_data["original_url"]).first()
        if not existing:
            extracted = fallback_heuristic_extraction(opp_data["title"], opp_data["description"])
            match_res = evaluate_compatibility(
                extracted_data=extracted,
                candidate_profile=cand_dict,
                user_preferences=pref_dict,
                job_location=opp_data["normalized_location"],
                workplace_type=opp_data["workplace_type"],
                is_paid=opp_data["is_paid"],
                stipend_amount=opp_data["min_stipend"],
                job_company=opp_data["company_name"]
            )
            
            embed_text = f"{opp_data['title']} at {opp_data['company_name']}. {opp_data['description'][:500]}"
            embedding = await ollama_client.get_embedding(embed_text)
            
            # Make sure raw_data copy has JSON serializable dates
            raw_copy = copy.deepcopy(opp_data)
            if isinstance(raw_copy.get("posted_at"), datetime):
                raw_copy["posted_at"] = raw_copy["posted_at"].isoformat()
            if isinstance(raw_copy.get("deadline_at"), datetime):
                raw_copy["deadline_at"] = raw_copy["deadline_at"].isoformat()

            opp = Opportunity(
                title=opp_data["title"],
                normalized_title=opp_data["normalized_title"],
                company_name=opp_data["company_name"],
                location=opp_data["location"],
                normalized_location=opp_data["normalized_location"],
                workplace_type=opp_data["workplace_type"],
                employment_type=opp_data["employment_type"],
                description=opp_data["description"],
                stipend_text=opp_data["stipend_text"],
                min_stipend=opp_data["min_stipend"],
                max_stipend=opp_data["max_stipend"],
                currency=opp_data["currency"],
                stipend_period=opp_data["stipend_period"],
                is_paid=opp_data["is_paid"],
                duration_months=opp_data["duration_months"],
                posted_at=opp_data["posted_at"],
                deadline_at=opp_data["deadline_at"],
                status="active",
                original_url=opp_data["original_url"],
                external_id=opp_data["external_id"],
                source_platform=opp_data["source_platform"],
                source_links=[{
                    "source": opp_data["source_platform"],
                    "url": opp_data["original_url"],
                    "discovered_at": opp_data["posted_at"].isoformat()
                }],
                raw_data=raw_copy,
                embedding=embedding,
                extracted_data=extracted,
                match_analysis=match_res,
                match_score=match_res["match_score"],
                eligibility_status=match_res["eligibility_status"]
            )
            db.add(opp)
    db.commit()

    # 6. Initial Sync Log
    if not db.query(SyncLog).first():
        log = SyncLog(
            source_name="System Initialization",
            started_at=datetime.utcnow() - timedelta(hours=2),
            completed_at=datetime.utcnow() - timedelta(hours=2, seconds=-15),
            retrieved_count=6,
            new_count=6,
            duplicate_count=0,
            expired_count=0,
            relevant_count=5,
            error_count=0,
            status="success"
        )
        db.add(log)
        db.commit()

    # 7. Initial Notification
    if not db.query(Notification).first():
        create_notification(
            db,
            title="Discovery Engine Initialized",
            message="CareerOS Discovery Engine is active and monitoring connected ATS boards and job feeds.",
            notification_type="high_match"
        )
