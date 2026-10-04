from typing import Dict, Optional, List
from app.storage.vector_db.base import AbstractVectorDB

class EmbeddingService:
    """
    Service for sync sqlite -> vector database
    """
    def __init__(self, db, vector_db: AbstractVectorDB):
        self.sql_db = db
        self.vector_db = vector_db
        print("✅ EmbeddingService ready")
    
    def sync_embeddings(self, batch_size: Optional[int]) -> Dict:
        jobs = self.sql_db.get_jobs_without_embedding(batch_size)

        if not jobs:
            print("No jobs to embed")
            return {"success": 0, "failed": 0}

        print(f"Found {len(jobs)} jobs to embed")

        try:
            # Native vector services (ChromaService, QdrantService) expect a list of dicts
            # and return a list of successfully added IDs
            success_ids = self.vector_db.add_jobs(jobs)
            
            for job_id in success_ids:
                self.sql_db.mark_as_embedded(job_id)
            
            success_count = len(success_ids)
            failed_count = len(jobs) - success_count
            
        except Exception as e:
            print(f"❌ Error during batch sync: {e}")
            success_count = 0
            failed_count = len(jobs)

        print("\n" + "=" * 60)
        print("Sync Complete!")
        print("=" * 60)
        print(f"✅ Success: {success_count}/{len(jobs)}")
        print(f"❌ Failed: {failed_count}/{len(jobs)}")

        stats = self.sql_db.get_stats()
        vector_stats = self.vector_db.get_stats()

        print(f"\n📊 Database Status:")
        print(f"   SQLite total: {stats['total_jobs']}")
        print(f"   With embeddings: {stats['embedded_jobs']}")
        print(f"   Pending: {stats['pending_embeddings']}")
        # Handle different stat formats between Qdrant and others
        count = vector_stats.get('total_points') or vector_stats.get('total_embeddings', 0)
        print(f"   VectorDB total: {count}")
        
        return {"success": success_count, "failed": failed_count}
