# CareerOS: Intelligent Job Discovery & Opportunity Aggregation Engine (`interniq`)

An automated internship and entry-level opportunity discovery engine designed for Indian undergraduate engineering students and early-career developers. 

The system continuously searches multiple company career pages (Greenhouse, Lever, Ashby, SmartRecruiters), public job APIs (Remotive, Remote OK, Adzuna, RSS), and supports compliant manual and URL-based ingestion from India platforms (Internshala, LinkedIn Jobs, Naukri, Wellfound, Indeed). Discovered opportunities are normalized into a unified schema, deduplicated across platforms, analyzed for geographical and cohort eligibility, ranked against verified candidate profiles using local Ollama AI and deterministic 6-factor scoring, and seamlessly handed off to an application tracker.

---

## Key Features

1. **Multi-Source Aggregation & Company Monitoring**:
   - **Company ATS Career Pages**: Direct monitoring of Greenhouse, Lever, Ashby, and SmartRecruiters public boards (e.g. Cloudflare, Palantir, Replit, Visa, Databricks, Postman, Razorpay, Zepto, Hasura).
   - **Job Discovery APIs & Remote Sources**: Remotive, Remote OK, Adzuna, and custom RSS feeds with strict geographical eligibility checks (Remote India vs US/EU resident restrictions).
   - **India-Focused Platforms**: Compliant URL extraction, description paste, and email alert digest parsing for Internshala, LinkedIn Jobs, Naukri, Wellfound, and Indeed without bypassing anti-bot or authentication barriers.
2. **5-Stage Ingestion Pipeline**:
   - **Stage 1 (Collection)**: Raw opportunity ingestion preserving origin data and URLs.
   - **Stage 2 (Normalization)**: Canonical role mapping, location normalization, and stipend currency parsing.
   - **Stage 3 (Duplicate Detection)**: Multi-source duplicate identification via URL, external IDs, and company/title similarity. Merges multiple links into a single opportunity record.
   - **Stage 4 (Validity & Expiration)**: Application deadline tracking (`active`, `possibly_expired`, `expired`, `closed`).
   - **Stage 5 (Candidate Eligibility)**: Graduation year and geographical authorization verification (flags non-Indian remote positions).
3. **Local AI Analysis & Transparent Matching**:
   - **Local Ollama Integration**: Uses `bge-m3` for 1024-dimensional semantic embeddings stored in PostgreSQL `pgvector`, and `qwen2.5:3b` / `llama3.2` for structured technical requirement extraction.
   - **Deterministic 6-Factor Compatibility Scorer**:
     - Required Technical Skills: 35%
     - Relevant Projects & Experience: 25%
     - Education & Eligibility: 15%
     - Preferred Skills: 10%
     - Location & Availability: 10%
     - Other Requirements: 5%
   - **Transferable Skills Reasoning**: Explains competency bridges (e.g., Express.js -> REST APIs, TensorFlow -> PyTorch, React -> Vue).
4. **Opportunity Discovery Dashboard & Application Handoff**:
   - Tabbed database views: **Recommended**, **Latest**, **Saved**, **Expiring Soon**, **Applied**, and **Dismissed**.
   - One-click **Track Application** handoff with tailored resume angles and cover letter talking points.
   - **Source Management Interface** with connection testing, sync intervals, and execution logs.
   - **Monitored Company Directory** with individual board polling.
   - **Discovery Analytics** reporting conversion rates, duplicate savings, and sync reliability.

---

## Architecture

```
interniq/
├── backend/
│   ├── app/
│   │   ├── ai/            # Ollama client, requirement extractor, 6-factor scorer
│   │   ├── api/           # FastAPI routers (opportunities, import, companies, sources, etc.)
│   │   ├── connectors/    # Greenhouse, Lever, Ashby, SmartRecruiters, Remotive, etc.
│   │   ├── models/        # SQLAlchemy models (pgvector Opportunity, Company, Source, etc.)
│   │   ├── pipeline/      # Normalizer, Duplicate Detector, Validity & Eligibility checkers
│   │   ├── services/      # Discovery scheduler, application handoff, analytics, seed data
│   │   ├── config.py      # Application settings & environment variables
│   │   ├── database.py    # PostgreSQL connection with pgvector
│   │   └── main.py        # FastAPI entrypoint
│   ├── tests/             # Automated test suite (Pytest)
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # Discovery, Detail Modal, Companies, Sources, Preferences, Tracker
│   │   ├── services/      # API client
│   │   ├── types/         # TypeScript definitions
│   │   ├── App.tsx        # Root application
│   │   └── index.css      # Tailwind styling
│   ├── package.json
│   └── vite.config.ts
├── run.sh                 # Unified launcher script
└── README.md
```

---

## Quick Start

### Prerequisites
- Python 3.10+ (tested on Python 3.14)
- Node.js 18+ (tested on Node v22)
- PostgreSQL with `pgvector` extension enabled
- Ollama running locally with `bge-m3` and `qwen2.5:3b`

### Launching the Application
Execute the root runner script:
```bash
./run.sh
```
- **Backend**: `http://127.0.0.1:8005` (API docs at `http://127.0.0.1:8005/docs`)
- **Frontend Dashboard**: `http://127.0.0.1:5174`

### Running Automated Tests
```bash
PYTHONPATH=. backend/venv/bin/pytest backend/tests/test_engine.py
```

### Continuous integration
`.github/workflows/ci.yml` runs pull-request and `main` validation: backend suite on a disposable synthetic CI database, frontend install/type-check/tests/build, static security checks, and Docker build + boot. `release-gate` passes only when every required check succeeds. Production deploy is **not** part of this pipeline and remains operator-controlled. See `.taste-skill/production-readiness/ci-release-gates.md`.
