from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class AlertSeverity(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class AlertStatus(str, Enum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"
    dismissed = "dismissed"


class AlertType(str, Enum):
    narrative_spike = "narrative_spike"
    keyword_match = "keyword_match"
    influencer_activity = "influencer_activity"
    sentiment_shift = "sentiment_shift"
    viral_content = "viral_content"
    coordinated_behavior = "coordinated_behavior"
    emerging_narrative = "emerging_narrative"
    hashtag_surge = "hashtag_surge"


class AlertResponse(BaseModel):
    id: str
    title: str
    description: Optional[str]
    severity: AlertSeverity
    status: AlertStatus
    alert_type: AlertType
    source_id: Optional[str]
    source_type: Optional[str]
    trigger_data: Dict[str, Any]
    affected_platforms: List[str]
    affected_languages: List[str]
    post_count: int
    reach_estimate: int
    created_at: datetime
    acknowledged_at: Optional[datetime]
    resolved_at: Optional[datetime]
    notes: Optional[str]


class AlertUpdateRequest(BaseModel):
    status: Optional[AlertStatus] = None
    notes: Optional[str] = None
    acknowledged_by: Optional[str] = None


class AlertListResponse(BaseModel):
    alerts: List[AlertResponse]
    total: int
    active_critical: int
    active_high: int
