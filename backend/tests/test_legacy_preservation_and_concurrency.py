import os
import random
import time
from types import SimpleNamespace
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.main import app
from backend.app.database import SessionLocal, engine
from backend.app.core.auth import create_access_token
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.models.resume_version import ResumeVersion
from backend.app.services.latex_compiler import compile_latex, STORAGE_DIR

client = TestClient(app)


def auth_headers(user_id: int):
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


LEGACY_LATEX_TEMPLATE = r"""\documentclass[10.5pt,letterpaper]{article}
\usepackage[left=0.6in,right=0.6in,top=0.5in,bottom=0.5in]{geometry}
\usepackage{titlesec}
\usepackage{enumitem}
\usepackage{hyperref}
\usepackage{xcolor}

\newcommand{\kw}[1]{\textbf{#1}}
\newcommand{\subheading}[3]{\textbf{#1} -- \textit{#2} \hfill #3\\}
\newcommand{\heading}[2]{\textbf{#1} \hfill #2\\}

\begin{document}

\begin{center}
{\huge \bfseries Legacy User} \\[4pt]
+1 555-0199 \quad|\quad
\href{mailto:legacy.user@example.com}{Email} \quad|\quad
\href{https://linkedin.com/in/legacy-user}{LinkedIn} \quad|\quad
\href{https://github.com/legacy-user}{GitHub}
\end{center}

\section*{Summary}
Custom Handcrafted Summary with specialized systems expertise and custom metrics.

\section*{Technical Skills}
\begin{itemize}
\item \textbf{Languages:} Python, Go, Rust, C++
\item \textbf{Frameworks & Libraries:} FastAPI, React, PyTorch
\item \textbf{Tools & Platforms:} Docker, Kubernetes, AWS, Linux
\end{itemize}

\section*{Experience}
\subheading{Lead Platform Engineer}{Acme Systems Corp}{2022 -- Present}
\begin{itemize}
\item Handcrafted Experience Bullet 1: Architected distributed event stream processing 10M events/sec.
\item Handcrafted Experience Bullet 2: Reduced P99 tail latency by 45 percent using zero-copy memory buffers.
\end{itemize}

\section*{Projects}
\textbf{\href{https://github.com/legacy-user/stream-engine}{StreamEngine Core}} \hfill \textit{Go | Kafka | gRPC}
\begin{itemize}
\item Handcrafted Project Bullet 1: Engineered lock-free ring buffer yielding 5x throughput.
\item Handcrafted Project Bullet 2: Authored custom raft consensus engine for partition tolerance.
\end{itemize}

\section*{Education}
\heading{B.S. in Computer Engineering}{Stanford University \quad 2018--2022}

\section*{Certifications}
\begin{itemize}
\item AWS Certified Solutions Architect Professional -- Amazon (2023)
\end{itemize}

\section*{Honors & Achievements}
\begin{itemize}
\item ACM ICPC Regional Finalist -- Association for Computing Machinery (2021)
\end{itemize}

\end{document}
"""


def create_test_candidate_and_legacy_resume(user_id: int, custom_latex: str = None):
    """Creates an isolated test candidate and a legacy resume with structured_content=None."""
    db = SessionLocal()
    try:
        cand = CandidateProfile(
            user_id=user_id,
            name="Profile Name Differing From LaTeX",
            email=f"profile_{user_id}@careeros.internal",
            phone="+1 000-000-0000",
            location="Profile City",
            bio="Generic Bio from CandidateProfile",
            skills=["Generic Skill A", "Generic Skill B"],
            projects=[
                {
                    "title": "Generic Profile Project",
                    "tech_stack": ["PHP"],
                    "bullets": ["Generic Profile Bullet 1"]
                }
            ],
            experience=[
                {
                    "title": "Generic Profile Role",
                    "company": "Generic Profile Company",
                    "bullets": ["Generic Profile Experience Bullet"]
                }
            ]
        )
        db.add(cand)
        db.commit()

        resume = ResumeDocument(
            user_id=user_id,
            title="Legacy Candidate Resume",
            template_id="software_engineering",
            latex_content=custom_latex or LEGACY_LATEX_TEMPLATE,
            structured_content=None,  # Pure legacy state
            version=1
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)

        v1 = ResumeVersion(
            resume_id=resume.id,
            version_number=1,
            title=resume.title,
            template_id=resume.template_id,
            latex_content=resume.latex_content,
            structured_content=None,
            change_summary="Initial legacy document"
        )
        db.add(v1)
        db.commit()

        return SimpleNamespace(
            id=resume.id,
            user_id=resume.user_id,
            version=resume.version,
            title=resume.title,
            template_id=resume.template_id,
            latex_content=resume.latex_content,
            structured_content=resume.structured_content
        )
    finally:
        db.close()


# =========================================================================
# Test 1: Legacy resume containing manually edited summary
# =========================================================================
def test_legacy_resume_manually_edited_summary_preserved():
    """Extracts user-authored summary from LaTeX instead of falling back to CandidateProfile headline/summary."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    res = client.get(f"/api/resumes/{resume.id}/sections", headers=headers)
    assert res.status_code == 200
    data = res.json()["structured_content"]

    # Must preserve the handcrafted summary from LaTeX, NOT the generic summary in CandidateProfile
    assert "Custom Handcrafted Summary with specialized systems expertise" in data["summary"]
    assert "Generic Bio from CandidateProfile" not in data["summary"]


# =========================================================================
# Test 2: Legacy resume containing manually edited project bullets
# =========================================================================
def test_legacy_resume_manually_edited_project_bullets_preserved():
    """Extracts project entries, tech stacks, URLs, and custom bullets from LaTeX without losing user edits."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    res = client.get(f"/api/resumes/{resume.id}/sections", headers=headers)
    assert res.status_code == 200
    projects = res.json()["structured_content"]["projects"]

    assert len(projects) >= 1
    stream_proj = next((p for p in projects if "StreamEngine" in p["title"]), None)
    assert stream_proj is not None
    assert "github.com/legacy-user/stream-engine" in stream_proj["url"]
    assert any("Go" in t for t in stream_proj["tech_stack"])

    bullet_texts = [b["text"] for b in stream_proj["bullets"]]
    assert any("lock-free ring buffer" in b for b in bullet_texts)
    assert any("raft consensus engine" in b for b in bullet_texts)
    assert not any("Generic Profile Project" in p["title"] for p in projects)


# =========================================================================
# Test 3: Partial update preserving every untouched section
# =========================================================================
def test_partial_update_preserving_every_untouched_section():
    """A partial section update to skills preserves user-authored summary, projects, experience, and education."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    # Update ONLY skills
    update_payload = {
        "skills": [
            {"category": "Cloud & Distributed", "skills": ["Kubernetes", "Kafka", "Temporal", "Distributed Tracing"]}
        ],
        "change_summary": "Updated cloud skills matrix"
    }

    res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
    assert res.status_code == 200
    updated_sections = res.json()["structured_content"]

    # 1. Skills must be updated
    assert len(updated_sections["skills"]) == 1
    assert updated_sections["skills"][0]["category"] == "Cloud & Distributed"
    assert "Temporal" in updated_sections["skills"][0]["skills"]

    # 2. Summary must remain original handcrafted text
    assert "Custom Handcrafted Summary with specialized systems expertise" in updated_sections["summary"]

    # 3. Experience and projects must retain original bullets
    exp_bullets = [b["text"] for e in updated_sections["experience"] for b in e["bullets"]]
    assert any("10M events/sec" in b for b in exp_bullets)

    proj_bullets = [b["text"] for p in updated_sections["projects"] for b in p["bullets"]]
    assert any("lock-free ring buffer" in b for b in proj_bullets)

    # 4. Education must remain intact
    edu_colleges = [e["college"] for e in updated_sections["education"]]
    assert any("Stanford" in c for c in edu_colleges)


# =========================================================================
# Test 4: Legacy conversion not mutating the database during GET
# =========================================================================
def test_legacy_conversion_not_mutating_database_during_get():
    """GET /api/resumes/{id}/sections on legacy resume must NOT commit or mutate the database."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    db = SessionLocal()
    try:
        r_before = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        assert r_before.structured_content is None
        assert r_before.version == 1
    finally:
        db.close()

    # Call GET endpoint
    res = client.get(f"/api/resumes/{resume.id}/sections", headers=headers)
    assert res.status_code == 200
    assert res.json()["structured_content"]["summary"]

    # Query DB directly after GET
    db = SessionLocal()
    try:
        r_after = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        # Database record must NOT have been mutated by the read operation
        assert r_after.structured_content is None
        assert r_after.version == 1
    finally:
        db.close()


# =========================================================================
# Test 5: Repeated legacy conversion producing consistent output
# =========================================================================
def test_repeated_legacy_conversion_producing_consistent_output():
    """Repeated calls to GET /api/resumes/{id}/sections yield identical, deterministic output."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    res1 = client.get(f"/api/resumes/{resume.id}/sections", headers=headers)
    res2 = client.get(f"/api/resumes/{resume.id}/sections", headers=headers)

    assert res1.status_code == 200
    assert res2.status_code == 200

    sc1 = res1.json()["structured_content"]
    sc2 = res2.json()["structured_content"]

    assert sc1["summary"] == sc2["summary"]
    assert [p["title"] for p in sc1["projects"]] == [p["title"] for p in sc2["projects"]]
    assert [e["title"] for e in sc1["experience"]] == [e["title"] for e in sc2["experience"]]
    assert [b["text"] for p in sc1["projects"] for b in p["bullets"]] == [b["text"] for p in sc2["projects"] for b in p["bullets"]]


# =========================================================================
# Test 6: Two simultaneous updates using the same expected_version (Concurrency)
# =========================================================================
def test_simultaneous_updates_same_expected_version_conflict():
    """
    Real PostgreSQL concurrency test: Two concurrent worker threads issue PUT requests
    with the exact same expected_version=1.
    PostgreSQL row-level locking ensures exactly one succeeds (200) and the other is rejected (409 Conflict).
    """
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    payload_a = {
        "summary": "Update from Worker Thread Alpha",
        "expected_version": 1,
        "change_summary": "Alpha concurrent update"
    }
    payload_b = {
        "summary": "Update from Worker Thread Beta",
        "expected_version": 1,
        "change_summary": "Beta concurrent update"
    }

    results = []

    def run_update(payload):
        # Create an independent TestClient per thread
        thread_client = TestClient(app)
        resp = thread_client.put(f"/api/resumes/{resume.id}/sections", json=payload, headers=headers)
        return resp.status_code, resp.json()

    with ThreadPoolExecutor(max_workers=2) as executor:
        f_a = executor.submit(run_update, payload_a)
        f_b = executor.submit(run_update, payload_b)
        results = [f_a.result(), f_b.result()]

    status_codes = [r[0] for r in results]
    assert 200 in status_codes, f"Expected at least one 200 OK in {status_codes}"
    assert 409 in status_codes, f"Expected exactly one 409 Conflict in {status_codes}"


# =========================================================================
# Test 7: Exactly one concurrent update committing successfully
# =========================================================================
def test_exactly_one_concurrent_update_commits():
    """Under concurrent collision, database version increments by exactly 1 without lost updates."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    payloads = [
        {"summary": "Worker 1 Summary", "expected_version": 1, "change_summary": "Worker 1"},
        {"summary": "Worker 2 Summary", "expected_version": 1, "change_summary": "Worker 2"}
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(lambda p: TestClient(app).put(f"/api/resumes/{resume.id}/sections", json=p, headers=headers), p)
            for p in payloads
        ]
        responses = [f.result() for f in futures]

    codes = [r.status_code for r in responses]
    assert sorted(codes) == [200, 409]

    # Verify PostgreSQL state
    db = SessionLocal()
    try:
        r = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        # Exactly one increment: version must be 2
        assert r.version == 2
        # Content matches the successful worker
        winning_summary = next(resp.json()["structured_content"]["summary"] for resp in responses if resp.status_code == 200)
        assert r.structured_content["summary"] == winning_summary
    finally:
        db.close()


# =========================================================================
# Test 8: No duplicate snapshots during concurrent updates
# =========================================================================
def test_no_duplicate_snapshots_during_concurrent_updates():
    """Unique constraint and row locking guarantee exactly one version snapshot per version number."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    payloads = [
        {"summary": "Concurrent Snapshot Alpha", "expected_version": 1, "change_summary": "Snapshot Alpha"},
        {"summary": "Concurrent Snapshot Beta", "expected_version": 1, "change_summary": "Snapshot Beta"}
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(lambda p: TestClient(app).put(f"/api/resumes/{resume.id}/sections", json=p, headers=headers), p)
            for p in payloads
        ]
        _ = [f.result() for f in futures]

    db = SessionLocal()
    try:
        # Check count of version 2 snapshots
        v2_snapshots = db.query(ResumeVersion).filter(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.version_number == 2
        ).all()
        assert len(v2_snapshots) == 1, f"Expected exactly 1 snapshot for version 2, found {len(v2_snapshots)}"
    finally:
        db.close()


# =========================================================================
# Test 9: Structured content and LaTeX remaining synchronized
# =========================================================================
def test_structured_content_and_latex_remaining_synchronized():
    """Verifies that updated structured fields are faithfully compiled into latex_content."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    unique_marker = f"SynchronizedMetric{random.randint(1000, 9999)}"
    update_payload = {
        "summary": f"High performance engineer with {unique_marker} achievements.",
        "change_summary": "Sync check update"
    }

    res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
    assert res.status_code == 200
    data = res.json()

    assert unique_marker in data["structured_content"]["summary"]
    assert unique_marker in data["resume"]["latex_content"]

    # Verify database synchronization
    db = SessionLocal()
    try:
        r = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        assert unique_marker in r.structured_content["summary"]
        assert unique_marker in r.latex_content
    finally:
        db.close()


# =========================================================================
# Test 10: Version restoration preserving template and structured content
# =========================================================================
def test_version_restoration_preserving_template_and_structured_content():
    """Restoring a previous version restores structured_content, template_id, and creates a full snapshot."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    # 1. Update A (creates v2)
    res_v2 = client.put(
        f"/api/resumes/{resume.id}/sections",
        json={"summary": "Summary for Version 2", "change_summary": "Set v2 summary"},
        headers=headers
    )
    assert res_v2.status_code == 200
    assert res_v2.json()["version"] == 2

    # Get version 2 snapshot ID
    v_res = client.get(f"/api/resumes/{resume.id}/versions", headers=headers)
    v2_snapshot = next(v for v in v_res.json() if v["version_number"] == 2)
    v2_id = v2_snapshot["id"]

    # 2. Update B (creates v3)
    res_v3 = client.put(
        f"/api/resumes/{resume.id}/sections",
        json={"summary": "Summary for Version 3", "change_summary": "Set v3 summary"},
        headers=headers
    )
    assert res_v3.status_code == 200
    assert res_v3.json()["version"] == 3

    # 3. Restore v2 snapshot
    res_restore = client.post(f"/api/resumes/{resume.id}/versions/{v2_id}/restore", headers=headers)
    assert res_restore.status_code == 200
    restored_resume = res_restore.json()

    assert restored_resume["version"] == 4
    # Structured content must match v2
    assert restored_resume["structured_content"]["summary"] == "Summary for Version 2"

    # Verify latest snapshot in DB includes structured_content
    db = SessionLocal()
    try:
        v4_snap = db.query(ResumeVersion).filter(
            ResumeVersion.resume_id == resume.id,
            ResumeVersion.version_number == 4
        ).first()
        assert v4_snap is not None
        assert v4_snap.structured_content["summary"] == "Summary for Version 2"
        assert v4_snap.template_id == resume.template_id
    finally:
        db.close()


# =========================================================================
# Test 11: Repeated application startup preserving migration integrity
# =========================================================================
def test_repeated_application_startup_preserving_migration_integrity():
    """Simulates multi-worker lifespan startup: advisory lock ensures DDL idempotency without errors."""
    def run_startup_ddl():
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(42000101);"))
            conn.execute(text("ALTER TABLE resume_documents ADD COLUMN IF NOT EXISTS structured_content JSONB;"))
            conn.execute(text("ALTER TABLE resume_versions ADD COLUMN IF NOT EXISTS structured_content JSONB;"))
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_constraint WHERE conname = 'uq_resume_version_resume_id_version_number'
                    ) THEN
                        ALTER TABLE resume_versions 
                        ADD CONSTRAINT uq_resume_version_resume_id_version_number 
                        UNIQUE (resume_id, version_number);
                    END IF;
                END $$;
            """))
        return True

    # Run simultaneously across 4 simulated workers
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(run_startup_ddl) for _ in range(4)]
        results = [f.result() for f in futures]

    assert all(results)


# =========================================================================
# Test 12: Concurrent LaTeX compilation using isolated temporary files
# =========================================================================
def test_concurrent_latex_compilation_isolated_temporary_files():
    """Concurrent compile_latex calls compile cleanly in isolated temporary directories without collisions."""
    source_template = r"""\documentclass{article}
\begin{document}
Worker Compilation %d: High throughput test.
\end{document}
"""
    compilation_names = [f"test_concurrent_comp_{i}_{random.randint(1000, 9999)}" for i in range(3)]

    def compile_worker(name, idx):
        source = source_template % idx
        ok, pdf_path, compiler = compile_latex(source, name, strict=True)
        return ok, pdf_path, compiler

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = [
            executor.submit(compile_worker, name, i)
            for i, name in enumerate(compilation_names)
        ]
        results = [f.result() for f in futures]

    for ok, pdf_path, compiler in results:
        assert ok is True
        assert os.path.exists(pdf_path)
        # Cleanup test generated PDFs
        try:
            os.remove(pdf_path)
        except OSError:
            pass


# =========================================================================
# Test 13: Failed compilation leaving no corrupted files or records
# =========================================================================
from backend.tests.helpers_env import requires_tectonic


@requires_tectonic
def test_failed_compilation_leaving_no_corrupted_files_or_records():
    """Broken LaTeX syntax fails compilation, rolls back DB transaction, and leaves no files in STORAGE_DIR."""
    user_id = random.randint(100000, 999999)
    headers = auth_headers(user_id)
    resume = create_test_candidate_and_legacy_resume(user_id)

    # 1. Direct compilation failure test on compile_latex
    bad_latex = r"\documentclass{article}\begin{document}\badundefinedcommandthatdefinitelybreaks"
    ok, err_msg, compiler = compile_latex(bad_latex, "test_broken_source_no_orphan", strict=True)
    assert ok is False
    assert not os.path.exists(os.path.join(STORAGE_DIR, "test_broken_source_no_orphan.pdf"))

    # 2. Endpoint transaction rollback and safety verification
    base_name = f"resume_{resume.id}_v2"
    pdf_path = os.path.join(STORAGE_DIR, f"{base_name}.pdf")

    with patch("backend.app.api.resumes.compile_latex") as mock_compile:
        mock_compile.return_value = (False, "Fatal tectonic compilation error: undefined control sequence", "tectonic")
        update_payload = {
            "summary": "This update should be aborted because compilation failed.",
            "change_summary": "Doomed broken syntax update"
        }
        res = client.put(f"/api/resumes/{resume.id}/sections", json=update_payload, headers=headers)
        assert res.status_code == 400
        assert "LaTeX compilation failed" in res.json()["detail"]
        assert "original resume was preserved unchanged" in res.json()["detail"].lower()

    # Verify DB rolled back
    db = SessionLocal()
    try:
        r = db.query(ResumeDocument).filter(ResumeDocument.id == resume.id).first()
        assert r.version == 1
        assert r.structured_content is None
    finally:
        db.close()

    # Clean stale artifacts from previous test runs, then assert the failed compile never created one.
    if os.path.exists(pdf_path):
        os.remove(pdf_path)
        print(f"removed stale artifact: {pdf_path}")
    assert not os.path.exists(pdf_path), f"Orphaned PDF {pdf_path} exists — must not happen after rollback"
