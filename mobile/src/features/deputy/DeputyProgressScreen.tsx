import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  useColorScheme,
  BackHandler,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import {
  AppHeader,
  Card,
  EmptyState,
  ErrorMessage,
  LoadingIndicator,
  ScreenContainer,
  StatusBadge,
} from '../../components';
import { extractErrorMessage } from '../../core/apiClient';
import {
  deputyService,
  DeputyLayoutProgressItem,
  DeputyOverallProgressResponse,
  DeputyHlbSummary,
} from '../../core/deputyService';
import { useTranslation } from '../../core/localization';
import type { DeputyNavigationProp } from '../../navigation/navigationTypes';

export function DeputyProgressScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const { t } = useTranslation();

  const [overallData, setOverallData] = useState<DeputyOverallProgressResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ACTIVE' | 'COMPLETED'>('ALL');

  // Expanded layout state for viewing HLBs
  const [expandedLayoutId, setExpandedLayoutId] = useState<string | null>(null);
  const [expandedHlbs, setExpandedHlbs] = useState<DeputyHlbSummary[]>([]);
  const [loadingHlbs, setLoadingHlbs] = useState(false);

  // Handle hardware back on Android
  useEffect(() => {
    const backAction = () => {
      navigation.goBack();
      return true;
    };
    const backHandler = BackHandler.addEventListener('hardwareBackPress', backAction);
    return () => backHandler.remove();
  }, [navigation]);

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const res = await deputyService.getOverallProgress();
      setOverallData(res);
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleToggleExpand = async (layoutId: string) => {
    if (expandedLayoutId === layoutId) {
      setExpandedLayoutId(null);
      setExpandedHlbs([]);
      return;
    }

    setExpandedLayoutId(layoutId);
    setLoadingHlbs(true);
    try {
      const detailRes = await deputyService.getLayoutProgress(layoutId);
      setExpandedHlbs(detailRes.hlbs || []);
    } catch {
      setExpandedHlbs([]);
    } finally {
      setLoadingHlbs(false);
    }
  };

  const filteredLayouts = useMemo(() => {
    if (!overallData?.layouts) return [];
    return overallData.layouts.filter((l) => {
      if (statusFilter === 'ACTIVE' && l.status === 'COMPLETED') return false;
      if (statusFilter === 'COMPLETED' && l.status !== 'COMPLETED') return false;

      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      const supName = l.supervisor?.name?.toLowerCase() || '';
      return (
        l.layout_name.toLowerCase().includes(q) ||
        (l.village_name && l.village_name.toLowerCase().includes(q)) ||
        supName.includes(q)
      );
    });
  }, [overallData, statusFilter, searchQuery]);

  const themeStyles = {
    text: { color: isDarkMode ? '#FFFFFF' : '#333333' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#666666' },
    cardBg: { backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF' },
    searchBox: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F5F7FA',
      borderColor: isDarkMode ? '#444444' : '#E0E0E0',
      color: isDarkMode ? '#FFFFFF' : '#333333',
    },
    filterTabActive: {
      backgroundColor: '#0066CC',
      borderColor: '#0066CC',
    },
    filterTabInactive: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F0F4F8',
      borderColor: isDarkMode ? '#444444' : '#D0DBE5',
    },
    filterTextActive: { color: '#FFFFFF', fontWeight: 'bold' as const },
    filterTextInactive: { color: isDarkMode ? '#A0A0A0' : '#555555' },
    summaryCard: {
      backgroundColor: isDarkMode ? '#1E293B' : '#EBF5FF',
      borderColor: isDarkMode ? '#3B82F6' : '#90CAF9',
    },
    expandBox: {
      backgroundColor: isDarkMode ? '#262626' : '#F8FAFC',
      borderColor: isDarkMode ? '#404040' : '#E2E8F0',
    },
  };

  const renderLayoutItem = ({ item }: { item: DeputyLayoutProgressItem }) => {
    const isExpanded = expandedLayoutId === item.layout_id;
    const progressPct = Math.round(item.overall_progress_percentage || 0);

    return (
      <Card testID={`progress-layout-card-${item.layout_id}`} style={styles.layoutCard}>
        <TouchableOpacity
          activeOpacity={0.8}
          onPress={() => handleToggleExpand(item.layout_id)}
          testID={`toggle-expand-${item.layout_id}`}
        >
          <View style={styles.cardHeader}>
            <View style={{ flex: 1 }}>
              <Text style={[styles.layoutName, themeStyles.text]}>{item.layout_name}</Text>
              <Text style={[styles.villageSubtitle, themeStyles.subtext]}>
                📍 {item.village_name || 'Village Jurisdiction'}
              </Text>
            </View>
            <StatusBadge
              type={item.status === 'COMPLETED' ? 'APPROVED' : 'ASSIGNED'}
              label={item.status}
            />
          </View>

          {/* Supervisor display */}
          <View style={styles.supervisorRow}>
            <Text style={[styles.supervisorLabel, themeStyles.subtext]}>Supervisor: </Text>
            <Text style={[styles.supervisorName, { color: '#0066CC' }]}>
              {item.supervisor?.name || 'Unassigned'}
            </Text>
          </View>

          {/* Progress bar */}
          <View style={styles.progressBarWrapper}>
            <View style={styles.progressBarTrack}>
              <View style={[styles.progressBarFill, { width: `${progressPct}%` }]} />
            </View>
            <Text style={[styles.progressPctText, themeStyles.text]}>{progressPct}%</Text>
          </View>

          {/* Metrics Row */}
          <View style={styles.metricsRow}>
            <View style={styles.metricCol}>
              <Text style={[styles.metricValue, themeStyles.text]}>{item.total_houses || 0}</Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>Total</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={[styles.metricValue, { color: '#2E7D32' }]}>{item.completed_houses || 0}</Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>Done</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={[styles.metricValue, { color: '#E65100' }]}>{item.remaining_houses || 0}</Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>Remaining</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={[styles.metricValue, { color: '#C62828' }]}>{item.locked_houses || 0}</Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>Locked</Text>
            </View>
            <View style={styles.metricCol}>
              <Text style={[styles.metricValue, { color: '#6A1B9A' }]}>{item.revisit_count || 0}</Text>
              <Text style={[styles.metricLabel, themeStyles.subtext]}>Revisits</Text>
            </View>
          </View>

          <Text style={[styles.expandHint, themeStyles.subtext]}>
            {isExpanded ? '▲ Hide HLB Details' : '▼ Tap to View HLBs'}
          </Text>
        </TouchableOpacity>

        {/* Expanded HLBs List */}
        {isExpanded && (
          <View style={[styles.expandedContainer, themeStyles.expandBox]} testID={`expanded-hlbs-${item.layout_id}`}>
            {loadingHlbs ? (
              <LoadingIndicator message="Loading HLB details..." />
            ) : expandedHlbs.length === 0 ? (
              <Text style={[styles.emptyHlbText, themeStyles.subtext]}>No HLBs found under this layout.</Text>
            ) : (
              expandedHlbs.map((hlb) => (
                <View key={hlb.hlb_id} style={styles.hlbItemRow} testID={`hlb-row-${hlb.hlb_id}`}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.hlbCode, themeStyles.text]}>{hlb.block_code}</Text>
                    <Text style={[styles.enumeratorName, themeStyles.subtext]}>
                      Enumerator: {hlb.assigned_enumerator_name || 'Unassigned'}
                    </Text>
                  </View>
                  <View style={styles.hlbProgressCol}>
                    <Text style={[styles.hlbProgressText, { color: '#0066CC', fontWeight: 'bold' }]}>
                      {hlb.completed_houses} / {hlb.total_houses}
                    </Text>
                    <StatusBadge
                      type={hlb.status === 'COMPLETED' ? 'APPROVED' : 'ASSIGNED'}
                      label={`${Math.round(hlb.progress_percentage || 0)}%`}
                    />
                  </View>
                </View>
              ))
            )}
          </View>
        )}
      </Card>
    );
  };

  return (
    <ScreenContainer testID="deputy-progress-screen">
      <View testID="progress-placeholder-screen" />
      <AppHeader
        title={t('progress') || 'Fieldwork Progress'}
        subtitle="AUTHORITATIVE MONITORING & ENUMERATION"
        roleType="DEPUTY_TAHSILDAR"
        roleLabel={t('role_deputy')}
        showBack
        onBack={() => navigation.goBack()}
      />

      {/* Overall KPI Summary Banner */}
      {overallData && (
        <View style={[styles.kpiContainer, themeStyles.summaryCard]} testID="progress-kpi-summary">
          <View style={styles.kpiHeader}>
            <Text style={[styles.kpiTitle, themeStyles.text]}>Jurisdiction Summary</Text>
            <Text style={[styles.kpiOverallPct, { color: '#0066CC' }]}>
              {`${Math.round(overallData.overall_progress_percentage || 0)}% Completed`}
            </Text>
          </View>

          <View style={styles.kpiRow}>
            <View style={styles.kpiCol}>
              <Text style={[styles.kpiValue, themeStyles.text]}>{overallData.total_layouts}</Text>
              <Text style={[styles.kpiLabel, themeStyles.subtext]}>Layouts</Text>
            </View>
            <View style={styles.kpiCol}>
              <Text style={[styles.kpiValue, themeStyles.text]}>{overallData.total_hlbs}</Text>
              <Text style={[styles.kpiLabel, themeStyles.subtext]}>HLBs</Text>
            </View>
            <View style={styles.kpiCol}>
              <Text style={[styles.kpiValue, themeStyles.text]}>{overallData.total_houses}</Text>
              <Text style={[styles.kpiLabel, themeStyles.subtext]}>Buildings</Text>
            </View>
            <View style={styles.kpiCol}>
              <Text style={[styles.kpiValue, { color: '#2E7D32' }]}>{overallData.completed_houses}</Text>
              <Text style={[styles.kpiLabel, themeStyles.subtext]}>Completed</Text>
            </View>
          </View>
        </View>
      )}

      {/* Search and Filters */}
      <View style={styles.filterSection}>
        <TextInput
          style={[styles.searchInput, themeStyles.searchBox]}
          placeholder="Search by layout, village, or supervisor..."
          placeholderTextColor="#999999"
          value={searchQuery}
          onChangeText={setSearchQuery}
          testID="progress-search-input"
        />

        <View style={styles.tabRow}>
          {(['ALL', 'ACTIVE', 'COMPLETED'] as const).map((tab) => (
            <TouchableOpacity
              key={tab}
              style={[
                styles.tabButton,
                statusFilter === tab ? themeStyles.filterTabActive : themeStyles.filterTabInactive,
              ]}
              onPress={() => setStatusFilter(tab)}
              testID={`progress-tab-${tab.toLowerCase()}`}
            >
              <Text
                style={[
                  styles.tabText,
                  statusFilter === tab ? themeStyles.filterTextActive : themeStyles.filterTextInactive,
                ]}
              >
                {tab}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {error && <ErrorMessage message={error} onRetry={() => loadData()} style={styles.error} />}

      {loading && !refreshing ? (
        <LoadingIndicator message="Loading progress metrics..." />
      ) : filteredLayouts.length === 0 ? (
        <EmptyState
          title="No Progress Data Found"
          description={searchQuery ? 'No layouts match the current filter.' : 'No active fieldwork layouts.'}
          actionTitle="Refresh"
          onAction={() => loadData(true)}
          testID="empty-progress-view"
        />
      ) : (
        <FlatList
          data={filteredLayouts}
          keyExtractor={(item) => item.layout_id}
          renderItem={renderLayoutItem}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadData(true)} />}
          testID="progress-flatlist"
        />
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  kpiContainer: {
    margin: 16,
    marginBottom: 8,
    borderWidth: 1,
    borderRadius: 10,
    padding: 14,
  },
  kpiHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  kpiTitle: {
    fontSize: 15,
    fontWeight: 'bold',
  },
  kpiOverallPct: {
    fontSize: 15,
    fontWeight: 'bold',
  },
  kpiRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
  },
  kpiCol: {
    alignItems: 'center',
  },
  kpiValue: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  kpiLabel: {
    fontSize: 11,
    marginTop: 2,
  },
  filterSection: {
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  searchInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 10,
    fontSize: 14,
    marginBottom: 10,
  },
  tabRow: {
    flexDirection: 'row',
    gap: 8,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 6,
    borderWidth: 1,
    alignItems: 'center',
  },
  tabText: {
    fontSize: 12,
    fontWeight: '600',
  },
  listContent: {
    padding: 16,
    paddingTop: 4,
    gap: 12,
  },
  layoutCard: {
    marginBottom: 10,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 6,
  },
  layoutName: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  villageSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  supervisorRow: {
    flexDirection: 'row',
    marginTop: 4,
    marginBottom: 8,
  },
  supervisorLabel: {
    fontSize: 13,
  },
  supervisorName: {
    fontSize: 13,
    fontWeight: '600',
  },
  progressBarWrapper: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginBottom: 12,
  },
  progressBarTrack: {
    flex: 1,
    height: 8,
    borderRadius: 4,
    backgroundColor: '#E0E0E0',
    overflow: 'hidden',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#0066CC',
  },
  progressPctText: {
    fontSize: 12,
    fontWeight: 'bold',
    minWidth: 35,
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  metricCol: {
    alignItems: 'center',
  },
  metricValue: {
    fontSize: 14,
    fontWeight: 'bold',
  },
  metricLabel: {
    fontSize: 11,
    marginTop: 2,
  },
  expandHint: {
    fontSize: 11,
    textAlign: 'center',
    marginTop: 6,
  },
  expandedContainer: {
    borderTopWidth: 1,
    marginTop: 10,
    paddingTop: 8,
    borderRadius: 6,
    padding: 8,
  },
  emptyHlbText: {
    fontSize: 12,
    textAlign: 'center',
    padding: 8,
  },
  hlbItemRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: 6,
    borderBottomWidth: 1,
    borderBottomColor: '#EEEEEE',
  },
  hlbCode: {
    fontSize: 13,
    fontWeight: 'bold',
  },
  enumeratorName: {
    fontSize: 11,
    marginTop: 2,
  },
  hlbProgressCol: {
    alignItems: 'flex-end',
    gap: 2,
  },
  hlbProgressText: {
    fontSize: 12,
  },
  error: {
    margin: 16,
  },
});
