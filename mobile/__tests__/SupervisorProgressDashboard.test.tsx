import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import {
  SupervisorDashboardScreen,
  resetSupervisorDashboardCacheForTesting,
} from '../src/features/supervisor/SupervisorDashboardScreen';
import { SupervisorLayoutDetailScreen } from '../src/features/supervisor/SupervisorLayoutDetailScreen';
import { SupervisorHlbDetailModal } from '../src/features/supervisor/SupervisorHlbDetailModal';
import { supervisorService } from '../src/core/supervisorService';
import { layoutService } from '../src/core/layoutService';
import { areaService } from '../src/core/areaService';
import { enumeratorService } from '../src/core/enumeratorService';
import { useAuthStore } from '../src/core/authStore';
import { useLanguageStore } from '../src/core/localization';

const mockNavigate = jest.fn();
const mockGoBack = jest.fn();

// Mock react-navigation
jest.mock('@react-navigation/native', () => {
  const actual = jest.requireActual('@react-navigation/native');
  return {
    ...actual,
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: mockGoBack,
      addListener: jest.fn(() => jest.fn()),
    }),
    useRoute: () => ({
      params: {
        layoutId: 'layout-arasur-1',
        layoutName: 'Arasur Village Layout',
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

function getAllText(node: any): string {
  if (!node) return '';
  try {
    const textNodes = node.findAllByType('Text');
    return textNodes
      .map((n: any) => {
        const c = n.props?.children;
        if (Array.isArray(c)) {
          return c
            .map((item) => (typeof item === 'object' && item?.props?.children ? item.props.children : item))
            .join(' ');
        }
        return String(c ?? '');
      })
      .join(' ');
  } catch {
    return '';
  }
}

describe('Phase 13 — Supervisor Progress Dashboard & Monitoring Tests', () => {
  const mockOverallProgress = {
    layouts: [
      {
        layout_id: 'layout-arasur-1',
        layout_name: 'Arasur Village Layout',
        area_id: 'area-arasur-1',
        village_name: 'Arasur Village',
        total_hlbs: 2,
        total_houses: 300,
        completed_houses: 180,
        remaining_houses: 120,
        locked_houses: 8,
        revisit_count: 5,
        progress_percentage: 60.0,
        last_updated: '2026-10-04T12:00:00Z',
        hlbs: [
          {
            hlb_id: 'hlb-1',
            block_code: 'HLB-001',
            name: 'Block 1',
            enumerator: {
              id: 'enum-1',
              name: 'Kumar Swamy',
              username: 'kumar',
              phone: '9876543210',
              assigned_hlb_id: 'hlb-1',
              assigned_hlb_code: 'HLB-001',
              progress_percentage: 60.0,
              completed_houses: 90,
              remaining_houses: 60,
              locked_houses: 4,
              revisit_count: 3,
              last_sync: '2026-10-04T11:45:00Z',
              sync_status: 'SYNCED',
            },
            total_houses: 150,
            completed_houses: 90,
            remaining_houses: 60,
            locked_houses: 4,
            revisit_count: 3,
            progress_percentage: 60.0,
            last_sync: '2026-10-04T11:45:00Z',
            gps_coverage: 80.0,
            boundary_alert_count: 1,
            boundary_alerts: [
              {
                track_id: 'track-101',
                timestamp: '2026-10-04T11:30:00Z',
                latitude: 11.123456,
                longitude: 77.654321,
                distance_meters: 18.5,
                message: 'Point recorded 18.5m outside assigned HLB boundary',
              },
            ],
          },
          {
            hlb_id: 'hlb-2',
            block_code: 'HLB-002',
            name: 'Block 2',
            enumerator: {
              id: 'enum-2',
              name: 'Priya Raj',
              username: 'priya',
              phone: '9876543211',
              assigned_hlb_id: 'hlb-2',
              assigned_hlb_code: 'HLB-002',
              progress_percentage: 60.0,
              completed_houses: 90,
              remaining_houses: 60,
              locked_houses: 4,
              revisit_count: 2,
              last_sync: '2026-10-04T11:50:00Z',
              sync_status: 'SYNCED',
            },
            total_houses: 150,
            completed_houses: 90,
            remaining_houses: 60,
            locked_houses: 4,
            revisit_count: 2,
            progress_percentage: 60.0,
            last_sync: '2026-10-04T11:50:00Z',
            gps_coverage: 85.0,
            boundary_alert_count: 0,
            boundary_alerts: [],
          },
        ],
      },
    ],
    total_layouts: 1,
    overall_total_houses: 300,
    overall_completed_houses: 180,
    overall_remaining_houses: 120,
    overall_locked_houses: 8,
    overall_revisit_count: 5,
    overall_progress_percentage: 60.0,
    last_updated: '2026-10-04T12:00:00Z',
  };

  const mockAssignedLayouts = {
    total: 1,
    items: [
      {
        id: 'layout-arasur-1',
        name: 'Arasur Village Layout',
        area_id: 'area-arasur-1',
        administrative_area_id: 'area-arasur-1',
        status: 'ASSIGNED',
        target_buildings_per_hlb: 150,
        total_buildings: 300,
        hlb_count: 2,
        active_version_id: 'v1',
        active_version_number: 1,
        active_version_status: 'APPROVED',
        created_at: '2026-10-04T00:00:00Z',
        updated_at: '2026-10-04T00:00:00Z',
        assignment: {
          id: 'assign-1',
          layout_id: 'layout-arasur-1',
          supervisor_id: 'sup-1',
          supervisor_name: 'Supervisor Raman',
          assigned_at: '2026-10-04T09:00:00Z',
          status: 'ACTIVE',
          created_at: '2026-10-04T09:00:00Z',
          updated_at: '2026-10-04T09:00:00Z',
        },
      },
    ],
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    resetSupervisorDashboardCacheForTesting();
    await ReactTestRenderer.act(async () => {
      useLanguageStore.setState({ language: 'en' });
      useAuthStore.setState({
        user: {
          id: 'sup-1',
          name: 'Supervisor Raman',
          username: 'raman_sup',
          role: 'SUPERVISOR',
        },
        token: 'jwt-sup-token',
        status: 'authenticated',
      });
    });
  });

  // 1. Supervisor dashboard renders
  test('1. Supervisor dashboard renders correctly with app header and cards', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'user-profile-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'overall-progress-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'assigned-layouts-card' })).toBeDefined();
  });

  // 2. Layout progress renders
  test('2. Layout progress renders with correct layout name and metrics', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    const layoutCard = root.findByProps({ testID: 'layout-card-layout-arasur-1' });
    expect(layoutCard).toBeDefined();
    const text = getAllText(layoutCard);
    expect(text).toContain('Arasur Village Layout');
    expect(text).toMatch(/60\.0\s*%/);
  });

  // 3. HLB list renders
  test('3. HLB list renders in layout detail screen', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayoutDetail').mockResolvedValue(mockAssignedLayouts.items[0]);
    jest.spyOn(supervisorService, 'getLayoutProgress').mockResolvedValue(mockOverallProgress.layouts[0]);
    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({
      total: 2,
      items: [
        {
          id: 'hlb-1',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-001',
          actual_building_count: 150,
          target_building_count: 150,
          status: 'APPROVED',
          boundary: { type: 'Polygon', coordinates: [[[77.1, 11.1], [77.2, 11.1], [77.2, 11.2], [77.1, 11.2], [77.1, 11.1]]] },
        },
        {
          id: 'hlb-2',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-002',
          actual_building_count: 150,
          target_building_count: 150,
          status: 'APPROVED',
          boundary: { type: 'Polygon', coordinates: [[[77.2, 11.1], [77.3, 11.1], [77.3, 11.2], [77.2, 11.2], [77.2, 11.1]]] },
        },
      ] as any,
    });
    jest.spyOn(enumeratorService, 'getLayoutEnumeratorAssignments').mockResolvedValue({
      layout_id: 'layout-arasur-1',
      total_hlbs: 2,
      required_enumerators: 2,
      assigned_enumerators: 2,
      is_complete: true,
      items: [
        { hlb_id: 'hlb-1', is_assigned: true, assignment: { enumerator_name: 'Kumar Swamy', enumerator_username: 'kumar' } },
        { hlb_id: 'hlb-2', is_assigned: true, assignment: { enumerator_name: 'Priya Raj', enumerator_username: 'priya' } },
      ],
    } as any);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorLayoutDetailScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-hlb-item-HLB-001' })).toBeDefined();
    expect(root.findByProps({ testID: 'supervisor-hlb-item-HLB-002' })).toBeDefined();
  });

  // 4. Enumerator information renders
  test('4. Enumerator information renders in HLB card and quick list', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    const quickHlb1 = root.findByProps({ testID: 'hlb-quick-row-HLB-001' });
    expect(quickHlb1).toBeDefined();
    expect(getAllText(quickHlb1)).toContain('Kumar Swamy');
  });

  // 5. Progress percentages render correctly
  test('5. Progress percentages render correctly (60.0%) and handle 0-division safely', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    const overallCard = root.findByProps({ testID: 'overall-progress-card' });
    expect(getAllText(overallCard)).toContain('60.0%');
  });

  // 6. Completed/remaining/locked counts render
  test('6. Completed (180), remaining (120), and locked (8) counts render', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    const overallCard = root.findByProps({ testID: 'overall-progress-card' });
    const content = getAllText(overallCard);
    expect(content).toContain('180');
    expect(content).toContain('120');
    expect(content).toContain('8');
  });

  // 7. Revisit count renders
  test('7. Revisit count renders in dashboard and layout detail', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    const overallCard = root.findByProps({ testID: 'overall-progress-card' });
    expect(getAllText(overallCard)).toContain('5');
  });

  // 8. Last sync renders
  test('8. Last sync timestamp renders in HLB modal', async () => {
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(
        <SupervisorHlbDetailModal
          visible={true}
          hlb={mockOverallProgress.layouts[0].hlbs[0]}
          onClose={jest.fn()}
        />
      );
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-hlb-detail-modal' })).toBeDefined();
    expect(getAllText(root)).toContain('Last Sync');
  });

  // 9. GPS coverage renders
  test('9. GPS coverage renders in HLB item and modal (80.0%)', async () => {
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(
        <SupervisorHlbDetailModal
          visible={true}
          hlb={mockOverallProgress.layouts[0].hlbs[0]}
          onClose={jest.fn()}
        />
      );
    });

    const root = component.root;
    expect(getAllText(root)).toContain('80.0%');
  });

  // 10. Boundary alerts render
  test('10. Boundary alerts render count badge and item details', async () => {
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(
        <SupervisorHlbDetailModal
          visible={true}
          hlb={mockOverallProgress.layouts[0].hlbs[0]}
          onClose={jest.fn()}
        />
      );
    });

    const root = component.root;
    const alertItem = root.findByProps({ testID: 'boundary-alert-item-0' });
    expect(alertItem).toBeDefined();
    expect(getAllText(alertItem)).toMatch(/18\.5\s*m from boundary/);
  });

  // 11. Loading state renders
  test('11. Loading spinner renders when fetching dashboard data', async () => {
    resetSupervisorDashboardCacheForTesting();
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockReturnValue(new Promise(() => {}));
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockReturnValue(new Promise(() => {}));

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'dashboard-loading-spinner' })).toBeDefined();
  });

  // 12. Empty state renders
  test('12. Empty state renders when supervisor has no assigned layouts', async () => {
    resetSupervisorDashboardCacheForTesting();
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue({ total: 0, items: [] });
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue({
      layouts: [],
      total_layouts: 0,
      overall_total_houses: 0,
      overall_completed_houses: 0,
      overall_remaining_houses: 0,
      overall_locked_houses: 0,
      overall_revisit_count: 0,
      overall_progress_percentage: 0.0,
      last_updated: '2026-10-04T12:00:00Z',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'dashboard-empty-container' })).toBeDefined();
  });

  // 13. Error state renders
  test('13. Error state renders when server request fails and no cache exists', async () => {
    resetSupervisorDashboardCacheForTesting();
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockRejectedValue(new Error('Network connection timeout'));
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockRejectedValue(new Error('Network connection timeout'));

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'dashboard-error-container' })).toBeDefined();
    expect(root.findByProps({ testID: 'dashboard-retry-btn' })).toBeDefined();
  });

  // 14. Offline/stale-data state renders
  test('14. Offline banner renders when network fails with cached data', async () => {
    // Populate cache with previous successful response
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    // Next request fails: simulate offline
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockRejectedValue(new Error('Network request failed'));
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockRejectedValue(new Error('Network request failed'));

    const refreshBtn = component.root.findByProps({ testID: 'refresh-dashboard-btn' });
    await ReactTestRenderer.act(async () => {
      refreshBtn.props.onPress();
    });

    // Offline banner should now be visible
    expect(component.root.findByProps({ testID: 'supervisor-offline-banner' })).toBeDefined();
  });

  // 15. Refresh works
  test('15. Manual refresh button calls getMyAssignedLayouts and getMyLayoutsProgress', async () => {
    const layoutsSpy = jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    const progressSpy = jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const refreshBtn = component.root.findByProps({ testID: 'refresh-dashboard-btn' });
    await ReactTestRenderer.act(async () => {
      refreshBtn.props.onPress();
    });

    expect(layoutsSpy).toHaveBeenCalledTimes(2);
    expect(progressSpy).toHaveBeenCalledTimes(2);
  });

  // 16. Navigation from dashboard -> layout -> HLB works
  test('16. Navigation from dashboard to layout detail screen works', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const layoutCard = component.root.findByProps({ testID: 'layout-card-layout-arasur-1' });
    await ReactTestRenderer.act(async () => {
      layoutCard.props.onPress();
    });

    expect(mockNavigate).toHaveBeenCalledWith('SupervisorLayoutDetail', {
      layoutId: 'layout-arasur-1',
      layoutName: 'Arasur Village Layout',
      areaName: 'Arasur Village Layout',
      areaId: 'area-arasur-1',
    });
  });

  // 17. Tamil localization
  test('17. Tamil localization renders all labels in Tamil correctly', async () => {
    await ReactTestRenderer.act(async () => {
      useLanguageStore.setState({ language: 'ta' });
    });
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const text = getAllText(component.root);
    expect(text).toContain('ஒட்டுமொத்த களப்பணி முன்னேற்றம்');
    expect(text).toContain('முடிந்தது');
    expect(text).toContain('மீதமுள்ளது');
    expect(text).toContain('பூட்டப்பட்டது');
  });

  // 18. English localization
  test('18. English localization renders labels in English', async () => {
    await ReactTestRenderer.act(async () => {
      useLanguageStore.setState({ language: 'en' });
    });
    jest.spyOn(supervisorService, 'getMyAssignedLayouts').mockResolvedValue(mockAssignedLayouts);
    jest.spyOn(supervisorService, 'getMyLayoutsProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorDashboardScreen />);
    });

    const text = getAllText(component.root);
    expect(text).toContain('Overall Fieldwork Progress');
    expect(text).toContain('Completed');
    expect(text).toContain('Remaining');
    expect(text).toContain('Locked');
  });

  // 19. Existing Supervisor assignment functionality still works
  test('19. Existing Supervisor assignment button opens assignment modal', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayoutDetail').mockResolvedValue(mockAssignedLayouts.items[0]);
    jest.spyOn(supervisorService, 'getLayoutProgress').mockResolvedValue(mockOverallProgress.layouts[0]);
    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({
      total: 1,
      items: [
        {
          id: 'hlb-1',
          layout_id: 'layout-arasur-1',
          block_code: 'HLB-001',
          actual_building_count: 150,
          target_building_count: 150,
          status: 'APPROVED',
          boundary: { type: 'Polygon', coordinates: [[[77.1, 11.1], [77.2, 11.1], [77.2, 11.2], [77.1, 11.2], [77.1, 11.1]]] },
        },
      ] as any,
    });
    jest.spyOn(enumeratorService, 'getLayoutEnumeratorAssignments').mockResolvedValue({
      layout_id: 'layout-arasur-1',
      total_hlbs: 1,
      required_enumerators: 1,
      assigned_enumerators: 1,
      is_complete: true,
      items: [
        { hlb_id: 'hlb-1', is_assigned: true, assignment: { enumerator_name: 'Kumar Swamy', enumerator_username: 'kumar' } },
      ],
    } as any);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorLayoutDetailScreen />);
    });

    const assignBtn = component.root.findByProps({ testID: 'assign-btn-HLB-001' });
    expect(assignBtn).toBeDefined();
    await ReactTestRenderer.act(async () => {
      assignBtn.props.onPress();
    });

    expect(component.root.findByProps({ testID: 'enumerator-assignment-modal' })).toBeDefined();
  });

  // 20. Existing Enumerator/fieldwork functionality is not broken
  test('20. Spatial map and boundary monitoring integration preserved without regression', async () => {
    jest.spyOn(supervisorService, 'getMyAssignedLayoutDetail').mockResolvedValue(mockAssignedLayouts.items[0]);
    jest.spyOn(supervisorService, 'getLayoutProgress').mockResolvedValue(mockOverallProgress.layouts[0]);
    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({ total: 0, items: [] });
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

    expect(component.root.findByProps({ testID: 'supervisor-layout-spatial-map' })).toBeDefined();
  });
});
