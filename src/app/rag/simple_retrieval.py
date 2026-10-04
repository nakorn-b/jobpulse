from .retrieval_strategy import RetrievalStrategy

class SimpleRetrievalStrategy(RetrievalStrategy):
    def retrieve(self, query: str, vector_db, k: int = 5):
        return vector_db.search(query, n_results=k)

    def get_name(self):
        return "Simple Vector Similarity"