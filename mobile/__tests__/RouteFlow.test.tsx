import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { EnumeratorHlbDetailScreen } from '../src/features/enumerator/EnumeratorHlbDetailScreen';
import {
  routeService,
  haversineDistanceMeters,
  calculateDistanceMatrix,
  solveTspNearestNeighbor,
  improveTsp2Opt,
  optimizeBuildingsLocally,
} from '../src/core/routeService';
import { fieldworkService } from '../src/core/fieldworkService';
import { offlineRepository } from '../src/core/sqlite/offlineRepositories';
import { resetDatabaseForTesting } from '../src/core/sqlite/database';
import { en } from '../src/core/localization/en';
import { ta } from '../src/core/localization/ta';
import type { OfflineBuildingRecord } from '../src/core/sqlite/types';

// Mock Navigation
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
let mockRouteParams: any = {
  hlbId: 'hlb-test-route-100',
  blockCode: 'HLB-ROUTE-100',
};

jest.mock('@react-navigation/native', () => {
  const actual = jest.requireActual('@react-navigation/native');
  return {
    ...actual,
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: mockGoBack,
    }),
    useRoute: () => ({
      params: mockRouteParams,
    }),
    useFocusEffect: (cb: any) => {
      const ReactLocal = require('react');
      ReactLocal.useEffect(() => {
        const cleanup = cb();
        return () => {
          if (typeof cleanup === 'function') cleanup();
        };
      }, []);
    },
  };
});

// Mock Leaflet Map component
jest.mock('../src/components/HlbSpatialMap', () => {
  const ReactLocal = require('react');
  const { View } = require('react-native');
  return {
    HlbSpatialMap: (props: any) => <View testID={props.testID || 'hlb-spatial-map'} />,
  };
});

// Auth Store mock
jest.mock('../src/core/authStore', () => ({
  useAuthStore: () => ({
    user: { id: 'enum-test-user-1', name: 'Ravi Kumar', role: 'ENUMERATOR' },
  }),
}));

describe('Phase 10 — Route Optimization Mobile Implementation', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetDatabaseForTesting();
    mockRouteParams = {
      hlbId: 'hlb-test-route-100',
      blockCode: 'HLB-ROUTE-100',
    };
  });

  // ============================================================================
  // 1. GIS & Algorithm Unit Tests
  // ============================================================================

  describe('GIS Distance and TSP Algorithms', () => {
    test('Haversine distance calculates accurate geographic straight-line distance', () => {
      // Salem (11.6643, 78.1460) to nearby coordinate (11.6743, 78.1460) ~ 1.11 km
      const distM = haversineDistanceMeters(11.6643, 78.1460, 11.6743, 78.1460);
      expect(distM).toBeGreaterThan(1100);
      expect(distM).toBeLessThan(1120);

      // Distance to identical coordinate is 0
      expect(haversineDistanceMeters(11.6643, 78.1460, 11.6643, 78.1460)).toBe(0);
    });

    test('Pairwise distance matrix is symmetric with zero diagonal', () => {
      const coords = [
        { latitude: 11.660, longitude: 78.140 },
        { latitude: 11.662, longitude: 78.142 },
        { latitude: 11.665, longitude: 78.145 },
      ];
      const matrix = calculateDistanceMatrix(coords);

      expect(matrix.length).toBe(3);
      expect(matrix[0][0]).toBe(0);
      expect(matrix[0][1]).toBe(matrix[1][0]);
      expect(matrix[0][1]).toBeGreaterThan(0);
      expect(matrix[1][2]).toBe(matrix[2][1]);
    });

    test('Nearest Neighbor + 2-Opt generates valid open TSP path with all nodes visited once', () => {
      const coords = [
        { latitude: 11.660, longitude: 78.140 },
        { latitude: 11.669, longitude: 78.149 },
        { latitude: 11.661, longitude: 78.141 },
        { latitude: 11.668, longitude: 78.148 },
        { latitude: 11.663, longitude: 78.143 },
      ];
      const matrix = calculateDistanceMatrix(coords);

      const nnPath = solveTspNearestNeighbor(coords, matrix, coords[0]);
      expect(nnPath.length).toBe(5);
      expect(new Set(nnPath).size).toBe(5);

      const optPath = improveTsp2Opt(nnPath, matrix);
      expect(optPath.length).toBe(5);
      expect(new Set(optPath).size).toBe(5);
    });

    test('Local optimization handles 0 and 1 building edge cases gracefully', () => {
      const emptyResult = optimizeBuildingsLocally([]);
      expect(emptyResult.orderedBuildings.length).toBe(0);
      expect(emptyResult.totalDistanceKm).toBe(0);
      expect(emptyResult.strategy).toBe('NONE');

      const singleBld: OfflineBuildingRecord = {
        id: 'bld-single',
        hlb_id: 'hlb-1',
        building_reference: 'BLD-001',
        house_number: '12',
        latitude: 11.664,
        longitude: 78.146,
        footprint_geojson: null,
        source_type: 'SATELLITE',
        status: 'PENDING',
        household_count: 0,
        last_updated_at: new Date().toISOString(),
      };

      const singleResult = optimizeBuildingsLocally([singleBld], {
        latitude: 11.660,
        longitude: 78.140,
      });
      expect(singleResult.orderedBuildings.length).toBe(1);
      expect(singleResult.orderedBuildings[0].sequence_order).toBe(1);
      expect(singleResult.orderedBuildings[0].building_id).toBe('bld-single');
      expect(singleResult.totalDistanceKm).toBeGreaterThan(0);
    });

    test('Optimization reduces or preserves baseline traversal distance', () => {
      const testBuildings: OfflineBuildingRecord[] = [
        {
          id: 'b1',
          hlb_id: 'hlb-1',
          building_reference: 'BLD-001',
          house_number: '1',
          latitude: 11.660,
          longitude: 78.140,
          footprint_geojson: null,
          source_type: 'SATELLITE',
          status: 'PENDING',
          household_count: 0,
          last_updated_at: new Date().toISOString(),
        },
        {
          id: 'b2',
          hlb_id: 'hlb-1',
          building_reference: 'BLD-002',
          house_number: '2',
          latitude: 11.669,
          longitude: 78.149,
          footprint_geojson: null,
          source_type: 'SATELLITE',
          status: 'PENDING',
          household_count: 0,
          last_updated_at: new Date().toISOString(),
        },
        {
          id: 'b3',
          hlb_id: 'hlb-1',
          building_reference: 'BLD-003',
          house_number: '3',
          latitude: 11.661,
          longitude: 78.141,
          footprint_geojson: null,
          source_type: 'SATELLITE',
          status: 'PENDING',
          household_count: 0,
          last_updated_at: new Date().toISOString(),
        },
        {
          id: 'b4',
          hlb_id: 'hlb-1',
          building_reference: 'BLD-004',
          house_number: '4',
          latitude: 11.668,
          longitude: 78.148,
          footprint_geojson: null,
          source_type: 'SATELLITE',
          status: 'PENDING',
          household_count: 0,
          last_updated_at: new Date().toISOString(),
        },
      ];

      const res = optimizeBuildingsLocally(testBuildings);
      expect(res.totalDistanceKm).toBeLessThanOrEqual(res.baselineDistanceKm);
      expect(res.distanceSavedKm).toBeGreaterThanOrEqual(0);
      expect(res.orderedBuildings.length).toBe(4);
    });
  });

  // ============================================================================
  // 2. Offline Route SQLite Caching & Service Integration
  // ============================================================================

  describe('Offline Route Persistence and Retrieval', () => {
    test('calculateOfflineRoute persists route to SQLite and re-retrieves it correctly', () => {
      const hlbId = 'hlb-offline-test';
      const enumId = 'enum-offline-user';

      // Seed offline HLB & buildings
      offlineRepository.saveDownloadedHlb(
        {
          id: hlbId,
          layout_id: 'layout-1',
          layout_name: 'Salem North',
          area_name: 'Salem',
          block_code: 'HLB-OFF-01',
          name: 'Block 1',
          status: 'APPROVED',
          target_building_count: 150,
          actual_building_count: 3,
          boundary: {
            type: 'Polygon',
            coordinates: [
              [
                [78.14, 11.66],
                [78.16, 11.66],
                [78.16, 11.68],
                [78.14, 11.68],
                [78.14, 11.66],
              ],
            ],
          },
        },
        [
          {
            id: 'bld-off-1',
            building_reference: 'BLD-001',
            house_number: '1',
            latitude: 11.662,
            longitude: 78.142,
            footprint: null,
            source_type: 'SATELLITE',
            status: 'PENDING',
          },
          {
            id: 'bld-off-2',
            building_reference: 'BLD-002',
            house_number: '2',
            latitude: 11.664,
            longitude: 78.144,
            footprint: null,
            source_type: 'SATELLITE',
            status: 'COMPLETED',
          },
          {
            id: 'bld-off-3',
            building_reference: 'BLD-003',
            house_number: '3',
            latitude: 11.666,
            longitude: 78.146,
            footprint: null,
            source_type: 'SATELLITE',
            status: 'PENDING',
          },
        ],
        enumId
      );

      const computed = routeService.calculateOfflineRoute(hlbId, enumId);
      expect(computed.building_count).toBe(3);
      expect(computed.ordered_buildings.length).toBe(3);

      // Verify cached read
      const cached = routeService.getOfflineRoute(hlbId);
      expect(cached).not.toBeNull();
      expect(cached?.hlb_id).toBe(hlbId);
      expect(cached?.building_count).toBe(3);
      expect(cached?.ordered_buildings[0].sequence_order).toBe(1);
    });
  });

  // ============================================================================
  // 3. UI Component & Screen Integration Tests
  // ============================================================================

  describe('EnumeratorHlbDetailScreen Route UI Flow', () => {
    beforeEach(() => {
      const hlbId = 'hlb-test-route-100';
      const enumId = 'enum-test-user-1';

      offlineRepository.saveDownloadedHlb(
        {
          id: hlbId,
          layout_id: 'layout-1',
          layout_name: 'Salem North',
          area_name: 'Salem',
          block_code: 'HLB-ROUTE-100',
          name: 'Block 100',
          status: 'APPROVED',
          target_building_count: 150,
          actual_building_count: 2,
          boundary: {
            type: 'Polygon',
            coordinates: [
              [
                [78.14, 11.66],
                [78.16, 11.66],
                [78.16, 11.68],
                [78.14, 11.68],
                [78.14, 11.66],
              ],
            ],
          },
        },
        [
          {
            id: 'bld-r-1',
            building_reference: 'BLD-001',
            house_number: '10-A',
            latitude: 11.662,
            longitude: 78.142,
            footprint: null,
            source_type: 'SATELLITE',
            status: 'COMPLETED',
          },
          {
            id: 'bld-r-2',
            building_reference: 'BLD-002',
            house_number: '10-B',
            latitude: 11.665,
            longitude: 78.145,
            footprint: null,
            source_type: 'SATELLITE',
            status: 'PENDING',
          },
        ],
        enumId
      );
    });

    test('Renders screen with BUILDINGS, ROUTE, and MAP tabs', async () => {
      let component: any;
      await ReactTestRenderer.act(async () => {
        component = ReactTestRenderer.create(<EnumeratorHlbDetailScreen />);
      });

      const root = component.root;
      expect(root.findByProps({ testID: 'enumerator-hlb-detail-screen' })).toBeDefined();
      expect(root.findByProps({ testID: 'tab-buildings-btn' })).toBeDefined();
      expect(root.findByProps({ testID: 'tab-route-btn' })).toBeDefined();
      expect(root.findByProps({ testID: 'tab-map-btn' })).toBeDefined();
    });

    test('Switching to ROUTE tab displays route metrics and traversal sequence', async () => {
      let component: any;
      await ReactTestRenderer.act(async () => {
        component = ReactTestRenderer.create(<EnumeratorHlbDetailScreen />);
      });

      const root = component.root;
      const routeTab = root.findByProps({ testID: 'tab-route-btn' });

      await ReactTestRenderer.act(async () => {
        routeTab.props.onPress();
      });

      expect(root.findByProps({ testID: 'btn-start-continue-route' })).toBeDefined();
      expect(root.findByProps({ testID: 'route-step-0' })).toBeDefined();
      expect(root.findByProps({ testID: 'route-step-1' })).toBeDefined();
    });

    test('Pressing START / CONTINUE ROUTE navigates to first pending building', async () => {
      let component: any;
      await ReactTestRenderer.act(async () => {
        component = ReactTestRenderer.create(<EnumeratorHlbDetailScreen />);
      });

      const root = component.root;
      const routeTab = root.findByProps({ testID: 'tab-route-btn' });

      await ReactTestRenderer.act(async () => {
        routeTab.props.onPress();
      });

      const startBtn = root.findByProps({ testID: 'btn-start-continue-route' });
      await ReactTestRenderer.act(async () => {
        startBtn.props.onPress();
      });

      // bld-r-1 is COMPLETED, so next pending building is bld-r-2
      expect(mockNavigate).toHaveBeenCalledWith('BuildingDetail', {
        buildingId: 'bld-r-2',
        hlbId: 'hlb-test-route-100',
        blockCode: 'HLB-ROUTE-100',
      });
    });

    test('Pressing building item in traversal list navigates to BuildingDetail', async () => {
      let component: any;
      await ReactTestRenderer.act(async () => {
        component = ReactTestRenderer.create(<EnumeratorHlbDetailScreen />);
      });

      const root = component.root;
      const routeTab = root.findByProps({ testID: 'tab-route-btn' });

      await ReactTestRenderer.act(async () => {
        routeTab.props.onPress();
      });

      const step0 = root.findByProps({ testID: 'route-step-0' });
      await ReactTestRenderer.act(async () => {
        step0.props.onPress();
      });

      expect(mockNavigate).toHaveBeenCalled();
      expect(mockNavigate.mock.calls[0][0]).toBe('BuildingDetail');
      expect(mockNavigate.mock.calls[0][1].hlbId).toBe('hlb-test-route-100');
    });
  });

  // ============================================================================
  // 4. Localization Validation Tests
  // ============================================================================

  describe('Localization Coverage for Route Optimization', () => {
    test('English and Tamil dictionaries contain all required Phase 10 keys', () => {
      const requiredKeys = [
        'route',
        'optimize_route',
        'route_ready',
        'route_distance',
        'buildings_in_route',
        'current_building',
        'start_route',
        'continue_route',
        'regenerate_route',
        'no_buildings_route',
        'route_offline',
        'route_optimization_failed',
        'route_generated',
        'route_completed',
        'baseline_distance',
        'distance_saved',
        'optimization_improvement',
        'starting_point_label',
        'route_view_tab',
      ];

      for (const key of requiredKeys) {
        expect(en[key as keyof typeof en]).toBeDefined();
        expect(typeof en[key as keyof typeof en]).toBe('string');
        expect(ta[key as keyof typeof ta]).toBeDefined();
        expect(typeof ta[key as keyof typeof ta]).toBe('string');
      }
    });
  });
});
