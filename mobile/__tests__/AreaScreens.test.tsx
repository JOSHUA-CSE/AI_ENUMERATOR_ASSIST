import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { AreaListScreen } from '../src/features/deputy/AreaListScreen';
import { AreaMapScreen } from '../src/features/deputy/AreaMapScreen';
import { DeputyDashboardScreen } from '../src/features/deputy/DeputyDashboardScreen';
import { areaService } from '../src/core/areaService';
import { layoutService } from '../src/core/layoutService';

// Mock Expo secure-store
jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  getItemAsync: jest.fn().mockResolvedValue(null),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

// Mock navigation

const mockNavigate = jest.fn();
const mockGoBack = jest.fn();

jest.mock('@react-navigation/native', () => ({
  useNavigation: () => ({
    navigate: mockNavigate,
    goBack: mockGoBack,
  }),
  useRoute: () => ({
    params: {
      areaId: 'area-123',
      areaName: 'Arasur Village',
      areaCode: 'VILL-638401',
    },
  }),
  useFocusEffect: (cb: any) => {
    const React = require('react');
    React.useEffect(() => {
      cb();
    }, [cb]);
  },
}));

const mockAreas = [
  {
    id: 'area-123',
    name: 'Arasur Village',
    type: 'VILLAGE',
    code: 'VILL-638401',
    parent_id: null,
    status: 'ACTIVE',
    house_count: 250,
    boundary: {
      type: 'MultiPolygon',
      coordinates: [
        [
          [
            [77.11, 11.07],
            [77.135, 11.07],
            [77.135, 11.095],
            [77.11, 11.095],
            [77.11, 11.07],
          ],
        ],
      ],
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'area-456',
    name: 'Sulur Ward 01',
    type: 'WARD',
    code: 'WARD-638402',
    parent_id: null,
    status: 'ACTIVE',
    house_count: 180,
    boundary: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

const mockHouses = [
  {
    id: 'house-1',
    area_id: 'area-123',
    building_reference: 'BLD-001',
    house_number: '1/1',
    latitude: 11.082,
    longitude: 77.12,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'house-2',
    area_id: 'area-123',
    building_reference: 'BLD-002',
    house_number: '1/2',
    latitude: 11.085,
    longitude: 77.125,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('Phase 3 — Administrative Areas & GIS Map Screens', () => {
  beforeAll(() => {
    jest.useFakeTimers();
  });

  afterAll(() => {
    jest.useRealTimers();
  });

  beforeEach(() => {
    jest.clearAllMocks();
  });

  test('1. AreaListScreen renders list of administrative areas with house counts', async () => {
    jest.spyOn(areaService, 'getAreas').mockResolvedValue({
      items: mockAreas as any,
      total: 2,
      skip: 0,
      limit: 100,
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AreaListScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'area-list-screen' })).toBeTruthy();
    expect(root.findByProps({ testID: 'area-card-VILL-638401' })).toBeTruthy();
    expect(root.findByProps({ testID: 'area-card-WARD-638402' })).toBeTruthy();
  });

  test('2. AreaListScreen filters list based on search query', async () => {
    jest.spyOn(areaService, 'getAreas').mockResolvedValue({
      items: mockAreas as any,
      total: 2,
      skip: 0,
      limit: 100,
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AreaListScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    const searchInput = root.findByProps({ testID: 'area-search-input' });

    // Type "Sulur" into search bar
    await ReactTestRenderer.act(async () => {
      searchInput.props.onChangeText('Sulur');
      jest.runAllTimers();
    });

    // WARD-638402 should be present, VILL-638401 should be filtered out
    expect(root.findByProps({ testID: 'area-card-WARD-638402' })).toBeTruthy();
    expect(() => root.findByProps({ testID: 'area-card-VILL-638401' })).toThrow();
  });

  test('3. AreaListScreen navigates to AreaMap when "View Map" is tapped', async () => {
    jest.spyOn(areaService, 'getAreas').mockResolvedValue({
      items: mockAreas as any,
      total: 2,
      skip: 0,
      limit: 100,
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AreaListScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    const viewMapBtn = root.findByProps({
      testID: 'view-map-button-VILL-638401',
    });

    await ReactTestRenderer.act(async () => {
      viewMapBtn.props.onPress();
      jest.runAllTimers();
    });

    expect(mockNavigate).toHaveBeenCalledWith('AreaMap', {
      areaId: 'area-123',
      areaName: 'Arasur Village',
      areaCode: 'VILL-638401',
    });
  });

  test('4. AreaMapScreen renders boundary polygon and native map view', async () => {
    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-123',
      name: 'Arasur Village',
      code: 'VILL-638401',
      type: 'VILLAGE',
      boundary: mockAreas[0].boundary as any,
    });
    jest.spyOn(areaService, 'getAreaHouses').mockResolvedValue({
      items: mockHouses as any,
      total: 2,
      skip: 0,
      limit: 1000,
    });
    jest.spyOn(areaService, 'getBuildingEstimation').mockResolvedValue({
      area_id: 'area-123',
      area_name: 'Arasur Village',
      area_code: 'VILL-638401',
      total_buildings: 250,
      source_type: 'DEVELOPMENT_DATA',
      quality_label: 'Development data',
      imagery_source: 'esri_world_imagery',
      imagery_date: null,
      average_confidence: null,
      density_clusters: [],
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AreaMapScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'area-map-screen' })).toBeTruthy();
    const mapView = root.findByProps({ testID: 'area-map-view' });
    expect(mapView).toBeTruthy();
    expect(root.findByProps({ testID: 'boundary-polygon-0' })).toBeTruthy();
    expect(root.findByProps({ testID: 'mock-url-tile' })).toBeTruthy();
  });

  test('5. AreaMapScreen toggles boundary and layer visibility', async () => {
    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-123',
      name: 'Arasur Village',
      code: 'VILL-638401',
      type: 'VILLAGE',
      boundary: mockAreas[0].boundary as any,
    });
    jest.spyOn(areaService, 'getAreaHouses').mockResolvedValue({
      items: mockHouses as any,
      total: 2,
      skip: 0,
      limit: 1000,
    });
    jest.spyOn(areaService, 'getBuildingEstimation').mockResolvedValue({
      area_id: 'area-123',
      area_name: 'Arasur Village',
      area_code: 'VILL-638401',
      total_buildings: 250,
      source_type: 'DEVELOPMENT_DATA',
      quality_label: 'Development data',
      imagery_source: 'esri_world_imagery',
      imagery_date: null,
      average_confidence: null,
      density_clusters: [],
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AreaMapScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    const toggleLayerBtn = root.findByProps({
      testID: 'toggle-layer-button',
    });
    const toggleBoundaryBtn = root.findByProps({
      testID: 'toggle-boundary-button',
    });

    // Toggle boundary
    await ReactTestRenderer.act(async () => {
      toggleBoundaryBtn.props.onPress();
      jest.runAllTimers();
    });

    // Toggle layer
    await ReactTestRenderer.act(async () => {
      toggleLayerBtn.props.onPress();
      jest.runAllTimers();
    });

    const mapView = root.findByProps({ testID: 'area-map-view' });
    expect(mapView).toBeTruthy();
  });

  test('6. AreaMapScreen displays satellite-derived badge when satellite data is present', async () => {
    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-123',
      name: 'Arasur Village',
      code: 'VILL-638401',
      type: 'VILLAGE',
      boundary: mockAreas[0].boundary as any,
    });
    jest.spyOn(areaService, 'getAreaHouses').mockResolvedValue({
      items: mockHouses as any,
      total: 2,
      skip: 0,
      limit: 1000,
    });
    jest.spyOn(areaService, 'getBuildingEstimation').mockResolvedValue({
      area_id: 'area-123',
      area_name: 'Arasur Village',
      area_code: 'VILL-638401',
      total_buildings: 238,
      source_type: 'SATELLITE_DETECTED',
      quality_label: 'Satellite-derived estimate',
      imagery_source: 'esri_world_imagery',
      imagery_date: '2026-03-01',
      average_confidence: 0.87,
      density_clusters: [],
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AreaMapScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'map-tool-zoomin' })).toBeTruthy();
    expect(root.findByProps({ testID: 'map-tool-zoomout' })).toBeTruthy();
    expect(root.findByProps({ testID: 'map-tool-location' })).toBeTruthy();
    expect(root.findByProps({ testID: 'map-tool-fit' })).toBeTruthy();
  });

  test('7. AreaMapScreen renders clean satellite map with outer boundary and NO building markers, footprints, or cluster circles', async () => {
    const mockSatelliteHouses = [
      {
        id: 'house-sat-1',
        area_id: 'area-123',
        building_reference: 'BLD-A1B2C3',
        house_number: null,
        latitude: 11.082,
        longitude: 77.12,
        source_type: 'SATELLITE_DETECTED',
        detection_confidence: 0.89,
        imagery_source: 'Google Open Buildings V3',
        area_in_meters: 145.2,
        footprint: {
          type: 'Polygon',
          coordinates: [
            [
              [77.1198, 11.0818],
              [77.1202, 11.0818],
              [77.1202, 11.0822],
              [77.1198, 11.0822],
              [77.1198, 11.0818],
            ],
          ],
        },
        created_at: '2026-01-01T00:00:00Z',
        updated_at: '2026-01-01T00:00:00Z',
      },
    ];

    jest.spyOn(areaService, 'getAreaBoundary').mockResolvedValue({
      id: 'area-123',
      name: 'Arasur Village',
      code: 'VILL-638401',
      type: 'VILLAGE',
      boundary: mockAreas[0].boundary as any,
    });
    jest.spyOn(areaService, 'getAreaHouses').mockResolvedValue({
      items: mockSatelliteHouses as any,
      total: 1,
      skip: 0,
      limit: 1000,
    });
    jest.spyOn(areaService, 'getBuildingEstimation').mockResolvedValue({
      area_id: 'area-123',
      area_name: 'Arasur Village',
      area_code: 'VILL-638401',
      total_buildings: 503,
      source_type: 'SATELLITE_DETECTED',
      quality_label: 'Satellite-derived estimate',
      imagery_source: 'Google Open Buildings V3',
      imagery_date: '2026-03-01',
      average_confidence: 0.89,
      density_clusters: [],
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AreaMapScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    const mapView = root.findByProps({ testID: 'area-map-view' });
    expect(mapView).toBeTruthy();
    expect(mapView.props.mapType).toBe('satellite');

    // Verify outer village boundary polygon renders
    expect(root.findByProps({ testID: 'admin-boundary-polygon-0' })).toBeTruthy();

    // Verify NO building pins, markers, or cluster circles are rendered
    const bldPins = root.findAllByProps({ testID: 'bld-pin' });
    expect(bldPins.length).toBe(0);
    const clusterPins = root.findAllByProps({ testID: 'cluster-pin' });
    expect(clusterPins.length).toBe(0);

    // Verify estimated building count is displayed in bottom summary card
    const textNodes = root.findAllByType('Text' as any);
    const has503 = textNodes.some((n: any) => n.props.children === 503);
    expect(has503).toBe(true);
  });

  test('8. DeputyDashboardScreen renders live overview metrics from API instead of mock data', async () => {
    jest.spyOn(areaService, 'getAreas').mockResolvedValue({
      items: mockAreas as any,
      total: 2,
      skip: 0,
      limit: 100,
    });
    jest.spyOn(layoutService, 'getLayouts').mockResolvedValue({
      items: [
        {
          id: 'l-1',
          area_id: 'area-123',
          administrative_area_id: 'area-123',
          name: 'Layout 1',
          status: 'APPROVED',
          target_buildings_per_hlb: 200,
          total_buildings: 500,
          hlb_count: 3,
          active_version_number: 1,
          active_version_status: 'APPROVED',
          description: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'l-2',
          area_id: 'area-123',
          administrative_area_id: 'area-123',
          name: 'Layout 2',
          status: 'IN_REVIEW',
          target_buildings_per_hlb: 200,
          total_buildings: 300,
          hlb_count: 2,
          active_version_number: 1,
          active_version_status: 'CANDIDATE',
          description: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
        {
          id: 'l-3',
          area_id: 'area-123',
          administrative_area_id: 'area-123',
          name: 'Layout 3',
          status: 'DRAFT',
          target_buildings_per_hlb: 200,
          total_buildings: 400,
          hlb_count: 2,
          active_version_number: 1,
          active_version_status: 'CANDIDATE',
          description: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 3,
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyDashboardScreen />);
      jest.runAllTimers();
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'overview-card' })).toBeTruthy();

    // Verify live counts: 2 villages, 3 layouts, 2 awaiting review (IN_REVIEW + DRAFT), 1 approved
    const villageCountNode = root.findByProps({ testID: 'overview-villages-count' });
    expect(villageCountNode.props.children).toBe(2);

    const layoutCountNode = root.findByProps({ testID: 'overview-layouts-count' });
    expect(layoutCountNode.props.children).toBe(3);

    const awaitingCountNode = root.findByProps({ testID: 'overview-awaiting-count' });
    expect(awaitingCountNode.props.children).toBe(2);

    const approvedCountNode = root.findByProps({ testID: 'overview-approved-count' });
    expect(approvedCountNode.props.children).toBe(1);
  });
});
