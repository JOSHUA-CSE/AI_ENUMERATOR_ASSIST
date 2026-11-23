import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import {
  DeputyDashboardScreen,
  resetDeputyDashboardCacheForTesting,
} from '../src/features/deputy/DeputyDashboardScreen';
import { DeputyLayoutDetailScreen } from '../src/features/deputy/DeputyLayoutDetailScreen';
import { deputyService, DeputyOverallProgressResponse, DeputyLayoutDetailProgressResponse } from '../src/core/deputyService';
import { areaService } from '../src/core/areaService';
import { layoutService } from '../src/core/layoutService';
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
        layoutName: 'Village A',
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

describe('Phase 14 — Deputy Tahsildar Progress Monitoring Tests', () => {
  const mockOverallProgress: DeputyOverallProgressResponse = {
    total_layouts: 2,
    total_hlbs: 5,
    active_hlbs: 2,
    completed_hlbs: 3,
    remaining_hlbs: 2,
    total_houses: 1240,
    completed_houses: 892,
    remaining_houses: 348,
    locked_houses: 20,
    revisit_count: 15,
    overall_progress_percentage: 71.94,
    last_updated: '2026-10-04T12:00:00Z',
    layouts: [
      {
        layout_id: 'layout-arasur-1',
        layout_name: 'Village A',
        area_id: 'area-arasur-1',
        village_name: 'Arasur Village',
        status: 'APPROVED',
        supervisor: {
          id: 'sup-1',
          name: 'Supervisor S001',
          username: 's001',
          phone: '9876543210',
          status: 'ACTIVE',
          is_assigned: true,
        },
        total_hlbs: 3,
        active_hlbs: 1,
        completed_hlbs: 2,
        remaining_hlbs: 1,
        total_houses: 700,
        completed_houses: 520,
        remaining_houses: 180,
        locked_houses: 12,
        revisit_count: 8,
        overall_progress_percentage: 74.29,
      },
      {
        layout_id: 'layout-arasur-2',
        layout_name: 'Village B',
        area_id: 'area-arasur-2',
        village_name: 'Kariampalayam',
        status: 'ASSIGNED',
        supervisor: {
          id: null,
          name: null,
          username: null,
          phone: null,
          status: null,
          is_assigned: false,
        },
        total_hlbs: 2,
        active_hlbs: 1,
        completed_hlbs: 1,
        remaining_hlbs: 1,
        total_houses: 540,
        completed_houses: 372,
        remaining_houses: 168,
        locked_houses: 8,
        revisit_count: 7,
        overall_progress_percentage: 68.89,
      },
    ],
  };

  const mockLayoutDetailProgress: DeputyLayoutDetailProgressResponse = {
    ...mockOverallProgress.layouts[0],
    last_updated: '2026-10-04T12:00:00Z',
    hlbs: [
      {
        hlb_id: 'hlb-1',
        block_code: 'HLB-001',
        name: 'Block 1',
        status: 'COMPLETED',
        assigned_enumerator_id: 'enum-1',
        assigned_enumerator_name: 'Kumar Swamy',
        assigned_supervisor_name: 'Supervisor S001',
        total_houses: 250,
        completed_houses: 250,
        remaining_houses: 0,
        locked_houses: 3,
        revisit_count: 2,
        progress_percentage: 100.0,
        is_completed: true,
        is_active: false,
        last_sync: '2026-10-04T11:45:00Z',
      },
      {
        hlb_id: 'hlb-2',
        block_code: 'HLB-002',
        name: 'Block 2',
        status: 'ACTIVE',
        assigned_enumerator_id: 'enum-2',
        assigned_enumerator_name: 'Priya Raj',
        assigned_supervisor_name: 'Supervisor S001',
        total_houses: 250,
        completed_houses: 150,
        remaining_houses: 100,
        locked_houses: 5,
        revisit_count: 4,
        progress_percentage: 60.0,
        is_completed: false,
        is_active: true,
        last_sync: '2026-10-04T11:50:00Z',
      },
      {
        hlb_id: 'hlb-3',
        block_code: 'HLB-003',
        name: 'Block 3',
        status: 'COMPLETED',
        assigned_enumerator_id: null,
        assigned_enumerator_name: null,
        assigned_supervisor_name: 'Supervisor S001',
        total_houses: 200,
        completed_houses: 200,
        remaining_houses: 0,
        locked_houses: 4,
        revisit_count: 2,
        progress_percentage: 100.0,
        is_completed: true,
        is_active: false,
        last_sync: '2026-10-04T11:30:00Z',
      },
    ],
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    resetDeputyDashboardCacheForTesting();
    // Default mocks for area and layout service to prevent unmocked fetch calls
    jest.spyOn(areaService, 'getAreas').mockResolvedValue({ items: [], total: 2 } as any);
    jest.spyOn(layoutService, 'getLayouts').mockResolvedValue({ items: [], total: 2 } as any);

    await ReactTestRenderer.act(async () => {
      useLanguageStore.setState({ language: 'en' });
      useAuthStore.setState({
        user: {
          id: 'deputy-1',
          username: 'deputy_arasur',
          name: 'Tahsildar Officer',
          role: 'DEPUTY_TAHSILDAR',
        } as any,
        token: 'jwt-deputy-token',
        status: 'authenticated',
      });
    });
  });

  // 1. Deputy dashboard renders
  test('1. Deputy dashboard renders with top-level container and header', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'deputy-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'overall-progress-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'layouts-progress-card' })).toBeDefined();
  });

  // 2. Overall progress renders
  test('2. Overall progress percentage and weighted ratio render accurately', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const pctNode = root.findByProps({ testID: 'overall-progress-pct' });
    expect(getAllText(pctNode)).toContain('71.9%');

    const ratioNode = root.findByProps({ testID: 'overall-houses-ratio' });
    expect(getAllText(ratioNode)).toContain('892 / 1240');
  });

  // 3. Layout list renders
  test('3. Layout list renders all layouts under jurisdiction', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'layout-card-layout-arasur-1' })).toBeDefined();
    expect(root.findByProps({ testID: 'layout-card-layout-arasur-2' })).toBeDefined();
  });

  // 4. Layout status renders
  test('4. Layout status renders authoritative text and status badge', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const text = getAllText(root.findByProps({ testID: 'layout-card-layout-arasur-1' }));
    expect(text).toContain('APPROVED');
    expect(text).toContain('Village A');

    const text2 = getAllText(root.findByProps({ testID: 'layout-card-layout-arasur-2' }));
    expect(text2).toContain('ASSIGNED');
    expect(text2).toContain('Village B');
  });

  // 5. Supervisor assignment renders
  test('5. Supervisor assignment renders assigned name or "Supervisor not assigned"', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    // Layout 1 has assigned supervisor
    const l1Text = getAllText(root.findByProps({ testID: 'layout-card-layout-arasur-1' }));
    expect(l1Text).toContain('Supervisor S001');

    // Layout 2 has no supervisor assigned
    const l2Text = getAllText(root.findByProps({ testID: 'layout-card-layout-arasur-2' }));
    expect(l2Text).toContain('Supervisor not assigned');
  });

  // 6. HLB totals render
  test('6. Total HLBs count renders in dashboard summary metric box', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const totalHlbBox = root.findByProps({ testID: 'metric-total-hlbs' });
    expect(getAllText(totalHlbBox)).toContain('5');
  });

  // 7. Active HLBs render
  test('7. Active HLBs count renders correctly in dashboard metric box', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const activeHlbBox = root.findByProps({ testID: 'metric-active-hlbs' });
    expect(getAllText(activeHlbBox)).toContain('2');
  });

  // 8. Completed HLBs render
  test('8. Completed HLBs count renders correctly in dashboard metric box', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const completedHlbBox = root.findByProps({ testID: 'metric-completed-hlbs' });
    expect(getAllText(completedHlbBox)).toContain('3');
  });

  // 9. Remaining HLBs render
  test('9. Remaining HLBs count renders correctly in dashboard metric box', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const remainingHlbBox = root.findByProps({ testID: 'metric-remaining-hlbs' });
    expect(getAllText(remainingHlbBox)).toContain('2');
  });

  // 10. House/building progress renders
  test('10. House and building progress breakdown renders completed, remaining, and locked counts', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const lockedPill = root.findByProps({ testID: 'pill-locked-houses' });
    expect(getAllText(lockedPill)).toContain('20');

    const revisitPill = root.findByProps({ testID: 'pill-revisits' });
    expect(getAllText(revisitPill)).toContain('15');
  });

  // 11. Loading state
  test('11. Loading spinner renders while fetching progress data', async () => {
    jest.spyOn(areaService, 'getAreas').mockReturnValue(new Promise(() => {}));
    jest.spyOn(layoutService, 'getLayouts').mockReturnValue(new Promise(() => {}));
    jest.spyOn(deputyService, 'getOverallProgress').mockReturnValue(new Promise(() => {}));

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'dashboard-loading-spinner' })).toBeDefined();
  });

  // 12. Empty state
  test('12. Empty state renders when no layouts exist under authority', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue({
      total_layouts: 0,
      total_hlbs: 0,
      active_hlbs: 0,
      completed_hlbs: 0,
      remaining_hlbs: 0,
      total_houses: 0,
      completed_houses: 0,
      remaining_houses: 0,
      locked_houses: 0,
      revisit_count: 0,
      overall_progress_percentage: 0.0,
      layouts: [],
      last_updated: '2026-10-04T12:00:00Z',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'dashboard-empty-container' })).toBeDefined();
    expect(getAllText(root.findByProps({ testID: 'dashboard-empty-container' }))).toContain('No layouts available');
  });

  // 13. Error state
  test('13. Error state renders when server request fails', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockRejectedValue(new Error('Network error: 503'));

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'dashboard-error-container' })).toBeDefined();
    expect(root.findByProps({ testID: 'dashboard-retry-btn' })).toBeDefined();
  });

  // 14. Offline/stale state
  test('14. Offline/stale state renders banner with last updated timestamp on refresh failure', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValueOnce(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    // Make next refresh call fail
    jest.spyOn(deputyService, 'getOverallProgress').mockRejectedValueOnce(new Error('Offline'));

    const refreshBtn = component.root.findByProps({ testID: 'refresh-dashboard-btn' });
    await ReactTestRenderer.act(async () => {
      refreshBtn.props.onPress();
    });

    expect(component.root.findByProps({ testID: 'deputy-offline-banner' })).toBeDefined();
  });

  // 15. Refresh works
  test('15. Manual refresh button triggers fresh getOverallProgress fetch', async () => {
    const progressSpy = jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const refreshBtn = component.root.findByProps({ testID: 'refresh-dashboard-btn' });
    await ReactTestRenderer.act(async () => {
      refreshBtn.props.onPress();
    });

    expect(progressSpy).toHaveBeenCalledTimes(2);
  });

  // 16. Layout detail navigation works
  test('16. Tapping a layout card navigates to DeputyLayoutDetail screen', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const card = component.root.findByProps({ testID: 'layout-card-layout-arasur-1' });
    await ReactTestRenderer.act(async () => {
      card.props.onPress();
    });

    expect(mockNavigate).toHaveBeenCalledWith('DeputyLayoutDetail', {
      layoutId: 'layout-arasur-1',
      layoutName: 'Village A',
      areaName: 'Arasur Village',
      areaId: 'area-arasur-1',
    });
  });

  // 17. HLB summary renders
  test('17. DeputyLayoutDetailScreen renders layout header, metrics, spatial map, and HLB breakdown list', async () => {
    jest.spyOn(deputyService, 'getLayoutProgress').mockResolvedValue(mockLayoutDetailProgress);
    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({ total: 3, items: [] });
    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-arasur-1',
      name: 'Arasur Village',
      code: 'VILL-638401',
      type: 'VILLAGE',
      boundary: null as any,
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyLayoutDetailScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'deputy-layout-detail-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'hlb-card-HLB-001' })).toBeDefined();
    expect(root.findByProps({ testID: 'hlb-card-HLB-002' })).toBeDefined();
    expect(root.findByProps({ testID: 'hlb-card-HLB-003' })).toBeDefined();

    const hlb1Text = getAllText(root.findByProps({ testID: 'hlb-card-HLB-001' }));
    expect(hlb1Text).toContain('HLB-001');
    expect(hlb1Text).toContain('Kumar Swamy');
    expect(hlb1Text).toMatch(/100\.0\s*%/);

    const hlb2Text = getAllText(root.findByProps({ testID: 'hlb-card-HLB-002' }));
    expect(hlb2Text).toContain('HLB-002');
    expect(hlb2Text).toContain('Priya Raj');
    expect(hlb2Text).toMatch(/60\.0\s*%/);
  });

  // 18. English localization
  test('18. English localization renders all Phase 14 labels in English', async () => {
    await ReactTestRenderer.act(async () => {
      useLanguageStore.setState({ language: 'en' });
    });
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const text = getAllText(component.root);
    expect(text).toContain('Overall Fieldwork Progress');
    expect(text).toContain('Active HLBs');
    expect(text).toContain('Completed HLBs');
    expect(text).toContain('Remaining HLBs');
    expect(text).toContain('Locked Houses');
    expect(text).toContain('Layout Status');
  });

  // 19. Tamil localization
  test('19. Tamil localization renders all Phase 14 labels in Tamil', async () => {
    await ReactTestRenderer.act(async () => {
      useLanguageStore.setState({ language: 'ta' });
    });
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const text = getAllText(component.root);
    expect(text).toContain('ஒட்டுமொத்த களப்பணி முன்னேற்றம்');
    expect(text).toContain('செயலில் உள்ள HLB-கள்');
    expect(text).toContain('முடிக்கப்பட்ட HLB-கள்');
    expect(text).toContain('மீதமுள்ள HLB-கள்');
    expect(text).toContain('பூட்டப்பட்ட வீடுகள்');
    expect(text).toContain('லேஅவுட் நிலை');
  });

  // 20. Existing Deputy navigation still works
  test('20. Existing Deputy navigation buttons (Areas, Layouts, Supervisors, Progress, Logout) remain functional', async () => {
    jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue(mockOverallProgress);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
    });

    const root = component.root;
    const areasBtn = root.findByProps({ testID: 'nav-areas-button' });
    await ReactTestRenderer.act(async () => {
      areasBtn.props.onPress();
    });
    expect(mockNavigate).toHaveBeenCalledWith('AreaList');

    const layoutsBtn = root.findByProps({ testID: 'nav-layouts-button' });
    await ReactTestRenderer.act(async () => {
      layoutsBtn.props.onPress();
    });
    expect(mockNavigate).toHaveBeenCalledWith('LayoutList');

    const supervisorsBtn = root.findByProps({ testID: 'nav-supervisors-button' });
    await ReactTestRenderer.act(async () => {
      supervisorsBtn.props.onPress();
    });
    expect(mockNavigate).toHaveBeenCalledWith('SupervisorsPlaceholder');

    const progressBtn = root.findByProps({ testID: 'nav-progress-button' });
    await ReactTestRenderer.act(async () => {
      progressBtn.props.onPress();
    });
    expect(mockNavigate).toHaveBeenCalledWith('ProgressPlaceholder');
  });
});
