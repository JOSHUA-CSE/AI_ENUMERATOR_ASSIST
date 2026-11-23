import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  useColorScheme,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import {
  AppHeader,
  Card,
  ErrorMessage,
  HlbSpatialMap,
  HlbSpatialMapRef,
  ScreenContainer,
  StatusBadge,
  PrimaryButton,
  SecondaryButton,
} from '../../components';
import { extractErrorMessage } from '../../core/apiClient';
import { AreaBoundaryResponse, areaService } from '../../core/areaService';
import { layoutService, HlbCandidate } from '../../core/layoutService';
import { parseGeoJSONToRings } from '../../core/geometryUtils';
import {
  supervisorService,
  SupervisorLayoutSummary,
  SupervisorLayoutProgress,
  SupervisorHlbProgress,
} from '../../core/supervisorService';
import {
  enumeratorService,
  LayoutEnumeratorAssignmentsResponse,
} from '../../core/enumeratorService';
import { useTranslation } from '../../core/localization';
import {
  EnumeratorAssignmentModal,
  HlbTargetInfo,
} from './EnumeratorAssignmentModal';
import { SupervisorHlbDetailModal } from './SupervisorHlbDetailModal';
import type {
  SupervisorNavigationProp,
  SupervisorStackParamList,
} from '../../navigation/navigationTypes';

const HLB_PALETTE = [
  { fill: 'rgba(2, 132, 199, 0.12)', stroke: '#0284C7', text: '#0284C7' },
  { fill: 'rgba(16, 185, 129, 0.12)', stroke: '#10B981', text: '#10B981' },
  { fill: 'rgba(139, 92, 246, 0.12)', stroke: '#8B5CF6', text: '#8B5CF6' },
  { fill: 'rgba(245, 158, 11, 0.12)', stroke: '#F59E0B', text: '#D97706' },
  { fill: 'rgba(236, 72, 153, 0.12)', stroke: '#EC4899', text: '#DB2777' },
  { fill: 'rgba(20, 184, 166, 0.12)', stroke: '#14B8A6', text: '#0D9488' },
  { fill: 'rgba(99, 102, 241, 0.12)', stroke: '#6366F1', text: '#4F46E5' },
  { fill: 'rgba(234, 88, 12, 0.12)', stroke: '#EA580C', text: '#C2410C' },
];

export function SupervisorLayoutDetailScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<SupervisorNavigationProp>();
  const route = useRoute<RouteProp<SupervisorStackParamList, 'SupervisorLayoutDetail'>>();
  const { t } = useTranslation();

  const layoutId = route.params?.layoutId;
  const passedLayoutName = route.params?.layoutName;

  const [layout, setLayout] = useState<SupervisorLayoutSummary | null>(null);
  const [hlbs, setHlbs] = useState<HlbCandidate[]>([]);
  const [layoutProgress, setLayoutProgress] = useState<SupervisorLayoutProgress | null>(null);
  const [assignmentSummary, setAssignmentSummary] = useState<LayoutEnumeratorAssignmentsResponse | null>(null);
  const [boundaryData, setBoundaryData] = useState<AreaBoundaryResponse | null>(null);
  const [selectedHlbId, setSelectedHlbId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Modals State
  const [assignmentModalVisible, setAssignmentModalVisible] = useState(false);
  const [targetHlbForModal, setTargetHlbForModal] = useState<HlbTargetInfo | null>(null);
  const [detailModalVisible, setDetailModalVisible] = useState(false);
  const [selectedHlbProgress, setSelectedHlbProgress] = useState<SupervisorHlbProgress | null>(null);

  const mapRef = useRef<HlbSpatialMapRef>(null);

  const loadData = useCallback(async (isRefresh = false) => {
    if (!layoutId) {
      setError('Layout ID is missing');
      setLoading(false);
      return;
    }

    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [layoutRes, hlbsRes, assignSummaryRes, progressRes] = await Promise.all([
        supervisorService.getMyAssignedLayoutDetail(layoutId),
        layoutService.getLayoutHlbs(layoutId),
        enumeratorService.getLayoutEnumeratorAssignments(layoutId).catch(() => null),
        supervisorService.getLayoutProgress(layoutId).catch(() => null),
      ]);

      setLayout(layoutRes);
      const hlbList = Array.isArray(hlbsRes) ? hlbsRes : (hlbsRes?.items || []);
      setHlbs(hlbList);
      setAssignmentSummary(assignSummaryRes);
      setLayoutProgress(progressRes);

      if (hlbList.length > 0 && !selectedHlbId) {
        setSelectedHlbId(hlbList[0].id);
      }

      // Fetch area boundary for background boundary overlay
      const areaId = layoutRes.area_id || layoutRes.administrative_area_id;
      if (areaId) {
        try {
          const bRes = await areaService.getAreaBoundary(areaId);
          setBoundaryData(bRes);
        } catch {
          // Non-fatal if area boundary fails
        }
      }
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [layoutId, selectedHlbId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Convert area boundary to map rings
  const boundaryRings = useMemo(() => {
    if (boundaryData?.boundary) {
      return parseGeoJSONToRings(boundaryData.boundary);
    }
    if (layout?.boundary) {
      return parseGeoJSONToRings(layout.boundary);
    }
    return [];
  }, [boundaryData, layout]);

  // Map items with palette colors
  const mapItems = useMemo(() => {
    return hlbs.map((hlb, index) => {
      const color = HLB_PALETTE[index % HLB_PALETTE.length];
      return {
        id: hlb.id,
        block_code: hlb.block_code,
        boundary: hlb.boundary,
        building_count: hlb.actual_building_count,
        target_building_count: hlb.target_building_count,
        strokeColor: color.stroke,
        fillColor: color.fill,
      };
    });
  }, [hlbs]);

  // Map of HLB ID to active enumerator assignment item
  const assignmentMap = useMemo(() => {
    const map = new Map<string, any>();
    if (assignmentSummary?.items) {
      for (const item of assignmentSummary.items) {
        map.set(item.hlb_id, item);
      }
    }
    return map;
  }, [assignmentSummary]);

  // Map of HLB ID to HLB progress item
  const progressMap = useMemo(() => {
    const map = new Map<string, SupervisorHlbProgress>();
    if (layoutProgress?.hlbs) {
      for (const hp of layoutProgress.hlbs) {
        map.set(hp.hlb_id, hp);
      }
    }
    return map;
  }, [layoutProgress]);

  const handleOpenAssignModal = (hlb: HlbCandidate) => {
    setTargetHlbForModal({
      id: hlb.id,
      block_code: hlb.block_code,
      name: hlb.name,
      actual_building_count: hlb.actual_building_count,
      target_building_count: hlb.target_building_count,
    });
    setAssignmentModalVisible(true);
  };

  const handleOpenDetailModal = (hlb: HlbCandidate, hlbProg?: SupervisorHlbProgress) => {
    const prog: SupervisorHlbProgress = hlbProg || {
      hlb_id: hlb.id,
      block_code: hlb.block_code,
      name: hlb.name,
      total_houses: hlb.actual_building_count || 0,
      completed_houses: 0,
      remaining_houses: hlb.actual_building_count || 0,
      locked_houses: 0,
      revisit_count: 0,
      progress_percentage: 0.0,
      boundary_alert_count: 0,
    };
    setSelectedHlbProgress(prog);
    setDetailModalVisible(true);
  };

  const handleAssignmentSuccess = () => {
    loadData(true);
  };

  const themeStyles = {
    container: { backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC' },
    card: { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' },
    text: { color: isDarkMode ? '#F1F5F9' : '#0F172A' },
    subtext: { color: isDarkMode ? '#94A3B8' : '#64748B' },
    highlight: { color: isDarkMode ? '#38BDF8' : '#0284C7' },
    itemBox: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
    selectedItemBox: {
      backgroundColor: isDarkMode ? '#1E3A5F' : '#E0F2FE',
      borderColor: isDarkMode ? '#38BDF8' : '#0284C7',
    },
    incompleteBox: {
      backgroundColor: isDarkMode ? '#2D1F1A' : '#FFF7ED',
      borderColor: isDarkMode ? '#9A3412' : '#FDBA74',
    },
    completeBox: {
      backgroundColor: isDarkMode ? '#14291F' : '#F0FDF4',
      borderColor: isDarkMode ? '#166534' : '#86EFAC',
    },
    progressTrack: {
      backgroundColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
    badgeWarning: {
      backgroundColor: isDarkMode ? '#451A03' : '#FFEDD5',
      borderColor: isDarkMode ? '#9A3412' : '#FDBA74',
    },
  };

  const layoutDisplayName = layout?.name || passedLayoutName || 'Assigned Layout';
  const supervisorName =
    layout?.supervisor_name ||
    layout?.assignment?.supervisor_name ||
    'Assigned Supervisor';

  const hlbCount = hlbs.length || layout?.hlb_count || layoutProgress?.total_hlbs || 0;
  const totalHouses =
    layoutProgress?.total_houses ?? layout?.total_buildings ?? layout?.actual_building_count ?? 0;
  const completedHouses = layoutProgress?.completed_houses ?? 0;
  const remainingHouses = layoutProgress?.remaining_houses ?? Math.max(0, totalHouses - completedHouses);
  const lockedHouses = layoutProgress?.locked_houses ?? 0;
  const revisitCount = layoutProgress?.revisit_count ?? 0;
  const progressPct =
    layoutProgress?.progress_percentage != null
      ? layoutProgress.progress_percentage
      : totalHouses > 0
      ? (completedHouses / totalHouses) * 100
      : 0.0;

  const assignedEnumCount = assignmentSummary?.assigned_enumerators ?? 0;
  const requiredEnumCount = assignmentSummary?.required_enumerators ?? hlbCount;
  const isAssignmentComplete =
    assignmentSummary?.is_complete ?? (assignedEnumCount === hlbCount && hlbCount > 0);

  return (
    <ScreenContainer testID="supervisor-layout-detail-screen" style={themeStyles.container}>
      <AppHeader
        title={layoutDisplayName}
        subtitle={`SUPERVISOR FIELDWORK MONITORING • ${layout?.id.substring(0, 8).toUpperCase() || ''}`}
        roleType="SUPERVISOR"
        roleLabel={t('role_supervisor')}
        showBack
        onBack={() => navigation.goBack()}
        testID="supervisor-layout-detail-header"
      />

      {error ? (
        <View style={styles.errorContainer} testID="supervisor-layout-error-view">
          <ErrorMessage
            message={error}
            onRetry={() => loadData()}
            testID="supervisor-layout-error-message"
          />
          <TouchableOpacity
            style={styles.goBackBtn}
            onPress={() => navigation.goBack()}
            testID="supervisor-error-go-back-btn"
          >
            <Text style={styles.goBackBtnText}>← {t('back')}</Text>
          </TouchableOpacity>
        </View>
      ) : loading && !refreshing ? (
        <View style={styles.loadingContainer} testID="supervisor-layout-loading-view">
          <ActivityIndicator size="large" color="#0284C7" />
          <Text style={[styles.loadingText, themeStyles.subtext]}>
            Loading assigned layout details...
          </Text>
        </View>
      ) : (
        <ScrollView
          style={styles.content}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => loadData(true)}
              tintColor="#0284C7"
            />
          }
        >
          {/* 1. Header Overview Card */}
          <Card testID="supervisor-layout-overview-card" style={themeStyles.card}>
            <View style={styles.cardHeaderRow}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.layoutNameText, themeStyles.text]}>
                  {layoutDisplayName}
                </Text>
                <Text style={[styles.layoutIdText, themeStyles.subtext]}>
                  Layout ID: {layout?.id.substring(0, 8).toUpperCase() || '-'}
                </Text>
              </View>
              <StatusBadge
                type={layout?.status === 'ASSIGNED' ? 'ASSIGNED' : 'APPROVED'}
                label={layout?.status || 'ASSIGNED'}
              />
            </View>

            <View style={styles.metricsGrid}>
              <View style={[styles.metricBox, themeStyles.itemBox]}>
                <Text style={[styles.metricVal, themeStyles.highlight]}>
                  {hlbCount}
                </Text>
                <Text style={[styles.metricLbl, themeStyles.subtext]}>
                  HLBs
                </Text>
              </View>
              <View style={[styles.metricBox, themeStyles.itemBox]}>
                <Text style={[styles.metricVal, themeStyles.text]}>
                  {totalHouses}
                </Text>
                <Text style={[styles.metricLbl, themeStyles.subtext]}>
                  {t('total_houses')}
                </Text>
              </View>
              <View style={[styles.metricBox, themeStyles.itemBox]}>
                <Text style={[styles.metricVal, { color: '#2E7D32' }]}>
                  {supervisorName}
                </Text>
                <Text style={[styles.metricLbl, themeStyles.subtext]}>
                  Supervisor
                </Text>
              </View>
            </View>
          </Card>

          {/* 2. Layout Fieldwork Progress Card */}
          <Card testID="supervisor-layout-progress-card" style={themeStyles.card}>
            <View style={styles.cardHeaderRow}>
              <View style={{ flex: 1 }}>
                <Text style={[styles.sectionTitle, themeStyles.text]}>
                  {t('layout_progress')}
                </Text>
                <Text style={[styles.progressRatioHeader, themeStyles.subtext]}>
                  {completedHouses} of {totalHouses} {t('houses_buildings_unit')} completed
                </Text>
              </View>
              <Text style={[styles.progressBigPct, { color: progressPct >= 100 ? '#16A34A' : '#0284C7' }]}>
                {progressPct.toFixed(1)}%
              </Text>
            </View>

            {/* Progress Bar */}
            <View style={[styles.progressBarTrack, themeStyles.progressTrack]}>
              <View
                style={[
                  styles.progressBarFill,
                  {
                    width: `${Math.min(100, Math.max(0, progressPct))}%`,
                    backgroundColor: progressPct >= 100 ? '#16A34A' : '#0284C7',
                  },
                ]}
              />
            </View>

            {/* Progress Metrics Grid */}
            <View style={styles.progressMetricsRow}>
              <View style={[styles.progressMiniBox, themeStyles.itemBox]}>
                <Text style={[styles.pMiniVal, { color: '#16A34A' }]}>{completedHouses}</Text>
                <Text style={[styles.pMiniLbl, themeStyles.subtext]}>{t('completed')}</Text>
              </View>
              <View style={[styles.progressMiniBox, themeStyles.itemBox]}>
                <Text style={[styles.pMiniVal, { color: '#EA580C' }]}>{remainingHouses}</Text>
                <Text style={[styles.pMiniLbl, themeStyles.subtext]}>{t('remaining')}</Text>
              </View>
              <View style={[styles.progressMiniBox, themeStyles.itemBox]}>
                <Text style={[styles.pMiniVal, { color: '#DC2626' }]}>{lockedHouses}</Text>
                <Text style={[styles.pMiniLbl, themeStyles.subtext]}>{t('locked')}</Text>
              </View>
              <View style={[styles.progressMiniBox, themeStyles.itemBox]}>
                <Text style={[styles.pMiniVal, themeStyles.text]}>{revisitCount}</Text>
                <Text style={[styles.pMiniLbl, themeStyles.subtext]}>{t('revisit_count')}</Text>
              </View>
            </View>
          </Card>

          {/* 3. Enumerator Assignment Summary Card */}
          <Card
            testID="supervisor-assignment-summary-card"
            style={[
              themeStyles.card,
              isAssignmentComplete ? themeStyles.completeBox : themeStyles.incompleteBox,
              styles.summaryBannerCard,
            ]}
          >
            <View style={styles.summaryHeaderRow}>
              <View>
                <Text style={[styles.summaryTitle, themeStyles.text]}>
                  {t('enumerator_assignment')}
                </Text>
                <Text style={[styles.summarySubtitle, themeStyles.subtext]}>
                  1 HLB = 1 Primary Enumerator
                </Text>
              </View>
              <StatusBadge
                type={isAssignmentComplete ? 'ACTIVE' : 'WARNING'}
                label={
                  isAssignmentComplete
                    ? `✓ ${t('assignment_complete')}`
                    : `⚠ ${t('assignment_incomplete')}`
                }
              />
            </View>

            <View style={styles.summaryStatsRow}>
              <View style={styles.summaryStatItem}>
                <Text style={[styles.summaryStatVal, themeStyles.text]}>
                  {hlbCount}
                </Text>
                <Text style={[styles.summaryStatLbl, themeStyles.subtext]}>
                  {t('hlbs_label')}
                </Text>
              </View>

              <View style={styles.summaryStatItem}>
                <Text style={[styles.summaryStatVal, { color: '#0284C7' }]}>
                  {requiredEnumCount}
                </Text>
                <Text style={[styles.summaryStatLbl, themeStyles.subtext]}>
                  {t('enumerators_required')}
                </Text>
              </View>

              <View style={styles.summaryStatItem}>
                <Text
                  style={[
                    styles.summaryStatVal,
                    { color: isAssignmentComplete ? '#16A34A' : '#EA580C' },
                  ]}
                >
                  {assignedEnumCount}
                </Text>
                <Text style={[styles.summaryStatLbl, themeStyles.subtext]}>
                  {t('enumerators_assigned')}
                </Text>
              </View>

              <View style={styles.summaryStatItem}>
                <Text
                  style={[
                    styles.summaryStatVal,
                    { color: isAssignmentComplete ? '#16A34A' : '#DC2626' },
                  ]}
                >
                  {Math.max(0, requiredEnumCount - assignedEnumCount)}
                </Text>
                <Text style={[styles.summaryStatLbl, themeStyles.subtext]}>
                  {t('remaining_enumerators')}
                </Text>
              </View>
            </View>

            {!isAssignmentComplete && (
              <View style={styles.incompleteWarningBox}>
                <Text style={styles.incompleteWarningText}>
                  ⚠ {Math.max(0, requiredEnumCount - assignedEnumCount)}{' '}
                  {t('hlbs_require_assignment')}
                </Text>
              </View>
            )}
          </Card>

          {/* 4. Map Section with Fullscreen Support */}
          <Card testID="supervisor-layout-map-card" style={[styles.mapCard, themeStyles.card]}>
            <View style={styles.mapTitleRow}>
              <Text style={[styles.sectionTitle, themeStyles.text]}>
                SPATIAL OVERVIEW
              </Text>
              <Text style={[styles.mapSubtitle, themeStyles.subtext]}>
                HLB Boundaries & Satellite View
              </Text>
            </View>

            <View style={styles.mapWrapper}>
              <HlbSpatialMap
                ref={mapRef}
                style={styles.map}
                boundaryRings={boundaryRings}
                boundaryStrokeColor="#E11D48"
                boundaryFillColor="rgba(225, 29, 72, 0.04)"
                candidateHlbs={mapItems}
                selectedHlbId={selectedHlbId}
                onSelectHlb={(item) => setSelectedHlbId(item.id)}
                fullscreenEnabled={true}
                fullscreenTitle={`${layoutDisplayName} — Spatial Overview`}
                testID="supervisor-layout-spatial-map"
              />
            </View>
          </Card>

          {/* 5. HLB List & Detailed Fieldwork Progress Cards */}
          <Card testID="supervisor-hlb-list-card" style={themeStyles.card}>
            <View style={styles.hlbListHeaderRow}>
              <Text style={[styles.sectionTitle, themeStyles.text]}>
                {t('hlb_summary_title')} ({hlbs.length} Blocks)
              </Text>
            </View>

            {hlbs.map((hlb, index) => {
              const isSelected = selectedHlbId === hlb.id;
              const palette = HLB_PALETTE[index % HLB_PALETTE.length];
              const assignItem = assignmentMap.get(hlb.id);
              const isAssigned = assignItem?.is_assigned || assignItem?.assignment != null;
              const assignedEnum = assignItem?.assignment;

              // Authoritative progress info
              const hlbProg = progressMap.get(hlb.id);
              const hlbProgressPct =
                hlbProg?.progress_percentage != null
                  ? hlbProg.progress_percentage
                  : 0.0;
              const hlbCompleted = hlbProg?.completed_houses ?? 0;
              const hlbTotal = hlbProg?.total_houses ?? hlb.actual_building_count ?? 0;
              const hlbRemaining = hlbProg?.remaining_houses ?? Math.max(0, hlbTotal - hlbCompleted);
              const hlbLocked = hlbProg?.locked_houses ?? 0;
              const hlbRevisits = hlbProg?.revisit_count ?? 0;
              const hlbGpsCoverage = hlbProg?.gps_coverage;
              const alertCount = hlbProg?.boundary_alert_count ?? 0;
              const lastSync = hlbProg?.last_sync;

              return (
                <View
                  key={hlb.id}
                  style={[
                    styles.hlbCardWrapper,
                    themeStyles.itemBox,
                    isSelected && themeStyles.selectedItemBox,
                  ]}
                  testID={`supervisor-hlb-item-${hlb.block_code}`}
                >
                  <TouchableOpacity
                    style={styles.hlbCardTop}
                    onPress={() => setSelectedHlbId(hlb.id)}
                    activeOpacity={0.8}
                  >
                    <View
                      style={[
                        styles.colorIndicator,
                        { backgroundColor: palette.stroke },
                      ]}
                    />

                    <View style={styles.hlbItemInfo}>
                      <View style={styles.hlbTitleRow}>
                        <Text style={[styles.hlbCodeText, { color: palette.stroke }]}>
                          {hlb.block_code}
                        </Text>
                        <View style={styles.hlbBadgeRow}>
                          {alertCount > 0 && (
                            <View style={[styles.alertBadgeBox, themeStyles.badgeWarning]}>
                              <Text style={styles.alertBadgeText}>
                                ⚠ {alertCount} {t('boundary_alerts_count')}
                              </Text>
                            </View>
                          )}
                          <StatusBadge
                            type={isAssigned ? 'ACTIVE' : 'REQUIRED'}
                            label={isAssigned ? t('assigned') : t('required')}
                          />
                        </View>
                      </View>

                      {/* Progress Bar in Card */}
                      <View style={styles.hlbProgressBarWrap}>
                        <View style={styles.hlbProgressHead}>
                          <Text
                            style={[
                              styles.hlbProgressPct,
                              { color: hlbProgressPct >= 100 ? '#16A34A' : '#0284C7' },
                            ]}
                          >
                            {hlbProgressPct.toFixed(1)}% {t('progress')}
                          </Text>
                          <Text style={[styles.hlbHousesRatio, themeStyles.subtext]}>
                            {hlbCompleted} / {hlbTotal} {t('houses_buildings_unit')}
                          </Text>
                        </View>
                        <View style={[styles.hlbProgressTrack, themeStyles.progressTrack]}>
                          <View
                            style={[
                              styles.hlbProgressFill,
                              {
                                width: `${Math.min(100, Math.max(0, hlbProgressPct))}%`,
                                backgroundColor: hlbProgressPct >= 100 ? '#16A34A' : '#0284C7',
                              },
                            ]}
                          />
                        </View>
                      </View>

                      {/* HLB Field Stats Row */}
                      <View style={styles.hlbStatsRow}>
                        <Text style={[styles.hlbStatItem, themeStyles.subtext]}>
                          {t('remaining')}: <Text style={{ color: '#EA580C', fontWeight: 'bold' }}>{hlbRemaining}</Text>
                        </Text>
                        <Text style={[styles.hlbStatItem, themeStyles.subtext]}>
                          {t('locked')}: <Text style={{ color: '#DC2626', fontWeight: 'bold' }}>{hlbLocked}</Text>
                        </Text>
                        <Text style={[styles.hlbStatItem, themeStyles.subtext]}>
                          {t('revisit_count')}: <Text style={[themeStyles.text, { fontWeight: 'bold' }]}>{hlbRevisits}</Text>
                        </Text>
                      </View>

                      {/* GPS & Sync Indicator */}
                      <View style={styles.hlbMetaRow}>
                        <Text style={[styles.hlbMetaText, themeStyles.subtext]}>
                          🌐 {t('gps_coverage')}: {hlbGpsCoverage != null ? `${hlbGpsCoverage.toFixed(0)}%` : '0%'}
                        </Text>
                        <Text style={[styles.hlbMetaText, themeStyles.subtext]}>
                          🔄 {t('last_sync')}: {lastSync ? new Date(lastSync).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : t('never_synced')}
                        </Text>
                      </View>

                      {/* Enumerator Details */}
                      <View style={styles.enumeratorInfoRow}>
                        <Text style={[styles.enumLabel, themeStyles.subtext]}>
                          {t('role_enumerator')}:
                        </Text>
                        {isAssigned && assignedEnum?.enumerator_name ? (
                          <Text style={[styles.enumNameText, themeStyles.text]} numberOfLines={1}>
                            {assignedEnum.enumerator_name} (@{assignedEnum.enumerator_username})
                          </Text>
                        ) : (
                          <Text style={styles.enumUnassignedText}>
                            {t('no_enumerator_assigned')}
                          </Text>
                        )}
                      </View>
                    </View>
                  </TouchableOpacity>

                  {/* Action Buttons: Assign / Change Enumerator & View Details */}
                  <View style={styles.hlbActionBtnRow}>
                    <TouchableOpacity
                      style={styles.detailLinkBtn}
                      onPress={() => handleOpenDetailModal(hlb, hlbProg)}
                      testID={`view-hlb-detail-btn-${hlb.block_code}`}
                    >
                      <Text style={styles.detailLinkText}>📋 {t('view_details')}</Text>
                    </TouchableOpacity>

                    <PrimaryButton
                      title={isAssigned ? t('change_enumerator') : t('assign_enumerator')}
                      onPress={() => handleOpenAssignModal(hlb)}
                      style={[
                        styles.assignActionBtn,
                        isAssigned ? styles.changeBtn : styles.assignBtn,
                      ]}
                      testID={`assign-btn-${hlb.block_code}`}
                    />
                  </View>
                </View>
              );
            })}
          </Card>
        </ScrollView>
      )}

      {/* Enumerator Assignment Modal */}
      <EnumeratorAssignmentModal
        visible={assignmentModalVisible}
        hlb={targetHlbForModal}
        layoutId={layoutId || ''}
        layoutName={layoutDisplayName}
        onClose={() => setAssignmentModalVisible(false)}
        onSuccess={handleAssignmentSuccess}
      />

      {/* Detailed HLB Progress & Boundary Alerts Modal */}
      <SupervisorHlbDetailModal
        visible={detailModalVisible}
        hlb={selectedHlbProgress}
        onClose={() => setDetailModalVisible(false)}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 16,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 14,
  },
  layoutNameText: {
    fontSize: 18,
    fontWeight: '700',
  },
  layoutIdText: {
    fontSize: 13,
    marginTop: 2,
  },
  metricsGrid: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 6,
  },
  metricBox: {
    flex: 1,
    padding: 12,
    borderRadius: 10,
    alignItems: 'center',
    borderWidth: 1,
  },
  metricVal: {
    fontSize: 16,
    fontWeight: '800',
    textAlign: 'center',
  },
  metricLbl: {
    fontSize: 11,
    marginTop: 3,
    textAlign: 'center',
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  progressRatioHeader: {
    fontSize: 12,
    marginTop: 2,
  },
  progressBigPct: {
    fontSize: 22,
    fontWeight: '800',
  },
  progressBarTrack: {
    height: 10,
    borderRadius: 5,
    overflow: 'hidden',
    marginTop: 8,
    marginBottom: 12,
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 5,
  },
  progressMetricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 8,
  },
  progressMiniBox: {
    flex: 1,
    padding: 8,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  pMiniVal: {
    fontSize: 15,
    fontWeight: '800',
  },
  pMiniLbl: {
    fontSize: 10,
    fontWeight: '600',
    marginTop: 2,
    textAlign: 'center',
  },
  summaryBannerCard: {
    padding: 16,
    borderWidth: 1.5,
  },
  summaryHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  summaryTitle: {
    fontSize: 16,
    fontWeight: '800',
  },
  summarySubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  summaryStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 14,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.15)',
  },
  summaryStatItem: {
    alignItems: 'center',
  },
  summaryStatVal: {
    fontSize: 18,
    fontWeight: '800',
  },
  summaryStatLbl: {
    fontSize: 11,
    marginTop: 2,
  },
  incompleteWarningBox: {
    marginTop: 12,
    padding: 8,
    backgroundColor: '#FFEDD5',
    borderRadius: 6,
  },
  incompleteWarningText: {
    fontSize: 12,
    color: '#C2410C',
    fontWeight: '700',
    textAlign: 'center',
  },
  mapCard: {
    padding: 14,
  },
  mapTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 10,
  },
  mapSubtitle: {
    fontSize: 12,
  },
  mapWrapper: {
    height: 280,
    borderRadius: 12,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(56, 189, 248, 0.3)',
  },
  map: {
    flex: 1,
  },
  hlbListHeaderRow: {
    marginBottom: 12,
  },
  hlbCardWrapper: {
    borderRadius: 12,
    borderWidth: 1,
    marginBottom: 12,
    overflow: 'hidden',
  },
  hlbCardTop: {
    flexDirection: 'row',
    padding: 14,
  },
  colorIndicator: {
    width: 6,
    borderRadius: 3,
    marginRight: 12,
  },
  hlbItemInfo: {
    flex: 1,
  },
  hlbTitleRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  hlbCodeText: {
    fontSize: 16,
    fontWeight: '800',
  },
  hlbBadgeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  alertBadgeBox: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    borderWidth: 1,
  },
  alertBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#C2410C',
  },
  hlbProgressBarWrap: {
    marginTop: 8,
    marginBottom: 6,
  },
  hlbProgressHead: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 3,
  },
  hlbProgressPct: {
    fontSize: 12,
    fontWeight: '700',
  },
  hlbHousesRatio: {
    fontSize: 11,
  },
  hlbProgressTrack: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  hlbProgressFill: {
    height: '100%',
    borderRadius: 3,
  },
  hlbStatsRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 4,
  },
  hlbStatItem: {
    fontSize: 11,
  },
  hlbMetaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 6,
    paddingTop: 4,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(150, 150, 150, 0.2)',
  },
  hlbMetaText: {
    fontSize: 11,
  },
  enumeratorInfoRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 6,
    gap: 6,
  },
  enumLabel: {
    fontSize: 12,
  },
  enumNameText: {
    fontSize: 13,
    fontWeight: '700',
    flex: 1,
  },
  enumUnassignedText: {
    fontSize: 12,
    color: '#EA580C',
    fontWeight: '700',
  },
  hlbActionBtnRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 14,
    paddingBottom: 12,
    paddingTop: 4,
  },
  detailLinkBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    backgroundColor: 'rgba(2, 132, 199, 0.1)',
  },
  detailLinkText: {
    color: '#0284C7',
    fontSize: 12,
    fontWeight: '700',
  },
  assignActionBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    minWidth: 140,
  },
  assignBtn: {
    backgroundColor: '#0284C7',
  },
  changeBtn: {
    backgroundColor: '#475569',
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  errorContainer: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  goBackBtn: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#0284C7',
  },
  goBackBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
});
