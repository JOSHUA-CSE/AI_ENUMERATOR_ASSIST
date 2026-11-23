import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { Linking } from 'react-native';
import { roadCoverageService } from '../src/core/roadCoverageService';
import { apiClient } from '../src/core/apiClient';

jest.mock('../src/core/apiClient');
jest.mock('../src/core/secureStore', () => ({
  secureStore: {
    getItem: jest.fn().mockResolvedValue(null),
    setItem: jest.fn().mockResolvedValue(undefined),
    removeItem: jest.fn().mockResolvedValue(undefined),
  },
}));

describe('Phase 8 — Mobile Road-Network Navigation and Coverage Service', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('fetchRoadCoverageRoute retrieves road network route and saves to local cache', async () => {
    const mockRouteData = {
      route_id: 'test-route-1',
      hlb_id: 'hlb-test-1',
      network_version: 'OSM_OVERPASS_V1',
      acquisition_date: '2026-11-11T09:42:04Z',
      total_distance_km: 3.45,
      estimated_walking_time_minutes: 46.0,
      total_segments_count: 24,
      surveyed_segments_count: 6,
      coverage_percentage: 25.0,
      sections: [],
      continuous_polyline: [[11.082, 77.120], [11.083, 77.121]],
      all_road_segments: [
        {
          segment_id: 'seg_1',
          coordinates: [[11.082, 77.120], [11.083, 77.121]],
          length_m: 140.0,
          highway: 'residential',
          is_surveyed: true,
          survey_status: 'SURVEYED',
        },
      ],
      disconnected_components_count: 1,
      warnings: [],
      generated_at: '2026-11-12T00:00:00Z',
    };

    (apiClient.post as jest.Mock).mockResolvedValueOnce(mockRouteData);

    const result = await roadCoverageService.fetchRoadCoverageRoute('hlb-test-1', null, false);

    expect(apiClient.post).toHaveBeenCalledWith(
      '/hlbs/hlb-test-1/route/coverage',
      expect.objectContaining({ return_to_start: false })
    );
    expect(result).toEqual(mockRouteData);
    expect(result.total_distance_km).toBe(3.45);
    expect(result.coverage_percentage).toBe(25.0);
  });

  test('checkRouteDeviation accurately flags deviation > 50m and passes within 20m', () => {
    const polyline: [number, number][] = [
      [11.082000, 77.120000],
      [11.082500, 77.120000],
      [11.083000, 77.120000],
    ];

    // Coordinate right on the route
    const onRoute = roadCoverageService.checkRouteDeviation(11.082200, 77.120000, polyline, 50.0);
    expect(onRoute.isDeviated).toBe(false);
    expect(onRoute.deviationDistanceM).toBeLessThan(15.0);

    // Coordinate ~150 meters west of the route
    const farOff = roadCoverageService.checkRouteDeviation(11.082200, 77.118500, polyline, 50.0);
    expect(farOff.isDeviated).toBe(true);
    expect(farOff.deviationDistanceM).toBeGreaterThan(50.0);
    expect(farOff.message).toContain('Off route');
  });

  test('trackGpsTrace submits trace coordinates with 20m tolerance', async () => {
    const mockTrackResponse = {
      hlb_id: 'hlb-test-1',
      total_segments_count: 10,
      surveyed_segments_count: 5,
      coverage_percentage: 50.0,
      updated_segments: ['seg_1', 'seg_2'],
    };

    (apiClient.post as jest.Mock).mockResolvedValueOnce(mockTrackResponse);

    const result = await roadCoverageService.trackGpsTrace(
      'hlb-test-1',
      [{ latitude: 11.082, longitude: 77.120, accuracy: 5.0 }],
      'device-001'
    );

    expect(apiClient.post).toHaveBeenCalledWith(
      '/hlbs/hlb-test-1/route/coverage/track',
      expect.objectContaining({
        tolerance_meters: 20.0,
        device_id: 'device-001',
      })
    );
    expect(result.coverage_percentage).toBe(50.0);
  });

  test('discoverBuilding submits new building structure for audit review', async () => {
    const mockDiscoveryResponse = {
      building_id: 'bld-new-disc-1',
      building_reference: 'DISC-2026-0001',
      hlb_id: 'hlb-test-1',
      latitude: 11.0825,
      longitude: 77.1215,
      source_type: 'FIELD_DISCOVERED',
      field_status: 'FIELD_ADDED',
      building_edit_id: 'edit-audit-1',
    };

    (apiClient.post as jest.Mock).mockResolvedValueOnce(mockDiscoveryResponse);

    const result = await roadCoverageService.discoverBuilding('hlb-test-1', {
      latitude: 11.0825,
      longitude: 77.1215,
      building_reference: 'DISC-2026-0001',
      house_number: '12/A',
      notes: 'New concrete dwelling',
    });

    expect(apiClient.post).toHaveBeenCalledWith(
      '/hlbs/hlb-test-1/buildings/discover',
      expect.objectContaining({
        latitude: 11.0825,
        longitude: 77.1215,
        building_reference: 'DISC-2026-0001',
      })
    );
    expect(result.source_type).toBe('FIELD_DISCOVERED');
    expect(result.field_status).toBe('FIELD_ADDED');
  });

  test('openGoogleMapsWalkingDirections opens external Google Maps intent with walking travelmode', async () => {
    const openSpy = jest.spyOn(Linking, 'openURL').mockResolvedValue(true as any);

    await roadCoverageService.openGoogleMapsWalkingDirections(11.0825, 77.1215);

    expect(openSpy).toHaveBeenCalledWith(
      'https://www.google.com/maps/dir/?api=1&destination=11.0825,77.1215&travelmode=walking'
    );
    openSpy.mockRestore();
  });
});
