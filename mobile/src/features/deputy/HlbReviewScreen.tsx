import React, { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import {
  Modal,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  useColorScheme,
  ActivityIndicator,
  Alert,
  Platform,
  BackHandler,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { extractErrorMessage } from '../../core/apiClient';
import {
  AppHeader,
  Card,
  ErrorMessage,
  HlbSpatialMap,
  HlbSpatialMapRef,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
  StatusBadge,
} from '../../components';
import { AreaBoundaryResponse, GeoJSONGeometry, areaService } from '../../core/areaService';
import {
  layoutService,
  LayoutSummary,
  HlbCandidate,
  LayoutValidationResponse,
  SplitPreviewResult,
  MergePreviewResult,
} from '../../core/layoutService';
import { simplifyPolygonForEditing } from '../../core/geometryUtils';
import { useTranslation } from '../../core/localization';
import { SupervisorAssignmentModal } from './SupervisorAssignmentModal';
import type { DeputyNavigationProp, DeputyStackParamList } from '../../navigation/navigationTypes';

interface LatLng {
  latitude: number;
  longitude: number;
}

const HLB_PALETTE = [
  { fill: 'rgba(2, 132, 199, 0.08)', stroke: '#0284C7', text: '#0284C7', lightBg: '#E0F2FE' },
  { fill: 'rgba(16, 185, 129, 0.08)', stroke: '#10B981', text: '#10B981', lightBg: '#D1FAE5' },
  { fill: 'rgba(139, 92, 246, 0.08)', stroke: '#8B5CF6', text: '#8B5CF6', lightBg: '#EDE9FE' },
  { fill: 'rgba(245, 158, 11, 0.08)', stroke: '#F59E0B', text: '#D97706', lightBg: '#FEF3C7' },
  { fill: 'rgba(236, 72, 153, 0.08)', stroke: '#EC4899', text: '#DB2777', lightBg: '#FCE7F3' },
  { fill: 'rgba(20, 184, 166, 0.08)', stroke: '#14B8A6', text: '#0D9488', lightBg: '#CCFBF1' },
  { fill: 'rgba(99, 102, 241, 0.08)', stroke: '#6366F1', text: '#4F46E5', lightBg: '#E0E7FF' },
  { fill: 'rgba(234, 88, 12, 0.08)', stroke: '#EA580C', text: '#C2410C', lightBg: '#FFEDD5' },
];

function parseGeoJSONToRings(geom: GeoJSONGeometry | any | null | undefined): LatLng[][] {
  if (!geom || !geom.coordinates) return [];
  const rings: LatLng[][] = [];

  if (geom.type === 'Polygon' && Array.isArray(geom.coordinates)) {
    for (const ring of geom.coordinates) {
      if (Array.isArray(ring)) {
        rings.push(
          ring.map((coord: [number, number]) => ({
            latitude: Number(coord[1]),
            longitude: Number(coord[0]),
          }))
        );
      }
    }
  } else if (geom.type === 'MultiPolygon' && Array.isArray(geom.coordinates)) {
    for (const poly of geom.coordinates) {
      if (Array.isArray(poly)) {
        for (const ring of poly) {
          if (Array.isArray(ring)) {
            rings.push(
              ring.map((coord: [number, number]) => ({
                latitude: Number(coord[1]),
                longitude: Number(coord[0]),
              }))
            );
          }
        }
      }
    }
  }
  return rings;
}

export function HlbReviewScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const route = useRoute<RouteProp<DeputyStackParamList, 'HlbReview'>>();
  const { t } = useTranslation();

  const routeParams = (route.params || {}) as Partial<DeputyStackParamList['HlbReview']>;
  const layoutId = routeParams.layoutId;
  const areaName = routeParams.areaName || 'Village';
  const areaCode = routeParams.areaCode || 'VILL-638401';

  const mapRef = useRef<HlbSpatialMapRef | null>(null);

  const [layout, setLayout] = useState<LayoutSummary | null>(null);
  const [boundaryData, setBoundaryData] = useState<AreaBoundaryResponse | null>(null);
  const [candidateHlbs, setCandidateHlbs] = useState<HlbCandidate[]>([]);
  const [validationData, setValidationData] = useState<LayoutValidationResponse | null>(null);
  const [selectedHlb, setSelectedHlb] = useState<HlbCandidate | null>(null);

  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionStep, setActionStep] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // ----------------------------------------------------
  // Part A: Map-based Boundary Editing State
  // ----------------------------------------------------
  const [isEditingBoundary, setIsEditingBoundary] = useState(false);
  const [editingBoundaryCoords, setEditingBoundaryCoords] = useState<LatLng[]>([]);
  const [originalBoundaryCoords, setOriginalBoundaryCoords] = useState<LatLng[]>([]);
  const [selectedVertexIndex, setSelectedVertexIndex] = useState<number | null>(null);

  // ----------------------------------------------------
  // Part B: Split Modal State
  // ----------------------------------------------------
  const [showSplitModal, setShowSplitModal] = useState(false);
  const [splitMethod, setSplitMethod] = useState<'AUTO_BALANCED' | 'TARGET_BASED' | 'DRAW_SPLIT_LINE' | 'DRAW_LINE'>('AUTO_BALANCED');
  const [sideACountStr, setSideACountStr] = useState<string>('70');
  const [sideBCountStr, setSideBCountStr] = useState<string>('70');
  const [splitLineCoords, setSplitLineCoords] = useState<LatLng[]>([]);
  const [splitPreview, setSplitPreview] = useState<SplitPreviewResult | null>(null);
  const [splitPreviewLoading, setSplitPreviewLoading] = useState(false);

  // ----------------------------------------------------
  // Part C: Merge Modal State
  // ----------------------------------------------------
  const [showMergeModal, setShowMergeModal] = useState(false);
  const [selectedMergeHlbIds, setSelectedMergeHlbIds] = useState<string[]>([]);
  const [mergePreview, setMergePreview] = useState<MergePreviewResult | null>(null);
  const [mergePreviewLoading, setMergePreviewLoading] = useState(false);
  const [showSupervisorModal, setShowSupervisorModal] = useState(false);

  const loadLayoutData = useCallback(async () => {
    if (!layoutId) {
      setError('Layout ID is missing. Please return and select a layout.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [layoutRes, hlbsRes, validationRes] = await Promise.all([
        layoutService.getLayout(layoutId),
        layoutService.getLayoutHlbs(layoutId),
        layoutService.validateLayout(layoutId).catch(() => null),
      ]);

      setLayout(layoutRes);
      setCandidateHlbs(hlbsRes.items || []);
      setValidationData(validationRes);

      // Select first HLB by default if none selected or maintain current selection
      if (hlbsRes.items && hlbsRes.items.length > 0) {
        setSelectedHlb((prev) => {
          if (!prev) return hlbsRes.items[0];
          const updatedSelected = hlbsRes.items.find((h) => h.id === prev.id);
          return updatedSelected || hlbsRes.items[0];
        });
      }

      const areaId = layoutRes.area_id || layoutRes.administrative_area_id;
      if (areaId) {
        try {
          const boundaryRes = await areaService.getAreaBoundary(areaId);
          setBoundaryData(boundaryRes);
        } catch {
          // Fallback if boundary endpoint unavailable
        }
      }
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [layoutId]);

  useEffect(() => {
    loadLayoutData();
  }, [loadLayoutData]);

  const layoutRings = useMemo(() => {
    return parseGeoJSONToRings(boundaryData?.boundary || layout?.boundary);
  }, [boundaryData, layout]);

  const mapHlbItems = useMemo(() => {
    return candidateHlbs.map((hlb, index) => {
      const palette = HLB_PALETTE[index % HLB_PALETTE.length];
      return {
        id: hlb.id,
        block_code: hlb.block_code,
        hlb_code: hlb.block_code,
        boundary: hlb.boundary,
        centroid: hlb.centroid,
        actual_building_count: hlb.actual_building_count,
        building_count: hlb.actual_building_count,
        target_building_count: hlb.target_building_count,
        quality_score: hlb.quality_score,
        validation_status: hlb.validation_status,
        strokeColor: palette.stroke,
        fillColor: palette.fill,
      };
    });
  }, [candidateHlbs]);

  const fitCoordinates = useMemo(() => {
    if (layoutRings.length > 0) {
      return layoutRings.flat();
    }
    const coords: LatLng[] = [];
    for (const hlb of candidateHlbs) {
      const rings = parseGeoJSONToRings(hlb.boundary);
      coords.push(...rings.flat());
    }
    return coords;
  }, [layoutRings, candidateHlbs]);

  // Handle back navigation with unsaved changes guard
  const handleBack = useCallback(() => {
    if (isEditingBoundary || splitLineCoords.length > 0) {
      Alert.alert(
        'Unsaved Changes',
        'You have active boundary or split modifications. Are you sure you want to discard them and leave?',
        [
          { text: 'Keep Editing', style: 'cancel' },
          {
            text: 'Discard & Exit',
            style: 'destructive',
            onPress: () => navigation.goBack(),
          },
        ]
      );
      return true;
    }
    navigation.goBack();
    return true;
  }, [isEditingBoundary, splitLineCoords, navigation]);

  useEffect(() => {
    const backHandler = BackHandler.addEventListener('hardwareBackPress', handleBack);
    return () => backHandler.remove();
  }, [handleBack]);

  // Handle HLB selection
  const handleSelectHlb = (hlbItem: { id: string }) => {
    if (isEditingBoundary) return; // Ignore selection during active boundary edit
    const found = candidateHlbs.find((h) => h.id === hlbItem.id);
    if (found) {
      setSelectedHlb(found);
      const rings = parseGeoJSONToRings(found.boundary);
      if (rings.length > 0 && mapRef.current) {
        mapRef.current.fitToCoordinates(rings.flat());
      }
    }
  };

  // ====================================================
  // PART A — Visual Map Boundary Editing Handlers
  // ====================================================
  const handleStartBoundaryEdit = () => {
    if (!selectedHlb) return;
    const rings = parseGeoJSONToRings(selectedHlb.boundary);
    const flatCoords = rings.length > 0 ? rings[0] : [];
    if (flatCoords.length < 3) {
      setError('Selected HLB has insufficient vertices to edit.');
      return;
    }

    // Automatically simplify boundary to minimal, clean draggable control points (6 to 8 points)
    const simplified = simplifyPolygonForEditing(flatCoords, 8, 4);

    setOriginalBoundaryCoords(flatCoords);
    setEditingBoundaryCoords(simplified);
    setSelectedVertexIndex(null);
    setIsEditingBoundary(true);
    setError(null);
    setSuccessMessage(null);

    // Zoom map to the editing polygon
    if (mapRef.current) {
      mapRef.current.fitToCoordinates(simplified.length > 0 ? simplified : flatCoords);
    }
  };

  const handleAddBoundaryPoint = () => {
    if (editingBoundaryCoords.length < 2) return;
    const insertIdx = selectedVertexIndex !== null ? selectedVertexIndex : 0;
    const p1 = editingBoundaryCoords[insertIdx];
    const p2 = editingBoundaryCoords[(insertIdx + 1) % editingBoundaryCoords.length];
    const newPt: LatLng = {
      latitude: (p1.latitude + p2.latitude) / 2,
      longitude: (p1.longitude + p2.longitude) / 2,
    };

    const updated = [...editingBoundaryCoords];
    updated.splice(insertIdx + 1, 0, newPt);
    setEditingBoundaryCoords(updated);
    setSelectedVertexIndex(insertIdx + 1);
  };

  const handleRemoveBoundaryPoint = () => {
    if (editingBoundaryCoords.length <= 3) {
      Alert.alert('Polygon Limit', 'A valid boundary polygon requires at least 3 points.');
      return;
    }
    const removeIdx = selectedVertexIndex !== null ? selectedVertexIndex : editingBoundaryCoords.length - 1;
    const updated = editingBoundaryCoords.filter((_, idx) => idx !== removeIdx);
    setEditingBoundaryCoords(updated);
    setSelectedVertexIndex(null);
  };

  const handleSimplifyBoundary = () => {
    const simplified = simplifyPolygonForEditing(editingBoundaryCoords, 6, 4);
    setEditingBoundaryCoords(simplified);
    setSelectedVertexIndex(null);
  };

  const handleResetBoundary = () => {
    const simplified = simplifyPolygonForEditing(originalBoundaryCoords, 8, 4);
    setEditingBoundaryCoords(simplified);
    setSelectedVertexIndex(null);
  };

  const handleCancelBoundaryEdit = () => {
    setIsEditingBoundary(false);
    setEditingBoundaryCoords([]);
    setOriginalBoundaryCoords([]);
    setSelectedVertexIndex(null);
  };

  const handleSaveBoundary = async () => {
    if (!selectedHlb || editingBoundaryCoords.length < 3) {
      Alert.alert('Invalid Boundary', 'Boundary must have at least 3 coordinates.');
      return;
    }

    // Ensure polygon is closed
    const coords = editingBoundaryCoords.map((c) => [c.longitude, c.latitude]);
    if (coords[0][0] !== coords[coords.length - 1][0] || coords[0][1] !== coords[coords.length - 1][1]) {
      coords.push([...coords[0]]);
    }

    const newPolygonGeoJson = {
      type: 'Polygon',
      coordinates: [coords],
    };

    try {
      setActionLoading(true);
      setActionStep('Validating geometry and recalculating building assignments...');
      setError(null);

      const result = await layoutService.editHlbBoundary(selectedHlb.id, newPolygonGeoJson);
      setSuccessMessage(
        `Boundary for ${result.block_code} updated successfully. Building count: ${result.actual_building_count} (${result.validation_status}).`
      );
      setIsEditingBoundary(false);
      setEditingBoundaryCoords([]);
      setOriginalBoundaryCoords([]);
      await loadLayoutData();
    } catch (err: any) {
      setError(extractErrorMessage(err) || 'Unable to save HLB boundary. Please check the boundary and try again.');
    } finally {
      setActionLoading(false);
    }
  };

  // ====================================================
  // PART B — Split HLB Handlers & Preview
  // ====================================================
  const handleOpenSplitModal = async () => {
    if (!selectedHlb) return;
    setSplitMethod('AUTO_BALANCED');
    const total = selectedHlb.actual_building_count || 10;
    const half = Math.max(1, Math.round(total / 2));
    const sideB = Math.max(1, total - half);
    setSideACountStr(String(half));
    setSideBCountStr(String(sideB));
    setSplitLineCoords([]);
    setSplitPreview(null);
    setShowSplitModal(true);

    // Automatically trigger initial auto-balanced preview
    fetchSplitPreview('AUTO_BALANCED', half, []);
  };

  const handleSideAChange = (val: string) => {
    setSideACountStr(val);
    const total = selectedHlb?.actual_building_count || 0;
    const countA = parseInt(val, 10);
    if (!isNaN(countA) && countA > 0 && countA < total) {
      setSideBCountStr(String(total - countA));
      fetchSplitPreview('TARGET_BASED', countA);
    }
  };

  const handleSideBChange = (val: string) => {
    setSideBCountStr(val);
    const total = selectedHlb?.actual_building_count || 0;
    const countB = parseInt(val, 10);
    if (!isNaN(countB) && countB > 0 && countB < total) {
      const derivedA = total - countB;
      setSideACountStr(String(derivedA));
      fetchSplitPreview('TARGET_BASED', derivedA);
    }
  };

  const handleSplitLineChange = (coords: LatLng[]) => {
    setSplitLineCoords(coords);
    setSplitPreview(null);
    if (coords.length >= 2) {
      fetchSplitPreview('DRAW_LINE', undefined, coords);
    }
  };

  const handleClearSplitLine = () => {
    setSplitLineCoords([]);
    setSplitPreview(null);
  };

  const handleUndoSplitLinePoint = () => {
    const updated = splitLineCoords.slice(0, -1);
    setSplitLineCoords(updated);
    setSplitPreview(null);
    if (updated.length >= 2) {
      fetchSplitPreview('DRAW_LINE', undefined, updated);
    }
  };

  const handleApplyHorizontalCutPreset = () => {
    if (!selectedHlb) return;
    const rings = parseGeoJSONToRings(selectedHlb.boundary);
    const coords = rings.flat();
    if (coords.length === 0) return;

    let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    for (const c of coords) {
      if (c.latitude < minLat) minLat = c.latitude;
      if (c.latitude > maxLat) maxLat = c.latitude;
      if (c.longitude < minLng) minLng = c.longitude;
      if (c.longitude > maxLng) maxLng = c.longitude;
    }
    const midLat = (minLat + maxLat) / 2;
    const dLng = Math.max((maxLng - minLng) * 0.2, 0.0005);

    const line: LatLng[] = [
      { latitude: midLat, longitude: minLng - dLng },
      { latitude: midLat, longitude: maxLng + dLng },
    ];
    setSplitLineCoords(line);
    setSplitPreview(null);
    fetchSplitPreview('DRAW_LINE', undefined, line);
  };

  const handleApplyVerticalCutPreset = () => {
    if (!selectedHlb) return;
    const rings = parseGeoJSONToRings(selectedHlb.boundary);
    const coords = rings.flat();
    if (coords.length === 0) return;

    let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    for (const c of coords) {
      if (c.latitude < minLat) minLat = c.latitude;
      if (c.latitude > maxLat) maxLat = c.latitude;
      if (c.longitude < minLng) minLng = c.longitude;
      if (c.longitude > maxLng) maxLng = c.longitude;
    }
    const midLng = (minLng + maxLng) / 2;
    const dLat = Math.max((maxLat - minLat) * 0.2, 0.0005);

    const line: LatLng[] = [
      { latitude: maxLat + dLat, longitude: midLng },
      { latitude: minLat - dLat, longitude: midLng },
    ];
    setSplitLineCoords(line);
    setSplitPreview(null);
    fetchSplitPreview('DRAW_LINE', undefined, line);
  };

  const handleApplyDiagonalCutPreset = () => {
    if (!selectedHlb) return;
    const rings = parseGeoJSONToRings(selectedHlb.boundary);
    const coords = rings.flat();
    if (coords.length === 0) return;

    let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    for (const c of coords) {
      if (c.latitude < minLat) minLat = c.latitude;
      if (c.latitude > maxLat) maxLat = c.latitude;
      if (c.longitude < minLng) minLng = c.longitude;
      if (c.longitude > maxLng) maxLng = c.longitude;
    }
    const dLng = Math.max((maxLng - minLng) * 0.2, 0.0005);
    const dLat = Math.max((maxLat - minLat) * 0.2, 0.0005);

    const line: LatLng[] = [
      { latitude: maxLat + dLat, longitude: minLng - dLng },
      { latitude: minLat - dLat, longitude: maxLng + dLng },
    ];
    setSplitLineCoords(line);
    setSplitPreview(null);
    fetchSplitPreview('DRAW_LINE', undefined, line);
  };

  const handleApplyUnevenCutPreset = () => {
    if (!selectedHlb) return;
    const rings = parseGeoJSONToRings(selectedHlb.boundary);
    const coords = rings.flat();
    if (coords.length === 0) return;

    let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
    for (const c of coords) {
      if (c.latitude < minLat) minLat = c.latitude;
      if (c.latitude > maxLat) maxLat = c.latitude;
      if (c.longitude < minLng) minLng = c.longitude;
      if (c.longitude > maxLng) maxLng = c.longitude;
    }
    const cutLat = minLat + (maxLat - minLat) * 0.3;
    const dLng = Math.max((maxLng - minLng) * 0.2, 0.0005);

    const line: LatLng[] = [
      { latitude: cutLat, longitude: minLng - dLng },
      { latitude: cutLat, longitude: maxLng + dLng },
    ];
    setSplitLineCoords(line);
    setSplitPreview(null);
    fetchSplitPreview('DRAW_LINE', undefined, line);
  };

  const fetchSplitPreview = async (
    method: 'AUTO_BALANCED' | 'TARGET_BASED' | 'DRAW_SPLIT_LINE' | 'DRAW_LINE',
    targetCount?: number,
    lineCoords?: LatLng[]
  ) => {
    if (!selectedHlb) return;
    setSplitPreviewLoading(true);
    try {
      const lineArray = lineCoords && lineCoords.length > 0 ? lineCoords.map((c) => [c.longitude, c.latitude]) : undefined;
      const apiMethod = (method === 'DRAW_SPLIT_LINE' || method === 'DRAW_LINE') ? 'DRAW_LINE' : method;
      const previewRes = await layoutService.previewSplitHlb(selectedHlb.id, {
        split_method: apiMethod as any,
        split_ratio: 0.5,
        target_building_count: targetCount,
        split_line_coordinates: lineArray,
      });
      setSplitPreview(previewRes);
    } catch (err: any) {
      setSplitPreview({
        is_valid: false,
        side_a_block_code: `${selectedHlb.block_code}A`,
        side_a_building_count: 0,
        side_b_block_code: `${selectedHlb.block_code}B`,
        side_b_building_count: 0,
        total_original_buildings: selectedHlb.actual_building_count,
        validation_errors: [extractErrorMessage(err) || 'Unable to create a valid split with current parameters.'],
      });
    } finally {
      setSplitPreviewLoading(false);
    }
  };

  const handleConfirmSplit = async () => {
    if (!selectedHlb || !splitPreview?.is_valid) return;
    try {
      setActionLoading(true);
      setActionStep(`Spatially splitting ${selectedHlb.block_code}...`);
      setShowSplitModal(false);

      const targetCountNum = parseInt(sideACountStr, 10);
      const lineArray = splitLineCoords.length > 0 ? splitLineCoords.map((c) => [c.longitude, c.latitude]) : undefined;

      const splitRes = await layoutService.splitHlb(selectedHlb.id, {
        split_method: splitMethod,
        split_ratio: 0.5,
        target_building_count: splitMethod === 'TARGET_BASED' && !isNaN(targetCountNum) ? targetCountNum : undefined,
        split_line_coordinates: (splitMethod === 'DRAW_SPLIT_LINE' || splitMethod === 'DRAW_LINE') ? lineArray : undefined,
      });

      setSuccessMessage(
        `Successfully split into ${splitRes.split_hlb_a.block_code} (${splitRes.split_hlb_a.actual_building_count} bldgs) and ${splitRes.split_hlb_b.block_code} (${splitRes.split_hlb_b.actual_building_count} bldgs).`
      );
      setSelectedHlb(splitRes.split_hlb_a);
      await loadLayoutData();
    } catch (err: any) {
      setError(extractErrorMessage(err) || 'Unable to execute split. Please adjust the split parameters.');
    } finally {
      setActionLoading(false);
    }
  };

  // ====================================================
  // PART C — Merge HLB Handlers & Preview
  // ====================================================
  const handleOpenMergeModal = () => {
    if (!selectedHlb) return;
    const initialSelection = [selectedHlb.id];
    // Find first adjacent or next candidate
    const other = candidateHlbs.find((h) => h.id !== selectedHlb.id);
    if (other) {
      initialSelection.push(other.id);
    }
    setSelectedMergeHlbIds(initialSelection);
    setShowMergeModal(true);
    setMergePreview(null);

    if (initialSelection.length === 2) {
      fetchMergePreview(initialSelection[0], initialSelection[1]);
    }
  };

  const toggleMergeSelection = (hlbId: string) => {
    let updated: string[];
    if (selectedMergeHlbIds.includes(hlbId)) {
      updated = selectedMergeHlbIds.filter((id) => id !== hlbId);
    } else {
      if (selectedMergeHlbIds.length >= 2) {
        // Replace second selection to keep exactly 2
        updated = [selectedMergeHlbIds[0], hlbId];
      } else {
        updated = [...selectedMergeHlbIds, hlbId];
      }
    }
    setSelectedMergeHlbIds(updated);

    if (updated.length === 2) {
      fetchMergePreview(updated[0], updated[1]);
    } else {
      setMergePreview(null);
    }
  };

  const fetchMergePreview = async (id1: string, id2: string) => {
    setMergePreviewLoading(true);
    try {
      const previewRes = await layoutService.previewMergeHlbs(id1, id2);
      setMergePreview(previewRes);
    } catch (err: any) {
      setMergePreview({
        is_valid: false,
        is_adjacent: false,
        merged_block_code: 'MERGE-FAILED',
        combined_building_count: 0,
        building_assignment_status: 'Error',
        validation_errors: [
          extractErrorMessage(err) || 'Selected HLBs cannot be merged because they are not geographically adjacent.',
        ],
      });
    } finally {
      setMergePreviewLoading(false);
    }
  };

  const handleConfirmMerge = async () => {
    if (selectedMergeHlbIds.length !== 2 || !mergePreview?.is_valid) return;
    try {
      setActionLoading(true);
      setActionStep(`Merging HLBs...`);
      setShowMergeModal(false);

      const mergeRes = await layoutService.mergeHlbs(selectedMergeHlbIds[0], selectedMergeHlbIds[1]);
      setSuccessMessage(
        `Merged into ${mergeRes.merged_hlb.block_code} (${mergeRes.merged_hlb.actual_building_count} total buildings).`
      );
      setSelectedHlb(mergeRes.merged_hlb);
      setSelectedMergeHlbIds([]);
      await loadLayoutData();
    } catch (err: any) {
      setError(
        extractErrorMessage(err) || 'Selected HLBs cannot be merged because they are not geographically adjacent.'
      );
    } finally {
      setActionLoading(false);
    }
  };

  // ====================================================
  // Final Approval Action
  // ====================================================
  const handleApproveLayout = async () => {
    if (!layoutId) return;
    try {
      setActionLoading(true);
      setActionStep('Validating and creating immutable approved layout version...');
      const approveRes = await layoutService.approveLayout(layoutId);
      setSuccessMessage(`Layout "${approveRes.name}" approved successfully as Version v${approveRes.version_number}!`);
      await loadLayoutData();
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setActionLoading(false);
    }
  };

  const isApproved = layout?.status === 'APPROVED';
  const totalAssigned = candidateHlbs.reduce((sum, h) => sum + h.actual_building_count, 0);
  const totalBuildings = layout?.total_buildings || layout?.actual_building_count || totalAssigned;
  const targetBuildingsPerHlb = layout?.target_buildings_per_hlb || 200;

  return (
    <ScreenContainer
      testID="hlb-review-screen"
      style={[styles.container, { backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC' }]}
    >
      <AppHeader
        title={t('hlb_review_approval') || 'HLB Review & Approval'}
        subtitle={`${areaName} (${areaCode})`}
        showBack
        onBack={handleBack}
        testID="hlb-review-header"
      />

      {loading ? (
        <View style={styles.loadingContainer} testID="loading-view">
          <ActivityIndicator size="large" color="#38BDF8" />
          <Text style={[styles.loadingText, { color: isDarkMode ? '#CBD5E1' : '#475569' }]}>
            Loading candidate layout and HLBs...
          </Text>
        </View>
      ) : (
        <ScrollView contentContainerStyle={styles.scrollContent} showsVerticalScrollIndicator={false}>
          {error && <ErrorMessage message={error} testID="error-message" />}

          {successMessage && (
            <View style={styles.successBanner} testID="success-banner">
              <Text style={styles.successIcon}>✓</Text>
              <Text style={styles.successText}>{successMessage}</Text>
            </View>
          )}

          {/* 1. Layout Header Badge Card */}
          <Card testID="layout-header-card" style={[styles.card, { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' }]}>
            <View style={styles.headerRow}>
              <View>
                <Text style={[styles.villageTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                  {areaName}
                </Text>
                <Text style={[styles.villageCode, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                  {areaCode} • Layout: {layout?.name || 'Candidate'}
                </Text>
              </View>
              <View style={styles.badgeCol}>
                <StatusBadge
                  status={isApproved ? 'APPROVED' : 'REVIEW'}
                  testID="layout-status-badge"
                />
                <Text style={[styles.versionLabel, { color: isDarkMode ? '#38BDF8' : '#0284C7' }]}>
                  Version: v{layout?.active_version_number || 1}
                </Text>
              </View>
            </View>
          </Card>

          {/* 2. Summary Metrics Card */}
          <Card testID="layout-summary-card" style={[styles.card, { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' }]}>
            <Text style={[styles.sectionTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
              LAYOUT SUMMARY
            </Text>
            <View style={{ marginBottom: 8, padding: 8, borderRadius: 6, backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9' }} testID="workload-unit-banner">
              <Text style={{ fontSize: 12, fontWeight: '600', color: isDarkMode ? '#38BDF8' : '#0284C7' }}>
                Workload Unit: {layout?.workload_unit || 'BUILDINGS'} • Target: {layout?.target_workload || targetBuildingsPerHlb} per HLB
              </Text>
              <Text style={{ fontSize: 11, color: isDarkMode ? '#94A3B8' : '#64748B', marginTop: 2 }}>
                Estimated Census Houses: {layout?.estimated_census_house_count ?? Math.round(totalBuildings * 0.3124)} (Census 2011 PCA Ratio)
              </Text>
            </View>
            <View style={styles.metricsGrid}>
              <View style={styles.metricBox}>
                <Text style={[styles.metricValue, { color: isDarkMode ? '#38BDF8' : '#0284C7' }]}>
                  {totalBuildings}
                </Text>
                <Text style={[styles.metricLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                  Detected Buildings
                </Text>
              </View>
              <View style={styles.metricBox}>
                <Text style={[styles.metricValue, { color: isDarkMode ? '#10B981' : '#059669' }]}>
                  {targetBuildingsPerHlb}
                </Text>
                <Text style={[styles.metricLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                  Target / HLB
                </Text>
              </View>
              <View style={styles.metricBox}>
                <Text style={[styles.metricValue, { color: isDarkMode ? '#A855F7' : '#7C3AED' }]}>
                  {candidateHlbs.length}
                </Text>
                <Text style={[styles.metricLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                  Candidate HLBs
                </Text>
              </View>
              <View style={styles.metricBox}>
                <Text style={[styles.metricValue, { color: isDarkMode ? '#F59E0B' : '#D97706' }]}>
                  {totalAssigned} / {totalBuildings}
                </Text>
                <Text style={[styles.metricLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                  Assigned
                </Text>
              </View>
            </View>
          </Card>

          {/* 3. HLB Spatial Partitioning Map with Fullscreen & Boundary Edit */}
          <Card testID="hlb-spatial-map-card" style={[styles.card, styles.mapCard, { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' }]}>
            {(layout?.boundary_status === 'PROVISIONAL' || selectedHlb?.boundary_status === 'PROVISIONAL') && (
              <View style={styles.provisionalBanner} testID="provisional-boundary-badge">
                <Text style={styles.provisionalBannerText}>
                  ⚠️ PROVISIONAL BOUNDARY — Pending official Survey of India Gazette confirmation
                </Text>
              </View>
            )}
            <View style={styles.mapHeaderRow}>
              <Text style={[styles.sectionTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                {isEditingBoundary ? `EDITING BOUNDARY: ${selectedHlb?.block_code}` : 'HLB SPATIAL REVIEW'}
              </Text>
              <Text style={[styles.mapBadge, { color: isEditingBoundary ? '#F59E0B' : '#38BDF8' }]}>
                {isEditingBoundary ? 'Interactive Vertex Handles' : 'Satellite View • Clean Boundaries'}
              </Text>
            </View>

            {/* Interactive Map Boundary Editing Toolbar */}
            {isEditingBoundary && (
              <View style={styles.mapEditingToolbar} testID="map-editing-toolbar">
                <View style={styles.editingToolbarRow}>
                  <TouchableOpacity
                    style={styles.toolBtn}
                    onPress={handleAddBoundaryPoint}
                    testID="add-point-btn"
                    accessibilityLabel="Add boundary point"
                  >
                    <Text style={styles.toolBtnText}>+ Add Point</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[styles.toolBtn, styles.toolBtnDanger]}
                    onPress={handleRemoveBoundaryPoint}
                    testID="remove-point-btn"
                    accessibilityLabel="Remove boundary point"
                  >
                    <Text style={styles.toolBtnText}>− Remove Point</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.toolBtn}
                    onPress={handleSimplifyBoundary}
                    testID="minimize-points-btn"
                    accessibilityLabel="Minimize boundary points"
                  >
                    <Text style={styles.toolBtnText}>⚡ Minimize</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={styles.toolBtn}
                    onPress={handleResetBoundary}
                    testID="reset-boundary-btn"
                    accessibilityLabel="Reset boundary changes"
                  >
                    <Text style={styles.toolBtnText}>↺ Reset</Text>
                  </TouchableOpacity>
                </View>

                <View style={styles.editingToolbarBottomRow}>
                  <TouchableOpacity
                    style={[styles.toolBtnSecondary, { flex: 1 }]}
                    onPress={handleCancelBoundaryEdit}
                    testID="cancel-boundary-edit-btn"
                  >
                    <Text style={styles.toolBtnSecondaryText}>Cancel</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[styles.toolBtnPrimary, { flex: 1.5 }]}
                    onPress={handleSaveBoundary}
                    disabled={actionLoading}
                    testID="save-boundary-btn"
                    accessibilityLabel="Save boundary"
                  >
                    <Text style={styles.toolBtnPrimaryText}>
                      {actionLoading ? 'Saving...' : '✓ Save Boundary'}
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
            )}

            <View style={styles.mapContainer} testID="review-map-container">
              <HlbSpatialMap
                ref={mapRef}
                testID="hlb-review-spatial-map"
                mapType="satellite"
                showBoundary={true}
                boundaryRings={layoutRings}
                boundaryStrokeColor="#38BDF8"
                candidateHlbs={mapHlbItems}
                selectedHlbId={selectedHlb?.id}
                highlightHlbIds={showMergeModal ? selectedMergeHlbIds : []}
                onSelectHlb={handleSelectHlb}
                fitCoordinates={fitCoordinates}
                fullscreenEnabled={true}
                fullscreenTitle={`${areaName} • HLB Partition Map`}
                isEditingBoundary={isEditingBoundary}
                editingHlbId={selectedHlb?.id}
                editingBoundaryCoords={editingBoundaryCoords}
                originalBoundaryCoords={originalBoundaryCoords}
                selectedVertexIndex={selectedVertexIndex}
                onVertexChange={setEditingBoundaryCoords}
                onSelectVertex={setSelectedVertexIndex}
              />
            </View>
          </Card>

          {/* 4. Selected HLB Detail Panel */}
          {selectedHlb && !isEditingBoundary && (
            <Card testID="selected-hlb-detail-card" style={[styles.card, styles.selectedCard, { backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9' }]}>
              <View style={styles.selectedHeaderRow}>
                <View>
                  <Text style={[styles.selectedTitle, { color: isDarkMode ? '#38BDF8' : '#0284C7' }]}>
                    {selectedHlb.block_code}
                  </Text>
                  <Text style={[styles.selectedSub, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                    {selectedHlb.name || 'Candidate Block'}
                  </Text>
                </View>
                <StatusBadge status={selectedHlb.validation_status} testID="selected-hlb-status" />
              </View>

              <View style={styles.detailGrid}>
                <View style={styles.detailItem}>
                  <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                    Detected Buildings
                  </Text>
                  <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                    {selectedHlb.actual_building_count}
                  </Text>
                </View>
                <View style={styles.detailItem}>
                  <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                    Target Sizing
                  </Text>
                  <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                    {selectedHlb.target_building_count}
                  </Text>
                </View>
                <View style={styles.detailItem}>
                  <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                    Deviation
                  </Text>
                  <Text
                    style={[
                      styles.detailVal,
                      {
                        color:
                          (selectedHlb.count_deviation || 0) > 0
                            ? '#F59E0B'
                            : isDarkMode
                            ? '#F1F5F9'
                            : '#0F172A',
                      },
                    ]}
                  >
                    {selectedHlb.count_deviation != null
                      ? selectedHlb.count_deviation > 0
                        ? `+${selectedHlb.count_deviation}`
                        : selectedHlb.count_deviation
                      : `${selectedHlb.actual_building_count - selectedHlb.target_building_count}`}
                  </Text>
                </View>
                <View style={styles.detailItem}>
                  <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                    Quality Score
                  </Text>
                  <Text style={[styles.detailVal, { color: isDarkMode ? '#10B981' : '#059669' }]}>
                    {Math.round((selectedHlb.quality_score || 1.0) * 100)}%
                  </Text>
                </View>
                <View style={styles.detailItem}>
                  <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                    Est. Census Houses
                  </Text>
                  <Text style={[styles.detailVal, { color: isDarkMode ? '#38BDF8' : '#0284C7' }]}>
                    {(selectedHlb as any).estimated_census_house_count ?? Math.round(selectedHlb.actual_building_count * 0.3124)} est.
                  </Text>
                </View>
              </View>

              {/* Spatial Quality Metrics Grid */}
              {selectedHlb.validation_details?.quality_metrics && (
                <View style={styles.qualityMetricsSection} testID="hlb-quality-metrics-section">
                  <Text style={[styles.sectionSubtitle, { color: isDarkMode ? '#38BDF8' : '#0284C7' }]}>
                    Spatial Quality Metrics
                  </Text>
                  <View style={styles.detailGrid}>
                    <View style={styles.detailItem}>
                      <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                        Area
                      </Text>
                      <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                        {Math.round(selectedHlb.validation_details.quality_metrics.area_sq_meters || 0).toLocaleString()} m²
                      </Text>
                    </View>
                    <View style={styles.detailItem}>
                      <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                        Polsby-Popper
                      </Text>
                      <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                        {((selectedHlb.validation_details.quality_metrics.compactness || 0) * 100).toFixed(1)}%
                      </Text>
                    </View>
                    <View style={styles.detailItem}>
                      <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                        Longest Axis
                      </Text>
                      <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                        {Math.round(selectedHlb.validation_details.quality_metrics.longest_axis_meters || 0)}m
                      </Text>
                    </View>
                    <View style={styles.detailItem}>
                      <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                        Road Crossings
                      </Text>
                      <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                        {selectedHlb.validation_details.quality_metrics.road_segments_crossed_count ?? 0}
                      </Text>
                    </View>
                    <View style={styles.detailItem}>
                      <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                        Intersecting Bldgs
                      </Text>
                      <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                        {selectedHlb.validation_details.quality_metrics.boundary_intersecting_buildings_count ?? 0}
                      </Text>
                    </View>
                    <View style={styles.detailItem}>
                      <Text style={[styles.detailLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                        Est. Walk Dist
                      </Text>
                      <Text style={[styles.detailVal, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                        {(selectedHlb.validation_details.quality_metrics.estimated_walking_distance_km || 0).toFixed(2)} km
                      </Text>
                    </View>
                  </View>
                </View>
              )}

              {/* Better Validation Warnings with Reasons & Suggested Actions */}
              {selectedHlb.validation_status === 'WARNING' && (
                <View style={styles.warningDetailCard} testID="hlb-warning-detail-card">
                  <Text style={styles.warningHeaderTitle}>⚠ Validation Warning Details</Text>
                  <View style={styles.warningReasonList}>
                    <Text style={styles.warningReasonItem}>
                      • Building count is {selectedHlb.actual_building_count < selectedHlb.target_building_count ? 'below target' : 'above target'} ({selectedHlb.actual_building_count} vs {selectedHlb.target_building_count} target).
                    </Text>
                    <Text style={styles.warningReasonItem}>
                      • Boundary geometry is valid and inside administrative area.
                    </Text>
                  </View>
                  <Text style={styles.warningActionText}>
                    💡 Suggested Action: Consider merging with an adjacent HLB or editing the boundary to balance building density.
                  </Text>
                </View>
              )}

              {/* Editing Action Buttons */}
              {!isApproved && (
                <View style={styles.actionButtonsRow}>
                  <TouchableOpacity
                    style={[styles.actionBtn, styles.editBtn]}
                    onPress={handleStartBoundaryEdit}
                    testID="edit-boundary-action-btn"
                    accessibilityLabel="Edit boundary visually on map"
                  >
                    <Text style={styles.actionBtnText}>✏️ EDIT BOUNDARY</Text>
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[styles.actionBtn, styles.splitBtn]}
                    onPress={handleOpenSplitModal}
                    testID="split-hlb-action-btn"
                    accessibilityLabel="Split HLB"
                  >
                    <Text style={styles.actionBtnText}>✂️ SPLIT HLB</Text>
                  </TouchableOpacity>

                  {candidateHlbs.length > 1 && (
                    <TouchableOpacity
                      style={[styles.actionBtn, styles.mergeBtn]}
                      onPress={handleOpenMergeModal}
                      testID="merge-hlb-action-btn"
                      accessibilityLabel="Merge HLBs"
                    >
                      <Text style={styles.actionBtnText}>🔗 MERGE HLBS</Text>
                    </TouchableOpacity>
                  )}
                </View>
              )}
            </Card>
          )}

          {/* 5. Candidate HLBs List */}
          <Card testID="candidate-hlb-list-card" style={[styles.card, { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' }]}>
            <Text style={[styles.sectionTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
              CANDIDATE HLBs ({candidateHlbs.length})
            </Text>

            {candidateHlbs.map((hlb, index) => {
              const isSelected = selectedHlb?.id === hlb.id;
              const palette = HLB_PALETTE[index % HLB_PALETTE.length];
              return (
                <TouchableOpacity
                  key={hlb.id}
                  style={[
                    styles.hlbListItem,
                    {
                      backgroundColor: isSelected
                        ? isDarkMode
                          ? '#1E293B'
                          : '#E2E8F0'
                        : isDarkMode
                        ? '#0F172A'
                        : '#F8FAFC',
                      borderColor: isSelected ? palette.stroke : isDarkMode ? '#1E293B' : '#E2E8F0',
                      borderLeftColor: palette.stroke,
                      borderLeftWidth: 4,
                    },
                  ]}
                  onPress={() => handleSelectHlb(hlb)}
                  testID={`hlb-row-${hlb.block_code}`}
                >
                  <View style={styles.hlbListHeader}>
                    <Text style={[styles.hlbCode, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                      {hlb.block_code}
                    </Text>
                    <StatusBadge status={hlb.validation_status} />
                  </View>

                  <View style={styles.hlbListMetrics}>
                    <Text style={[styles.hlbSubText, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                      Buildings: <Text style={{ fontWeight: '700', color: isDarkMode ? '#38BDF8' : '#0284C7' }}>{hlb.actual_building_count}</Text>
                    </Text>
                    <Text style={[styles.hlbSubText, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                      Target: {hlb.target_building_count}
                    </Text>
                    <Text style={[styles.hlbSubText, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                      Quality: {Math.round((hlb.quality_score || 1.0) * 100)}%
                    </Text>
                  </View>
                </TouchableOpacity>
              );
            })}
          </Card>

          {/* 6. Layout Validation Checklist Section */}
          <Card testID="layout-validation-card" style={[styles.card, { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' }]}>
            <View style={styles.valHeaderRow}>
              <Text style={[styles.sectionTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                LAYOUT VALIDATION
              </Text>
              <StatusBadge
                status={(validationData?.can_approve ?? validationData?.is_valid) ? 'VALID' : 'INVALID'}
                testID="layout-validation-status-badge"
              />
            </View>

            {validationData?.checklist && validationData.checklist.length > 0 ? (
              validationData.checklist.map((item) => (
                <View key={item.id} style={styles.checklistItem} testID={`checklist-item-${item.id}`}>
                  <Text style={[styles.checkIcon, { color: item.passed ? '#10B981' : '#EF4444' }]}>
                    {item.passed ? '✓' : '✗'}
                  </Text>
                  <View style={styles.checkTextCol}>
                    <Text style={[styles.checkTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                      {item.title}
                    </Text>
                    <Text style={[styles.checkDetail, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                      {item.detail}
                    </Text>
                  </View>
                </View>
              ))
            ) : (
              <View style={styles.checklistItem}>
                <Text style={[styles.checkIcon, { color: '#10B981' }]}>✓</Text>
                <View style={styles.checkTextCol}>
                  <Text style={[styles.checkTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                    Invariants Satisfied
                  </Text>
                  <Text style={[styles.checkDetail, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                    {totalAssigned} / {totalBuildings} buildings assigned
                  </Text>
                </View>
              </View>
            )}

            <View style={styles.approvalStatusBanner}>
              <Text style={[styles.approvalStatusLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                STATUS:
              </Text>
              <Text
                style={[
                  styles.approvalStatusText,
                  { color: (validationData?.can_approve ?? validationData?.is_valid) || isApproved ? '#10B981' : '#EF4444' },
                ]}
                testID="approval-readiness-text"
              >
                {isApproved
                  ? 'APPROVED LAYOUT (LOCKED)'
                  : (validationData?.can_approve ?? validationData?.is_valid)
                  ? 'READY FOR APPROVAL'
                  : 'NOT READY FOR APPROVAL'}
              </Text>
            </View>

            {validationData?.errors && validationData.errors.length > 0 && (
              <View style={styles.errorsContainer}>
                {validationData.errors.map((err, idx) => (
                  <Text key={idx} style={styles.errorTextItem}>
                    • {err}
                  </Text>
                ))}
              </View>
            )}
          </Card>

          {/* 7. Approve Layout Action Button */}
          {!isApproved && (
            <View style={styles.approvalActionContainer}>
              <PrimaryButton
                title={actionLoading ? actionStep : 'APPROVE LAYOUT'}
                onPress={handleApproveLayout}
                disabled={actionLoading || (validationData ? !(validationData.can_approve ?? validationData.is_valid) : false)}
                testID="approve-layout-action-btn"
              />
            </View>
          )}

          {isApproved && (
            <View style={styles.approvedBanner} testID="layout-approved-banner">
              <Text style={styles.approvedBannerText}>
                ✓ Layout Approved & Stable. HLB partitions are finalized for supervisor and enumerator assignment.
              </Text>
              <View style={{ marginTop: 12 }}>
                <PrimaryButton
                  title={t('assign_supervisor') || 'ASSIGN SUPERVISOR'}
                  onPress={() => setShowSupervisorModal(true)}
                  testID="approved-assign-supervisor-btn"
                />
              </View>
            </View>
          )}
        </ScrollView>
      )}

      {/* ====================================================
          PART B: SPLIT MODAL (Auto, Target-Based, Draw Line)
      ==================================================== */}
      <Modal visible={showSplitModal} transparent animationType="slide" onRequestClose={() => setShowSplitModal(false)}>
        <View style={styles.modalOverlay} testID="split-hlb-modal">
          <View style={[styles.modalContent, { backgroundColor: isDarkMode ? '#1E293B' : '#FFFFFF' }]}>
            {/* Modal Header */}
            <View style={styles.modalHeaderRow}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.modalTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                  Split {selectedHlb?.block_code}
                </Text>
                <Text style={[styles.modalSubHeader, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                  Current: {selectedHlb?.actual_building_count} buildings • Target: {selectedHlb?.target_building_count || 150} / HLB
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => setShowSplitModal(false)}
                style={styles.modalCloseBtn}
                testID="split-modal-close-btn"
                accessibilityLabel="Close split modal"
              >
                <Text style={styles.modalCloseBtnText}>✕</Text>
              </TouchableOpacity>
            </View>

            {/* Scrollable Modal Body */}
            <ScrollView
              style={styles.modalScrollBody}
              contentContainerStyle={styles.modalScrollContent}
              showsVerticalScrollIndicator={true}
              nestedScrollEnabled={true}
              keyboardShouldPersistTaps="handled"
              testID="split-modal-scroll-body"
            >
              {/* Split Method Selector */}
              <Text style={[styles.modalSectionHeading, { color: isDarkMode ? '#CBD5E1' : '#334155' }]}>
                Choose Split Method:
              </Text>
              <View style={styles.splitMethodsContainer}>
                <TouchableOpacity
                  style={[styles.splitMethodOption, splitMethod === 'AUTO_BALANCED' && styles.splitMethodOptionActive]}
                  onPress={() => {
                    setSplitMethod('AUTO_BALANCED');
                    fetchSplitPreview('AUTO_BALANCED');
                  }}
                  testID="split-method-auto"
                >
                  <Text style={[styles.splitMethodRadio, splitMethod === 'AUTO_BALANCED' && styles.splitMethodRadioActive]}>
                    {splitMethod === 'AUTO_BALANCED' ? '●' : '○'}
                  </Text>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.splitMethodTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                      Auto Balanced Split
                    </Text>
                    <Text style={styles.splitMethodDesc}>Divides into two spatially coherent 50/50 halves.</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.splitMethodOption, splitMethod === 'TARGET_BASED' && styles.splitMethodOptionActive]}
                  onPress={() => {
                    setSplitMethod('TARGET_BASED');
                    const total = selectedHlb?.actual_building_count || 10;
                    const half = Math.max(1, Math.round(total / 2));
                    setSideACountStr(String(half));
                    setSideBCountStr(String(total - half));
                    fetchSplitPreview('TARGET_BASED', half);
                  }}
                  testID="split-method-target"
                >
                  <Text style={[styles.splitMethodRadio, splitMethod === 'TARGET_BASED' && styles.splitMethodRadioActive]}>
                    {splitMethod === 'TARGET_BASED' ? '●' : '○'}
                  </Text>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.splitMethodTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                      Target-Based Split
                    </Text>
                    <Text style={styles.splitMethodDesc}>Specify desired building counts for both Side A and Side B.</Text>
                  </View>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.splitMethodOption, splitMethod === 'DRAW_SPLIT_LINE' && styles.splitMethodOptionActive]}
                  onPress={() => {
                    setSplitMethod('DRAW_SPLIT_LINE');
                    if (splitLineCoords.length >= 2) {
                      fetchSplitPreview('DRAW_SPLIT_LINE', undefined, splitLineCoords);
                    } else {
                      handleApplyHorizontalCutPreset();
                    }
                  }}
                  testID="split-method-draw"
                >
                  <Text style={[styles.splitMethodRadio, splitMethod === 'DRAW_SPLIT_LINE' && styles.splitMethodRadioActive]}>
                    {splitMethod === 'DRAW_SPLIT_LINE' ? '●' : '○'}
                  </Text>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.splitMethodTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                      Draw Split Line
                    </Text>
                    <Text style={styles.splitMethodDesc}>Draw a custom cut line across the block on the interactive map.</Text>
                  </View>
                </TouchableOpacity>
              </View>

              {/* Target-Based Count Inputs (Both Side A and Side B) */}
              {splitMethod === 'TARGET_BASED' && (
                <View style={styles.targetInputContainer} testID="target-based-inputs">
                  <View style={styles.targetTotalRow}>
                    <Text style={[styles.targetTotalLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                      Total in Block: <Text style={{ color: isDarkMode ? '#F1F5F9' : '#0F172A', fontWeight: '800' }}>{selectedHlb?.actual_building_count || 0} buildings</Text>
                    </Text>
                  </View>

                  <View style={styles.targetDualRow}>
                    {/* Side A Field */}
                    <View style={styles.targetDualCol}>
                      <Text style={[styles.inputLabel, { color: isDarkMode ? '#38BDF8' : '#0284C7' }]}>
                        Side A ({selectedHlb?.block_code}A):
                      </Text>
                      <TextInput
                        style={[
                          styles.numInput,
                          {
                            backgroundColor: isDarkMode ? '#0F172A' : '#F8FAFC',
                            color: isDarkMode ? '#F1F5F9' : '#0F172A',
                            borderColor: isDarkMode ? '#38BDF8' : '#0284C7',
                          },
                        ]}
                        keyboardType="numeric"
                        value={sideACountStr}
                        onChangeText={handleSideAChange}
                        placeholder="e.g. 21"
                        placeholderTextColor={isDarkMode ? '#64748B' : '#94A3B8'}
                        testID="split-target-side-a-input"
                      />
                      <Text style={styles.targetPercentageText}>
                        {Math.round(((parseInt(sideACountStr, 10) || 0) / (selectedHlb?.actual_building_count || 1)) * 100)}% of block
                      </Text>
                    </View>

                    {/* Side B Field */}
                    <View style={styles.targetDualCol}>
                      <Text style={[styles.inputLabel, { color: isDarkMode ? '#10B981' : '#059669' }]}>
                        Side B ({selectedHlb?.block_code}B):
                      </Text>
                      <TextInput
                        style={[
                          styles.numInput,
                          {
                            backgroundColor: isDarkMode ? '#0F172A' : '#F8FAFC',
                            color: isDarkMode ? '#F1F5F9' : '#0F172A',
                            borderColor: isDarkMode ? '#10B981' : '#059669',
                          },
                        ]}
                        keyboardType="numeric"
                        value={sideBCountStr}
                        onChangeText={handleSideBChange}
                        placeholder="e.g. 21"
                        placeholderTextColor={isDarkMode ? '#64748B' : '#94A3B8'}
                        testID="split-target-side-b-input"
                      />
                      <Text style={styles.targetPercentageText}>
                        {Math.round(((parseInt(sideBCountStr, 10) || 0) / (selectedHlb?.actual_building_count || 1)) * 100)}% of block
                      </Text>
                    </View>
                  </View>
                </View>
              )}

              {/* Draw Split Line Interactive Map & Controls */}
              {splitMethod === 'DRAW_SPLIT_LINE' && (
                <View style={styles.splitMapSection} testID="split-drawing-map-section">
                  <View style={styles.splitMapInstructionsRow}>
                    <Text style={styles.splitMapInstructionsText}>
                      {splitLineCoords.length === 0
                        ? '📍 Tap on map to place point 1 of cut line.'
                        : splitLineCoords.length === 1
                        ? '📍 Tap 2nd point across the block to cut.'
                        : `✓ Cut line drawn (${splitLineCoords.length} points)`}
                    </Text>
                    <View style={styles.splitMapBtnGroup}>
                      {splitLineCoords.length > 0 && (
                        <TouchableOpacity
                          style={styles.splitMapActionBtn}
                          onPress={handleUndoSplitLinePoint}
                          testID="undo-split-point-btn"
                        >
                          <Text style={styles.splitMapActionBtnText}>↶ Undo</Text>
                        </TouchableOpacity>
                      )}
                      {splitLineCoords.length > 0 && (
                        <TouchableOpacity
                          style={[styles.splitMapActionBtn, styles.splitMapActionBtnDanger]}
                          onPress={handleClearSplitLine}
                          testID="clear-split-line-btn"
                        >
                          <Text style={styles.splitMapActionBtnText}>↺ Clear</Text>
                        </TouchableOpacity>
                      )}
                    </View>
                  </View>

                  {/* Interactive Drawing Map */}
                  <View style={styles.splitModalMapContainer} testID="split-interactive-map">
                    <HlbSpatialMap
                      testID="split-drawing-spatial-map"
                      mapType="satellite"
                      showBoundary={false}
                      candidateHlbs={selectedHlb ? [selectedHlb] : []}
                      selectedHlbId={selectedHlb?.id}
                      fitCoordinates={selectedHlb ? parseGeoJSONToRings(selectedHlb.boundary).flat() : []}
                      fullscreenEnabled={false}
                      isDrawingSplitLine={true}
                      splitLineCoords={splitLineCoords}
                      onSplitLineChange={handleSplitLineChange}
                      splitPreview={splitPreview}
                    />
                  </View>

                  {/* Quick Cut Presets */}
                  <View style={styles.splitPresetsRow}>
                    <Text style={[styles.presetLabel, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>Presets:</Text>
                    <TouchableOpacity
                      style={styles.presetBtn}
                      onPress={handleApplyHorizontalCutPreset}
                      testID="preset-horizontal-cut"
                    >
                      <Text style={styles.presetBtnText}>↔ Horizontal Cut</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.presetBtn}
                      onPress={handleApplyVerticalCutPreset}
                      testID="preset-vertical-cut"
                    >
                      <Text style={styles.presetBtnText}>↕ Vertical Cut</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.presetBtn}
                      onPress={handleApplyDiagonalCutPreset}
                      testID="preset-diagonal-cut"
                    >
                      <Text style={styles.presetBtnText}>⤢ Diagonal Cut</Text>
                    </TouchableOpacity>
                    <TouchableOpacity
                      style={styles.presetBtn}
                      onPress={handleApplyUnevenCutPreset}
                      testID="preset-uneven-cut"
                    >
                      <Text style={styles.presetBtnText}>⚖ 70/30 Uneven</Text>
                    </TouchableOpacity>
                  </View>
                </View>
              )}

              {/* Split Live Preview Card */}
              <View style={styles.previewContainer} testID="split-preview-card">
                <Text style={styles.previewHeading}>Split Preview</Text>
                {splitPreviewLoading ? (
                  <ActivityIndicator size="small" color="#38BDF8" style={{ marginVertical: 12 }} />
                ) : splitPreview ? (
                  <View>
                    <View style={styles.splitPreviewBoxesRow}>
                      <View style={styles.splitSubBox}>
                        <Text style={styles.splitCodeText}>{splitPreview.side_a_block_code}</Text>
                        <Text style={styles.splitBldText}>{splitPreview.side_a_building_count} bldgs</Text>
                      </View>
                      <Text style={{ color: '#94A3B8', fontSize: 18, fontWeight: 'bold' }}>+</Text>
                      <View style={styles.splitSubBox}>
                        <Text style={styles.splitCodeText}>{splitPreview.side_b_block_code}</Text>
                        <Text style={styles.splitBldText}>{splitPreview.side_b_building_count} bldgs</Text>
                      </View>
                    </View>

                    <Text style={styles.previewTotalText}>
                      Total: {splitPreview.side_a_building_count} + {splitPreview.side_b_building_count} = {splitPreview.total_original_buildings} bldgs
                    </Text>

                    {splitPreview.is_valid ? (
                      <View style={styles.previewChecklist}>
                        <Text style={styles.previewValidItem}>✓ Both boundaries geographically valid</Text>
                        <Text style={styles.previewValidItem}>✓ No duplicate building assignments</Text>
                        <Text style={styles.previewValidItem}>✓ 0 unassigned buildings</Text>
                        <Text style={styles.previewValidItem}>✓ Both inside administrative area</Text>
                      </View>
                    ) : (
                      <View style={styles.previewErrorContainer}>
                        <Text style={styles.previewErrorTitle}>⚠ Split cannot be applied:</Text>
                        {splitPreview.validation_errors?.map((err, i) => (
                          <Text key={i} style={styles.previewErrorItem}>• {err}</Text>
                        ))}
                      </View>
                    )}
                  </View>
                ) : null}
              </View>
            </ScrollView>

            {/* Modal Bottom Actions */}
            <View style={styles.modalBtnRow}>
              <SecondaryButton title="Cancel" onPress={() => setShowSplitModal(false)} />
              <PrimaryButton
                title="Confirm Split"
                onPress={handleConfirmSplit}
                disabled={!splitPreview?.is_valid || splitPreviewLoading}
                testID="confirm-split-btn"
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* ====================================================
          PART C: MERGE MODAL (Select ANY 2 HLBs + Adjacency)
      ==================================================== */}
      <Modal visible={showMergeModal} transparent animationType="slide" onRequestClose={() => setShowMergeModal(false)}>
        <View style={styles.modalOverlay} testID="merge-hlb-modal">
          <View style={[styles.modalContent, { backgroundColor: isDarkMode ? '#1E293B' : '#FFFFFF' }]}>
            {/* Modal Header */}
            <View style={styles.modalHeaderRow}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.modalTitle, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                  Merge HLBs
                </Text>
                <Text style={[styles.modalSubHeader, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                  Select exactly TWO candidate HLBs to merge into a single consolidated partition.
                </Text>
              </View>
              <TouchableOpacity
                onPress={() => setShowMergeModal(false)}
                style={styles.modalCloseBtn}
                testID="merge-modal-close-btn"
                accessibilityLabel="Close merge modal"
              >
                <Text style={styles.modalCloseBtnText}>✕</Text>
              </TouchableOpacity>
            </View>

            {/* Scrollable Modal Body */}
            <ScrollView
              style={styles.modalScrollBody}
              contentContainerStyle={styles.modalScrollContent}
              showsVerticalScrollIndicator={true}
              nestedScrollEnabled={true}
              testID="merge-modal-scroll-body"
            >
              <View style={styles.mergeSelectionHeader}>
                <Text style={[styles.modalSectionHeading, { color: isDarkMode ? '#CBD5E1' : '#334155' }]}>
                  Selected: {selectedMergeHlbIds.length} / 2
                </Text>
              </View>

              {/* Candidate HLB Selection List */}
              <View style={styles.mergeScrollList}>
                {candidateHlbs.map((h) => {
                  const isChecked = selectedMergeHlbIds.includes(h.id);
                  return (
                    <TouchableOpacity
                      key={h.id}
                      style={[
                        styles.mergeOptionItem,
                        {
                          borderColor: isChecked ? '#38BDF8' : isDarkMode ? '#334155' : '#CBD5E1',
                          backgroundColor: isChecked
                            ? isDarkMode
                              ? '#0F172A'
                              : '#E0F2FE'
                            : isDarkMode
                            ? '#1E293B'
                            : '#F8FAFC',
                        },
                      ]}
                      onPress={() => toggleMergeSelection(h.id)}
                      testID={`merge-candidate-${h.block_code}`}
                    >
                      <Text style={[styles.mergeCheckbox, { color: isChecked ? '#38BDF8' : '#94A3B8' }]}>
                        {isChecked ? '☑' : '☐'}
                      </Text>
                      <View style={{ flex: 1, marginLeft: 8 }}>
                        <Text style={[styles.mergeHlbCode, { color: isDarkMode ? '#F1F5F9' : '#0F172A' }]}>
                          {h.block_code}
                        </Text>
                        <Text style={[styles.mergeHlbCount, { color: isDarkMode ? '#94A3B8' : '#64748B' }]}>
                          {h.actual_building_count} buildings
                        </Text>
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {/* Merge Live Preview Card */}
              {selectedMergeHlbIds.length === 2 && (
                <View style={styles.previewContainer} testID="merge-preview-card">
                  <Text style={styles.previewHeading}>Merge Preview</Text>
                  {mergePreviewLoading ? (
                    <ActivityIndicator size="small" color="#38BDF8" style={{ marginVertical: 10 }} />
                  ) : mergePreview ? (
                    <View>
                      <Text style={styles.mergePreviewCodeText}>
                        {mergePreview.merged_block_code}
                      </Text>
                      <Text style={styles.mergePreviewCountText}>
                        Combined Buildings: {mergePreview.combined_building_count}
                      </Text>

                      <View style={styles.previewChecklist}>
                        <Text style={mergePreview.is_adjacent ? styles.previewValidItem : styles.previewErrorItem}>
                          {mergePreview.is_adjacent ? '✓ Adjacent • Valid merge candidate' : '⚠ Not geographically adjacent'}
                        </Text>
                        <Text style={mergePreview.is_valid ? styles.previewValidItem : styles.previewErrorItem}>
                          {mergePreview.is_valid ? '✓ Geometry: Valid Single Polygon' : '⚠ Disconnected MultiPolygon'}
                        </Text>
                        <Text style={styles.previewValidItem}>
                          ✓ Building Assignment: {mergePreview.building_assignment_status}
                        </Text>
                      </View>

                      {!mergePreview.is_valid && (
                        <View style={styles.previewErrorContainer}>
                          {mergePreview.validation_errors?.map((err, idx) => (
                            <Text key={idx} style={styles.previewErrorItem}>• {err}</Text>
                          ))}
                        </View>
                      )}
                    </View>
                  ) : null}
                </View>
              )}
            </ScrollView>

            {/* Modal Bottom Actions */}
            <View style={styles.modalBtnRow}>
              <SecondaryButton title="Cancel" onPress={() => setShowMergeModal(false)} />
              <PrimaryButton
                title="Confirm Merge"
                onPress={handleConfirmMerge}
                disabled={selectedMergeHlbIds.length !== 2 || !mergePreview?.is_valid || mergePreviewLoading}
                testID="confirm-merge-btn"
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* Supervisor Assignment Modal */}
      <SupervisorAssignmentModal
        visible={showSupervisorModal}
        layout={layout}
        areaName={areaName}
        onClose={() => setShowSupervisorModal(false)}
        onSuccess={() => {
          loadLayoutData();
        }}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 32,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 14,
    fontWeight: '500',
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  successBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderWidth: 1,
    borderColor: '#10B981',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  successIcon: {
    color: '#10B981',
    fontSize: 18,
    fontWeight: 'bold',
    marginRight: 8,
  },
  successText: {
    flex: 1,
    color: '#10B981',
    fontSize: 13,
    fontWeight: '600',
  },
  card: {
    marginBottom: 16,
    padding: 16,
    borderRadius: 12,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  villageTitle: {
    fontSize: 20,
    fontWeight: '800',
    letterSpacing: 0.3,
  },
  villageCode: {
    fontSize: 13,
    marginTop: 4,
    fontWeight: '500',
  },
  badgeCol: {
    alignItems: 'flex-end',
  },
  versionLabel: {
    fontSize: 11,
    fontWeight: '700',
    marginTop: 4,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1,
    marginBottom: 12,
  },
  metricsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 8,
  },
  metricBox: {
    flex: 1,
    alignItems: 'center',
    backgroundColor: 'rgba(2, 132, 199, 0.05)',
    paddingVertical: 10,
    paddingHorizontal: 4,
    borderRadius: 8,
  },
  metricValue: {
    fontSize: 18,
    fontWeight: '800',
  },
  metricLabel: {
    fontSize: 10,
    marginTop: 2,
    fontWeight: '600',
    textAlign: 'center',
  },
  mapCard: {
    padding: 12,
  },
  mapHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  mapBadge: {
    fontSize: 11,
    fontWeight: '700',
  },
  mapContainer: {
    width: '100%',
    height: 300,
    borderRadius: 8,
    overflow: 'hidden',
    position: 'relative',
    backgroundColor: '#0F172A',
  },
  mapEditingToolbar: {
    backgroundColor: '#1E293B',
    padding: 8,
    borderRadius: 8,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: '#38BDF8',
  },
  editingToolbarRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 6,
    marginBottom: 8,
  },
  toolBtn: {
    flex: 1,
    backgroundColor: '#0F172A',
    borderWidth: 1,
    borderColor: '#38BDF8',
    paddingVertical: 6,
    paddingHorizontal: 6,
    borderRadius: 6,
    alignItems: 'center',
  },
  toolBtnDanger: {
    borderColor: '#EF4444',
  },
  toolBtnText: {
    color: '#F1F5F9',
    fontSize: 11,
    fontWeight: '700',
  },
  editingToolbarBottomRow: {
    flexDirection: 'row',
    gap: 8,
  },
  toolBtnSecondary: {
    backgroundColor: '#334155',
    paddingVertical: 8,
    borderRadius: 6,
    alignItems: 'center',
  },
  toolBtnSecondaryText: {
    color: '#CBD5E1',
    fontSize: 12,
    fontWeight: '700',
  },
  toolBtnPrimary: {
    backgroundColor: '#0284C7',
    paddingVertical: 8,
    borderRadius: 6,
    alignItems: 'center',
  },
  toolBtnPrimaryText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  selectedCard: {
    borderWidth: 1.5,
    borderColor: '#38BDF8',
  },
  selectedHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  selectedTitle: {
    fontSize: 18,
    fontWeight: '800',
  },
  selectedSub: {
    fontSize: 12,
    marginTop: 2,
  },
  detailGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 12,
  },
  detailItem: {
    alignItems: 'center',
  },
  detailLabel: {
    fontSize: 11,
    fontWeight: '500',
  },
  detailVal: {
    fontSize: 15,
    fontWeight: '800',
    marginTop: 2,
  },
  warningDetailCard: {
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    borderWidth: 1,
    borderColor: '#F59E0B',
    borderRadius: 8,
    padding: 10,
    marginBottom: 12,
  },
  warningHeaderTitle: {
    color: '#F59E0B',
    fontSize: 12,
    fontWeight: '800',
    marginBottom: 4,
  },
  warningReasonList: {
    marginBottom: 6,
  },
  warningReasonItem: {
    color: '#CBD5E1',
    fontSize: 11,
    lineHeight: 16,
  },
  warningActionText: {
    color: '#FEF08A',
    fontSize: 11,
    fontWeight: '600',
    lineHeight: 16,
  },
  actionButtonsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  actionBtn: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
  },
  editBtn: {
    backgroundColor: '#0284C7',
  },
  splitBtn: {
    backgroundColor: '#8B5CF6',
  },
  mergeBtn: {
    backgroundColor: '#F59E0B',
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '800',
  },
  hlbListItem: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 8,
  },
  hlbListHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  hlbCode: {
    fontSize: 15,
    fontWeight: '700',
  },
  hlbListMetrics: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
  },
  hlbSubText: {
    fontSize: 12,
    fontWeight: '500',
  },
  valHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  checklistItem: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    paddingVertical: 6,
    borderBottomWidth: 0.5,
    borderBottomColor: 'rgba(148, 163, 184, 0.2)',
  },
  checkIcon: {
    fontSize: 15,
    fontWeight: 'bold',
    marginRight: 8,
    marginTop: 1,
  },
  checkTextCol: {
    flex: 1,
  },
  checkTitle: {
    fontSize: 13,
    fontWeight: '700',
  },
  checkDetail: {
    fontSize: 11,
    marginTop: 1,
  },
  approvalStatusBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: 12,
    paddingTop: 8,
  },
  approvalStatusLabel: {
    fontSize: 12,
    fontWeight: '700',
  },
  approvalStatusText: {
    fontSize: 13,
    fontWeight: '800',
  },
  errorsContainer: {
    marginTop: 8,
    padding: 8,
    backgroundColor: 'rgba(239, 68, 68, 0.1)',
    borderRadius: 6,
  },
  errorTextItem: {
    color: '#EF4444',
    fontSize: 12,
    lineHeight: 16,
  },
  approvalActionContainer: {
    marginTop: 8,
    marginBottom: 24,
  },
  approvedBanner: {
    backgroundColor: 'rgba(16, 185, 129, 0.15)',
    borderWidth: 1,
    borderColor: '#10B981',
    borderRadius: 8,
    padding: 14,
    marginBottom: 24,
  },
  approvedBannerText: {
    color: '#10B981',
    fontSize: 13,
    fontWeight: '700',
    lineHeight: 18,
    textAlign: 'center',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.75)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalContent: {
    width: '100%',
    maxWidth: 720,
    maxHeight: '92%',
    borderRadius: 14,
    padding: 20,
    display: 'flex',
    flexDirection: 'column',
    ...Platform.select({
      web: {
        boxShadow: '0px 10px 30px rgba(0, 0, 0, 0.5)',
      },
      default: {
        elevation: 10,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 6 },
        shadowOpacity: 0.5,
        shadowRadius: 10,
      },
    }),
  },
  modalHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  modalCloseBtn: {
    padding: 6,
    marginLeft: 8,
  },
  modalCloseBtnText: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#94A3B8',
  },
  modalScrollBody: {
    flexGrow: 1,
    flexShrink: 1,
    marginVertical: 4,
  },
  modalScrollContent: {
    paddingBottom: 8,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 4,
  },
  modalSubHeader: {
    fontSize: 12,
    marginBottom: 8,
  },
  modalSectionHeading: {
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 8,
  },
  splitMethodsContainer: {
    gap: 8,
    marginBottom: 12,
  },
  splitMethodOption: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#334155',
    backgroundColor: 'rgba(15, 23, 42, 0.4)',
  },
  splitMethodOptionActive: {
    borderColor: '#38BDF8',
    backgroundColor: 'rgba(56, 189, 248, 0.1)',
  },
  splitMethodRadio: {
    fontSize: 16,
    color: '#94A3B8',
    marginRight: 8,
  },
  splitMethodRadioActive: {
    color: '#38BDF8',
    fontWeight: 'bold',
  },
  splitMethodTitle: {
    fontSize: 13,
    fontWeight: '700',
  },
  splitMethodDesc: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 2,
  },
  targetInputContainer: {
    marginBottom: 12,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  numInput: {
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 15,
    fontWeight: '700',
  },
  targetTotalRow: {
    marginBottom: 8,
  },
  targetTotalLabel: {
    fontSize: 12,
  },
  targetDualRow: {
    flexDirection: 'row',
    gap: 12,
  },
  targetDualCol: {
    flex: 1,
  },
  targetPercentageText: {
    fontSize: 11,
    color: '#94A3B8',
    marginTop: 4,
    fontWeight: '600',
  },
  splitMapSection: {
    marginBottom: 14,
  },
  splitMapInstructionsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  splitMapInstructionsText: {
    fontSize: 12,
    color: '#38BDF8',
    fontWeight: '600',
    flex: 1,
  },
  splitMapBtnGroup: {
    flexDirection: 'row',
    gap: 6,
  },
  splitMapActionBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: '#0284C7',
  },
  splitMapActionBtnDanger: {
    backgroundColor: '#EF4444',
  },
  splitMapActionBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  splitModalMapContainer: {
    height: 240,
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: '#38BDF8',
    marginBottom: 8,
  },
  splitPresetsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    flexWrap: 'wrap',
  },
  presetLabel: {
    fontSize: 11,
    fontWeight: '600',
  },
  presetBtn: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 6,
    backgroundColor: 'rgba(56, 189, 248, 0.15)',
    borderWidth: 1,
    borderColor: '#38BDF8',
  },
  presetBtnText: {
    color: '#38BDF8',
    fontSize: 11,
    fontWeight: '700',
  },
  previewContainer: {
    backgroundColor: 'rgba(15, 23, 42, 0.6)',
    borderWidth: 1,
    borderColor: '#334155',
    borderRadius: 8,
    padding: 12,
    marginBottom: 16,
  },
  previewHeading: {
    color: '#38BDF8',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  splitPreviewBoxesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-around',
    marginBottom: 8,
  },
  splitSubBox: {
    alignItems: 'center',
    backgroundColor: '#0F172A',
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#38BDF8',
  },
  splitCodeText: {
    color: '#38BDF8',
    fontSize: 14,
    fontWeight: '800',
  },
  splitBldText: {
    color: '#CBD5E1',
    fontSize: 12,
    fontWeight: '600',
    marginTop: 2,
  },
  previewTotalText: {
    color: '#F1F5F9',
    fontSize: 12,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 8,
  },
  previewChecklist: {
    gap: 4,
    marginTop: 4,
  },
  previewValidItem: {
    color: '#10B981',
    fontSize: 11,
    fontWeight: '600',
  },
  previewErrorContainer: {
    marginTop: 6,
  },
  previewErrorTitle: {
    color: '#EF4444',
    fontSize: 12,
    fontWeight: '700',
    marginBottom: 2,
  },
  previewErrorItem: {
    color: '#EF4444',
    fontSize: 11,
    lineHeight: 15,
  },
  mergeSelectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  mergeScrollList: {
    maxHeight: 180,
    marginBottom: 12,
  },
  mergeOptionItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 6,
  },
  mergeCheckbox: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  mergeHlbCode: {
    fontSize: 14,
    fontWeight: '700',
  },
  mergeHlbCount: {
    fontSize: 11,
    marginTop: 1,
  },
  mergePreviewCodeText: {
    color: '#38BDF8',
    fontSize: 15,
    fontWeight: '800',
    textAlign: 'center',
    marginBottom: 2,
  },
  mergePreviewCountText: {
    color: '#F1F5F9',
    fontSize: 12,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 6,
  },
  modalBtnRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(148, 163, 184, 0.2)',
  },
  provisionalBanner: {
    backgroundColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: '#F59E0B',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 10,
  },
  provisionalBannerText: {
    color: '#F59E0B',
    fontSize: 12,
    fontWeight: '700',
    textAlign: 'center',
  },
  qualityMetricsSection: {
    marginTop: 12,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(148, 163, 184, 0.15)',
  },
  sectionSubtitle: {
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 8,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
});
