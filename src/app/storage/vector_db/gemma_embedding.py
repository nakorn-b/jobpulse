import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()


class GemmaEmbedding:
    """EmbeddingGemma served by Ollama (POST /api/embed)."""

    # EmbeddingGemma is trained with task prefixes; using them improves retrieval quality
    QUERY_PREFIX = "task: search result | query: "
    DOCUMENT_PREFIX = "title: none | text: "

    def __init__(
        self,
        url: str = os.getenv("OLLAMA_HOST_URL", "http://localhost:11434"),
        model: str = os.getenv("OLLAMA_EMBED_MODEL", "embeddinggemma-2:270m"),
        timeout: int = 120,
    ):
        self.logger = logging.getLogger(__name__)
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

        # Probe once: verifies Ollama is reachable, the model is pulled, and gives the vector size
        self.dimension = len(self._embed(["ping"])[0])
        self.logger.info(f"Connected to Ollama at {self.url} using {self.model} (dim={self.dimension})")

    def _embed(self, texts: list[str]) -> list[list[float]]:
        response = self.session.post(
            f"{self.url}/api/embed",
            json={"model": self.model, "input": texts},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([self.DOCUMENT_PREFIX + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self.QUERY_PREFIX + text])[0]
