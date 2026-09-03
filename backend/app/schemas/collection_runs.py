from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


RunStatus = Literal[
    "queued",
    "running",
    "paused",
    "waiting_user",
    "completed",
    "completed_partial",
    "stopped",
    "failed",
]
RegionTaskStatus = Literal[
    "queued",
    "running",
    "waiting_user",
    "completed",
    "failed",
    "skipped",
]


class CreateCollectionRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: Literal["jd"] = "jd"


class CollectionRunView(BaseModel):
    id: int
    search_session_id: int
    platform: Literal["jd"]
    status: RunStatus
    stage: str
    candidate_source: str
    candidate_count: int
    selected_candidate_count: int
    total_region_count: int = Field(default=31)
    completed_region_count: int
    failed_region_count: int
    skipped_region_count: int
    current_region_code: str | None
    pause_requested: bool
    stop_requested: bool
    last_error_code: str | None
    last_error_summary: str | None
    started_at: datetime | None
    updated_at: datetime
    finished_at: datetime | None


class CollectionRegionTaskView(BaseModel):
    id: int
    collection_run_id: int
    region_code: str
    province: str
    city: str
    district: str
    street: str
    sequence: int
    status: RegionTaskStatus
    attempts: int
    verified_candidate_count: int
    accepted_offer_count: int
    error_code: str | None
    error_summary: str | None
    started_at: datetime | None
    finished_at: datetime | None


class AutomationEnvironmentView(BaseModel):
    agent_reach_available: bool
    opencli_available: bool
    browser_bridge_ready: bool
    plugin_ready: bool
    safe_message: str
