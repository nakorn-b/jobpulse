from abc import ABC, abstractmethod
from typing import List, Dict, Any

class AbstractVectorDB(ABC):
    @abstractmethod
    def create_embeddings(self, jobs: List[Dict[str, Any]]) -> List[List[float]]:
        """Convert a list of jobs (dictionaries) into their embedding vectors."""
        pass

    @abstractmethod
    def add_jobs(self, jobs: List[Dict[str, Any]]) -> List[str]:
        """Add a list of jobs (dictionaries) to the vector database (batch). Returns list of IDs."""
        pass

    @abstractmethod
    def search(self, query: str, n_results: int = 5) -> List[Dict[str, Any]]:
        """Search for jobs based on a query string."""
        pass

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Return statistics about the database."""
        pass
