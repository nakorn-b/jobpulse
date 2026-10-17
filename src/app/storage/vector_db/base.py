from abc import ABC, abstractmethod
from typing import Any


class AbstractVectorDB(ABC):
    @abstractmethod
    def create_embeddings(self, jobs: list[dict[str, Any]]) -> list[list[float]]:
        """Convert a list of jobs (dictionaries) into their embedding vectors."""

    @abstractmethod
    def add_jobs(self, jobs: list[dict[str, Any]]) -> list[str]:
        """Add a list of jobs (dictionaries) to the vector database (batch). Returns list of IDs."""

    @abstractmethod
    def search(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """Search for jobs based on a query string."""

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Return statistics about the database."""
