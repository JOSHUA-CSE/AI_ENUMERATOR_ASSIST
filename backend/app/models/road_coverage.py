import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class RoadSegmentSurveyStatus(enum.StrEnum):
    NOT_VISITED = "NOT_VISITED"
    IN_PROGRESS = "IN_PROGRESS"
    SURVEYED = "SURVEYED"
    NEEDS_REVISIT = "NEEDS_REVISIT"


class RoadCoverageSyncStatus(enum.StrEnum):
    PENDING = "PENDING"
    SYNCED = "SYNCED"


class MissingPathStatus(enum.StrEnum):
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class RoadGraph(Base):
    """
    Authoritative base pedestrian and road network graph for an administrative area.
    Acquired from OpenStreetMap or approved surveyor data.
    """

    __tablename__ = "road_graphs"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    area_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("administrative_areas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source = Column(String, nullable=False, default="OpenStreetMap")
    license = Column(String, nullable=False, default="ODbL")
    network_version = Column(String, nullable=False, default="v1.0")
    acquisition_date = Column(String, nullable=False, default="2026-11-11T09:42:04Z")
    node_count = Column(Integer, nullable=False, default=0)
    edge_count = Column(Integer, nullable=False, default=0)
    total_length_m = Column(Float, nullable=False, default=0.0)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    nodes = relationship("RoadNode", back_populates="graph", cascade="all, delete-orphan")
    edges = relationship("RoadEdge", back_populates="graph", cascade="all, delete-orphan")


class RoadNode(Base):
    """
    Node in the base road network graph.
    """

    __tablename__ = "road_nodes"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("road_graphs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    node_identifier = Column(String, nullable=False, index=True)
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    degree = Column(Integer, nullable=False, default=0)
    is_intersection = Column(Boolean, nullable=False, default=False)

    graph = relationship("RoadGraph", back_populates="nodes")


class RoadEdge(Base):
    """
    Edge in the base road network graph representing a walkable road or pathway segment.
    """

    __tablename__ = "road_edges"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    graph_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("road_graphs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_identifier = Column(String, nullable=False, index=True)
    osm_way_id = Column(String, nullable=True, index=True)
    start_node_id = Column(String, nullable=False)
    end_node_id = Column(String, nullable=False)
    highway_type = Column(String, nullable=False, default="residential")
    road_name = Column(String, nullable=True)
    surface = Column(String, nullable=True)
    foot = Column(String, nullable=True)
    access = Column(String, nullable=True)
    length_m = Column(Float, nullable=False, default=0.0)
    walking_cost = Column(Float, nullable=False, default=0.0)
    is_walkable = Column(Boolean, nullable=False, default=True)
    coordinates = Column(JSON, nullable=False)  # [[lat, lon], ...]

    graph = relationship("RoadGraph", back_populates="edges")


class HlbRequiredEdge(Base):
    """
    Every eligible walkable road/pathway edge inside an HLB boundary.
    All internal road edges inside the HLB are classified as REQUIRED for census coverage,
    independent of whether building footprints exist along that road.
    """

    __tablename__ = "hlb_required_edges"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    edge_id = Column(String, nullable=False, index=True)
    source_way_id = Column(String, nullable=True, index=True)
    start_node_id = Column(String, nullable=False)
    end_node_id = Column(String, nullable=False)
    coordinates = Column(JSON, nullable=False)  # [[lat, lon], ...]
    length_m = Column(Float, nullable=False, default=0.0)
    walking_cost = Column(Float, nullable=False, default=0.0)  # Walking time in minutes
    highway_type = Column(String, nullable=False, default="residential")
    pedestrian_access = Column(String, nullable=True)
    road_surface = Column(String, nullable=True)
    boundary_classification = Column(String, nullable=False, default="INTERNAL")  # INTERNAL, EXTERNAL_TRANSIT
    required_status = Column(String, nullable=False, default="REQUIRED")  # REQUIRED, TRANSIT
    coverage_status = Column(
        Enum(RoadSegmentSurveyStatus, name="road_segment_survey_status_enum"),
        nullable=False,
        default=RoadSegmentSurveyStatus.NOT_VISITED,
        index=True,
    )
    graph_version = Column(String, nullable=False, default="v1.0")
    source = Column(String, nullable=False, default="OpenStreetMap")
    acquired_at = Column(String, nullable=False, default="2026-11-11T09:42:04Z")

    # Major road two-sided enumeration flags
    requires_two_sided = Column(Boolean, nullable=False, default=False)
    left_surveyed = Column(Boolean, nullable=False, default=False)
    right_surveyed = Column(Boolean, nullable=False, default=False)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("hlb_id", "edge_id", name="uq_hlb_required_edge"),
    )


class HlbRoutePlan(Base):
    """
    Persisted Rural Postman Problem (RPP) full-road-coverage route plan for an HLB.
    Contains overall metrics, deadheading distance, and versioning.
    """

    __tablename__ = "hlb_route_plans"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_version = Column(Integer, nullable=False, default=1)
    graph_version = Column(String, nullable=False, default="v1.0")
    status = Column(String, nullable=False, default="ACTIVE")  # ACTIVE, SUPERSEDED

    total_distance_km = Column(Float, nullable=False, default=0.0)
    estimated_walking_time_minutes = Column(Float, nullable=False, default=0.0)
    total_required_edges_count = Column(Integer, nullable=False, default=0)
    surveyed_edges_count = Column(Integer, nullable=False, default=0)
    coverage_percentage = Column(Float, nullable=False, default=0.0)
    deadhead_distance_km = Column(Float, nullable=False, default=0.0)
    deadhead_percentage = Column(Float, nullable=False, default=0.0)
    disconnected_components_count = Column(Integer, nullable=False, default=1)
    external_transit_count = Column(Integer, nullable=False, default=0)

    start_lat = Column(Float, nullable=True)
    start_lon = Column(Float, nullable=True)
    end_lat = Column(Float, nullable=True)
    end_lon = Column(Float, nullable=True)

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    traversals = relationship(
        "HlbRouteTraversal",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="HlbRouteTraversal.step_index",
    )


class HlbRouteTraversal(Base):
    """
    Individual step in the planned Eulerian / RPP edge traversal sequence.
    """

    __tablename__ = "hlb_route_traversals"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("hlb_route_plans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_index = Column(Integer, nullable=False, index=True)
    section_index = Column(Integer, nullable=False, default=1)
    edge_id = Column(String, nullable=False, index=True)
    is_transit = Column(Boolean, nullable=False, default=False)
    is_deadhead = Column(Boolean, nullable=False, default=False)
    from_node = Column(String, nullable=True)
    to_node = Column(String, nullable=True)
    direction_forward = Column(Boolean, nullable=False, default=True)
    cumulative_distance_m = Column(Float, nullable=False, default=0.0)
    cumulative_walking_time_minutes = Column(Float, nullable=False, default=0.0)
    coordinates = Column(JSON, nullable=False)  # Line coordinates for this traversal step

    plan = relationship("HlbRoutePlan", back_populates="traversals")


class MissingPathSubmission(Base):
    """
    Enumerator report for an unmapped or newly discovered road or pedestrian pathway.
    Submitted from the field with GPS track or drawn coordinates; pending supervisor review.
    """

    __tablename__ = "missing_path_submissions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    coordinates = Column(JSON, nullable=False)  # [[lat, lon], ...]
    highway_type = Column(String, nullable=False, default="path")
    road_name = Column(String, nullable=True)
    notes = Column(Text, nullable=True)

    status = Column(
        Enum(MissingPathStatus, name="missing_path_status_enum"),
        nullable=False,
        default=MissingPathStatus.PENDING_REVIEW,
        index=True,
    )

    reviewed_by = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)

    submitted_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )


class RoadSegmentCoverage(Base):
    """
    Tracks ground survey coverage for a specific road/pathway segment within an HLB.
    Coverage is computed from GPS traces and spatial matching, independent of building enumeration.
    """

    __tablename__ = "road_segment_coverages"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    segment_id = Column(String, nullable=False, index=True)
    osm_way_id = Column(String, nullable=True, index=True)
    highway_type = Column(String, nullable=True)
    road_name = Column(String, nullable=True)

    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_id = Column(String, nullable=True)

    survey_status = Column(
        Enum(RoadSegmentSurveyStatus, name="road_segment_survey_status_enum"),
        nullable=False,
        default=RoadSegmentSurveyStatus.NOT_VISITED,
        index=True,
    )

    total_length_m = Column(Float, nullable=False, default=0.0)
    surveyed_length_m = Column(Float, nullable=False, default=0.0)
    coverage_percentage = Column(Float, nullable=False, default=0.0)

    # GPS trace matched to this segment: list of [lat, lon, timestamp] points
    gps_trace = Column(JSON, nullable=True)

    # Segment geometry: GeoJSON LineString coordinates [[lat, lon], ...]
    segment_geometry = Column(JSON, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    sync_status = Column(
        Enum(RoadCoverageSyncStatus, name="road_coverage_sync_status_enum"),
        nullable=False,
        default=RoadCoverageSyncStatus.SYNCED,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("hlb_id", "segment_id", name="uq_hlb_segment_coverage"),
    )


# Alias for domain naming consistency
RoadEdgeCoverage = RoadSegmentCoverage


class BoundaryEventType(enum.StrEnum):
    EXIT = "EXIT"
    ENTRY = "ENTRY"
    ACCURACY_WARNING = "ACCURACY_WARNING"


class HlbBoundaryEvent(Base):
    """
    Audit log of enumerator boundary transitions (exit, re-entry) and geofence alerts.
    """

    __tablename__ = "hlb_boundary_events"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hlb_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("houselisting_blocks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    enumerator_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(
        String,
        nullable=False,
        default="EXIT",
        index=True,
    )
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_meters = Column(Float, nullable=True)
    distance_to_boundary_meters = Column(Float, nullable=True)
    boundary_status = Column(String, nullable=False, default="OUTSIDE")
    device_id = Column(String, nullable=True)
    timestamp = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    supervisor_notified = Column(Boolean, nullable=False, default=False)
    notification_details = Column(JSON, nullable=True)
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    hlb = relationship("HouselistingBlock", backref="boundary_events")
    enumerator = relationship("User", foreign_keys=[enumerator_id])

