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
  PrimaryButton,
  SecondaryButton,
  ScreenContainer,
  StatusBadge,
} from '../../components';
import { extractErrorMessage } from '../../core/apiClient';
import { layoutService, LayoutSummary } from '../../core/layoutService';
import {
  supervisorService,
  SupervisorSummary,
} from '../../core/supervisorService';
import { useTranslation } from '../../core/localization';
import { SupervisorAssignmentModal } from './SupervisorAssignmentModal';
import type { DeputyNavigationProp } from '../../navigation/navigationTypes';

export function DeputySupervisorsScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const { t } = useTranslation();

  const [supervisors, setSupervisors] = useState<SupervisorSummary[]>([]);
  const [layouts, setLayouts] = useState<LayoutSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'ASSIGNED' | 'UNASSIGNED'>('ALL');

  // Modal assignment state
  const [selectedLayoutForAssignment, setSelectedLayoutForAssignment] = useState<LayoutSummary | null>(null);

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
      const [supRes, layoutRes] = await Promise.all([
        supervisorService.getSupervisors(),
        layoutService.getLayouts(),
      ]);
      setSupervisors(supRes.items || []);
      setLayouts(layoutRes.items || []);
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

  // Map supervisors to their assigned layouts
  const supervisorLayoutMap = useMemo(() => {
    const map = new Map<string, LayoutSummary[]>();
    for (const layout of layouts) {
      if (layout.supervisor_id) {
        const existing = map.get(layout.supervisor_id) || [];
        existing.push(layout);
        map.set(layout.supervisor_id, existing);
      }
    }
    return map;
  }, [layouts]);

  // Filtered list
  const filteredSupervisors = useMemo(() => {
    return supervisors.filter((sup) => {
      const assigned = (supervisorLayoutMap.get(sup.id) || []).length > 0;
      if (statusFilter === 'ASSIGNED' && !assigned) return false;
      if (statusFilter === 'UNASSIGNED' && assigned) return false;

      if (!searchQuery.trim()) return true;
      const q = searchQuery.toLowerCase();
      return (
        sup.name.toLowerCase().includes(q) ||
        sup.username.toLowerCase().includes(q) ||
        (sup.phone && sup.phone.includes(q))
      );
    });
  }, [supervisors, supervisorLayoutMap, statusFilter, searchQuery]);

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
    infoBox: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F8FAFC',
      borderColor: isDarkMode ? '#444444' : '#E2E8F0',
    },
  };

  const renderSupervisorItem = ({ item }: { item: SupervisorSummary }) => {
    const assignedLayouts = supervisorLayoutMap.get(item.id) || [];
    const isAssigned = assignedLayouts.length > 0;
    const totalHlbs = assignedLayouts.reduce((acc, l) => acc + (l.hlb_count || 0), 0);
    const totalBuildings = assignedLayouts.reduce((acc, l) => acc + (l.total_buildings || 0), 0);

    return (
      <Card testID={`supervisor-card-${item.id}`} style={styles.card}>
        <View style={styles.cardHeader}>
          <View style={{ flex: 1 }}>
            <Text style={[styles.supervisorName, themeStyles.text]}>{item.name}</Text>
            <Text style={[styles.supervisorUsername, themeStyles.subtext]}>
              @{item.username} {item.phone ? `• 📞 ${item.phone}` : ''}
            </Text>
          </View>
          <StatusBadge
            type={item.status === 'ACTIVE' ? 'ASSIGNED' : 'IN_REVIEW'}
            label={item.status}
          />
        </View>

        <View style={[styles.assignmentBox, themeStyles.infoBox]}>
          <Text style={[styles.sectionTitle, themeStyles.text]}>
            {isAssigned ? '📍 Assigned Jurisdictions' : '⚠️ Unassigned'}
          </Text>
          {isAssigned ? (
            assignedLayouts.map((l) => (
              <View key={l.id} style={styles.layoutRow}>
                <Text style={[styles.layoutNameText, themeStyles.text]}>• {l.name}</Text>
                <Text style={[styles.layoutMetaText, themeStyles.subtext]}>
                  {l.hlb_count || 0} HLBs • {l.total_buildings || 0} Buildings
                </Text>
              </View>
            ))
          ) : (
            <Text style={[styles.noLayoutText, themeStyles.subtext]}>
              No active layouts currently assigned to this supervisor.
            </Text>
          )}

          {isAssigned && (
            <View style={styles.summaryStatsRow}>
              <Text style={[styles.statsBadge, { color: '#0066CC' }]}>
                Total HLBs: {totalHlbs}
              </Text>
              <Text style={[styles.statsBadge, { color: '#2E7D32' }]}>
                Total Buildings: {totalBuildings}
              </Text>
            </View>
          )}
        </View>

        <View style={styles.cardActions}>
          {isAssigned ? (
            <SecondaryButton
              title="Change Assignment"
              onPress={() => setSelectedLayoutForAssignment(assignedLayouts[0])}
              testID={`reassign-supervisor-btn-${item.id}`}
            />
          ) : (
            <PrimaryButton
              title="Assign to Layout"
              onPress={() => navigation.navigate('LayoutList')}
              testID={`assign-to-layout-btn-${item.id}`}
            />
          )}
        </View>
      </Card>
    );
  };

  return (
    <ScreenContainer testID="deputy-supervisors-screen">
      <View testID="supervisors-placeholder-screen" />
      <AppHeader
        title={t('supervisors') || 'Supervisors'}
        subtitle="FIELDWORK SUPERVISION & JURISDICTION"
        roleType="DEPUTY_TAHSILDAR"
        roleLabel={t('role_deputy')}
        showBack
        onBack={() => navigation.goBack()}
      />

      {/* Search and Filters */}
      <View style={styles.filterSection}>
        <TextInput
          style={[styles.searchInput, themeStyles.searchBox]}
          placeholder="Search by name, username, or phone..."
          placeholderTextColor="#999999"
          value={searchQuery}
          onChangeText={setSearchQuery}
          testID="supervisors-search-input"
        />

        <View style={styles.tabRow}>
          {(['ALL', 'ASSIGNED', 'UNASSIGNED'] as const).map((tab) => (
            <TouchableOpacity
              key={tab}
              style={[
                styles.tabButton,
                statusFilter === tab ? themeStyles.filterTabActive : themeStyles.filterTabInactive,
              ]}
              onPress={() => setStatusFilter(tab)}
              testID={`tab-${tab.toLowerCase()}`}
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
        <LoadingIndicator message="Loading supervisors..." />
      ) : filteredSupervisors.length === 0 ? (
        <EmptyState
          title="No Supervisors Found"
          description={searchQuery ? 'No supervisors match the current filter.' : 'No supervisors registered.'}
          actionTitle="Refresh"
          onAction={() => loadData(true)}
          testID="empty-supervisors-view"
        />
      ) : (
        <FlatList
          data={filteredSupervisors}
          keyExtractor={(item) => item.id}
          renderItem={renderSupervisorItem}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadData(true)} />}
          testID="supervisors-flatlist"
        />
      )}

      {/* Supervisor Assignment Modal */}
      <SupervisorAssignmentModal
        visible={selectedLayoutForAssignment !== null}
        layout={selectedLayoutForAssignment}
        onClose={() => {
          setSelectedLayoutForAssignment(null);
          loadData();
        }}
        onSuccess={() => {
          loadData();
        }}
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  filterSection: {
    paddingHorizontal: 16,
    paddingVertical: 12,
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
  card: {
    marginBottom: 8,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  supervisorName: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  supervisorUsername: {
    fontSize: 13,
    marginTop: 2,
  },
  assignmentBox: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginTop: 4,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: 'bold',
    marginBottom: 6,
  },
  layoutRow: {
    marginTop: 4,
  },
  layoutNameText: {
    fontSize: 14,
    fontWeight: '600',
  },
  layoutMetaText: {
    fontSize: 12,
    marginLeft: 10,
    marginTop: 2,
  },
  noLayoutText: {
    fontSize: 12,
    fontStyle: 'italic',
  },
  summaryStatsRow: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#E2E8F0',
  },
  statsBadge: {
    fontSize: 12,
    fontWeight: 'bold',
  },
  cardActions: {
    marginTop: 4,
  },
  error: {
    margin: 16,
  },
});
