export interface LatLng {
  latitude: number;
  longitude: number;
}

/**
 * Calculates perpendicular distance from a point P to a line segment AB.
 */
function perpendicularDistance(p: LatLng, a: LatLng, b: LatLng): number {
  const dx = b.longitude - a.longitude;
  const dy = b.latitude - a.latitude;
  const lenSq = dx * dx + dy * dy;
  if (lenSq === 0) {
    const px = p.longitude - a.longitude;
    const py = p.latitude - a.latitude;
    return Math.sqrt(px * px + py * py);
  }
  const t = Math.max(0, Math.min(1, ((p.longitude - a.longitude) * dx + (p.latitude - a.latitude) * dy) / lenSq));
  const projX = a.longitude + t * dx;
  const projY = a.latitude + t * dy;
  const ex = p.longitude - projX;
  const ey = p.latitude - projY;
  return Math.sqrt(ex * ex + ey * ey);
}

/**
 * Ramer-Douglas-Peucker (RDP) polyline simplification algorithm.
 */
function rdpSimplify(points: LatLng[], epsilon: number): LatLng[] {
  if (points.length <= 2) return points;

  let maxDist = 0;
  let maxIdx = 0;
  const first = points[0];
  const last = points[points.length - 1];

  for (let i = 1; i < points.length - 1; i++) {
    const d = perpendicularDistance(points[i], first, last);
    if (d > maxDist) {
      maxDist = d;
      maxIdx = i;
    }
  }

  if (maxDist > epsilon) {
    const left = rdpSimplify(points.slice(0, maxIdx + 1), epsilon);
    const right = rdpSimplify(points.slice(maxIdx), epsilon);
    return left.slice(0, left.length - 1).concat(right);
  }

  return [first, last];
}

/**
 * Simplifies a dense polygon boundary down to a clean, minimal set of key control vertices
 * (default: 6 - 8 points max) suitable for easy, clutter-free drag-and-drop boundary editing.
 *
 * @param coords Array of LatLng coordinates representing the polygon boundary ring.
 * @param targetMaxVertices Maximum number of draggable control points desired (default: 8).
 * @param minVertices Minimum number of vertices to preserve polygon validity (default: 4).
 * @returns A minimal array of LatLng vertices representing the simplified polygon.
 */
export function simplifyPolygonForEditing(
  coords: LatLng[],
  targetMaxVertices: number = 8,
  minVertices: number = 4
): LatLng[] {
  if (!coords || coords.length <= minVertices) {
    return coords ? [...coords] : [];
  }

  // Strip trailing duplicate closing coordinate if present
  let pts = [...coords];
  const isClosed =
    pts.length > 1 &&
    pts[0].latitude === pts[pts.length - 1].latitude &&
    pts[0].longitude === pts[pts.length - 1].longitude;
  if (isClosed) {
    pts.pop();
  }

  if (pts.length <= targetMaxVertices) {
    return pts;
  }

  // Identify the two most distant points across the polygon to split the loop into two arcs
  let maxDSq = -1;
  let idxA = 0;
  let idxB = Math.floor(pts.length / 2);

  for (let i = 0; i < pts.length; i++) {
    for (let j = i + 1; j < pts.length; j++) {
      const dx = pts[i].longitude - pts[j].longitude;
      const dy = pts[i].latitude - pts[j].latitude;
      const dSq = dx * dx + dy * dy;
      if (dSq > maxDSq) {
        maxDSq = dSq;
        idxA = i;
        idxB = j;
      }
    }
  }

  if (idxA > idxB) {
    const temp = idxA;
    idxA = idxB;
    idxB = temp;
  }

  const arc1 = pts.slice(idxA, idxB + 1);
  const arc2 = pts.slice(idxB).concat(pts.slice(0, idxA + 1));

  // Adaptive binary search for the optimal epsilon tolerance that yields targetMaxVertices
  let lowEps = 0.000005; // ~0.5m
  let highEps = 0.05;    // ~5km
  let bestResult = pts;

  for (let iter = 0; iter < 16; iter++) {
    const midEps = (lowEps + highEps) / 2;
    const simArc1 = rdpSimplify(arc1, midEps);
    const simArc2 = rdpSimplify(arc2, midEps);

    // Merge arcs without duplicating junction vertices
    const merged = simArc1.slice(0, -1).concat(simArc2.slice(0, -1));

    if (merged.length >= minVertices && merged.length <= targetMaxVertices) {
      bestResult = merged;
      break;
    } else if (merged.length > targetMaxVertices) {
      bestResult = merged;
      lowEps = midEps; // Increase epsilon tolerance to reduce points further
    } else {
      // Too few points, reduce tolerance
      highEps = midEps;
    }
  }

  // Guarantee at least minVertices
  if (bestResult.length < minVertices) {
    bestResult = pts.slice(0, Math.min(pts.length, targetMaxVertices));
  }

  return bestResult;
}

/**
 * Extracts coordinates array of rings from a GeoJSON Polygon or MultiPolygon.
 */
export function parseGeoJSONToRings(geometry: any): LatLng[][] {
  if (!geometry || !geometry.coordinates) return [];
  if (geometry.type === 'Polygon') {
    return geometry.coordinates.map((ring: number[][]) =>
      ring.map(([lng, lat]: number[]) => ({ latitude: lat, longitude: lng }))
    );
  } else if (geometry.type === 'MultiPolygon') {
    return geometry.coordinates.flatMap((poly: number[][][]) =>
      poly.map((ring: number[][]) =>
        ring.map(([lng, lat]: number[]) => ({ latitude: lat, longitude: lng }))
      )
    );
  }
  return [];
}
