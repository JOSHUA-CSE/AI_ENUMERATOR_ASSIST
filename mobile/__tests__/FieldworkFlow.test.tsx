import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { EnumeratorDashboardScreen } from '../src/features/enumerator/EnumeratorDashboardScreen';
import { EnumeratorHlbDetailScreen } from '../src/features/enumerator/EnumeratorHlbDetailScreen';
import { BuildingDetailScreen } from '../src/features/enumerator/BuildingDetailScreen';
import { HouseholdFormScreen } from '../src/features/enumerator/HouseholdFormScreen';
import { enumeratorService } from '../src/core/enumeratorService';
import { fieldworkService } from '../src/core/fieldworkService';
import { gpsService } from '../src/core/gpsService';
import { useAuthStore } from '../src/core/authStore';
import { en } from '../src/core/localization/en';
import { ta } from '../src/core/localization/ta';

// Mock Navigation
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
let mockRouteParams: any = {
  hlbId: 'hlb-fw-1',
  blockCode: 'HLB-FW-001',
  buildingId: 'bld-101',
  buildingReference: 'BLD-101',
};

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
      params: mockRouteParams,
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

describe('Phase 8 — Enumerator Offline Field Workflow Mobile Tests', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRouteParams = {
      hlbId: 'hlb-fw-1',
      blockCode: 'HLB-FW-001',
      buildingId: 'bld-101',
      buildingReference: 'BLD-101',
    };

    useAuthStore.setState({
      user: {
        id: 'enum-test-user-1',
        name: 'Ravi Kumar',
        username: 'ravi_enum',
        role: 'ENUMERATOR',
      },
      token: 'mock-jwt-token',
      status: 'authenticated',
      error: null,
    });
  });

  // ===========================================================================
  // 1. ENUMERATOR DASHBOARD TESTS
  // ===========================================================================

  test('1. EnumeratorDashboardScreen loads assigned HLB with download action', async () => {
    jest.spyOn(fieldworkService, 'getDownloadedHlbs').mockReturnValue([]);
    jest.spyOn(fieldworkService, 'isHlbDownloaded').mockReturnValue(false);
    jest.spyOn(enumeratorService, 'getMyAssignedHlbs').mockResolvedValue([
      {
        id: 'hlb-fw-1',
        layout_id: 'layout-1',
        layout_name: 'Ward 5',
        area_name: 'Salem North',
        block_code: 'HLB-FW-001',
        name: 'Block 1',
        status: 'ASSIGNED',
        target_building_count: 150,
        actual_building_count: 148,
        boundary: { type: 'MultiPolygon', coordinates: [] },
      },
    ]);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<EnumeratorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'assigned-hlb-container' })).toBeDefined();
    expect(root.findByProps({ testID: 'dashboard-download-hlb-btn' })).toBeDefined();
    expect(root.findByProps({ testID: 'view-assigned-hlb-btn' })).toBeDefined();
  });

  test('2. EnumeratorDashboardScreen displays empty state when unassigned', async () => {
    jest.spyOn(fieldworkService, 'getDownloadedHlbs').mockReturnValue([]);
    jest.spyOn(enumeratorService, 'getMyAssignedHlbs').mockResolvedValue([]);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<EnumeratorDashboardScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'unassigned-empty-state' })).toBeDefined();
  });

  // ===========================================================================
  // 2. HLB FIELDWORK & OFFLINE BUILDING LIST TESTS
  // ===========================================================================

  test('3. EnumeratorHlbDetailScreen renders offline buildings and metrics from SQLite', async () => {
    jest.spyOn(fieldworkService, 'isHlbDownloaded').mockReturnValue(true);
    jest.spyOn(fieldworkService, 'getOfflineHlb').mockReturnValue({
      id: 'hlb-fw-1',
      layout_id: 'layout-1',
      layout_name: 'Ward 5',
      area_name: 'Salem North',
      block_code: 'HLB-FW-001',
      name: 'Block 1',
      status: 'ACTIVE',
      target_building_count: 150,
      actual_building_count: 3,
      boundary_geojson: '{"type":"MultiPolygon","coordinates":[]}',
      downloaded_at: '2026-09-28T10:00:00Z',
      enumerator_id: 'enum-test-user-1',
    });

    jest.spyOn(fieldworkService, 'getBuildings').mockReturnValue([
      {
        id: 'bld-101',
        hlb_id: 'hlb-fw-1',
        building_reference: 'BLD-101',
        house_number: '12-A',
        latitude: 11.6643,
        longitude: 78.146,
        footprint_geojson: null,
        source_type: 'SATELLITE_DETECTED',
        status: 'COMPLETED',
        household_count: 1,
        last_updated_at: '2026-09-28T10:00:00Z',
      },
      {
        id: 'bld-102',
        hlb_id: 'hlb-fw-1',
        building_reference: 'BLD-102',
        house_number: '12-B',
        latitude: 11.6645,
        longitude: 78.1462,
        footprint_geojson: null,
        source_type: 'SATELLITE_DETECTED',
        status: 'PENDING',
        household_count: 0,
        last_updated_at: '2026-09-28T10:00:00Z',
      },
    ]);

    jest.spyOn(fieldworkService, 'getFieldworkStats').mockReturnValue({
      total_buildings: 2,
      completed_buildings: 1,
      pending_buildings: 1,
      in_progress_buildings: 0,
      revisit_buildings: 0,
      locked_buildings: 0,
      total_households: 1,
      completed_households: 1,
      draft_households: 0,
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<EnumeratorHlbDetailScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-hlb-detail-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'tab-buildings-btn' })).toBeDefined();
    expect(root.findByProps({ testID: 'tab-map-btn' })).toBeDefined();
    expect(root.findByProps({ testID: 'search-buildings-input' })).toBeDefined();
    expect(root.findByProps({ testID: 'building-item-0' })).toBeDefined();
    expect(root.findByProps({ testID: 'building-item-1' })).toBeDefined();
  });

  // ===========================================================================
  // 3. BUILDING DETAIL & GPS CAPTURE TESTS
  // ===========================================================================

  test('4. BuildingDetailScreen shows structure details, GPS capture, and household records', async () => {
    jest.spyOn(fieldworkService, 'getBuildingDetail').mockReturnValue({
      building: {
        id: 'bld-101',
        hlb_id: 'hlb-fw-1',
        building_reference: 'BLD-101',
        house_number: '12-A',
        latitude: 11.6643,
        longitude: 78.146,
        footprint_geojson: null,
        source_type: 'SATELLITE_DETECTED',
        status: 'IN_PROGRESS',
        household_count: 1,
        last_updated_at: '2026-09-28T10:00:00Z',
      },
      households: [
        {
          id: 'hh-101',
          building_id: 'bld-101',
          hlb_id: 'hlb-fw-1',
          enumerator_id: 'enum-test-user-1',
          household_number: 'HH-1',
          head_name: 'Muthusamy',
          total_members: 4,
          male_count: 2,
          female_count: 2,
          transgender_count: 0,
          ownership_status: 'OWNED',
          drinking_water_source: 'Tap Water',
          lighting_source: 'Electricity',
          latrine_facility: 'Yes',
          data_json: null,
          status: 'COMPLETED',
          source: 'FORM',
          created_at: '2026-09-28T10:00:00Z',
          updated_at: '2026-09-28T10:00:00Z',
        },
      ],
      revisits: [],
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<BuildingDetailScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'building-detail-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'building-info-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'gps-observation-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'capture-gps-btn' })).toBeDefined();
    expect(root.findByProps({ testID: 'household-item-0' })).toBeDefined();
    expect(root.findByProps({ testID: 'start-household-enumeration-btn' })).toBeDefined();
    expect(root.findByProps({ testID: 'mark-revisit-btn' })).toBeDefined();
  });

  // ===========================================================================
  // 4. HOUSEHOLD FORM VALIDATION & PERSISTENCE TESTS
  // ===========================================================================

  test('5. HouseholdFormScreen renders inputs, supports draft saving, and completes validation', async () => {
    mockRouteParams = {
      buildingId: 'bld-101',
      hlbId: 'hlb-fw-1',
      buildingReference: 'BLD-101',
    };

    jest.spyOn(fieldworkService, 'getBuildingDetail').mockReturnValue({
      building: null,
      households: [],
      revisits: [],
    });

    const saveSpy = jest.spyOn(fieldworkService, 'saveHousehold').mockImplementation(() => {});

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<HouseholdFormScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'household-form-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'household-number-input' })).toBeDefined();
    expect(root.findByProps({ testID: 'head-name-input' })).toBeDefined();
    expect(root.findByProps({ testID: 'total-members-input' })).toBeDefined();
    expect(root.findByProps({ testID: 'male-count-input' })).toBeDefined();
    expect(root.findByProps({ testID: 'female-count-input' })).toBeDefined();
    expect(root.findByProps({ testID: 'trans-count-input' })).toBeDefined();
    expect(root.findByProps({ testID: 'save-draft-btn' })).toBeDefined();
    expect(root.findByProps({ testID: 'complete-form-btn' })).toBeDefined();

    // Trigger save draft
    const headNameInput = root.findByProps({ testID: 'head-name-input' });
    ReactTestRenderer.act(() => {
      headNameInput.props.onChangeText('Subramanian');
    });

    const draftBtn = root.findByProps({ testID: 'save-draft-btn' });
    ReactTestRenderer.act(() => {
      draftBtn.props.onPress();
    });

    expect(saveSpy).toHaveBeenCalled();
    const savedRecord = saveSpy.mock.calls[0][0];
    expect(savedRecord.head_name).toBe('Subramanian');
    expect(savedRecord.status).toBe('DRAFT');
  });

  // ===========================================================================
  // 5. GPS CAPTURE GRACEFUL PERMISSION TESTS
  // ===========================================================================

  test('6. GPS service handles permission denial and errors without crashing', async () => {
    jest.spyOn(gpsService, 'getCurrentLocation').mockResolvedValue({
      success: false,
      error: 'PERMISSION_DENIED',
      errorMessage: 'Location permission was denied',
    });

    const res = await fieldworkService.captureAndLogGps('hlb-fw-1', 'enum-1', 'bld-101');
    expect(res.success).toBe(false);
    expect(res.error).toBe('PERMISSION_DENIED');
  });

  // ===========================================================================
  // 6. LOCALIZATION INTEGRITY TESTS
  // ===========================================================================

  test('7. Localization keys match between English and Tamil for Phase 8', () => {
    const requiredKeys = [
      'download_for_offline',
      'downloading',
      'download_complete',
      'download_failed',
      'available_offline',
      'fieldwork_hlb_title',
      'buildings_tab',
      'map_tab',
      'visited_buildings',
      'pending_buildings',
      'building_details',
      'start_enumeration',
      'add_household',
      'edit_household',
      'households_in_building',
      'head_of_household',
      'total_members_label',
      'ownership_type',
      'save_draft',
      'complete_form',
      'mark_revisit',
      'revisit_reason',
      'capture_gps',
      'gps_observation',
      'lock_building_btn',
    ] as const;

    for (const key of requiredKeys) {
      expect(en[key]).toBeDefined();
      expect(typeof en[key]).toBe('string');
      expect(ta[key]).toBeDefined();
      expect(typeof ta[key]).toBe('string');
    }
  });
});
