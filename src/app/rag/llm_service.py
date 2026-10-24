import os

import httpx
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate

from .retrieval_strategy import RetrievalStrategy

load_dotenv()

MAX_CHARS_PER_DOC = 5000
# Give up on the LLM after this long so /chat returns an error instead of hanging
LLM_TIMEOUT_SECONDS = 120
LLM_CONTEXT_TOKENS = 16384


class Model:
    def __init__(self) -> None:
        pass

def format_docs(docs):
    formatted = []
    for doc in docs:
        title    = doc.get('title', 'N/A')
        company  = doc.get('company', 'N/A')
        location = doc.get('location', 'N/A')
        url = doc.get('url', 'N/A')
        # Truncate long descriptions so the total prompt stays within token limits
        content  = doc.get('description', '')[:MAX_CHARS_PER_DOC]
        if len(doc.get('description', '')) > MAX_CHARS_PER_DOC:
            content += "..."
        formatted.append(f"{title} at {company}, {location}: {content}. Source: {url}")
    return "\n\n".join(formatted)

class LLMService:
    def __init__(self, vector_db, strategy: RetrievalStrategy):
        self.ollama_url = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434").rstrip("/")
        self.model_id = os.getenv("OLLAMA_CHAT_MODEL", "qwen3.5:4b")
        self.vector_db = vector_db
        # self.client = # Future work
        self.strategy = strategy        
        self.prompt = PromptTemplate.from_template("""You are a friendly and helpful job search assistant.

Your goal is to help the user find the best job matches based on the provided context. 

Start your response with a brief, friendly introduction about what you found (or didn't find).

For each relevant job found, provide a concise summary using the following format:

1. **[Job Title]** at **[Company]**
   - **Location**: [Location]
   - **Salary**: [Salary or "Not specified"]
   - **Summary**: [A 3-4 sentence summary of key responsibilities and requirements]
   - **Link**: [URL Source]

Separate each job with a numbered label (1., 2., 3., etc.).

After the list, provide a brief, encouraging closing statement.

If there is no relevant context or job given to you, say something friendly like "I couldn't find any exact matches for that right now, but I'll keep an eye out as more jobs are posted!"

---
CONTEXT:
{context}
---

Answer the question based on the above context: {question}
""")       

    def set_strategy(self, strategy: RetrievalStrategy):
        """Setter function for retrievel strategy"""
        self.strategy = strategy

    def retrieve(self, question: str, k: int = 5) -> list[dict]:
        """Return the job chunks most relevant to the question. Raises on failure."""
        return self.strategy.retrieve(question, self.vector_db, k=k)

    def generate(self, question: str, docs: list[dict]) -> str:
        """Answer the question using only the given docs as context. Raises on failure."""
        context = format_docs(docs=docs)
        prompt = self.prompt.format(context=context, question=question)

        # Non-streaming: Ollama sends nothing until the answer is complete, so the read timeout
        # caps total generation time
        response = httpx.post(
            url=f"{self.ollama_url}/api/chat",
            json={
                "model": self.model_id,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                # Qwen3.5 thinks before answering by default; skip it for faster replies
                "think": False,
                # Ollama's default context is too small for 5 job descriptions and silently
                # drops the start of the prompt (the instructions) when it overflows
                "options": {"num_ctx": LLM_CONTEXT_TOKENS},
            },
            timeout=LLM_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()['message']['content']

    def chat(self, question: str) -> dict:
        """Answer the question and return the retrieved jobs it was based on.

        Returns {"response": str, "job_list": list[dict]}. Raises on failure.
        """
        docs = self.retrieve(question)
        return {
            "response": self.generate(question, docs),
            "job_list": docs,
        }

    def get_data_count(self):
        return self.vector_db.get_data_count()