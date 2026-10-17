from datetime import datetime

from pydantic import BaseModel, Field, HttpUrl


class Job(BaseModel):
    title: str = Field(..., min_length=1, description="Job title")
    company: str = Field(..., min_length=1, description="Compamy name")
    description: str = Field(..., description="Job description")
    url: HttpUrl | None = Field(..., description="Job posting URL")
    location: str = Field(default="Unknown", description="Job location")
    posted_date: datetime | None = None
    scraped_at: datetime = Field(default_factory=datetime.now)
    has_embedded: bool = Field(default=False, description="This job has been embedded or not?")
    embedded_at: datetime | None = Field(default=None)
    category: str | None = Field(default=None) # New field
