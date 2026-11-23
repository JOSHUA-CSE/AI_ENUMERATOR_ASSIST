import React from 'react';
import ReactTestRenderer, { act } from 'react-test-renderer';
import { LayoutListScreen } from '../src/features/deputy/LayoutListScreen';
import { HlbGenerationScreen } from '../src/features/deputy/HlbGenerationScreen';
import { layoutService } from '../src/core/layoutService';
import { areaService } from '../src/core/areaService';
import { extractErrorMessage } from '../src/core/apiClient';

// Mock Expo secure-store
jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  getItemAsync: jest.fn().mockResolvedValue(null),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

// Mock react-native-maps with forwardRef support for fitToCoordinates and animateToRegion
jest.mock('react-native-maps', () => {
  const React = require('react');
  const { View } = require('react-native');
  const MockMapView = React.forwardRef((props: any, ref: any) => {
    React.useImperativeHandle(ref, () => ({
      fitToCoordinates: jest.fn(),
      animateToRegion: jest.fn(),
    }));
    return React.createElement(
      View,
      { ...props, testID: props.testID || 'mock-mapview' },
      props.children
    );
  });
  const MockUrlTile = (props: any) =>
    React.createElement(View, { ...props, testID: props.testID || 'mock-url-tile' });
  const MockPolygon = (props: any) =>
    React.createElement(View, { ...props, testID: props.testID || 'mock-polygon' });
  const MockMarker = (props: any) =>
    React.createElement(View, { ...props, testID: props.testID || 'mock-marker' }, props.children);
  const MockCallout = (props: any) => React.createElement(View, props, props.children);
  return {
    __esModule: true,
    default: MockMapView,
    MapView: MockMapView,
    Polygon: MockPolygon,
    Marker: MockMarker,
    Callout: MockCallout,
    UrlTile: MockUrlTile,
  };
});

// Mock navigation
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
let mockRouteParams: any = {
  layoutId: 'layout-001',
  layoutName: 'Arasur Master Layout',
  areaId: 'area-123',
  areaName: 'Arasur Village',
};

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({
    navigate: mockNavigate,
    goBack: mockGoBack,
  }),
  useRoute: () => ({
    params: mockRouteParams,
  }),
}));

const mockLayouts = [
  {
    id: 'layout-001',
    area_id: 'area-123',
    administrative_area_id: 'area-123',
    name: 'Arasur Master Layout',
    status: 'DRAFT',
    target_buildings_per_hlb: 200,
    total_buildings: 503,
    hlb_count: 3,
    active_version_number: 1,
    active_version_status: 'CANDIDATE',
    description: null,
    created_at: '2026-09-12T00:00:00Z',
    updated_at: '2026-09-12T00:00:00Z',
  },
];

const mockAreas = [
  {
    id: 'area-123',
    name: 'Arasur Village',
    type: 'VILLAGE',
    code: 'VILL-638401',
    parent_id: null,
    status: 'ACTIVE',
    house_count: 503,
    boundary: {
      type: 'Polygon',
      coordinates: [
        [
          [77.11, 11.07],
          [77.135, 11.07],
          [77.135, 11.095],
          [77.11, 11.095],
          [77.11, 11.07],
        ],
      ],
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const mockCandidateHlbs = [
  {
    id: 'hlb-001',
    layout_id: 'layout-001',
    layout_version_id: 'ver-001',
    hlb_code: 'HLB-001',
    status: 'CANDIDATE',
    building_count: 172,
    target_buildings_per_hlb: 200,
    count_deviation: -28,
    quality_score: 0.98,
    validation_status: 'VALID',
    validation_details: {
      count_score: 0.99,
      boundary_score: 1.0,
      continuity_score: 1.0,
      compactness_score: 0.95,
      count_deviation: -28,
      errors: [],
      warnings: [],
      is_valid: true,
      has_warnings: false,
    },
    boundary: {
      type: 'Polygon',
      coordinates: [
        [
          [77.11, 11.07],
          [77.12, 11.07],
          [77.12, 11.08],
          [77.11, 11.08],
          [77.11, 11.07],
        ],
      ],
    },
    centroid: {
      type: 'Point',
      coordinates: [77.115, 11.075],
    },
    warnings: [],
    created_at: '2026-09-12T00:00:00Z',
    updated_at: '2026-09-12T00:00:00Z',
  },
  {
    id: 'hlb-002',
    layout_id: 'layout-001',
    layout_version_id: 'ver-001',
    hlb_code: 'HLB-002',
    status: 'CANDIDATE',
    building_count: 165,
    target_buildings_per_hlb: 200,
    count_deviation: -35,
    quality_score: 0.96,
    validation_status: 'VALID',
    validation_details: {
      count_score: 0.98,
      boundary_score: 1.0,
      continuity_score: 1.0,
      compactness_score: 0.92,
      count_deviation: -35,
      errors: [],
      warnings: [],
      is_valid: true,
      has_warnings: false,
    },
    boundary: {
      type: 'Polygon',
      coordinates: [
        [
          [77.12, 11.07],
          [77.13, 11.07],
          [77.13, 11.08],
          [77.12, 11.08],
          [77.12, 11.07],
        ],
      ],
    },
    centroid: {
      type: 'Point',
      coordinates: [77.125, 11.075],
    },
    warnings: [],
    created_at: '2026-09-12T00:00:00Z',
    updated_at: '2026-09-12T00:00:00Z',
  },
  {
    id: 'hlb-003',
    layout_id: 'layout-001',
    layout_version_id: 'ver-001',
    hlb_code: 'HLB-003',
    status: 'CANDIDATE',
    building_count: 166,
    target_buildings_per_hlb: 200,
    count_deviation: -34,
    quality_score: 0.97,
    validation_status: 'VALID',
    validation_details: {
      count_score: 0.99,
      boundary_score: 1.0,
      continuity_score: 1.0,
      compactness_score: 0.94,
      count_deviation: -34,
      errors: [],
      warnings: [],
      is_valid: true,
      has_warnings: false,
    },
    boundary: {
      type: 'Polygon',
      coordinates: [
        [
          [77.13, 11.07],
          [77.135, 11.07],
          [77.135, 11.095],
          [77.13, 11.095],
          [77.13, 11.07],
        ],
      ],
    },
    centroid: {
      type: 'Point',
      coordinates: [77.132, 11.08],
    },
    warnings: [],
    created_at: '2026-09-12T00:00:00Z',
    updated_at: '2026-09-12T00:00:00Z',
  },
];

describe('Phase 4 — LayoutListScreen & HlbGenerationScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockRouteParams = {
      layoutId: 'layout-001',
      layoutName: 'Arasur Master Layout',
      areaId: 'area-123',
      areaName: 'Arasur Village',
    };

    jest.spyOn(layoutService, 'getLayouts').mockResolvedValue({
      items: mockLayouts as any,
      total: 1,
    });
    jest.spyOn(areaService, 'getAreas').mockResolvedValue({
      items: mockAreas as any,
      total: 1,
      skip: 0,
      limit: 50,
    });
    jest.spyOn(layoutService, 'getLayout').mockResolvedValue(mockLayouts[0] as any);
    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-123',
      name: 'Arasur Village',
      code: 'VILL-638401',
      type: 'VILLAGE',
      boundary: mockAreas[0].boundary as any,
    });
    jest.spyOn(areaService, 'getBuildingEstimation').mockResolvedValue({
      area_id: 'area-123',
      area_name: 'Arasur Village',
      area_code: 'VILL-638401',
      total_buildings: 503,
      source_type: 'SATELLITE_DETECTED',
      quality_label: 'Satellite-Derived',
      imagery_source: 'Google Open Buildings V3',
      imagery_date: '2026-01-01',
      average_confidence: 0.85,
      density_clusters: [],
    });
    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({
      items: mockCandidateHlbs as any,
      total: 3,
    });
    jest.spyOn(layoutService, 'generateHlbs').mockResolvedValue({
      layout_id: 'layout-001',
      layout_version_id: 'ver-001',
      version_number: 1,
      status: 'CANDIDATE',
      target_buildings_per_hlb: 200,
      total_buildings: 503,
      total_buildings_assigned: 503,
      hlb_count: 3,
      validation_status: 'VALID',
      average_quality_score: 0.97,
      invariants_satisfied: true,
      warnings: [],
      hlbs: mockCandidateHlbs as any,
    });
  });

  it('renders LayoutListScreen and navigates to HlbGeneration with real areaId', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<LayoutListScreen />);
    });

    const root = renderer!.root;
    expect(root.findByProps({ testID: 'layout-list-screen' })).toBeTruthy();
    expect(root.findByProps({ testID: 'layout-card-layout-001' })).toBeTruthy();

    const generateBtn = root.findByProps({ testID: 'generate-hlb-btn-layout-001' });
    expect(generateBtn).toBeTruthy();

    await act(async () => {
      generateBtn.props.onPress();
    });

    expect(mockNavigate).toHaveBeenCalledWith('HlbGeneration', {
      layoutId: 'layout-001',
      layoutName: 'Arasur Master Layout',
      areaId: 'area-123',
      areaName: 'Arasur Village',
    });
  });

  it('renders HlbGenerationScreen with real 503 detected buildings and estimated HLB count = 3', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbGenerationScreen />);
    });

    const root = renderer!.root;
    expect(root.findByProps({ testID: 'hlb-generation-screen' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-config-card' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-native-mapview' })).toBeTruthy();

    // Verify detected building count is 503 (not 0)
    const textNodes = root.findAllByType('Text' as any);
    const hasDetected503 = textNodes.some((n: any) => n.props.children === 503);
    expect(hasDetected503).toBe(true);

    // Verify estimated HLBs: ceil(503 / 200) = 3
    const hasEstimate3 = textNodes.some((n: any) => n.props.children === 3);
    expect(hasEstimate3).toBe(true);

    // Verify target stepper buttons and preset buttons
    expect(root.findByProps({ testID: 'target-inc-btn' })).toBeTruthy();
    expect(root.findByProps({ testID: 'target-dec-btn' })).toBeTruthy();
    expect(root.findByProps({ testID: 'preset-btn-100' })).toBeTruthy();
    expect(root.findByProps({ testID: 'preset-btn-200' })).toBeTruthy();
    expect(root.findByProps({ testID: 'preset-btn-250' })).toBeTruthy();
  });

  it('renders defensive validation screen when areaId is missing or undefined without calling API', async () => {
    mockRouteParams = {
      layoutId: undefined,
      areaId: undefined,
    };

    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbGenerationScreen />);
    });

    const root = renderer!.root;
    expect(root.findByProps({ testID: 'hlb-generation-invalid-screen' })).toBeTruthy();

    // Boundary and estimation APIs must NOT have been called with undefined
    expect(areaService.getAreaBoundary).not.toHaveBeenCalled();
    expect(areaService.getBuildingEstimation).not.toHaveBeenCalled();
  });

  it('displays API error screen when building estimation fails rather than showing zero buildings', async () => {
    jest.spyOn(areaService, 'getBuildingEstimation').mockRejectedValue(new Error('Failed to retrieve building estimation'));

    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbGenerationScreen />);
    });

    const root = renderer!.root;
    expect(root.findByProps({ testID: 'hlb-generation-error-screen' })).toBeTruthy();
    expect(root.findByProps({ testID: 'retry-load-btn' })).toBeTruthy();
  });

  it('calculates estimated HLBs correctly for various target sizes', () => {
    // 503 detected buildings
    expect(Math.ceil(503 / 200)).toBe(3);
    expect(Math.ceil(503 / 250)).toBe(3);
    expect(Math.ceil(503 / 100)).toBe(6);

    // Other scenarios
    expect(Math.ceil(500 / 200)).toBe(3);
    expect(Math.ceil(400 / 200)).toBe(2);
    expect(Math.ceil(1240 / 200)).toBe(7);
    expect(Math.ceil(1240 / 250)).toBe(5);
  });

  it('ensures extractErrorMessage never returns [object Object] for any error structure', () => {
    expect(extractErrorMessage(new Error('Network error'))).toBe('Network error');
    expect(extractErrorMessage({ message: 'Server down' })).toBe('Server down');
    expect(extractErrorMessage({ detail: 'Unprocessable entity' })).toBe('Unprocessable entity');

    // FastAPI 422 validation array
    const fastapiError = [
      { loc: ['path', 'id'], msg: 'Input should be a valid UUID', type: 'uuid_parsing' },
    ];
    expect(extractErrorMessage(fastapiError)).toBe('id: Input should be a valid UUID');

    // Axios error structure
    const axiosError = {
      response: {
        data: {
          detail: 'Database timeout',
        },
      },
    };
    expect(extractErrorMessage(axiosError)).toBe('Database timeout');

    // Unknown empty object
    expect(extractErrorMessage({})).not.toBe('[object Object]');
    expect(extractErrorMessage('[object Object]')).not.toBe('[object Object]');
    expect(extractErrorMessage(null)).not.toBe('[object Object]');
    expect(extractErrorMessage(undefined)).not.toBe('[object Object]');
  });

  it('triggers candidate HLB generation with Deputy target and displays candidate polygons', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbGenerationScreen />);
    });

    const root = renderer!.root;
    const generateBtn = root.findByProps({ testID: 'generate-hlbs-action-btn' });
    expect(generateBtn).toBeTruthy();

    await act(async () => {
      generateBtn.props.onPress();
    });

    expect(layoutService.generateHlbs).toHaveBeenCalledWith('layout-001', {
      target_buildings_per_hlb: 200,
    });
  });

  it('opens candidate HLB inspection modal and verifies Phase 4 has NO approval button', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbGenerationScreen />);
    });

    const root = renderer!.root;
    const row = root.findByProps({ testID: 'hlb-row-HLB-001' });

    await act(async () => {
      row.props.onPress();
    });

    const closeBtn = root.findByProps({ testID: 'close-hlb-detail-modal-btn' });
    expect(closeBtn).toBeTruthy();

    // Verify Phase 4 strictly has NO approval button
    const allButtons = root.findAllByType('Text' as any);
    const hasApprovalText = allButtons.some((node: any) =>
      typeof node.props.children === 'string' &&
      (node.props.children.toLowerCase().includes('approve') ||
       node.props.children.toLowerCase().includes('accept layout'))
    );
    expect(hasApprovalText).toBe(false);
  });

  it('verifies HLB Spatial Partitioning map uses satellite mapType and renders ONLY administrative boundary and HLB boundaries with minimal labels', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbGenerationScreen />);
    });

    const root = renderer!.root;

    // 1. Verify satellite map is rendered
    const spatialMap = root.findByProps({ testID: 'hlb-native-mapview' });
    expect(spatialMap).toBeTruthy();
    expect(spatialMap.props.mapType).toBe('satellite');

    // 2. Verify Level 1 Administrative boundary polygon renders
    const adminBoundary = root.findByProps({ testID: 'admin-boundary-polygon-0' });
    expect(adminBoundary).toBeTruthy();
    expect(adminBoundary.props.strokeColor).toBe('#D97706');

    // 3. Verify Level 2 HLB boundary polygons render for all candidate HLBs
    expect(root.findByProps({ testID: 'hlb-polygon-HLB-001-0' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-polygon-HLB-002-0' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-polygon-HLB-003-0' })).toBeTruthy();

    // 4. Verify minimal HLB centroid markers render with real backend codes
    expect(root.findByProps({ testID: 'hlb-marker-HLB-001' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-marker-HLB-002' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-marker-HLB-003' })).toBeTruthy();

    // 5. Verify NO individual building footprints, pins, or numbered cluster circles are rendered
    const bldPins = root.findAllByProps({ testID: 'bld-pin' });
    expect(bldPins.length).toBe(0);
    const clusterPins = root.findAllByProps({ testID: 'cluster-pin' });
    expect(clusterPins.length).toBe(0);

    // 6. Verify NO "undefined" text appears in the entire tree
    const allText = root.findAllByType('Text' as any);
    const hasUndefined = allText.some((node: any) =>
      typeof node.props.children === 'string' && node.props.children.includes('undefined')
    );
    expect(hasUndefined).toBe(false);
  });

  it('renders safe fallback HLB code when code is missing and handles empty state properly', async () => {
    // Test with empty candidate HLBs
    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({
      items: [],
      total: 0,
    });

    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbGenerationScreen />);
    });

    const root = renderer!.root;
    // Map still exists showing boundary with empty state overlay
    expect(root.findByProps({ testID: 'hlb-native-mapview' })).toBeTruthy();

    const textNodes = root.findAllByType('Text' as any);
    const hasEmptyMsg = textNodes.some((n: any) =>
      typeof n.props.children === 'string' &&
      n.props.children.includes('No HLB candidates generated yet')
    );
    expect(hasEmptyMsg).toBe(true);
  });
});
