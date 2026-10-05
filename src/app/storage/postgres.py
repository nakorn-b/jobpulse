import os
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row

JOB_COLUMNS = (
    'id', 'title', 'company', 'description', 'url', 'location',
    'posted_date', 'scraped_at', 'has_embedded', 'embedded_at', 'category',
)


class PostgresDatabase:
    def __init__(self, dsn: Optional[str] = None):
        self.dsn = dsn or os.environ['DATABASE_URL']
        # autocommit so each `with self.conn.transaction()` block is its own committed transaction
        self.conn = psycopg.connect(self.dsn, autocommit=True, row_factory=dict_row)

    def create_tables(self):
        with self.conn.transaction():
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    description TEXT,
                    url TEXT NOT NULL,
                    location TEXT,
                    posted_date TIMESTAMPTZ,
                    scraped_at TIMESTAMPTZ NOT NULL,
                    has_embedded BOOLEAN NOT NULL DEFAULT FALSE,
                    embedded_at TIMESTAMPTZ,
                    category TEXT
                )
            ''')

    def insert_new_jobs(self, jobs: List[Dict[str, Any]]) -> List[str]:
        """
        Load today's scrape into a temp table, then insert only the rows whose id
        is not already in `jobs` (temp LEFT JOIN jobs WHERE jobs.id IS NULL).
        Returns the ids that were inserted.
        """
        if not jobs:
            return []

        columns = ', '.join(JOB_COLUMNS)
        with self.conn.transaction():
            self.conn.execute('CREATE TEMP TABLE today_jobs (LIKE jobs) ON COMMIT DROP')

            with self.conn.cursor().copy(f'COPY today_jobs ({columns}) FROM STDIN') as copy:
                for job in jobs:
                    copy.write_row([job.get(col) for col in JOB_COLUMNS])

            # DISTINCT ON guards against the same id appearing twice in one scrape
            cursor = self.conn.execute(f'''
                INSERT INTO jobs ({columns})
                SELECT DISTINCT ON (t.id) {', '.join(f't.{col}' for col in JOB_COLUMNS)}
                FROM today_jobs t
                LEFT JOIN jobs j ON j.id = t.id
                WHERE j.id IS NULL
                ORDER BY t.id
                RETURNING id
            ''')
            return [row['id'] for row in cursor.fetchall()]

    def get_jobs_without_embedding(self) -> List[Dict[str, Any]]:
        cursor = self.conn.execute('SELECT * FROM jobs WHERE has_embedded IS NOT TRUE')
        return cursor.fetchall()

    def mark_as_embedded(self, job_ids: List[str]) -> int:
        with self.conn.transaction():
            cursor = self.conn.execute(
                '''
                UPDATE jobs
                SET has_embedded = TRUE,
                    embedded_at = now()
                WHERE id = ANY(%s)
                ''',
                (job_ids,)
            )
            return cursor.rowcount

    def get_stats(self) -> Dict[str, int]:
        cursor = self.conn.execute('''
            SELECT
                COUNT(*) AS total_jobs,
                COUNT(*) FILTER (WHERE has_embedded) AS embedded_jobs,
                COUNT(*) FILTER (WHERE has_embedded IS NOT TRUE) AS pending_embeddings
            FROM jobs
        ''')
        return cursor.fetchone()

    def get_category_stats(self) -> List[Dict[str, Any]]:
        """Fetch category counts for ECharts visualization."""
        cursor = self.conn.execute('''
            SELECT category AS name, COUNT(*) AS value
            FROM jobs
            WHERE category IS NOT NULL
            GROUP BY category
            ORDER BY value DESC
        ''')
        return cursor.fetchall()

    def close(self):
        if self.conn:
            self.conn.close()
