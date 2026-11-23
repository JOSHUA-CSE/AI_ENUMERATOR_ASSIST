import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { EnumeratorHlbDetailScreen } from '../src/features/enumerator/EnumeratorHlbDetailScreen';
import { BuildingDetailScreen } from '../src/features/enumerator/BuildingDetailScreen';
import {
  routeService,
  haversineDistanceMeters,
  calculateDistanceMatrix,
  calculatePathDistanceKm,
  optimizeBuildingsLocally,
} from '../src/core/routeService';
import { offlineRepository } from '../src/core/sqlite/offlineRepositories';
import { resetDatabaseForTesting } from '../src/core/sqlite/database';
import type { OfflineBuildingRecord } from '../src/core/sqlite/types';

const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
let mockRouteParams: any = {
  hlbId: 'hlb-p7-test-100',
  blockCode: 'HLB-P7-100',
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

jest.mock('../src/components/HlbSpatialMap', () => {
  const ReactLocal = require('react');
  const { View } = require('react-native');
  return {
    HlbSpatialMap: (props: any) => <View testID={props.testID || 'hlb-spatial-map'} />,
  };
});

jest.mock('../src/core/authStore', () => ({
  useAuthStore: () => ({
    user: { id: 'enum-p7-user-1', name: 'Ravi Kumar', role: 'ENUMERATOR' },
  }),
}));

describe('Phase 7 — Route Optimization Mobile UI and Offline Engine', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetDatabaseForTesting();
    mockRouteParams = {
      hlbId: 'hlb-p7-test-100',
      blockCode: 'HLB-P7-100',
    };
  });

  // 1. Offline Engine: FALSE_DETECTION Exclusion and Return-to-Start
  test('Local optimization excludes FALSE_DETECTION buildings and supports returnToStart', () => {
    const buildings: OfflineBuildingRecord[] = [
      {
        id: 'b1',
        hlb_id: 'hlb-1',
        building_reference: 'BLD-001',
        house_number: '1',
        latitude: 11.080,
        longitude: 77.080,
        footprint_geojson: null,
        source_type: 'SATELLITE',
        field_status: 'CONFIRMED',
        status: 'PENDING',
        household_count: 0,
        last_updated_at: new Date().toISOString(),
      },
      {
        id: 'b2_ghost',
        hlb_id: 'hlb-1',
        building_reference: 'BLD-002-GHOST',
        house_number: '2',
        latitude: 11.085,
        longitude: 77.085,
        footprint_geojson: null,
        source_type: 'SATELLITE',
        field_status: 'FALSE_DETECTION',
        status: 'PENDING',
        household_count: 0,
        last_updated_at: new Date().toISOString(),
      },
      {
        id: 'b3',
        hlb_id: 'hlb-1',
        building_reference: 'BLD-003',
        house_number: '3',
        latitude: 11.090,
        longitude: 77.090,
        footprint_geojson: null,
        source_type: 'SATELLITE',
        field_status: 'CONFIRMED',
        status: 'PENDING',
        household_count: 0,
        last_updated_at: new Date().toISOString(),
      },
    ];

    // Open route
    const resOpen = optimizeBuildingsLocally(buildings, { latitude: 11.080, longitude: 77.080 }, false);
    expect(resOpen.orderedBuildings.length).toBe(2);
    expect(resOpen.orderedBuildings.some((b) => b.building_id === 'b2_ghost')).toBe(false);

    // Closed route
    const resClosed = optimizeBuildingsLocally(buildings, { latitude: 11.080, longitude: 77.080 }, true);
    expect(resClosed.orderedBuildings.length).toBe(2);
    expect(resClosed.totalDistanceKm).toBeGreaterThan(resOpen.totalDistanceKm);
  });

  // 2. Mobile Route Tab: Displays routing method badge, return-to-start toggle, and navigate next
  test('Route Tab displays routing method badge, return toggle, and next building button', async () => {
    const hlbId = 'hlb-p7-test-100';
    const enumId = 'enum-p7-user-1';

    offlineRepository.saveDownloadedHlb(
      {
        id: hlbId,
        layout_id: 'layout-p7',
        layout_name: 'Arasur North',
        area_name: 'Arasur',
        block_code: 'HLB-P7-100',
        name: 'Block 100',
        status: 'APPROVED',
        target_building_count: 120,
        actual_building_count: 2,
        boundary: {
          type: 'Polygon',
          coordinates: [
            [
              [77.08, 11.08],
              [77.12, 11.08],
              [77.12, 11.12],
              [77.08, 11.12],
              [77.08, 11.08],
            ],
          ],
        },
      },
      [
        {
          id: 'bld-p7-1',
          building_reference: 'BLD-001',
          house_number: '1',
          latitude: 11.090,
          longitude: 77.090,
          footprint: null,
          source_type: 'SATELLITE',
          status: 'COMPLETED',
        },
        {
          id: 'bld-p7-2',
          building_reference: 'BLD-002',
          house_number: '2',
          latitude: 11.095,
          longitude: 77.095,
          footprint: null,
          source_type: 'SATELLITE',
          status: 'PENDING',
        },
      ],
      enumId
    );

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<EnumeratorHlbDetailScreen />);
    });

    const root = component.root;
    const routeTab = root.findByProps({ testID: 'tab-route-btn' });

    await ReactTestRenderer.act(async () => {
      routeTab.props.onPress();
    });

    // Check routing method badge
    expect(root.findByProps({ testID: 'routing-method-badge' })).toBeDefined();

    // Check return to start toggle
    const toggleReturn = root.findByProps({ testID: 'toggle-return-to-start' });
    expect(toggleReturn).toBeDefined();

    // Toggle return to start
    await ReactTestRenderer.act(async () => {
      toggleReturn.props.onPress();
    });

    // Check next building button
    const nextBtn = root.findByProps({ testID: 'btn-navigate-next-building' });
    expect(nextBtn).toBeDefined();

    await ReactTestRenderer.act(async () => {
      nextBtn.props.onPress();
    });

    // Must navigate to bld-p7-2 (pending building)
    expect(mockNavigate).toHaveBeenCalledWith('BuildingDetail', {
      buildingId: 'bld-p7-2',
      hlbId: 'hlb-p7-test-100',
      blockCode: 'HLB-P7-100',
    });
  });

  // 3. BuildingDetailScreen: Skip Building Action
  test('BuildingDetailScreen offers Skip Building action', async () => {
    mockRouteParams = {
      buildingId: 'bld-p7-2',
      hlbId: 'hlb-p7-test-100',
      blockCode: 'HLB-P7-100',
    };

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<BuildingDetailScreen />);
    });

    const root = component.root;
    const skipBtn = root.findByProps({ testID: 'skip-building-btn' });
    expect(skipBtn).toBeDefined();

    // Pressing skip building opens modal
    await ReactTestRenderer.act(async () => {
      skipBtn.props.onPress();
    });

    expect(root.findByProps({ testID: 'revisit-notes-input' })).toBeDefined();
  });
});

