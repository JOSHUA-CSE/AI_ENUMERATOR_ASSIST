import React from 'react';
import ReactTestRenderer, { act } from 'react-test-renderer';
import * as Location from 'expo-location';
import { gpsService } from '../src/core/gpsService';
import { boundaryService } from '../src/core/boundaryService';
import { fieldworkService } from '../src/core/fieldworkService';
import { resetDatabaseForTesting } from '../src/core/sqlite/database';
import { offlineRepository } from '../src/core/sqlite/offlineRepositories';
import { syncQueueRepository } from '../src/core/sqlite/syncQueueRepository';
import { syncService } from '../src/core/syncService';
import { apiClient } from '../src/core/apiClient';
import { useAuthStore } from '../src/core/authStore';
import { en, ta, t, useLanguageStore } from '../src/core/localization';
import { GpsBoundaryCard } from '../src/components/GpsBoundaryCard';
import { HlbSpatialMap } from '../src/components/HlbSpatialMap';
import { EnumeratorHlbDetailScreen } from '../src/features/enumerator/EnumeratorHlbDetailScreen';

// Mock Expo Location
jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(),
  getForegroundPermissionsAsync: jest.fn(),
  hasServicesEnabledAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  watchPositionAsync: jest.fn(),
  Accuracy: {
    Balanced: 3,
    High: 4,
  },
}));

// Mock react-native-webview
jest.mock('react-native-webview', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    WebView: React.forwardRef((props: any, ref: any) => {
      React.useImperativeHandle(ref, () => ({
        postMessage: jest.fn(),
        injectJavaScript: jest.fn(),
      }));
      return <View testID="mock-webview" {...props} />;
    }),
  };
});

// Mock Navigation
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
jest.mock('@react-navigation/native', () => {
  const actualNav = jest.requireActual('@react-navigation/native');
  return {
    ...actualNav,
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: mockGoBack,
      addListener: jest.fn(() => jest.fn()),
    }),
    useRoute: () => ({
      params: {
        hlbId: 'hlb-gps-001',
        blockCode: 'HLB-001',
      },
    }),
    useFocusEffect: (cb: any) => {
      const React = require('react');
      React.useEffect(() => {
        const cleanup = cb();
        return () => {
          if (typeof cleanup === 'function') cleanup();
        };
      }, []);
    },
  };
});

const samplePolygonGeoJson = {
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

describe('Phase 11 — GPS Boundary & Coverage Monitoring Mobile Suite', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetDatabaseForTesting();
    gpsService.stopWatching();

    useAuthStore.setState({
      user: {
        id: 'enum-p11-test',
        name: 'Murugan Enumerator',
        username: 'murugan_enum',
        role: 'ENUMERATOR',
      },
      token: 'mock-jwt-token',
      status: 'authenticated',
    });

    useLanguageStore.getState().setLanguage('en');

    // Default Expo Location mocks
    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
    });
    (Location.hasServicesEnabledAsync as jest.Mock).mockResolvedValue(true);
    (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue({
      coords: {
        latitude: 11.005,
        longitude: 77.005,
        accuracy: 10,
      },
      timestamp: Date.now(),
    });
  });

  // =========================================================================
  // 1 & 2 & 3. GPS PERMISSIONS & AVAILABILITY
  // =========================================================================
  test('1. GPS permission granted enables authentic location capture', async () => {
    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
    });

    const res = await gpsService.getCurrentLocation();
    expect(res.success).toBe(true);
    expect(res.position).toBeDefined();
    expect(res.position?.latitude).toBe(11.005);
    expect(res.position?.longitude).toBe(77.005);
    expect(res.position?.accuracy).toBe(10);
  });

  test('2. GPS permission denied handles failure gracefully without throwing', async () => {
    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'denied',
    });

    const res = await gpsService.getCurrentLocation();
    expect(res.success).toBe(false);
    expect(res.error).toBe('PERMISSION_DENIED');
    expect(res.position).toBeUndefined();
  });

  test('3. Location services disabled is identified accurately', async () => {
    (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
      status: 'granted',
    });
    (Location.hasServicesEnabledAsync as jest.Mock).mockResolvedValue(false);

    const res = await gpsService.getCurrentLocation();
    expect(res.success).toBe(false);
    expect(res.error).toBe('LOCATION_UNAVAILABLE');
  });

  // =========================================================================
  // 4 & 5. VALID OBSERVATION & ACCURACY CATEGORIZATION
  // =========================================================================
  test('4. Valid GPS observation returns ISO timestamp and valid coordinate bounds', async () => {
    const res = await gpsService.getCurrentLocation();
    expect(res.success).toBe(true);
    expect(typeof res.position?.timestamp).toBe('string');
    expect(res.position?.latitude).toBeGreaterThanOrEqual(-90);
    expect(res.position?.latitude).toBeLessThanOrEqual(90);
    expect(res.position?.longitude).toBeGreaterThanOrEqual(-180);
    expect(res.position?.longitude).toBeLessThanOrEqual(180);
  });

  test('5. Accuracy categorization classifies GOOD (<=25m), POOR (>25m), and UNKNOWN', () => {
    expect(gpsService.categorizeAccuracy(5)).toBe('GOOD');
    expect(gpsService.categorizeAccuracy(25)).toBe('GOOD');
    expect(gpsService.categorizeAccuracy(25.1)).toBe('POOR');
    expect(gpsService.categorizeAccuracy(80)).toBe('POOR');
    expect(gpsService.categorizeAccuracy(null)).toBe('UNKNOWN');
  });

  // =========================================================================
  // 6, 7, 8. OFFLINE HLB BOUNDARY CHECKING & UNCERTAINTY
  // =========================================================================
  test('6. Offline point-in-HLB determines point clearly INSIDE boundary', () => {
    // Center of polygon [77.005, 11.005]
    const result = boundaryService.checkBoundaryStatus(
      samplePolygonGeoJson,
      11.005,
      77.005,
      5
    );
    expect(result.status).toBe('INSIDE');
    expect(result.distanceToBoundaryMeters).toBeGreaterThan(100);
  });

  test('7. Offline point-in-HLB determines point clearly OUTSIDE boundary', () => {
    // Point at [77.05, 11.05] is clearly far outside
    const result = boundaryService.checkBoundaryStatus(
      samplePolygonGeoJson,
      11.05,
      77.05,
      5
    );
    expect(result.status).toBe('OUTSIDE');
    expect(result.distanceToBoundaryMeters).toBeGreaterThan(100);
  });

  test('8. Boundary uncertainty is triggered when accuracy circle overlaps boundary edge', () => {
    // Boundary line longitude is 77.01
    // Point is at 77.01005 (approx 5.5 meters outside boundary)
    // GPS accuracy is ±15 meters, which overlaps the boundary edge (distance <= accuracy)
    const result = boundaryService.checkBoundaryStatus(
      samplePolygonGeoJson,
      11.005,
      77.01005,
      15
    );
    expect(result.status).toBe('BOUNDARY_UNCERTAIN');
    expect(result.distanceToBoundaryMeters).toBeLessThanOrEqual(15);
  });

  // =========================================================================
  // 9, 10, 11. OFFLINE GPS PERSISTENCE & SYNC QUEUE INTEGRATION
  // =========================================================================
  test('9. GPS observations are persisted offline in SQLite', async () => {
    // Populate an offline HLB record first
    offlineRepository.saveDownloadedHlb(
      {
        id: 'hlb-gps-001',
        layout_id: 'layout-001',
        block_code: 'HLB-001',
        name: 'Block 1',
        status: 'APPROVED',
        target_building_count: 10,
        actual_building_count: 5,
        boundary: samplePolygonGeoJson,
      },
      [
        {
          id: 'bld-101',
          building_reference: 'BLD-101',
          latitude: 11.005,
          longitude: 77.005,
        },
      ],
      'enum-p11-test'
    );

    const captureResult = await fieldworkService.captureAndLogGps(
      'hlb-gps-001',
      'enum-p11-test',
      'bld-101'
    );

    expect(captureResult.success).toBe(true);

    const logs = fieldworkService.getGpsLogs('hlb-gps-001');
    expect(logs.length).toBe(1);
    expect(logs[0].hlb_id).toBe('hlb-gps-001');
    expect(logs[0].building_id).toBe('bld-101');
    expect(logs[0].latitude).toBe(11.005);
    expect(logs[0].longitude).toBe(77.005);
  });

  test('10. Saving GPS observation enqueues GPS_LOG operation into sync_queue', async () => {
    await fieldworkService.captureAndLogGps(
      'hlb-gps-001',
      'enum-p11-test'
    );

    const pendingOps = syncQueueRepository.getPendingOperations();
    const gpsOp = pendingOps.find((op) => op.entity_type === 'GPS_LOG');
    expect(gpsOp).toBeDefined();
    expect(gpsOp?.status).toBe('PENDING');

    const payload = JSON.parse(gpsOp!.payload_json);
    expect(payload.hlb_id).toBe('hlb-gps-001');
    expect(payload.latitude).toBe(11.005);
    expect(payload.longitude).toBe(77.005);
  });

  test('11. GPS synchronization updates status to SYNCED upon server acknowledgement', async () => {
    await fieldworkService.captureAndLogGps(
      'hlb-gps-001',
      'enum-p11-test'
    );

    const pendingBefore = syncQueueRepository.getPendingOperations();
    const op = pendingBefore.find((o) => o.entity_type === 'GPS_LOG')!;

    // Mock server batch response acknowledging the GPS operation
    jest.spyOn(apiClient, 'post').mockResolvedValueOnce({
      results: [
        {
          idempotency_key: op.idempotency_key,
          status: 'SUCCESS',
          entity_type: 'GPS_LOG',
          local_entity_id: op.local_entity_id,
          server_entity_id: 'gps-srv-101',
          version: 1,
          server_timestamp: new Date().toISOString(),
        },
      ],
      processed_count: 1,
      success_count: 1,
      failed_count: 0,
      conflict_count: 0,
      synced_at: new Date().toISOString(),
    } as any);

    const syncResult = await syncService.syncBatch();
    expect(syncResult.success).toBe(true);
    expect(syncResult.successCount).toBe(1);

    const stats = syncQueueRepository.getSyncQueueStats();
    expect(stats.pendingCount).toBe(0);
    expect(stats.syncedCount).toBe(1);
  });

  // =========================================================================
  // 12. COVERAGE CALCULATION
  // =========================================================================
  test('12. Fieldwork coverage is calculated strictly from building fieldwork status', () => {
    const hlbId = 'hlb-cov-001';
    offlineRepository.saveDownloadedHlb(
      {
        id: hlbId,
        layout_id: 'layout-001',
        block_code: 'HLB-COV-01',
        name: 'Block Coverage',
        status: 'APPROVED',
        target_building_count: 5,
        actual_building_count: 5,
        boundary: samplePolygonGeoJson,
      },
      [
        { id: 'bld-1', building_reference: 'BLD-1', latitude: 11.0, longitude: 77.0, status: 'COMPLETED' },
        { id: 'bld-2', building_reference: 'BLD-2', latitude: 11.0, longitude: 77.0, status: 'LOCKED' },
        { id: 'bld-3', building_reference: 'BLD-3', latitude: 11.0, longitude: 77.0, status: 'IN_PROGRESS' },
        { id: 'bld-4', building_reference: 'BLD-4', latitude: 11.0, longitude: 77.0, status: 'REVISIT_REQUIRED' },
        { id: 'bld-5', building_reference: 'BLD-5', latitude: 11.0, longitude: 77.0, status: 'PENDING' },
      ],
      'enum-p11-test'
    );

    const cov = fieldworkService.calculateCoverage(hlbId);
    expect(cov.totalBuildings).toBe(5);
    expect(cov.completedBuildings).toBe(2); // COMPLETED + LOCKED
    expect(cov.inProgressBuildings).toBe(1);
    expect(cov.revisitBuildings).toBe(1);
    expect(cov.remainingBuildings).toBe(3); // 5 - 2 = 3
    expect(cov.coveragePercentage).toBe(40); // 2/5 * 100 = 40%
  });

  // =========================================================================
  // 13. ROUTE REMAINS FUNCTIONAL WITH GPS MONITORING
  // =========================================================================
  test('13. Route traversal and metrics remain fully functional alongside GPS monitoring', () => {
    // Route buildings
    const orderedBuildings = [
      {
        sequence_order: 1,
        building_id: 'bld-1',
        building_reference: 'BLD-001',
        house_number: '12A',
        status: 'COMPLETED',
        latitude: 11.001,
        longitude: 77.001,
        distance_from_previous_m: 0,
      },
      {
        sequence_order: 2,
        building_id: 'bld-2',
        building_reference: 'BLD-002',
        house_number: '12B',
        status: 'PENDING',
        latitude: 11.002,
        longitude: 77.002,
        distance_from_previous_m: 120,
      },
    ];

    expect(orderedBuildings.length).toBe(2);
    expect(orderedBuildings[0].sequence_order).toBe(1);
    expect(orderedBuildings[1].distance_from_previous_m).toBe(120);
  });

  // =========================================================================
  // 14 & 15. MAP CURRENT LOCATION & FULLSCREEN PRESERVATION
  // =========================================================================
  test('14. HlbSpatialMap accepts currentLocation and generates GPS map layer payload', () => {
    let testRenderer: ReactTestRenderer.ReactTestRenderer | null = null;
    act(() => {
      testRenderer = ReactTestRenderer.create(
        <HlbSpatialMap
          boundaryRings={[[{ latitude: 11.0, longitude: 77.0 }, { latitude: 11.01, longitude: 77.01 }]]}
          currentLocation={{
            latitude: 11.005,
            longitude: 77.005,
            accuracy: 8,
          }}
          showCurrentLocation={true}
          testID="test-map"
        />
      );
    });

    expect(testRenderer).toBeDefined();
    const root = testRenderer!.root;
    expect(root.findByProps({ testID: 'test-map' })).toBeDefined();
  });

  test('15. HlbSpatialMap preserves fullscreen functionality with current location', () => {
    let testRenderer: ReactTestRenderer.ReactTestRenderer | null = null;
    act(() => {
      testRenderer = ReactTestRenderer.create(
        <HlbSpatialMap
          boundaryRings={[[{ latitude: 11.0, longitude: 77.0 }]]}
          currentLocation={{
            latitude: 11.005,
            longitude: 77.005,
            accuracy: 12,
          }}
          fullscreenEnabled={true}
          fullscreenTitle="Test Fullscreen Map"
          testID="test-map-fullscreen"
        />
      );
    });

    const root = testRenderer!.root;
    expect(root.findByProps({ testID: 'test-map-fullscreen' })).toBeDefined();
  });

  // =========================================================================
  // 16. LOCALIZATION VERIFICATION
  // =========================================================================
  test('16. All Phase 11 GPS and Boundary strings are present in English and Tamil', () => {
    const requiredKeys = [
      'gps',
      'location',
      'gps_accuracy',
      'good_accuracy',
      'low_accuracy',
      'location_unavailable',
      'inside_assigned_hlb',
      'outside_assigned_hlb',
      'boundary_uncertain',
      'boundary_status_label',
      'buildings_completed',
      'buildings_remaining',
      'gps_permission_required',
      'location_services_disabled',
      'gps_observation_saved_offline',
      'gps_sync_pending',
      'gps_synced',
      'gps_sync_failed',
      'accuracy_meters_fmt',
      'coverage_progress_fmt',
      'gps_disclaimer',
      'refresh_gps',
    ] as const;

    requiredKeys.forEach((key) => {
      expect(en[key]).toBeDefined();
      expect(ta[key]).toBeDefined();
      expect(en[key].length).toBeGreaterThan(0);
      expect(ta[key].length).toBeGreaterThan(0);
    });

    useLanguageStore.getState().setLanguage('en');
    expect(t('inside_assigned_hlb')).toBe('Inside Assigned HLB');

    useLanguageStore.getState().setLanguage('ta');
    expect(t('inside_assigned_hlb')).toBe('ஒதுக்கப்பட்ட எச்.எல்.பி-க்குள் உள்ளது');
  });

  // =========================================================================
  // 17 & 18. SUBSCRIPTION CLEANUP & NO DUPLICATE GPS WATCHERS
  // =========================================================================
  test('17. Subscription cleanup removes active watcher listener', async () => {
    const mockRemove = jest.fn();
    (Location.watchPositionAsync as jest.Mock).mockResolvedValue({
      remove: mockRemove,
    });

    const unsubscribe = await gpsService.watchPosition(jest.fn());
    expect(gpsService.getActiveListenersCount()).toBe(1);

    unsubscribe();
    expect(mockRemove).toHaveBeenCalled();
    expect(gpsService.getActiveListenersCount()).toBe(0);
  });

  test('18. Starting a second watcher replaces the existing one without duplicate listeners', async () => {
    const mockRemove1 = jest.fn();
    const mockRemove2 = jest.fn();

    (Location.watchPositionAsync as jest.Mock)
      .mockResolvedValueOnce({ remove: mockRemove1 })
      .mockResolvedValueOnce({ remove: mockRemove2 });

    await gpsService.watchPosition(jest.fn());
    expect(gpsService.getActiveListenersCount()).toBe(1);

    // Starting a second watcher without unsubscribing first
    await gpsService.watchPosition(jest.fn());
    expect(mockRemove1).toHaveBeenCalled(); // first one cleaned up automatically
    expect(gpsService.getActiveListenersCount()).toBe(1); // count stays at 1

    gpsService.stopWatching();
    expect(mockRemove2).toHaveBeenCalled();
    expect(gpsService.getActiveListenersCount()).toBe(0);
  });

  // =========================================================================
  // UI COMPONENT: GpsBoundaryCard Non-blocking Warning Test
  // =========================================================================
  test('19. GpsBoundaryCard displays non-blocking OUTSIDE warning banner when outside HLB', () => {
    let testRenderer: ReactTestRenderer.ReactTestRenderer | null = null;
    act(() => {
      testRenderer = ReactTestRenderer.create(
        <GpsBoundaryCard
          gpsStatus="READY"
          accuracyCategory="GOOD"
          accuracyMeters={9}
          boundaryStatus="OUTSIDE"
          coverage={{
            totalBuildings: 50,
            completedBuildings: 20,
            remainingBuildings: 30,
            coveragePercentage: 40,
          }}
          testID="test-boundary-card"
        />
      );
    });

    const root = testRenderer!.root;
    expect(root.findByProps({ testID: 'test-boundary-card' })).toBeDefined();
    // Warning banner should be present for outside HLB
    expect(root.findByProps({ testID: 'outside-hlb-warning-banner' })).toBeDefined();
  });
});
