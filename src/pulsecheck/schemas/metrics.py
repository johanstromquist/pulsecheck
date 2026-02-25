from datetime import datetime

from pydantic import BaseModel


class MetricsBucket(BaseModel):
    timestamp: datetime
    avg_response_time_ms: float | None
    min_response_time_ms: int | None
    max_response_time_ms: int | None
    check_count: int
    healthy_count: int
    degraded_count: int
    down_count: int
    uptime_percentage: float


class UptimePeriod(BaseModel):
    period: str
    uptime_percentage: float | None
    total_checks: int
