import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  FlatList,
  Modal,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  useColorScheme,
  BackHandler,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
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
import { AdministrativeArea, areaService } from '../../core/areaService';
import { layoutService, LayoutSummary } from '../../core/layoutService';
import { useTranslation } from '../../core/localization';
import { SupervisorAssignmentModal } from './SupervisorAssignmentModal';
import type { DeputyNavigationProp, DeputyStackParamList } from '../../navigation/navigationTypes';

export function LayoutListScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const route = useRoute<RouteProp<DeputyStackParamList, 'LayoutList'>>();
  const { t } = useTranslation();

  const filterAreaId = route.params?.areaId;
  const filterAreaName = route.params?.areaName;

  const [layouts, setLayouts] = useState<LayoutSummary[]>([]);
  const [areas, setAreas] = useState<AdministrativeArea[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Create/Edit layout modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [editingLayout, setEditingLayout] = useState<LayoutSummary | null>(null);
  const [selectedAreaIds, setSelectedAreaIds] = useState<string[]>(filterAreaId ? [filterAreaId] : []);
  const [areaSearchQuery, setAreaSearchQuery] = useState('');
  const [newLayoutName, setNewLayoutName] = useState('');
  const [targetSizeInput, setTargetSizeInput] = useState('250');
  const [createLoading, setCreateLoading] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  // Supervisor assignment modal state
  const [selectedLayoutForAssignment, setSelectedLayoutForAssignment] = useState<LayoutSummary | null>(null);

  // Backwards compatibility alias for single-area checks
  const selectedAreaId = selectedAreaIds[0] || filterAreaId || '';

  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const [layoutRes, areaRes] = await Promise.all([
        layoutService.getLayouts(filterAreaId ? { administrative_area_id: filterAreaId } : undefined),
        areaService.getAreas(),
      ]);
      setLayouts(layoutRes.items || []);
      setAreas(areaRes.items || []);

      setSelectedAreaIds((prev) => {
        if (prev.length > 0) return prev;
        if (filterAreaId) return [filterAreaId];
        return [];
      });
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filterAreaId]);

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

  // Multi-area derived calculations
  const selectedAreas = useMemo(() => {
    return areas.filter((a) => selectedAreaIds.includes(a.id));
  }, [areas, selectedAreaIds]);

  const combinedBuildingCount = useMemo(() => {
    return selectedAreas.reduce((sum, a) => sum + (a.house_count || 0), 0);
  }, [selectedAreas]);

  const estimatedHlbCount = useMemo(() => {
    const targetSize = parseInt(targetSizeInput, 10) || 250;
    return Math.max(1, Math.ceil(combinedBuildingCount / Math.max(1, targetSize)));
  }, [combinedBuildingCount, targetSizeInput]);

  const filteredAreas = useMemo(() => {
    if (!areaSearchQuery.trim()) return areas;
    const q = areaSearchQuery.toLowerCase();
    return areas.filter(
      (a) => a.name.toLowerCase().includes(q) || a.code.toLowerCase().includes(q)
    );
  }, [areas, areaSearchQuery]);

  // Conflict detection: returns info if an area is already in another active layout
  const conflictingAreaInfo = useCallback(
    (areaId: string): { areaName: string; layoutName: string; status: string } | null => {
      const area = areas.find((a) => a.id === areaId);
      for (const l of layouts) {
        if (editingLayout && l.id === editingLayout.id) continue;
        const lAreaIds =
          l.area_ids && l.area_ids.length > 0
            ? l.area_ids
            : [l.area_id, l.administrative_area_id].filter(Boolean) as string[];
        if (lAreaIds.includes(areaId)) {
          return {
            areaName: area?.name || 'Area',
            layoutName: l.name,
            status: l.status,
          };
        }
      }
      return null;
    },
    [areas, layouts, editingLayout]
  );

  const conflictWarning = useMemo(() => {
    for (const aid of selectedAreaIds) {
      const conf = conflictingAreaInfo(aid);
      if (conf) {
        return `"${conf.areaName}" is already part of active layout "${conf.layoutName}" (${conf.status}).`;
      }
    }
    return null;
  }, [selectedAreaIds, conflictingAreaInfo]);

  const handleToggleArea = (areaId: string) => {
    setSelectedAreaIds((prev) => {
      if (prev.includes(areaId)) {
        return prev.filter((id) => id !== areaId);
      }
      return [...prev, areaId];
    });
  };

  const handleRemoveArea = (areaId: string) => {
    setSelectedAreaIds((prev) => prev.filter((id) => id !== areaId));
  };

  const handleOpenCreateModal = () => {
    setEditingLayout(null);
    setNewLayoutName('');
    setTargetSizeInput('250');
    setAreaSearchQuery('');
    setCreateError(null);
    setSelectedAreaIds(filterAreaId ? [filterAreaId] : []);
    setShowCreateModal(true);
  };

  const handleOpenEditModal = (layout: LayoutSummary) => {
    setEditingLayout(layout);
    setNewLayoutName(layout.name);
    setTargetSizeInput(String(layout.target_buildings_per_hlb || layout.target_houses_per_hlb || 250));
    setAreaSearchQuery('');
    setCreateError(null);
    const existingAreaIds =
      layout.area_ids && layout.area_ids.length > 0
        ? layout.area_ids
        : [layout.area_id, layout.administrative_area_id].filter(Boolean) as string[];
    setSelectedAreaIds(existingAreaIds.length > 0 ? existingAreaIds : areas.length > 0 ? [areas[0].id] : []);
    setShowCreateModal(true);
  };

  const handleSaveLayout = async () => {
    if (selectedAreaIds.length === 0) {
      setCreateError('Please select at least one village/ward');
      return;
    }
    const targetSize = parseInt(targetSizeInput, 10);
    if (isNaN(targetSize) || targetSize < 10) {
      setCreateError('Target buildings per HLB must be at least 10');
      return;
    }

    setCreateLoading(true);
    setCreateError(null);
    try {
      const chosenArea = areas.find((a) => selectedAreaIds.includes(a.id));
      const defaultName =
        selectedAreaIds.length === 1
          ? `${chosenArea?.name || 'Village'} Layout`
          : `Multi-Area Layout (${selectedAreaIds.length} areas)`;
      const layoutName = newLayoutName.trim() || defaultName;

      if (editingLayout) {
        // Edit existing layout without creating duplicate
        await layoutService.updateLayout(editingLayout.id, {
          name: layoutName,
          target_buildings_per_hlb: targetSize,
          target_houses_per_hlb: targetSize,
          area_ids: selectedAreaIds,
        });

        setShowCreateModal(false);
        setEditingLayout(null);
        await loadData();
      } else {
        // Create new layout
        const created = await layoutService.createLayout({
          administrative_area_id: selectedAreaIds[0],
          area_id: selectedAreaIds[0],
          area_ids: selectedAreaIds,
          name: layoutName,
          target_buildings_per_hlb: targetSize,
          target_houses_per_hlb: targetSize,
        });

        setShowCreateModal(false);
        setNewLayoutName('');
        setTargetSizeInput('250');
        await loadData();

        // Navigate directly to HLB Generation screen for the newly created layout
        const targetAreaId = created.area_id || created.administrative_area_id || selectedAreaIds[0];
        navigation.navigate('HlbGeneration', {
          layoutId: created.id,
          layoutName: created.name,
          areaId: targetAreaId,
          areaName: selectedAreas.map((a) => a.name).join(', ') || 'Village',
        });
      }
    } catch (err: any) {
      setCreateError(extractErrorMessage(err));
    } finally {
      setCreateLoading(false);
    }
  };

  const themeStyles = {
    text: { color: isDarkMode ? '#FFFFFF' : '#1A237E' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#5C6BC0' },
    cardBackground: { backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF' },
    modalContent: { backgroundColor: isDarkMode ? '#242424' : '#FFFFFF' },
    input: {
      backgroundColor: isDarkMode ? '#2D2D2D' : '#F5F7FA',
      color: isDarkMode ? '#FFFFFF' : '#333333',
      borderColor: isDarkMode ? '#444444' : '#D0DBE5',
    },
    selectorItem: {
      backgroundColor: isDarkMode ? '#2D2D2D' : '#F5F7FA',
      borderColor: isDarkMode ? '#444444' : '#E0E0E0',
    },
    selectorSelected: {
      backgroundColor: isDarkMode ? '#1A365D' : '#E3F2FD',
      borderColor: isDarkMode ? '#90CAF9' : '#0066CC',
    },
  };

  const getAreaName = (areaId: string) => {
    const found = areas.find((a) => a.id === areaId);
    return found ? found.name : 'Administrative Area';
  };

  const renderLayoutItem = ({ item }: { item: LayoutSummary }) => {
    const targetAreaId =
      item.area_id ||
      item.administrative_area_id ||
      filterAreaId ||
      selectedAreaId ||
      '';
    const areaName = getAreaName(targetAreaId);
    const hasCandidates = item.active_version_number !== null;
    const targetVal = item.target_buildings_per_hlb || item.target_houses_per_hlb || 250;

    const areaSummary =
      item.area_names && item.area_names.length > 0
        ? item.area_names.length <= 2
          ? item.area_names.join(', ')
          : `${item.area_names.slice(0, 2).join(', ')} +${item.area_names.length - 2} more (${item.area_names.length} areas)`
        : item.areas_count && item.areas_count > 1
        ? `${item.areas_count} areas included`
        : areaName;

    return (
      <Card testID={`layout-card-${item.id}`} style={styles.layoutCard}>
        <View style={styles.cardHeader}>
          <View style={{ flex: 1, marginRight: 8 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 2 }}>
              <Text style={[styles.layoutName, themeStyles.text, { flex: 1 }]}>{item.name}</Text>
              <TouchableOpacity
                onPress={() => handleOpenEditModal(item)}
                style={styles.editBtn}
                testID={`edit-layout-btn-${item.id}`}
              >
                <Text style={styles.editBtnText}>✏️ Edit</Text>
              </TouchableOpacity>
            </View>
            <Text style={[styles.areaSubtitle, themeStyles.subtext]}>📍 {areaSummary}</Text>
          </View>
          <StatusBadge
            type={
              item.status === 'APPROVED'
                ? 'APPROVED'
                : item.status === 'ASSIGNED'
                ? 'ASSIGNED'
                : item.status === 'IN_REVIEW'
                ? 'IN_REVIEW'
                : 'DRAFT'
            }
            label={item.status}
          />
        </View>

        <View style={styles.metricsRow}>
          <View style={styles.metricCol}>
            <Text style={[styles.metricValue, themeStyles.text]}>{item.total_buildings || 0}</Text>
            <Text style={[styles.metricLabel, themeStyles.subtext]}>Buildings</Text>
          </View>
          <View style={styles.metricCol}>
            <Text style={[styles.metricValue, { color: '#0066CC' }]}>{item.hlb_count || 0}</Text>
            <Text style={[styles.metricLabel, themeStyles.subtext]}>HLBs</Text>
          </View>
          <View style={styles.metricCol}>
            <Text style={[styles.metricValue, themeStyles.text]}>~{targetVal}</Text>
            <Text style={[styles.metricLabel, themeStyles.subtext]}>Buildings / HLB</Text>
          </View>
          <View style={styles.metricCol}>
            <Text style={[styles.metricValue, { color: hasCandidates ? '#2E7D32' : '#F57C00' }]}>
              {hasCandidates ? `v${item.active_version_number}` : 'None'}
            </Text>
            <Text style={[styles.metricLabel, themeStyles.subtext]}>Candidate</Text>
          </View>
        </View>

        {item.assigned_supervisor_name ? (
          <View style={styles.supervisorInfoRow} testID={`layout-supervisor-row-${item.id}`}>
            <Text
              style={[styles.supervisorInfoText, { color: '#0066CC', fontWeight: '600' }]}
              testID={`layout-supervisor-${item.id}`}
            >
              👤 Supervisor: {item.assigned_supervisor_name}
            </Text>
          </View>
        ) : item.status === 'APPROVED' || item.status === 'ASSIGNED' ? (
          <View style={styles.supervisorInfoRow} testID={`layout-supervisor-row-${item.id}`}>
            <Text style={[styles.supervisorInfoText, themeStyles.subtext]}>
              👤 Supervisor: None Assigned
            </Text>
          </View>
        ) : null}

        <View style={styles.cardActions}>
          {item.status === 'APPROVED' || item.status === 'ASSIGNED' ? (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1.2 }}>
                <PrimaryButton
                  title={
                    item.assigned_supervisor_name || item.status === 'ASSIGNED'
                      ? t('change_supervisor')
                      : t('assign_supervisor')
                  }
                  onPress={() => setSelectedLayoutForAssignment(item)}
                  testID={`assign-supervisor-btn-${item.id}`}
                />
              </View>
              <View style={{ flex: 0.8 }}>
                <SecondaryButton
                  title="VIEW HLBs"
                  onPress={() =>
                    navigation.navigate('HlbReview', {
                      layoutId: item.id,
                      areaName: areaName,
                      areaId: targetAreaId,
                    })
                  }
                  testID={`review-hlb-btn-${item.id}`}
                />
              </View>
            </View>
          ) : hasCandidates ? (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <View style={{ flex: 1 }}>
                <PrimaryButton
                  title="REVIEW & APPROVE"
                  onPress={() =>
                    navigation.navigate('HlbReview', {
                      layoutId: item.id,
                      areaName: areaName,
                      areaId: targetAreaId,
                    })
                  }
                  testID={`review-hlb-btn-${item.id}`}
                />
              </View>
              <View style={{ flex: 1 }}>
                <SecondaryButton
                  title="⚡ REGENERATE"
                  onPress={() =>
                    navigation.navigate('HlbGeneration', {
                      layoutId: item.id,
                      layoutName: item.name,
                      areaId: targetAreaId,
                      areaName: areaName,
                    })
                  }
                  testID={`generate-hlb-btn-${item.id}`}
                />
              </View>
            </View>
          ) : (
            <PrimaryButton
              title="⚡ GENERATE HLBs"
              onPress={() =>
                navigation.navigate('HlbGeneration', {
                  layoutId: item.id,
                  layoutName: item.name,
                  areaId: targetAreaId,
                  areaName: areaName,
                })
              }
              testID={`generate-hlb-btn-${item.id}`}
            />
          )}
        </View>
      </Card>
    );
  };

  return (
    <ScreenContainer testID="layout-list-screen">
      <AppHeader
        title={filterAreaName ? `${filterAreaName} Layouts` : t('layouts_title')}
        subtitle="PHASE 4 • AI-ASSISTED CANDIDATE HLB GENERATION"
        roleType="DEPUTY_TAHSILDAR"
        roleLabel={t('role_deputy')}
        showBack
        onBack={() => navigation.goBack()}
      />

      <View style={styles.actionHeader}>
        <Text style={[styles.headerCount, themeStyles.subtext]}>
          {layouts.length} {layouts.length === 1 ? 'Layout' : 'Layouts'}
        </Text>
        <PrimaryButton
          title={`+ ${t('create_layout')}`}
          onPress={handleOpenCreateModal}
          style={styles.createBtn}
          testID="open-create-layout-modal-btn"
        />
      </View>

      {error && <ErrorMessage message={error} onRetry={() => loadData()} style={styles.error} />}

      {loading && !refreshing ? (
        <LoadingIndicator message="Loading layouts..." />
      ) : layouts.length === 0 ? (
        <EmptyState
          title={t('no_layouts_found')}
          description="Create a new layout for an administrative area to generate candidate HLBs."
          actionTitle={`+ ${t('create_layout')}`}
          onAction={handleOpenCreateModal}
          testID="empty-layouts-view"
        />
      ) : (
        <FlatList
          data={layouts}
          keyExtractor={(item) => item.id}
          renderItem={renderLayoutItem}
          contentContainerStyle={styles.listContent}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => loadData(true)} />}
          testID="layouts-flatlist"
        />
      )}

      {/* Create / Edit Layout Modal */}
      <Modal visible={showCreateModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, themeStyles.modalContent]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              {editingLayout ? 'Edit Layout' : t('create_layout_title')}
            </Text>

            {createError && <ErrorMessage message={createError} style={{ marginBottom: 12 }} />}

            {conflictWarning && (
              <View style={styles.warningBanner} testID="layout-conflict-warning">
                <Text style={styles.warningText}>⚠️ {conflictWarning}</Text>
              </View>
            )}

            <ScrollView
              style={{ maxHeight: 420 }}
              showsVerticalScrollIndicator={true}
              keyboardShouldPersistTaps="handled"
            >
              <Text style={[styles.inputLabel, themeStyles.subtext]}>
                Select Villages / Wards ({selectedAreaIds.length} selected):
              </Text>

              {/* Area search */}
              <TextInput
                style={[styles.textInput, themeStyles.input, { marginBottom: 8 }]}
                placeholder="Search villages / wards..."
                placeholderTextColor="#999999"
                value={areaSearchQuery}
                onChangeText={setAreaSearchQuery}
                testID="search-area-input"
              />

              {/* Selected Area Chips */}
              {selectedAreas.length > 0 && (
                <View style={styles.chipsContainer} testID="selected-areas-chips">
                  {selectedAreas.map((a) => (
                    <View key={a.id} style={styles.chip} testID={`selected-area-chip-${a.id}`}>
                      <Text style={styles.chipText}>
                        {a.name} ({a.house_count || 0})
                      </Text>
                      <TouchableOpacity
                        onPress={() => handleRemoveArea(a.id)}
                        style={styles.chipRemoveBtn}
                        testID={`remove-area-chip-${a.id}`}
                      >
                        <Text style={styles.chipRemoveText}>✕</Text>
                      </TouchableOpacity>
                    </View>
                  ))}
                </View>
              )}

              {/* Multi-Area Selection List */}
              <View style={styles.areaSelectorList}>
                {filteredAreas.map((a) => {
                  const isSelected = selectedAreaIds.includes(a.id);
                  const isConflict = Boolean(conflictingAreaInfo(a.id));
                  return (
                    <TouchableOpacity
                      key={a.id}
                      style={[
                        styles.selectorItem,
                        themeStyles.selectorItem,
                        isSelected && themeStyles.selectorSelected,
                        isConflict && !isSelected && styles.conflictSelectorItem,
                      ]}
                      onPress={() => handleToggleArea(a.id)}
                      testID={`select-area-${a.id}`}
                    >
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text
                          style={[
                            styles.selectorItemText,
                            themeStyles.text,
                            isSelected && { fontWeight: 'bold', color: '#0066CC' },
                          ]}
                        >
                          {isSelected ? '✓ ' : '+ '}
                          {a.name} ({a.code})
                        </Text>
                        <Text style={[styles.areaCountBadge, themeStyles.subtext]}>
                          {a.house_count || 0} bldgs
                        </Text>
                      </View>
                    </TouchableOpacity>
                  );
                })}
              </View>

              {/* Combined Totals & House Count Estimates */}
              <View style={styles.selectionSummaryBox}>
                <View style={styles.summaryItem}>
                  <Text style={styles.summaryValue} testID="combined-areas-count">
                    {selectedAreaIds.length}
                  </Text>
                  <Text style={styles.summaryLabel}>Areas</Text>
                </View>
                <View style={styles.summaryItem}>
                  <Text style={styles.summaryValue} testID="combined-buildings-count">
                    {combinedBuildingCount}
                  </Text>
                  <Text style={styles.summaryLabel}>Total Buildings</Text>
                </View>
                <View style={styles.summaryItem}>
                  <Text style={styles.summaryValue} testID="combined-est-hlbs">
                    ~{estimatedHlbCount}
                  </Text>
                  <Text style={styles.summaryLabel}>Est. HLBs</Text>
                </View>
              </View>

              <Text style={[styles.inputLabel, themeStyles.subtext]}>{t('layout_name_label')}:</Text>
              <TextInput
                style={[styles.textInput, themeStyles.input]}
                placeholder="e.g. Arasur Master Layout 2026"
                placeholderTextColor="#999999"
                value={newLayoutName}
                onChangeText={setNewLayoutName}
                testID="new-layout-name-input"
              />

              <Text style={[styles.inputLabel, themeStyles.subtext]}>{t('target_hlb_size_label')}:</Text>
              <TextInput
                style={[styles.textInput, themeStyles.input]}
                placeholder="250"
                placeholderTextColor="#999999"
                keyboardType="numeric"
                value={targetSizeInput}
                onChangeText={setTargetSizeInput}
                testID="new-layout-target-input"
              />
              <Text style={[styles.helperText, themeStyles.subtext]}>{t('target_size_desc')}</Text>
            </ScrollView>

            <View style={styles.modalActions}>
              <SecondaryButton
                title={t('cancel')}
                onPress={() => setShowCreateModal(false)}
                style={{ flex: 1, marginRight: 8 }}
                testID="cancel-create-layout-btn"
              />
              <PrimaryButton
                title={editingLayout ? 'Update Layout' : t('save')}
                onPress={handleSaveLayout}
                loading={createLoading}
                style={{ flex: 1, marginLeft: 8 }}
                testID="confirm-create-layout-btn"
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* Supervisor Assignment Modal */}
      <SupervisorAssignmentModal
        visible={selectedLayoutForAssignment !== null}
        layout={selectedLayoutForAssignment}
        areaName={
          selectedLayoutForAssignment
            ? getAreaName(
                selectedLayoutForAssignment.area_id ||
                  selectedLayoutForAssignment.administrative_area_id ||
                  ''
              )
            : undefined
        }
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
  actionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  headerCount: {
    fontSize: 14,
    fontWeight: '600',
  },
  createBtn: {
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  listContent: {
    padding: 16,
    paddingBottom: 32,
  },
  layoutCard: {
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  layoutName: {
    fontSize: 17,
    fontWeight: 'bold',
  },
  areaSubtitle: {
    fontSize: 13,
    marginTop: 3,
  },
  editBtn: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    backgroundColor: 'rgba(0, 102, 204, 0.1)',
    borderRadius: 6,
    borderWidth: 1,
    borderColor: 'rgba(0, 102, 204, 0.25)',
  },
  editBtnText: {
    fontSize: 12,
    fontWeight: '600',
    color: '#0066CC',
  },
  chipsContainer: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 8,
  },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#E0F2FE',
    borderColor: '#38BDF8',
    borderWidth: 1,
    borderRadius: 14,
    paddingHorizontal: 8,
    paddingVertical: 3,
    gap: 4,
  },
  chipText: {
    fontSize: 12,
    color: '#0369A1',
    fontWeight: '500',
  },
  chipRemoveBtn: {
    paddingHorizontal: 3,
  },
  chipRemoveText: {
    fontSize: 11,
    color: '#0284C7',
    fontWeight: 'bold',
  },
  areaCountBadge: {
    fontSize: 11,
    fontWeight: '500',
  },
  conflictSelectorItem: {
    borderColor: '#F59E0B',
  },
  selectionSummaryBox: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    backgroundColor: 'rgba(0, 102, 204, 0.08)',
    borderRadius: 8,
    paddingVertical: 8,
    marginVertical: 8,
  },
  summaryItem: {
    alignItems: 'center',
  },
  summaryValue: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#0066CC',
  },
  summaryLabel: {
    fontSize: 11,
    color: '#666666',
    marginTop: 2,
  },
  warningBanner: {
    backgroundColor: '#FEF3C7',
    borderColor: '#F59E0B',
    borderWidth: 1,
    borderRadius: 8,
    padding: 8,
    marginBottom: 10,
  },
  warningText: {
    fontSize: 12,
    color: '#92400E',
  },
  metricsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    backgroundColor: 'rgba(0, 0, 0, 0.03)',
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 12,
    marginBottom: 14,
  },
  metricCol: {
    alignItems: 'center',
  },
  metricValue: {
    fontSize: 16,
    fontWeight: 'bold',
  },
  metricLabel: {
    fontSize: 11,
    marginTop: 2,
  },
  cardActions: {
    marginTop: 4,
  },
  error: {
    margin: 16,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    padding: 20,
  },
  modalBox: {
    borderRadius: 12,
    padding: 20,
    maxHeight: '85%',
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: 'bold',
    marginBottom: 16,
    textAlign: 'center',
  },
  inputLabel: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 6,
    marginTop: 10,
  },
  textInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  helperText: {
    fontSize: 11,
    marginTop: 4,
    marginBottom: 8,
  },
  areaSelectorList: {
    maxHeight: 120,
    marginBottom: 8,
  },
  selectorItem: {
    padding: 10,
    borderWidth: 1,
    borderRadius: 6,
    marginBottom: 6,
  },
  selectorItemText: {
    fontSize: 13,
  },
  modalActions: {
    flexDirection: 'row',
    marginTop: 18,
  },
  supervisorInfoRow: {
    marginTop: 6,
    marginBottom: 6,
    paddingHorizontal: 2,
  },
  supervisorInfoText: {
    fontSize: 13,
  },
});
