import { apiClient } from './apiClient';
import { LayoutSummary } from './layoutService';

export interface SupervisorSummary {
  id: string;
  name: string;
  username: string;
  phone?: string | null;
  role: string;
  status: string;
  assigned_layouts_count: number;
}

export interface SupervisorAssignment {
  id: string;
  layout_id: string;
  layout_name?: string | null;
  supervisor_id: string;
  supervisor_name?: string | null;
  supervisor_username?: string | null;
  assigned_by?: string | null;
  assigned_by_name?: string | null;
  assigned_at: string;
  status: 'ACTIVE' | 'COMPLETED' | 'CANCELLED' | string;
  created_at: string;
  updated_at: string;
}

export interface SupervisorLayoutSummary extends LayoutSummary {
  assignment?: SupervisorAssignment | null;
  supervisor_name?: string | null;
}

export interface SupervisorListResponse {
  items: SupervisorSummary[];
  total: number;
}

export interface SupervisorLayoutListResponse {
  items: SupervisorLayoutSummary[];
  total: number;
}

export interface SupervisorEnumeratorProgress {
  id: string;
  name: string;
  username?: string | null;
  phone?: string | null;
  assigned_hlb_id?: string | null;
  assigned_hlb_code?: string | null;
  progress_percentage: number;
  completed_houses: number;
  remaining_houses: number;
  locked_houses: number;
  revisit_count: number;
  last_sync?: string | null;
  sync_status?: string | null;
}

export interface BoundaryAlertItem {
  track_id: string;
  timestamp: string;
  latitude: number;
  longitude: number;
  distance_meters?: number | null;
  message?: string | null;
}

export interface SupervisorHlbProgress {
  hlb_id: string;
  block_code: string;
  name?: string | null;
  enumerator?: SupervisorEnumeratorProgress | null;
  total_houses: number;
  completed_houses: number;
  remaining_houses: number;
  locked_houses: number;
  revisit_count: number;
  progress_percentage: number;
  last_sync?: string | null;
  gps_coverage?: number | null;
  boundary_alert_count: number;
  boundary_alerts?: BoundaryAlertItem[];
}

export interface SupervisorLayoutProgress {
  layout_id: string;
  layout_name: string;
  area_id?: string | null;
  village_name?: string | null;
  total_hlbs: number;
  total_houses: number;
  completed_houses: number;
  remaining_houses: number;
  locked_houses: number;
  revisit_count: number;
  progress_percentage: number;
  last_updated: string;
  hlbs: SupervisorHlbProgress[];
}

export interface SupervisorOverallProgressResponse {
  layouts: SupervisorLayoutProgress[];
  total_layouts: number;
  overall_total_houses: number;
  overall_completed_houses: number;
  overall_remaining_houses: number;
  overall_locked_houses: number;
  overall_revisit_count: number;
  overall_progress_percentage: number;
  last_updated: string;
}

export const supervisorService = {
  /**
   * List all active supervisors.
   * Authorized for DEPUTY_TAHSILDAR.
   */
  async getSupervisors(): Promise<SupervisorListResponse> {
    return apiClient.get<SupervisorListResponse>('/supervisors');
  },

  /**
   * Assign an approved layout to a Supervisor.
   * Authorized for DEPUTY_TAHSILDAR.
   */
  async assignSupervisor(
    layoutId: string,
    supervisorId: string
  ): Promise<SupervisorAssignment> {
    return apiClient.post<SupervisorAssignment>(
      `/layouts/${layoutId}/assign-supervisor`,
      { supervisor_id: supervisorId }
    );
  },

  /**
   * Get active supervisor assignment for a layout.
   */
  async getSupervisorAssignment(
    layoutId: string
  ): Promise<SupervisorAssignment | null> {
    return apiClient.get<SupervisorAssignment | null>(
      `/layouts/${layoutId}/supervisor-assignment`
    );
  },

  /**
   * Retrieve all layouts assigned to the authenticated supervisor.
   * Authorized for SUPERVISOR. Derived from JWT identity.
   */
  async getMyAssignedLayouts(): Promise<SupervisorLayoutListResponse> {
    return apiClient.get<SupervisorLayoutListResponse>('/supervisor/layouts');
  },

  /**
   * Retrieve details for a supervisor's assigned layout.
   * Authorized for SUPERVISOR. Backend enforces 403 if unassigned.
   */
  async getMyAssignedLayoutDetail(
    layoutId: string
  ): Promise<SupervisorLayoutSummary> {
    return apiClient.get<SupervisorLayoutSummary>(
      `/supervisor/layouts/${layoutId}`
    );
  },

  /**
   * Phase 13: Retrieve progress metrics across all layouts assigned to the supervisor.
   */
  async getMyLayoutsProgress(): Promise<SupervisorOverallProgressResponse> {
    return apiClient.get<SupervisorOverallProgressResponse>('/supervisor/layouts/progress');
  },

  /**
   * Phase 13: Retrieve aggregated fieldwork progress for an assigned layout.
   */
  async getLayoutProgress(layoutId: string): Promise<SupervisorLayoutProgress> {
    return apiClient.get<SupervisorLayoutProgress>(`/supervisor/layouts/${layoutId}/progress`);
  },

  /**
   * Phase 13: Retrieve authoritative fieldwork progress for an individual HLB.
   */
  async getHlbProgress(hlbId: string): Promise<SupervisorHlbProgress> {
    return apiClient.get<SupervisorHlbProgress>(`/supervisor/hlbs/${hlbId}/progress`);
  },

  /**
   * Retrieve household submissions across assigned layouts.
   */
  async getSubmissions(params?: {
    hlb_id?: string;
    review_state?: string;
  }): Promise<{ items: any[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.hlb_id) query.append('hlb_id', params.hlb_id);
    if (params?.review_state) query.append('review_state', params.review_state);
    const qs = query.toString();
    return apiClient.get<{ items: any[]; total: number }>(
      qs ? `/supervisor/submissions?${qs}` : '/supervisor/submissions'
    );
  },

  /**
   * Supervisor verification of a submitted household record.
   */
  async verifySubmission(id: string, comment?: string): Promise<any> {
    return apiClient.post(`/supervisor/submissions/${id}/verify`, { comment });
  },

  /**
   * Return a submitted household record for correction.
   */
  async returnSubmission(
    id: string,
    rejectionReason: string,
    comment?: string
  ): Promise<any> {
    return apiClient.post(`/supervisor/submissions/${id}/return`, {
      rejection_reason: rejectionReason,
      supervisor_comment: comment,
    });
  },

  /**
   * Retrieve building edits queued for review.
   */
  async getBuildingEdits(params?: {
    hlb_id?: string;
    status?: string;
  }): Promise<{ items: any[]; total: number }> {
    const query = new URLSearchParams();
    if (params?.hlb_id) query.append('hlb_id', params.hlb_id);
    if (params?.status) query.append('status', params.status);
    const qs = query.toString();
    return apiClient.get<{ items: any[]; total: number }>(
      qs ? `/supervisor/building-edits?${qs}` : '/supervisor/building-edits'
    );
  },

  /**
   * Review a building edit (approve or reject).
   */
  async reviewBuildingEdit(
    id: string,
    approved: boolean,
    notes?: string
  ): Promise<any> {
    return apiClient.post(`/supervisor/building-edits/${id}/review`, {
      approved,
      notes,
    });
  },

  /**
   * Submit a Change Request to Deputy Tahsildar.
   */
  async createChangeRequest(payload: {
    layout_id: string;
    hlb_id?: string;
    request_type: string;
    description: string;
    proposed_payload?: any;
  }): Promise<any> {
    return apiClient.post('/supervisor/change-requests', payload);
  },

  /**
   * List supervisor change requests.
   */
  async getChangeRequests(layoutId?: string): Promise<{ items: any[]; total: number }> {
    const url = layoutId
      ? `/supervisor/change-requests?layout_id=${encodeURIComponent(layoutId)}`
      : '/supervisor/change-requests';
    return apiClient.get<{ items: any[]; total: number }>(url);
  },
};

