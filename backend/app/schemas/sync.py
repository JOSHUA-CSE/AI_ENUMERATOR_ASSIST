from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SyncOperationItem(BaseModel):
    idempotency_key: str = Field(
        ..., description="Unique client-generated idempotency key"
    )
    operation_type: str = Field(
        ..., description="CREATE, UPDATE, STATUS_UPDATE, DELETE"
    )
    entity_type: str = Field(
        ..., description="HOUSEHOLD, REVISIT, GPS_LOG, BUILDING_STATUS"
    )
    local_entity_id: str = Field(..., description="Local client ID of the entity")
    server_entity_id: UUID | None = Field(
        default=None, description="Server UUID if entity already exists"
    )
    client_timestamp: datetime = Field(..., description="Client device timestamp")
    version: int | None = Field(
        default=1, description="Client record version for conflict detection"
    )
    payload: dict[str, Any] = Field(
        ..., description="Structured payload for the entity"
    )

    model_config = ConfigDict(from_attributes=True)


class SyncBatchRequest(BaseModel):
    device_id: str | None = Field(
        default=None, description="Optional device identifier"
    )
    operations: list[SyncOperationItem] = Field(
        ..., description="List of sync operations in the batch"
    )


class SyncOperationResultItem(BaseModel):
    idempotency_key: str
    status: str = Field(..., description="SUCCESS, FAILED, CONFLICT, QUARANTINE")
    entity_type: str
    local_entity_id: str
    server_entity_id: UUID | None = None
    version: int | None = None
    server_timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_message: str | None = None
    conflict_data: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class SyncBatchResponse(BaseModel):
    results: list[SyncOperationResultItem]
    processed_count: int
    success_count: int
    failed_count: int
    conflict_count: int
    quarantine_count: int = 0
    synced_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
