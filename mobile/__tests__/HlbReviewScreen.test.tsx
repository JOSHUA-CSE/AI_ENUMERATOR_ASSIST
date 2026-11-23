import React from 'react';
import ReactTestRenderer, { act } from 'react-test-renderer';
import { HlbReviewScreen } from '../src/features/deputy/HlbReviewScreen';
import {
  layoutService,
  LayoutSummary,
  HlbCandidate,
  LayoutValidationResponse,
  SplitPreviewResult,
  MergePreviewResult,
} from '../src/core/layoutService';
import { areaService } from '../src/core/areaService';

// Mock Expo secure-store
jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  getItemAsync: jest.fn().mockResolvedValue(null),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

// Mock react-native-maps
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
  layoutId: 'layout-arasur-001',
  areaName: 'Arasur Village',
  areaId: 'area-arasur-001',
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

const mockLayout: LayoutSummary = {
  id: 'layout-arasur-001',
  area_id: 'area-arasur-001',
  administrative_area_id: 'area-arasur-001',
  name: 'Arasur Village Layout',
  status: 'REVIEW',
  target_buildings_per_hlb: 200,
  total_buildings: 503,
  hlb_count: 3,
  active_version_id: 'v1',
  active_version_number: 1,
  active_version_status: 'CANDIDATE',
  created_at: '2026-09-18T00:00:00Z',
  updated_at: '2026-09-18T00:00:00Z',
};

const mockHlbs: HlbCandidate[] = [
  {
    id: 'hlb-001',
    layout_id: 'layout-arasur-001',
    block_code: 'HLB-001',
    hlb_code: 'HLB-001',
    status: 'CANDIDATE',
    building_count: 139,
    actual_building_count: 139,
    target_building_count: 200,
    target_buildings_per_hlb: 200,
    count_deviation: -61,
    quality_score: 0.92,
    validation_status: 'VALID',
    validation_details: { count_score: 0.92, boundary_score: 1.0 },
    boundary: {
      type: 'Polygon',
      coordinates: [
        [
          [77.12, 11.08],
          [77.125, 11.08],
          [77.125, 11.085],
          [77.12, 11.085],
          [77.12, 11.08],
        ],
      ],
    },
    centroid: { type: 'Point', coordinates: [77.1225, 11.0825] },
    warnings: [],
  },
  {
    id: 'hlb-002',
    layout_id: 'layout-arasur-001',
    block_code: 'HLB-002',
    hlb_code: 'HLB-002',
    status: 'CANDIDATE',
    building_count: 173,
    actual_building_count: 173,
    target_building_count: 200,
    target_buildings_per_hlb: 200,
    count_deviation: -27,
    quality_score: 0.87,
    validation_status: 'VALID',
    validation_details: { count_score: 0.87, boundary_score: 1.0 },
    boundary: {
      type: 'Polygon',
      coordinates: [
        [
          [77.125, 11.08],
          [77.13, 11.08],
          [77.13, 11.085],
          [77.125, 11.085],
          [77.125, 11.08],
        ],
      ],
    },
    centroid: { type: 'Point', coordinates: [77.1275, 11.0825] },
    warnings: [],
  },
  {
    id: 'hlb-003',
    layout_id: 'layout-arasur-001',
    block_code: 'HLB-003',
    hlb_code: 'HLB-003',
    status: 'CANDIDATE',
    building_count: 191,
    actual_building_count: 191,
    target_building_count: 200,
    target_buildings_per_hlb: 200,
    count_deviation: -9,
    quality_score: 0.81,
    validation_status: 'VALID',
    validation_details: { count_score: 0.81, boundary_score: 1.0 },
    boundary: {
      type: 'Polygon',
      coordinates: [
        [
          [77.12, 11.075],
          [77.13, 11.075],
          [77.13, 11.08],
          [77.12, 11.08],
          [77.12, 11.075],
        ],
      ],
    },
    centroid: { type: 'Point', coordinates: [77.125, 11.0775] },
    warnings: [],
  },
];

const mockAreaBoundary = {
  id: 'area-arasur-001',
  name: 'Arasur Village',
  code: 'VILL-638401',
  area_code: 'VILL-638401',
  type: 'VILLAGE',
  boundary: {
    type: 'Polygon',
    coordinates: [
      [
        [77.12, 11.075],
        [77.13, 11.075],
        [77.13, 11.085],
        [77.12, 11.085],
        [77.12, 11.075],
      ],
    ],
  },
};

const mockLayoutValidation: LayoutValidationResponse = {
  layout_id: 'layout-arasur-001',
  is_valid: true,
  can_approve: true,
  status: 'READY_FOR_APPROVAL',
  total_buildings: 503,
  assigned_buildings: 503,
  unassigned_buildings: 0,
  duplicate_assignments: 0,
  hlb_count: 3,
  checklist: [
    { id: '1', title: 'All Buildings Assigned', passed: true, detail: '503 of 503 assigned' },
    { id: '2', title: 'No Duplicate Assignments', passed: true, detail: '0 overlaps' },
  ],
  errors: [],
  warnings: [],
};

const mockSplitPreview: SplitPreviewResult = {
  is_valid: true,
  side_a_block_code: 'HLB-001A',
  side_a_building_count: 70,
  side_b_block_code: 'HLB-001B',
  side_b_building_count: 69,
  total_original_buildings: 139,
  validation_errors: [],
};

const mockMergePreview: MergePreviewResult = {
  is_valid: true,
  is_adjacent: true,
  merged_block_code: 'HLB-001 + HLB-002',
  combined_building_count: 312,
  building_assignment_status: '312 / 312',
  validation_errors: [],
};

describe('Phase 5.1 — HlbReviewScreen', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.spyOn(layoutService, 'getLayout').mockResolvedValue(mockLayout);
    jest.spyOn(layoutService, 'getLayoutHlbs').mockResolvedValue({ items: mockHlbs, total: 3 });
    jest.spyOn(layoutService, 'validateLayout').mockResolvedValue(mockLayoutValidation);
    jest.spyOn(layoutService, 'previewSplitHlb').mockResolvedValue(mockSplitPreview);
    jest.spyOn(layoutService, 'previewMergeHlbs').mockResolvedValue(mockMergePreview);
    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue(mockAreaBoundary);
  });

  afterEach(() => {
    jest.restoreAllMocks();
  });

  const renderScreen = async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<HlbReviewScreen />);
      await Promise.resolve();
      await Promise.resolve();
      await Promise.resolve();
    });
    return renderer!;
  };

  it('renders layout header, summary metrics, and candidate HLB list correctly', async () => {
    const renderer = await renderScreen();
    const root = renderer.root;

    expect(root.findByProps({ testID: 'hlb-review-screen' })).toBeTruthy();
    expect(root.findByProps({ testID: 'layout-summary-card' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-spatial-map-card' })).toBeTruthy();
    expect(root.findByProps({ testID: 'candidate-hlb-list-card' })).toBeTruthy();
    expect(root.findByProps({ testID: 'layout-validation-card' })).toBeTruthy();

    // Verify candidate HLB rows are rendered
    expect(root.findByProps({ testID: 'hlb-row-HLB-001' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-row-HLB-002' })).toBeTruthy();
    expect(root.findByProps({ testID: 'hlb-row-HLB-003' })).toBeTruthy();

    const textStrings = root
      .findAllByType('Text' as any)
      .flatMap((t) => (Array.isArray(t.props.children) ? t.props.children : [t.props.children]))
      .filter((c) => typeof c === 'string' || typeof c === 'number')
      .join(' ');

    expect(textStrings).toContain('503');
    expect(textStrings).toContain('139');
    expect(textStrings).toContain('173');
    expect(textStrings).toContain('191');
    expect(textStrings).not.toContain('undefined');
    expect(textStrings).not.toContain('[object Object]');
  });

  it('switches to dedicated map editing mode with toolbar when EDIT BOUNDARY is clicked', async () => {
    const editSpy = jest.spyOn(layoutService, 'editHlbBoundary').mockResolvedValue({
      ...mockHlbs[0],
      actual_building_count: 145,
      building_count: 145,
    });

    const renderer = await renderScreen();
    const root = renderer.root;

    // Click EDIT BOUNDARY
    await act(async () => {
      root.findByProps({ testID: 'edit-boundary-action-btn' }).props.onPress();
      await Promise.resolve();
    });

    // Check that Map Editing Toolbar is visible
    expect(root.findByProps({ testID: 'map-editing-toolbar' })).toBeTruthy();
    expect(root.findByProps({ testID: 'add-point-btn' })).toBeTruthy();
    expect(root.findByProps({ testID: 'remove-point-btn' })).toBeTruthy();
    expect(root.findByProps({ testID: 'reset-boundary-btn' })).toBeTruthy();
    expect(root.findByProps({ testID: 'save-boundary-btn' })).toBeTruthy();

    // Tap Add Point
    await act(async () => {
      root.findByProps({ testID: 'add-point-btn' }).props.onPress();
      await Promise.resolve();
    });

    // Tap Save Boundary
    await act(async () => {
      root.findByProps({ testID: 'save-boundary-btn' }).props.onPress();
      await Promise.resolve();
    });

    expect(editSpy).toHaveBeenCalledWith('hlb-001', expect.anything());
  });

  it('provides Auto, Target (Side A & Side B), and Draw Line split methods with live preview', async () => {
    const splitSpy = jest.spyOn(layoutService, 'splitHlb').mockResolvedValue({
      layout_id: 'layout-arasur-001',
      version_id: 'v1',
      split_hlb_a: { ...mockHlbs[0], id: 'hlb-001a', block_code: 'HLB-001A', actual_building_count: 70 },
      split_hlb_b: { ...mockHlbs[0], id: 'hlb-001b', block_code: 'HLB-001B', actual_building_count: 69 },
    });

    const renderer = await renderScreen();
    const root = renderer.root;

    // Open Split Modal
    await act(async () => {
      root.findByProps({ testID: 'split-hlb-action-btn' }).props.onPress();
      await Promise.resolve();
    });

    expect(root.findByProps({ testID: 'split-hlb-modal' })).toBeTruthy();
    expect(root.findByProps({ testID: 'split-method-auto' })).toBeTruthy();
    expect(root.findByProps({ testID: 'split-method-target' })).toBeTruthy();
    expect(root.findByProps({ testID: 'split-method-draw' })).toBeTruthy();
    expect(root.findByProps({ testID: 'split-preview-card' })).toBeTruthy();

    // Select Target-Based Split and verify both Side A and Side B fields
    await act(async () => {
      root.findByProps({ testID: 'split-method-target' }).props.onPress();
      await Promise.resolve();
    });

    expect(root.findByProps({ testID: 'target-based-inputs' })).toBeTruthy();
    const sideAInput = root.findByProps({ testID: 'split-target-side-a-input' });
    const sideBInput = root.findByProps({ testID: 'split-target-side-b-input' });
    expect(sideAInput).toBeTruthy();
    expect(sideBInput).toBeTruthy();

    // Change Side A value
    await act(async () => {
      sideAInput.props.onChangeText('80');
      await Promise.resolve();
    });

    // Select Draw Split Line mode and verify map section
    await act(async () => {
      root.findByProps({ testID: 'split-method-draw' }).props.onPress();
      await Promise.resolve();
    });

    expect(root.findByProps({ testID: 'split-drawing-map-section' })).toBeTruthy();
    expect(root.findByProps({ testID: 'split-interactive-map' })).toBeTruthy();
    expect(root.findByProps({ testID: 'preset-horizontal-cut' })).toBeTruthy();

    // Apply horizontal cut preset
    await act(async () => {
      root.findByProps({ testID: 'preset-horizontal-cut' }).props.onPress();
      await Promise.resolve();
    });

    // Confirm Split
    await act(async () => {
      root.findByProps({ testID: 'confirm-split-btn' }).props.onPress();
      await Promise.resolve();
    });

    expect(splitSpy).toHaveBeenCalledWith('hlb-001', expect.objectContaining({ split_method: 'DRAW_SPLIT_LINE' }));
  });

  it('allows selecting any two candidate HLBs for merge with preview and adjacency check', async () => {
    const mergeSpy = jest.spyOn(layoutService, 'mergeHlbs').mockResolvedValue({
      layout_id: 'layout-arasur-001',
      version_id: 'v1',
      merged_hlb: {
        ...mockHlbs[0],
        id: 'hlb-001',
        block_code: 'HLB-001',
        actual_building_count: 312,
      },
    });

    const renderer = await renderScreen();
    const root = renderer.root;

    // Open Merge Modal
    await act(async () => {
      root.findByProps({ testID: 'merge-hlb-action-btn' }).props.onPress();
      await Promise.resolve();
    });

    expect(root.findByProps({ testID: 'merge-hlb-modal' })).toBeTruthy();

    // Toggle candidate HLB-003
    await act(async () => {
      root.findByProps({ testID: 'merge-candidate-HLB-003' }).props.onPress();
      await Promise.resolve();
    });

    // Confirm Merge
    await act(async () => {
      root.findByProps({ testID: 'confirm-merge-btn' }).props.onPress();
      await Promise.resolve();
    });

    expect(mergeSpy).toHaveBeenCalled();
  });

  it('provides a global fullscreen map expansion button on the map', async () => {
    const renderer = await renderScreen();
    const root = renderer.root;

    const fsBtn = root.findByProps({ testID: 'map-fullscreen-btn' });
    expect(fsBtn).toBeTruthy();

    // Tap fullscreen button
    await act(async () => {
      fsBtn.props.onPress();
      await Promise.resolve();
    });

    // Exit fullscreen button should now be available in fullscreen modal
    expect(root.findByProps({ testID: 'exit-fullscreen-btn' })).toBeTruthy();
    expect(root.findByProps({ testID: 'fullscreen-layer-toggle' })).toBeTruthy();
    expect(root.findByProps({ testID: 'fullscreen-recenter' })).toBeTruthy();
  });
});
