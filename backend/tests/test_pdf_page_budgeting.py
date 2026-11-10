import os
import io
import hashlib
import tempfile
import pytest
from concurrent.futures import ThreadPoolExecutor, as_completed
from fastapi.testclient import TestClient
import pypdf

from backend.tests.helpers_env import requires_tectonic

from backend.app.main import app
from backend.app.database import SessionLocal
from backend.app.core.auth import create_access_token
from backend.app.models.candidate import CandidateProfile
from backend.app.models.resume import ResumeDocument
from backend.app.services.latex_compiler import (
    compile_latex,
    compile_and_validate_resume,
    STORAGE_DIR
)
from backend.app.services.pdf_layout_validator import (
    analyze_pdf,
    estimate_content_density,
    determine_target_page_count,
    validate_pdf_layout
)

client = TestClient(app)


def auth_headers(user_id: int):
    token = create_access_token(user_id=user_id)
    return {"Authorization": f"Bearer {token}"}


SAMPLE_1_PAGE_LATEX = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=0.6in]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage[nobottomtitles*]{titlesec}
\usepackage{parskip}
\usepackage{microtype}

\renewcommand{\bottomtitlespace}{0.8in}
\raggedbottom

\titleformat{\section}{\large\bfseries\uppercase}{}{0em}{}	[\titlerule]
\titlespacing*{\section}{0pt}{5pt plus 1pt minus 1pt}{2.5pt plus 1pt minus 1pt}

\pagestyle{empty}

\begin{document}
\begin{center}
{\Huge \textbf{Candidate Single}} \\[2pt]
San Francisco, CA $\cdot$ +1 555-0199 $\cdot$ \href{mailto:candidate@example.com}{candidate@example.com} \\[2pt]
\href{https://github.com/candidate}{GitHub} $\cdot$ \href{https://linkedin.com/in/candidate}{LinkedIn}
\end{center}

\section*{Professional Summary}
Focused software engineer with expertise in distributed databases, asynchronous architectures, and cloud microservices.

\section*{Education}
\textbf{University of California, Berkeley} \hfill Expected 2025 \\
B.S. in Computer Science \hfill CGPA: 3.8 / 4.0 \\

\section*{Technical Skills}
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item \textbf{Languages:} Python, Go, TypeScript, SQL
\item \textbf{Frameworks \& Libraries:} FastAPI, React, PostgreSQL, Docker
\end{itemize}

\section*{Experience}
\textbf{Software Engineering Intern} \hfill June 2024 -- Aug 2024 \\
\textit{CloudStream Inc.} \\
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item Built streaming ETL pipeline handling 5,000 events/second using Kafka and Python.
\item Reduced database connection churn by 35\% via pooled connection architecture.
\end{itemize}

\section*{Projects}
\textbf{Distributed Key-Value Store} | \textit{Go, Raft} \hfill \href{https://github.com/candidate/raft-kv}{[Code]} \\
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item Implemented linearizable Raft consensus algorithm with snapshotting and log compaction.
\item Benchmarked throughput achieving 12,000 writes/second across a 3-node cluster.
\end{itemize}

\end{document}
"""

SAMPLE_2_PAGE_LATEX = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=0.6in]{geometry}
\usepackage{hyperref}
\usepackage{enumitem}
\usepackage[nobottomtitles*]{titlesec}
\usepackage{parskip}
\usepackage{microtype}

\renewcommand{\bottomtitlespace}{0.8in}
\raggedbottom

\titleformat{\section}{\large\bfseries\uppercase}{}{0em}{}	[\titlerule]
\titlespacing*{\section}{0pt}{5pt plus 1pt minus 1pt}{2.5pt plus 1pt minus 1pt}

\pagestyle{empty}

\begin{document}
\begin{center}
{\Huge \textbf{Candidate Veteran}} \\[2pt]
New York, NY $\cdot$ +1 555-0188 $\cdot$ \href{mailto:veteran@example.com}{veteran@example.com} \\[2pt]
\href{https://github.com/veteran}{GitHub} $\cdot$ \href{https://linkedin.com/in/veteran}{LinkedIn}
\end{center}

\section*{Professional Summary}
Senior Systems Architect with 8+ years experience designing ultra-low-latency distributed infrastructure, transaction processing platforms, and high-availability database engines.

\section*{Experience}
\textbf{Staff Infrastructure Engineer} \hfill 2022 -- Present \\
\textit{Fintech Core Global} \\
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item Architected core transaction gateway processing \$4B daily settlement volume with sub-10ms p99 latency.
\item Redesigned multi-region replication protocol reducing failover Recovery Point Objective (RPO) to zero.
\item Managed fleet of 150 Kubernetes worker nodes with automated zero-downtime rolling upgrades.
\item Led cross-functional team of 12 engineers in migrating legacy mainframe batches into event-driven services.
\item Decreased cloud infrastructure costs by \$320K/yr through proactive memory profile optimization.
\end{itemize}

\textbf{Senior Distributed Systems Engineer} \hfill 2019 -- 2022 \\
\textit{ScaleCloud Systems} \\
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item Built high-throughput distributed message broker supporting 500k messages/sec with end-to-end encryption.
\item Designed custom tiered storage manager offloading older log segments to object storage.
\item Implemented distributed tracing across 40 microservices using OpenTelemetry.
\item Mentored 6 junior and mid-level software engineers through structured pair programming.
\end{itemize}

\textbf{Systems Software Engineer} \hfill 2016 -- 2019 \\
\textit{Enterprise Data Labs} \\
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item Implemented columnar query execution optimizations in C++ for petabyte-scale analytics.
\item Authored kernel bypass networking modules using DPDK to minimize packet serialization overhead.
\item Optimized cache locality of inner join algorithms resulting in 2.8x query speedups.
\end{itemize}

\section*{Featured Systems Architecture Projects}
\textbf{Vector Indexing Storage Engine} | \textit{C++, SIMD, AVX-512} \\
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item Designed HNSW vector indexing library with custom quantization achieving 98\% recall.
\item Optimized vector similarity calculations utilizing AVX-512 SIMD vector instructions.
\end{itemize}

\textbf{Consensus-Based Replicated State Machine} | \textit{Rust, Tokio} \\
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item Implemented Paxos-variant replicated state machine with dynamic cluster reconfiguration.
\item Verified fault tolerance under partition injection tests using Jepsen-style network disruption.
\end{itemize}

\section*{Technical Skills}
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item \textbf{Languages:} C++, Rust, Go, Python, SQL, x86 Assembly
\item \textbf{Distributed Systems:} Raft, Paxos, Kafka, Redis, Etcd, CockroachDB
\item \textbf{Platforms \& Tools:} Linux Kernel Internals, eBPF, Docker, Kubernetes, AWS, GCP
\end{itemize}

\section*{Education}
\textbf{Massachusetts Institute of Technology} \hfill 2012 -- 2016 \\
B.S. in Electrical Engineering and Computer Science \hfill GPA: 4.9 / 5.0

\section*{Patents \& Publications}
\begin{itemize}[leftmargin=12pt, topsep=2pt, itemsep=1pt]
\item \textbf{Deterministic Multi-Master Replication}: US Patent 11,234,567, Granted 2021.
\item \textbf{Low-Overhead Cache Coherence Protocols for NVMe Arrays}: IEEE Transactions, 2018.
\end{itemize}

\end{document}
"""


def test_one_page_resume_within_budget():
    """1. Valid 1-page resume matches target=1 with 'passed' validation status."""
    base_name = "test_budget_1page_target1"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex = os.path.join(STORAGE_DIR, f"{base_name}.tex")
    try:
        ok, path, comp, analysis = compile_and_validate_resume(
            latex_source=SAMPLE_1_PAGE_LATEX,
            base_name=base_name,
            target_page_count=1,
            template_id="fresher_student"
        )
        assert ok is True
        assert analysis["page_count"] == 1
        assert analysis["target_page_count"] == 1
        assert analysis["page_size"] == "Letter"
        assert analysis["validation_status"] == "passed"
        assert len(analysis["errors"]) == 0
        assert len(analysis["warnings"]) == 0
    finally:
        if os.path.exists(target_pdf): os.remove(target_pdf)
        if os.path.exists(target_tex): os.remove(target_tex)


@requires_tectonic
def test_two_page_resume_within_budget():
    """2. Valid 2-page resume matches target=2 with 'passed' validation status."""
    base_name = "test_budget_2page_target2"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex = os.path.join(STORAGE_DIR, f"{base_name}.tex")
    try:
        ok, path, comp, analysis = compile_and_validate_resume(
            latex_source=SAMPLE_2_PAGE_LATEX,
            base_name=base_name,
            target_page_count=2,
            template_id="experience_focused"
        )
        assert ok is True
        assert analysis["page_count"] == 2
        assert analysis["target_page_count"] == 2
        assert analysis["validation_status"] == "passed"
        assert len(analysis["errors"]) == 0
    finally:
        if os.path.exists(target_pdf): os.remove(target_pdf)
        if os.path.exists(target_tex): os.remove(target_tex)


@requires_tectonic
def test_resume_exceeding_target_page_count():
    """3. Resume targeted for 1 page that spills to 2 pages returns 'warning' with overflow diagnostics."""
    base_name = "test_budget_overflow_target1"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex = os.path.join(STORAGE_DIR, f"{base_name}.tex")
    try:
        # Pass 2-page content with explicit target 1
        ok, path, comp, analysis = compile_and_validate_resume(
            latex_source=SAMPLE_2_PAGE_LATEX,
            base_name=base_name,
            target_page_count=1,
            template_id="minimal_professional"
        )
        assert ok is True
        assert analysis["page_count"] == 2
        assert analysis["target_page_count"] == 1
        assert analysis["validation_status"] == "warning"
        assert any("exceeds target budget of 1" in w for w in analysis["warnings"])
    finally:
        if os.path.exists(target_pdf): os.remove(target_pdf)
        if os.path.exists(target_tex): os.remove(target_tex)


def test_empty_or_malformed_pdf():
    """4. Empty (0-byte) or corrupted file returns 'failed' with is_empty_or_malformed=True."""
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"")  # 0 bytes
        empty_path = f.name

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4\nInvalid Corrupted Bytes That Cannot Be Parsed")
        corrupt_path = f.name

    try:
        res_empty = validate_pdf_layout(empty_path, target_page_count=1)
        assert res_empty["validation_status"] == "failed"
        assert len(res_empty["errors"]) > 0

        res_corrupt = validate_pdf_layout(corrupt_path, target_page_count=1)
        assert res_corrupt["validation_status"] == "failed"
        assert len(res_corrupt["errors"]) > 0
    finally:
        if os.path.exists(empty_path): os.remove(empty_path)
        if os.path.exists(corrupt_path): os.remove(corrupt_path)


def test_inconsistent_page_dimensions():
    """5. Multi-page document with mismatched dimensions is detected and flagged."""
    from reportlab.pdfgen import canvas
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        temp_pdf = f.name

    c = canvas.Canvas(temp_pdf, pagesize=(612.0, 792.0))
    c.drawString(100, 700, "Page 1 in standard Letter format.")
    c.showPage()
    c.setPageSize((500.0, 700.0))  # Mismatched dimension
    c.drawString(100, 600, "Page 2 in non-standard Custom format.")
    c.showPage()
    c.save()

    try:
        analysis = analyze_pdf(temp_pdf)
        assert analysis.has_inconsistent_dimensions is True
        assert analysis.page_size == "Inconsistent"

        val = validate_pdf_layout(temp_pdf, target_page_count=2)
        assert any("inconsistent" in w.lower() for w in val["warnings"])
    finally:
        if os.path.exists(temp_pdf): os.remove(temp_pdf)


def test_empty_trailing_page():
    """6. Multi-page document with an empty trailing page is detected and flagged."""
    # Create page 1 with content via reportlab, and page 2 blank
    from reportlab.pdfgen import canvas
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        temp_pdf = f.name

    c = canvas.Canvas(temp_pdf, pagesize=(612, 792))
    c.drawString(100, 700, "Substantive content on Page 1 of the resume document.")
    c.showPage()
    # Page 2 has no text drawn
    c.showPage()
    c.save()

    try:
        analysis = analyze_pdf(temp_pdf)
        assert analysis.page_count == 2
        assert analysis.trailing_page_empty is True

        val = validate_pdf_layout(temp_pdf, target_page_count=2)
        assert any("empty trailing page" in w.lower() for w in val["warnings"])
    finally:
        if os.path.exists(temp_pdf): os.remove(temp_pdf)


def test_sparse_page_detection():
    """7. Multi-page document with a sparse trailing page (< 120 chars) is detected."""
    from reportlab.pdfgen import canvas
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        temp_pdf = f.name

    c = canvas.Canvas(temp_pdf, pagesize=(612, 792))
    # Full substantive content on Page 1
    for y in range(700, 100, -20):
        c.drawString(50, y, "Extensive engineering experience building microservices and data pipelines.")
    c.showPage()
    # Very few characters on Page 2 (e.g. 1 spilled bullet)
    c.drawString(50, 700, "Spilled lone bullet point.")
    c.showPage()
    c.save()

    try:
        analysis = analyze_pdf(temp_pdf)
        assert analysis.page_count == 2
        assert analysis.trailing_page_sparse is True

        val = validate_pdf_layout(temp_pdf, target_page_count=2)
        assert any("sparse" in w.lower() for w in val["warnings"])
    finally:
        if os.path.exists(temp_pdf): os.remove(temp_pdf)


def test_missing_expected_sections():
    """8. Detects when candidate profile has experience or projects but output lacks them."""
    structured_data = {
        "experience": [
            {"company": "Google", "title": "Software Engineer", "bullets": ["Built search"]}
        ],
        "projects": [
            {"title": "Open Source DB", "tech_stack": ["Rust"]}
        ]
    }
    # Compile a minimal PDF containing only summary and education
    minimal_latex = r"""\documentclass[10pt,letterpaper]{article}
\begin{document}
\Huge Candidate Minimal
\section*{Summary}
Only summary text here.
\end{document}
"""
    base_name = "test_missing_sections_check"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    try:
        ok, path, comp = compile_latex(minimal_latex, base_name)
        assert ok is True
        val = validate_pdf_layout(target_pdf, target_page_count=1, structured_data=structured_data)
        assert any("experience" in w.lower() for w in val["warnings"])
        assert any("projects" in w.lower() for w in val["warnings"])
    finally:
        if os.path.exists(target_pdf): os.remove(target_pdf)
        tex = target_pdf.replace(".pdf", ".tex")
        if os.path.exists(tex): os.remove(tex)


def test_long_bullet_wrapping():
    """9. Long technical bullets wrap cleanly without clipping or compiler errors."""
    long_bullet_latex = r"""\documentclass[10pt,letterpaper]{article}
\usepackage[utf8]{inputenc}
\usepackage[margin=0.6in]{geometry}
\usepackage{enumitem}
\usepackage{microtype}
\begin{document}
\section*{Experience}
\begin{itemize}[leftmargin=12pt]
\item Architected, deployed, and benchmarked enterprise-scale distributed consensus cluster utilizing non-blocking asynchronous event loops, custom ring buffers, dynamic rate limiting, and zero-copy protobuf serialization across multiple heterogeneous multi-cloud regions.
\end{itemize}
\end{document}
"""
    base_name = "test_long_bullet_wrapping"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    try:
        ok, path, comp, analysis = compile_and_validate_resume(
            latex_source=long_bullet_latex,
            base_name=base_name,
            target_page_count=1,
            strict=True
        )
        assert ok is True
        assert analysis["page_count"] == 1
        assert analysis["validation_status"] == "passed"
    finally:
        if os.path.exists(target_pdf): os.remove(target_pdf)
        tex = target_pdf.replace(".pdf", ".tex")
        if os.path.exists(tex): os.remove(tex)


@requires_tectonic
def test_failed_validation_preserves_valid_pdf():
    """10. Broken compilation preserves existing valid PDF file with identical hash."""
    base_name = "test_budget_preservation_target"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    target_tex = os.path.join(STORAGE_DIR, f"{base_name}.tex")
    try:
        # Step 1: Compile initial valid PDF
        ok, path, comp, analysis = compile_and_validate_resume(
            latex_source=SAMPLE_1_PAGE_LATEX,
            base_name=base_name,
            target_page_count=1
        )
        assert ok is True
        with open(target_pdf, "rb") as f:
            original_bytes = f.read()
        original_hash = hashlib.sha256(original_bytes).hexdigest()

        # Step 2: Attempt broken compilation
        bad_latex = r"\documentclass{article}\begin{document}\badcommand{broken"
        bad_ok, bad_path, bad_comp, bad_analysis = compile_and_validate_resume(
            latex_source=bad_latex,
            base_name=base_name,
            target_page_count=1,
            strict=True
        )
        assert bad_ok is False
        assert bad_analysis["validation_status"] == "failed"

        # Step 3: Verify original PDF was preserved untouched
        assert os.path.exists(target_pdf)
        with open(target_pdf, "rb") as f:
            current_bytes = f.read()
        current_hash = hashlib.sha256(current_bytes).hexdigest()
        assert current_hash == original_hash
    finally:
        if os.path.exists(target_pdf): os.remove(target_pdf)
        if os.path.exists(target_tex): os.remove(target_tex)


def test_concurrent_compilation_and_promotion_safety():
    """11. Multiple threads compiling resumes concurrently with layout validation execute safely."""
    base_name = "test_concurrent_budget_compilation"
    target_pdf = os.path.join(STORAGE_DIR, f"{base_name}.pdf")
    try:
        def worker(src):
            return compile_and_validate_resume(src, base_name, target_page_count=1)

        with ThreadPoolExecutor(max_workers=2) as executor:
            f1 = executor.submit(worker, SAMPLE_1_PAGE_LATEX)
            f2 = executor.submit(worker, SAMPLE_1_PAGE_LATEX)
            res1 = f1.result()
            res2 = f2.result()

        assert res1[0] is True
        assert res2[0] is True
        assert os.path.exists(target_pdf)
        reader = pypdf.PdfReader(target_pdf)
        assert len(reader.pages) == 1
    finally:
        if os.path.exists(target_pdf): os.remove(target_pdf)
        tex = target_pdf.replace(".pdf", ".tex")
        if os.path.exists(tex): os.remove(tex)


def test_correct_default_target_selection():
    """12. Default target selection: fresher_student -> 1, experienced -> 2."""
    student_data = {"experience": [{"company": "Campus Club", "title": "Lead"}]}
    assert determine_target_page_count("fresher_student", student_data) == 1

    exp_data = {
        "experience": [
            {"company": "Company A", "title": "Engineer"},
            {"company": "Company B", "title": "Senior Engineer"}
        ]
    }
    assert determine_target_page_count("experience_focused", exp_data) == 2
    assert determine_target_page_count("minimal_professional", exp_data) == 2
    assert determine_target_page_count("minimal_professional", student_data) == 1


def test_explicit_target_override():
    """13. Explicit user target overrides template and experience heuristics."""
    exp_data = {
        "experience": [
            {"company": "Company A", "title": "Engineer"},
            {"company": "Company B", "title": "Senior Engineer"}
        ]
    }
    # Explicit target 1 for experienced candidate
    assert determine_target_page_count("experience_focused", exp_data, explicit_target=1) == 1

    # Explicit target 2 for student candidate
    student_data = {"experience": []}
    assert determine_target_page_count("fresher_student", student_data, explicit_target=2) == 2


def test_metadata_consistency_between_api_database_and_pdf():
    """14. Metadata consistency between API response, database, and physical PDF file."""
    user_id = 1501
    db = SessionLocal()
    try:
        cand = CandidateProfile(
            user_id=user_id,
            name="Budgeting Consistency Candidate",
            email="consistency@example.com",
            bio="Software engineer."
        )
        db.add(cand)
        db.commit()

        resume = ResumeDocument(
            user_id=user_id,
            title="Consistency Validation Resume",
            template_id="minimal_professional",
            latex_content=SAMPLE_1_PAGE_LATEX,
            version=1
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        resume_id = resume.id
    finally:
        db.close()

    headers = auth_headers(user_id)
    resp = client.post(
        f"/api/resumes/{resume_id}/compile",
        json={"target_page_count": 1},
        headers=headers
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "page_analysis" in data
    page_analysis = data["page_analysis"]
    assert page_analysis["page_count"] == 1
    assert page_analysis["target_page_count"] == 1
    assert page_analysis["validation_status"] == "passed"

    # Verify physical file on disk matches
    db = SessionLocal()
    try:
        db_resume = db.query(ResumeDocument).filter(ResumeDocument.id == resume_id).first()
        assert db_resume.pdf_path is not None
        assert os.path.exists(db_resume.pdf_path)

        reader = pypdf.PdfReader(db_resume.pdf_path)
        assert len(reader.pages) == page_analysis["page_count"]

        # Verify database JSON persistence
        sc = db_resume.structured_content
        assert isinstance(sc, dict)
        assert "metadata" in sc
        assert "layout_metadata" in sc["metadata"]
        assert sc["metadata"]["layout_metadata"]["page_count"] == 1
        assert sc["metadata"]["layout_metadata"]["target_page_count"] == 1
    finally:
        if db_resume and db_resume.pdf_path and os.path.exists(db_resume.pdf_path):
            os.remove(db_resume.pdf_path)
        db.close()