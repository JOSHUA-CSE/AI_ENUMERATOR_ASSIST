import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { EnumeratorDashboardScreen } from '../src/features/enumerator/EnumeratorDashboardScreen';
import { EnumeratorHlbDetailScreen } from '../src/features/enumerator/EnumeratorHlbDetailScreen';
import { EnumeratorAssignmentModal } from '../src/features/supervisor/EnumeratorAssignmentModal';
import { SupervisorLayoutDetailScreen } from '../src/features/supervisor/SupervisorLayoutDetailScreen';
import { enumeratorService } from '../src/core/enumeratorService';
import { supervisorService } from '../src/core/supervisorService';
import { layoutService } from '../src/core/layoutService';
import { areaService } from '../src/core/areaService';
import { useAuthStore } from '../src/core/authStore';

// Mock dependencies
jest.mock('@react-navigation/native', () => {
  const actual = jest.requireActual('@react-navigation/native');
  return {
    ...actual,
    useNavigation: () => ({
      navigate: jest.fn(),
      goBack: jest.fn(),
      addListener: jest.fn(() => jest.fn()),
    }),
    useRoute: () => ({
      params: {
        layoutId: 'layout-arasur-1',
        layoutName: 'VILL-638401',
        areaName: 'Arasur Village',
        areaId: 'area-arasur-1',
        hlbId: 'hlb-001',
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

jest.mock('../src/components/HlbSpatialMap', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    HlbSpatialMap: (props: any) => <View testID={props.testID || 'hlb-spatial-map'} />,
  };
});

describe('Phase 7 — HLB & Enumerator Assignment Mobile Flow', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
  });

  // ===========================================================================
  // 1. ENUMERATOR ASSIGNMENT MODAL TESTS
  // ===========================================================================

  test('1. EnumeratorAssignmentModal lists eligible enumerators and handles assignment', async () => {
    jest.spyOn(enumeratorService, 'getEnumerators').mockResolvedValue({
      total: 3,
      items: [
        {
          id: 'enum-1',
          name: 'Enumerator One',
          username: 'enum1',
          role: 'ENUMERATOR',
          status: 'ACTIVE',
          availability: 'AVAILABLE',
          assigned_hlb_code: null,
          assigned_layout_name: null,
        },
        {
          id: 'enum-2',
          name: 'Enumerator Two',
          username: 'enum2',
          role: 'ENUMERATOR',
          status: 'ACTIVE',
          availability: 'ASSIGNED',
          assigned_hlb_code: 'HLB-002',
          assigned_layout_name: 'Arasur Village',
        },
        {
          id: 'enum-3',
          name: 'Enumerator Three',
          username: 'enum3',
          role: 'ENUMERATOR',
          status: 'INACTIVE',
          availability: 'INACTIVE',
          assigned_hlb_code: null,
          assigned_layout_name: null,
        },
      ],
    });

    jest.spyOn(enumeratorService, 'getHlbEnumeratorAssignment').mockResolvedValue(null);
    jest.spyOn(enumeratorService, 'assignEnumerator').mockResolvedValue({
      id: 'assign-1',
      hlb_id: 'hlb-001',
      block_code: 'HLB-001',
      layout_id: 'layout-arasur-1',
      enumerator_id: 'enum-1',
      enumerator_name: 'Enumerator One',
      enumerator_username: 'enum1',
      supervisor_id: 'sup-1',
      assigned_at: '2026-09-28T10:00:00Z',
      status: 'ACTIVE',
      created_at: '2026-09-28T10:00:00Z',
      updated_at: '2026-09-28T10:00:00Z',
    });

    const onClose = jest.fn();
    const onSuccess = jest.fn();

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(
        <EnumeratorAssignmentModal
          visible={true}
          hlb={{
            id: 'hlb-001',
            block_code: 'HLB-001',
            actual_building_count: 145,
            target_building_count: 150,
          }}
          layoutId="layout-arasur-1"
          layoutName="Arasur Village"
          onClose={onClose}
          onSuccess={onSuccess}
        />
      );
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-assignment-modal' })).toBeDefined();
    expect(root.findByProps({ testID: 'enumerator-option-enum1' })).toBeDefined();
    expect(root.findByProps({ testID: 'enumerator-option-enum2' })).toBeDefined();
    expect(root.findByProps({ testID: 'enumerator-option-enum3' })).toBeDefined();

    // Select available enumerator (enum1)
    await ReactTestRenderer.act(async () => {
      root.findByProps({ testID: 'enumerator-option-enum1' }).props.onPress();
    });

    // Proceed to Step 2 (Confirmation)
    await ReactTestRenderer.act(async () => {
      root.findByProps({ testID: 'proceed-confirm-assignment-btn' }).props.onPress();
    });

    expect(root.findByProps({ testID: 'confirm-assignment-btn' })).toBeDefined();

    // Confirm assignment
    await ReactTestRenderer.act(async () => {
      await root.findByProps({ testID: 'confirm-assignment-btn' }).props.onPress();
    });

    expect(enumeratorService.assignEnumerator).toHaveBeenCalledWith(
      'hlb-001',
      'enum-1'
    );
    expect(onSuccess).toHaveBeenCalled();
    expect(root.findByProps({ testID: 'done-assignment-btn' })).toBeDefined();
  });

  // ===========================================================================
  // 2. SUPERVISOR LAYOUT DETAIL SCREEN (ENUMERATOR ASSIGNMENT)
  // ===========================================================================

  test('2. SupervisorLayoutDetailScreen displays assignment summary and HLB list with assignment status', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayoutDetail').mockResolvedValue({
      id: 'layout-arasur-1',
      name: 'Arasur Village',
      area_id: 'area-arasur-1',
      administrative_area_id: 'area-arasur-1',
      status: 'ASSIGNED',
      target_buildings_per_hlb: 150,
      total_buildings: 300,
      hlb_count: 2,
      active_version_id: 'v1',
      active_version_number: 1,
      active_version_status: 'APPROVED',
      created_at: '2026-09-28T00:00:00Z',
      updated_at: '2026-09-28T00:00:00Z',
    });

    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({
      items: [
        {
          id: 'hlb-001',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-001',
          hlb_code: 'HLB-001',
          name: 'Block 1',
          status: 'VALID',
          building_count: 145,
          actual_building_count: 145,
          target_building_count: 150,
          target_buildings_per_hlb: 150,
          quality_score: 95.0,
          validation_status: 'VALID',
          validation_details: null,
          boundary: { type: 'MultiPolygon', coordinates: [] },
        },
        {
          id: 'hlb-002',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-002',
          hlb_code: 'HLB-002',
          name: 'Block 2',
          status: 'VALID',
          building_count: 155,
          actual_building_count: 155,
          target_building_count: 150,
          target_buildings_per_hlb: 150,
          quality_score: 95.0,
          validation_status: 'VALID',
          validation_details: null,
          boundary: { type: 'MultiPolygon', coordinates: [] },
        },
      ],
      total: 2,
    });


    jest.spyOn(enumeratorService, 'getLayoutEnumeratorAssignments').mockResolvedValue({
      layout_id: 'layout-arasur-1',
      layout_name: 'Arasur Village',
      total_hlbs: 2,
      required_enumerators: 2,
      assigned_enumerators: 1,
      remaining_enumerators: 1,
      status: 'INCOMPLETE',
      is_complete: false,
      items: [
        {
          hlb_id: 'hlb-001',
          block_code: 'HLB-001',
          name: 'Block 1',
          actual_building_count: 145,
          target_building_count: 150,
          is_assigned: true,
          assignment: {
            id: 'assign-1',
            hlb_id: 'hlb-001',
            block_code: 'HLB-001',
            layout_id: 'layout-arasur-1',
            enumerator_id: 'enum-1',
            enumerator_name: 'Enumerator One',
            enumerator_username: 'enum1',
            supervisor_id: 'sup-1',
            assigned_at: '2026-09-28T10:00:00Z',
            status: 'ACTIVE',
            created_at: '2026-09-28T10:00:00Z',
            updated_at: '2026-09-28T10:00:00Z',
          },
        },
        {
          hlb_id: 'hlb-002',
          block_code: 'HLB-002',
          name: 'Block 2',
          actual_building_count: 155,
          target_building_count: 150,
          is_assigned: false,
          assignment: null,
        },
      ],
    });

    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-arasur-1',
      code: 'ARASUR',
      name: 'Arasur Village',
      type: 'VILLAGE',
      boundary: { type: 'MultiPolygon', coordinates: [] },
    });



    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorLayoutDetailScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-layout-detail-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-assignment-summary-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-hlb-item-HLB-001' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-hlb-item-HLB-002' })).toBeDefined();
    expect(root.findByProps({ testID: 'assign-btn-HLB-001' })).toBeDefined();
    expect(root.findByProps({ testID: 'assign-btn-HLB-002' })).toBeDefined();
  });

  // ===========================================================================
  // 3. ENUMERATOR DASHBOARD TESTS
  // ===========================================================================

  test('3. EnumeratorDashboardScreen displays active assigned HLB details', async () => {
    await ReactTestRenderer.act(async () => {
      useAuthStore.setState({
        user: {
          id: 'enum-1',
          name: 'Enumerator One',
          username: 'enum1',
          role: 'ENUMERATOR',
        },
        token: 'jwt-enum-token',
        status: 'authenticated',
      });
    });

    jest.spyOn(enumeratorService, 'getMyAssignedHlbs').mockResolvedValue([
      {
        id: 'hlb-001',
        layout_id: 'layout-arasur-1',
        layout_name: 'Arasur Village',
        area_name: 'Arasur Village',
        block_code: 'HLB-001',
        name: 'Block 1',
        status: 'ASSIGNED',
        target_building_count: 150,
        actual_building_count: 145,
        boundary: null,
      },
    ]);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<EnumeratorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'assigned-hlb-container' })).toBeDefined();
    expect(root.findByProps({ testID: 'view-assigned-hlb-btn' })).toBeDefined();
    expect(enumeratorService.getMyAssignedHlbs).toHaveBeenCalled();
  });

  test('4. EnumeratorDashboardScreen displays clean empty state when no HLB is assigned', async () => {
    await ReactTestRenderer.act(async () => {
      useAuthStore.setState({
        user: {
          id: 'enum-unassigned',
          name: 'Unassigned Enum',
          username: 'enum_unassigned',
          role: 'ENUMERATOR',
        },
        token: 'jwt-enum-token-unassigned',
        status: 'authenticated',
      });
    });

    jest.spyOn(enumeratorService, 'getMyAssignedHlbs').mockResolvedValue([]);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<EnumeratorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'unassigned-empty-state' })).toBeDefined();
  });

  // ===========================================================================
  // 4. ENUMERATOR HLB DETAIL SCREEN TESTS
  // ===========================================================================

  test('5. EnumeratorHlbDetailScreen renders assigned block boundary and Phase 8 roadmap notice', async () => {
    jest.spyOn(enumeratorService, 'getMyAssignedHlbDetail').mockResolvedValue({
      id: 'hlb-001',
      layout_id: 'layout-arasur-1',
      layout_name: 'Arasur Village',
      area_name: 'Arasur Village',
      block_code: 'HLB-001',
      name: 'Block 1',
      status: 'ASSIGNED',
      target_building_count: 150,
      actual_building_count: 145,
      boundary: {
        type: 'Polygon',
        coordinates: [
          [
            [77.0, 11.0],
            [77.005, 11.0],
            [77.005, 11.01],
            [77.0, 11.01],
            [77.0, 11.0],
          ],
        ],
      },
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<EnumeratorHlbDetailScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-hlb-detail-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'enumerator-hlb-overview-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'tab-buildings-btn' })).toBeDefined();
    expect(root.findByProps({ testID: 'tab-map-btn' })).toBeDefined();
    expect(enumeratorService.getMyAssignedHlbDetail).toHaveBeenCalledWith('hlb-001');
  });
});

