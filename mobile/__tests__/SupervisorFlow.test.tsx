import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { SupervisorDashboardScreen } from '../src/features/supervisor/SupervisorDashboardScreen';
import { SupervisorLayoutDetailScreen } from '../src/features/supervisor/SupervisorLayoutDetailScreen';
import { SupervisorAssignmentModal } from '../src/features/deputy/SupervisorAssignmentModal';
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

describe('Phase 6 — Supervisor Assignment & Dashboard Mobile Flow', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await ReactTestRenderer.act(async () => {
      useAuthStore.setState({
        user: {
          id: 'sup-1',
          name: 'Supervisor 001',
          username: 'supervisor1',
          role: 'SUPERVISOR',
        },
        token: 'jwt-sup-token',
        status: 'authenticated',
      });
    });
  });

  test('1. SupervisorDashboardScreen fetches and renders assigned layouts correctly', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue({
      total: 1,
      items: [
        {
          id: 'layout-arasur-1',
          name: 'Arasur Village',
          area_id: 'area-arasur-1',
          administrative_area_id: 'area-arasur-1',
          status: 'ASSIGNED',
          target_buildings_per_hlb: 150,
          total_buildings: 503,
          hlb_count: 3,
          active_version_id: 'v1',
          active_version_number: 1,
          active_version_status: 'APPROVED',
          created_at: '2026-09-28T00:00:00Z',
          updated_at: '2026-09-28T00:00:00Z',
          assignment: {
            id: 'assign-1',
            layout_id: 'layout-arasur-1',
            supervisor_id: 'sup-1',
            supervisor_name: 'Supervisor 001',
            assigned_at: '2026-09-28T10:00:00Z',
            status: 'ACTIVE',
            created_at: '2026-09-28T10:00:00Z',
            updated_at: '2026-09-28T10:00:00Z',
          },
        },
      ],
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'layout-card-layout-arasur-1' })).toBeDefined();
    expect(supervisorService.getMyAssignedLayouts).toHaveBeenCalled();
  });

  test('2. SupervisorDashboardScreen displays empty state when no layouts are assigned', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue({
      total: 0,
      items: [],
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-dashboard-screen' })).toBeDefined();
    expect(root.findAllByProps({ testID: 'layout-card-layout-arasur-1' }).length).toBe(0);
  });

  test('3. SupervisorLayoutDetailScreen renders layout metadata, spatial map, and HLBs without editing controls', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayoutDetail').mockResolvedValue({
      id: 'layout-arasur-1',
      name: 'VILL-638401',
      area_id: 'area-arasur-1',
      administrative_area_id: 'area-arasur-1',
      status: 'ASSIGNED',
      target_buildings_per_hlb: 150,
      total_buildings: 503,
      hlb_count: 3,
      active_version_id: 'v1',
      active_version_number: 1,
      active_version_status: 'APPROVED',
      created_at: '2026-09-28T00:00:00Z',
      updated_at: '2026-09-28T00:00:00Z',
      supervisor_name: 'Supervisor 001',
    });

    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({
      total: 3,
      items: [
        {
          id: 'hlb-1',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-001',
          hlb_code: 'HLB-001',
          name: 'HLB-001',
          status: 'APPROVED',
          building_count: 139,
          actual_building_count: 139,
          target_building_count: 150,
          target_buildings_per_hlb: 150,
          quality_score: 1.0,
          validation_status: 'VALID',
          validation_details: null,
          boundary: { type: 'Polygon', coordinates: [[[77.1, 11.1], [77.2, 11.1], [77.2, 11.2], [77.1, 11.2], [77.1, 11.1]]] },
        },
        {
          id: 'hlb-2',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-002',
          hlb_code: 'HLB-002',
          name: 'HLB-002',
          status: 'APPROVED',
          building_count: 173,
          actual_building_count: 173,
          target_building_count: 150,
          target_buildings_per_hlb: 150,
          quality_score: 1.0,
          validation_status: 'VALID',
          validation_details: null,
          boundary: { type: 'Polygon', coordinates: [[[77.2, 11.1], [77.3, 11.1], [77.3, 11.2], [77.2, 11.2], [77.2, 11.1]]] },
        },
        {
          id: 'hlb-3',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-003',
          hlb_code: 'HLB-003',
          name: 'HLB-003',
          status: 'APPROVED',
          building_count: 191,
          actual_building_count: 191,
          target_building_count: 150,
          target_buildings_per_hlb: 150,
          quality_score: 1.0,
          validation_status: 'VALID',
          validation_details: null,
          boundary: { type: 'Polygon', coordinates: [[[77.1, 11.2], [77.2, 11.2], [77.2, 11.3], [77.1, 11.3], [77.1, 11.2]]] },
        },
      ],
    });

    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-arasur-1',
      code: 'VILL-638401',
      name: 'Arasur Village',
      type: 'VILLAGE',
      boundary: { type: 'Polygon', coordinates: [[[77.0, 11.0], [77.4, 11.0], [77.4, 11.4], [77.0, 11.4], [77.0, 11.0]]] },
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorLayoutDetailScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-layout-detail-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-layout-overview-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-layout-map-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-hlb-list-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-layout-progress-card' })).toBeDefined();

    // Verify all 3 HLB cards exist
    expect(root.findByProps({ testID: 'supervisor-hlb-item-HLB-001' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-hlb-item-HLB-002' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-hlb-item-HLB-003' })).toBeDefined();

    // Verify immutability: NO edit, split, merge, or approve buttons exist on supervisor screen
    expect(root.findAllByProps({ testID: 'edit-boundary-btn' }).length).toBe(0);
    expect(root.findAllByProps({ testID: 'split-hlb-btn' }).length).toBe(0);
    expect(root.findAllByProps({ testID: 'merge-hlb-btn' }).length).toBe(0);
    expect(root.findAllByProps({ testID: 'approve-layout-btn' }).length).toBe(0);
  });

  test('4. SupervisorAssignmentModal renders supervisor selector and assigns supervisor', async () => {
    jest.spyOn(supervisorService, 'getSupervisors').mockResolvedValue({
      total: 2,
      items: [
        {
          id: 'sup-1',
          name: 'Supervisor 001',
          username: 'supervisor1',
          role: 'SUPERVISOR',
          status: 'ACTIVE',
          assigned_layouts_count: 0,
        },
        {
          id: 'sup-2',
          name: 'Supervisor 002',
          username: 'supervisor2',
          role: 'SUPERVISOR',
          status: 'ACTIVE',
          assigned_layouts_count: 1,
        },
      ],
    });

    jest.spyOn(supervisorService, 'getSupervisorAssignment').mockResolvedValue(null);

    const onSuccessMock = jest.fn();
    const onCloseMock = jest.fn();

    const sampleLayout = {
      id: 'layout-arasur-1',
      name: 'Arasur Village',
      area_id: 'area-arasur-1',
      administrative_area_id: 'area-arasur-1',
      status: 'APPROVED',
      target_buildings_per_hlb: 150,
      total_buildings: 503,
      hlb_count: 3,
      active_version_id: 'v1',
      active_version_number: 1,
      active_version_status: 'APPROVED',
      created_at: '2026-09-28T00:00:00Z',
      updated_at: '2026-09-28T00:00:00Z',
    };

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(
        <SupervisorAssignmentModal
          visible={true}
          layout={sampleLayout}
          areaName="Arasur Village"
          onClose={onCloseMock}
          onSuccess={onSuccessMock}
        />
      );
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-assignment-modal' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-option-sup-1' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-option-sup-2' })).toBeDefined();

    // Select Supervisor 001
    await ReactTestRenderer.act(async () => {
      root.findByProps({ testID: 'supervisor-option-sup-1' }).props.onPress();
    });

    // Press proceed button to open confirmation
    await ReactTestRenderer.act(async () => {
      root.findByProps({ testID: 'proceed-to-confirm-assignment-btn' }).props.onPress();
    });

    // Mock successful assignment
    jest.spyOn(supervisorService, 'assignSupervisor').mockResolvedValue({
      id: 'assign-1',
      layout_id: 'layout-arasur-1',
      supervisor_id: 'sup-1',
      supervisor_name: 'Supervisor 001',
      assigned_at: '2026-09-28T10:00:00Z',
      status: 'ACTIVE',
      created_at: '2026-09-28T10:00:00Z',
      updated_at: '2026-09-28T10:00:00Z',
    });

    // Confirm assignment
    await ReactTestRenderer.act(async () => {
      root.findByProps({ testID: 'confirm-assignment-submit-btn' }).props.onPress();
    });

    expect(supervisorService.assignSupervisor).toHaveBeenCalledWith('layout-arasur-1', 'sup-1');
  });
});

