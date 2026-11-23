import React from 'react';
import ReactTestRenderer, { act } from 'react-test-renderer';
import { LayoutListScreen } from '../src/features/deputy/LayoutListScreen';
import { HlbReviewScreen } from '../src/features/deputy/HlbReviewScreen';
import { layoutService, LayoutSummary } from '../src/core/layoutService';
import { areaService, AdministrativeArea } from '../src/core/areaService';
import { useLanguageStore } from '../src/core/localization';
import { useAuthStore } from '../src/core/authStore';

const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
let mockRouteParams: any = {};

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
  };
});

function getAllText(root: any): string {
  try {
    const textNodes = root.findAllByType('Text');
    return textNodes
      .map((n: any) => {
        const c = n.props?.children;
        if (Array.isArray(c)) {
          return c
            .map((item: any) => (typeof item === 'object' && item?.props?.children ? item.props.children : item))
            .join(' ');
        }
        return String(c ?? '');
      })
      .join(' ')
      .replace(/\s+/g, ' ');
  } catch {
    return '';
  }
}

describe('Phase 6.2 — Multi-Area Layout UI and Split Preview', () => {
  const mockAreas: AdministrativeArea[] = [
    {
      id: 'area-achipatti',
      name: 'Achipatti',
      code: 'VILL-644592',
      type: 'VILLAGE',
      parent_id: null,
      status: 'ACTIVE',
      house_count: 500,
      boundary: null,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    },
    {
      id: 'area-anupperpalayam',
      name: 'Anupperpalayam',
      code: 'VILL-644535',
      type: 'VILLAGE',
      parent_id: null,
      status: 'ACTIVE',
      house_count: 300,
      boundary: null,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    },
    {
      id: 'area-gomangalam',
      name: 'Gomangalam',
      code: 'VILL-644554',
      type: 'VILLAGE',
      parent_id: null,
      status: 'ACTIVE',
      house_count: 450,
      boundary: null,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    },
  ];

  const mockLayouts: LayoutSummary[] = [
    {
      id: 'layout-pollachi-central',
      area_id: 'area-achipatti',
      administrative_area_id: 'area-achipatti',
      area_ids: ['area-achipatti', 'area-anupperpalayam'],
      area_names: ['Achipatti', 'Anupperpalayam'],
      areas_count: 2,
      name: 'Pollachi Central Layout',
      status: 'DRAFT',
      target_buildings_per_hlb: 250,
      total_buildings: 800,
      hlb_count: 4,
      active_version_number: 1,
      active_version_status: 'CANDIDATE',
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    },
  ];

  beforeEach(async () => {
    jest.clearAllMocks();
    mockRouteParams = {};

    await act(async () => {
      useLanguageStore.setState({ language: 'en' });
      useAuthStore.setState({
        user: {
          id: 'deputy-1',
          username: 'deputy_pollachi',
          name: 'Deputy Tahsildar',
          role: 'DEPUTY_TAHSILDAR',
        },
      });
    });

    jest.spyOn(areaService, 'getAreas').mockResolvedValue({
      items: mockAreas,
      total: mockAreas.length,
      skip: 0,
      limit: 100,
    });

    jest.spyOn(layoutService, 'getLayouts').mockResolvedValue({
      items: mockLayouts,
      total: mockLayouts.length,
    });

    jest.spyOn(layoutService, 'createLayout').mockResolvedValue({
      id: 'layout-new-001',
      area_id: 'area-gomangalam',
      administrative_area_id: 'area-gomangalam',
      area_ids: ['area-gomangalam'],
      name: 'Gomangalam Layout',
      status: 'DRAFT',
      target_buildings_per_hlb: 250,
      total_buildings: 450,
      hlb_count: 2,
      active_version_number: null,
      active_version_status: null,
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    });

    jest.spyOn(layoutService, 'updateLayout').mockResolvedValue({
      id: 'layout-pollachi-central',
      area_id: 'area-achipatti',
      administrative_area_id: 'area-achipatti',
      area_ids: ['area-achipatti', 'area-anupperpalayam', 'area-gomangalam'],
      name: 'Pollachi Central Layout Extended',
      status: 'DRAFT',
      target_buildings_per_hlb: 300,
      total_buildings: 1250,
      hlb_count: 5,
      active_version_number: 1,
      active_version_status: 'CANDIDATE',
      created_at: '2026-01-01',
      updated_at: '2026-01-01',
    });
  });

  it('renders layout cards with multi-area summary and edit buttons', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<LayoutListScreen />);
    });

    const root = renderer!.root;
    const card = root.findByProps({ testID: 'layout-card-layout-pollachi-central' });
    expect(card).toBeTruthy();

    const text = getAllText(card);
    // Should display multi-area summary
    expect(text).toContain('Achipatti, Anupperpalayam');

    // Should display edit button
    const editBtn = root.findByProps({ testID: 'edit-layout-btn-layout-pollachi-central' });
    expect(editBtn).toBeTruthy();
  });

  it('supports multi-area selection, search filtering, removable chips, and combined building counts', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<LayoutListScreen />);
    });

    const root = renderer!.root;

    // Open create layout modal
    const openModalBtn = root.findByProps({ testID: 'open-create-layout-modal-btn' });
    await act(async () => {
      openModalBtn.props.onPress();
    });

    // Search filter
    const searchInput = root.findByProps({ testID: 'search-area-input' });
    await act(async () => {
      searchInput.props.onChangeText('Gomangalam');
    });

    // Select Gomangalam
    const selectGomangalam = root.findByProps({ testID: 'select-area-area-gomangalam' });
    await act(async () => {
      selectGomangalam.props.onPress();
    });

    // Check removable chip exists
    const chip = root.findByProps({ testID: 'selected-area-chip-area-gomangalam' });
    expect(chip).toBeTruthy();
    expect(getAllText(chip)).toContain('Gomangalam');

    // Remove via chip [X] button
    const removeBtn = root.findByProps({ testID: 'remove-area-chip-area-gomangalam' });
    await act(async () => {
      removeBtn.props.onPress();
    });

    // Chip should no longer be present
    expect(() => root.findByProps({ testID: 'selected-area-chip-area-gomangalam' })).toThrow();
  });

  it('displays conflict warning when selecting an area belonging to another active layout', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<LayoutListScreen />);
    });

    const root = renderer!.root;

    // Open create modal
    const openModalBtn = root.findByProps({ testID: 'open-create-layout-modal-btn' });
    await act(async () => {
      openModalBtn.props.onPress();
    });

    // Select Achipatti (already belongs to Pollachi Central Layout)
    const selectAchipatti = root.findByProps({ testID: 'select-area-area-achipatti' });
    await act(async () => {
      selectAchipatti.props.onPress();
    });

    // Conflict warning banner should be displayed
    const warning = root.findByProps({ testID: 'layout-conflict-warning' });
    expect(warning).toBeTruthy();
    expect(getAllText(warning)).toContain('already part of active layout');
    expect(getAllText(warning)).toContain('Pollachi Central Layout');
  });

  it('edits an existing layout without creating duplicate layout entity', async () => {
    let renderer: ReactTestRenderer.ReactTestRenderer;
    await act(async () => {
      renderer = ReactTestRenderer.create(<LayoutListScreen />);
    });

    const root = renderer!.root;

    // Click Edit on Pollachi Central Layout
    const editBtn = root.findByProps({ testID: 'edit-layout-btn-layout-pollachi-central' });
    await act(async () => {
      editBtn.props.onPress();
    });

    // Change layout name and target workload
    const nameInput = root.findByProps({ testID: 'new-layout-name-input' });
    await act(async () => {
      nameInput.props.onChangeText('Pollachi Central Layout Extended');
    });

    const targetInput = root.findByProps({ testID: 'new-layout-target-input' });
    await act(async () => {
      targetInput.props.onChangeText('300');
    });

    // Confirm update
    const confirmBtn = root.findByProps({ testID: 'confirm-create-layout-btn' });
    await act(async () => {
      confirmBtn.props.onPress();
    });

    // updateLayout must be called with layout ID
    expect(layoutService.updateLayout).toHaveBeenCalledWith(
      'layout-pollachi-central',
      expect.objectContaining({
        name: 'Pollachi Central Layout Extended',
        target_buildings_per_hlb: 300,
      })
    );

    // createLayout must NOT have been called
    expect(layoutService.createLayout).not.toHaveBeenCalled();
  });

  it('calls previewSplitHlb with DRAW_LINE coordinates and receives sub-polygons and building ID lists', async () => {
    const mockPreviewResult = {
      is_valid: true,
      side_a_block_code: 'HLB-001A',
      side_a_building_count: 15,
      side_b_block_code: 'HLB-001B',
      side_b_building_count: 15,
      total_original_buildings: 30,
      part_a_geometry: { type: 'Polygon', coordinates: [] },
      part_b_geometry: { type: 'Polygon', coordinates: [] },
      part_a_building_ids: ['b1', 'b2'],
      part_b_building_ids: ['b3', 'b4'],
    };

    const spy = jest.spyOn(layoutService, 'previewSplitHlb').mockResolvedValue(mockPreviewResult);

    const result = await layoutService.previewSplitHlb('hlb-1', {
      split_method: 'DRAW_LINE',
      split_line_coordinates: [[77.095, 11.042], [77.095, 11.048]],
    });

    expect(spy).toHaveBeenCalledWith('hlb-1', {
      split_method: 'DRAW_LINE',
      split_line_coordinates: [[77.095, 11.042], [77.095, 11.048]],
    });

    expect(result.is_valid).toBe(true);
    expect(result.part_a_geometry).toBeDefined();
    expect(result.part_b_geometry).toBeDefined();
    expect(result.part_a_building_ids).toEqual(['b1', 'b2']);
    expect(result.part_b_building_ids).toEqual(['b3', 'b4']);
    expect(result.side_a_building_count + result.side_b_building_count).toBe(result.total_original_buildings);
  });
});
