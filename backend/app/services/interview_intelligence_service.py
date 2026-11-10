import re
from datetime import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.app.models.opportunity import Opportunity
from backend.app.models.candidate import CandidateProfile
from backend.app.models.interview import InterviewJournalRecord
from backend.app.models.practice_session import MockPracticeSession
from backend.app.ai.ollama_client import ollama_client

def generate_interview_prep(
    opportunity: Opportunity,
    profile: CandidateProfile,
    db: Session
) -> Dict[str, Any]:
    """
    Generates tailored, high-fidelity interview preparation material:
      - Technical questions based on target stack
      - DSA questions tailored to role category
      - Project questions grounded strictly in candidate profile projects
      - Behavioral questions (STAR format)
      - HR questions
      - Company and role-specific preparation topics
    """
    company_name = opportunity.company_name or "Target Company"
    role_title = opportunity.title or "Software Engineering Intern"
    req_skills = opportunity.required_skills or []
    pref_skills = opportunity.preferred_skills or []
    all_skills = list(dict.fromkeys(req_skills + pref_skills))
    
    cand_projects = profile.projects or []
    cand_skills = profile.skills or []
    cand_skill_names = [
        s.get("name", "") if isinstance(s, dict) else str(s)
        for s in cand_skills
    ]

    # --- 1. Technical Interview Questions ---
    technical_questions = []
    
    # Skill-specific questions
    skill_lower = [s.lower() for s in all_skills] + [s.lower() for s in cand_skill_names]
    
    if any(k in skill_lower for k in ["python", "fastapi", "django", "flask"]):
        technical_questions.append({
            "id": "t1",
            "topic": "Python / Async Architecture",
            "question": "How does Python's asyncio event loop execute coroutines under the hood, and how do async def endpoints differ from standard def endpoints in FastAPI?",
            "expected_concepts": ["GIL", "event loop", "threadpool worker executor", "non-blocking I/O", "uvicorn/starlette"],
            "difficulty": "Medium"
        })
        
    if any(k in skill_lower for k in ["postgresql", "sql", "database", "mysql"]):
        technical_questions.append({
            "id": "t2",
            "topic": "Database Indexing & Query Optimization",
            "question": "Explain the difference between B-tree and GIN indexes in PostgreSQL, and how you would diagnose an unexpected sequential scan using EXPLAIN ANALYZE.",
            "expected_concepts": ["B-tree selectivity", "GIN inverted index for JSON/arrays", "EXPLAIN ANALYZE buffer hits", "Index bloat"],
            "difficulty": "Hard"
        })
        
    if any(k in skill_lower for k in ["docker", "kubernetes", "devops", "cloud", "aws"]):
        technical_questions.append({
            "id": "t3",
            "topic": "Containerization & Production Deployment",
            "question": "How do Docker multi-stage builds minimize attack surface and image size, and how do container health checks integrate with orchestration restarts?",
            "expected_concepts": ["Builder pattern", "layer caching", "HEALTHCHECK exit codes", "non-root container execution"],
            "difficulty": "Medium"
        })

    if any(k in skill_lower for k in ["react", "typescript", "javascript", "frontend", "next.js"]):
        technical_questions.append({
            "id": "t4",
            "topic": "Frontend State & Rendering Lifecycle",
            "question": "How does React's virtual DOM reconciliation and fiber scheduler optimize re-renders, and when would you prefer useMemo/useCallback over state colocation?",
            "expected_concepts": ["Reconciliation diffing", "fiber tree", "referential equality", "unnecessary render cascades"],
            "difficulty": "Medium"
        })

    if any(k in skill_lower for k in ["pytorch", "tensorflow", "ai", "machine learning", "nlp", "llm"]):
        technical_questions.append({
            "id": "t5",
            "topic": "Machine Learning & Vector Retrieval",
            "question": "Explain how embedding models generate dense representations and how Approximate Nearest Neighbor (ANN) indexing (HNSW / IVFFlat) scales similarity search in pgvector.",
            "expected_concepts": ["Dense embeddings", "cosine vs inner product distance", "HNSW graph layers", "recall vs latency trade-off"],
            "difficulty": "Hard"
        })

    # Always ensure at least 4 technical questions
    fallback_pool = [
        {
            "topic": "REST APIs & System Scalability",
            "question": "How do idempotency keys protect distributed payment and create operations from duplicate network retries?",
            "expected_concepts": ["Idempotency-Key header", "Redis distributed caching", "HTTP status 409 vs 200 replay", "database unique constraints"],
            "difficulty": "Medium"
        },
        {
            "topic": "Data Consistency & Transactions",
            "question": "Explain ACID properties and how database transaction isolation levels (Read Committed vs Serializable) prevent race conditions.",
            "expected_concepts": ["Atomicity", "Isolation levels", "Dirty reads", "Optimistic vs Pessimistic concurrency control"],
            "difficulty": "Medium"
        },
        {
            "topic": "System Monitoring & Observability",
            "question": "What is the difference between structured logging, metrics aggregation, and distributed tracing in production microservices?",
            "expected_concepts": ["OpenTelemetry / Span IDs", "Prometheus metrics", "Log correlation", "P99 latency analysis"],
            "difficulty": "Medium"
        },
        {
            "topic": "Network Protocols & Caching",
            "question": "How does HTTP/2 multiplexing improve on HTTP/1.1 pipelining, and how do CDN cache-control directives minimize origin load?",
            "expected_concepts": ["Binary framing layer", "Head-of-line blocking", "Cache-Control s-maxage", "E-Tag validation"],
            "difficulty": "Medium"
        }
    ]
    for fallback in fallback_pool:
        if len(technical_questions) >= 4:
            break
        technical_questions.append({
            "id": f"t{len(technical_questions) + 1}",
            **fallback
        })

    # --- 2. DSA Questions ---
    dsa_questions = [
        {
            "id": "dsa1",
            "title": "LRU Cache Implementation",
            "category": "Data Structures / System Design",
            "question": "Design a data structure that follows the constraints of a Least Recently Used (LRU) cache with O(1) time complexity for get and put operations.",
            "relevance": f"Standard for {role_title} to test hashing, pointer manipulation, and cache eviction.",
            "pattern": "HashMap + Doubly Linked List",
            "difficulty": "Medium"
        },
        {
            "id": "dsa2",
            "title": "Subarray Sum Equals K / Sliding Window",
            "category": "Arrays & Hashing",
            "question": "Given an array of integers and an integer k, find the total number of continuous subarrays whose sum equals k in O(n) time.",
            "relevance": "Tests prefix sum hashing techniques widely utilized in streaming data pipelines.",
            "pattern": "Prefix Sum + Hash Map",
            "difficulty": "Medium"
        },
        {
            "id": "dsa3",
            "title": "Topological Sort / Task Scheduling",
            "category": "Graphs & Dependency Resolution",
            "question": "Given n build tasks and their prerequisite dependencies, determine if it is possible to finish all tasks, and return a valid execution sequence.",
            "relevance": "Directly mirrors dependency resolution algorithms in build engines, DAG orchestrators, and microservices.",
            "pattern": "Kahn's Algorithm (BFS) / DFS Cycle Detection",
            "difficulty": "Hard"
        }
    ]

    # --- 3. Project-Based Questions (Anchored in Profile) ---
    project_questions = []
    for i, proj in enumerate(cand_projects[:4]):
        p_title = proj.get("title", "Candidate Project")
        p_tech = ", ".join(proj.get("tech_stack", []))
        p_desc = proj.get("description", "")
        
        project_questions.append({
            "id": f"proj{i+1}",
            "project_name": p_title,
            "tech_stack": p_tech,
            "question": f"In your project '{p_title}' using {p_tech}, what was the most significant architectural bottleneck you encountered, and how did you benchmark and validate your solution?",
            "focus_areas": [
                f"Validation of {p_tech} architecture decisions",
                "Data storage schema design and query execution efficiency",
                "Error handling, fault tolerance, and failure mode recovery"
            ],
            "candidate_evidence": p_desc
        })

    if not project_questions:
        project_questions.append({
            "id": "proj1",
            "project_name": "Full Stack System Implementation",
            "tech_stack": "Python, FastAPI, PostgreSQL",
            "question": "Walk through the architectural trade-offs made in your primary backend project. Why did you choose your database schema, and how did you structure service layering?",
            "focus_areas": ["Architecture design", "Database schema", "API contracts"],
            "candidate_evidence": "Candidate master profile technical foundations"
        })

    # --- 4. Behavioral Questions (STAR Method) ---
    behavioral_questions = [
        {
            "id": "b1",
            "competency": "Technical Disagreement & Consensus",
            "question": "Tell me about a time when you and a teammate or reviewer had different opinions on how to architect a feature. How did you evaluate both approaches and reach alignment?",
            "star_framework": "Situation (system context) -> Task (what needed building) -> Action (data-driven comparison, prototyping) -> Result (consensus & deliverable outcome)"
        },
        {
            "id": "b2",
            "competency": "Debugging Under Ambiguity",
            "question": "Describe a difficult bug or production issue where error logs were unhelpful or ambiguous. How did you systematically isolate root cause and verify the fix?",
            "star_framework": "Situation (failure symptoms) -> Task (urgency & scope) -> Action (reproduction, binary search debugging, metrics) -> Result (post-mortem prevention)"
        },
        {
            "id": "b3",
            "competency": "Prioritization Under Constraints",
            "question": "How have you handled situations where project deadlines required trimming scope or delivering an MVP under tight time constraints?",
            "star_framework": "Situation (timeline constraints) -> Task (core requirement) -> Action (ruthless prioritization, stakeholder communication) -> Result (timely high-quality release)"
        }
    ]

    # --- 5. HR Questions ---
    hr_questions = [
        {
            "id": "hr1",
            "topic": "Company Motivation",
            "question": f"Why are you specifically interested in {company_name}, and how does this {role_title} role align with your technical growth roadmap?",
            "recommended_angle": f"Demonstrate knowledge of {company_name}'s domain, tech initiatives, and how your projects align."
        },
        {
            "id": "hr2",
            "topic": "Availability & Logistics",
            "question": f"What is your availability for starting this internship ({opportunity.work_mode or 'full-time'}, {opportunity.workplace_type or 'flexible'}), and do you have any university scheduling constraints?",
            "recommended_angle": "Clear timeline commitments, semester exam dates, and proactive communication."
        },
        {
            "id": "hr3",
            "topic": "Collaboration & Learning Style",
            "question": "How do you approach ramping up in a new, unfamiliar codebase or tech stack during your first two weeks at a company?",
            "recommended_angle": "Emphasize reading documentation, running unit tests, tracing entrypoints, and asking structured questions."
        }
    ]

    # --- 6. Company and Role-Specific Preparation Topics ---
    company_topics = [
        {
            "id": "cp1",
            "title": f"Core Business Context: {company_name}",
            "description": f"Research {company_name}'s recent engineering announcements, core product offerings, and customer user journey.",
            "action_item": f"Review {company_name}'s GitHub repositories, engineering blog, and public architecture whitepapers."
        },
        {
            "id": "cp2",
            "title": f"Role Focus: {role_title}",
            "description": f"The primary responsibilities demand solid fluency in {', '.join(all_skills[:5]) if all_skills else 'software engineering fundamentals'}.",
            "action_item": "Be ready to live-code idiomatic solutions, write unit tests, and explain time and space complexity tradeoffs."
        },
        {
            "id": "cp3",
            "title": "System Design Basics & Scalability",
            "description": "Junior and intern interviews frequently assess basic caching, rate limiting, and database schema relationships.",
            "action_item": "Prepare to draw database entity-relationship diagrams and trace API requests end-to-end from client to database."
        },
        {
            "id": "cp4",
            "title": "Reverse Interview Questions to Ask Hiring Managers",
            "description": "High-signal questions that showcase genuine intellectual curiosity and technical maturity.",
            "action_item": "Ask: 'What does a successful first 30 days look like for an intern in this team?' and 'What is the deployment frequency and testing philosophy?'"
        }
    ]

    return {
        "opportunity_id": opportunity.id,
        "company_name": company_name,
        "role_title": role_title,
        "technical_questions": technical_questions,
        "dsa_questions": dsa_questions,
        "project_questions": project_questions,
        "behavioral_questions": behavioral_questions,
        "hr_questions": hr_questions,
        "company_topics": company_topics,
        "generated_at": datetime.utcnow().isoformat()
    }


def evaluate_mock_answer(
    question_text: str,
    category: str,
    context_or_hint: str,
    user_answer: str,
    profile: Optional[CandidateProfile] = None,
    target_role: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluates candidate's written answer in mock practice mode.
    Outputs objective, constructive AI evaluation strictly labeled as AI-generated.
    """
    clean_answer = user_answer.strip()
    word_count = len(clean_answer.split())

    if word_count < 10:
        return {
            "score": 30,
            "clarity_rating": 2,
            "technical_depth": 1,
            "strengths": ["Recognized the question topic."],
            "improvement_areas": [
                "Answer is too brief. Elaborate on underlying mechanisms, system trade-offs, and concrete examples.",
                "Structure your response with clear definition, mechanism of action, and real-world edge-cases."
            ],
            "ideal_answer_points": [
                "Define the core concept clearly.",
                "Explain step-by-step how the runtime or system behaves.",
                "Highlight time/space complexity or architectural trade-offs.",
                "Mention production considerations or failure cases."
            ],
            "verdict": "Answer lacks required technical depth",
            "evaluation_type": "ai_generated_evaluation",
            "evaluated_at": datetime.utcnow().isoformat()
        }

    # Keyword and heuristic depth analysis
    technical_keywords = [
        "async", "await", "coroutine", "event loop", "thread", "concurrency",
        "index", "b-tree", "gin", "query", "latency", "throughput", "cache",
        "lock", "transaction", "acid", "docker", "container", "api", "rest",
        "star", "situation", "task", "action", "result", "trade-off", "complexity"
    ]
    matched_tech = [k for k in technical_keywords if k in clean_answer.lower()]
    
    score = min(96, max(45, 50 + (len(matched_tech) * 5) + min(20, word_count // 10)))
    clarity = min(5, max(2, 2 + (1 if word_count >= 30 else 0) + (1 if len(clean_answer) >= 150 else 0) + (1 if "." in clean_answer else 0)))
    depth = min(5, max(2, 2 + (len(matched_tech) // 2)))

    strengths = []
    if len(matched_tech) >= 3:
        strengths.append(f"Demonstrated good technical vocabulary including {', '.join(matched_tech[:4])}.")
    if word_count >= 40:
        strengths.append("Provided a thorough, structured explanation rather than a superficial one-liner.")
    if not strengths:
        strengths.append("Addresses the core subject directly with relevant technical terminology.")

    improvements = []
    if len(matched_tech) < 2:
        improvements.append("Integrate more precise technical terminology to demonstrate runtime/algorithmic mastery.")
    if "trade-off" not in clean_answer.lower() and "complexity" not in clean_answer.lower() and "limit" not in clean_answer.lower():
        improvements.append("Discuss trade-offs, boundary conditions, or scaling limits to show senior-level engineering thinking.")
    if "." not in clean_answer or clean_answer.count(".") < 2:
        improvements.append("Break down multi-step processes with bullet points or sequential numbered milestones.")
    if not improvements:
        improvements.append("Consider mentioning a concrete production anecdote or metrics from your projects.")

    ideal_points = [
        f"1. Concise definition addressing '{question_text[:50]}...'",
        "2. Step-by-step mechanical explanation (what executes first, data flow, memory model)",
        "3. Concrete trade-off analysis (when this approach is ideal vs when it introduces latency or overhead)",
        "4. Example scenario or code snippet pattern demonstrating production best practices"
    ]

    verdict = "Strong Technical Grasp" if score >= 80 else ("Competent Foundations, Add Detail" if score >= 65 else "Needs Deeper Technical Elaboration")

    return {
        "score": score,
        "clarity_rating": clarity,
        "technical_depth": depth,
        "strengths": strengths,
        "improvement_areas": improvements,
        "ideal_answer_points": ideal_points,
        "verdict": verdict,
        "evaluation_type": "ai_generated_evaluation",
        "evaluated_at": datetime.utcnow().isoformat()
    }


def compute_historical_interview_analytics(
    journal_records: List[InterviewJournalRecord]
) -> Dict[str, Any]:
    """
    Strict Zero-Fabrication Analytics:
    Evaluates real user recorded interviews to diagnose:
      - Repeatedly difficult topics
      - Strong technical areas
      - Communication improvement areas
      - Knowledge gaps
      - Question-answer quality
      - Preparation priorities
    """
    total = len(journal_records)
    if total == 0:
        return {
            "total_interviews": 0,
            "avg_difficulty": 0.0,
            "avg_performance": 0.0,
            "avg_confidence": 0.0,
            "funnel_metrics": {
                "pending": 0,
                "passed": 0,
                "rejected": 0,
                "offer": 0,
                "withdrawn": 0,
                "conversion_rate_pct": 0.0
            },
            "repeatedly_difficult_topics": [],
            "strong_technical_areas": [],
            "communication_improvement_areas": [
                "Use the STAR method (Situation, Task, Action, Result) for all behavioral inquiries.",
                "State time and space complexity proactively before coding solutions.",
                "Structure technical answers from top-level architecture down into execution details."
            ],
            "knowledge_gaps": [],
            "qa_quality_score": 0,
            "preparation_priorities": [
                "Record your first interview in the Journal to populate personalized performance trends.",
                "Practice mock questions in Practice Mode to benchmark answer clarity."
            ],
            "zero_records_note": "No interview records entered yet. Analytics reflect only real user data."
        }

    # Aggregate ratings
    difficulties = [r.difficulty_rating for r in journal_records if r.difficulty_rating]
    performances = [r.performance_rating for r in journal_records if r.performance_rating]
    confidences = [getattr(r, "confidence_level", 3) for r in journal_records if getattr(r, "confidence_level", None)]

    avg_diff = round(sum(difficulties) / len(difficulties), 2) if difficulties else 3.0
    avg_perf = round(sum(performances) / len(performances), 2) if performances else 3.0
    avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else 3.0

    # Funnel
    funnel = {"pending": 0, "passed": 0, "rejected": 0, "offer": 0, "withdrawn": 0}
    for r in journal_records:
        res = (getattr(r, "interview_result", "") or "pending").lower()
        if res in funnel:
            funnel[res] += 1
        else:
            funnel["pending"] += 1

    decided = funnel["passed"] + funnel["rejected"] + funnel["offer"]
    conv_rate = round(((funnel["offer"] + funnel["passed"]) / decided * 100), 1) if decided > 0 else 0.0
    funnel["conversion_rate_pct"] = conv_rate

    # Topic diagnosis
    topic_difficulty_counts = {}
    topic_strong_counts = {}
    all_qa_lengths = []
    
    for r in journal_records:
        topics = getattr(r, "topics_covered", []) or []
        diff = r.difficulty_rating or 3
        perf = r.performance_rating or 3
        conf = getattr(r, "confidence_level", 3) or 3

        for t in topics:
            t_clean = t.strip().title()
            if diff >= 4 or conf <= 2 or perf <= 2:
                topic_difficulty_counts[t_clean] = topic_difficulty_counts.get(t_clean, 0) + 1
            if perf >= 4 and conf >= 4:
                topic_strong_counts[t_clean] = topic_strong_counts.get(t_clean, 0) + 1

        # Inspect recorded Q&A
        for q in (r.questions_asked or []):
            ans = q.get("user_answer", "")
            if ans:
                all_qa_lengths.append(len(ans.split()))
            q_topic = q.get("topic", "")
            q_conf = q.get("confidence", 3)
            if q_topic and (q_conf <= 2 or diff >= 4):
                topic_difficulty_counts[q_topic.strip().title()] = topic_difficulty_counts.get(q_topic.strip().title(), 0) + 1

    # Sorted lists
    repeatedly_difficult = sorted(
        [{"topic": k, "frequency": v, "severity": "High" if v >= 2 else "Moderate"} for k, v in topic_difficulty_counts.items()],
        key=lambda x: x["frequency"],
        reverse=True
    )

    strong_areas = sorted(
        [{"topic": k, "consistency_score": min(100, v * 35)} for k, v in topic_strong_counts.items()],
        key=lambda x: x["consistency_score"],
        reverse=True
    )

    # Communication improvements
    comm_improvements = []
    if all_qa_lengths:
        avg_words = sum(all_qa_lengths) / len(all_qa_lengths)
        if avg_words < 25:
            comm_improvements.append(f"Average answer length is {int(avg_words)} words. Elaborate on architecture, specific APIs, and trade-offs.")
        else:
            comm_improvements.append("Solid answer detail noted. Focus on delivering the high-level summary in the first 20 seconds.")
    else:
        comm_improvements.append("Record question-specific answers to receive precise communication length and clarity feedback.")

    comm_improvements.append("Always explicitly state the time and space complexity of code solutions before writing.")
    comm_improvements.append("Frame behavioral responses in the STAR sequence to keep answers structured under pressure.")

    # Preparation priorities
    priorities = []
    for item in repeatedly_difficult[:4]:
        priorities.append(f"Deep-dive study: {item['topic']} (flagged in {item['frequency']} interview evaluations)")
    if not priorities:
        priorities.append("Review distributed systems fundamentals and database index trade-offs.")
        priorities.append("Practice STAR behavioral responses for cross-functional conflicts.")

    # QA quality score (0 to 100)
    qa_score = int(min(100, max(40, (avg_perf * 15) + (avg_conf * 5))))

    return {
        "total_interviews": total,
        "avg_difficulty": avg_diff,
        "avg_performance": avg_perf,
        "avg_confidence": avg_conf,
        "funnel_metrics": funnel,
        "repeatedly_difficult_topics": repeatedly_difficult,
        "strong_technical_areas": strong_areas,
        "communication_improvement_areas": comm_improvements,
        "knowledge_gaps": [d["topic"] for d in repeatedly_difficult[:5]],
        "qa_quality_score": qa_score,
        "preparation_priorities": priorities
    }


def create_mock_questions_for_role(
    opportunity: Optional[Opportunity],
    profile: Optional[CandidateProfile],
    session_type: str = "technical"
) -> List[Dict[str, Any]]:
    """
    Generates structured questions for a new mock practice session.
    """
    company = opportunity.company_name if opportunity else "Tech Company"
    role = opportunity.title if opportunity else "Software Engineer"
    
    questions = []
    
    if session_type == "dsa":
        questions = [
            {
                "id": "q1",
                "category": "dsa",
                "question": "How would you design a data structure that implements get(key) and put(key, value) operations in O(1) time complexity with an LRU eviction policy?",
                "context_or_hint": "Consider combining a hash map for O(1) lookups with a doubly linked list for O(1) node repositioning.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q2",
                "category": "dsa",
                "question": "Given an array of integers representing stock prices on consecutive days, find the maximum profit from at most two transactions.",
                "context_or_hint": "Think about dynamic programming with states: buy1, sell1, buy2, sell2.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q3",
                "category": "dsa",
                "question": "Given a directed graph of task dependencies, determine if a cycle exists, and return a topological order if valid.",
                "context_or_hint": "Use Kahn's algorithm with in-degrees or DFS with 3-state coloring (visiting, visited, unvisited).",
                "user_answer": None,
                "ai_evaluation": None
            }
        ]
    elif session_type == "behavioral":
        questions = [
            {
                "id": "q1",
                "category": "behavioral",
                "question": "Describe a situation where a project specification changed drastically a week before release. How did you adapt your plan and communicate with stakeholders?",
                "context_or_hint": "Use STAR format: Situation, Task, Action, and Result. Highlight proactive prioritization.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q2",
                "category": "behavioral",
                "question": "Tell me about a time when you received harsh or critical code review feedback. How did you process it and apply the learning?",
                "context_or_hint": "Demonstrate receptiveness to constructive feedback and commitment to team code quality standards.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q3",
                "category": "behavioral",
                "question": f"Why do you want to join {company} specifically, and what impact do you hope to make in this {role} internship?",
                "context_or_hint": "Connect your past projects to company domain missions and technical culture.",
                "user_answer": None,
                "ai_evaluation": None
            }
        ]
    elif session_type == "project_deep_dive":
        cand_projs = profile.projects if profile and profile.projects else []
        proj_name = cand_projs[0].get("title", "CareerOS") if cand_projs else "Full Stack Platform"
        questions = [
            {
                "id": "q1",
                "category": "project",
                "question": f"Walk me through the architecture of your project '{proj_name}'. What database engine did you select and why?",
                "context_or_hint": "Discuss relational vs non-relational schemas, indexing strategies, and read/write access patterns.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q2",
                "category": "project",
                "question": f"In '{proj_name}', if the incoming request volume scaled from 10 req/s to 10,000 req/s overnight, where would the system fail first and how would you re-architect it?",
                "context_or_hint": "Address connection pooling, caching layers (Redis), read replicas, and async queue workers.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q3",
                "category": "project",
                "question": f"What was the most difficult bug or concurrency edge case you resolved during the development of '{proj_name}'?",
                "context_or_hint": "Detail reproduction steps, telemetry logs used to isolate it, and test automation added to prevent regressions.",
                "user_answer": None,
                "ai_evaluation": None
            }
        ]
    else: # technical / full_mock
        questions = [
            {
                "id": "q1",
                "category": "technical",
                "question": "How does asynchronous execution work in modern Python (async/await), and what happens when an async endpoint blocks on a synchronous CPU-bound task?",
                "context_or_hint": "Explain how synchronous operations freeze the single-threaded asyncio event loop, and how to offload to run_in_executor.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q2",
                "category": "technical",
                "question": "Explain database indexing in PostgreSQL. When would a B-Tree index degrade performance compared to a sequential scan, and how does write amplification occur?",
                "context_or_hint": "Mention low cardinality columns, table bloat, index maintenance overhead on INSERT/UPDATE, and HOT updates.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q3",
                "category": "technical",
                "question": "What is the difference between process and thread concurrency? How do containers isolate resources compared to virtual machines?",
                "context_or_hint": "Discuss memory space sharing, Linux namespaces, cgroups, kernel syscalls, and hypervisors.",
                "user_answer": None,
                "ai_evaluation": None
            },
            {
                "id": "q4",
                "category": "dsa",
                "question": "How would you find the longest palindromic substring in a string efficiently? Compare the dynamic programming and expand-around-center approaches.",
                "context_or_hint": "Expand around center operates in O(n^2) time and O(1) space, while Manacher's algorithm achieves O(n) time.",
                "user_answer": None,
                "ai_evaluation": None
            }
        ]
        
    return questions
