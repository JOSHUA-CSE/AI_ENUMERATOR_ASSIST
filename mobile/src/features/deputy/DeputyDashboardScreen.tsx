import React, { useState, useEffect, useCallback } from 'react';
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
import { areaService } from '../../core/areaService';
import { layoutService } from '../../core/layoutService';
import {
  deputyService,
  DeputyOverallProgressResponse,
  DeputyLayoutProgressItem,
} from '../../core/deputyService';
import type { DeputyNavigationProp } from '../../navigation/navigationTypes';

// In-memory cache for offline/stale data fallback
let cachedOverallProgress: DeputyOverallProgressResponse | null = null;

export function resetDeputyDashboardCacheForTesting() {
  cachedOverallProgress = null;
}

export function DeputyDashboardScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const { user, logout } = useAuthStore();
  const { t } = useTranslation();

  // Overview Quick Stats (Preserved from Phase 3/4)
  const [stats, setStats] = useState({
    villagesCount: 0,
    layoutsCount: 0,
    awaitingReviewCount: 0,
    approvedLayoutsCount: 0,
  });

  // Phase 14 Live Progress State
  const [progressData, setProgressData] =
    useState<DeputyOverallProgressResponse | null>(cachedOverallProgress);
  const [loading, setLoading] = useState(!cachedOverallProgress);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<string | null>(
    cachedOverallProgress?.last_updated || null
  );
  const [loggingOut, setLoggingOut] = useState(false);

  const fetchDashboardData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else if (!cachedOverallProgress) {
      setLoading(true);
    }
    setErrorMessage(null);

    try {
      const [areasRes, layoutsRes] = await Promise.all([
        areaService.getAreas({ limit: 100 }).catch(() => ({ items: [], total: 0 })),
        layoutService.getLayouts({ limit: 100 }).catch(() => ({ items: [], total: 0 })),
      ]);

      const items = layoutsRes?.items || [];
      const awaitingReview = items.filter(
        (l: any) =>
          l.status === 'IN_REVIEW' ||
          l.status === 'DRAFT' ||
          l.status === 'GENERATED' ||
          l.status === 'REVIEW' ||
          l.status === 'CANDIDATE'
      ).length;
      const approved = items.filter((l) => l.status === 'APPROVED').length;

      setStats({
        villagesCount: areasRes?.total ?? (areasRes?.items ? areasRes.items.length : 0),
        layoutsCount: layoutsRes?.total ?? items.length,
        awaitingReviewCount: awaitingReview,
        approvedLayoutsCount: approved,
      });

      const progressRes = await deputyService.getOverallProgress();

      if (progressRes && Array.isArray(progressRes.layouts)) {
        setProgressData(progressRes);
        setLastUpdated(progressRes.last_updated || new Date().toISOString());
        cachedOverallProgress = progressRes;
      }
      setIsOffline(false);
    } catch (err: any) {
      if (cachedOverallProgress) {
        setIsOffline(true);
        setProgressData(cachedOverallProgress);
        setLastUpdated(cachedOverallProgress.last_updated);
      } else {
        const msg =
          err?.response?.data?.detail || err?.message || 'Unable to load progress';
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

  const layouts: DeputyLayoutProgressItem[] = progressData?.layouts || [];
  const totalLayouts = progressData?.total_layouts ?? layouts.length;
  const totalHlbs = progressData?.total_hlbs ?? 0;
  const completedHlbs = progressData?.completed_hlbs ?? 0;
  const activeHlbs = progressData?.active_hlbs ?? 0;
  const remainingHlbs = progressData?.remaining_hlbs ?? 0;

  const totalHouses = progressData?.total_houses ?? 0;
  const completedHouses = progressData?.completed_houses ?? 0;
  const remainingHouses = progressData?.remaining_houses ?? 0;
  const lockedHouses = progressData?.locked_houses ?? 0;
  const revisitCount = progressData?.revisit_count ?? 0;
  const overallProgressPct = progressData?.overall_progress_percentage ?? 0.0;

  const themeStyles = {
    text: { color: isDarkMode ? '#FFFFFF' : '#333333' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#666666' },
    metricBox: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F0F4F8',
      borderColor: isDarkMode ? '#444444' : '#D0DBE5',
    },
    metricValue: { color: isDarkMode ? '#90CAF9' : '#0066CC' },
    cardBorder: {
      borderColor: isDarkMode ? '#333333' : '#E0E0E0',
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
    },
    progressTrack: {
      backgroundColor: isDarkMode ? '#333333' : '#E2E8F0',
    },
    offlineBanner: {
      backgroundColor: isDarkMode ? '#3F2C1D' : '#FEF3C7',
      borderColor: isDarkMode ? '#92400E' : '#F59E0B',
    },
    offlineText: {
      color: isDarkMode ? '#FCD34D' : '#92400E',
    },
    emptyBox: {
      backgroundColor: isDarkMode ? '#23272A' : '#F8F9FA',
      borderColor: isDarkMode ? '#3D4144' : '#E9ECEF',
    },
  };

  return (
    <ScreenContainer
      scrollable
      testID="deputy-dashboard-screen"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => fetchDashboardData(true)}
          colors={['#0066CC']}
        />
      }
    >
      <AppHeader
        roleType="DEPUTY_TAHSILDAR"
        roleLabel={t('role_deputy')}
        userName={user?.name}
      />

      <View style={styles.content}>
        {/* Offline / Stale Data Banner */}
        {isOffline && (
          <View
            style={[styles.offlineBanner, themeStyles.offlineBanner]}
            testID="deputy-offline-banner"
          >
            <Text style={[styles.offlineBannerText, themeStyles.offlineText]}>
              ⚠ {t('offline_stale_data')}
            </Text>
            {lastUpdated && (
              <Text style={[styles.offlineTimestamp, themeStyles.offlineText]}>
                {t('last_updated')}: {new Date(lastUpdated).toLocaleTimeString()}
              </Text>
            )}
          </View>
        )}

        {/* User Profile Card */}
        <Card title={t('user_profile')} testID="user-profile-card">
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('name')}: <Text style={styles.boldText}>{user?.name || 'Officer'}</Text>
          </Text>
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('user_id')}: <Text style={styles.boldText}>{user?.username || '-'}</Text>
          </Text>
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('role')}: <Text style={styles.boldText}>{t('role_deputy')}</Text>
          </Text>
        </Card>

        {/* Quick Overview Section (Preserved for backward compatibility) */}
        <Card title={t('deputy_overview')} testID="overview-card">
          <View style={styles.overviewGrid}>
            <View style={[styles.overviewItem, themeStyles.metricBox]} testID="overview-villages-box">
              <Text style={[styles.overviewNumber, themeStyles.metricValue]} testID="overview-villages-count">
                {stats.villagesCount}
              </Text>
              <Text style={[styles.overviewLabel, themeStyles.subtext]}>{t('villages_wards')}</Text>
            </View>
            <View style={[styles.overviewItem, themeStyles.metricBox]} testID="overview-layouts-box">
              <Text style={[styles.overviewNumber, themeStyles.metricValue]} testID="overview-layouts-count">
                {stats.layoutsCount}
              </Text>
              <Text style={[styles.overviewLabel, themeStyles.subtext]}>{t('layouts')}</Text>
            </View>
            <View style={[styles.overviewItem, themeStyles.metricBox]} testID="overview-awaiting-box">
              <Text style={[styles.overviewNumber, { color: '#F57C00' }]} testID="overview-awaiting-count">
                {stats.awaitingReviewCount}
              </Text>
              <Text style={[styles.overviewLabel, themeStyles.subtext]}>{t('awaiting_review')}</Text>
            </View>
            <View style={[styles.overviewItem, themeStyles.metricBox]} testID="overview-approved-box">
              <Text style={[styles.overviewNumber, { color: '#2E7D32' }]} testID="overview-approved-count">
                {stats.approvedLayoutsCount}
              </Text>
              <Text style={[styles.overviewLabel, themeStyles.subtext]}>{t('approved_layouts')}</Text>
            </View>
          </View>
        </Card>

        {/* Level 1: Overall Progress Monitoring Card */}
        <Card
          title={`📊 ${t('overall_progress')}`}
          subtitle={
            lastUpdated
              ? `${t('last_updated')}: ${new Date(lastUpdated).toLocaleTimeString()}`
              : undefined
          }
          testID="overall-progress-card"
        >
          {/* Main House/Building Progress Bar */}
          <View style={styles.overallProgressSection}>
            <View style={styles.progressHeaderRow}>
              <Text style={[styles.progressPctText, themeStyles.text]} testID="overall-progress-pct">
                {loading ? '-' : `${overallProgressPct.toFixed(1)}%`}
              </Text>
              <Text style={[styles.progressRatioText, themeStyles.subtext]} testID="overall-houses-ratio">
                {loading
                  ? '-'
                  : `${completedHouses} / ${totalHouses} ${t('houses_buildings_unit')}`}
              </Text>
            </View>

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

          {/* HLB Totals Grid */}
          <Text style={[styles.sectionSubtitle, themeStyles.subtext]}>
            {t('hlb_status')}
          </Text>
          <View style={styles.metricsGrid} testID="hlb-metrics-grid">
            <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-total-layouts">
              <Text style={[styles.metricNumber, { color: '#0066CC' }]}>
                {loading ? '-' : totalLayouts}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('layouts')}
              </Text>
            </View>
            <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-total-hlbs">
              <Text style={[styles.metricNumber, { color: '#0066CC' }]}>
                {loading ? '-' : totalHlbs}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('total_hlbs_label')}
              </Text>
            </View>
            <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-completed-hlbs">
              <Text style={[styles.metricNumber, { color: '#16A34A' }]}>
                {loading ? '-' : completedHlbs}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('completed_hlbs')}
              </Text>
            </View>
            <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-active-hlbs">
              <Text style={[styles.metricNumber, { color: '#0284C7' }]}>
                {loading ? '-' : activeHlbs}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('active_hlbs')}
              </Text>
            </View>
            <View style={[styles.metricItem, themeStyles.metricBox]} testID="metric-remaining-hlbs">
              <Text style={[styles.metricNumber, { color: '#F57C00' }]}>
                {loading ? '-' : remainingHlbs}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('remaining_hlbs')}
              </Text>
            </View>
          </View>

          {/* House Stats Row */}
          <View style={styles.secondaryStatsRow}>
            <View style={styles.statPill} testID="pill-locked-houses">
              <Text style={[styles.statLabel, themeStyles.subtext]}>
                {t('locked_houses')}:
              </Text>
              <Text style={[styles.statVal, { color: '#DC2626' }]}>
                {loading ? '-' : lockedHouses}
              </Text>
            </View>
            <View style={styles.statPill} testID="pill-revisits">
              <Text style={[styles.statLabel, themeStyles.subtext]}>
                {t('revisit_count')}:
              </Text>
              <Text style={[styles.statVal, themeStyles.text]}>
                {loading ? '-' : revisitCount}
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

        {/* Level 2: Layouts Progress Cards */}
        <Card
          title={`📑 ${t('layouts')}`}
          subtitle={`${layouts.length} ${t('layouts')}`}
          testID="layouts-progress-card"
        >
          {loading ? (
            <View style={styles.centerLoading} testID="dashboard-loading-spinner">
              <ActivityIndicator size="large" color="#0066CC" />
              <Text style={[styles.loadingText, themeStyles.subtext]}>
                {t('loading_progress')}
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
                {t('no_layouts')}
              </Text>
            </View>
          ) : (
            <View style={styles.layoutsList} testID="layouts-list">
              {layouts.map((item) => {
                const lProgressPct = item.overall_progress_percentage ?? 0.0;
                const supervisor = item.supervisor;
                const hasSupervisor = supervisor?.is_assigned && supervisor?.name;
                const supervisorDisplay = hasSupervisor
                  ? supervisor.name
                  : t('no_supervisor_assigned');

                return (
                  <TouchableOpacity
                    key={item.layout_id}
                    style={[styles.layoutCard, themeStyles.cardBorder]}
                    onPress={() =>
                      navigation.navigate('DeputyLayoutDetail', {
                        layoutId: item.layout_id,
                        layoutName: item.layout_name,
                        areaName: item.village_name || item.layout_name,
                        areaId: item.area_id || undefined,
                      })
                    }
                    activeOpacity={0.7}
                    testID={`layout-card-${item.layout_id}`}
                  >
                    {/* Header */}
                    <View style={styles.layoutHeader}>
                      <View style={styles.layoutTitleCol}>
                        <Text style={[styles.areaNameText, themeStyles.text]} numberOfLines={1}>
                          {item.village_name || item.layout_name}
                        </Text>
                        <Text style={[styles.layoutCodeText, themeStyles.subtext]}>
                          {item.layout_name}
                        </Text>
                      </View>
                      <View style={styles.statusCol}>
                        <Text style={[styles.statusTextLabel, themeStyles.subtext]}>
                          {t('layout_status')}:
                        </Text>
                        <StatusBadge status={item.status} />
                      </View>
                    </View>

                    {/* Supervisor Assignment */}
                    <View style={styles.cardSupervisorRow}>
                      <Text style={[styles.cardSupervisorLabel, themeStyles.subtext]}>
                        {t('supervisor')}:
                      </Text>
                      <Text
                        style={[
                          styles.cardSupervisorValue,
                          hasSupervisor ? { color: '#0066CC' } : themeStyles.subtext,
                        ]}
                      >
                        {supervisorDisplay}
                      </Text>
                    </View>

                    {/* Progress Bar for Layout */}
                    <View style={styles.layoutProgressWrapper}>
                      <View style={styles.layoutProgressHeader}>
                        <Text
                          style={[
                            styles.layoutProgressPctText,
                            { color: lProgressPct >= 100 ? '#16A34A' : '#0066CC' },
                          ]}
                        >
                          {lProgressPct.toFixed(1)}% {t('progress')}
                        </Text>
                        <Text style={[styles.layoutHousesRatioText, themeStyles.subtext]}>
                          {item.completed_houses} / {item.total_houses} {t('houses_buildings_unit')}
                        </Text>
                      </View>
                      <View style={[styles.miniProgressTrack, themeStyles.progressTrack]}>
                        <View
                          style={[
                            styles.miniProgressFill,
                            {
                              width: `${Math.min(100, Math.max(0, lProgressPct))}%`,
                              backgroundColor: lProgressPct >= 100 ? '#16A34A' : '#0066CC',
                            },
                          ]}
                        />
                      </View>
                    </View>

                    {/* HLB Breakdown Row */}
                    <View style={styles.layoutHlbRow}>
                      <View style={styles.hlbStatItem}>
                        <Text style={[styles.hlbStatVal, themeStyles.text]}>{item.total_hlbs}</Text>
                        <Text style={[styles.hlbStatLbl, themeStyles.subtext]}>{t('total_hlbs_label')}</Text>
                      </View>
                      <View style={styles.hlbStatItem}>
                        <Text style={[styles.hlbStatVal, { color: '#16A34A' }]}>{item.completed_hlbs}</Text>
                        <Text style={[styles.hlbStatLbl, themeStyles.subtext]}>{t('completed')}</Text>
                      </View>
                      <View style={styles.hlbStatItem}>
                        <Text style={[styles.hlbStatVal, { color: '#0284C7' }]}>{item.active_hlbs}</Text>
                        <Text style={[styles.hlbStatLbl, themeStyles.subtext]}>{t('active_hlbs')}</Text>
                      </View>
                      <View style={styles.hlbStatItem}>
                        <Text style={[styles.hlbStatVal, { color: '#F57C00' }]}>{item.remaining_hlbs}</Text>
                        <Text style={[styles.hlbStatLbl, themeStyles.subtext]}>{t('remaining')}</Text>
                      </View>
                    </View>

                    <View style={styles.openDetailRow}>
                      <Text style={styles.openDetailText}>{t('view_layout_details')} →</Text>
                    </View>
                  </TouchableOpacity>
                );
              })}
            </View>
          )}
        </Card>

        {/* Existing Navigation Shortcuts */}
        <Card title={t('dashboard')} testID="sections-card">
          <PrimaryButton
            title={`🗺 ${t('administrative_areas')}`}
            onPress={() => navigation.navigate('AreaList')}
            style={styles.navButton}
            testID="nav-areas-button"
          />

          <PrimaryButton
            title="📝 Supervisor Change Requests"
            onPress={() => navigation.navigate('DeputyChangeRequests')}
            style={styles.navButton}
            testID="nav-change-requests-button"
          />

          <PrimaryButton
            title={`📑 ${t('layouts')}`}
            onPress={() => navigation.navigate('LayoutList')}
            style={styles.navButton}
            testID="nav-layouts-button"
          />

          <PrimaryButton
            title={`👥 ${t('supervisors')}`}
            onPress={() => navigation.navigate('SupervisorsPlaceholder')}
            style={styles.navButton}
            testID="nav-supervisors-button"
          />

          <PrimaryButton
            title={`📊 ${t('progress')}`}
            onPress={() => navigation.navigate('ProgressPlaceholder')}
            style={styles.navButton}
            testID="nav-progress-button"
          />
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
  offlineTimestamp: {
    fontSize: 11,
    marginTop: 2,
  },
  infoRow: {
    fontSize: 15,
    marginBottom: 6,
  },
  boldText: {
    fontWeight: 'bold',
  },
  overviewGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  overviewItem: {
    width: '48%',
    borderWidth: 1,
    borderRadius: 6,
    padding: 12,
    alignItems: 'center',
    marginBottom: 10,
  },
  overviewNumber: {
    fontSize: 22,
    fontWeight: 'bold',
    marginBottom: 4,
  },
  overviewLabel: {
    fontSize: 12,
    fontWeight: '600',
    textAlign: 'center',
  },
  sectionSubtitle: {
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
    marginTop: 8,
    marginBottom: 4,
  },
  overallProgressSection: {
    marginBottom: 8,
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
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    marginTop: 4,
  },
  metricItem: {
    width: '18%',
    borderWidth: 1,
    borderRadius: 6,
    paddingVertical: 8,
    alignItems: 'center',
    marginBottom: 8,
  },
  metricNumber: {
    fontSize: 16,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  metricLabel: {
    fontSize: 9,
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
  refreshIconBtn: {
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  refreshIconText: {
    color: '#0066CC',
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
    fontSize: 15,
    fontWeight: '600',
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
    marginBottom: 6,
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
  statusCol: {
    alignItems: 'flex-end',
  },
  statusTextLabel: {
    fontSize: 10,
    marginBottom: 2,
  },
  cardSupervisorRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginVertical: 4,
  },
  cardSupervisorLabel: {
    fontSize: 12,
    marginRight: 4,
  },
  cardSupervisorValue: {
    fontSize: 13,
    fontWeight: '700',
  },
  layoutProgressWrapper: {
    marginVertical: 6,
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
  layoutHlbRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    paddingVertical: 6,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: '#E0E0E0',
    marginTop: 6,
  },
  hlbStatItem: {
    alignItems: 'center',
  },
  hlbStatVal: {
    fontSize: 13,
    fontWeight: '700',
  },
  hlbStatLbl: {
    fontSize: 10,
    marginTop: 1,
  },
  openDetailRow: {
    marginTop: 8,
    alignItems: 'flex-end',
  },
  openDetailText: {
    color: '#0066CC',
    fontWeight: '600',
    fontSize: 13,
  },
  navButton: {
    marginBottom: 12,
  },
  logoutButton: {
    marginTop: 8,
    marginBottom: 24,
  },
});
