import { apiClient } from './apiClient';

export interface GeoJSONGeometry {
  type: 'Polygon' | 'MultiPolygon' | 'Point' | string;
  coordinates: any;
}

export interface AdministrativeArea {
  id: string;
  name: string;
  type: 'VILLAGE' | 'WARD' | 'TALUK' | 'DISTRICT' | string;
  code: string;
  parent_id: string | null;
  status: string;
  house_count: number;
  boundary: GeoJSONGeometry | null;
  created_at: string;
  updated_at: string;
}

export interface AreaBoundaryResponse {
  id: string;
  name: string;
  code: string;
  type: string;
  boundary: GeoJSONGeometry;
}

export interface AreaListResponse {
  items: AdministrativeArea[];
  total: number;
  skip: number;
  limit: number;
}

export interface House {
  id: string;
  area_id: string;
  building_reference: string | null;
  house_number: string | null;
  latitude: number;
  longitude: number;
  source_type?: 'SATELLITE_DETECTED' | 'DEVELOPMENT_DATA' | 'MANUAL' | 'GOVERNMENT_IMPORT' | 'FIELD_VERIFIED' | string;
  detection_confidence?: number | null;
  detected_at?: string | null;
  imagery_source?: string | null;
  imagery_date?: string | null;
  area_in_meters?: number | null;
  footprint?: GeoJSONGeometry | null;
  created_at: string;
  updated_at: string;
}

export interface HouseListResponse {
  items: House[];
  total: number;
  skip: number;
  limit: number;
}

export interface BuildingDensityCluster {
  latitude: number;
  longitude: number;
  count: number;
  bounds: number[][];
}

export interface BuildingEstimationResponse {
  area_id: string;
  area_name: string;
  area_code: string;
  total_buildings: number;
  source_type: string;
  quality_label: string;
  imagery_source: string | null;
  imagery_date: string | null;
  average_confidence: number | null;
  density_clusters: BuildingDensityCluster[];
}

function assertValidAreaId(id: string): void {
  if (!id || id === 'undefined' || id === 'null' || id.trim() === '') {
    throw new Error('Administrative area could not be identified. Please return and select the area again.');
  }
}

export const areaService = {
  getAreas: async (params?: { skip?: number; limit?: number; type?: string; parent_id?: string }): Promise<AreaListResponse> => {
    const queryParts: string[] = [];
    if (params?.skip !== undefined) queryParts.push(`skip=${params.skip}`);
    if (params?.limit !== undefined) queryParts.push(`limit=${params.limit}`);
    if (params?.type) queryParts.push(`type=${encodeURIComponent(params.type)}`);
    if (params?.parent_id) queryParts.push(`parent_id=${encodeURIComponent(params.parent_id)}`);
    const qs = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
    return apiClient.get<AreaListResponse>(`/areas${qs}`);
  },

  getAreaById: async (id: string): Promise<AdministrativeArea> => {
    assertValidAreaId(id);
    return apiClient.get<AdministrativeArea>(`/areas/${id}`);
  },

  getAreaBoundary: async (id: string): Promise<AreaBoundaryResponse> => {
    assertValidAreaId(id);
    return apiClient.get<AreaBoundaryResponse>(`/areas/${id}/boundary`);
  },

  getAreaHouses: async (id: string, params?: { skip?: number; limit?: number; source_type?: string }): Promise<HouseListResponse> => {
    assertValidAreaId(id);
    const queryParts: string[] = [];
    if (params?.skip !== undefined) queryParts.push(`skip=${params.skip}`);
    if (params?.limit !== undefined) queryParts.push(`limit=${params.limit}`);
    if (params?.source_type) queryParts.push(`source_type=${encodeURIComponent(params.source_type)}`);
    const qs = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
    return apiClient.get<HouseListResponse>(`/areas/${id}/houses${qs}`);
  },

  getBuildingEstimation: async (id: string): Promise<BuildingEstimationResponse> => {
    assertValidAreaId(id);
    return apiClient.get<BuildingEstimationResponse>(`/areas/${id}/estimation`);
  },

  detectBuildings: async (id: string, params?: { imagery_source?: string; confidence_threshold?: number }): Promise<BuildingEstimationResponse> => {
    assertValidAreaId(id);
    const queryParts: string[] = [];
    if (params?.imagery_source) queryParts.push(`imagery_source=${encodeURIComponent(params.imagery_source)}`);
    if (params?.confidence_threshold !== undefined) queryParts.push(`confidence_threshold=${params.confidence_threshold}`);
    const qs = queryParts.length > 0 ? `?${queryParts.join('&')}` : '';
    return apiClient.post<BuildingEstimationResponse>(`/areas/${id}/detect-buildings${qs}`, {});
  },
};

