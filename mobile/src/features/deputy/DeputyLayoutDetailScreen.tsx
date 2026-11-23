import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  useColorScheme,
  ActivityIndicator,
  RefreshControl,
  BackHandler,
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
  SecondaryButton,
} from '../../components';
import { extractErrorMessage } from '../../core/apiClient';
import { AreaBoundaryResponse, areaService } from '../../core/areaService';
import { layoutService, HlbCandidate } from '../../core/layoutService';
import { parseGeoJSONToRings } from '../../core/geometryUtils';
import {
  deputyService,
  DeputyLayoutDetailProgressResponse,
  DeputyHlbSummary,
} from '../../core/deputyService';
import { useTranslation } from '../../core/localization';
import type {
  DeputyNavigationProp,
  DeputyStackParamList,
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

export function DeputyLayoutDetailScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const route = useRoute<RouteProp<DeputyStackParamList, 'DeputyLayoutDetail'>>();
  const { t } = useTranslation();

  const layoutId = route.params?.layoutId;
  const passedLayoutName = route.params?.layoutName;
  const passedAreaName = route.params?.areaName;
  const passedAreaId = route.params?.areaId;

  const [layoutProgress, setLayoutProgress] =
    useState<DeputyLayoutDetailProgressResponse | null>(null);
  const [hlbCandidates, setHlbCandidates] = useState<HlbCandidate[]>([]);
  const [boundaryData, setBoundaryData] = useState<AreaBoundaryResponse | null>(null);
  const [selectedHlbId, setSelectedHlbId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);

  const mapRef = useRef<HlbSpatialMapRef>(null);

  const loadData = useCallback(
    async (isRefresh = false) => {
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
        const [progressRes, hlbsRes] = await Promise.all([
          deputyService.getLayoutProgress(layoutId),
          layoutService.getLayoutHlbs(layoutId).catch(() => []),
        ]);

        setLayoutProgress(progressRes);
        const hlbList = Array.isArray(hlbsRes) ? hlbsRes : ((hlbsRes as any)?.items || []);
        setHlbCandidates(hlbList);
        setIsOffline(false);

        if (hlbList.length > 0) {
          setSelectedHlbId((prev) => prev || hlbList[0].id);
        }

        // Fetch area boundary for map background
        const areaIdToUse = progressRes.area_id || passedAreaId;
        if (areaIdToUse) {
          try {
            const bData = await areaService.getAreaBoundary(areaIdToUse);
            setBoundaryData(bData);
          } catch {
            // Non-critical
          }
        }
      } catch (err: any) {
        setIsOffline(true);
        const msg = extractErrorMessage(err) || 'Unable to load progress';
        setError(msg);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [layoutId, passedAreaId]
  );

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    const backAction = () => {
      navigation.goBack();
      return true;
    };
    const backHandler = BackHandler.addEventListener('hardwareBackPress', backAction);
    return () => backHandler.remove();
  }, [navigation]);

  // Convert area boundary polygon to coordinate rings
  const boundaryRings = useMemo(() => {
    if (!boundaryData?.boundary) return [];
    return parseGeoJSONToRings(boundaryData.boundary);
  }, [boundaryData]);

  // Map candidate items for HlbSpatialMap
  const mapItems = useMemo(() => {
    return hlbCandidates.map((c, index) => {
      const palette = HLB_PALETTE[index % HLB_PALETTE.length];
      return {
        id: c.id,
        block_code: c.block_code,
        boundary: c.boundary,
        building_count: c.actual_building_count,
        target_building_count: c.target_building_count,
        fillColor: palette.fill,
        strokeColor: palette.stroke,
      };
    });
  }, [hlbCandidates]);

  const themeStyles = {
    text: { color: isDarkMode ? '#FFFFFF' : '#333333' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#666666' },
    metricBox: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F0F4F8',
      borderColor: isDarkMode ? '#444444' : '#D0DBE5',
    },
    cardBorder: {
      borderColor: isDarkMode ? '#333333' : '#E0E0E0',
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
    },
    progressTrack: {
      backgroundColor: isDarkMode ? '#333333' : '#E2E8F0',
    },
    hlbCard: {
      backgroundColor: isDarkMode ? '#23272A' : '#F8FAFC',
      borderColor: isDarkMode ? '#3D4144' : '#E2E8F0',
    },
    offlineBanner: {
      backgroundColor: isDarkMode ? '#3F2C1D' : '#FEF3C7',
      borderColor: isDarkMode ? '#92400E' : '#F59E0B',
    },
    offlineText: {
      color: isDarkMode ? '#FCD34D' : '#92400E',
    },
  };

  const layoutDisplayName =
    layoutProgress?.layout_name || passedLayoutName || 'Layout Progress';
  const villageDisplayName =
    layoutProgress?.village_name || passedAreaName || layoutDisplayName;

  const totalHlbs = layoutProgress?.total_hlbs ?? 0;
  const activeHlbs = layoutProgress?.active_hlbs ?? 0;
  const completedHlbs = layoutProgress?.completed_hlbs ?? 0;
  const remainingHlbs = layoutProgress?.remaining_hlbs ?? 0;

  const totalHouses = layoutProgress?.total_houses ?? 0;
  const completedHouses = layoutProgress?.completed_houses ?? 0;
  const remainingHouses = layoutProgress?.remaining_houses ?? 0;
  const lockedHouses = layoutProgress?.locked_houses ?? 0;
  const revisitCount = layoutProgress?.revisit_count ?? 0;
  const overallProgressPct = layoutProgress?.overall_progress_percentage ?? 0.0;

  const supervisor = layoutProgress?.supervisor;
  const supervisorName = supervisor?.is_assigned && supervisor?.name
    ? supervisor.name
    : t('no_supervisor_assigned');

  return (
    <ScreenContainer
      scrollable
      testID="deputy-layout-detail-screen"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => loadData(true)}
          colors={['#0066CC']}
        />
      }
    >
      <AppHeader
        roleType="DEPUTY_TAHSILDAR"
        roleLabel={t('role_deputy')}
        userName="Deputy Tahsildar"
        showBack
        onBack={() => navigation.goBack()}
      />

      <View style={styles.content}>
        {/* Navigation Breadcrumb / Back Row */}
        <TouchableOpacity
          style={styles.backButton}
          onPress={() => navigation.goBack()}
          testID="layout-detail-back-button"
        >
          <Text style={styles.backButtonText}>← {t('back')}</Text>
        </TouchableOpacity>

        {/* Offline Banner */}
        {isOffline && (
          <View
            style={[styles.offlineBanner, themeStyles.offlineBanner]}
            testID="deputy-detail-offline-banner"
          >
            <Text style={[styles.offlineBannerText, themeStyles.offlineText]}>
              ⚠ {t('offline_stale_data')}
            </Text>
          </View>
        )}

        {loading ? (
          <View style={styles.centerLoading} testID="layout-detail-loading">
            <ActivityIndicator size="large" color="#0066CC" />
            <Text style={[styles.loadingText, themeStyles.subtext]}>
              {t('loading_progress')}
            </Text>
          </View>
        ) : error && !layoutProgress ? (
          <View style={styles.errorContainer} testID="layout-detail-error">
            <ErrorMessage message={error} />
            <SecondaryButton
              title={t('retry')}
              onPress={() => loadData()}
              style={styles.retryButton}
              testID="layout-detail-retry-button"
            />
          </View>
        ) : (
          <>
            {/* 1. Layout Overview Card */}
            <Card title={layoutDisplayName} testID="layout-info-card">
              <View style={styles.layoutHeaderRow}>
                <View style={styles.layoutTitleCol}>
                  <Text style={[styles.villageNameText, themeStyles.text]}>
                    📍 {villageDisplayName}
                  </Text>
                  <Text style={[styles.layoutCodeText, themeStyles.subtext]}>
                    ID: {layoutProgress?.layout_id || layoutId}
                  </Text>
                </View>
                {layoutProgress?.status && (
                  <View style={styles.statusRow}>
                    <Text style={[styles.statusLabel, themeStyles.subtext]}>
                      {t('layout_status')}:
                    </Text>
                    <StatusBadge status={layoutProgress.status} />
                  </View>
                )}
              </View>

              {/* Supervisor Assignment Display */}
              <View style={styles.supervisorRow} testID="supervisor-assignment-info">
                <Text style={[styles.infoLabel, themeStyles.subtext]}>
                  {t('supervisor')}:
                </Text>
                <Text
                  style={[
                    styles.supervisorNameText,
                    supervisor?.is_assigned ? { color: '#0066CC' } : themeStyles.subtext,
                  ]}
                  testID="supervisor-name-text"
                >
                  {supervisorName}
                </Text>
              </View>
            </Card>

            {/* 2. Overall House/Building Progress Card */}
            <Card title={`📊 ${t('house_building_progress')}`} testID="house-progress-card">
              <View style={styles.overallProgressSection}>
                <View style={styles.progressHeaderRow}>
                  <Text style={[styles.progressPctText, themeStyles.text]} testID="overall-pct-text">
                    {overallProgressPct.toFixed(1)}%
                  </Text>
                  <Text style={[styles.progressRatioText, themeStyles.subtext]} testID="house-ratio-text">
                    {completedHouses} / {totalHouses} {t('houses_buildings_unit')}
                  </Text>
                </View>

                {/* Progress Fill Bar */}
                <View style={[styles.progressTrack, themeStyles.progressTrack]}>
                  <View
                    style={[
                      styles.progressFill,
                      {
                        width: `${Math.min(100, Math.max(0, overallProgressPct))}%`,
                        backgroundColor: overallProgressPct >= 100 ? '#16A34A' : '#0066CC',
                      },
                    ]}
                  />
                </View>
              </View>

              {/* Metrics Grid */}
              <View style={styles.metricsGrid}>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-completed-houses">
                  <Text style={[styles.metricNumber, { color: '#16A34A' }]}>
                    {completedHouses}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('completed_houses')}
                  </Text>
                </View>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-remaining-houses">
                  <Text style={[styles.metricNumber, { color: '#F57C00' }]}>
                    {remainingHouses}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('remaining_houses')}
                  </Text>
                </View>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-locked-houses">
                  <Text style={[styles.metricNumber, { color: '#DC2626' }]}>
                    {lockedHouses}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('locked_houses')}
                  </Text>
                </View>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-revisits">
                  <Text style={[styles.metricNumber, themeStyles.text]}>
                    {revisitCount}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('revisit_count')}
                  </Text>
                </View>
              </View>
            </Card>

            {/* 3. HLB Breakdown Totals Card */}
            <Card title={`📑 ${t('hlb_status')}`} testID="hlb-totals-card">
              <View style={styles.metricsGrid}>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="total-hlbs-box">
                  <Text style={[styles.metricNumber, { color: '#0066CC' }]}>
                    {totalHlbs}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('total_hlbs_label')}
                  </Text>
                </View>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="completed-hlbs-box">
                  <Text style={[styles.metricNumber, { color: '#16A34A' }]}>
                    {completedHlbs}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('completed_hlbs')}
                  </Text>
                </View>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="active-hlbs-box">
                  <Text style={[styles.metricNumber, { color: '#0284C7' }]}>
                    {activeHlbs}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('active_hlbs')}
                  </Text>
                </View>
                <View style={[styles.metricItem, themeStyles.metricBox]} testID="remaining-hlbs-box">
                  <Text style={[styles.metricNumber, { color: '#F57C00' }]}>
                    {remainingHlbs}
                  </Text>
                  <Text style={[styles.metricLabel, themeStyles.subtext]}>
                    {t('remaining_hlbs')}
                  </Text>
                </View>
              </View>
            </Card>

            {/* 4. Spatial Map Card with Fullscreen Support */}
            <Card title="🗺 Spatial Overview" testID="layout-map-card">
              <View style={styles.mapWrapper}>
                <HlbSpatialMap
                  ref={mapRef}
                  style={styles.map}
                  boundaryRings={boundaryRings}
                  boundaryStrokeColor="#0066CC"
                  boundaryFillColor="rgba(0, 102, 204, 0.05)"
                  candidateHlbs={mapItems}
                  selectedHlbId={selectedHlbId}
                  onSelectHlb={(item) => setSelectedHlbId(item.id)}
                  fullscreenEnabled={true}
                  fullscreenTitle={`${layoutDisplayName} — Map`}
                  testID="deputy-layout-spatial-map"
                />
              </View>
            </Card>

            {/* 5. HLB Summary List */}
            <Card
              title={`📋 ${t('hlb_summary')}`}
              subtitle={`${totalHlbs} Blocks`}
              testID="hlb-summary-list-card"
            >
              {layoutProgress?.hlbs && layoutProgress.hlbs.length > 0 ? (
                <View style={styles.hlbList}>
                  {layoutProgress.hlbs.map((hlb: DeputyHlbSummary) => {
                    const hlbPct = hlb.progress_percentage != null ? hlb.progress_percentage : 0.0;
                    const isCompleted = hlb.is_completed;
                    const isActive = hlb.is_active;
                    const enumName = hlb.assigned_enumerator_name || t('no_enumerator_assigned');

                    return (
                      <View
                        key={hlb.hlb_id}
                        style={[styles.hlbCard, themeStyles.hlbCard]}
                        testID={`hlb-card-${hlb.block_code}`}
                      >
                        {/* Header */}
                        <View style={styles.hlbHeaderRow}>
                          <View style={{ flex: 1 }}>
                            <Text style={[styles.hlbCodeText, themeStyles.text]}>
                              {hlb.block_code}
                              {hlb.name ? ` • ${hlb.name}` : ''}
                            </Text>
                            <Text style={[styles.hlbEnumText, themeStyles.subtext]}>
                              👤 {enumName}
                            </Text>
                          </View>
                          <View style={styles.hlbTagCol}>
                            {isCompleted ? (
                              <View style={[styles.statusTag, { backgroundColor: '#DCFCE7', borderColor: '#86EFAC' }]}>
                                <Text style={[styles.statusTagText, { color: '#15803D' }]}>
                                  ✓ {t('completed')}
                                </Text>
                              </View>
                            ) : isActive ? (
                              <View style={[styles.statusTag, { backgroundColor: '#E0F2FE', borderColor: '#BAE6FD' }]}>
                                <Text style={[styles.statusTagText, { color: '#0369A1' }]}>
                                  ● {t('active_hlbs')}
                                </Text>
                              </View>
                            ) : (
                              <View style={[styles.statusTag, { backgroundColor: '#FEF3C7', borderColor: '#FDE68A' }]}>
                                <Text style={[styles.statusTagText, { color: '#B45309' }]}>
                                  ⏳ {t('remaining')}
                                </Text>
                              </View>
                            )}
                          </View>
                        </View>

                        {/* Progress Bar */}
                        <View style={styles.hlbProgressWrapper}>
                          <View style={styles.hlbProgressHeader}>
                            <Text style={[styles.hlbPctText, { color: isCompleted ? '#16A34A' : '#0284C7' }]}>
                              {hlbPct.toFixed(1)}%
                            </Text>
                            <Text style={[styles.hlbRatioText, themeStyles.subtext]}>
                              {hlb.completed_houses} / {hlb.total_houses} {t('houses_buildings_unit')}
                            </Text>
                          </View>
                          <View style={[styles.miniProgressTrack, themeStyles.progressTrack]}>
                            <View
                              style={[
                                styles.miniProgressFill,
                                {
                                  width: `${Math.min(100, Math.max(0, hlbPct))}%`,
                                  backgroundColor: isCompleted ? '#16A34A' : '#0284C7',
                                },
                              ]}
                            />
                          </View>
                        </View>

                        {/* Secondary Stats */}
                        <View style={styles.hlbStatsRow}>
                          <Text style={[styles.hlbStatItem, themeStyles.subtext]}>
                            {t('remaining')}: <Text style={{ fontWeight: '700' }}>{hlb.remaining_houses}</Text>
                          </Text>
                          {hlb.locked_houses > 0 && (
                            <Text style={[styles.hlbStatItem, { color: '#DC2626' }]}>
                              {t('locked')}: <Text style={{ fontWeight: '700' }}>{hlb.locked_houses}</Text>
                            </Text>
                          )}
                          {hlb.revisit_count > 0 && (
                            <Text style={[styles.hlbStatItem, themeStyles.subtext]}>
                              {t('revisit_count')}: <Text style={{ fontWeight: '700' }}>{hlb.revisit_count}</Text>
                            </Text>
                          )}
                        </View>
                      </View>
                    );
                  })}
                </View>
              ) : (
                <View style={styles.emptyContainer} testID="no-hlbs-empty">
                  <Text style={[styles.emptyText, themeStyles.subtext]}>
                    {t('no_hlbs_in_layout')}
                  </Text>
                </View>
              )}
            </Card>
          </>
        )}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingVertical: 12,
  },
  backButton: {
    paddingVertical: 6,
    paddingHorizontal: 4,
    marginBottom: 8,
  },
  backButtonText: {
    fontSize: 15,
    color: '#0066CC',
    fontWeight: '700',
  },
  offlineBanner: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 12,
    alignItems: 'center',
  },
  offlineBannerText: {
    fontSize: 13,
    fontWeight: '700',
  },
  layoutHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  layoutTitleCol: {
    flex: 1,
    marginRight: 8,
  },
  villageNameText: {
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 4,
  },
  layoutCodeText: {
    fontSize: 12,
  },
  statusRow: {
    alignItems: 'flex-end',
  },
  statusLabel: {
    fontSize: 10,
    marginBottom: 2,
    fontWeight: '600',
  },
  supervisorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#E0E0E0',
  },
  infoLabel: {
    fontSize: 13,
    fontWeight: '600',
    marginRight: 6,
  },
  supervisorNameText: {
    fontSize: 14,
    fontWeight: '700',
  },
  overallProgressSection: {
    marginBottom: 12,
    marginTop: 4,
  },
  progressHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 6,
  },
  progressPctText: {
    fontSize: 26,
    fontWeight: '800',
  },
  progressRatioText: {
    fontSize: 13,
  },
  progressTrack: {
    height: 10,
    borderRadius: 5,
    overflow: 'hidden',
  },
  progressFill: {
    height: '100%',
    borderRadius: 5,
  },
  metricsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 8,
  },
  metricItem: {
    flex: 1,
    marginHorizontal: 3,
    borderWidth: 1,
    borderRadius: 8,
    padding: 8,
    alignItems: 'center',
  },
  metricNumber: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  metricLabel: {
    fontSize: 10,
    fontWeight: '600',
    textAlign: 'center',
  },
  mapWrapper: {
    height: 260,
    borderRadius: 8,
    overflow: 'hidden',
    marginTop: 4,
  },
  map: {
    flex: 1,
  },
  hlbList: {
    marginTop: 4,
  },
  hlbCard: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 12,
    marginBottom: 10,
  },
  hlbHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  hlbCodeText: {
    fontSize: 15,
    fontWeight: '700',
  },
  hlbEnumText: {
    fontSize: 12,
    marginTop: 2,
  },
  hlbTagCol: {
    alignItems: 'flex-end',
  },
  statusTag: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 12,
    borderWidth: 1,
  },
  statusTagText: {
    fontSize: 11,
    fontWeight: '700',
  },
  hlbProgressWrapper: {
    marginVertical: 6,
  },
  hlbProgressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  hlbPctText: {
    fontSize: 13,
    fontWeight: '700',
  },
  hlbRatioText: {
    fontSize: 11,
  },
  miniProgressTrack: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
  },
  miniProgressFill: {
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
  centerLoading: {
    paddingVertical: 32,
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 8,
    fontSize: 14,
  },
  errorContainer: {
    padding: 16,
    alignItems: 'center',
  },
  retryButton: {
    marginTop: 12,
    minWidth: 120,
  },
  emptyContainer: {
    paddingVertical: 20,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 13,
  },
});
