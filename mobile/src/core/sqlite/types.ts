export type BuildingStatus =
  | 'PENDING'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'LOCKED'
  | 'REVISIT_REQUIRED';

export type BuildingFieldStatus =
  | 'UNVERIFIED'
  | 'CONFIRMED'
  | 'FALSE_DETECTION'
  | 'FIELD_ADDED';

export type CensusHouseListingState =
  | 'NOT_VISITED'
  | 'LISTED'
  | 'VACANT'
  | 'NON_RESIDENTIAL'
  | 'LOCKED';

export type CensusHouseUseCode =
  | 'RESIDENTIAL'
  | 'RESIDENTIAL_CUM_COMMERCIAL'
  | 'COMMERCIAL'
  | 'WORKSHOP_FACTORY'
  | 'PLACE_OF_WORSHIP'
  | 'INSTITUTIONAL'
  | 'VACANT'
  | 'OTHER';

export type HouseholdStatus = 'DRAFT' | 'COMPLETED';

export type HouseholdReviewState =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'SUPERVISOR_VERIFIED'
  | 'ACCEPTED'
  | 'RETURNED_FOR_CORRECTION';

export type PersonReviewState =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'SUPERVISOR_VERIFIED'
  | 'ACCEPTED';

export type BuildingEditType = 'ADD' | 'DELETE' | 'MERGE' | 'MOVE' | 'RENUMBER';

export type BuildingEditReviewStatus = 'PENDING' | 'APPROVED' | 'REJECTED';

export type OwnershipStatus = 'OWNED' | 'RENTED' | 'OTHER';

export type RevisitReason =
  | 'NO_ONE_AVAILABLE'
  | 'LOCKED'
  | 'NEEDS_ADDITIONAL_INFO'
  | 'REFUSAL'
  | 'OTHER';

export type RevisitStatus = 'PENDING' | 'RESOLVED' | 'CANCELLED';

export type SyncOperationType = 'CREATE' | 'UPDATE' | 'STATUS_UPDATE' | 'DELETE';

export type SyncEntityType =
  | 'BUILDING'
  | 'CENSUS_HOUSE'
  | 'HOUSEHOLD'
  | 'PERSON'
  | 'BUILDING_EDIT'
  | 'REVISIT'
  | 'GPS_LOG'
  | 'GPS_TRACK'
  | 'BOUNDARY_EVENT'
  | 'BUILDING_STATUS'
  | 'CHANGE_REQUEST'
  | 'REVIEW_UPDATE';

export type SyncQueueStatus = 'PENDING' | 'SYNCING' | 'SYNCED' | 'FAILED' | 'CONFLICT';

export interface OfflineHlbRecord {
  id: string; // HLB UUID
  layout_id: string;
  layout_name: string | null;
  area_name: string | null;
  block_code: string;
  name: string | null;
  status: string;
  target_building_count: number;
  actual_building_count: number;
  boundary_geojson: string; // JSON stringified GeoJSON
  downloaded_at: string; // ISO string
  enumerator_id: string; // Authenticated user ID
}

export interface OfflineBuildingRecord {
  id: string; // House UUID
  hlb_id: string;
  building_reference: string;
  house_number: string | null;
  latitude: number;
  longitude: number;
  footprint_geojson: string | null; // JSON stringified GeoJSON or null
  source_type: string | null;
  field_status?: BuildingFieldStatus;
  listing_closed?: boolean;
  listing_closed_at?: string | null;
  status: BuildingStatus;
  household_count: number;
  census_house_count?: number;
  last_updated_at: string;
}

export interface OfflineCensusHouseRecord {
  id: string; // Local UUID
  server_id?: string | null; // Server UUID once synced
  building_id: string;
  hlb_id: string;
  census_house_number: string;
  use_code: CensusHouseUseCode;
  listing_state: CensusHouseListingState;
  latitude?: number | null;
  longitude?: number | null;
  geotag_accuracy_m?: number | null;
  visited_at?: string | null;
  locked_attempts: number;
  notes?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OfflinePersonRecord {
  id: string; // Local UUID
  server_id?: string | null;
  household_id: string;
  person_number: number;
  name: string;
  relationship_to_head: string;
  sex: string;
  age?: number | null;
  date_of_birth?: string | null;
  marital_status?: string | null;
  answers_json?: string | null;
  questionnaire_version: string;
  review_state: PersonReviewState;
  created_at: string;
  updated_at: string;
}

export interface OfflineBuildingEditRecord {
  id: string;
  hlb_id: string;
  building_id?: string | null;
  edit_type: BuildingEditType;
  proposed_changes_json: string;
  reason: string;
  review_status: BuildingEditReviewStatus;
  created_at: string;
}

export interface OfflineHouseholdRecord {
  id: string; // Local UUID
  server_id?: string | null; // Canonical Server UUID once synced
  building_id: string;
  census_house_id?: string | null; // Linked census house
  hlb_id: string;
  enumerator_id: string;
  household_number: string;
  head_name: string;
  total_members: number;
  male_count: number;
  female_count: number;
  transgender_count: number;
  ownership_status: OwnershipStatus;
  drinking_water_source: string | null;
  lighting_source: string | null;
  latrine_facility: string | null;
  data_json: string | null;
  questionnaire_version?: string;
  status: HouseholdStatus;
  review_state?: HouseholdReviewState;
  rejection_reason?: string | null;
  supervisor_comment?: string | null;
  source: string;
  version?: number;
  sync_status?: SyncQueueStatus;
  created_at: string;
  updated_at: string;
}

export interface OfflineRevisitRecord {
  id: string; // UUID
  building_id: string;
  hlb_id: string;
  enumerator_id: string;
  reason: RevisitReason;
  notes: string | null;
  status: RevisitStatus;
  created_at: string;
  resolved_at: string | null;
}

export interface OfflineGpsLogRecord {
  id: string;
  hlb_id: string;
  building_id: string | null;
  enumerator_id: string;
  latitude: number;
  longitude: number;
  accuracy: number | null;
  timestamp: string;
}

export interface SyncQueueItem {
  id: string; // Queue Item UUID
  idempotency_key: string; // Unique idempotency key sent to server
  entity_type: SyncEntityType;
  local_entity_id: string;
  server_entity_id: string | null;
  operation_type: SyncOperationType;
  payload_json: string; // Serialized JSON payload
  status: SyncQueueStatus;
  attempt_count: number;
  last_attempt_at: string | null;
  last_error: string | null;
  created_at: string;
  synced_at: string | null;
}

export interface SyncQueueStats {
  pendingCount: number;
  syncingCount: number;
  syncedCount: number;
  failedCount: number;
  conflictCount: number;
  totalCount: number;
  lastSyncedAt: string | null;
}

export interface FieldworkStats {
  total_buildings: number;
  completed_buildings: number;
  pending_buildings: number;
  in_progress_buildings: number;
  revisit_buildings: number;
  locked_buildings: number;
  total_households: number;
  completed_households: number;
  draft_households: number;
}

export interface RouteBuildingDetail {
  sequence_order: number;
  building_id: string;
  building_reference: string;
  house_number: string | null;
  latitude: number;
  longitude: number;
  distance_from_previous_m: number;
  status?: BuildingStatus;
}

export interface OfflineRouteRecord {
  id: string; // Route UUID
  hlb_id: string; // HLB UUID
  enumerator_id: string;
  strategy: string; // CURRENT_GPS, HLB_CENTROID, FIRST_BUILDING, NONE
  start_lat: number | null;
  start_lon: number | null;
  total_distance_km: number;
  baseline_distance_km: number;
  building_count: number;
  ordered_buildings_json: string; // Serialized JSON array of RouteBuildingDetail
  generated_at: string;
}

export interface OptimizedRouteData {
  id: string;
  hlb_id: string;
  block_code?: string;
  enumerator_id: string;
  strategy: string;
  start_lat: number | null;
  start_lon: number | null;
  total_distance_km: number;
  baseline_distance_km: number;
  distance_saved_km: number;
  improvement_percentage: number;
  building_count: number;
  ordered_buildings: RouteBuildingDetail[];
  generated_at: string;
  routing_method?: string;
  return_to_start?: boolean;
  warning?: string | null;
  version?: number;
  unroutable_count?: number;
  orderedBuildings: RouteBuildingDetail[];
  totalDistanceKm: number;
  baselineDistanceKm: number;
  distanceSavedKm: number;
}

// --- Phase 8 Road-Network-Based Field Navigation Types ---

export type RoadSurveyStatus =
  | 'NOT_VISITED'
  | 'IN_PROGRESS'
  | 'SURVEYED'
  | 'NEEDS_REVISIT';

export interface RoadSegmentData {
  segment_id: string;
  osm_way_id?: number | null;
  osm_node_ids?: number[];
  coordinates: [number, number][]; // [[lat, lon], ...]
  length_m: number;
  highway: string;
  name?: string | null;
  foot?: string | null;
  access?: string | null;
  surface?: string | null;
  is_surveyed: boolean;
  survey_status?: RoadSurveyStatus;
  surveyed_length_m?: number;
  coverage_percentage?: number;
  walking_speed_factor?: number;
}

export interface RouteSectionData {
  section_index: number;
  is_primary: boolean;
  segment_count: number;
  total_distance_km: number;
  estimated_walking_time_minutes: number;
  ordered_coordinates: [number, number][];
  traversed_segment_ids: string[];
  is_disconnected: boolean;
  disconnection_distance_m: number;
  disconnection_note: string | null;
}

export interface RoadCoverageNavigationData {
  route_id: string;
  hlb_id: string;
  network_version: string;
  acquisition_date: string;
  total_distance_km: number;
  estimated_walking_time_minutes: number;
  total_segments_count: number;
  surveyed_segments_count: number;
  coverage_percentage: number;
  sections: RouteSectionData[];
  continuous_polyline: [number, number][];
  all_road_segments: RoadSegmentData[];
  disconnected_components_count: number;
  warnings: string[];
  generated_at: string;
  building_count: number;
  ordered_buildings: any[];
}


export interface RppRouteStepData {
  step_index: number;
  section_index: number;
  edge_id: string;
  osm_way_id?: number | null;
  highway_type: string;
  road_name?: string | null;
  is_transit: boolean;
  is_deadhead: boolean;
  from_node: [number, number];
  to_node: [number, number];
  length_m: number;
  walking_time_minutes: number;
  cumulative_distance_m: number;
  cumulative_walking_time_minutes: number;
  coordinates: [number, number][];
  nearby_building_ids: string[];
}

export interface BuildingEncounterData {
  building_id: string;
  building_reference: string;
  latitude: number;
  longitude: number;
  matched_edge_id: string;
  distance_along_edge_m: number;
  traversal_step_index: number;
  encounter_order: number;
}

export interface OfflineMissingPath {
  id: string;
  hlb_id: string;
  enumerator_id: string;
  coordinates: [number, number][];
  highway_type: string;
  road_name?: string | null;
  notes?: string | null;
  status: 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED';
  submitted_at: string;
}

export interface OfflineRppPackage {
  hlb_id: string;
  graph_version: string;
  route_version: number;
  source: string;
  license: string;
  acquisition_date: string;
  boundary_geojson: any;
  nodes: any[];
  edges: RoadSegmentData[];
  required_edge_ids: string[];
  planned_route: RoadCoverageNavigationData;
  building_markers: any[];
  building_encounter_order: BuildingEncounterData[];
  coverage_status: any[];
  tile_source: any;
}
