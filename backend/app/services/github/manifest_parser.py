import re
import json
import logging
from typing import Dict, Any, List, Optional
from backend.app.schemas.github_intelligence import TechnologyEvidence

logger = logging.getLogger(__name__)

# Canonical Technology Catalogs
PYTHON_CATALOG = {
    "fastapi": ("FastAPI", "Framework"),
    "django": ("Django", "Framework"),
    "flask": ("Flask", "Framework"),
    "sqlalchemy": ("SQLAlchemy", "Database"),
    "alembic": ("Alembic", "Database"),
    "pytest": ("pytest", "Testing"),
    "unittest": ("unittest", "Testing"),
    "torch": ("PyTorch", "AI/ML"),
    "pytorch": ("PyTorch", "AI/ML"),
    "tensorflow": ("TensorFlow", "AI/ML"),
    "pandas": ("Pandas", "AI/ML"),
    "numpy": ("NumPy", "AI/ML"),
    "celery": ("Celery", "Tooling"),
    "redis": ("Redis", "Database"),
    "pydantic": ("Pydantic", "Framework"),
    "uvicorn": ("Uvicorn", "Tooling"),
    "psycopg": ("PostgreSQL", "Database"),
    "psycopg2": ("PostgreSQL", "Database"),
    "asyncpg": ("PostgreSQL", "Database"),
    "pymongo": ("MongoDB", "Database"),
    "scikit-learn": ("Scikit-Learn", "AI/ML"),
    "sklearn": ("Scikit-Learn", "AI/ML"),
    "beautifulsoup4": ("BeautifulSoup", "Tooling"),
    "scrapy": ("Scrapy", "Tooling"),
    "httpx": ("HTTPX", "Tooling"),
    "requests": ("Requests", "Tooling"),
}

JS_TS_CATALOG = {
    "react": ("React", "Framework"),
    "next": ("Next.js", "Framework"),
    "vue": ("Vue.js", "Framework"),
    "angular": ("Angular", "Framework"),
    "express": ("Express", "Framework"),
    "@nestjs/core": ("NestJS", "Framework"),
    "fastify": ("Fastify", "Framework"),
    "typescript": ("TypeScript", "Language"),
    "tailwindcss": ("Tailwind CSS", "Framework"),
    "tailwind": ("Tailwind CSS", "Framework"),
    "prisma": ("Prisma", "Database"),
    "@prisma/client": ("Prisma", "Database"),
    "mongoose": ("Mongoose", "Database"),
    "pg": ("PostgreSQL", "Database"),
    "typeorm": ("TypeORM", "Database"),
    "drizzle-orm": ("Drizzle ORM", "Database"),
    "jest": ("Jest", "Testing"),
    "vitest": ("Vitest", "Testing"),
    "@playwright/test": ("Playwright", "Testing"),
    "cypress": ("Cypress", "Testing"),
    "mocha": ("Mocha", "Testing"),
    "redux": ("Redux", "Framework"),
    "@reduxjs/toolkit": ("Redux Toolkit", "Framework"),
    "graphql": ("GraphQL", "Architecture"),
    "apollo-server": ("Apollo GraphQL", "Framework"),
    "socket.io": ("Socket.IO", "Tooling"),
    "electron": ("Electron", "Framework"),
    "vite": ("Vite", "Build Tool"),
    "webpack": ("Webpack", "Build Tool"),
    "eslint": ("ESLint", "Tooling")
}

RUST_CATALOG = {
    "tokio": ("Tokio", "Framework"),
    "axum": ("Axum", "Framework"),
    "actix-web": ("Actix-web", "Framework"),
    "serde": ("Serde", "Framework"),
    "diesel": ("Diesel", "Database"),
    "sqlx": ("SQLx", "Database"),
    "anyhow": ("Anyhow", "Tooling"),
    "tracing": ("Tracing", "Tooling")
}

GO_CATALOG = {
    "github.com/gin-gonic/gin": ("Gin", "Framework"),
    "github.com/gofiber/fiber": ("Fiber", "Framework"),
    "github.com/gorilla/mux": ("Gorilla Mux", "Framework"),
    "github.com/go-chi/chi": ("Chi", "Framework"),
    "gorm.io/gorm": ("GORM", "Database"),
    "github.com/lib/pq": ("PostgreSQL", "Database"),
    "github.com/jackc/pgx": ("PostgreSQL", "Database"),
    "google.golang.org/grpc": ("gRPC", "Architecture")
}


def parse_package_json(content: str, filename: str = "package.json") -> List[TechnologyEvidence]:
    """Extracts frameworks, libraries, databases, and testing tools from package.json."""
    results = []
    try:
        data = json.loads(content)
        deps = data.get("dependencies", {})
        dev_deps = data.get("devDependencies", {})
        all_deps = {**deps, **dev_deps}

        for pkg_name, ver in all_deps.items():
            clean_pkg = pkg_name.lower().strip()
            if clean_pkg in JS_TS_CATALOG:
                name, cat = JS_TS_CATALOG[clean_pkg]
                results.append(TechnologyEvidence(
                    name=name,
                    category=cat,
                    source_file=filename,
                    confidence="high",
                    version=str(ver).lstrip("^~>=<") if ver else None
                ))
            elif "react" in clean_pkg:
                results.append(TechnologyEvidence(name="React", category="Framework", source_file=filename, confidence="high"))
            elif "tailwind" in clean_pkg:
                results.append(TechnologyEvidence(name="Tailwind CSS", category="Framework", source_file=filename, confidence="high"))
            elif "postgres" in clean_pkg:
                results.append(TechnologyEvidence(name="PostgreSQL", category="Database", source_file=filename, confidence="high"))

    except Exception as e:
        logger.debug(f"Failed to parse package.json {filename}: {e}")
    return results


def parse_requirements_txt(content: str, filename: str = "requirements.txt") -> List[TechnologyEvidence]:
    """Extracts Python libraries and tools from requirements.txt."""
    results = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Split on standard version specifiers (==, >=, <=, ~=, !=) and extras bracket [
        pkg_part = re.split(r'[=><~;\[]', line)[0].strip().lower()
        if not pkg_part:
            continue
        if pkg_part in PYTHON_CATALOG:
            name, cat = PYTHON_CATALOG[pkg_part]
            results.append(TechnologyEvidence(
                name=name,
                category=cat,
                source_file=filename,
                confidence="high"
            ))
    return results


def parse_pyproject_toml(content: str, filename: str = "pyproject.toml") -> List[TechnologyEvidence]:
    """Extracts Python dependencies from pyproject.toml."""
    results = []
    # Search for dependencies array/table without requiring toml dependency
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg_part = re.split(r'[=><~;,"]', line.strip('[]"\' ,'))[0].strip().lower()
        if pkg_part in PYTHON_CATALOG:
            name, cat = PYTHON_CATALOG[pkg_part]
            results.append(TechnologyEvidence(
                name=name,
                category=cat,
                source_file=filename,
                confidence="high"
            ))
    return results


def parse_cargo_toml(content: str, filename: str = "Cargo.toml") -> List[TechnologyEvidence]:
    """Extracts Rust crates from Cargo.toml."""
    results = [TechnologyEvidence(name="Rust", category="Language", source_file=filename, confidence="high")]
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("["):
            continue
        crate_name = line.split("=")[0].strip().lower()
        if crate_name in RUST_CATALOG:
            name, cat = RUST_CATALOG[crate_name]
            results.append(TechnologyEvidence(name=name, category=cat, source_file=filename, confidence="high"))
    return results


def parse_go_mod(content: str, filename: str = "go.mod") -> List[TechnologyEvidence]:
    """Extracts Go modules from go.mod."""
    results = [TechnologyEvidence(name="Go", category="Language", source_file=filename, confidence="high")]
    for line in content.splitlines():
        line = line.strip()
        for mod_prefix, (name, cat) in GO_CATALOG.items():
            if mod_prefix in line:
                results.append(TechnologyEvidence(name=name, category=cat, source_file=filename, confidence="high"))
    return results


def parse_pom_xml(content: str, filename: str = "pom.xml") -> List[TechnologyEvidence]:
    """Extracts Java libraries from pom.xml."""
    results = [TechnologyEvidence(name="Java", category="Language", source_file=filename, confidence="high")]
    if "spring-boot" in content.lower():
        results.append(TechnologyEvidence(name="Spring Boot", category="Framework", source_file=filename, confidence="high"))
    if "junit" in content.lower():
        results.append(TechnologyEvidence(name="JUnit", category="Testing", source_file=filename, confidence="high"))
    if "hibernate" in content.lower():
        results.append(TechnologyEvidence(name="Hibernate", category="Database", source_file=filename, confidence="high"))
    return results


def parse_build_gradle(content: str, filename: str = "build.gradle") -> List[TechnologyEvidence]:
    """Extracts Gradle / Kotlin / Java dependencies."""
    results = []
    if "kotlin" in content.lower():
        results.append(TechnologyEvidence(name="Kotlin", category="Language", source_file=filename, confidence="high"))
    else:
        results.append(TechnologyEvidence(name="Java", category="Language", source_file=filename, confidence="high"))
    if "spring" in content.lower():
        results.append(TechnologyEvidence(name="Spring Boot", category="Framework", source_file=filename, confidence="high"))
    if "junit" in content.lower():
        results.append(TechnologyEvidence(name="JUnit", category="Testing", source_file=filename, confidence="high"))
    return results


def parse_composer_json(content: str, filename: str = "composer.json") -> List[TechnologyEvidence]:
    """Extracts PHP dependencies from composer.json."""
    results = [TechnologyEvidence(name="PHP", category="Language", source_file=filename, confidence="high")]
    try:
        data = json.loads(content)
        reqs = {**data.get("require", {}), **data.get("require-dev", {})}
        for pkg in reqs:
            if "laravel" in pkg.lower():
                results.append(TechnologyEvidence(name="Laravel", category="Framework", source_file=filename, confidence="high"))
            elif "symfony" in pkg.lower():
                results.append(TechnologyEvidence(name="Symfony", category="Framework", source_file=filename, confidence="high"))
            elif "phpunit" in pkg.lower():
                results.append(TechnologyEvidence(name="PHPUnit", category="Testing", source_file=filename, confidence="high"))
    except Exception:
        pass
    return results


def parse_dockerfile(content: str, filename: str = "Dockerfile") -> List[TechnologyEvidence]:
    """Detects containerization, base environments, and database services from Dockerfiles."""
    results = [TechnologyEvidence(name="Docker", category="Containerization", source_file=filename, confidence="high")]
    lower = content.lower()
    if "postgres" in lower:
        results.append(TechnologyEvidence(name="PostgreSQL", category="Database", source_file=filename, confidence="high"))
    if "redis" in lower:
        results.append(TechnologyEvidence(name="Redis", category="Database", source_file=filename, confidence="high"))
    if "node" in lower:
        results.append(TechnologyEvidence(name="Node.js", category="Language", source_file=filename, confidence="high"))
    if "python" in lower:
        results.append(TechnologyEvidence(name="Python", category="Language", source_file=filename, confidence="high"))
    if "nginx" in lower:
        results.append(TechnologyEvidence(name="Nginx", category="Tooling", source_file=filename, confidence="high"))
    return results


def parse_github_actions(content: str, filename: str) -> List[TechnologyEvidence]:
    """Detects CI/CD workflows and automation practices."""
    results = [TechnologyEvidence(name="GitHub Actions", category="CI/CD", source_file=filename, confidence="high")]
    lower = content.lower()
    if "pytest" in lower or "test" in lower or "jest" in lower:
        results.append(TechnologyEvidence(name="Automated CI Testing", category="CI/CD", source_file=filename, confidence="high"))
    if "docker" in lower or "build-push-action" in lower:
        results.append(TechnologyEvidence(name="Docker Deployment CI", category="CI/CD", source_file=filename, confidence="high"))
    return results


def extract_technologies_from_manifests(manifest_files: Dict[str, str]) -> List[TechnologyEvidence]:
    """
    Orchestrates deterministic technology extraction across all discovered repository manifest files.
    Deduplicates results by technology name, prioritizing explicit manifest files over descriptions.
    """
    discovered: List[TechnologyEvidence] = []
    seen = set()

    for path, content in manifest_files.items():
        if not content:
            continue
        base_name = path.split("/")[-1].lower()

        if base_name == "package.json":
            discovered.extend(parse_package_json(content, filename=path))
        elif base_name == "requirements.txt" or base_name.endswith(".requirements.txt"):
            discovered.extend(parse_requirements_txt(content, filename=path))
        elif base_name == "pyproject.toml":
            discovered.extend(parse_pyproject_toml(content, filename=path))
        elif base_name == "cargo.toml":
            discovered.extend(parse_cargo_toml(content, filename=path))
        elif base_name == "go.mod":
            discovered.extend(parse_go_mod(content, filename=path))
        elif base_name == "pom.xml":
            discovered.extend(parse_pom_xml(content, filename=path))
        elif base_name in ("build.gradle", "build.gradle.kts"):
            discovered.extend(parse_build_gradle(content, filename=path))
        elif base_name == "composer.json":
            discovered.extend(parse_composer_json(content, filename=path))
        elif "dockerfile" in base_name or "docker-compose" in base_name:
            discovered.extend(parse_dockerfile(content, filename=path))
        elif ".github/workflows" in path and (path.endswith(".yml") or path.endswith(".yaml")):
            discovered.extend(parse_github_actions(content, filename=path))

    # Deduplicate while preserving source citations
    unique_tech: List[TechnologyEvidence] = []
    for t in discovered:
        key = (t.name.lower(), t.category.lower())
        if key not in seen:
            seen.add(key)
            if not t.evidence_id:
                clean_slug = re.sub(r'[^a-zA-Z0-9_]', '_', t.name.lower()).strip('_')
                t.evidence_id = f"tech_{clean_slug}"
            unique_tech.append(t)

    return unique_tech


parse_manifests = extract_technologies_from_manifests
extract_file_content_manifests = extract_technologies_from_manifests

KNOWN_MANIFESTS = {
    "package.json", "requirements.txt", "pyproject.toml", "pipfile",
    "cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "composer.json", "dockerfile", "docker-compose.yml", "docker-compose.yaml"
}

