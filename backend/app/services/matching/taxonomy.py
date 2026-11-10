"""
Canonical Technology Taxonomy & Relationship Graph for CareerOS Matching Intelligence.
Defines canonical naming aliases, related technologies, and transferable skills.
Strictly distinguishes exact technology matches from related or transferable technologies.
"""
from typing import Dict, Tuple, List, Optional

# Canonical Tech Aliases: Raw keyword -> Canonical Name
CANONICAL_ALIASES: Dict[str, str] = {
    "python": "Python",
    "python3": "Python",
    "py": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "ecmascript": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "c++": "C++",
    "cpp": "C++",
    "cxx": "C++",
    "c": "C",
    "c#": "C#",
    "csharp": "C#",
    ".net": "C#",
    "dotnet": "C#",
    "golang": "Go",
    "go": "Go",
    "rust": "Rust",
    "java": "Java",
    "kotlin": "Kotlin",
    "swift": "Swift",
    "sql": "SQL",
    "react": "React",
    "react.js": "React",
    "reactjs": "React",
    "next": "Next.js",
    "next.js": "Next.js",
    "nextjs": "Next.js",
    "vue": "Vue.js",
    "vue.js": "Vue.js",
    "vuejs": "Vue.js",
    "angular": "Angular",
    "angular.js": "Angular",
    "angularjs": "Angular",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "express": "Express",
    "express.js": "Express",
    "expressjs": "Express",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "nest": "NestJS",
    "nest.js": "NestJS",
    "nestjs": "NestJS",
    "fastify": "Fastify",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "psql": "PostgreSQL",
    "mysql": "MySQL",
    "mariadb": "MySQL",
    "mongodb": "MongoDB",
    "mongo": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "docker": "Docker",
    "kubernetes": "Kubernetes",
    "k8s": "Kubernetes",
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "tensorflow": "TensorFlow",
    "tf": "TensorFlow",
    "keras": "TensorFlow",
    "scikit-learn": "Scikit-Learn",
    "sklearn": "Scikit-Learn",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "graphql": "GraphQL",
    "rest": "REST API",
    "rest api": "REST API",
    "restful": "REST API",
    "kafka": "Kafka",
    "apache kafka": "Kafka",
    "git": "Git",
    "github": "Git",
    "gitlab": "Git",
    "linux": "Linux",
    "unix": "Linux",
    "bash": "Linux",
    "shell": "Linux",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "html": "HTML",
    "html5": "HTML",
    "css": "CSS",
    "css3": "CSS",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "terraform": "Terraform",
    "ci/cd": "CI/CD",
    "github actions": "CI/CD",
    "gitlab ci": "CI/CD",
    "jenkins": "CI/CD"
}


# Related Technologies Graph: (Canonical Tech A, Canonical Tech B) -> (similarity_strength, rationale)
# Strength is strictly bounded (0.50 to 0.65), NEVER 1.0 (exact match)
RELATED_TECH_GRAPH: Dict[Tuple[str, str], Tuple[float, str]] = {
    # Frontend frameworks: React is NOT Angular, but they are related
    ("React", "Vue.js"): (0.65, "Component-based reactive UI paradigm translates well between React and Vue."),
    ("Vue.js", "React"): (0.65, "Component-based reactive UI paradigm translates well between Vue and React."),
    ("React", "Angular"): (0.55, "Typed component architectures and web state concepts overlap, but Angular has distinct framework abstractions."),
    ("Angular", "React"): (0.55, "Typed component architectures and web state concepts overlap, but React uses distinct JSX/hooks paradigms."),
    ("Vue.js", "Angular"): (0.55, "Reactive state management and two-way template binding concepts overlap."),
    ("Angular", "Vue.js"): (0.55, "Reactive state management and two-way template binding concepts overlap."),
    ("React", "Next.js"): (0.80, "Next.js is a full-stack framework built directly on React component foundations."),
    ("Next.js", "React"): (0.85, "Next.js mastery inherently encompasses foundational React skills."),

    # Backend frameworks
    ("FastAPI", "Flask"): (0.65, "Both are lightweight Python microframeworks sharing WSGI/ASGI and REST concepts."),
    ("Flask", "FastAPI"): (0.65, "Both are lightweight Python microframeworks sharing WSGI/ASGI and REST concepts."),
    ("FastAPI", "Django"): (0.60, "Both are Python backend frameworks with ORM and routing principles."),
    ("Django", "FastAPI"): (0.60, "Both are Python backend frameworks with ORM and routing principles."),
    ("Flask", "Django"): (0.60, "Both are Python backend frameworks sharing web request/response lifecycles."),
    ("Django", "Flask"): (0.60, "Both are Python backend frameworks sharing web request/response lifecycles."),
    ("Express", "NestJS"): (0.65, "NestJS is built on Node.js/Express primitives with TypeScript architectural layers."),
    ("NestJS", "Express"): (0.70, "NestJS developers have strong mastery over underlying Express/Node.js HTTP handlers."),
    ("Express", "Fastify"): (0.65, "Both are high-performance Node.js HTTP server microframeworks."),
    ("Fastify", "Express"): (0.65, "Both are high-performance Node.js HTTP server microframeworks."),

    # Machine Learning
    ("PyTorch", "TensorFlow"): (0.65, "Deep learning tensor graphs, gradient backpropagation, and neural layers map between frameworks."),
    ("TensorFlow", "PyTorch"): (0.65, "Deep learning tensor graphs, gradient backpropagation, and neural layers map between frameworks."),
    ("Scikit-Learn", "PyTorch"): (0.50, "Classical machine learning pipelines and feature preprocessing share data modeling fundamentals with deep learning."),
    ("PyTorch", "Scikit-Learn"): (0.50, "Data preprocessing, evaluation metrics, and model splitting principles overlap."),

    # Relational Databases
    ("PostgreSQL", "MySQL"): (0.65, "Relational schema design, SQL querying, indexing, and ACID transactions translate directly."),
    ("MySQL", "PostgreSQL"): (0.65, "Relational schema design, SQL querying, indexing, and ACID transactions translate directly."),
    ("PostgreSQL", "SQLite"): (0.60, "Standard SQL syntax, relational tables, and foreign key constraints overlap."),
    ("SQLite", "PostgreSQL"): (0.60, "Standard SQL syntax, relational tables, and foreign key constraints overlap."),

    # Document & Key-Value Stores
    ("MongoDB", "Redis"): (0.45, "Both handle non-relational NoSQL data access and flexible schemas."),
    ("Redis", "MongoDB"): (0.45, "Both handle non-relational NoSQL data access and flexible schemas."),

    # Cloud & DevOps
    ("AWS", "GCP"): (0.60, "Core cloud primitives (VM compute, blob storage, IAM, VPC networks) map directly between AWS and GCP."),
    ("GCP", "AWS"): (0.60, "Core cloud primitives (VM compute, blob storage, IAM, VPC networks) map directly between GCP and AWS."),
    ("AWS", "Azure"): (0.60, "Enterprise cloud architecture, serverless functions, and storage buckets map between AWS and Azure."),
    ("Azure", "AWS"): (0.60, "Enterprise cloud architecture, serverless functions, and storage buckets map between Azure and AWS."),
    ("GCP", "Azure"): (0.60, "Cloud infrastructure, managed Kubernetes, and identity services map between GCP and Azure."),
    ("Azure", "GCP"): (0.60, "Cloud infrastructure, managed Kubernetes, and identity services map between Azure and GCP.")
}


# Transferable Skills Graph: (Candidate Tech -> Target Tech) -> (transferable_strength, rationale)
TRANSFERABLE_TECH_GRAPH: Dict[Tuple[str, str], Tuple[float, str]] = {
    ("Docker", "Kubernetes"): (0.40, "Container image building and runtime fundamentals provide a foundation for Kubernetes orchestration."),
    ("REST API", "GraphQL"): (0.40, "API contract design, HTTP status patterns, and data modeling transfer to GraphQL schema design."),
    ("PostgreSQL", "Redis"): (0.35, "Relational database indexing and query optimization inform effective caching strategies in Redis."),
    ("Python", "Go"): (0.35, "Backend API service design and clean modular code transfer to Go concurrent microservices."),
    ("JavaScript", "TypeScript"): (0.50, "Deep JavaScript runtime, event loop, and DOM mastery forms the core foundation of TypeScript."),
    ("Linux", "CI/CD"): (0.40, "Shell scripting, process management, and environment variables transfer to automated CI/CD pipelines.")
}


def canonicalize_tech_name(raw_name: str) -> str:
    """Returns canonical technology name, or normalized title-cased string if unlisted."""
    if not raw_name:
        return ""
    clean = raw_name.strip().lower()
    return CANONICAL_ALIASES.get(clean, raw_name.strip())


def get_technology_relationship(
    candidate_tech: str,
    required_tech: str
) -> Tuple[str, float, str]:
    """
    Evaluates relationship between candidate technology and required technology.
    Returns: (match_type, strength, explanation)
    match_type: 'exact', 'related', 'transferable', 'none'
    strength: 1.0 (exact), 0.5-0.65 (related), 0.35-0.4 (transferable), 0.0 (none)
    """
    cand_canon = canonicalize_tech_name(candidate_tech)
    req_canon = canonicalize_tech_name(required_tech)

    if not cand_canon or not req_canon:
        return ("none", 0.0, "Missing technology data.")

    # 1. Exact match
    if cand_canon.lower() == req_canon.lower():
        return (
            "exact",
            1.0,
            f"Exact match on {req_canon}."
        )

    # 2. Related technology
    rel_key = (cand_canon, req_canon)
    if rel_key in RELATED_TECH_GRAPH:
        strength, rationale = RELATED_TECH_GRAPH[rel_key]
        return (
            "related",
            strength,
            f"Related technology: Candidate demonstrates {cand_canon}. {rationale}"
        )

    # 3. Transferable skill
    trans_key = (cand_canon, req_canon)
    if trans_key in TRANSFERABLE_TECH_GRAPH:
        strength, rationale = TRANSFERABLE_TECH_GRAPH[trans_key]
        return (
            "transferable",
            strength,
            f"Transferable skill: Candidate demonstrates {cand_canon}. {rationale}"
        )

    return ("none", 0.0, f"No technology alignment between {cand_canon} and {req_canon}.")
