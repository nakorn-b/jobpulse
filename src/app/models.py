from pydantic import BaseModel, Field, HttpUrl, validator
from typing import Optional, List
from datetime import datetime

class Job(BaseModel):
    title: str = Field(..., min_length=1, description="Job title")
    company: str = Field(..., min_length=1, description="Compamy name")
    description: str = Field(..., description="Job description")
    url: Optional[HttpUrl] = Field(..., description="Job posting URL")
    location: str = Field(default="Unknown", description="Job location")
    posted_date: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.now)
    has_embedded: bool = Field(default=False, description="This job has been embedded or not?")
    embedded_at: Optional[datetime] = Field(default=None)
    category: Optional[str] = Field(default=None) # New field
