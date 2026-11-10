"""
Structured Skill Gap Analyzer for CareerOS Matching Intelligence.
Detects missing or partially matched mandatory and preferred requirements,
constructs granular missing evidence descriptions, and provides specific,
actionable project/learning recommendations (never recommending skills
the candidate has already verified).
"""
import logging
from typing import List, Dict, Optional

from backend.app.schemas.matching import (
    RequirementMatchResult,
    SkillGap,
    MatchStatus,
    RequirementPriority
)

logger = logging.getLogger(__name__)

# Specialized Actionable Recommendations Catalog
SPECIALIZED_RECOMMENDATIONS: Dict[str, str] = {
    "angular": "Build a modular web dashboard using Angular standalone components, RxJS state streams, and typed reactive forms.",
    "react": "Build an interactive client application featuring React functional components, custom hooks, and modern state management.",
    "vue.js": "Create a responsive single-page application utilizing Vue 3 Composition API, Pinia store, and Vue Router.",
    "next.js": "Implement a full-stack web application leveraging Next.js App Router, Server Components, and API route handlers.",
    "fastapi": "Develop an asynchronous REST microservice using FastAPI, Pydantic data validation schemas, and async SQLAlchemy sessions.",
    "django": "Construct a full-featured web backend using Django ORM, authentication middleware, and class-based REST API views.",
    "flask": "Implement a modular RESTful service using Flask Blueprints, application factories, and pytest test fixtures.",
    "docker": "Containerize an existing multi-tier web application using Docker multi-stage builds and docker-compose service definitions.",
    "kubernetes": "Deploy and orchestrate containerized services on local Minikube/k3s with Helm charts, Ingress controllers, and pod autoscaling.",
    "aws": "Architect and deploy cloud infrastructure using AWS Lambda, S3 storage buckets, API Gateway, and Terraform IaC.",
    "gcp": "Deploy containerized services on Google Cloud Run with Cloud SQL database integration and IAM least-privilege security roles.",
    "azure": "Configure Azure App Services and Azure Blob Storage connected to Azure SQL with automated GitHub Actions deployment.",
    "postgresql": "Design a relational schema with PostgreSQL foreign key cascades, partial indexes, and JSONB document queries.",
    "mongodb": "Implement a document data model in MongoDB with compound indexing, aggregation pipelines, and replica sets.",
    "redis": "Implement distributed session caching, background task queues, and token-bucket rate limiting using Redis data structures.",
    "graphql": "Build a typed GraphQL schema using Apollo Server with query resolvers, mutations, and DataLoader batching.",
    "kafka": "Implement an event-driven pub/sub architecture using Apache Kafka topics, partitioned event streams, and consumer groups.",
    "pytorch": "Train and evaluate a deep neural network model using PyTorch tensor operations, DataLoader pipelines, and GPU acceleration.",
    "tensorflow": "Build and export an end-to-end machine learning pipeline using TensorFlow/Keras with custom training loops.",
    "typescript": "Migrate a JavaScript codebase to strict TypeScript with generic interfaces, union discriminators, and type guards.",
    "c++": "Implement a performance-critical data structure emulator in modern C++ (C++17/20) with RAII and smart pointers.",
    "go": "Develop a high-throughput microservice in Go utilizing goroutines, sync channels, and standard library HTTP handlers."
}


def generate_actionable_recommendation(skill_name: str, category: str) -> str:
    """Generates concrete, domain-specific project and learning recommendations."""
    clean = skill_name.strip().lower()
    if clean in SPECIALIZED_RECOMMENDATIONS:
        return SPECIALIZED_RECOMMENDATIONS[clean]
    
    # Category-based tailored fallbacks (never generic 'learn programming')
    if category == "database":
        return f"Design a production data schema using {skill_name}, implement indexing strategies, and optimize query latency."
    elif category == "cloud_devops":
        return f"Automate deployment pipelines and cloud infrastructure provisioning utilizing {skill_name}."
    elif category == "framework_library":
        return f"Build and deploy an architectural portfolio module demonstrating production-grade features in {skill_name}."
    elif category == "programming_language":
        return f"Develop a modular, test-driven backend or systems utility in {skill_name} showcasing idiomatic patterns."
    else:
        return f"Build a verifiable portfolio project demonstrating practical implementation of {skill_name} with automated tests."


def analyze_skill_gaps(requirement_matches: List[RequirementMatchResult]) -> List[SkillGap]:
    """
    Identifies genuine gaps where candidate lacks verified evidence.
    - Excludes requirements where candidate already demonstrates STRONG_MATCH (verified exact match).
    - Prioritizes Mandatory gaps before Preferred gaps.
    """
    gaps: List[SkillGap] = []

    for m in requirement_matches:
        req = m.requirement
        
        # Candidate already demonstrates verified exact match -> NOT a skill gap
        if m.status == MatchStatus.STRONG_MATCH:
            continue

        skill_name = req.name
        priority = req.priority
        
        if m.status in [MatchStatus.PARTIAL_MATCH, MatchStatus.WEAK_MATCH]:
            current_evidence = m.explanation
            missing_evidence = (
                f"Candidate demonstrates related/transferable competencies, but lacks verified "
                f"production or project proof in exact technology '{skill_name}'."
            )
        else: # NO_EVIDENCE
            current_evidence = "No candidate evidence found in profile, projects, or repository intelligence."
            missing_evidence = f"Candidate has zero verified coursework, projects, or repository evidence for '{skill_name}'."

        recommendation = generate_actionable_recommendation(skill_name, req.category)

        gaps.append(SkillGap(
            skill_name=skill_name,
            priority=priority,
            current_evidence=current_evidence,
            missing_evidence=missing_evidence,
            suggested_learning_or_improvement=recommendation
        ))

    # Sort gaps: MANDATORY first, then PREFERRED, then OPTIONAL
    priority_order = {
        RequirementPriority.MANDATORY: 0,
        RequirementPriority.PREFERRED: 1,
        RequirementPriority.OPTIONAL: 2
    }
    gaps.sort(key=lambda g: priority_order.get(g.priority, 3))
    return gaps
