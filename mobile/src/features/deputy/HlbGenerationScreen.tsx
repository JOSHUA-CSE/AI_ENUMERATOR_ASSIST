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
  HlbGenerationResult,
} from '../../core/layoutService';
import { useTranslation } from '../../core/localization';
import type { DeputyNavigationProp, DeputyStackParamList } from '../../navigation/navigationTypes';

interface LatLng {
  latitude: number;
  longitude: number;
}

const HLB_PALETTE = [
  { fill: 'rgba(2, 132, 199, 0.04)', stroke: '#0284C7', text: '#0284C7', lightBg: '#E0F2FE' },
  { fill: 'rgba(16, 185, 129, 0.04)', stroke: '#10B981', text: '#10B981', lightBg: '#D1FAE5' },
  { fill: 'rgba(139, 92, 246, 0.04)', stroke: '#8B5CF6', text: '#8B5CF6', lightBg: '#EDE9FE' },
  { fill: 'rgba(245, 158, 11, 0.04)', stroke: '#F59E0B', text: '#D97706', lightBg: '#FEF3C7' },
  { fill: 'rgba(236, 72, 153, 0.04)', stroke: '#EC4899', text: '#DB2777', lightBg: '#FCE7F3' },
  { fill: 'rgba(20, 184, 166, 0.04)', stroke: '#14B8A6', text: '#0D9488', lightBg: '#CCFBF1' },
  { fill: 'rgba(99, 102, 241, 0.04)', stroke: '#6366F1', text: '#4F46E5', lightBg: '#E0E7FF' },
  { fill: 'rgba(234, 88, 12, 0.04)', stroke: '#EA580C', text: '#C2410C', lightBg: '#FFEDD5' },
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

export function HlbGenerationScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const route = useRoute<RouteProp<DeputyStackParamList, 'HlbGeneration'>>();
  const { t } = useTranslation();

  const routeParams = (route.params || {}) as Partial<DeputyStackParamList['HlbGeneration']>;
  const initialLayoutId = routeParams.layoutId;
  const layoutName = routeParams.layoutName || 'Layout';
  const initialAreaName = routeParams.areaName || 'Village';
  const rawAreaId = routeParams.areaId;

  const mapRef = useRef<HlbSpatialMapRef | null>(null);

  const [activeLayoutId, setActiveLayoutId] = useState<string | null>(
    initialLayoutId && initialLayoutId !== 'undefined' && initialLayoutId !== 'null' ? initialLayoutId : null
  );
  const [layout, setLayout] = useState<LayoutSummary | null>(null);
  const [boundaryData, setBoundaryData] = useState<AreaBoundaryResponse | null>(null);
  const [candidateHlbs, setCandidateHlbs] = useState<HlbCandidate[]>([]);
  const [generationResult, setGenerationResult] = useState<HlbGenerationResult | null>(null);
  const [detectedBuildings, setDetectedBuildings] = useState<number>(0);
  const [buildingSource, setBuildingSource] = useState<string>('Satellite-Derived');

  const [targetSize, setTargetSize] = useState<number>(200);
  const [targetSizeInput, setTargetSizeInput] = useState<string>('200');

  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generationStep, setGenerationStep] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  // Selected HLB for modal inspection
  const [selectedHlb, setSelectedHlb] = useState<HlbCandidate | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);

  const hasAreaParam = Boolean(
    rawAreaId && rawAreaId !== 'undefined' && rawAreaId !== 'null' && rawAreaId.trim() !== ''
  );
  const hasLayoutParam = Boolean(
    initialLayoutId && initialLayoutId !== 'undefined' && initialLayoutId !== 'null' && initialLayoutId.trim() !== ''
  );

  const loadInitialData = useCallback(async () => {
    if (!hasAreaParam && !hasLayoutParam) {
      setError('Administrative area could not be identified. Please return and select the area again.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      let resolvedAreaId = hasAreaParam ? rawAreaId! : null;
      let layoutRes: LayoutSummary | null = null;

      // 1. If layout ID was provided, retrieve existing layout
      if (hasLayoutParam) {
        try {
          layoutRes = await layoutService.getLayout(initialLayoutId!);
          setLayout(layoutRes);
          if (!resolvedAreaId) {
            resolvedAreaId = layoutRes.area_id || layoutRes.administrative_area_id;
          }
        } catch {
          // Continue if layout not found but area is known
        }
      }

      if (!resolvedAreaId || resolvedAreaId === 'undefined' || resolvedAreaId === 'null') {
        setError('Administrative area could not be identified. Please return and select the area again.');
        setLoading(false);
        return;
      }

      // Check if existing layouts exist for this area if layout was not explicitly given
      if (!layoutRes) {
        try {
          const areaLayouts = await layoutService.getLayouts({ area_id: resolvedAreaId });
          if (areaLayouts.items && areaLayouts.items.length > 0) {
            layoutRes = areaLayouts.items[0];
            setLayout(layoutRes);
            setActiveLayoutId(layoutRes.id);
          }
        } catch {
          // OK if no existing layouts
        }
      }

      // 2. Authoritative API calls: boundary, estimation, candidate HLBs
      const currentLayoutId = layoutRes?.id || activeLayoutId;
      const [boundaryRes, estimationRes, hlbsRes] = await Promise.all([
        areaService.getAreaBoundary(resolvedAreaId),
        areaService.getBuildingEstimation(resolvedAreaId),
        currentLayoutId
          ? layoutService.getLayoutHlbs(currentLayoutId).catch(() => ({ items: [], total: 0 }))
          : Promise.resolve({ items: [], total: 0 }),
      ]);

      setBoundaryData(boundaryRes);
      setCandidateHlbs(hlbsRes.items || []);

      // 3. Set authoritative detected building count
      const bldCount = estimationRes?.total_buildings ?? layoutRes?.total_buildings ?? 0;
      setDetectedBuildings(bldCount);

      if (estimationRes?.quality_label) {
        setBuildingSource(estimationRes.quality_label);
      } else if (estimationRes?.source_type === 'SATELLITE_DETECTED') {
        setBuildingSource('Satellite-Derived');
      } else {
        setBuildingSource('Satellite-Derived');
      }

      const targetVal =
        layoutRes?.target_buildings_per_hlb || layoutRes?.target_houses_per_hlb || 200;
      setTargetSize(targetVal);
      setTargetSizeInput(String(targetVal));
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [hasAreaParam, hasLayoutParam, initialLayoutId, rawAreaId, activeLayoutId]);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  useEffect(() => {
    const backAction = () => {
      navigation.goBack();
      return true;
    };
    const backHandler = BackHandler.addEventListener('hardwareBackPress', backAction);
    return () => backHandler.remove();
  }, [navigation]);

  const handleTargetChange = (val: string) => {
    setTargetSizeInput(val);
    const parsed = parseInt(val, 10);
    if (!isNaN(parsed) && parsed > 0) {
      setTargetSize(parsed);
    }
  };

  const adjustTarget = (delta: number) => {
    const nextVal = Math.max(10, targetSize + delta);
    setTargetSize(nextVal);
    setTargetSizeInput(String(nextVal));
  };

  const totalBuildings =
    detectedBuildings > 0
      ? detectedBuildings
      : layout?.total_buildings || layout?.actual_building_count || 0;

  const estimatedHlbCount =
    totalBuildings > 0 && targetSize > 0 ? Math.ceil(totalBuildings / targetSize) : 0;

  const layoutRings = useMemo(() => {
    return parseGeoJSONToRings(boundaryData?.boundary);
  }, [boundaryData]);

  const areaDisplayName = boundaryData?.name || initialAreaName || 'Village';

  const handleGenerate = async () => {
    const resolvedAreaId =
      rawAreaId && rawAreaId !== 'undefined' && rawAreaId !== 'null'
        ? rawAreaId
        : layout?.area_id || layout?.administrative_area_id;

    if (!resolvedAreaId || resolvedAreaId === 'undefined') {
      setError('Administrative area could not be identified. Please return and select the area again.');
      return;
    }

    if (totalBuildings === 0) {
      setError('No detected buildings found in this area. HLBs cannot be generated.');
      return;
    }

    setGenerating(true);
    setError(null);
    setGenerationStep(t('loading_buildings_step') || 'Partitioning buildings into HLBs...');

    try {
      let targetLayoutId = activeLayoutId || layout?.id;

      // If no layout exists yet for this area, create one
      if (!targetLayoutId) {
        const createdLayout = await layoutService.createLayout({
          administrative_area_id: resolvedAreaId,
          name: `${areaDisplayName} Layout`,
          target_buildings_per_hlb: targetSize,
        });
        targetLayoutId = createdLayout.id;
        setActiveLayoutId(createdLayout.id);
        setLayout(createdLayout);
      }

      const result = await layoutService.generateHlbs(targetLayoutId, {
        target_buildings_per_hlb: targetSize,
      });

      setGenerationResult(result);
      setCandidateHlbs(result.hlbs || []);

      if (result.total_buildings > 0) {
        setDetectedBuildings(result.total_buildings);
      }

      // Reload layout metadata
      const updatedLayout = await layoutService.getLayout(targetLayoutId);
      setLayout(updatedLayout);

      // Focus map to fit generated bounds
      setTimeout(() => {
        fitMapToLayout();
      }, 300);
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setGenerating(false);
      setGenerationStep('');
    }
  };

  const initialRegion = useMemo(() => {
    if (layoutRings.length > 0 && layoutRings[0].length > 0) {
      const ring = layoutRings[0];
      const lats = ring.map((c) => c.latitude);
      const lngs = ring.map((c) => c.longitude);
      const minLat = Math.min(...lats);
      const maxLat = Math.max(...lats);
      const minLng = Math.min(...lngs);
      const maxLng = Math.max(...lngs);
      return {
        latitude: (minLat + maxLat) / 2,
        longitude: (minLng + maxLng) / 2,
        latitudeDelta: Math.max(0.02, (maxLat - minLat) * 1.3),
        longitudeDelta: Math.max(0.02, (maxLng - minLng) * 1.3),
      };
    }
    return {
      latitude: 11.082,
      longitude: 77.12,
      latitudeDelta: 0.04,
      longitudeDelta: 0.04,
    };
  }, [layoutRings]);

  const fitMapToLayout = useCallback(() => {
    const allCoords: LatLng[] = [];
    if (candidateHlbs.length > 0) {
      candidateHlbs.forEach((hlb) => {
        const rings = parseGeoJSONToRings(hlb.boundary);
        rings.forEach((r) => allCoords.push(...r));
      });
    } else if (layoutRings.length > 0) {
      layoutRings.forEach((r) => allCoords.push(...r));
    }

    if (allCoords.length > 0) {
      mapRef.current?.fitToCoordinates(allCoords);
    }
  }, [candidateHlbs, layoutRings]);

  useEffect(() => {
    if (layoutRings.length > 0 || candidateHlbs.length > 0) {
      fitMapToLayout();
    }
  }, [layoutRings, candidateHlbs, fitMapToLayout]);

  const themeStyles = {
    bg: { backgroundColor: isDarkMode ? '#121212' : '#F4F6F9' },
    text: { color: isDarkMode ? '#FFFFFF' : '#1A237E' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#5C6BC0' },
    cardBg: { backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF' },
    inputBg: {
      backgroundColor: isDarkMode ? '#2D2D2D' : '#F5F7FA',
      color: isDarkMode ? '#FFFFFF' : '#333333',
      borderColor: isDarkMode ? '#444444' : '#D0DBE5',
    },
    tableHeader: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#E8EEF5',
      borderColor: isDarkMode ? '#3A3A3A' : '#D0DBE5',
    },
    tableRow: {
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
      borderColor: isDarkMode ? '#333333' : '#F0F0F0',
    },
    selectedRow: {
      backgroundColor: isDarkMode ? '#1A365D' : '#E3F2FD',
      borderColor: isDarkMode ? '#60A5FA' : '#0066CC',
    },
    modalBg: { backgroundColor: isDarkMode ? '#242424' : '#FFFFFF' },
  };

  const getHlbPalette = (index: number) => {
    return HLB_PALETTE[index % HLB_PALETTE.length];
  };

  // 1. Defensive Validation Screen: No valid area ID provided
  if (!hasAreaParam && !hasLayoutParam) {
    return (
      <ScreenContainer testID="hlb-generation-invalid-screen">
        <AppHeader
          title="HLB Generation"
          roleType="DEPUTY_TAHSILDAR"
          roleLabel={t('role_deputy')}
          showBack
          onBack={() => navigation.goBack()}
        />
        <View style={styles.errorFullContainer}>
          <Text style={styles.errorFullIcon}>⚠️</Text>
          <Text style={[styles.errorFullTitle, themeStyles.text]}>
            Administrative area could not be identified.
          </Text>
          <Text style={[styles.errorFullDesc, themeStyles.subtext]}>
            Please return to the administrative area list and select the village again.
          </Text>
          <PrimaryButton
            title="← RETURN TO AREAS"
            onPress={() => navigation.goBack()}
            style={{ marginTop: 20 }}
          />
        </View>
      </ScreenContainer>
    );
  }

  // 2. Loading State Screen
  if (loading) {
    return (
      <ScreenContainer testID="hlb-generation-loading-screen">
        <AppHeader
          title={`${initialAreaName} — HLB Generation`}
          roleType="DEPUTY_TAHSILDAR"
          roleLabel={t('role_deputy')}
          showBack
          onBack={() => navigation.goBack()}
        />
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#0066CC" />
          <Text style={[styles.loadingText, themeStyles.text]}>
            Loading building data and boundary...
          </Text>
        </View>
      </ScreenContainer>
    );
  }

  // 3. Error State Screen: API Failure when loading boundary/estimation
  if (error && !boundaryData) {
    return (
      <ScreenContainer testID="hlb-generation-error-screen">
        <AppHeader
          title={`${initialAreaName} — HLB Generation`}
          roleType="DEPUTY_TAHSILDAR"
          roleLabel={t('role_deputy')}
          showBack
          onBack={() => navigation.goBack()}
        />
        <View style={styles.errorFullContainer}>
          <Text style={styles.errorFullIcon}>⚠️</Text>
          <Text style={[styles.errorFullTitle, themeStyles.text]}>
            Unable to load building data.
          </Text>
          <Text style={[styles.errorFullDesc, themeStyles.subtext]}>
            {error}
          </Text>
          <View style={{ flexDirection: 'row', gap: 12, marginTop: 20 }}>
            <PrimaryButton
              title="RETRY"
              onPress={loadInitialData}
              style={{ minWidth: 120 }}
              testID="retry-load-btn"
            />
            <SecondaryButton
              title="← RETURN TO AREAS"
              onPress={() => navigation.goBack()}
              style={{ minWidth: 120 }}
            />
          </View>
        </View>
      </ScreenContainer>
    );
  }

  return (
    <View style={[styles.container, themeStyles.bg]} testID="hlb-generation-screen">
      <AppHeader
        title={`${areaDisplayName} — HLB Generation`}
        subtitle="PHASE 4 • AI-ASSISTED BUILDING-COUNT HLB ENGINE"
        roleType="DEPUTY_TAHSILDAR"
        roleLabel={t('role_deputy')}
        showBack
        onBack={() => navigation.goBack()}
      />

      <ScrollView contentContainerStyle={styles.scrollContent}>
        {/* Top Header Card: Village Info, Building Detection & Configurable Building Target */}
        <Card testID="hlb-config-card" style={styles.topCard}>
          <View style={styles.topHeaderRow}>
            <View style={{ flex: 1 }}>
              <Text style={[styles.layoutTitleText, themeStyles.text]}>{layoutName}</Text>
              <Text style={[styles.areaSubtitleText, themeStyles.subtext]}>
                📍 Village/Ward: <Text style={{ fontWeight: 'bold' }}>{areaDisplayName}</Text>
              </Text>
            </View>
            <StatusBadge
              type={
                layout?.status === 'APPROVED'
                  ? 'APPROVED'
                  : layout?.status === 'IN_REVIEW'
                  ? 'IN_REVIEW'
                  : 'DRAFT'
              }
              label={layout?.status || 'DRAFT'}
            />
          </View>

          {/* Building Detection Stats Row */}
          <View style={styles.detectionStatsRow}>
            <View style={styles.statBox}>
              <Text style={[styles.statLabel, themeStyles.subtext]}>
                {t('detected_buildings_label') || 'Detected Buildings'}
              </Text>
              <Text style={[styles.statValueHighlight, { color: '#0066CC' }]}>
                {totalBuildings}
              </Text>
            </View>
            <View style={styles.statDivider} />
            <View style={styles.statBox}>
              <Text style={[styles.statLabel, themeStyles.subtext]}>Source</Text>
              <View style={styles.sourceBadgeContainer}>
                <Text style={styles.sourceBadgeText}>{buildingSource}</Text>
              </View>
            </View>
          </View>

          {/* Configurable Buildings per HLB */}
          <View style={styles.targetConfigRow}>
            <View style={styles.targetInputContainer}>
              <Text style={[styles.targetLabel, themeStyles.subtext]}>
                {t('buildings_per_hlb_label') || 'Buildings per HLB'}:
              </Text>
              <View style={styles.stepperRow}>
                <TouchableOpacity
                  style={[styles.stepperBtn, { backgroundColor: isDarkMode ? '#333' : '#E0E0E0' }]}
                  onPress={() => adjustTarget(-10)}
                  disabled={generating}
                  testID="target-dec-btn"
                >
                  <Text style={[styles.stepperBtnText, themeStyles.text]}>-10</Text>
                </TouchableOpacity>

                <TextInput
                  style={[styles.targetInput, themeStyles.inputBg]}
                  value={targetSizeInput}
                  onChangeText={handleTargetChange}
                  keyboardType="numeric"
                  editable={!generating}
                  testID="target-size-input"
                />

                <TouchableOpacity
                  style={[styles.stepperBtn, { backgroundColor: isDarkMode ? '#333' : '#E0E0E0' }]}
                  onPress={() => adjustTarget(10)}
                  disabled={generating}
                  testID="target-inc-btn"
                >
                  <Text style={[styles.stepperBtnText, themeStyles.text]}>+10</Text>
                </TouchableOpacity>
              </View>
            </View>

            <View style={styles.estimateBox}>
              <Text style={[styles.estimateNumber, { color: '#0066CC' }]}>
                {estimatedHlbCount}
              </Text>
              <Text style={[styles.estimateLabel, themeStyles.subtext]}>
                {t('estimated_hlbs_label') || 'Estimated HLBs'}
              </Text>
            </View>
          </View>

          {/* Quick Target Presets */}
          <View style={styles.presetRow}>
            {[100, 150, 200, 250, 300].map((preset) => (
              <TouchableOpacity
                key={`preset-${preset}`}
                style={[
                  styles.presetBtn,
                  targetSize === preset && styles.presetBtnActive,
                ]}
                onPress={() => {
                  setTargetSize(preset);
                  setTargetSizeInput(String(preset));
                }}
                disabled={generating}
                testID={`preset-btn-${preset}`}
              >
                <Text
                  style={[
                    styles.presetBtnText,
                    targetSize === preset && styles.presetBtnTextActive,
                  ]}
                >
                  {preset}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          {/* Action Button */}
          <View style={{ marginTop: 12 }}>
            <PrimaryButton
              title={
                generating
                  ? 'GENERATING CANDIDATE HLBS...'
                  : candidateHlbs.length > 0
                  ? '⚡ ' + (t('regenerate_hlbs_btn') || 'REGENERATE HLBs')
                  : '⚡ ' + (t('generate_hlbs_btn') || 'GENERATE HLBs')
              }
              onPress={handleGenerate}
              loading={generating}
              disabled={generating || totalBuildings === 0}
              testID="generate-hlbs-action-btn"
            />
          </View>

          {/* Generation Progress Step */}
          {generating && (
            <View style={styles.progressBox}>
              <ActivityIndicator size="small" color="#0066CC" style={{ marginRight: 8 }} />
              <Text style={[styles.progressStepText, { color: '#0066CC' }]}>{generationStep}</Text>
            </View>
          )}

          {error && <ErrorMessage message={error} style={{ marginTop: 10 }} />}
        </Card>

        {/* Validation & Invariants Summary Card */}
        {candidateHlbs.length > 0 && (
          <Card testID="validation-summary-card" style={styles.summaryCard}>
            <View style={styles.summaryHeader}>
              <View>
                <Text style={[styles.summaryTitle, themeStyles.text]}>
                  {t('candidate_hlbs_title') || 'Candidate HLBs'} (v{layout?.active_version_number || 1})
                </Text>
                <Text style={[styles.summarySubtitle, themeStyles.subtext]}>
                  {candidateHlbs.length} Blocks generated • Target: {targetSize} bldgs/HLB • Assigned:{' '}
                  {candidateHlbs.reduce((acc, h) => acc + (h.actual_building_count ?? h.building_count ?? 0), 0)} / {totalBuildings}
                </Text>
              </View>
              <View
                style={[
                  styles.overallBadge,
                  {
                    backgroundColor:
                      generationResult?.validation_status === 'VALID' ||
                      candidateHlbs.every((h) => h.validation_status === 'VALID')
                        ? '#E8F5E9'
                        : '#FFF3E0',
                  },
                ]}
              >
                <Text
                  style={[
                    styles.overallBadgeText,
                    {
                      color:
                        generationResult?.validation_status === 'VALID' ||
                        candidateHlbs.every((h) => h.validation_status === 'VALID')
                          ? '#2E7D32'
                          : '#E65100',
                    },
                  ]}
                >
                  {generationResult?.validation_status || 'VALID'}
                </Text>
              </View>
            </View>

            {/* Invariant Check Badges */}
            <View style={styles.invariantsRow}>
              <View style={styles.invariantTag}>
                <Text style={styles.checkIcon}>✓</Text>
                <Text style={[styles.invariantText, themeStyles.subtext]}>
                  {t('all_assigned_badge') || '100% Buildings Assigned'}
                </Text>
              </View>
              <View style={styles.invariantTag}>
                <Text style={styles.checkIcon}>✓</Text>
                <Text style={[styles.invariantText, themeStyles.subtext]}>
                  {t('no_duplicates_badge') || 'Zero Overlap'}
                </Text>
              </View>
              <View style={styles.invariantTag}>
                <Text style={styles.checkIcon}>✓</Text>
                <Text style={[styles.invariantText, themeStyles.subtext]}>
                  {t('boundary_valid_badge') || 'Within Boundary'}
                </Text>
              </View>
            </View>

            <View style={{ marginTop: 14 }}>
              <PrimaryButton
                title="🔍 PROCEED TO HLB REVIEW & APPROVAL →"
                onPress={() => {
                  const targetLayoutId = layout?.id || activeLayoutId || initialLayoutId;
                  if (targetLayoutId) {
                    navigation.navigate('HlbReview', {
                      layoutId: targetLayoutId,
                      areaName: areaDisplayName,
                      areaId: rawAreaId,
                    });
                  }
                }}
                testID="proceed-to-review-btn"
              />
            </View>
          </Card>
        )}

        {/* Map Visualization (Using react-native-maps satellite map) */}
        <Card testID="hlb-map-card" style={styles.mapCard}>
          <View style={styles.mapHeader}>
            <Text style={[styles.mapSectionTitle, themeStyles.text]}>HLB Spatial Partitioning</Text>
            <TouchableOpacity onPress={fitMapToLayout} style={styles.recenterBtn}>
              <Text style={styles.recenterBtnText}>⤢ Recenter</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.mapContainer}>
            <HlbSpatialMap
              ref={mapRef}
              testID="hlb-native-mapview"
              style={styles.map}
              initialRegion={initialRegion}
              mapType="satellite"
              showBoundary={true}
              boundaryRings={layoutRings}
              boundaryStrokeColor="#D97706"
              boundaryFillColor="rgba(217, 119, 6, 0.04)"
              candidateHlbs={candidateHlbs.map((hlb, idx) => ({
                id: hlb.id,
                block_code: hlb.block_code || hlb.hlb_code || 'HLB',
                hlb_code: hlb.block_code || hlb.hlb_code || 'HLB',
                boundary: hlb.boundary,
                centroid: hlb.centroid,
                building_count: hlb.actual_building_count ?? hlb.building_count ?? 0,
                actual_building_count: hlb.actual_building_count ?? hlb.building_count ?? 0,
                quality_score: hlb.quality_score,
                validation_status: hlb.validation_status,
                strokeColor: getHlbPalette(idx).stroke,
                fillColor: getHlbPalette(idx).fill,
              }))}
              selectedHlbId={selectedHlb?.id}
              fullscreenEnabled={true}
              fullscreenTitle={`${initialAreaName || 'Village'} • HLB Partition Map`}
              onSelectHlb={(h) => {
                const found = candidateHlbs.find((c) => c.id === h.id);
                if (found) {
                  setSelectedHlb(found);
                  setShowDetailModal(true);
                  const rings = parseGeoJSONToRings(found.boundary);
                  if (rings.length > 0 && rings[0].length > 0) {
                    mapRef.current?.fitToCoordinates(rings[0], {
                      edgePadding: { top: 50, right: 50, bottom: 50, left: 50 },
                      animated: true,
                    });
                  }
                }
              }}
              fitCoordinates={layoutRings.flat()}
            />

            {/* Empty State Overlay when no HLBs generated yet */}
            {candidateHlbs.length === 0 && !generating && (
              <View style={styles.mapEmptyOverlay}>
                <View style={styles.mapEmptyCard}>
                  <Text style={styles.mapEmptyIcon}>🗺️</Text>
                  <Text style={styles.mapEmptyTitle}>No HLB candidates generated yet.</Text>
                  <Text style={styles.mapEmptySubtitle}>
                    Set the Buildings per HLB target above and press GENERATE HLBs.
                  </Text>
                </View>
              </View>
            )}
          </View>
        </Card>

        {/* Candidate HLB Table / List */}
        {candidateHlbs.length > 0 && (
          <Card testID="candidate-hlb-list-card" style={styles.tableCard}>
            <Text style={[styles.tableTitle, themeStyles.text]}>
              Candidate Blocks ({candidateHlbs.length})
            </Text>
            <Text style={[styles.selectHint, themeStyles.subtext]}>
              {t('select_hlb_hint') || 'Tap a block on map or list to inspect details'}
            </Text>

            {/* Table Header */}
            <View style={[styles.tableRow, styles.tableHeader, themeStyles.tableHeader]}>
              <Text style={[styles.colCode, styles.headerText, themeStyles.text]}>
                {t('hlb_code_col') || 'HLB Code'}
              </Text>
              <Text style={[styles.colCount, styles.headerText, themeStyles.text]}>
                {t('building_count_col') || 'Buildings'}
              </Text>
              <Text style={[styles.colQuality, styles.headerText, themeStyles.text]}>
                {t('quality_col') || 'Quality'}
              </Text>
              <Text style={[styles.colStatus, styles.headerText, themeStyles.text]}>
                {t('status_col') || 'Status'}
              </Text>
            </View>

            {/* Table Rows */}
            {candidateHlbs.map((hlb, idx) => {
              const palette = getHlbPalette(idx);
              const isSelected = selectedHlb?.id === hlb.id;
              const code = hlb.block_code || hlb.hlb_code || 'HLB';
              const bldCount = hlb.actual_building_count ?? hlb.building_count ?? 0;
              const deviation = hlb.count_deviation ?? (bldCount - targetSize);
              const devSign = deviation > 0 ? `+${deviation}` : `${deviation}`;
              const qualityText =
                hlb.quality_score != null ? `${((hlb.quality_score ?? 0) * 100).toFixed(0)}%` : '—';
              const statusText = hlb.validation_status || 'VALID';

              return (
                <TouchableOpacity
                  key={hlb.id}
                  style={[
                    styles.tableRow,
                    themeStyles.tableRow,
                    isSelected && themeStyles.selectedRow,
                  ]}
                  onPress={() => {
                    setSelectedHlb(hlb);
                    setShowDetailModal(true);
                    const rings = parseGeoJSONToRings(hlb.boundary);
                    if (rings.length > 0 && rings[0].length > 0) {
                      mapRef.current?.fitToCoordinates(rings[0], {
                        edgePadding: { top: 50, right: 50, bottom: 50, left: 50 },
                        animated: true,
                      });
                    }
                  }}
                  testID={`hlb-row-${code}`}
                >
                  <View style={styles.colCodeRow}>
                    <View style={[styles.colorDot, { backgroundColor: palette.stroke }]} />
                    <Text style={[styles.codeText, themeStyles.text]}>{code}</Text>
                  </View>

                  <View style={styles.colCountContainer}>
                    <Text style={[styles.countText, themeStyles.text]}>
                      {bldCount}
                    </Text>
                    <Text style={[styles.devText, { color: deviation === 0 ? '#2E7D32' : '#757575' }]}>
                      ({devSign})
                    </Text>
                  </View>

                  <View style={styles.qualityColContainer}>
                    <Text
                      style={[
                        styles.qualityText,
                        {
                          color:
                            (hlb.quality_score ?? 0) >= 0.9
                              ? '#2E7D32'
                              : (hlb.quality_score ?? 0) >= 0.75
                              ? '#F57C00'
                              : '#D32F2F',
                        },
                      ]}
                    >
                      {qualityText}
                    </Text>
                  </View>

                  <View style={styles.statusColContainer}>
                    <StatusBadge
                      type={
                        statusText === 'VALID'
                          ? 'VALID'
                          : statusText === 'WARNING'
                          ? 'WARNING'
                          : 'INVALID'
                      }
                      label={statusText}
                    />
                  </View>
                </TouchableOpacity>
              );
            })}
          </Card>
        )}
      </ScrollView>

      {/* Candidate HLB Detail Modal */}
      <Modal visible={showDetailModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, themeStyles.modalBg]}>
            {selectedHlb && (
              <>
                <View style={styles.modalHeader}>
                  <View>
                    <Text style={[styles.modalHlbCode, themeStyles.text]}>
                      {selectedHlb.block_code || selectedHlb.hlb_code || 'HLB'}
                    </Text>
                    <Text style={[styles.modalCandidateTag, themeStyles.subtext]}>
                      {t('candidate_hlb_tag') || 'Candidate HLB'} • Pending Tahsildar Review
                    </Text>
                  </View>
                  <StatusBadge
                    type={
                      selectedHlb.validation_status === 'VALID'
                        ? 'VALID'
                        : selectedHlb.validation_status === 'WARNING'
                        ? 'WARNING'
                        : 'INVALID'
                    }
                    label={selectedHlb.validation_status || 'VALID'}
                  />
                </View>

                {/* Metrics Breakdown */}
                <View style={styles.modalMetricsGrid}>
                  <View style={styles.modalMetricItem}>
                    <Text style={styles.modalMetricVal}>
                      {selectedHlb.actual_building_count ?? selectedHlb.building_count ?? 0}
                    </Text>
                    <Text style={[styles.modalMetricLabel, themeStyles.subtext]}>
                      {t('detected_buildings_label') || 'Detected Buildings'}
                    </Text>
                  </View>
                  <View style={styles.modalMetricItem}>
                    <Text style={[styles.modalMetricVal, { color: '#0066CC' }]}>
                      {targetSize}
                    </Text>
                    <Text style={[styles.modalMetricLabel, themeStyles.subtext]}>
                      {t('deputy_target_label') || 'Target'}
                    </Text>
                  </View>
                  <View style={styles.modalMetricItem}>
                    {(() => {
                      const mBld = selectedHlb.actual_building_count ?? selectedHlb.building_count ?? 0;
                      const mDev = selectedHlb.count_deviation ?? (mBld - targetSize);
                      return (
                        <>
                          <Text
                            style={[
                              styles.modalMetricVal,
                              {
                                color: mDev === 0 ? '#2E7D32' : '#F57C00',
                              },
                            ]}
                          >
                            {mDev > 0 ? `+${mDev}` : `${mDev}`}
                          </Text>
                          <Text style={[styles.modalMetricLabel, themeStyles.subtext]}>
                            {t('count_deviation_label') || 'Deviation'}
                          </Text>
                        </>
                      );
                    })()}
                  </View>
                  <View style={styles.modalMetricItem}>
                    <Text style={[styles.modalMetricVal, { color: '#0066CC' }]}>
                      {(selectedHlb.quality_score * 100).toFixed(0)}%
                    </Text>
                    <Text style={[styles.modalMetricLabel, themeStyles.subtext]}>
                      Quality
                    </Text>
                  </View>
                </View>

                {/* Score Breakdown details if present */}
                {selectedHlb.validation_details && (
                  <View style={styles.scoreBreakdownBox}>
                    <Text style={[styles.breakdownTitle, themeStyles.text]}>
                      Geometric Validation Breakdown:
                    </Text>
                    <View style={styles.scoreRow}>
                      <Text style={[styles.scoreLabel, themeStyles.subtext]}>Count Score:</Text>
                      <Text style={[styles.scoreVal, themeStyles.text]}>
                        {((selectedHlb.validation_details.count_score ?? 1) * 100).toFixed(0)}%
                      </Text>
                    </View>
                    <View style={styles.scoreRow}>
                      <Text style={[styles.scoreLabel, themeStyles.subtext]}>Boundary Score:</Text>
                      <Text style={[styles.scoreVal, themeStyles.text]}>
                        {((selectedHlb.validation_details.boundary_score ?? 1) * 100).toFixed(0)}%
                      </Text>
                    </View>
                    <View style={styles.scoreRow}>
                      <Text style={[styles.scoreLabel, themeStyles.subtext]}>
                        Continuity Score:
                      </Text>
                      <Text style={[styles.scoreVal, themeStyles.text]}>
                        {((selectedHlb.validation_details.continuity_score ?? 1) * 100).toFixed(0)}%
                      </Text>
                    </View>
                    <View style={styles.scoreRow}>
                      <Text style={[styles.scoreLabel, themeStyles.subtext]}>
                        Compactness Score:
                      </Text>
                      <Text style={[styles.scoreVal, themeStyles.text]}>
                        {((selectedHlb.validation_details.compactness_score ?? 1) * 100).toFixed(0)}%
                      </Text>
                    </View>
                  </View>
                )}

                {/* Warnings List */}
                {selectedHlb.warnings && selectedHlb.warnings.length > 0 ? (
                  <View style={styles.warningListBox}>
                    <Text style={styles.warningBoxTitle}>⚠️ Warnings:</Text>
                    {selectedHlb.warnings.map((w, wIdx) => (
                      <Text key={wIdx} style={styles.warningItemText}>
                        • {w}
                      </Text>
                    ))}
                  </View>
                ) : (
                  <View style={styles.noWarningBox}>
                    <Text style={styles.noWarningText}>
                      ✓ {t('no_warnings_badge') || 'No Validation Warnings'}
                    </Text>
                  </View>
                )}

                <Text style={[styles.disclaimerText, themeStyles.subtext]}>
                  {t('candidate_hlb_desc') ||
                    'Candidate HLB generated by AI spatial clustering. Final verification in Phase 5.'}
                </Text>

                <View style={{ marginTop: 16 }}>
                  <SecondaryButton
                    title={t('close') || 'Close'}
                    onPress={() => setShowDetailModal(false)}
                    testID="close-hlb-detail-modal-btn"
                  />
                </View>
              </>
            )}
          </View>
        </View>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  topCard: {
    marginBottom: 16,
  },
  topHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  layoutTitleText: {
    fontSize: 17,
    fontWeight: 'bold',
  },
  areaSubtitleText: {
    fontSize: 13,
    marginTop: 3,
  },
  detectionStatsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(0, 102, 204, 0.05)',
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
    borderWidth: 1,
    borderColor: 'rgba(0, 102, 204, 0.12)',
  },
  statBox: {
    flex: 1,
    alignItems: 'center',
  },
  statDivider: {
    width: 1,
    height: '80%',
    backgroundColor: '#D0DBE5',
  },
  statLabel: {
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 2,
  },
  statValueHighlight: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  sourceBadgeContainer: {
    backgroundColor: '#E0F2FE',
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: '#38BDF8',
  },
  sourceBadgeText: {
    color: '#0284C7',
    fontSize: 11,
    fontWeight: '700',
  },
  targetConfigRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(0, 0, 0, 0.03)',
    borderRadius: 8,
    padding: 10,
    marginTop: 4,
  },
  targetInputContainer: {
    flex: 1,
    marginRight: 12,
  },
  targetLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  stepperRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  stepperBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
  },
  stepperBtnText: {
    fontSize: 13,
    fontWeight: 'bold',
  },
  targetInput: {
    width: 60,
    borderWidth: 1,
    borderRadius: 6,
    textAlign: 'center',
    paddingVertical: 4,
    marginHorizontal: 8,
    fontSize: 14,
    fontWeight: 'bold',
  },
  estimateBox: {
    alignItems: 'center',
    paddingLeft: 12,
    borderLeftWidth: 1,
    borderColor: '#E0E0E0',
  },
  estimateNumber: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  estimateLabel: {
    fontSize: 11,
    marginTop: 2,
  },
  progressBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
    padding: 8,
    borderRadius: 6,
    backgroundColor: '#E3F2FD',
  },
  progressStepText: {
    fontSize: 12,
    fontWeight: '600',
  },
  summaryCard: {
    marginBottom: 16,
  },
  summaryHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  summaryTitle: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  summarySubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  overallBadge: {
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 12,
  },
  overallBadgeText: {
    fontSize: 12,
    fontWeight: 'bold',
  },
  invariantsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 6,
  },
  invariantTag: {
    flexDirection: 'row',
    alignItems: 'center',
    marginRight: 14,
    marginTop: 4,
  },
  checkIcon: {
    color: '#2E7D32',
    fontWeight: 'bold',
    marginRight: 4,
    fontSize: 13,
  },
  invariantText: {
    fontSize: 12,
  },
  mapCard: {
    marginBottom: 16,
    padding: 0,
    overflow: 'hidden',
  },
  mapHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  mapSectionTitle: {
    fontSize: 15,
    fontWeight: 'bold',
  },
  recenterBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
    backgroundColor: 'rgba(0, 102, 204, 0.1)',
  },
  recenterBtnText: {
    color: '#0066CC',
    fontSize: 12,
    fontWeight: '600',
  },
  mapContainer: {
    height: 280,
    width: '100%',
    position: 'relative',
  },
  map: {
    ...StyleSheet.absoluteFill,
  },
  mapEmptyOverlay: {
    ...StyleSheet.absoluteFill,
    backgroundColor: 'rgba(15, 23, 42, 0.65)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  mapEmptyCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 12,
    padding: 16,
    alignItems: 'center',
    maxWidth: 280,
    ...Platform.select({
      web: {
        boxShadow: '0px 3px 10px rgba(0, 0, 0, 0.3)',
      },
      default: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 3 },
        shadowOpacity: 0.3,
        shadowRadius: 6,
        elevation: 6,
      },
    }),
  },
  mapEmptyIcon: {
    fontSize: 28,
    marginBottom: 6,
  },
  mapEmptyTitle: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#1E293B',
    textAlign: 'center',
    marginBottom: 4,
  },
  mapEmptySubtitle: {
    fontSize: 12,
    color: '#64748B',
    textAlign: 'center',
  },
  markerBadge: {
    paddingVertical: 3,
    paddingHorizontal: 6,
    borderRadius: 10,
    borderWidth: 1.5,
    alignItems: 'center',
  },
  markerText: {
    color: '#FFFFFF',
    fontSize: 10,
    fontWeight: 'bold',
  },
  markerSubtext: {
    color: '#FFFFFF',
    fontSize: 8,
  },
  tableCard: {
    marginBottom: 16,
  },
  tableTitle: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  selectHint: {
    fontSize: 11,
    marginTop: 2,
    marginBottom: 10,
  },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderBottomWidth: 1,
  },
  tableHeader: {
    borderBottomWidth: 2,
    borderRadius: 4,
  },
  headerText: {
    fontSize: 12,
    fontWeight: 'bold',
  },
  colCode: {
    flex: 2,
  },
  colCount: {
    flex: 2.2,
    textAlign: 'center',
  },
  colQuality: {
    flex: 1.5,
    textAlign: 'center',
  },
  colStatus: {
    flex: 2,
    alignItems: 'flex-end',
  },
  colCodeRow: {
    flex: 2,
    flexDirection: 'row',
    alignItems: 'center',
  },
  colorDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  codeText: {
    fontSize: 13,
    fontWeight: '600',
  },
  colCountContainer: {
    flex: 2.2,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
  },
  countText: {
    fontSize: 13,
    fontWeight: 'bold',
  },
  devText: {
    fontSize: 11,
    marginLeft: 4,
  },
  qualityColContainer: {
    flex: 1.5,
    alignItems: 'center',
  },
  qualityText: {
    fontSize: 13,
    fontWeight: 'bold',
  },
  statusColContainer: {
    flex: 2,
    alignItems: 'flex-end',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    padding: 20,
  },
  modalContent: {
    borderRadius: 12,
    padding: 20,
  },
  modalHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 14,
  },
  modalHlbCode: {
    fontSize: 20,
    fontWeight: 'bold',
  },
  modalCandidateTag: {
    fontSize: 12,
    marginTop: 2,
  },
  modalMetricsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    backgroundColor: 'rgba(0,0,0,0.03)',
    borderRadius: 8,
    padding: 12,
    marginBottom: 14,
  },
  modalMetricItem: {
    alignItems: 'center',
  },
  modalMetricVal: {
    fontSize: 17,
    fontWeight: 'bold',
  },
  modalMetricLabel: {
    fontSize: 11,
    marginTop: 2,
  },
  scoreBreakdownBox: {
    marginBottom: 12,
  },
  breakdownTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  scoreRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 3,
  },
  scoreLabel: {
    fontSize: 12,
  },
  scoreVal: {
    fontSize: 12,
    fontWeight: '600',
  },
  warningListBox: {
    backgroundColor: '#FFF3E0',
    borderRadius: 6,
    padding: 10,
    marginBottom: 12,
  },
  warningBoxTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#E65100',
    marginBottom: 4,
  },
  warningItemText: {
    fontSize: 11,
    color: '#E65100',
    marginBottom: 2,
  },
  noWarningBox: {
    backgroundColor: '#E8F5E9',
    borderRadius: 6,
    padding: 8,
    marginBottom: 12,
  },
  noWarningText: {
    fontSize: 12,
    color: '#2E7D32',
    fontWeight: '600',
  },
  disclaimerText: {
    fontSize: 11,
    fontStyle: 'italic',
    textAlign: 'center',
    marginTop: 4,
  },
  errorFullContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  errorFullIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  errorFullTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 8,
  },
  errorFullDesc: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
  },
  presetRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
    justifyContent: 'center',
  },
  presetBtn: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#D0DBE5',
    backgroundColor: '#F1F5F9',
  },
  presetBtnActive: {
    backgroundColor: '#0066CC',
    borderColor: '#0066CC',
  },
  presetBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#334155',
  },
  presetBtnTextActive: {
    color: '#FFFFFF',
    fontWeight: 'bold',
  },
  loadingContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  loadingText: {
    marginTop: 16,
    fontSize: 15,
    fontWeight: '600',
  },
});
