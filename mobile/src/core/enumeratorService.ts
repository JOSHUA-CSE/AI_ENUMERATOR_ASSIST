import { apiClient } from './apiClient';

export interface EnumeratorSummary {
  id: string;
  name: string;
  username: string;
  phone?: string | null;
  role: string;
  status: string;
  availability: 'AVAILABLE' | 'ASSIGNED' | 'INACTIVE';
  assigned_hlb_code?: string | null;
  assigned_layout_name?: string | null;
}

export interface EnumeratorListResponse {
  items: EnumeratorSummary[];
  total: number;
}

export interface EnumeratorAssignment {
  id: string;
  hlb_id: string;
  block_code?: string | null;
  layout_id: string;
  layout_name?: string | null;
  enumerator_id: string;
  enumerator_name?: string | null;
  enumerator_username?: string | null;
  supervisor_id: string;
  supervisor_name?: string | null;
  assigned_at: string;
  status: 'ACTIVE' | 'COMPLETED' | 'CANCELLED' | string;
  created_at: string;
  updated_at: string;
}

export interface HlbAssignmentStatusItem {
  hlb_id: string;
  block_code: string;
  name: string;
  actual_building_count: number;
  target_building_count: number;
  is_assigned: boolean;
  assignment?: EnumeratorAssignment | null;
}

export interface LayoutEnumeratorAssignmentsResponse {
  layout_id: string;
  layout_name: string;
  total_hlbs: number;
  required_enumerators: number;
  assigned_enumerators: number;
  remaining_enumerators: number;
  status: 'COMPLETE' | 'INCOMPLETE';
  is_complete: boolean;
  items: HlbAssignmentStatusItem[];
}

export interface EnumeratorAssignedHlbDetail {
  id: string;
  layout_id: string;
  layout_name?: string | null;
  area_name?: string | null;
  block_code: string;
  name: string;
  status: string;
  target_building_count: number;
  actual_building_count: number;
  boundary?: any;
  assignment?: EnumeratorAssignment | null;
}

export interface EnumeratorBuildingItem {
  id: string;
  building_reference: string;
  house_number?: string | null;
  latitude: number;
  longitude: number;
  footprint?: any;
  source_type?: string | null;
  status: string;
}

export interface EnumeratorHlbDownloadResponse {
  hlb: EnumeratorAssignedHlbDetail;
  buildings: EnumeratorBuildingItem[];
  total_buildings: number;
  downloaded_at: string;
}

export const enumeratorService = {
  /**
   * List all enumerators and their real-time availability.
   * Authorized for DEPUTY_TAHSILDAR and SUPERVISOR.
   */
  async getEnumerators(): Promise<EnumeratorListResponse> {
    return apiClient.get<EnumeratorListResponse>('/enumerators');
  },

  /**
   * Assign an HLB to a Primary Enumerator.
   * Authorized for the SUPERVISOR assigned to the layout.
   */
  async assignEnumerator(
    hlbId: string,
    enumeratorId: string
  ): Promise<EnumeratorAssignment> {
    return apiClient.post<EnumeratorAssignment>(
      `/hlbs/${hlbId}/assign-enumerator`,
      { enumerator_id: enumeratorId }
    );
  },

  /**
   * Get active primary enumerator assignment for an HLB.
   */
  async getHlbEnumeratorAssignment(
    hlbId: string
  ): Promise<EnumeratorAssignment | null> {
    return apiClient.get<EnumeratorAssignment | null>(
      `/hlbs/${hlbId}/enumerator-assignment`
    );
  },

  /**
   * Get layout-level enumerator assignment summary and status for all HLBs.
   * Authorized for DEPUTY_TAHSILDAR and responsible SUPERVISOR.
   */
  async getLayoutEnumeratorAssignments(
    layoutId: string
  ): Promise<LayoutEnumeratorAssignmentsResponse> {
    return apiClient.get<LayoutEnumeratorAssignmentsResponse>(
      `/layouts/${layoutId}/enumerator-assignments`
    );
  },

  /**
   * Retrieve all HLBs actively assigned to the authenticated enumerator.
   * Authorized for ENUMERATOR. Derived strictly from JWT.
   */
  async getMyAssignedHlbs(): Promise<EnumeratorAssignedHlbDetail[]> {
    return apiClient.get<EnumeratorAssignedHlbDetail[]>('/enumerator/hlbs');
  },

  /**
   * Retrieve details and boundary for a specific assigned HLB.
   * Authorized for ENUMERATOR. Backend returns 403 if unassigned.
   */
  async getMyAssignedHlbDetail(
    hlbId: string
  ): Promise<EnumeratorAssignedHlbDetail> {
    return apiClient.get<EnumeratorAssignedHlbDetail>(
      `/enumerator/hlbs/${hlbId}`
    );
  },

  /**
   * Download complete HLB dataset (boundary, metadata, and all assigned buildings)
   * for offline field operations. Backend returns 403 if unassigned.
   */
  async downloadAssignedHlb(
    hlbId: string
  ): Promise<EnumeratorHlbDownloadResponse> {
    return apiClient.get<EnumeratorHlbDownloadResponse>(
      `/enumerator/hlbs/${hlbId}/download`
    );
  },
};

