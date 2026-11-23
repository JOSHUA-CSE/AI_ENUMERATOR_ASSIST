import { parseGeoJSONToRings, LatLng } from './geometryUtils';
import { GPS_ACCURACY_POOR_THRESHOLD_M, GPS_ACCURACY_MAX_RELIABLE_THRESHOLD_M } from './gpsService';
import { apiClient } from './apiClient';

export type BoundaryStatus =
  | 'INSIDE'
  | 'OUTSIDE'
  | 'BOUNDARY_UNCERTAIN'
  | 'GPS_UNCERTAIN'
  | 'LOCATION_PERMISSION_DENIED'
  | 'UNKNOWN';

export interface BoundaryCheckResult {
  status: BoundaryStatus;
  distanceToBoundaryMeters: number | null;
  accuracyMeters: number | null;
  message: string;
}

let lastAlertTime = 0;
let consecutiveOutsideCount = 0;
let lastKnownStatus: BoundaryStatus = 'UNKNOWN';
const ALERT_COOLDOWN_MS = 30000; // 30-second cooldown between repeated boundary alerts
const CONSECUTIVE_OUTSIDE_THRESHOLD = 2; // Require 2 consecutive outside fixes to filter GPS drift

/**
 * Calculates perpendicular distance from point (px, py) to line segment (x1, y1)-(x2, y2).
 */
function pointToSegmentDistanceMeters(
  px: float,
  py: float,
  x1: float,
  y1: float,
  x2: float,
  y2: float
): number {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) {
    const ex = px - x1;
    const ey = py - y1;
    return Math.sqrt(ex * ex + ey * ey);
  }

  const t = Math.max(0, Math.min(1, ((px - x1) * dx + (py - y1) * dy) / lenSq));
  const projX = x1 + t * dx;
  const projY = y1 + t * dy;
  const ex = px - projX;
  const ey = py - projY;
  return Math.sqrt(ex * ex + ey * ey);
}

type float = number;

/**
 * Tests whether a geographic point is inside a single closed polygon ring using ray-casting.
 */
function isPointInRing(point: LatLng, ring: LatLng[]): boolean {
  let inside = false;
  const n = ring.length;
  if (n < 3) return false;

  for (let i = 0, j = n - 1; i < n; j = i++) {
    const xi = ring[i].longitude;
    const yi = ring[i].latitude;
    const xj = ring[j].longitude;
    const yj = ring[j].latitude;

    const intersect =
      yi > point.latitude !== yj > point.latitude &&
      point.longitude < ((xj - xi) * (point.latitude - yi)) / (yj - yi) + xi;
    if (intersect) {
      inside = !inside;
    }
  }

  return inside;
}

export const boundaryService = {
  /**
   * Calculate minimum straight-line distance in meters from (lat, lon) to boundary edges.
   */
  calculateMinDistanceToBoundary(point: LatLng, rings: LatLng[][]): number {
    const mPerDegLat = 111320.0;
    const mPerDegLon = 111320.0 * Math.cos((point.latitude * Math.PI) / 180.0);
    let minDistance = Infinity;

    for (const ring of rings) {
      if (!ring || ring.length < 2) continue;
      for (let i = 0; i < ring.length - 1; i++) {
        const p1 = ring[i];
        const p2 = ring[i + 1];

        const x1 = (p1.longitude - point.longitude) * mPerDegLon;
        const y1 = (p1.latitude - point.latitude) * mPerDegLat;
        const x2 = (p2.longitude - point.longitude) * mPerDegLon;
        const y2 = (p2.latitude - point.latitude) * mPerDegLat;

        const d = pointToSegmentDistanceMeters(0, 0, x1, y1, x2, y2);
        if (d < minDistance) {
          minDistance = d;
        }
      }
    }

    return minDistance === Infinity ? 0 : minDistance;
  },

  /**
   * Determine whether a point is inside the given polygon boundary rings.
   * If MultiPolygon has multiple rings, returns true if point is inside any outer ring.
   */
  isPointInPolygon(point: LatLng, rings: LatLng[][]): boolean {
    if (!rings || rings.length === 0) return false;
    for (const ring of rings) {
      if (isPointInRing(point, ring)) {
        return true;
      }
    }
    return false;
  },

  /**
   * Offline boundary status evaluation combining containment testing,
   * distance-to-perimeter measurement, and GPS accuracy uncertainty tolerance.
   *
   * @param boundaryGeoJson GeoJSON geometry object or stringified GeoJSON
   * @param latitude Device latitude [-90, 90]
   * @param longitude Device longitude [-180, 180]
   * @param accuracyMeters Device horizontal accuracy radius in meters
   */
  checkBoundaryStatus(
    boundaryGeoJson: any,
    latitude: number,
    longitude: number,
    accuracyMeters: number | null
  ): BoundaryCheckResult {
    // 1. Validate coordinates
    if (
      typeof latitude !== 'number' ||
      typeof longitude !== 'number' ||
      isNaN(latitude) ||
      isNaN(longitude) ||
      latitude < -90 ||
      latitude > 90 ||
      longitude < -180 ||
      longitude > 180
    ) {
      return {
        status: 'UNKNOWN',
        distanceToBoundaryMeters: null,
        accuracyMeters,
        message: 'Invalid coordinate values',
      };
    }

    // 2. Parse GeoJSON boundary
    let parsedGeometry = boundaryGeoJson;
    if (typeof boundaryGeoJson === 'string') {
      try {
        parsedGeometry = JSON.parse(boundaryGeoJson);
      } catch {
        parsedGeometry = null;
      }
    }

    if (!parsedGeometry) {
      return {
        status: 'UNKNOWN',
        distanceToBoundaryMeters: null,
        accuracyMeters,
        message: 'HLB boundary data is unavailable',
      };
    }

    const rings = parseGeoJSONToRings(parsedGeometry);
    if (!rings || rings.length === 0 || rings[0].length < 3) {
      return {
        status: 'UNKNOWN',
        distanceToBoundaryMeters: null,
        accuracyMeters,
        message: 'HLB boundary geometry is empty or invalid',
      };
    }

    const point: LatLng = { latitude, longitude };
    const distanceMeters = this.calculateMinDistanceToBoundary(point, rings);
    const isInside = this.isPointInPolygon(point, rings);

    // 3. Accuracy and uncertainty evaluation
    if (accuracyMeters === null || accuracyMeters === undefined || isNaN(accuracyMeters) || accuracyMeters < 0) {
      // Accuracy is unknown: cannot make a strong conclusion near boundary
      if (distanceMeters < 30) {
        return {
          status: 'BOUNDARY_UNCERTAIN',
          distanceToBoundaryMeters: Math.round(distanceMeters),
          accuracyMeters: null,
          message: 'GPS accuracy unavailable near boundary',
        };
      }
      return {
        status: isInside ? 'INSIDE' : 'OUTSIDE',
        distanceToBoundaryMeters: Math.round(distanceMeters),
        accuracyMeters: null,
        message: isInside ? 'Inside assigned HLB (accuracy unknown)' : 'Outside assigned HLB (accuracy unknown)',
      };
    }

    if (accuracyMeters > GPS_ACCURACY_POOR_THRESHOLD_M) {
      return {
        status: 'GPS_UNCERTAIN',
        distanceToBoundaryMeters: Math.round(distanceMeters),
        accuracyMeters,
        message: `GPS accuracy (±${Math.round(accuracyMeters)}m) is too poor for boundary verification (>75m)`,
      };
    }

    if (accuracyMeters > GPS_ACCURACY_MAX_RELIABLE_THRESHOLD_M) {
      return {
        status: 'UNKNOWN',
        distanceToBoundaryMeters: Math.round(distanceMeters),
        accuracyMeters,
        message: `GPS accuracy (±${Math.round(accuracyMeters)}m) is too low for boundary determination`,
      };
    }

    // Uncertainty circle overlaps boundary edge
    if (distanceMeters <= accuracyMeters) {
      return {
        status: 'BOUNDARY_UNCERTAIN',
        distanceToBoundaryMeters: Math.round(distanceMeters),
        accuracyMeters,
        message: `GPS accuracy circle (±${Math.round(accuracyMeters)}m) overlaps HLB boundary (distance: ${Math.round(distanceMeters)}m)`,
      };
    }

    // Confident determination
    if (isInside) {
      return {
        status: 'INSIDE',
        distanceToBoundaryMeters: Math.round(distanceMeters),
        accuracyMeters,
        message: `Inside assigned HLB (${Math.round(distanceMeters)}m from boundary)`,
      };
    } else {
      return {
        status: 'OUTSIDE',
        distanceToBoundaryMeters: Math.round(distanceMeters),
        accuracyMeters,
        message: `Outside assigned HLB (${Math.round(distanceMeters)}m from boundary)`,
      };
    }
  },

  /**
   * Helper that checks boundary status given a point object and boundary geometry.
   */
  checkBoundary(
    point: LatLng & { accuracy?: number | null },
    boundaryGeoJson: any
  ): BoundaryCheckResult {
    return this.checkBoundaryStatus(
      boundaryGeoJson,
      point.latitude,
      point.longitude,
      point.accuracy ?? null
    );
  },

  /**
   * Reset transition state (e.g. when opening a new HLB or unmounting).
   */
  resetTransitionState(): void {
    lastAlertTime = 0;
    consecutiveOutsideCount = 0;
    lastKnownStatus = 'UNKNOWN';
  },

  /**
   * Submit boundary event (EXIT, ENTRY) to backend API if network is available,
   * preserving event integrity without failing fieldwork if offline.
   */
  async submitBoundaryEvent(
    hlbId: string,
    eventType: 'EXIT' | 'ENTRY' | 'ACCURACY_WARNING',
    latitude: number,
    longitude: number,
    accuracyMeters: number | null,
    distanceToBoundaryMeters: number | null
  ): Promise<void> {
    try {
      await apiClient.post(`/hlbs/${hlbId}/gps/boundary-event`, {
        event_type: eventType,
        latitude,
        longitude,
        accuracy_meters: accuracyMeters,
        distance_to_boundary_meters: distanceToBoundaryMeters,
        timestamp: new Date().toISOString(),
      });
    } catch {
      // Offline fallback: event can be queued for synchronization
    }
  },

  /**
   * Process incoming GPS fix with drift-filtering hysteresis and transition detection.
   * Invokes onExitAlert only when genuine transition from INSIDE -> OUTSIDE occurs.
   * Invokes onReEntry when returning inside.
   */
  evaluateBoundaryTransition(
    point: LatLng & { accuracy?: number | null },
    boundaryGeoJson: any,
    hlbId: string,
    onExitAlert?: (message: string) => void,
    onReEntry?: (message: string) => void
  ): BoundaryCheckResult {
    const result = this.checkBoundary(point, boundaryGeoJson);
    const now = Date.now();

    if (result.status === 'OUTSIDE') {
      consecutiveOutsideCount += 1;
      // Require consecutive confirmation to avoid GPS jitter along edge
      if (consecutiveOutsideCount >= CONSECUTIVE_OUTSIDE_THRESHOLD) {
        if (lastKnownStatus !== 'OUTSIDE' && now - lastAlertTime > ALERT_COOLDOWN_MS) {
          lastAlertTime = now;
          const alertMessage =
            'HLB Boundary Alert: You have moved outside your assigned HLB. Please return to your assigned area. Road traversal and route optimization are unavailable until you re-enter.';
          onExitAlert?.(alertMessage);
          this.submitBoundaryEvent(
            hlbId,
            'EXIT',
            point.latitude,
            point.longitude,
            point.accuracy ?? null,
            result.distanceToBoundaryMeters
          );
        }
        lastKnownStatus = 'OUTSIDE';
      }
    } else if (result.status === 'INSIDE') {
      consecutiveOutsideCount = 0;
      if (lastKnownStatus === 'OUTSIDE') {
        const reEntryMessage = 'Re-entry confirmed. You have returned to your assigned HLB. Road traversal access restored.';
        onReEntry?.(reEntryMessage);
        this.submitBoundaryEvent(
          hlbId,
          'ENTRY',
          point.latitude,
          point.longitude,
          point.accuracy ?? null,
          result.distanceToBoundaryMeters
        );
      }
      lastKnownStatus = 'INSIDE';
    } else {
      // UNCERTAIN or UNKNOWN
      consecutiveOutsideCount = 0;
    }

    return result;
  },
};
