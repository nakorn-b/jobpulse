import os
import hashlib
from typing import Any, Dict, List

from dotenv import load_dotenv
from prefect import flow, task, get_run_logger

from app.ingestion.scrapers.remoteok import RemoteOKScraper
from app.ingestion.adapters.remoteok_adapter import RemoteOKAdapter
from app.storage.postgres import PostgresDatabase
from app.storage.vector_db.qdrant import QdrantService

load_dotenv()

# Retry policy shared by every task (2 retries, 5 minutes apart)
RETRIES = 2
RETRY_DELAY_SECONDS = 300


@task(retries=RETRIES, retry_delay_seconds=RETRY_DELAY_SECONDS)
def ensure_table_exists():
    db = PostgresDatabase()
    try:
        db.create_tables()
    finally:
        db.close()


@task(retries=RETRIES, retry_delay_seconds=RETRY_DELAY_SECONDS)
def scrape_remoteOK() -> List[Dict[str, Any]]:
    """
    Fetch jobs from remoteOK and return them
    """
    logger = get_run_logger()
    logger.info("Starting RemoteOK scrape...")
    scraper = RemoteOKScraper()
    try:
        raw_jobs = scraper.scrape_jobs()
        logger.info(f"Fetched {len(raw_jobs)} raw jobs from RemoteOK")
        return raw_jobs
    except Exception as e:
        logger.error(f"Error fetching jobs: {e}")
        raise


@task(retries=RETRIES, retry_delay_seconds=RETRY_DELAY_SECONDS)
def transform_jobs(raw_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Transform raw jobs into dicts with a stable `id`
    """
    logger = get_run_logger()

    jobs_list = []
    for job in raw_jobs:
        try:
            standard_job = RemoteOKAdapter.transform(job)
            if standard_job is not None:
                job_dict = standard_job.model_dump(mode='json')

                # Use the RemoteOK API ID if available, otherwise hash
                remote_id = job.get('id')
                if remote_id:
                    job_dict['id'] = str(remote_id)
                else:
                    unique_str = f"{standard_job.title}{standard_job.company}{standard_job.description}"
                    job_dict['id'] = hashlib.sha256(unique_str.encode("utf-8")).hexdigest()

                jobs_list.append(job_dict)
        except Exception as e:
            logger.warning(f"Error processing job: {e}")
            continue

    logger.info(f"Transformed {len(jobs_list)}/{len(raw_jobs)} jobs")
    return jobs_list


@task(retries=RETRIES, retry_delay_seconds=RETRY_DELAY_SECONDS)
def load_new_jobs(jobs: List[Dict[str, Any]]) -> List[str]:
    """
    Insert only jobs not already in Postgres (temp table LEFT JOIN jobs)
    """
    logger = get_run_logger()
    db = PostgresDatabase()
    try:
        new_ids = db.insert_new_jobs(jobs)
    finally:
        db.close()

    logger.info(f"Inserted {len(new_ids)} new jobs ({len(jobs) - len(new_ids)} already existed)")
    return new_ids


@task(retries=RETRIES, retry_delay_seconds=RETRY_DELAY_SECONDS)
def fetch_unembedded_jobs() -> List[Dict[str, Any]]:
    """
    New jobs plus any earlier jobs whose embedding failed
    """
    db = PostgresDatabase()
    try:
        return db.get_jobs_without_embedding()
    finally:
        db.close()


@task(retries=RETRIES, retry_delay_seconds=RETRY_DELAY_SECONDS)
def embed_jobs(jobs: List[Dict[str, Any]]) -> List[str]:
    logger = get_run_logger()
    if not jobs:
        return []

    # Connects to QDRANT_LOCAL_HOST_URL (QdrantService default)
    qdrant_service = QdrantService(API_KEY=os.getenv('QDRANT_API_KEY'))

    # Process in smaller batches of 20 to avoid timeouts
    all_success_ids = []
    batch_size = 20
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i:i + batch_size]
        logger.info(f"Processing batch {i//batch_size + 1} ({len(batch)} jobs)...")
        batch_ids = qdrant_service.add_jobs(batch)
        all_success_ids.extend(batch_ids)

    # Return only IDs that were successfully processed
    return all_success_ids


@task(retries=RETRIES, retry_delay_seconds=RETRY_DELAY_SECONDS)
def update_job_status(success_ids: List[str]) -> int:
    logger = get_run_logger()
    if not success_ids:
        logger.info("No jobs to update")
        return 0

    db = PostgresDatabase()
    try:
        updated = db.mark_as_embedded(success_ids)
    finally:
        db.close()

    logger.info(f"Successfully updated {updated} jobs as embedded.")
    return updated


@task
def summary(new_ids: List[str], embedded_ids: List[str]) -> str:
    db = PostgresDatabase()
    try:
        stats = db.get_stats()
    finally:
        db.close()

    summary_text = f"""
    ====================================
    JobPulse Daily Run Summary
    ====================================
    This run:
       New Jobs: {len(new_ids)}
       Embedded: {len(embedded_ids)}
    Database Status:
       Total Jobs: {stats.get('total_jobs', 0)}
       With Embeddings: {stats.get('embedded_jobs', 0)}
       Pending: {stats.get('pending_embeddings', 0)}
    """
    print(summary_text)
    return summary_text


@flow(
    name='daily-job-scraper',
    description='Scrape RemoteOK, store new jobs in Postgres, and embed them into Qdrant',
    log_prints=True,
)
def daily_job_scraper():
    ensure_table_exists()
    raw_jobs = scrape_remoteOK()
    jobs = transform_jobs(raw_jobs)
    new_ids = load_new_jobs(jobs)
    unembedded = fetch_unembedded_jobs()
    embedded_ids = embed_jobs(unembedded)
    update_job_status(embedded_ids)
    return summary(new_ids, embedded_ids)


if __name__ == '__main__':
    daily_job_scraper()
