import { apiClient } from './apiClient';

export interface DeputySupervisorInfo {
  id?: string | null;
  name?: string | null;
  username?: string | null;
  phone?: string | null;
  status?: string | null;
  is_assigned: boolean;
}

export interface DeputyHlbSummary {
  hlb_id: string;
  block_code: string;
  name?: string | null;
  status: string;
  assigned_enumerator_id?: string | null;
  assigned_enumerator_name?: string | null;
  assigned_supervisor_name?: string | null;
  total_houses: number;
  completed_houses: number;
  remaining_houses: number;
  locked_houses: number;
  revisit_count: number;
  progress_percentage: number;
  is_completed: boolean;
  is_active: boolean;
  last_sync?: string | null;
}

export interface DeputyLayoutProgressItem {
  layout_id: string;
  layout_name: string;
  area_id?: string | null;
  village_name?: string | null;
  status: string;
  supervisor?: DeputySupervisorInfo | null;
  total_hlbs: number;
  active_hlbs: number;
  completed_hlbs: number;
  remaining_hlbs: number;
  total_houses: number;
  completed_houses: number;
  remaining_houses: number;
  locked_houses: number;
  revisit_count: number;
  overall_progress_percentage: number;
}

export interface DeputyLayoutDetailProgressResponse extends DeputyLayoutProgressItem {
  hlbs: DeputyHlbSummary[];
  last_updated: string;
}

export interface DeputyOverallProgressResponse {
  total_layouts: number;
  total_hlbs: number;
  active_hlbs: number;
  completed_hlbs: number;
  remaining_hlbs: number;
  total_houses: number;
  completed_houses: number;
  remaining_houses: number;
  locked_houses: number;
  revisit_count: number;
  overall_progress_percentage: number;
  layouts: DeputyLayoutProgressItem[];
  last_updated: string;
}

class DeputyService {
  /**
   * Retrieve Level 1 overall fieldwork progress and per-layout progress cards.
   */
  async getOverallProgress(areaId?: string): Promise<DeputyOverallProgressResponse> {
    const url = areaId ? `/deputy/progress?area_id=${encodeURIComponent(areaId)}` : '/deputy/progress';
    return apiClient.get<DeputyOverallProgressResponse>(url);
  }

  /**
   * Retrieve Level 2 & Level 3 layout progress details and HLB summaries.
   */
  async getLayoutProgress(layoutId: string): Promise<DeputyLayoutDetailProgressResponse> {
    return apiClient.get<DeputyLayoutDetailProgressResponse>(
      `/deputy/layouts/${layoutId}/progress`
    );
  }

  /**
   * List pending change requests across the Deputy's jurisdiction.
   */
  async getChangeRequests(status?: string): Promise<{ items: any[]; total: number }> {
    const url = status
      ? `/deputy/change-requests?status=${encodeURIComponent(status)}`
      : '/deputy/change-requests';
    return apiClient.get<{ items: any[]; total: number }>(url);
  }

  /**
   * Resolve a change request (approve or reject with notes).
   */
  async resolveChangeRequest(
    id: string,
    resolution: { approved: boolean; resolution_notes?: string }
  ): Promise<any> {
    return apiClient.post(`/deputy/change-requests/${id}/resolve`, resolution);
  }

  /**
   * Retrieve final accepted census figures strictly isolated from draft progress.
   */
  async getAcceptedTotals(areaId?: string, layoutId?: string): Promise<any> {
    let url = '/deputy/accepted-totals';
    const params: string[] = [];
    if (areaId) params.push(`area_id=${encodeURIComponent(areaId)}`);
    if (layoutId) params.push(`layout_id=${encodeURIComponent(layoutId)}`);
    if (params.length > 0) url += `?${params.join('&')}`;
    return apiClient.get<any>(url);
  }

  /**
   * List message thread entries for a change request.
   */
  async getRequestMessages(requestId: string): Promise<{ items: any[]; total: number }> {
    return apiClient.get<{ items: any[]; total: number }>(
      `/deputy/change-requests/${requestId}/messages`
    );
  }

  /**
   * Post message to a change request discussion thread.
   */
  async postRequestMessage(
    requestId: string,
    message: string,
    attachments?: any
  ): Promise<any> {
    return apiClient.post(`/deputy/change-requests/${requestId}/messages`, {
      message,
      attachments,
    });
  }
}

export const deputyService = new DeputyService();
