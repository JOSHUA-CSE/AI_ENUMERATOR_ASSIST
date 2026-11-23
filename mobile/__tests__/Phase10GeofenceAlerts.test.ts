import { boundaryService } from '../src/core/boundaryService';
import { routeService } from '../src/core/routeService';
import { apiClient } from '../src/core/apiClient';

jest.mock('../src/core/apiClient', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
    patch: jest.fn(),
    put: jest.fn(),
    delete: jest.fn(),
  },
  extractErrorMessage: (err: any) => (err?.message ? err.message : String(err)),
}));

const mockApiClient = apiClient as jest.Mocked<typeof apiClient>;

describe('Phase 10 — Mobile Geofencing, Boundary Alerts & Traversal Services', () => {
  const sampleSquareBoundary = {
    type: 'Polygon',
    coordinates: [
      [
        [77.0, 11.0],
        [77.01, 11.0],
        [77.01, 11.01],
        [77.0, 11.01],
        [77.0, 11.0],
      ],
    ],
  };

  beforeEach(() => {
    jest.clearAllMocks();
    boundaryService.resetTransitionState();
  });

  describe('boundaryService.evaluateBoundaryTransition', () => {
    it('detects point inside HLB with good accuracy', () => {
      const insidePoint = { latitude: 11.005, longitude: 77.005, accuracy: 8.0 };
      const res = boundaryService.evaluateBoundaryTransition(
        insidePoint,
        sampleSquareBoundary,
        'hlb-p10-test'
      );

      expect(res.status).toBe('INSIDE');
      expect(res.distanceToBoundaryMeters).toBeGreaterThan(0);
      expect(mockApiClient.post).not.toHaveBeenCalled();
    });

    it('requires consecutive outside fixes to filter GPS jitter before firing exit alert', () => {
      const exitAlertFn = jest.fn();
      const reEntryFn = jest.fn();
      const outsidePoint = { latitude: 11.02, longitude: 77.02, accuracy: 10.0 };

      // 1st fix outside: consecutive count = 1, should NOT trigger alert yet
      const firstFix = boundaryService.evaluateBoundaryTransition(
        outsidePoint,
        sampleSquareBoundary,
        'hlb-p10-test',
        exitAlertFn,
        reEntryFn
      );
      expect(firstFix.status).toBe('OUTSIDE');
      expect(exitAlertFn).not.toHaveBeenCalled();
      expect(mockApiClient.post).not.toHaveBeenCalled();

      // 2nd consecutive fix outside: threshold met, fires alert & submits boundary event
      const secondFix = boundaryService.evaluateBoundaryTransition(
        outsidePoint,
        sampleSquareBoundary,
        'hlb-p10-test',
        exitAlertFn,
        reEntryFn
      );
      expect(secondFix.status).toBe('OUTSIDE');
      expect(exitAlertFn).toHaveBeenCalledTimes(1);
      expect(exitAlertFn).toHaveBeenCalledWith(expect.stringContaining('HLB Boundary Alert'));
      expect(mockApiClient.post).toHaveBeenCalledWith(
        '/hlbs/hlb-p10-test/gps/boundary-event',
        expect.objectContaining({
          event_type: 'EXIT',
          latitude: 11.02,
          longitude: 77.02,
          accuracy_meters: 10.0,
        })
      );
    });

    it('prevents repeated alert spam during 30s cooldown when remaining outside', () => {
      const exitAlertFn = jest.fn();
      const outsidePoint = { latitude: 11.02, longitude: 77.02, accuracy: 10.0 };

      // 1st fix
      boundaryService.evaluateBoundaryTransition(outsidePoint, sampleSquareBoundary, 'hlb-p10-test', exitAlertFn);
      // 2nd fix (fires alert)
      boundaryService.evaluateBoundaryTransition(outsidePoint, sampleSquareBoundary, 'hlb-p10-test', exitAlertFn);
      expect(exitAlertFn).toHaveBeenCalledTimes(1);

      // 3rd & 4th fixes immediately after (within cooldown)
      boundaryService.evaluateBoundaryTransition(outsidePoint, sampleSquareBoundary, 'hlb-p10-test', exitAlertFn);
      boundaryService.evaluateBoundaryTransition(outsidePoint, sampleSquareBoundary, 'hlb-p10-test', exitAlertFn);
      expect(exitAlertFn).toHaveBeenCalledTimes(1); // Still 1, cooldown prevented spam
    });

    it('confirms re-entry when enumerator returns inside HLB', () => {
      const exitAlertFn = jest.fn();
      const reEntryFn = jest.fn();
      const outsidePoint = { latitude: 11.02, longitude: 77.02, accuracy: 10.0 };
      const insidePoint = { latitude: 11.005, longitude: 77.005, accuracy: 8.0 };

      // Transition outside
      boundaryService.evaluateBoundaryTransition(outsidePoint, sampleSquareBoundary, 'hlb-p10-test', exitAlertFn, reEntryFn);
      boundaryService.evaluateBoundaryTransition(outsidePoint, sampleSquareBoundary, 'hlb-p10-test', exitAlertFn, reEntryFn);
      expect(exitAlertFn).toHaveBeenCalledTimes(1);

      // Re-enter inside
      const insideRes = boundaryService.evaluateBoundaryTransition(insidePoint, sampleSquareBoundary, 'hlb-p10-test', exitAlertFn, reEntryFn);
      expect(insideRes.status).toBe('INSIDE');
      expect(reEntryFn).toHaveBeenCalledTimes(1);
      expect(reEntryFn).toHaveBeenCalledWith(expect.stringContaining('Re-entry confirmed'));
      expect(mockApiClient.post).toHaveBeenCalledWith(
        '/hlbs/hlb-p10-test/gps/boundary-event',
        expect.objectContaining({
          event_type: 'ENTRY',
          latitude: 11.005,
          longitude: 77.005,
        })
      );
    });

    it('flags GPS_UNCERTAIN when horizontal accuracy > 75m', () => {
      const poorAccPoint = { latitude: 11.005, longitude: 77.005, accuracy: 80.0 };
      const res = boundaryService.evaluateBoundaryTransition(
        poorAccPoint,
        sampleSquareBoundary,
        'hlb-p10-test'
      );
      expect(res.status).toBe('GPS_UNCERTAIN');
    });
  });

  describe('routeService Traversal & Missed Roads API Client calls', () => {
    it('startTraversal invokes start endpoint with coordinates and accuracy', async () => {
      mockApiClient.post.mockResolvedValueOnce({
        status: 'TRAVERSAL_STARTED',
        hlb_id: 'hlb-100',
        is_inside_hlb: true,
        message: 'Started',
      });

      const res = await routeService.startTraversal('hlb-100', 11.002, 77.002, 12.0);
      expect(mockApiClient.post).toHaveBeenCalledWith('/hlbs/hlb-100/route/traversal/start', {
        current_latitude: 11.002,
        current_longitude: 77.002,
        accuracy_meters: 12.0,
        device_id: null,
      });
      expect(res.status).toBe('TRAVERSAL_STARTED');
    });

    it('resumeTraversal invokes resume endpoint with coordinates and accuracy', async () => {
      mockApiClient.post.mockResolvedValueOnce({
        status: 'TRAVERSAL_RESUMED',
        hlb_id: 'hlb-100',
        is_inside_hlb: true,
        message: 'Resumed',
      });

      const res = await routeService.resumeTraversal('hlb-100', 11.002, 77.002, 8.5);
      expect(mockApiClient.post).toHaveBeenCalledWith('/hlbs/hlb-100/route/traversal/resume', {
        current_latitude: 11.002,
        current_longitude: 77.002,
        accuracy_meters: 8.5,
        device_id: null,
      });
      expect(res.status).toBe('TRAVERSAL_RESUMED');
    });

    it('getMissedRoads retrieves unvisited edges from backend', async () => {
      mockApiClient.get.mockResolvedValueOnce({
        hlb_id: 'hlb-100',
        total_required_edges: 5,
        missed_edges_count: 2,
        total_missed_length_m: 230.5,
        missed_roads: [
          {
            edge_id: 'e1',
            road_name: 'Cross Street 1',
            highway_type: 'residential',
            length_meters: 120.0,
            completion_percentage: 0.0,
            status: 'UNVISITED',
            reason: 'Road segment was not traversed',
            center_lat: 11.003,
            center_lon: 77.003,
            coordinates: [[11.002, 77.002], [11.004, 77.004]],
          },
        ],
      });

      const res = await routeService.getMissedRoads('hlb-100');
      expect(mockApiClient.get).toHaveBeenCalledWith('/hlbs/hlb-100/route/missed-roads');
      expect(res.missed_edges_count).toBe(2);
      expect(res.missed_roads[0].road_name).toBe('Cross Street 1');
    });
  });
});

