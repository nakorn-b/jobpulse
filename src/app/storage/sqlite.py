import sqlite3
from app.models import Job
from datetime import datetime
from typing import List
import os
import hashlib

class Database:
    def __init__(self, db_path='/opt/airflow/data/jobpulse.db'):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()


    def create_tables(self):
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                description TEXT,
                url TEXT UNIQUE NOT NULL,
                location TEXT,
                posted_date TEXT,
                scraped_at TEXT NOT NULL,
                has_embedded BOOLEAN DEFAULT FALSE,
                embedded_at TEXT,
                category TEXT
            )
        ''')
        

        self.conn.commit()

    def insert_job(self, job: Job):
        job_id = hashlib.sha256(job.description.encode("utf-8")).hexdigest()
        cursor = self.conn.execute(
            '''
            INSERT OR IGNORE INTO jobs
            (id, title, company, description, url, location, posted_date, scraped_at, category)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', 
            (   
                job_id,
                job.title,
                job.company,
                job.description,
                str(job.url),
                job.location,
                job.posted_date.isoformat() if job.posted_date else None,
                job.scraped_at.isoformat(),
                job.category
            )
        )
        self.conn.commit()
        return cursor.rowcount == 1

    def insert_jobs_bulk(self, jobs: List[Job]):
        job_tuple = []
    
        for job in jobs:
            job_id = f"{job.company}_{hash(str(job.url))}"
            job_tuple.append(
                (
                    job_id,
                    job.title,
                    job.company,
                    job.description,
                    str(job.url),
                    job.location,
                    job.posted_date.isoformat() if job.posted_date else None,
                    job.scraped_at.isoformat()
                )
            )

        self.conn.executemany(
            '''
            INSERT OR IGNORE INTO jobs
            (id, title, company, description, url, location, posted_date, scraped_at)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ''', 
            job_tuple
        )
        self.conn.commit()

    def get_all_jobs(self):
        cursor = self.conn.execute("SELECT * FROM jobs ORDER BY scraped_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    
    def get_data_count(self):
        cursor = self.conn.execute("SELECT COUNT(*) FROM jobs")
        return cursor.fetchone()[0]
    
    def mark_as_embedded(self, job_id) -> bool:
        try:
            self.conn.execute(
                '''
                UPDATE jobs
                SET has_embedded = TRUE,
                embedded_at = ?
                WHERE id = ?
                ''',
                (datetime.now().isoformat(), job_id)
            )

            self.conn.commit()
            return True
        except Exception as e:
            print(f"Error marking job as embedded: {e}")
            return False
        
    def get_jobs_without_embedding(self, limit=50):
        if limit is not None:
            cursor = self.conn.execute(
                '''
                SELECT * FROM jobs
                WHERE has_embedded = FALSE
                LIMIT ?
                ''',
                (limit,)
            )
        else:
            cursor = self.conn.execute(
                '''
                SELECT * FROM jobs
                WHERE has_embedded = FALSE
                ''',
            )
        return [dict(row) for row in cursor.fetchall()]
    
    def get_stats(self):
        stats = {}

        cursor = self.conn.execute("SELECT COUNT(*) FROM jobs")
        stats['total_jobs'] = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE has_embedded = TRUE")
        stats['embedded_jobs'] = cursor.fetchone()[0]

        cursor = self.conn.execute("SELECT COUNT(*) FROM jobs WHERE has_embedded = False")
        stats['pending_embeddings'] = cursor.fetchone()[0]

        return stats

    def close(self):
        if self.conn:
            self.conn.close()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path, timeout=10)  # Add timeout
        self.conn.row_factory = sqlite3.Row
        self.create_tables()

