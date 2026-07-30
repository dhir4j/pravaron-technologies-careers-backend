from __future__ import annotations

from .extensions import db
from .models import Job, User
from .services import slugify

JOB_CATALOG = [
    {
        "public_code": "PRV-AIML-BE-INTERN",
        "title": "AI/ML & Backend Intern",
        "slug": "ai-ml-backend-intern",
        "department": "AI Systems",
        "employment_type": "Internship",
        "experience_level": "Recent Graduate",
        "openings": 1,
        "location": "Sector 140A, Noida",
        "workplace_model": "Onsite",
        "role_summary": "Contribute to generative AI, machine learning, agentic systems, backend APIs, automation workflows, and intelligent product development.",
        "responsibilities": "Develop AI/ML prototypes, build agents and RAG pipelines, research AI frameworks, work with embeddings and vector databases, clean and validate datasets, build Flask APIs, support PostgreSQL models, integrate AI services, write tests, debug, and document experiments.",
        "required_skills": ["Python", "Machine learning basics", "Generative AI", "LLM basics", "Flask", "REST APIs", "PostgreSQL", "SQL", "Pandas", "NumPy", "Git", "Data processing", "Debugging", "Communication"],
        "preferred_skills": ["FastAPI", "SQLAlchemy", "MongoDB", "LangChain", "LangGraph", "LlamaIndex", "Hugging Face", "scikit-learn", "PyTorch", "TensorFlow", "Vector databases", "NLP", "Selenium", "Playwright", "Docker", "Linux", "Cloud deployment"],
        "education_preference": "Recent 2025 or 2026 B.Tech/B.E. graduates in CS, IT, or AI/ML.",
        "experience_requirement": "0-1 year; at least one relevant AI/ML or backend project.",
        "source_metadata": {"role_family": "ai_ml_backend", "target_track": "Internship", "priority_locations": ["Delhi", "Noida", "Greater Noida", "NCR", "Ghaziabad", "Gurgaon", "Gurugram", "Faridabad"]},
        "status": "published",
    },
    {
        "public_code": "PRV-FS-DEV",
        "title": "Full-Stack Software Developer",
        "slug": "full-stack-software-developer",
        "department": "Engineering",
        "employment_type": "Full-time",
        "experience_level": "Early Career",
        "openings": 1,
        "location": "Sector 140A, Noida",
        "workplace_model": "Onsite",
        "role_summary": "Build web applications, AI-powered products, automation platforms, internal tools, admin dashboards, and scalable software systems.",
        "responsibilities": "Build full-stack applications, React/Next.js frontends, Python/Flask APIs, PostgreSQL and MongoDB data models, RBAC, dashboards, API integrations, forms, analytics interfaces, notifications, background jobs, tests, deployments, and maintainable documented code.",
        "required_skills": ["JavaScript", "TypeScript", "React", "Next.js", "HTML", "CSS", "Tailwind CSS", "Python", "Flask", "REST APIs", "PostgreSQL", "SQL", "MongoDB", "Authentication", "Authorization", "Git", "Responsive web development", "Testing", "Linux", "Deployment"],
        "preferred_skills": ["Node.js", "SQLAlchemy", "Flask-Migrate", "React Hook Form", "Zod", "TanStack Query", "Zustand", "Redux", "Docker", "Redis", "WebSockets", "Selenium", "Playwright", "Vercel", "PythonAnywhere", "AWS", "Azure", "CI/CD", "LLM APIs", "n8n", "Security"],
        "education_preference": "B.Tech/B.E./M.Tech/MCA/M.Sc/MS in CS, IT, Software Engineering, AI/ML, or related field.",
        "experience_requirement": "1-2 years relevant full-stack or software-development experience.",
        "source_metadata": {"role_family": "full_stack", "target_track": "Full-time", "priority_locations": ["Delhi", "Noida", "Greater Noida", "NCR", "Ghaziabad", "Gurgaon", "Gurugram", "Faridabad"]},
        "status": "published",
    },
    {
        "public_code": "PRV-UIUX-DES",
        "title": "UI/UX Designer",
        "slug": "ui-ux-designer",
        "department": "Design",
        "employment_type": "Full-time",
        "experience_level": "Early Career",
        "openings": 1,
        "location": "Sector 140A, Noida",
        "workplace_model": "Onsite",
        "role_summary": "Design modern, intuitive, responsive, and visually distinctive digital experiences for products, dashboards, admin panels, internal tools, and company websites.",
        "responsibilities": "Create user flows, journey maps, IA, wireframes, prototypes, high-fidelity Figma designs, SaaS dashboards, design systems, responsive states, developer handoff, accessibility improvements, and design reviews.",
        "required_skills": ["Figma", "UI design", "UX design", "User flows", "Information architecture", "Wireframing", "Prototyping", "Responsive design", "SaaS dashboards", "Design systems", "Typography", "Visual hierarchy", "Interaction design", "Developer handoff", "Accessibility"],
        "preferred_skills": ["AI product design", "Workflow platforms", "Admin panels", "Data dashboards", "React", "Next.js", "HTML", "CSS", "Tailwind CSS", "Motion design", "Framer", "User testing", "Branding"],
        "education_preference": "Design degree, HCI/UX degree, or technical degree with strong portfolio.",
        "experience_requirement": "1-2 years relevant UI/UX or product-design experience.",
        "source_metadata": {"role_family": "ui_ux", "target_track": "Full-time", "priority_locations": ["Delhi", "Noida", "Greater Noida", "NCR", "Ghaziabad", "Gurgaon", "Gurugram", "Faridabad"]},
        "status": "published",
    },
    {
        "public_code": "PRV-AIML-INTERN",
        "title": "AI/ML Intern",
        "slug": "ai-ml-intern",
        "department": "AI Systems",
        "employment_type": "Internship",
        "experience_level": "Recent Graduate",
        "openings": 1,
        "location": "Sector 140A, Noida",
        "workplace_model": "Onsite",
        "role_summary": "Work on generative AI, machine learning, AI agents, retrieval systems, automation workflows, and intelligent product development.",
        "responsibilities": "Build AI/ML prototypes, research model frameworks, support RAG pipelines, prepare data, test prompts and structured outputs, integrate AI APIs, build Python utilities, document experiments, and learn responsible AI practices.",
        "required_skills": ["Python", "Machine learning basics", "Generative AI", "LLM basics", "SQL", "Pandas", "NumPy", "REST APIs", "Git", "Data processing", "Problem solving", "Documentation"],
        "preferred_skills": ["AI/ML projects", "scikit-learn", "PyTorch", "TensorFlow", "Hugging Face", "Flask", "FastAPI", "LangChain", "LangGraph", "Vector databases", "NLP", "Selenium", "Playwright", "Docker", "Cloud"],
        "education_preference": "Recent B.Tech/B.E. graduates in CS, IT, or AI/ML.",
        "experience_requirement": "0-1 year with at least one academic or personal AI/ML project.",
        "source_metadata": {"role_family": "ai_ml", "target_track": "Internship", "priority_locations": ["Delhi", "Noida", "Greater Noida", "NCR", "Ghaziabad", "Gurgaon", "Gurugram", "Faridabad"]},
        "status": "published",
    },
    {
        "public_code": "PRV-FE-INTERN",
        "title": "Frontend Development Intern",
        "slug": "frontend-development-intern",
        "department": "Engineering",
        "employment_type": "Internship",
        "experience_level": "Recent Graduate",
        "openings": 1,
        "location": "Sector 140A, Noida",
        "workplace_model": "Onsite",
        "role_summary": "Build modern, responsive, and user-friendly web interfaces for company websites, AI product interfaces, SaaS dashboards, admin panels, recruitment systems, internal tools, and automation platforms.",
        "responsibilities": "Develop React/Next.js interfaces, convert Figma designs, build reusable UI components, integrate REST APIs, implement forms/tables/filters/dashboards, handle states, test responsive layouts, improve accessibility and performance, and document frontend work.",
        "required_skills": ["HTML", "CSS", "JavaScript", "React", "Responsive web design", "REST APIs", "Git", "GitHub", "Component development", "Forms", "Problem solving", "Visual detail"],
        "preferred_skills": ["Next.js", "TypeScript", "Tailwind CSS", "React Hook Form", "Zod", "TanStack Query", "Zustand", "Redux", "Framer Motion", "Figma", "UI/UX", "Playwright", "Vercel"],
        "education_preference": "Recent B.Tech/B.E. graduates in CS, IT, or AI/ML.",
        "experience_requirement": "0-1 year with at least one React or Next.js project.",
        "source_metadata": {"role_family": "frontend", "target_track": "Internship", "priority_locations": ["Delhi", "Noida", "Greater Noida", "NCR", "Ghaziabad", "Gurgaon", "Gurugram", "Faridabad"]},
        "status": "published",
    },
]


def upsert_job_catalog(admin: User | None = None) -> int:
    count = 0
    for item in JOB_CATALOG:
        job = Job.query.filter_by(public_code=item["public_code"]).first() or Job.query.filter_by(slug=item["slug"]).first()
        if not job:
            job = Job(public_code=item["public_code"], slug=item["slug"], title=item["title"], role_summary=item["role_summary"])
        for key, value in item.items():
            setattr(job, key, value)
        if admin and not job.created_by_id:
            job.created_by_id = admin.id
        if admin and not job.owner_id:
            job.owner_id = admin.id
        db.session.add(job)
        count += 1
    db.session.flush()
    return count