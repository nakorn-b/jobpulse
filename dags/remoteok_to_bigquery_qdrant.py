import os

from airflow.providers.google.cloud.hooks.gcs import GCSHook
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.hooks.bigquery import BigQueryHook
from airflow.providers.google.cloud.operators.bigquery import BigQueryInsertJobOperator
from datetime import timedelta
from airflow.sdk import dag, task
from langchain_huggingface import HuggingFaceEndpointEmbeddings
import pendulum
import hashlib
from app.storage.vector_db.qdrant import QdrantService
from app.storage.bigquery import BigQueryService
from app.ingestion.adapters.remoteok_adapter import RemoteOKAdapter
from app.storage.sqlite import Database
from app.ingestion.scrapers.remoteok import RemoteOKScraper
import json
from datetime import date
import logging

default_args = {
    'owner': 'jobpulse',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}

GCS_BUCKET_NAME = f"jobpulse-data-lake-v1"


@dag(
    dag_id='airflow_to_GCS_bucket',
    default_args=default_args,
    description='Load data from RemoteOK to GCS and BigQuery',
    # schedule='0 2 * * *',
    start_date=pendulum.today('UTC').add(days=-1),
    catchup=False
)
def local_to_GCS_bucket_dag():

    @task
    def scrape_remoteOK():
        """
        Fetch jobs from remoteOK and return them
        """
        logger = logging.getLogger("airflow.task")
        logger.info("Starting RemoteOK scrape...")
        scraper = RemoteOKScraper()
        try:
            raw_jobs = scraper.scrape_jobs()
            logger.info(f"Fetched {len(raw_jobs)} raw jobs from RemoteOK")
            return raw_jobs
        except Exception as e:
            logger.error(f"Error fetching jobs: {e}")
            raise

    @task
    def transform_and_upload(raw_jobs):
        """
        Transform raw jobs and upload directly to GCS
        """
        logger = logging.getLogger("airflow.task")
        
        jobs_list = []
        success_count = 0

        for job in raw_jobs:
            try:
                standard_job = RemoteOKAdapter.transform(job)
                if standard_job is not None:
                    job_dict = standard_job.model_dump(mode='json')
                    job_dict['id'] = hashlib.sha256(standard_job.description.encode("utf-8")).hexdigest()
                    jobs_list.append(job_dict)
                    success_count += 1
            except Exception as e:
                logger.warning(f"Error processing job: {e}")
                continue
        
        # Convert list of dicts to newline-delimited JSON string
        ndjson_data = "\n".join([json.dumps(record) for record in jobs_list])
        
        upload_path = f'raw/{date.today()}/jobs.json'
        hook = GCSHook(gcp_conn_id="google_cloud_default")
        
        logger.info(f"Uploading {success_count} jobs to gs://{GCS_BUCKET_NAME}/{upload_path}")
        hook.upload(
            bucket_name=GCS_BUCKET_NAME,
            object_name=upload_path,
            data=ndjson_data,
            encoding='utf-8'
        )
        
        return upload_path

    # Execute tasks and pass data via XCom
    raw_data = scrape_remoteOK()
    upload_task = transform_and_upload(raw_data)

    load_to_staging = GCSToBigQueryOperator(
        task_id="load_to_staging",
        bucket=GCS_BUCKET_NAME,
        source_objects=[upload_task],
        destination_project_dataset_table="jobpulse-492611.jobpulse.jobs_staging",
        source_format="NEWLINE_DELIMITED_JSON", 
        write_disposition="WRITE_TRUNCATE",
        create_disposition="CREATE_IF_NEEDED",
        gcp_conn_id="google_cloud_default",
        schema_fields=[
            {"name": "id", "type": "STRING", "mode": "REQUIRED"},
            {"name": "title", "type": "STRING", "mode": "REQUIRED"},
            {"name": "company", "type": "STRING", "mode": "REQUIRED"},
            {"name": "description", "type": "STRING", "mode": "NULLABLE"},
            {"name": "url", "type": "STRING", "mode": "REQUIRED"},
            {"name": "location", "type": "STRING", "mode": "NULLABLE"},
            {"name": "posted_date", "type": "TIMESTAMP", "mode": "NULLABLE"},
            {"name": "scraped_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
            {"name": "has_embedded", "type": "BOOLEAN", "mode": "NULLABLE"},
            {"name": "embedded_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
            {"name": "category", "type": "STRING", "mode": "NULLABLE"},
        ],
    )

    # Prepare to merge with final BigQuery table
    merge_to_final = BigQueryInsertJobOperator(
        task_id="merge_to_final",
        configuration={
            "query": {
                "query": """
                    MERGE `jobpulse-492611.jobpulse.jobs` T
                    USING `jobpulse-492611.jobpulse.jobs_staging` S
                    ON T.id = S.id
                    WHEN NOT MATCHED THEN
                    INSERT (id, title, company, description, url, location, posted_date, scraped_at, has_embedded, embedded_at, category)
                    VALUES (id, title, company, description, url, location, posted_date, scraped_at, has_embedded, embedded_at, category)
                """,
                "useLegacySql": False,
            }
        },
        gcp_conn_id="google_cloud_default"
    )

    #Embed to Qdrant
    @task
    def embed_jobs():
        QDRANT_API_KEY = os.getenv('QDRANT_API_KEY')
        QDRANT_ENDPOINT = os.getenv('QDRANT_CLUSTER_ENDPOINT', 'http://qdrant:6333')
        QDRANT_LOCAL_MODE = os.getenv('QDRANT_LOCAL_MODE', 'True').lower() == 'true'
        
        qdrant_service = QdrantService(
            API_KEY=QDRANT_API_KEY, 
            url=QDRANT_ENDPOINT, 
            local=QDRANT_LOCAL_MODE
        )

        service = BigQueryService(hook=BigQueryHook(gcp_conn_id='google_cloud_default'))
        # 1. Pull data from BigQuery
        jobs = service.get_unembedded_jobs()
        if not jobs:
            return []

        job_ids = qdrant_service.add_jobs(jobs)
        
        # Return only IDs that were successfully processed
        return job_ids

    @task
    def update_job_status(success_ids):
        if not success_ids:
            return "No jobs to update"

        hook = BigQueryHook(gcp_conn_id='google_cloud_default')
        
        # SQL with UNNEST for safe list passing
        sql = f"""
            UPDATE `jobpulse-492611.jobpulse.jobs`
            SET has_embedded = True, 
                embedded_at = CURRENT_TIMESTAMP()
            WHERE id IN UNNEST({success_ids})
        """
        
        hook.get_client().query(sql).result()
        print(f"Successfully updated {len(success_ids)} jobs as embedded.")

    embedded_ids = embed_jobs()
    upload_task >> load_to_staging >> merge_to_final >> embedded_ids >> update_job_status(embedded_ids)
    
local_to_GCS_bucket_dag()