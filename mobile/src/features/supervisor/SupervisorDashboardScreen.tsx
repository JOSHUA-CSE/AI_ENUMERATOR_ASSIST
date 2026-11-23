import React, { useState, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  useColorScheme,
} from 'react-native';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import {
  ScreenContainer,
  AppHeader,
  Card,
  PrimaryButton,
  SecondaryButton,
  StatusBadge,
} from '../../components';
import { useAuthStore } from '../../core/authStore';
import { useTranslation } from '../../core/localization';
import {
  supervisorService,
  SupervisorLayoutSummary,
  SupervisorOverallProgressResponse,
  SupervisorLayoutProgress,
} from '../../core/supervisorService';
import type { SupervisorNavigationProp } from '../../navigation/navigationTypes';

// In-memory cache for offline/stale data fallback
let cachedProgressData: SupervisorOverallProgressResponse | null = null;
let cachedLayoutsList: SupervisorLayoutSummary[] = [];

export function resetSupervisorDashboardCacheForTesting() {
  cachedProgressData = null;
  cachedLayoutsList = [];
}

export function SupervisorDashboardScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<SupervisorNavigationProp>();
  const { user, logout } = useAuthStore();
  const { t } = useTranslation();

  const [layouts, setLayouts] = useState<SupervisorLayoutSummary[]>(cachedLayoutsList);
  const [progressData, setProgressData] = useState<SupervisorOverallProgressResponse | null>(
    cachedProgressData
  );
  const [loading, setLoading] = useState(!cachedProgressData && cachedLayoutsList.length === 0);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(
    cachedProgressData?.last_updated || null
  );
  const [loggingOut, setLoggingOut] = useState(false);

  const fetchDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else if (!cachedProgressData && cachedLayoutsList.length === 0) {
      setLoading(true);
    }
    setErrorMessage(null);

    try {
      const [layoutsRes, progressRes] = await Promise.all([
        supervisorService.getMyAssignedLayouts(),
        supervisorService.getMyLayoutsProgress().catch(() => null),
      ]);

      const items = layoutsRes?.items || [];
      setLayouts(items);
      if (progressRes) {
        setProgressData(progressRes);
        setLastUpdated(progressRes.last_updated || new Date().toISOString());
      }
      setIsOffline(false);

      // Cache locally
      cachedLayoutsList = items;
      if (progressRes) {
        cachedProgressData = progressRes;
      }
    } catch (err: any) {
      // Check if we have cached data to show offline
      if (cachedProgressData || cachedLayoutsList.length > 0) {
        setIsOffline(true);
        if (cachedProgressData) {
          setProgressData(cachedProgressData);
          setLastUpdated(cachedProgressData.last_updated);
        }
        if (cachedLayoutsList.length > 0) {
          setLayouts(cachedLayoutsList);
        }
      } else {
        const msg =
          err?.response?.data?.detail || err?.message || 'Failed to load supervisor dashboard';
        setErrorMessage(typeof msg === 'string' ? msg : JSON.stringify(msg));
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      fetchDashboardData();
    }, [fetchDashboardData])
  );

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  };

  // Safe metrics calculations
  const totalAssignedLayouts = progressData?.total_layouts ?? layouts.length;
  const overallTotalHouses = progressData?.overall_total_houses ?? 0;
  const overallCompletedHouses = progressData?.overall_completed_houses ?? 0;
  const overallRemainingHouses = progressData?.overall_remaining_houses ?? 0;
  const overallLockedHouses = progressData?.overall_locked_houses ?? 0;
  const overallRevisits = progressData?.overall_revisit_count ?? 0;
  const overallProgressPct =
    progressData?.overall_progress_percentage != null
      ? progressData.overall_progress_percentage
      : overallTotalHouses > 0
      ? (overallCompletedHouses / overallTotalHouses) * 100
      : 0.0;

  // Map progress by layout_id for fast lookup
  const layoutProgressMap = new Map<string, SupervisorLayoutProgress>();
  if (progressData?.layouts) {
    for (const lp of progressData.layouts) {
      layoutProgressMap.set(lp.layout_id, lp);
    }
  }

  const themeStyles = {
    text: { color: isDarkMode ? '#FFFFFF' : '#333333' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#666666' },
    metricBox: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F0F4F8',
      borderColor: isDarkMode ? '#444444' : '#D0DBE5',
    },
    metricValue: { color: isDarkMode ? '#FFB74D' : '#F57C00' },
    cardBorder: {
      borderColor: isDarkMode ? '#333333' : '#E0E0E0',
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
    },
    detailLabel: { color: isDarkMode ? '#9E9E9E' : '#757575' },
    detailValue: { color: isDarkMode ? '#E0E0E0' : '#212121' },
    emptyBox: {
      backgroundColor: isDarkMode ? '#23272A' : '#F8F9FA',
      borderColor: isDarkMode ? '#3D4144' : '#E9ECEF',
    },
    offlineBanner: {
      backgroundColor: isDarkMode ? '#3F2C1D' : '#FEF3C7',
      borderColor: isDarkMode ? '#92400E' : '#F59E0B',
    },
    offlineText: {
      color: isDarkMode ? '#FCD34D' : '#92400E',
    },
    progressTrack: {
      backgroundColor: isDarkMode ? '#333333' : '#E2E8F0',
    },
    hlbMiniCard: {
      backgroundColor: isDarkMode ? '#252B3B' : '#F8FAFC',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
  };

  return (
    <ScreenContainer
      scrollable
      testID="supervisor-dashboard-screen"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => fetchDashboardData(true)}
          colors={['#1976D2']}
        />
      }
    >
      <AppHeader
        roleType="SUPERVISOR"
        roleLabel={t('role_supervisor')}
        userName={user?.name}
      />

      <View style={styles.content}>
        {/* Offline / Stale Data Banner */}
        {isOffline && (
          <View
            style={[styles.offlineBanner, themeStyles.offlineBanner]}
            testID="supervisor-offline-banner"
          >
            <Text style={[styles.offlineBannerText, themeStyles.offlineText]}>
              ⚠ {t('offline_notice')}
            </Text>
          </View>
        )}

        {/* User Profile Card */}
        <Card title={t('user_profile')} testID="user-profile-card">
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('name')}: <Text style={styles.boldText}>{user?.name || 'Supervisor'}</Text>
          </Text>
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('user_id')}: <Text style={styles.boldText}>{user?.username || '-'}</Text>
          </Text>
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('role')}: <Text style={styles.boldText}>{t('role_supervisor')}</Text>
          </Text>
        </Card>

        {/* Overall Fieldwork Progress Card */}
        <Card
          title={`📊 ${t('overall_progress')}`}
          subtitle={
            lastUpdated
              ? `${t('last_updated')}: ${new Date(lastUpdated).toLocaleTimeString()}`
              : undefined
          }
          testID="overall-progress-card"
        >
          {/* Main Progress Bar */}
          <View style={styles.overallProgressSection}>
            <View style={styles.progressHeaderRow}>
              <Text style={[styles.progressPctText, themeStyles.text]}>
                {loading ? '-' : `${overallProgressPct.toFixed(1)}%`}
              </Text>
              <Text style={[styles.progressRatioText, themeStyles.subtext]}>
                {loading ? '-' : `${overallCompletedHouses} / ${overallTotalHouses} ${t('houses_buildings_unit')}`}
              </Text>
            </View>

            <View style={[styles.progressTrack, themeStyles.progressTrack]}>
              <View
                style={[
                  styles.progressFill,
                  {
                    width: `${Math.min(100, Math.max(0, overallProgressPct))}%`,
                    backgroundColor: overallProgressPct >= 100 ? '#16A34A' : '#1976D2',
                  },
                ]}
              />
            </View>
          </View>

          {/* Core Metric Grid */}
          <View style={styles.metricsGrid} testID="layouts-summary-card">
            <View style={[styles.metricItem, themeStyles.metricBox]}>
              <Text style={[styles.metricNumber, { color: '#1976D2' }]}>
                {loading ? '-' : totalAssignedLayouts}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('assigned_layouts')}
              </Text>
            </View>
            <View style={[styles.metricItem, themeStyles.metricBox]}>
              <Text style={[styles.metricNumber, { color: '#16A34A' }]}>
                {loading ? '-' : overallCompletedHouses}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('completed')}
              </Text>
            </View>
            <View style={[styles.metricItem, themeStyles.metricBox]}>
              <Text style={[styles.metricNumber, { color: '#F57C00' }]}>
                {loading ? '-' : overallRemainingHouses}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('remaining')}
              </Text>
            </View>
            <View style={[styles.metricItem, themeStyles.metricBox]}>
              <Text style={[styles.metricNumber, { color: '#DC2626' }]}>
                {loading ? '-' : overallLockedHouses}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('locked')}
              </Text>
            </View>
          </View>

          {/* Secondary Metric Details */}
          <View style={styles.secondaryStatsRow}>
            <View style={styles.statPill}>
              <Text style={[styles.statLabel, themeStyles.detailLabel]}>
                {t('revisit_count')}:
              </Text>
              <Text style={[styles.statVal, themeStyles.detailValue]}>
                {loading ? '-' : overallRevisits}
              </Text>
            </View>
            <TouchableOpacity
              style={styles.refreshIconBtn}
              onPress={() => fetchDashboardData(true)}
              testID="refresh-dashboard-btn"
            >
              <Text style={styles.refreshIconText}>🔄 {t('refresh')}</Text>
            </TouchableOpacity>
          </View>
        </Card>

        {/* Verification & Change Requests Action Card */}
        <Card title="✅ Verification & Change Requests" testID="verification-action-card">
          <Text style={[styles.infoRow, themeStyles.subtext]}>
            Audit enumerator submissions, approve building edits, and submit layout change requests.
          </Text>
          <PrimaryButton
            title="Open Verification Dashboard"
            onPress={() => navigation.navigate('SupervisorVerification')}
            style={{ marginTop: 10 }}
            testID="open-supervisor-verification-btn"
          />
        </Card>

        {/* Assigned Layouts Section */}
        <Card
          title={`📋 ${t('my_layouts')}`}
          subtitle="Layouts assigned by Deputy Tahsildar for supervision"
          testID="assigned-layouts-card"
        >
          {loading ? (
            <View style={styles.centerLoading} testID="dashboard-loading-spinner">
              <ActivityIndicator size="large" color="#1976D2" />
              <Text style={[styles.loadingText, themeStyles.subtext]}>
                {t('loading')}
              </Text>
            </View>
          ) : errorMessage ? (
            <View style={styles.errorContainer} testID="dashboard-error-container">
              <Text style={styles.errorText}>{errorMessage}</Text>
              <SecondaryButton
                title={t('retry')}
                onPress={() => fetchDashboardData()}
                style={styles.retryButton}
                testID="dashboard-retry-btn"
              />
            </View>
          ) : layouts.length === 0 ? (
            <View style={[styles.emptyContainer, themeStyles.emptyBox]} testID="dashboard-empty-container">
              <Text style={styles.emptyIcon}>📂</Text>
              <Text style={[styles.emptyTitle, themeStyles.text]}>
                {t('no_assigned_layouts_supervisor')}
              </Text>
              <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                {t('contact_deputy')}
              </Text>
            </View>
          ) : (
            <View style={styles.layoutsList}>
              {layouts.map((item) => {
                const layoutProgress = layoutProgressMap.get(item.id);
                const lProgressPct =
                  layoutProgress?.progress_percentage != null
                    ? layoutProgress.progress_percentage
                    : item.total_buildings && item.total_buildings > 0
                    ? 0.0
                    : 0.0;
                const lCompleted = layoutProgress?.completed_houses ?? 0;
                const lTotal =
                  layoutProgress?.total_houses ?? item.total_buildings ?? item.actual_building_count ?? 0;
                const lRemaining = layoutProgress?.remaining_houses ?? Math.max(0, lTotal - lCompleted);
                const lLocked = layoutProgress?.locked_houses ?? 0;
                const lRevisits = layoutProgress?.revisit_count ?? 0;
                const hlbs = layoutProgress?.hlbs || [];

                return (
                  <TouchableOpacity
                    key={item.id}
                    style={[styles.layoutCard, themeStyles.cardBorder]}
                    onPress={() =>
                      navigation.navigate('SupervisorLayoutDetail', {
                        layoutId: item.id,
                        layoutName: item.name,
                        areaName: item.name,
                        areaId: item.administrative_area_id || item.area_id,
                      })
                    }
                    activeOpacity={0.7}
                    testID={`layout-card-${item.id}`}
                  >
                    {/* Header */}
                    <View style={styles.layoutHeader}>
                      <View style={styles.layoutTitleCol}>
                        <Text style={[styles.areaNameText, themeStyles.text]} numberOfLines={1}>
                          {item.name}
                        </Text>
                        <Text style={[styles.layoutCodeText, themeStyles.subtext]}>
                          {item.name ? `${item.name} (${item.id.slice(0, 8)})` : item.id}
                        </Text>
                      </View>
                      <StatusBadge status={item.status} />
                    </View>

                    {/* Progress Bar for Layout */}
                    <View style={styles.layoutProgressWrapper}>
                      <View style={styles.layoutProgressHeader}>
                        <Text style={[styles.layoutProgressPctText, { color: lProgressPct >= 100 ? '#16A34A' : '#1976D2' }]}>
                          {lProgressPct.toFixed(1)}% {t('progress')}
                        </Text>
                        <Text style={[styles.layoutHousesRatioText, themeStyles.subtext]}>
                          {lCompleted} / {lTotal} {t('houses_buildings_unit')}
                        </Text>
                      </View>
                      <View style={[styles.miniProgressTrack, themeStyles.progressTrack]}>
                        <View
                          style={[
                            styles.miniProgressFill,
                            {
                              width: `${Math.min(100, Math.max(0, lProgressPct))}%`,
                              backgroundColor: lProgressPct >= 100 ? '#16A34A' : '#1976D2',
                            },
                          ]}
                        />
                      </View>
                    </View>

                    {/* Stats Row */}
                    <View style={styles.layoutStatsRow}>
                      <View style={styles.statPill}>
                        <Text style={[styles.statLabel, themeStyles.detailLabel]}>
                          {t('hlbs_label')}:
                        </Text>
                        <Text style={[styles.statVal, themeStyles.detailValue]}>
                          {item.hlb_count || layoutProgress?.total_hlbs || 0}
                        </Text>
                      </View>
                      <View style={styles.statPill}>
                        <Text style={[styles.statLabel, themeStyles.detailLabel]}>
                          {t('remaining')}:
                        </Text>
                        <Text style={[styles.statVal, { color: '#F57C00' }]}>
                          {lRemaining}
                        </Text>
                      </View>
                      <View style={styles.statPill}>
                        <Text style={[styles.statLabel, themeStyles.detailLabel]}>
                          {t('locked')}:
                        </Text>
                        <Text style={[styles.statVal, { color: '#DC2626' }]}>
                          {lLocked}
                        </Text>
                      </View>
                      <View style={styles.statPill}>
                        <Text style={[styles.statLabel, themeStyles.detailLabel]}>
                          {t('revisit_count')}:
                        </Text>
                        <Text style={[styles.statVal, themeStyles.detailValue]}>
                          {lRevisits}
                        </Text>
                      </View>
                    </View>

                    {/* Quick HLB Breakdown List if available */}
                    {hlbs.length > 0 && (
                      <View style={styles.hlbQuickList}>
                        <Text style={[styles.hlbQuickListTitle, themeStyles.subtext]}>
                          {t('block_progress')}:
                        </Text>
                        {hlbs.map((hlb) => {
                          const hPct = hlb.progress_percentage != null ? hlb.progress_percentage : 0.0;
                          const enumName = hlb.enumerator?.name || t('no_enumerator_assigned');
                          const alertCount = hlb.boundary_alert_count || 0;
                          return (
                            <View
                              key={hlb.hlb_id}
                              style={[styles.hlbMiniRow, themeStyles.hlbMiniCard]}
                              testID={`hlb-quick-row-${hlb.block_code}`}
                            >
                              <View style={{ flex: 1 }}>
                                <Text style={[styles.hlbMiniCode, themeStyles.text]}>
                                  {hlb.block_code}
                                </Text>
                                <Text style={[styles.hlbMiniEnum, themeStyles.subtext]} numberOfLines={1}>
                                  👤 {enumName}
                                </Text>
                              </View>
                              <View style={styles.hlbMiniRight}>
                                <Text
                                  style={[
                                    styles.hlbMiniPct,
                                    { color: hPct >= 100 ? '#16A34A' : '#0284C7' },
                                  ]}
                                >
                                  {hPct.toFixed(1)}%
                                </Text>
                                {alertCount > 0 && (
                                  <Text style={styles.hlbAlertTag}>
                                    ⚠ {alertCount}
                                  </Text>
                                )}
                              </View>
                            </View>
                          );
                        })}
                      </View>
                    )}

                    <View style={styles.openDetailRow}>
                      <Text style={styles.openDetailText}>View Layout & Map →</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        </Card>

        {/* Logout Button */}
        <SecondaryButton
          title={t('logout')}
          onPress={handleLogout}
          loading={loggingOut}
          variant="neutral"
          style={styles.logoutButton}
          testID="logout-button"
        />
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    paddingVertical: 12,
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
  infoRow: {
    fontSize: 15,
    marginBottom: 6,
  },
  boldText: {
    fontWeight: 'bold',
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
    fontSize: 24,
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
    marginBottom: 8,
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
  secondaryStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 4,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#E0E0E0',
  },
  refreshIconBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  refreshIconText: {
    color: '#1976D2',
    fontSize: 12,
    fontWeight: '700',
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
  errorText: {
    color: '#D32F2F',
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 12,
  },
  retryButton: {
    minWidth: 120,
  },
  emptyContainer: {
    borderWidth: 1,
    borderRadius: 8,
    borderStyle: 'dashed',
    padding: 24,
    alignItems: 'center',
    marginVertical: 8,
  },
  emptyIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 16,
    fontWeight: '600',
    textAlign: 'center',
    marginBottom: 4,
  },
  emptySubtitle: {
    fontSize: 13,
    textAlign: 'center',
  },
  layoutsList: {
    marginTop: 4,
  },
  layoutCard: {
    borderWidth: 1,
    borderRadius: 10,
    padding: 14,
    marginBottom: 12,
    elevation: 1,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.1,
    shadowRadius: 2,
  },
  layoutHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  layoutTitleCol: {
    flex: 1,
    marginRight: 8,
  },
  areaNameText: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  layoutCodeText: {
    fontSize: 12,
  },
  layoutProgressWrapper: {
    marginVertical: 8,
  },
  layoutProgressHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  layoutProgressPctText: {
    fontSize: 13,
    fontWeight: '700',
  },
  layoutHousesRatioText: {
    fontSize: 12,
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
  layoutStatsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    marginTop: 6,
    marginBottom: 8,
    gap: 12,
  },
  statPill: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statLabel: {
    fontSize: 12,
    marginRight: 4,
  },
  statVal: {
    fontSize: 12,
    fontWeight: '700',
  },
  hlbQuickList: {
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#E0E0E0',
  },
  hlbQuickListTitle: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  hlbMiniRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 8,
    borderRadius: 6,
    borderWidth: 1,
    marginBottom: 4,
  },
  hlbMiniCode: {
    fontSize: 13,
    fontWeight: '700',
  },
  hlbMiniEnum: {
    fontSize: 11,
    marginTop: 1,
  },
  hlbMiniRight: {
    alignItems: 'flex-end',
  },
  hlbMiniPct: {
    fontSize: 13,
    fontWeight: '800',
  },
  hlbAlertTag: {
    fontSize: 10,
    fontWeight: '700',
    color: '#EA580C',
    marginTop: 1,
  },
  openDetailRow: {
    marginTop: 8,
    alignItems: 'flex-end',
  },
  openDetailText: {
    color: '#1976D2',
    fontWeight: '600',
    fontSize: 13,
  },
  logoutButton: {
    marginTop: 8,
    marginBottom: 24,
  },
});
