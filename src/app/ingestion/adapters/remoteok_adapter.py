from app.models import Job
from datetime import datetime
from app.ml.classification import classify_category
from app.utils import clean_text

class RemoteOKAdapter:
    @staticmethod
    def transform(raw_job: dict) -> Job:
        if not raw_job.get('position') or not raw_job.get('company'):
            return None

        raw_description = raw_job.get('description', '')
        cleaned_description = clean_text(raw_description)

        return Job(
            title=raw_job.get('position', 'Unknown Title'),
            company=raw_job.get('company') or 'Unknown',
            description=cleaned_description,
            url=raw_job.get('url') if raw_job.get('url') else None,
            location=raw_job.get('location') or 'Unknown',
            posted_date=raw_job.get('date'),
            scraped_at=datetime.now(),
            category=classify_category(raw_job.get('position'), cleaned_description)
        )