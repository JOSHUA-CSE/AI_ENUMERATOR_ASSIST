import { simplifyPolygonForEditing, LatLng } from '../src/core/geometryUtils';

describe('GeometryUtils - simplifyPolygonForEditing', () => {
  it('simplifies a dense circle/polygon with 60 points down to <= 8 key vertices', () => {
    // Generate a dense circle with 60 points
    const denseCoords: LatLng[] = [];
    const centerLat = 11.082;
    const centerLng = 77.12;
    const radius = 0.005;

    for (let i = 0; i < 60; i++) {
      const angle = (i / 60) * 2 * Math.PI;
      denseCoords.push({
        latitude: centerLat + radius * Math.sin(angle),
        longitude: centerLng + radius * Math.cos(angle),
      });
    }

    const simplified = simplifyPolygonForEditing(denseCoords, 8, 4);

    expect(simplified.length).toBeLessThanOrEqual(8);
    expect(simplified.length).toBeGreaterThanOrEqual(4);
  });

  it('preserves small polygons that already have minimal vertices (e.g. 4 or 5 points)', () => {
    const quadCoords: LatLng[] = [
      { latitude: 11.08, longitude: 77.12 },
      { latitude: 11.09, longitude: 77.12 },
      { latitude: 11.09, longitude: 77.13 },
      { latitude: 11.08, longitude: 77.13 },
    ];

    const simplified = simplifyPolygonForEditing(quadCoords, 8, 4);
    expect(simplified.length).toBe(4);
  });

  it('handles closed polygon rings with duplicate closing coordinates gracefully', () => {
    const closedRing: LatLng[] = [
      { latitude: 11.08, longitude: 77.12 },
      { latitude: 11.085, longitude: 77.12 },
      { latitude: 11.09, longitude: 77.12 },
      { latitude: 11.09, longitude: 77.125 },
      { latitude: 11.09, longitude: 77.13 },
      { latitude: 11.085, longitude: 77.13 },
      { latitude: 11.08, longitude: 77.13 },
      { latitude: 11.08, longitude: 77.125 },
      { latitude: 11.08, longitude: 77.12 }, // closing point
    ];

    const simplified = simplifyPolygonForEditing(closedRing, 6, 4);
    expect(simplified.length).toBeLessThanOrEqual(6);
    expect(simplified.length).toBeGreaterThanOrEqual(4);
  });

  it('handles empty or small coordinate arrays safely', () => {
    expect(simplifyPolygonForEditing([])).toEqual([]);
    const triangle: LatLng[] = [
      { latitude: 11.08, longitude: 77.12 },
      { latitude: 11.09, longitude: 77.12 },
      { latitude: 11.08, longitude: 77.13 },
    ];
    expect(simplifyPolygonForEditing(triangle, 8, 4)).toEqual(triangle);
  });
});
