import json
import os
from datetime import datetime
from typing import Optional, Union


from app.storage.sqlite import Database
from app.models import Job
from app.ml.embedding import EmbeddingService
from app.storage.vector_db.base import AbstractVectorDB

def seed_databases(json_path: str, db_path: str, chroma_dir: Optional[str] = None, vector_db: Optional[AbstractVectorDB] = None):
    db = Database(db_path)
    
    if vector_db is None and chroma_dir is not None:
        from dags.include.vector_db import VectorDatabase
        vector_db = VectorDatabase(chroma_dir)
    elif vector_db is None:
        raise ValueError("Either vector_db or chroma_dir must be provided")

    with open(json_path, "r") as f:
        jobs_data = json.load(f)

    print(f"Seeding {len(jobs_data)} jobs...")

    for job in jobs_data:
        # Check if job already exists to avoid duplicates in SQLite
        # Using URL or title+company as a simple check
        
        job_obj = Job(
            title=job.get('title') or job.get('position') or 'Unknown Title',
            company=job.get('company') or 'Unknown',
            description=job.get('description', ''),
            url=job.get('url', ''),
            location=job.get('location') or 'Unknown',
            posted_date=job.get('posted_date'),
            scraped_at=datetime.now()
        )
        db.insert_job(job_obj)

    sync_service = EmbeddingService(db, vector_db)
    # Sync in batches until no more jobs pending
    while True:
        stats = db.get_stats()
        if stats['pending_embeddings'] == 0:
            break
        print(f"Syncing batch... {stats['pending_embeddings']} jobs remaining")
        sync_service.sync_embeddings(batch_size=100)

    db.close()

if __name__ == "__main__":
    # Default behavior for CLI usage
    from app.storage.vector_db.qdrant import QdrantService
    
    QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
    QDRANT_ENDPOINT = os.getenv('QDRANT_CLUSTER_ENDPOINT', 'http://qdrant:6333')
    QDRANT_LOCAL_MODE = os.getenv('QDRANT_LOCAL_MODE', 'True').lower() == 'true'

    qdrant = QdrantService(QDRANT_API_KEY, QDRANT_ENDPOINT, QDRANT_LOCAL_MODE)
    seed_databases("jobs.json", "data/jobpulse.db", vector_db=qdrant)
