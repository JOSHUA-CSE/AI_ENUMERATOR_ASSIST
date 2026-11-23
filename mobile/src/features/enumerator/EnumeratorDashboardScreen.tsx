import React, { useState, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ActivityIndicator,
  RefreshControl,
  Alert,
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
  enumeratorService,
  EnumeratorAssignedHlbDetail,
} from '../../core/enumeratorService';
import { extractErrorMessage } from '../../core/apiClient';
import { fieldworkService } from '../../core/fieldworkService';
import type { EnumeratorNavigationProp } from '../../navigation/navigationTypes';
import type { FieldworkStats, SyncQueueStats } from '../../core/sqlite/types';

export function EnumeratorDashboardScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<EnumeratorNavigationProp>();
  const { user, logout } = useAuthStore();
  const { t } = useTranslation();

  const [assignedHlbs, setAssignedHlbs] = useState<EnumeratorAssignedHlbDetail[]>([]);
  const [isDownloaded, setIsDownloaded] = useState<boolean>(false);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [fieldworkStats, setFieldworkStats] = useState<FieldworkStats | null>(null);

  // Sync State
  const [syncStats, setSyncStats] = useState<SyncQueueStats>({
    pendingCount: 0,
    syncingCount: 0,
    syncedCount: 0,
    failedCount: 0,
    conflictCount: 0,
    totalCount: 0,
    lastSyncedAt: null,
  });
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [loggingOut, setLoggingOut] = useState(false);

  const fetchMyAssignments = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setErrorMessage(null);

    const enumeratorId = user?.id || 'enumerator-local';
    let offlineHlbs: any[] = [];

    // 1. Fetch Sync Queue Stats from SQLite (Safe)
    try {
      const queueStats = fieldworkService.getSyncStats();
      setSyncStats(queueStats);
    } catch (err) {
      console.warn('[Dashboard] Could not read sync stats:', err);
    }

    // 2. Check if we have locally downloaded HLBs in SQLite (Offline-First, Safe)
    try {
      offlineHlbs = fieldworkService.getDownloadedHlbs(enumeratorId);
      if (offlineHlbs.length > 0) {
        const local = offlineHlbs[0];
        let boundaryObj = null;
        try {
          boundaryObj = JSON.parse(local.boundary_geojson);
        } catch {
          boundaryObj = null;
        }

        setAssignedHlbs([
          {
            id: local.id,
            layout_id: local.layout_id,
            layout_name: local.layout_name,
            area_name: local.area_name,
            block_code: local.block_code,
            name: local.name || local.block_code,
            status: local.status,
            target_building_count: local.target_building_count,
            actual_building_count: local.actual_building_count,
            boundary: boundaryObj,
          },
        ]);
        setIsDownloaded(true);
        const stats = fieldworkService.getFieldworkStats(local.id);
        setFieldworkStats(stats);
      }
    } catch (err) {
      console.warn('[Dashboard] Could not read offline HLBs:', err);
    }

    // 3. Fetch fresh assignment from server if online
    try {
      const data = await enumeratorService.getMyAssignedHlbs();
      if (data && data.length > 0) {
        setAssignedHlbs(data);
        const downloaded = fieldworkService.isHlbDownloaded(data[0].id, enumeratorId);
        setIsDownloaded(downloaded);
        const stats = fieldworkService.getFieldworkStats(data[0].id);
        setFieldworkStats(stats);
      } else if (offlineHlbs.length === 0) {
        setAssignedHlbs([]);
      }
    } catch (netErr: any) {
      // If offline and we already have local HLB, suppress error
      if (offlineHlbs.length === 0) {
        const msg = extractErrorMessage(netErr);
        setErrorMessage(msg);
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [user?.id]);

  useFocusEffect(
    useCallback(() => {
      fetchMyAssignments();
    }, [fetchMyAssignments])
  );

  const handleDownload = async (hlbId: string) => {
    setDownloading(true);
    try {
      const enumeratorId = user?.id || 'enumerator-local';
      const res = await fieldworkService.downloadHlbForOffline(hlbId, enumeratorId);
      if (res.success) {
        setIsDownloaded(true);
        const stats = fieldworkService.getFieldworkStats(hlbId);
        setFieldworkStats(stats);
        Alert.alert(
          t('download_complete'),
          `${t('available_offline')} (${res.totalBuildings} ${t('detected_buildings').toLowerCase()})`
        );
      } else {
        Alert.alert(t('download_failed'), res.error || 'Failed to download assigned HLB.');
      }
    } catch (err: any) {
      Alert.alert(t('download_failed'), err?.message || 'Download error.');
    } finally {
      setDownloading(false);
    }
  };

  const handleSyncNow = async () => {
    setIsSyncing(true);
    try {
      const res = await fieldworkService.syncNow();
      const updatedStats = fieldworkService.getSyncStats();
      setSyncStats(updatedStats);

      if (res.success) {
        if (res.processedCount > 0) {
          Alert.alert(
            t('synced'),
            `${t('sync_success_notice')} (${res.successCount} / ${res.processedCount})`
          );
        } else {
          Alert.alert(t('synced'), t('all_records_synced'));
        }
      } else {
        Alert.alert(
          t('sync_failed'),
          `${t('sync_failed_notice')}\n${res.error || ''}`
        );
      }
    } catch (err: any) {
      Alert.alert(
        t('sync_failed'),
        `${t('sync_failed_notice')}\n${err?.message || ''}`
      );
    } finally {
      setIsSyncing(false);
    }
  };

  const handleRetryFailed = async () => {
    setIsSyncing(true);
    try {
      const res = await fieldworkService.retrySync();
      const updatedStats = fieldworkService.getSyncStats();
      setSyncStats(updatedStats);
      if (res.success) {
        Alert.alert(t('synced'), t('sync_success_notice'));
      } else {
        Alert.alert(t('sync_failed'), res.error || t('sync_failed_notice'));
      }
    } finally {
      setIsSyncing(false);
    }
  };

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await logout();
    } finally {
      setLoggingOut(false);
    }
  };

  const primaryHlb = assignedHlbs.length > 0 ? assignedHlbs[0] : null;

  const themeStyles = {
    text: { color: isDarkMode ? '#FFFFFF' : '#333333' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#666666' },
    metricBox: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F0F4F8',
      borderColor: isDarkMode ? '#444444' : '#D0DBE5',
    },
    metricValue: { color: isDarkMode ? '#81C784' : '#2E7D32' },
    cardBorder: {
      borderColor: isDarkMode ? '#333333' : '#E0E0E0',
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
    },
    emptyBox: {
      backgroundColor: isDarkMode ? '#23272A' : '#F8F9FA',
      borderColor: isDarkMode ? '#334155' : '#E9ECEF',
    },
    assignmentCard: {
      backgroundColor: isDarkMode ? '#14291F' : '#F0FDF4',
      borderColor: isDarkMode ? '#166534' : '#86EFAC',
    },
    syncCard: {
      backgroundColor: isDarkMode ? '#0F172A' : '#F8FAFC',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
  };

  return (
    <ScreenContainer
      scrollable
      testID="enumerator-dashboard-screen"
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => fetchMyAssignments(true)}
          colors={['#0284C7']}
        />
      }
    >
      <AppHeader
        roleType="ENUMERATOR"
        roleLabel={t('role_enumerator')}
        userName={user?.name}
      />

      <View style={styles.content}>
        {/* User Profile Card */}
        <Card title={t('user_profile')} testID="user-profile-card">
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('name')}: <Text style={styles.boldText}>{user?.name || 'Enumerator'}</Text>
          </Text>
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('user_id')}: <Text style={styles.boldText}>{user?.username || '-'}</Text>
          </Text>
          <Text style={[styles.infoRow, themeStyles.text]}>
            {t('role')}: <Text style={styles.boldText}>{t('role_enumerator')}</Text>
          </Text>
        </Card>

        {/* Synchronization Card */}
        <Card
          title={t('sync_status_title')}
          testID="enumerator-sync-card"
          style={themeStyles.syncCard}
        >
          <View style={styles.syncHeaderRow}>
            <View>
              <Text style={[styles.syncTitleText, themeStyles.text]}>
                {syncStats.pendingCount > 0
                  ? `${syncStats.pendingCount} ${t('records_pending_sync')}`
                  : t('all_records_synced')}
              </Text>
              <Text style={[styles.syncSubtext, themeStyles.subtext]}>
                {t('last_synced')}:{' '}
                {syncStats.lastSyncedAt
                  ? new Date(syncStats.lastSyncedAt).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                    })
                  : '—'}
              </Text>
            </View>
            <StatusBadge
              type={
                syncStats.failedCount > 0
                  ? 'WARNING'
                  : syncStats.pendingCount > 0
                  ? 'PENDING'
                  : 'COMPLETED'
              }
              label={
                syncStats.failedCount > 0
                  ? t('sync_failed')
                  : syncStats.pendingCount > 0
                  ? t('pending_sync')
                  : t('synced')
              }
            />
          </View>

          <View style={styles.syncMetricsRow}>
            <View style={[styles.syncMetricBox, themeStyles.metricBox]}>
              <Text style={[styles.syncMetricNum, { color: '#0284C7' }]}>
                {syncStats.pendingCount}
              </Text>
              <Text style={[styles.syncMetricLabel, themeStyles.subtext]}>
                {t('pending_sync')}
              </Text>
            </View>
            <View style={[styles.syncMetricBox, themeStyles.metricBox]}>
              <Text style={[styles.syncMetricNum, { color: '#10B981' }]}>
                {syncStats.syncedCount}
              </Text>
              <Text style={[styles.syncMetricLabel, themeStyles.subtext]}>
                {t('synced')}
              </Text>
            </View>
            <View style={[styles.syncMetricBox, themeStyles.metricBox]}>
              <Text style={[styles.syncMetricNum, { color: '#EF4444' }]}>
                {syncStats.failedCount}
              </Text>
              <Text style={[styles.syncMetricLabel, themeStyles.subtext]}>
                {t('sync_failed')}
              </Text>
            </View>
          </View>

          <View style={styles.syncActionsRow}>
            <PrimaryButton
              title={isSyncing ? t('syncing') : t('sync_now')}
              onPress={handleSyncNow}
              disabled={isSyncing}
              loading={isSyncing}
              testID="sync-now-button"
            />
            {syncStats.failedCount > 0 && (
              <SecondaryButton
                title={t('retry_sync')}
                onPress={handleRetryFailed}
                disabled={isSyncing}
                testID="retry-sync-button"
                style={{ marginTop: 8 }}
              />
            )}
          </View>
        </Card>

        {/* Fieldwork Status Card */}
        <Card title={t('fieldwork_status')} testID="fieldwork-status-card">
          <View style={styles.metricsGrid}>
            <View style={[styles.metricItem, themeStyles.metricBox]}>
              <Text style={[styles.metricNumber, { color: '#0284C7' }]}>
                {fieldworkStats?.total_buildings ?? (primaryHlb?.actual_building_count || 0)}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('detected_buildings')}
              </Text>
            </View>

            <View style={[styles.metricItem, themeStyles.metricBox]}>
              <Text style={[styles.metricNumber, { color: '#10B981' }]}>
                {fieldworkStats?.completed_buildings ?? 0}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('visited_buildings')}
              </Text>
            </View>

            <View style={[styles.metricItem, themeStyles.metricBox]}>
              <Text style={[styles.metricNumber, { color: '#F59E0B' }]}>
                {fieldworkStats?.pending_buildings ?? (primaryHlb?.actual_building_count || 0)}
              </Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>
                {t('pending_buildings')}
              </Text>
            </View>
          </View>
        </Card>

        {/* Assigned HLB Card */}
        <Card
          title={t('my_assignment')}
          testID="enumerator-assignment-card"
          style={primaryHlb ? themeStyles.assignmentCard : undefined}
        >
          {loading && !refreshing ? (
            <View style={styles.loadingContainer}>
              <ActivityIndicator size="small" color="#0284C7" />
              <Text style={[styles.loadingText, themeStyles.subtext]}>
                {t('loading')}
              </Text>
            </View>
          ) : errorMessage ? (
            <View style={styles.errorBox}>
              <Text style={styles.errorText}>{errorMessage}</Text>
              <TouchableOpacity
                onPress={() => fetchMyAssignments(true)}
                style={styles.retryBtn}
              >
                <Text style={styles.retryBtnText}>{t('retry')}</Text>
              </TouchableOpacity>
            </View>
          ) : primaryHlb ? (
            <View testID="assigned-hlb-container">
              <View style={styles.hlbHeaderRow}>
                <View>
                  <Text style={[styles.hlbCodeTitle, themeStyles.text]}>
                    {primaryHlb.block_code}
                  </Text>
                  <Text style={[styles.hlbSubtitle, themeStyles.subtext]}>
                    {primaryHlb.layout_name || primaryHlb.area_name || 'Village Area'}
                  </Text>
                </View>
                <StatusBadge
                  type={isDownloaded ? 'OFFLINE' : 'ONLINE'}
                  label={isDownloaded ? t('available_offline') : t('online_badge')}
                />
              </View>

              {/* Action Buttons */}
              <View style={styles.actionButtonsContainer}>
                {!isDownloaded && (
                  <PrimaryButton
                    title={downloading ? t('downloading') : t('download_for_offline')}
                    onPress={() => handleDownload(primaryHlb.id)}
                    disabled={downloading}
                    loading={downloading}
                    testID="dashboard-download-hlb-btn"
                    style={{ marginBottom: 8 }}
                  />
                )}
                <PrimaryButton
                  title={t('view_assigned_hlb')}
                  onPress={() =>
                    navigation.navigate('EnumeratorHlbDetail', {
                      hlbId: primaryHlb.id,
                      blockCode: primaryHlb.block_code,
                    })
                  }
                  testID="view-assigned-hlb-btn"
                />
              </View>
            </View>
          ) : (
            <View style={[styles.emptyContainer, themeStyles.emptyBox]} testID="unassigned-empty-state">
              <Text style={[styles.emptyTitle, themeStyles.text]}>
                {t('no_hlb_assigned_to_you')}
              </Text>
              <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                {t('contact_supervisor')}
              </Text>
              <TouchableOpacity
                style={styles.checkAssignmentBtn}
                onPress={() => fetchMyAssignments(true)}
                activeOpacity={0.8}
                testID="refresh-assignment-btn"
              >
                <Text style={styles.checkAssignmentBtnText}>↻ {t('check_for_assignments')}</Text>
              </TouchableOpacity>
            </View>
          )}
        </Card>

        {/* Logout Button */}
        <View style={styles.logoutContainer}>
          <SecondaryButton
            title={loggingOut ? t('logging_out') : t('logout')}
            onPress={handleLogout}
            disabled={loggingOut}
            testID="logout-button"
          />
        </View>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    gap: 16,
    paddingBottom: 24,
  },
  infoRow: {
    fontSize: 14,
    marginBottom: 8,
  },
  boldText: {
    fontWeight: '700',
  },
  loadingContainer: {
    paddingVertical: 24,
    alignItems: 'center',
    gap: 8,
  },
  loadingText: {
    fontSize: 13,
  },
  errorBox: {
    padding: 16,
    borderRadius: 8,
    backgroundColor: '#FEE2E2',
    alignItems: 'center',
    gap: 12,
  },
  errorText: {
    color: '#DC2626',
    fontSize: 13,
    textAlign: 'center',
  },
  retryBtn: {
    backgroundColor: '#DC2626',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
  },
  retryBtnText: {
    color: '#FFFFFF',
    fontWeight: '600',
    fontSize: 12,
  },
  hlbHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  hlbCodeTitle: {
    fontSize: 18,
    fontWeight: '800',
  },
  hlbSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  metricsGrid: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 8,
  },
  metricItem: {
    flex: 1,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  metricNumber: {
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 2,
  },
  metricLabel: {
    fontSize: 11,
    textAlign: 'center',
  },
  actionButtonsContainer: {
    marginTop: 4,
  },
  syncHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  syncTitleText: {
    fontSize: 15,
    fontWeight: '700',
  },
  syncSubtext: {
    fontSize: 12,
    marginTop: 2,
  },
  syncMetricsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  syncMetricBox: {
    flex: 1,
    padding: 8,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: 'center',
  },
  syncMetricNum: {
    fontSize: 16,
    fontWeight: '700',
  },
  syncMetricLabel: {
    fontSize: 10,
    marginTop: 2,
  },
  syncActionsRow: {
    marginTop: 4,
  },
  emptyContainer: {
    padding: 24,
    borderRadius: 8,
    borderWidth: 1,
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 4,
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 13,
    textAlign: 'center',
    marginBottom: 12,
  },
  checkAssignmentBtn: {
    backgroundColor: '#0284C7',
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 6,
    marginTop: 4,
  },
  checkAssignmentBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 12,
    letterSpacing: 0.5,
  },
  logoutContainer: {
    marginTop: 8,
  },
});
