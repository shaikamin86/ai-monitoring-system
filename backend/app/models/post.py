from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import uuid


class Platform(str, Enum):
    twitter = "twitter"
    facebook = "facebook"
    instagram = "instagram"
    tiktok = "tiktok"
    reddit = "reddit"
    telegram = "telegram"
    news = "news"
    youtube = "youtube"
    other = "other"


class Language(str, Enum):
    ms = "ms"
    en = "en"
    mixed = "mixed"
    other = "other"


class Sentiment(str, Enum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"
    mixed = "mixed"


class PostIngest(BaseModel):
    external_id: str
    platform: Platform
    content: str
    author_id: Optional[str] = None
    author_username: Optional[str] = None
    author_display_name: Optional[str] = None
    author_followers: int = 0
    author_verified: bool = False
    url: Optional[str] = None
    likes_count: int = 0
    shares_count: int = 0
    comments_count: int = 0
    views_count: int = 0
    is_repost: bool = False
    posted_at: datetime
    metadata: Dict[str, Any] = {}


class PostResponse(BaseModel):
    id: str
    external_id: Optional[str]
    platform: Platform
    content: str
    author_username: Optional[str]
    author_display_name: Optional[str]
    author_followers: int
    author_verified: bool
    url: Optional[str]
    language: Language
    sentiment: Optional[Sentiment]
    sentiment_score: Optional[float]
    engagement_score: float
    likes_count: int
    shares_count: int
    comments_count: int
    views_count: int
    posted_at: datetime
    collected_at: datetime
    hashtags: List[str] = []
    entities: List[str] = []
    narrative_ids: List[str] = []


class PostSearchRequest(BaseModel):
    query: Optional[str] = None
    semantic_query: Optional[str] = None
    platforms: Optional[List[Platform]] = None
    languages: Optional[List[Language]] = None
    sentiments: Optional[List[Sentiment]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    hashtags: Optional[List[str]] = None
    min_engagement: Optional[float] = None
    author_username: Optional[str] = None
    limit: int = Field(default=50, le=500)
    offset: int = 0


class PostSearchResponse(BaseModel):
    posts: List[PostResponse]
    total: int
    limit: int
    offset: int
