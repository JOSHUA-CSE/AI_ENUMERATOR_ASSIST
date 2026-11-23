import { apiClient } from './apiClient';

export interface LayoutSummary {
  id: string;
  area_id: string;
  administrative_area_id: string;
  area_ids?: string[];
  area_names?: string[];
  areas_count?: number;
  supervisor_id?: string | null;
  assigned_supervisor_name?: string | null;
  name: string;
  status: 'DRAFT' | 'GENERATED' | 'REVIEW' | 'APPROVED' | 'ACTIVE' | 'COMPLETED' | string;
  boundary_status?: string;
  target_buildings_per_hlb: number;
  target_houses_per_hlb?: number;
  workload_unit?: string;
  target_workload?: number;
  estimated_census_house_count?: number | null;
  total_buildings: number;
  actual_building_count?: number;
  expected_hlb_count?: number;
  hlb_count: number;
  active_version_id?: string | null;
  active_version_number: number | null;
  active_version_status: string | null;
  boundary?: any;
  approved_by?: string | null;
  approved_at?: string | null;
  description?: string | null;
  created_at: string;
  updated_at: string;
}

export interface LayoutListResponse {
  items: LayoutSummary[];
  total: number;
}

export interface HlbCandidate {
  id: string;
  layout_id: string;
  layout_version_id?: string;
  version_id?: string;
  block_code: string;
  hlb_code: string;
  name?: string;
  boundary_status?: string;
  status: 'CANDIDATE' | 'REVIEW' | 'APPROVED' | 'GENERATED' | string;
  building_count: number;
  actual_building_count: number;
  target_building_count: number;
  target_buildings_per_hlb: number;
  target_houses_per_hlb?: number;
  count_deviation?: number;
  quality_score: number;
  validation_status: 'VALID' | 'WARNING' | 'INVALID' | string;
  validation_details: {
    count_score?: number;
    boundary_score?: number;
    continuity_score?: number;
    compactness_score?: number;
    count_deviation?: number;
    errors?: string[];
    warnings?: string[];
    is_valid?: boolean;
    has_warnings?: boolean;
    building_count?: number;
    target_buildings_per_hlb?: number;
    quality_metrics?: {
      area_sq_meters?: number;
      perimeter_meters?: number;
      compactness?: number;
      longest_axis_meters?: number;
      boundary_intersecting_buildings_count?: number;
      road_segments_crossed_count?: number;
      estimated_walking_distance_km?: number;
      quality_warnings?: string[];
    };
  } | null;
  boundary: any; // GeoJSON Geometry (Polygon/MultiPolygon)
  centroid?: any | null; // GeoJSON Point
  warnings?: string[];
  created_at?: string;
  updated_at?: string;
}

export interface HlbListResponse {
  items: HlbCandidate[];
  total: number;
  layout_id?: string;
  version_id?: string | null;
}

export interface LayoutVersionSummary {
  id: string;
  layout_id: string;
  version_number: number;
  status: 'CANDIDATE' | 'APPROVED' | 'SUPERSEDED' | 'ARCHIVED' | string;
  source: 'AI_GENERATED' | 'MANUAL_EDIT' | 'APPROVED' | string;
  hlb_count: number;
  total_buildings: number;
  target_buildings_per_hlb: number;
  target_houses_per_hlb?: number;
  validation_status: 'VALID' | 'WARNING' | 'INVALID' | string;
  quality_score?: number | null;
  validation_summary?: any;
  generation_metadata?: any;
  created_by?: string | null;
  created_at: string;
}

export interface LayoutVersionListResponse {
  items: LayoutVersionSummary[];
  total: number;
  layout_id: string;
}

export interface HlbGenerationResult {
  layout_id: string;
  layout_name?: string;
  version_id?: string;
  layout_version_id?: string;
  version_number: number;
  total_buildings: number;
  total_buildings_assigned?: number;
  target_buildings_per_hlb: number;
  target_houses_per_hlb?: number;
  hlb_count: number;
  status?: string;
  quality_score?: number | null;
  average_quality_score?: number | null;
  invariants_satisfied?: boolean;
  warnings?: string[];
  validation_status: 'VALID' | 'WARNING' | 'INVALID' | string;
  validation_summary?: any;
  generation_metadata?: any;
  hlbs: HlbCandidate[];
}

export interface CreateLayoutPayload {
  administrative_area_id?: string;
  area_id?: string;
  area_ids?: string[];
  name: string;
  target_buildings_per_hlb?: number;
  target_houses_per_hlb?: number;
  description?: string;
}

export interface UpdateLayoutPayload {
  name?: string;
  target_buildings_per_hlb?: number;
  target_houses_per_hlb?: number;
  area_ids?: string[];
  area_id?: string;
  description?: string;
}

export interface GenerateHlbsPayload {
  target_buildings_per_hlb?: number;
  confidence_threshold?: number;
}

export interface SplitOptions {
  split_ratio?: number;
  split_method?: 'AUTO_BALANCED' | 'TARGET_BASED' | 'DRAW_SPLIT_LINE' | 'DRAW_LINE';
  target_building_count?: number;
  split_line_coordinates?: number[][];
}

export interface SplitPreviewResult {
  is_valid: boolean;
  side_a_block_code: string;
  side_a_building_count: number;
  side_b_block_code: string;
  side_b_building_count: number;
  total_original_buildings: number;
  validation_errors?: string[];
  invariants?: Record<string, boolean>;
  part_a_geometry?: any;
  part_b_geometry?: any;
  part_a_building_ids?: string[];
  part_b_building_ids?: string[];
}

export interface MergePreviewResult {
  is_valid: boolean;
  is_adjacent: boolean;
  merged_block_code: string;
  combined_building_count: number;
  building_assignment_status: string;
  validation_errors?: string[];
}

export interface HlbSplitResponse {
  layout_id: string;
  version_id: string;
  split_hlb_a: HlbCandidate;
  split_hlb_b: HlbCandidate;
}

export interface HlbMergeResponse {
  layout_id: string;
  version_id: string;
  merged_hlb: HlbCandidate;
}

export interface LayoutValidationChecklistItem {
  id: string;
  title: string;
  passed: boolean;
  detail: string;
}

export interface LayoutValidationResponse {
  layout_id: string;
  version_id?: string | null;
  version_number?: number | null;
  is_valid: boolean;
  can_approve: boolean;
  status: 'READY_FOR_APPROVAL' | 'NOT_READY_FOR_APPROVAL' | string;
  total_buildings: number;
  assigned_buildings: number;
  unassigned_buildings: number;
  duplicate_assignments: number;
  hlb_count: number;
  quality_score?: number | null;
  checklist: LayoutValidationChecklistItem[];
  warnings: string[];
  errors: string[];
}

export interface LayoutApprovalResponse {
  layout_id: string;
  name: string;
  status: string;
  version_id: string;
  version_number: number;
  version_status: string;
  total_buildings: number;
  hlb_count: number;
  approved_by?: string | null;
  approved_at?: string | null;
  validation_summary: LayoutValidationResponse;
}

function assertValidLayoutId(id: string): void {
  if (!id || id === 'undefined' || id === 'null' || id.trim() === '') {
    throw new Error('Layout ID could not be identified. Please select a valid layout.');
  }
}

function normalizeHlbCandidate(h: any): HlbCandidate {
  const code = h.block_code || h.hlb_code || h.code || 'HLB';
  const bldCount = h.actual_building_count ?? h.building_count ?? h.actual_house_count ?? 0;
  const targetBld = h.target_building_count ?? h.target_buildings_per_hlb ?? h.target_houses_per_hlb ?? 250;
  return {
    ...h,
    block_code: code,
    hlb_code: code,
    building_count: bldCount,
    actual_building_count: bldCount,
    target_building_count: targetBld,
    target_buildings_per_hlb: targetBld,
    quality_score: h.quality_score ?? 1.0,
    validation_status: h.validation_status || 'VALID',
    validation_details: h.validation_details || null,
    boundary: h.boundary || null,
    centroid: h.centroid || null,
    status: h.status || 'CANDIDATE',
  };
}

export const layoutService = {
  async getLayouts(params?: {
    area_id?: string;
    administrative_area_id?: string;
    status?: string;
    limit?: number;
    skip?: number;
  }): Promise<LayoutListResponse> {
    const queryParts: string[] = [];
    const areaId = params?.area_id || params?.administrative_area_id;
    if (areaId) {
      queryParts.push(`area_id=${encodeURIComponent(areaId)}`);
      queryParts.push(`administrative_area_id=${encodeURIComponent(areaId)}`);
    }
    if (params?.status) {
      queryParts.push(`status=${encodeURIComponent(params.status)}`);
    }
    if (params?.limit != null) {
      queryParts.push(`limit=${encodeURIComponent(params.limit)}`);
    }
    if (params?.skip != null) {
      queryParts.push(`skip=${encodeURIComponent(params.skip)}`);
    }
    const query = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
    return apiClient.get<LayoutListResponse>(`/layouts${query}`);
  },

  async getLayout(layoutId: string): Promise<LayoutSummary> {
    assertValidLayoutId(layoutId);
    return apiClient.get<LayoutSummary>(`/layouts/${layoutId}`);
  },

  async createLayout(payload: CreateLayoutPayload): Promise<LayoutSummary> {
    return apiClient.post<LayoutSummary>('/layouts', payload);
  },

  async updateLayout(layoutId: string, payload: UpdateLayoutPayload): Promise<LayoutSummary> {
    assertValidLayoutId(layoutId);
    return apiClient.put<LayoutSummary>(`/layouts/${layoutId}`, payload);
  },

  async generateHlbs(layoutId: string, payload?: GenerateHlbsPayload): Promise<HlbGenerationResult> {
    assertValidLayoutId(layoutId);
    const res = await apiClient.post<HlbGenerationResult>(`/layouts/${layoutId}/generate-hlbs`, payload || {});
    if (res && res.hlbs) {
      res.hlbs = res.hlbs.map(normalizeHlbCandidate);
    }
    return res;
  },

  async getLayoutHlbs(layoutId: string, versionId?: string): Promise<HlbListResponse> {
    assertValidLayoutId(layoutId);
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : '';
    const res = await apiClient.get<HlbListResponse>(`/layouts/${layoutId}/hlbs${query}`);
    if (res && res.items) {
      res.items = res.items.map(normalizeHlbCandidate);
    }
    return res;
  },

  async getLayoutVersions(layoutId: string): Promise<LayoutVersionListResponse> {
    assertValidLayoutId(layoutId);
    return apiClient.get<LayoutVersionListResponse>(`/layouts/${layoutId}/versions`);
  },

  async getHlb(hlbId: string): Promise<HlbCandidate & { houses?: any[] }> {
    const res = await apiClient.get<any>(`/hlbs/${hlbId}`);
    return normalizeHlbCandidate(res);
  },

  async editHlbBoundary(hlbId: string, boundaryGeoJson: any): Promise<HlbCandidate> {
    const res = await apiClient.patch<any>(`/hlbs/${hlbId}/boundary`, { boundary: boundaryGeoJson });
    return normalizeHlbCandidate(res);
  },

  async previewSplitHlb(hlbId: string, options: SplitOptions = {}): Promise<SplitPreviewResult> {
    const res = await apiClient.post<any>(`/hlbs/${hlbId}/split/preview`, {
      split_ratio: options.split_ratio ?? 0.5,
      split_method: options.split_method ?? 'AUTO_BALANCED',
      target_building_count: options.target_building_count,
      split_line_coordinates: options.split_line_coordinates,
    });
    const sideACode = res.side_a_block_code || res.part_a_code || 'HLB-A';
    const sideBCode = res.side_b_block_code || res.part_b_code || 'HLB-B';
    const sideABld = res.side_a_building_count ?? res.part_a_buildings ?? 0;
    const sideBBld = res.side_b_building_count ?? res.part_b_buildings ?? 0;
    const totalBld = res.total_original_buildings ?? res.total_buildings ?? (sideABld + sideBBld);
    return {
      is_valid: res.is_valid ?? true,
      side_a_block_code: sideACode,
      side_a_building_count: sideABld,
      side_b_block_code: sideBCode,
      side_b_building_count: sideBBld,
      total_original_buildings: totalBld,
      validation_errors: res.validation_errors || res.errors || [],
      invariants: res.invariants || {},
      part_a_geometry: res.part_a_geometry || null,
      part_b_geometry: res.part_b_geometry || null,
      part_a_building_ids: res.part_a_building_ids || [],
      part_b_building_ids: res.part_b_building_ids || [],
    };
  },

  async splitHlb(hlbId: string, splitRatioOrOptions: number | SplitOptions = 0.5): Promise<HlbSplitResponse> {
    const payload = typeof splitRatioOrOptions === 'number'
      ? { split_ratio: splitRatioOrOptions }
      : {
          split_ratio: splitRatioOrOptions.split_ratio ?? 0.5,
          split_method: splitRatioOrOptions.split_method ?? 'AUTO_BALANCED',
          target_building_count: splitRatioOrOptions.target_building_count,
          split_line_coordinates: splitRatioOrOptions.split_line_coordinates,
        };
    const res = await apiClient.post<any>(`/hlbs/${hlbId}/split`, payload);
    return {
      layout_id: res.layout_id,
      version_id: res.version_id,
      split_hlb_a: normalizeHlbCandidate(res.split_hlb_a),
      split_hlb_b: normalizeHlbCandidate(res.split_hlb_b),
    };
  },

  async previewMergeHlbs(hlbId1: string, hlbId2: string): Promise<MergePreviewResult> {
    const res = await apiClient.post<any>('/hlbs/merge/preview', {
      hlb_id_1: hlbId1,
      hlb_id_2: hlbId2,
    });
    const combinedCount = res.combined_building_count ?? res.combined_buildings ?? ((res.buildings_1 || 0) + (res.buildings_2 || 0));
    const mergedCode = res.merged_block_code || res.suggested_name || `${res.hlb_code_1 || 'HLB-1'} + ${res.hlb_code_2 || 'HLB-2'}`;
    return {
      is_valid: res.is_valid ?? true,
      is_adjacent: res.is_adjacent ?? true,
      merged_block_code: mergedCode,
      combined_building_count: combinedCount,
      building_assignment_status: res.building_assignment_status || `${combinedCount} / ${combinedCount}`,
      validation_errors: res.validation_errors || res.errors || [],
    };
  },

  async mergeHlbs(hlbId1: string, hlbId2: string): Promise<HlbMergeResponse> {
    const res = await apiClient.post<any>('/hlbs/merge', { hlb_id_1: hlbId1, hlb_id_2: hlbId2 });
    return {
      layout_id: res.layout_id,
      version_id: res.version_id,
      merged_hlb: normalizeHlbCandidate(res.merged_hlb),
    };
  },

  async validateLayout(layoutId: string, versionId?: string): Promise<LayoutValidationResponse> {
    assertValidLayoutId(layoutId);
    const query = versionId ? `?version_id=${encodeURIComponent(versionId)}` : '';
    return apiClient.post<LayoutValidationResponse>(`/layouts/${layoutId}/validate${query}`, {});
  },

  async approveLayout(layoutId: string): Promise<LayoutApprovalResponse> {
    assertValidLayoutId(layoutId);
    return apiClient.post<LayoutApprovalResponse>(`/layouts/${layoutId}/approve`, {});
  },
};
