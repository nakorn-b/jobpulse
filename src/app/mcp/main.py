import requests
from app.api.routers.chat import get_llm_service
from app.rag import LLMService
from fastmcp import FastMCP
from fastmcp.dependencies import Depends
from fastmcp.exceptions import ToolError
from qdrant_client.http.exceptions import UnexpectedResponse

mcp = FastMCP("JobPulse MCP🚀")

@mcp.tool
def greet():
    "Call this to greet user"
    return "Hello!👋🏻"

@mcp.tool
def find_relevant_jobs(description: str, llm: LLMService = Depends(get_llm_service)) -> list[dict]:
    """Search job listings. Use when the user wants to find jobs.
    `description` is a short search query, e.g. 'remote python backend developer'."""
    try:
        return llm.retrieve(description)
    except requests.HTTPError as e:
        # Embedding the query via Ollama failed
        print(f"Status {e.response.status_code}, Embedding error: {e}")
        raise ToolError("Failed to embed the job description")
    except UnexpectedResponse as e:
        # Qdrant search failed
        print(f"Status {e.status_code}, Search error: {e}")
        raise ToolError("Failed to search jobs")
    except Exception as e:
        print(f"Search error: {e}")
        raise ToolError("Failed to retrieve jobs")

if __name__ == "__main__":
    mcp.run(transport="sse", host='0.0.0.0', port=8001)