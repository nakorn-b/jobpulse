import json
import os
from datetime import datetime
from dags.include.embedding_service import EmbeddingService


from dags.include.database import Database
from dags.include.vector_db import VectorDatabase
from dags.include.models import Job

def seed_databases(json_path: str, db_path: str, chroma_dir: str):
    db = Database(db_path)
    vector_db = VectorDatabase(chroma_dir)

    with open(json_path, "r") as f:
        jobs_data = json.load(f)

    for job in jobs_data:
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
    
















# def seed_databases(json_path="jobs.json", db_path="data/jobpulse.db", chroma_dir="data/chroma_db"):
#     print(f"Starting database seeding from {json_path}...")
    
#     if not os.path.exists(json_path):
#         print(f"Error: {json_path} not found.")
#         return

#     # Initialize Databases
#     db = Database(db_path=db_path)
#     vdb = VectorDatabase(persist_directory=chroma_dir)
    
#     # Check if already seeded
#     stats = db.get_stats()
#     if stats['total_jobs'] > 0:
#         print(f"Database already contains {stats['total_jobs']} jobs. Skipping seeding.")
#         return

#     with open(json_path, 'r') as f:
#         jobs_data = json.load(f)

#     count = 0
#     total = len(jobs_data)
    
#     for item in jobs_data:
#         try:
#             # Prepare data for Pydantic model
#             # Note: models.py Job expects a URL as HttpUrl or Optional[HttpUrl]
#             # jobs.json has position, company, description, url, etc.
            
#             job_obj = Job(
#                 title=item.get("position", "N/A"),
#                 company=item.get("company", "N/A"),
#                 description=item.get("description", ""),
#                 url=item.get("url"),
#                 location=item.get("location", "Remote"),
#                 posted_date=datetime.fromisoformat(item["date"].replace("Z", "+00:00")) if "date" in item else None,
#                 scraped_at=datetime.now()
#             )
            
#             # 1. Insert into SQLite
#             # Database.insert_job uses hash of description as ID
#             id_created = db.insert_job(job_obj)
            
#             # Re-fetch or re-calculate job_id to match Database.insert_job
#             import hashlib
#             job_id = hashlib.sha256(job_obj.description.encode("utf-8")).hexdigest()

#             # 2. Insert into Vector DB
#             # VectorDatabase.add_job(job_id, job_data: dict)
#             job_dict = {
#                 "title": job_obj.title,
#                 "company": job_obj.company,
#                 "description": job_obj.description,
#                 "location": job_obj.location,
#                 "url": str(job_obj.url)
#             }
#             vdb.add_job(job_id, job_dict)
            
#             # 3. Mark as embedded in SQLite
#             db.mark_as_embedded(job_id)
            
#             count += 1
#             if count % 10 == 0:
#                 print(f"Processed {count}/{total} jobs...")
                
#         except Exception as e:
#             print(f"Error processing job {item.get('id', 'unknown')}: {e}")

#     print(f"Seeding completed! Added {count} jobs.")
#     db.close()

# if __name__ == "__main__":
#     seed_databases()
