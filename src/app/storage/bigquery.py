import os
from google.cloud import bigquery
import logging
from fastembed import TextEmbedding
import json
from typing import List


logger = logging.getLogger(__name__)

class BigQueryService:
    def __init__(self, hook):
        self.client = hook.get_client()

    def get_unembedded_jobs(self, save_local=False):
        try:
            logger.info("Querying BigQuery for unembedded jobs...")
            sql = "SELECT * FROM `jobpulse-492611.jobpulse.jobs` WHERE has_embedded = False"
            df = self.client.query(sql).to_dataframe()

            if save_local:
                cache_path = "jobs_cache.jsonl"
                df.to_json(cache_path, orient='records', lines=True, date_format='iso')
                logger.info(f"Saved {len(df)} jobs to {cache_path}")

            return df.to_dict('records')
        except Exception as e:
            logger.error(f"Error in BigQueryService: {e}")
            raise

    def get_category_count(self):
        logger.info("Querying job category...")
        sql = "SELECT category, COUNT(*) as count FROM `jobpulse-492611.jobpulse.jobs` GROUP BY category"
        df = self.client.query(sql).to_dataframe()
        return df

    def get_category_stats(self) -> List[dict]:
        """Fetch category counts for ECharts visualization."""
        logger.info("Fetching category stats for visualization...")
        sql = """
            SELECT category as name, COUNT(*) as value 
            FROM `jobpulse-492611.jobpulse.jobs` 
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY value DESC
        """
        df = self.client.query(sql).to_dataframe()
        return df.to_dict('records')
