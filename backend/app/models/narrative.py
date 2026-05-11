from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum


class NarrativeStatus(str, Enum):
    emerging = "emerging"
    active = "active"
    declining = "declining"
    dormant = "dormant"


class NarrativeResponse(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    description: Optional[str] = None
    status: NarrativeStatus
    key_themes: List[str] = []
    key_hashtags: List[str] = []
    sentiment_distribution: Dict[str, int] = {}
    post_count: int = 0
    unique_authors: int = 0
    engagement_total: float = 0.0
    virality_score: float = 0.0
    threat_level: int = 0
    first_detected: Optional[datetime] = None
    last_activity: Optional[datetime] = None
    is_coordinated: bool = False
    languages: Dict[str, int] = {}
    platforms: Dict[str, int] = {}
    momentum_score: Optional[float] = None
    coordination_score: Optional[float] = None
    coordination_signals: Optional[List[str]] = None
    related_narrative_ids: Optional[List[str]] = None


class NarrativeListResponse(BaseModel):
    narratives: List[NarrativeResponse]
    total: int


class NarrativeTimelinePoint(BaseModel):
    bucket: datetime
    post_count: int = 0
    new_authors: int = 0
    engagement: float = 0.0
    sentiment_score: float = 0.0


class NarrativeDetailResponse(NarrativeResponse):
    timeline: List[NarrativeTimelinePoint]
    sample_posts: List[Dict[str, Any]]
    related_narratives: List[Dict[str, Any]]
