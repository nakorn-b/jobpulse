import os
import pendulum
import json
from datetime import datetime, timedelta

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

from airflow.decorators import dag, task
from app.ingestion.scrapers.remoteok import RemoteOKScraper
from app.ingestion.adapters.remoteok_adapter import RemoteOKAdapter
from app.storage.sqlite import Database
from app.ml.embedding import EmbeddingService
from app.storage.vector_db import ChromaService

default_args = {
    'owner': 'jobpulse',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

TEST_DATABASE = '/opt/airflow/data/jobpulse-with-category.db'

@dag(
    dag_id='daily_job_scraper',
    default_args=default_args,
    description='Scrape jobs from RemoteOK daily',
    schedule='0 2 * * *',
    start_date=pendulum.today('UTC').add(days=-2),
    catchup=True
)
def daily_job_scraper_dag():

    @task()
    def scrape_remoteOK():
        """
        Fetch and store jobs from remoteOK
        """
        print("Starting RemoteOK scrape...")
        scraper = RemoteOKScraper()
        raw_jobs = scraper.scrape_jobs()

        print(f"Fetched {len(raw_jobs)} raw jobs from RemoteOK")

        db = Database(TEST_DATABASE)
        success_count = 0

        for job in raw_jobs:
            try:
                standard_job = RemoteOKAdapter.transform(job)
                if standard_job is None:
                    continue

                if db.insert_job(standard_job):
                    success_count += 1
            except Exception as e:
                print(f"Error processing job:", e)
                continue

        print(f"Successfully stored {success_count}/{len(raw_jobs)} RemoteOK jobs")

        # Export ALL jobs from SQLite to jobs.json for Streamlit seeding
        try:
            root_json_path = os.path.join(project_root, 'jobs-with-category.json')
            print(f"Exporting to: {root_json_path}")

            # Get all jobs from database (returns list of dicts)
            all_jobs = db.get_all_jobs()
            print(f"Total jobs in SQLite: {len(all_jobs)}")

            # Convert datetime objects to ISO format strings for JSON serialization
            for job in all_jobs:
                if job.get('posted_date') and hasattr(job['posted_date'], 'isoformat'):
                    job['posted_date'] = job['posted_date'].isoformat()
                if job.get('scraped_at') and hasattr(job['scraped_at'], 'isoformat'):
                    job['scraped_at'] = job['scraped_at'].isoformat()
                if job.get('embedded_at') and hasattr(job['embedded_at'], 'isoformat'):
                    job['embedded_at'] = job['embedded_at'].isoformat()

            with open(root_json_path, 'w') as f:
                json.dump(all_jobs, f)
            print(f"Successfully exported {len(all_jobs)} jobs to {root_json_path}")
        except Exception as e:
            import traceback
            print(f"JSON export failed: {e}")
            traceback.print_exc()

        return success_count

    @task()
    def sync_embedding():
        db = Database(TEST_DATABASE)
        vector_db = ChromaService()
        service = EmbeddingService(db, vector_db)

        result = service.sync_embeddings(batch_size=None)

        return result

    @task()
    def summary():
        sql_db = Database()
        embed_result = sql_db.get_stats()
        summary_text = f"""
        ====================================
        JobPulse Daily Run Summary
        ====================================
        Database Status:
           Total Jobs: {embed_result.get('total_jobs', 0)}
           With Embeddings: {embed_result.get('embedded_jobs', 0)}
           Pending: {embed_result.get('pending_embeddings', 0)}
        """
        print(summary_text)
        return summary_text

    # Set dependencies
    scrape_remoteOK() >> sync_embedding() >> summary()

# Instantiate the DAG
daily_job_scraper_dag()