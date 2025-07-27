from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, ConfigDict


class WikipediaSearchResult(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)
    
    title: str = Field(..., description="Article title")
    description: str = Field(..., description="Article description or snippet")
    url: str = Field(..., description="Full URL to the Wikipedia article")


class WikipediaSearchResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    
    query: str = Field(..., description="Original search query")
    results: List[WikipediaSearchResult] = Field(default_factory=list)
    total_count: int = Field(..., ge=0, description="Total number of results found")
    language: str = Field(..., pattern=r"^[a-z]{2}$", description="Language code")


class WikipediaArticle(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, frozen=True)
    
    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Full article content")
    summary: str = Field(..., description="Article summary/introduction")
    url: str = Field(..., description="Full URL to the Wikipedia article")
    language: str = Field(..., pattern=r"^[a-z]{2}$", description="Language code")
    last_modified: Optional[str] = Field(None, description="Last modification timestamp")


class WikipediaError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code