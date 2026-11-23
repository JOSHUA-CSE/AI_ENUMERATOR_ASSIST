import { Linking } from 'react-native';
import { apiClient } from './apiClient';
import { getDatabase } from './sqlite/database';
import type {
  RoadCoverageNavigationData,
  RoadSegmentData,
  RoadSurveyStatus,
} from './sqlite/types';

const EARTH_RADIUS_METERS = 6371000.0;
const DEFAULT_DEVIATION_THRESHOLD_METERS = 50.0;

function haversineMeters(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  if (lat1 === lat2 && lon1 === lon2) return 0.0;
  const phi1 = (lat1 * Math.PI) / 180.0;
  const phi2 = (lat2 * Math.PI) / 180.0;
  const dPhi = ((lat2 - lat1) * Math.PI) / 180.0;
  const dLambda = ((lon2 - lon1) * Math.PI) / 180.0;

  const a =
    Math.sin(dPhi / 2.0) ** 2 +
    Math.cos(phi1) * Math.cos(phi2) * Math.sin(dLambda / 2.0) ** 2;
  const c = 2.0 * Math.atan2(Math.sqrt(a), Math.sqrt(Math.max(0, 1.0 - a)));
  return EARTH_RADIUS_METERS * c;
}

/**
 * Distance from point P to line segment AB in meters.
 */
function distanceToSegmentMeters(
  pLat: number,
  pLon: number,
  aLat: number,
  aLon: number,
  bLat: number,
  bLon: number
): number {
  const dAB = haversineMeters(aLat, aLon, bLat, bLon);
  if (dAB < 1e-4) {
    return haversineMeters(pLat, pLon, aLat, aLon);
  }

  // Linear projection parameter t in planar approximation
  const cosLat = Math.cos(((aLat + bLat) / 2.0) * (Math.PI / 180.0));
  const dx = (bLon - aLon) * cosLat;
  const dy = bLat - aLat;
  const px = (pLon - aLon) * cosLat;
  const py = pLat - aLat;

  const t = Math.max(0.0, Math.min(1.0, (px * dx + py * dy) / (dx * dx + dy * dy)));
  const projLat = aLat + t * (bLat - aLat);
  const projLon = aLon + t * (bLon - aLon);

  return haversineMeters(pLat, pLon, projLat, projLon);
}

class RoadCoverageService {
  private routeCache: Map<string, RoadCoverageNavigationData> = new Map();

  /**
   * Fetch road coverage route from backend following walkable road network.
   */
  async fetchRoadCoverageRoute(
    hlbId: string,
    currentGps?: { latitude: number; longitude: number } | null,
    returnToStart = false
  ): Promise<RoadCoverageNavigationData> {
    const payload: Record<string, any> = {
      return_to_start: returnToStart,
    };
    if (currentGps?.latitude && currentGps?.longitude) {
      payload.latitude = currentGps.latitude;
      payload.longitude = currentGps.longitude;
    }

    try {
      const response = await apiClient.post<RoadCoverageNavigationData>(
        `/hlbs/${hlbId}/route/coverage`,
        payload
      );
      const data = response;
      this.routeCache.set(hlbId, data);
      await this.saveRoadCoverageLocally(hlbId, data);
      return data;
    } catch (err) {
      // Offline fallback: try to load from local cache
      const cached = await this.getOfflineRoadCoverageRoute(hlbId);
      if (cached) {
        return cached;
      }
      throw err;
    }
  }

  /**
   * Load locally stored road coverage navigation data.
   */
  async getOfflineRoadCoverageRoute(
    hlbId: string
  ): Promise<RoadCoverageNavigationData | null> {
    if (this.routeCache.has(hlbId)) {
      return this.routeCache.get(hlbId)!;
    }

    try {
      const db = await getDatabase();
      const rows = await db.getAllAsync<{ data_json: string }>(
        'SELECT data_json FROM offline_road_routes WHERE hlb_id = ? LIMIT 1;',
        [hlbId]
      );
      if (rows && rows.length > 0) {
        const parsed = JSON.parse(rows[0].data_json) as RoadCoverageNavigationData;
        this.routeCache.set(hlbId, parsed);
        return parsed;
      }
    } catch (err) {
      // Table might not exist yet if offline route wasn't downloaded
    }
    return null;
  }

  /**
   * Save road coverage navigation data in SQLite for offline fieldwork.
   */
  async saveRoadCoverageLocally(
    hlbId: string,
    data: RoadCoverageNavigationData
  ): Promise<void> {
    try {
      const db = await getDatabase();
      await db.execAsync(`
        CREATE TABLE IF NOT EXISTS offline_road_routes (
          hlb_id TEXT PRIMARY KEY,
          data_json TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
      `);
      await db.runAsync(
        `INSERT OR REPLACE INTO offline_road_routes (hlb_id, data_json, updated_at)
         VALUES (?, ?, ?);`,
        [hlbId, JSON.stringify(data), new Date().toISOString()]
      );
    } catch (err) {
      console.warn('Failed to save road coverage locally in SQLite:', err);
    }
  }

  /**
   * Submit live GPS points to update road segment survey coverage.
   */
  async trackGpsTrace(
    hlbId: string,
    gpsPoints: Array<{
      latitude: number;
      longitude: number;
      timestamp?: string;
      accuracy?: number;
    }>,
    deviceId?: string
  ): Promise<any> {
    try {
      const response = await apiClient.post<any>(
        `/hlbs/${hlbId}/route/coverage/track`,
        {
          gps_points: gpsPoints,
          device_id: deviceId,
          tolerance_meters: 20.0,
        }
      );
      return response;
    } catch (err) {
      console.warn('Failed to submit GPS coverage track:', err);
      return null;
    }
  }

  /**
   * Record newly discovered unmapped building during road traversal.
   */
  async discoverBuilding(
    hlbId: string,
    data: {
      latitude: number;
      longitude: number;
      building_reference?: string;
      house_number?: string;
      notes?: string;
      placement_mode?: 'CURRENT_GPS' | 'MANUAL_MAP';
    }
  ): Promise<any> {
    const response = await apiClient.post<any>(
      `/hlbs/${hlbId}/buildings/discover`,
      data
    );
    return response;
  }

  /**
   * Check if current GPS coordinate deviates from the active planned road route.
   */
  checkRouteDeviation(
    currentLat: number,
    currentLon: number,
    routePolyline: [number, number][],
    thresholdMeters = DEFAULT_DEVIATION_THRESHOLD_METERS
  ): { isDeviated: boolean; deviationDistanceM: number; message: string } {
    if (!routePolyline || routePolyline.length < 2) {
      return { isDeviated: false, deviationDistanceM: 0.0, message: 'On track' };
    }

    let minDistance = Infinity;
    for (let i = 0; i < routePolyline.length - 1; i++) {
      const a = routePolyline[i];
      const b = routePolyline[i + 1];
      const d = distanceToSegmentMeters(
        currentLat,
        currentLon,
        a[0],
        a[1],
        b[0],
        b[1]
      );
      if (d < minDistance) {
        minDistance = d;
      }
    }

    const isDeviated = minDistance > thresholdMeters;
    return {
      isDeviated,
      deviationDistanceM: Math.round(minDistance),
      message: isDeviated
        ? `Off route by ${Math.round(minDistance)}m! Planned road is ${Math.round(minDistance)}m away.`
        : 'On track',
    };
  }

  /**
   * Open Google Maps walking directions to the destination or route checkpoint.
   */
  async openGoogleMapsWalkingDirections(
    destLat: number,
    destLon: number
  ): Promise<void> {
    const url = `https://www.google.com/maps/dir/?api=1&destination=${destLat},${destLon}&travelmode=walking`;
    const supported = await Linking.canOpenURL(url);
    if (supported) {
      await Linking.openURL(url);
    } else {
      console.warn('Google Maps URL not supported:', url);
    }
  }
}

export const roadCoverageService = new RoadCoverageService();
