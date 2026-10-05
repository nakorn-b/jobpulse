
CATEGORY_KEYWORDS = {
    "AI/ML Engineer": ["machine learning", "deep learning", "llm", "ai", "neural", "pytorch", "tensorflow", "jax", "computer vision", "natural language processing"],
    "Data Engineer": ["pipeline", "etl", "airflow", "spark", "bigquery", "dbt", "kafka", "snowflake", "data warehouse", "sql"],
    "Data Scientist": ["statistics", "analysis", "hypothesis", "experiment", "r ", "pandas", "scipy", "modeling", "insights"],
    "Backend Engineer": ["backend", "django", "flask", "fastapi", "node.js", "golang", "elixir", "microservices", "ruby on rails", "java", "spring"],
    "Frontend/Full Stack Engineer": ["frontend", "react", "vue", "angular", "next.js", "css", "html", "typescript", "full stack", "web developer", "wordpress"],
    "DevOps/SRE": ["mlflow", "kubeflow", "model serving", "ci/cd", "deployment", "docker", "kubernetes", "terraform", "aws", "gcp", "azure", "infrastructure", "sre"],
    "Design": ["ux", "ui", "product designer", "graphic design", "figma", "brand designer"],
    "Product/Project Management": ["product manager", "program manager", "project manager", "agile", "scrum", "roadmap"],
    "Sales/Marketing": ["sales development", "account executive", "growth", "marketing", "revenue", "sdr", "lead generation"],
    "Finance/Legal": ["finance", "accounting", "payroll", "legal counsel", "compliance", "tax", "rcm"],
    "Healthcare": ["psychologist", "clinician", "nurse", "therapist", "healthcare", "clinical"],
}

def classify_category(title: str, description: str):

    title = title or ""
    description = description or ""
    text = f"{title} {description}".lower()
   
    scores = {
     category: sum(1 for kw in keywords if kw in text) 
     for category, keywords in CATEGORY_KEYWORDS.items()
     }
    
    best_match = max(scores, key=scores.get)

    return best_match if scores[best_match] > 0 else "Other"
