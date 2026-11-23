import React, { useState, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  Modal,
  TextInput,
  Alert,
  useColorScheme,
  ActivityIndicator,
} from 'react-native';
import { useRoute, useNavigation, RouteProp, useFocusEffect } from '@react-navigation/native';
import {
  AppHeader,
  Card,
  PrimaryButton,
  SecondaryButton,
  ScreenContainer,
  StatusBadge,
} from '../../components';
import { useAuthStore } from '../../core/authStore';
import { fieldworkService } from '../../core/fieldworkService';
import { useTranslation } from '../../core/localization';
import type {
  EnumeratorNavigationProp,
  EnumeratorStackParamList,
} from '../../navigation/navigationTypes';
import type {
  OfflineBuildingRecord,
  OfflineHouseholdRecord,
  OfflineRevisitRecord,
  OfflineCensusHouseRecord,
  BuildingFieldStatus,
  CensusHouseListingState,
  CensusHouseUseCode,
  BuildingEditType,
  RevisitReason,
} from '../../core/sqlite/types';

export function BuildingDetailScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<EnumeratorNavigationProp>();
  const route = useRoute<RouteProp<EnumeratorStackParamList, 'BuildingDetail'>>();
  const { user } = useAuthStore();
  const { t } = useTranslation();

  const { buildingId, hlbId, blockCode } = route.params;

  const [building, setBuilding] = useState<OfflineBuildingRecord | null>(null);
  const [households, setHouseholds] = useState<OfflineHouseholdRecord[]>([]);
  const [censusHouses, setCensusHouses] = useState<OfflineCensusHouseRecord[]>([]);
  const [revisits, setRevisits] = useState<OfflineRevisitRecord[]>([]);
  const [loading, setLoading] = useState(true);

  // GPS State
  const [capturingGps, setCapturingGps] = useState(false);
  const [gpsMessage, setGpsMessage] = useState<string | null>(null);

  // Revisit Modal State
  const [revisitModalVisible, setRevisitModalVisible] = useState(false);
  const [selectedReason, setSelectedReason] = useState<RevisitReason>('NO_ONE_AVAILABLE');
  const [revisitNotes, setRevisitNotes] = useState('');

  // Census House Modal State
  const [addChModalVisible, setAddChModalVisible] = useState(false);
  const [newChNumber, setNewChNumber] = useState('');
  const [newChUseCode, setNewChUseCode] = useState<CensusHouseUseCode>('RESIDENTIAL');
  const [newChListingState, setNewChListingState] = useState<CensusHouseListingState>('LISTED');
  const [newChNotes, setNewChNotes] = useState('');

  // Building Edit Modal State
  const [buildingEditModalVisible, setBuildingEditModalVisible] = useState(false);
  const [editType, setEditType] = useState<BuildingEditType>('MOVE');
  const [editReason, setEditReason] = useState('');

  const loadData = useCallback(() => {
    setLoading(true);
    try {
      const detail = fieldworkService.getBuildingDetail(buildingId);
      setBuilding(detail.building);
      setHouseholds(detail.households);
      setRevisits(detail.revisits);

      try {
        const chList = fieldworkService.getCensusHouses(buildingId);
        setCensusHouses(chList || []);
      } catch {
        setCensusHouses([]);
      }
    } catch (err: any) {
      console.error('Failed to load building detail from SQLite:', err);
    } finally {
      setLoading(false);
    }
  }, [buildingId]);

  useFocusEffect(
    useCallback(() => {
      loadData();
    }, [loadData])
  );

  const handleCaptureGps = async () => {
    setCapturingGps(true);
    setGpsMessage(null);
    try {
      const result = await fieldworkService.captureAndLogGps(
        hlbId,
        user?.id || 'enumerator-local',
        buildingId
      );

      if (result.success && result.position) {
        const boundaryResult = fieldworkService.checkBoundaryOffline(
          hlbId,
          result.position.latitude,
          result.position.longitude,
          result.position.accuracy
        );
        let boundaryLabel = '';
        if (boundaryResult.status === 'INSIDE') {
          boundaryLabel = ` • ${t('inside_hlb')}`;
        } else if (boundaryResult.status === 'OUTSIDE') {
          boundaryLabel = ` • ⚠ ${t('outside_hlb')}`;
        } else if (boundaryResult.status === 'BOUNDARY_UNCERTAIN') {
          boundaryLabel = ` • ❓ ${t('boundary_uncertain')}`;
        }

        setGpsMessage(
          `✓ Lat: ${result.position.latitude.toFixed(5)}, Long: ${result.position.longitude.toFixed(5)} (±${Math.round(result.position.accuracy || 0)}m)${boundaryLabel}`
        );
      } else if (result.error === 'PERMISSION_DENIED') {
        Alert.alert(t('gps_observation'), t('gps_permission_denied'));
      } else {
        Alert.alert(t('gps_observation'), result.errorMessage || t('gps_unavailable'));
      }
    } finally {
      setCapturingGps(false);
    }
  };

  const handleConfirmBuilding = () => {
    try {
      fieldworkService.setBuildingFieldStatus(buildingId, 'CONFIRMED');
      loadData();
      Alert.alert('Building Confirmed', 'Building structure confirmed successfully.');
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to confirm building.');
    }
  };

  const handleFalseDetection = () => {
    Alert.alert(
      'Mark False Detection',
      'Are you sure this structure does not exist on the ground (false detection)?',
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: 'Mark False',
          style: 'destructive',
          onPress: () => {
            try {
              fieldworkService.setBuildingFieldStatus(buildingId, 'FALSE_DETECTION');
              loadData();
              Alert.alert('Status Updated', 'Building marked as false detection.');
            } catch (err: any) {
              Alert.alert('Error', err?.message || 'Failed to update status.');
            }
          },
        },
      ]
    );
  };

  const handleOpenAddCensusHouse = () => {
    const nextNum = `CH-${censusHouses.length + 1}`;
    setNewChNumber(nextNum);
    setNewChUseCode('RESIDENTIAL');
    setNewChListingState('LISTED');
    setNewChNotes('');
    setAddChModalVisible(true);
  };

  const handleSaveCensusHouse = () => {
    if (!newChNumber.trim()) {
      Alert.alert('Validation Error', 'Census House Number is required.');
      return;
    }

    try {
      const now = new Date().toISOString();
      const chRecord: OfflineCensusHouseRecord = {
        id: `ch-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
        building_id: buildingId,
        hlb_id: hlbId,
        census_house_number: newChNumber.trim(),
        use_code: newChUseCode,
        listing_state: newChListingState,
        latitude: building?.latitude || null,
        longitude: building?.longitude || null,
        visited_at: now,
        locked_attempts: newChListingState === 'LOCKED' ? 1 : 0,
        notes: newChNotes.trim() || null,
        created_at: now,
        updated_at: now,
      };

      fieldworkService.saveCensusHouse(chRecord);
      setAddChModalVisible(false);
      loadData();
      Alert.alert('Success', `Census house ${newChNumber} saved.`);
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to save census house.');
    }
  };

  const handleSaveBuildingEdit = () => {
    if (!editReason.trim()) {
      Alert.alert('Validation Error', 'Please provide a reason for the building edit.');
      return;
    }

    try {
      const now = new Date().toISOString();
      fieldworkService.saveBuildingEdit({
        id: `bld-edit-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
        hlb_id: hlbId,
        building_id: buildingId,
        edit_type: editType,
        proposed_changes_json: JSON.stringify({
          building_id: buildingId,
          latitude: building?.latitude,
          longitude: building?.longitude,
          building_reference: building?.building_reference,
        }),
        reason: editReason.trim(),
        review_status: 'PENDING',
        created_at: now,
      });

      setBuildingEditModalVisible(false);
      setEditReason('');
      Alert.alert('Edit Requested', 'Building edit request queued for supervisor review.');
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to submit building edit.');
    }
  };

  const handleCloseListing = () => {
    if (censusHouses.length === 0) {
      Alert.alert(
        'Cannot Close Listing',
        'At least one census house must be listed for this building before closing listing.'
      );
      return;
    }

    const unresolved = censusHouses.filter(
      (ch) => ch.listing_state === 'NOT_VISITED' || ch.listing_state === 'LOCKED'
    );
    if (unresolved.length > 0) {
      Alert.alert(
        'Cannot Close Listing',
        `All census houses must be in a resolved state (LISTED, VACANT, or NON_RESIDENTIAL). Found ${unresolved.length} unresolved census house(s).`
      );
      return;
    }

    Alert.alert(
      'Close Census House Listing',
      'Are you sure you want to officially close listing for this building? All census houses are resolved.',
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: 'Confirm Closure',
          onPress: () => {
            try {
              fieldworkService.closeBuildingListing(buildingId);
              loadData();
              Alert.alert('Listing Closed', 'Building fieldwork listing closed successfully.');
            } catch (err: any) {
              Alert.alert('Error', err?.message || 'Failed to close listing.');
            }
          },
        },
      ]
    );
  };

  const handleSaveRevisit = () => {
    try {
      const revisitRecord: OfflineRevisitRecord = {
        id: `rev-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
        building_id: buildingId,
        hlb_id: hlbId,
        enumerator_id: user?.id || 'enumerator-local',
        reason: selectedReason,
        notes: revisitNotes.trim() || null,
        status: 'PENDING',
        created_at: new Date().toISOString(),
        resolved_at: null,
      };

      fieldworkService.saveRevisit(revisitRecord);
      setRevisitModalVisible(false);
      setRevisitNotes('');
      loadData();
      Alert.alert(t('revisit_badge'), t('revisit_logged'));
    } catch (err: any) {
      Alert.alert('Error', err?.message || 'Failed to record revisit.');
    }
  };

  const handleLockBuilding = () => {
    Alert.alert(
      t('confirm_lock'),
      t('confirm_lock_msg'),
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: t('lock_building_btn'),
          style: 'destructive',
          onPress: () => {
            try {
              fieldworkService.lockBuilding(buildingId);
              loadData();
              Alert.alert(t('locked_badge'), t('building_locked_success'));
            } catch (err: any) {
              Alert.alert('Error', err?.message || 'Failed to lock building.');
            }
          },
        },
      ]
    );
  };

  const handleDeleteHousehold = (householdId: string) => {
    Alert.alert(
      'Delete Household Record',
      'Are you sure you want to delete this household record?',
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: 'Delete',
          style: 'destructive',
          onPress: () => {
            fieldworkService.deleteHousehold(householdId, buildingId);
            loadData();
          },
        },
      ]
    );
  };

  const getStatusBadgeType = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'COMPLETED';
      case 'LOCKED':
        return 'LOCKED';
      case 'REVISIT_REQUIRED':
        return 'WARNING';
      case 'IN_PROGRESS':
        return 'IN_REVIEW';
      default:
        return 'PENDING';
    }
  };

  const getListingStateBadgeType = (state: CensusHouseListingState) => {
    switch (state) {
      case 'LISTED':
        return 'COMPLETED';
      case 'VACANT':
        return 'IN_REVIEW';
      case 'NON_RESIDENTIAL':
        return 'IN_REVIEW';
      case 'LOCKED':
        return 'LOCKED';
      default:
        return 'PENDING';
    }
  };

  const themeStyles = {
    container: { backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC' },
    card: { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' },
    text: { color: isDarkMode ? '#F1F5F9' : '#0F172A' },
    subtext: { color: isDarkMode ? '#94A3B8' : '#64748B' },
    itemBox: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
    modalContent: {
      backgroundColor: isDarkMode ? '#1E293B' : '#FFFFFF',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
    input: {
      backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC',
      color: isDarkMode ? '#FFFFFF' : '#0F172A',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
  };

  const bRef = building?.building_reference || 'BLD';
  const fieldStatus = building?.field_status || 'UNVERIFIED';
  const isClosed = Boolean(building?.listing_closed);

  return (
    <ScreenContainer testID="building-detail-screen" style={themeStyles.container}>
      <AppHeader
        title={bRef}
        subtitle={`${blockCode || 'HLB'} • ${t('building_details').toUpperCase()}`}
        roleType="ENUMERATOR"
        roleLabel={t('role_enumerator')}
        showBack
        onBack={() => navigation.goBack()}
        testID="building-detail-header"
      />

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#0284C7" />
          <Text style={[styles.loadingText, themeStyles.subtext]}>
            {t('loading')}
          </Text>
        </View>
      ) : (
        <ScrollView style={styles.content} showsVerticalScrollIndicator={false}>
          {/* 1. Building Summary & Domain Badges Card */}
          <Card title={t('building_details')} style={themeStyles.card} testID="building-info-card">
            <View style={styles.summaryHeaderRow}>
              <View>
                <Text style={[styles.buildingRefTitle, themeStyles.text]}>
                  {bRef}
                </Text>
                {building?.house_number && (
                  <Text style={[styles.houseNumText, themeStyles.subtext]}>
                    {t('house_num')}: {building.house_number}
                  </Text>
                )}
              </View>
              <View style={styles.statusBadgesGroup}>
                <StatusBadge
                  type={getStatusBadgeType(building?.status || 'PENDING')}
                  label={building?.status || 'PENDING'}
                />
                <StatusBadge
                  type={
                    fieldStatus === 'CONFIRMED'
                      ? 'COMPLETED'
                      : fieldStatus === 'FALSE_DETECTION'
                      ? 'LOCKED'
                      : 'IN_REVIEW'
                  }
                  label={fieldStatus}
                />
                {isClosed && (
                  <StatusBadge type="COMPLETED" label="LISTING CLOSED" />
                )}
              </View>
            </View>

            <View style={styles.geoInfoRow}>
              <Text style={[styles.geoText, themeStyles.subtext]}>
                📍 {building?.latitude.toFixed(5)}, {building?.longitude.toFixed(5)}
              </Text>
              <Text style={[styles.sourceText, themeStyles.subtext]}>
                {building?.source_type ? building.source_type.replace('_', ' ') : 'SATELLITE'}
              </Text>
            </View>

            {/* Quick Field Status Actions */}
            <View style={styles.quickActionsRow}>
              <TouchableOpacity
                style={[styles.smallActionBtn, { backgroundColor: '#10B981' }]}
                onPress={handleConfirmBuilding}
                testID="confirm-building-btn"
              >
                <Text style={styles.smallActionBtnText}>✓ Confirm</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.smallActionBtn, { backgroundColor: '#EF4444' }]}
                onPress={handleFalseDetection}
                testID="mark-false-detection-btn"
              >
                <Text style={styles.smallActionBtnText}>✕ False Detection</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.smallActionBtn, { backgroundColor: '#6366F1' }]}
                onPress={() => setBuildingEditModalVisible(true)}
                testID="request-building-edit-btn"
              >
                <Text style={styles.smallActionBtnText}>✎ Request Edit</Text>
              </TouchableOpacity>
            </View>
          </Card>

          {/* 2. GPS Location Observation */}
          <Card title={t('gps_observation')} style={themeStyles.card} testID="gps-observation-card">
            <Text style={[styles.gpsDescText, themeStyles.subtext]}>
              Record verified fieldwork location coordinates using on-device GPS.
            </Text>

            {gpsMessage && (
              <View style={styles.gpsSuccessBox} testID="gps-success-banner">
                <Text style={styles.gpsSuccessText}>{gpsMessage}</Text>
              </View>
            )}

            <PrimaryButton
              title={t('capture_gps')}
              onPress={handleCaptureGps}
              loading={capturingGps}
              style={styles.gpsBtn}
              testID="capture-gps-btn"
            />
          </Card>

          {/* 3. Census Houses in this Building */}
          <Card
            title={`Census Houses (${censusHouses.length})`}
            style={themeStyles.card}
            testID="census-houses-list-card"
          >
            {censusHouses.length === 0 ? (
              <View style={[styles.emptyBox, themeStyles.itemBox]}>
                <Text style={styles.emptyIcon}>🏢</Text>
                <Text style={[styles.emptyTitle, themeStyles.text]}>
                  No Census Houses Listed
                </Text>
                <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                  Add census houses (residential, commercial, etc.) within this building.
                </Text>
              </View>
            ) : (
              <View style={styles.censusHousesList}>
                {censusHouses.map((ch, idx) => (
                  <View
                    key={ch.id}
                    style={[styles.censusHouseItemCard, themeStyles.itemBox]}
                    testID={`census-house-item-${idx}`}
                  >
                    <View style={styles.chHeaderRow}>
                      <View>
                        <Text style={[styles.chNumberTitle, themeStyles.text]}>
                          {ch.census_house_number}
                        </Text>
                        <Text style={[styles.chSubText, themeStyles.subtext]}>
                          Use: {ch.use_code.replace(/_/g, ' ')}
                        </Text>
                      </View>
                      <StatusBadge
                        type={getListingStateBadgeType(ch.listing_state)}
                        label={ch.listing_state}
                      />
                    </View>

                    {ch.notes && (
                      <Text style={[styles.chNotesText, themeStyles.subtext]}>
                        Notes: {ch.notes}
                      </Text>
                    )}

                    <View style={styles.chActionRow}>
                      <TouchableOpacity
                        style={styles.chEnumerateBtn}
                        onPress={() =>
                          navigation.navigate('HouseholdForm', {
                            buildingId,
                            hlbId,
                            censusHouseId: ch.id,
                            buildingReference: bRef,
                          })
                        }
                      >
                        <Text style={styles.chEnumerateBtnText}>+ Enumerate Household</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            )}

            <PrimaryButton
              title="+ Add Census House"
              onPress={handleOpenAddCensusHouse}
              style={styles.addChBtn}
              testID="add-census-house-btn"
            />
          </Card>

          {/* 4. Households in this Building */}
          <Card
            title={`${t('households_in_building')} (${households.length})`}
            style={themeStyles.card}
            testID="households-list-card"
          >
            {households.length === 0 ? (
              <View style={[styles.emptyBox, themeStyles.itemBox]} testID="empty-households-view">
                <Text style={styles.emptyIcon}>🏠</Text>
                <Text style={[styles.emptyTitle, themeStyles.text]}>
                  {t('no_households_yet')}
                </Text>
                <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                  {t('tap_add_household_hint')}
                </Text>
              </View>
            ) : (
              <View style={styles.householdsList}>
                {households.map((hh, idx) => (
                  <View
                    key={hh.id}
                    style={[styles.householdItemCard, themeStyles.itemBox]}
                    testID={`household-item-${idx}`}
                  >
                    <View style={styles.householdHeaderRow}>
                      <View>
                        <Text style={[styles.hhNumberTitle, themeStyles.text]}>
                          {hh.household_number}: {hh.head_name}
                        </Text>
                        <Text style={[styles.hhMembersSub, themeStyles.subtext]}>
                          {hh.total_members} Members ({hh.male_count}M • {hh.female_count}F • {hh.transgender_count}T)
                        </Text>
                      </View>
                      <StatusBadge
                        type={hh.status === 'COMPLETED' ? 'COMPLETED' : 'DRAFT'}
                        label={hh.status === 'COMPLETED' ? t('completed_badge') : t('draft_badge')}
                      />
                    </View>

                    <View style={styles.hhDetailsGrid}>
                      <Text style={[styles.hhDetailChip, themeStyles.subtext]}>
                        🏷️ {hh.ownership_status}
                      </Text>
                      <Text style={[styles.hhDetailChip, themeStyles.subtext]}>
                        💧 {hh.drinking_water_source || 'Water'}
                      </Text>
                      <Text style={[styles.hhDetailChip, themeStyles.subtext]}>
                        💡 {hh.lighting_source || 'Lighting'}
                      </Text>
                    </View>

                    <View style={styles.hhActionRow}>
                      <TouchableOpacity
                        style={styles.editBtn}
                        onPress={() =>
                          navigation.navigate('HouseholdForm', {
                            buildingId,
                            hlbId,
                            householdId: hh.id,
                            censusHouseId: hh.census_house_id || undefined,
                            buildingReference: bRef,
                          })
                        }
                        testID={`edit-household-btn-${idx}`}
                      >
                        <Text style={styles.editBtnText}>✏️ {t('edit_household')}</Text>
                      </TouchableOpacity>

                      <TouchableOpacity
                        style={styles.deleteBtn}
                        onPress={() => handleDeleteHousehold(hh.id)}
                        testID={`delete-household-btn-${idx}`}
                      >
                        <Text style={styles.deleteBtnText}>🗑️</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))}
              </View>
            )}

            <PrimaryButton
              title={t('start_enumeration')}
              onPress={() =>
                navigation.navigate('HouseholdForm', {
                  buildingId,
                  hlbId,
                  buildingReference: bRef,
                })
              }
              style={styles.addHhBtn}
              testID="start-household-enumeration-btn"
            />
          </Card>

          {/* 5. Revisits History (if any) */}
          {revisits.length > 0 && (
            <Card title={`${t('revisit_badge')} History`} style={themeStyles.card}>
              {revisits.map((rev) => (
                <View key={rev.id} style={[styles.revisitCard, themeStyles.itemBox]}>
                  <View style={styles.revisitHeaderRow}>
                    <Text style={[styles.revisitReasonText, { color: '#DC2626' }]}>
                      ⚠️ {rev.reason.replace(/_/g, ' ')}
                    </Text>
                    <Text style={[styles.revisitDateText, themeStyles.subtext]}>
                      {new Date(rev.created_at).toLocaleDateString()}
                    </Text>
                  </View>
                  {rev.notes && (
                    <Text style={[styles.revisitNotesText, themeStyles.text]}>
                      Notes: {rev.notes}
                    </Text>
                  )}
                </View>
              ))}
            </Card>
          )}

          {/* 6. Fieldwork Management Actions */}
          <View style={styles.bottomActionsSection}>
            <PrimaryButton
              title={isClosed ? '✓ Listing Closed' : '🔒 Close Listing'}
              onPress={handleCloseListing}
              disabled={isClosed}
              style={[styles.closeListingBtn, isClosed && { backgroundColor: '#10B981' }]}
              testID="close-listing-btn"
            />

            <SecondaryButton
              title={t('mark_revisit')}
              onPress={() => setRevisitModalVisible(true)}
              variant="neutral"
              style={styles.revisitBtn}
              testID="mark-revisit-btn"
            />

            <SecondaryButton
              title="⏭️ Skip Building"
              onPress={() => {
                setSelectedReason('OTHER');
                setRevisitNotes('[SKIPPED] Temporarily skipped in route order: ');
                setRevisitModalVisible(true);
              }}
              variant="neutral"
              style={styles.revisitBtn}
              testID="skip-building-btn"
            />

            {building?.status !== 'LOCKED' && (
              <SecondaryButton
                title={t('lock_building_btn')}
                onPress={handleLockBuilding}
                variant="neutral"
                style={styles.lockBtn}
                testID="lock-building-action-btn"
              />
            )}
          </View>
        </ScrollView>
      )}

      {/* Revisit Modal */}
      <Modal
        visible={revisitModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setRevisitModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, themeStyles.modalContent]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              {t('mark_revisit')}
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              {t('revisit_reason')}
            </Text>

            <View style={styles.reasonsList}>
              {(
                [
                  'NO_ONE_AVAILABLE',
                  'LOCKED',
                  'NEEDS_ADDITIONAL_INFO',
                  'REFUSAL',
                  'OTHER',
                ] as RevisitReason[]
              ).map((reason) => (
                <TouchableOpacity
                  key={reason}
                  style={[
                    styles.reasonOption,
                    selectedReason === reason && styles.reasonOptionSelected,
                  ]}
                  onPress={() => setSelectedReason(reason)}
                  testID={`revisit-reason-${reason.toLowerCase()}`}
                >
                  <Text
                    style={[
                      styles.reasonOptionText,
                      selectedReason === reason && styles.reasonOptionTextSelected,
                    ]}
                  >
                    {reason === 'NO_ONE_AVAILABLE'
                      ? t('no_one_available')
                      : reason === 'LOCKED'
                      ? t('building_locked')
                      : reason === 'NEEDS_ADDITIONAL_INFO'
                      ? t('needs_info')
                      : reason === 'REFUSAL'
                      ? t('refusal')
                      : t('other_ownership')}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.notesLabel, themeStyles.text]}>
              {t('revisit_notes')}
            </Text>
            <TextInput
              style={[styles.notesInput, themeStyles.input]}
              value={revisitNotes}
              onChangeText={setRevisitNotes}
              placeholder="e.g. resident requested visit after 6 PM"
              placeholderTextColor="#94A3B8"
              multiline
              numberOfLines={3}
              testID="revisit-notes-input"
            />

            <View style={styles.modalButtonsRow}>
              <SecondaryButton
                title={t('cancel')}
                onPress={() => setRevisitModalVisible(false)}
                variant="neutral"
                style={{ flex: 1 }}
                testID="cancel-revisit-modal-btn"
              />
              <PrimaryButton
                title={t('save_revisit')}
                onPress={handleSaveRevisit}
                style={{ flex: 1 }}
                testID="save-revisit-confirm-btn"
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* Add Census House Modal */}
      <Modal
        visible={addChModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setAddChModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, themeStyles.modalContent]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              Add Census House
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              Structure: {bRef}
            </Text>

            <Text style={[styles.notesLabel, themeStyles.text]}>
              Census House Number *
            </Text>
            <TextInput
              style={[styles.notesInput, themeStyles.input]}
              value={newChNumber}
              onChangeText={setNewChNumber}
              placeholder="e.g. CH-1, CH-2"
              placeholderTextColor="#94A3B8"
              testID="census-house-number-input"
            />

            <Text style={[styles.notesLabel, themeStyles.text]}>
              Use Code
            </Text>
            <View style={styles.chipsRow}>
              {(
                [
                  'RESIDENTIAL',
                  'COMMERCIAL',
                  'RESIDENTIAL_CUM_COMMERCIAL',
                  'VACANT',
                  'OTHER',
                ] as CensusHouseUseCode[]
              ).map((uc) => (
                <TouchableOpacity
                  key={uc}
                  style={[
                    styles.chip,
                    newChUseCode === uc && styles.chipActive,
                  ]}
                  onPress={() => setNewChUseCode(uc)}
                >
                  <Text
                    style={[
                      styles.chipText,
                      newChUseCode === uc && styles.chipTextActive,
                    ]}
                  >
                    {uc.replace(/_/g, ' ')}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.notesLabel, themeStyles.text, { marginTop: 8 }]}>
              Listing State
            </Text>
            <View style={styles.chipsRow}>
              {(
                [
                  'LISTED',
                  'VACANT',
                  'NON_RESIDENTIAL',
                  'LOCKED',
                ] as CensusHouseListingState[]
              ).map((ls) => (
                <TouchableOpacity
                  key={ls}
                  style={[
                    styles.chip,
                    newChListingState === ls && styles.chipActive,
                  ]}
                  onPress={() => setNewChListingState(ls)}
                >
                  <Text
                    style={[
                      styles.chipText,
                      newChListingState === ls && styles.chipTextActive,
                    ]}
                  >
                    {ls}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.notesLabel, themeStyles.text, { marginTop: 8 }]}>
              Notes (Optional)
            </Text>
            <TextInput
              style={[styles.notesInput, themeStyles.input]}
              value={newChNotes}
              onChangeText={setNewChNotes}
              placeholder="e.g. Ground floor shop, 1st floor residence"
              placeholderTextColor="#94A3B8"
            />

            <View style={styles.modalButtonsRow}>
              <SecondaryButton
                title={t('cancel')}
                onPress={() => setAddChModalVisible(false)}
                variant="neutral"
                style={{ flex: 1 }}
              />
              <PrimaryButton
                title="Save"
                onPress={handleSaveCensusHouse}
                style={{ flex: 1 }}
                testID="save-census-house-modal-btn"
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* Building Edit Modal */}
      <Modal
        visible={buildingEditModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setBuildingEditModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, themeStyles.modalContent]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              Request Building Edit
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              Submit proposed correction for supervisor review
            </Text>

            <Text style={[styles.notesLabel, themeStyles.text]}>
              Edit Type
            </Text>
            <View style={styles.chipsRow}>
              {(['MOVE', 'DELETE', 'MERGE', 'RENUMBER'] as BuildingEditType[]).map((et) => (
                <TouchableOpacity
                  key={et}
                  style={[
                    styles.chip,
                    editType === et && styles.chipActive,
                  ]}
                  onPress={() => setEditType(et)}
                >
                  <Text
                    style={[
                      styles.chipText,
                      editType === et && styles.chipTextActive,
                    ]}
                  >
                    {et}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.notesLabel, themeStyles.text, { marginTop: 10 }]}>
              Reason *
            </Text>
            <TextInput
              style={[styles.notesInput, themeStyles.input]}
              value={editReason}
              onChangeText={setEditReason}
              placeholder="e.g. GPS pin is 20m south of actual building"
              placeholderTextColor="#94A3B8"
              multiline
              numberOfLines={3}
            />

            <View style={styles.modalButtonsRow}>
              <SecondaryButton
                title={t('cancel')}
                onPress={() => setBuildingEditModalVisible(false)}
                variant="neutral"
                style={{ flex: 1 }}
              />
              <PrimaryButton
                title="Submit Request"
                onPress={handleSaveBuildingEdit}
                style={{ flex: 1 }}
              />
            </View>
          </View>
        </View>
      </Modal>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 16,
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
  summaryHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  statusBadgesGroup: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
    justifyContent: 'flex-end',
    maxWidth: '55%',
  },
  buildingRefTitle: {
    fontSize: 20,
    fontWeight: '800',
  },
  houseNumText: {
    fontSize: 13,
    marginTop: 2,
  },
  geoInfoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.15)',
  },
  geoText: {
    fontSize: 12,
    fontWeight: '600',
  },
  sourceText: {
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  quickActionsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 12,
  },
  smallActionBtn: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
  },
  smallActionBtnText: {
    color: '#FFFFFF',
    fontSize: 11,
    fontWeight: '700',
  },
  gpsDescText: {
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 10,
  },
  gpsSuccessBox: {
    backgroundColor: '#F0FDF4',
    borderWidth: 1,
    borderColor: '#86EFAC',
    borderRadius: 8,
    padding: 10,
    marginBottom: 10,
  },
  gpsSuccessText: {
    color: '#166534',
    fontSize: 12,
    fontWeight: '700',
  },
  gpsBtn: {
    marginTop: 4,
  },
  emptyBox: {
    padding: 20,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    marginBottom: 12,
  },
  emptyIcon: {
    fontSize: 28,
    marginBottom: 6,
  },
  emptyTitle: {
    fontSize: 14,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 2,
  },
  emptySubtitle: {
    fontSize: 12,
    textAlign: 'center',
  },
  censusHousesList: {
    gap: 10,
    marginBottom: 12,
  },
  censusHouseItemCard: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
  },
  chHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  chNumberTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  chSubText: {
    fontSize: 12,
    marginTop: 2,
  },
  chNotesText: {
    fontSize: 12,
    marginTop: 6,
    fontStyle: 'italic',
  },
  chActionRow: {
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.15)',
  },
  chEnumerateBtn: {
    alignSelf: 'flex-start',
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  chEnumerateBtnText: {
    color: '#0284C7',
    fontSize: 12,
    fontWeight: '700',
  },
  addChBtn: {
    marginTop: 6,
  },
  householdsList: {
    gap: 10,
    marginBottom: 14,
  },
  householdItemCard: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
  },
  householdHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  hhNumberTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  hhMembersSub: {
    fontSize: 12,
    marginTop: 2,
  },
  hhDetailsGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginVertical: 6,
  },
  hhDetailChip: {
    fontSize: 11,
  },
  hhActionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.15)',
  },
  editBtn: {
    paddingVertical: 4,
    paddingHorizontal: 8,
  },
  editBtnText: {
    color: '#0284C7',
    fontWeight: '700',
    fontSize: 12,
  },
  deleteBtn: {
    padding: 4,
  },
  deleteBtnText: {
    fontSize: 14,
  },
  addHhBtn: {
    marginTop: 4,
  },
  revisitCard: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 8,
  },
  revisitHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  revisitReasonText: {
    fontSize: 13,
    fontWeight: '700',
  },
  revisitDateText: {
    fontSize: 11,
  },
  revisitNotesText: {
    fontSize: 12,
    marginTop: 4,
  },
  bottomActionsSection: {
    marginTop: 10,
    marginBottom: 36,
    gap: 8,
  },
  closeListingBtn: {
    backgroundColor: '#0284C7',
  },
  revisitBtn: {
    borderColor: '#DC2626',
  },
  lockBtn: {
    borderColor: '#475569',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    padding: 20,
  },
  modalBox: {
    borderRadius: 12,
    padding: 18,
    borderWidth: 1,
  },
  modalTitle: {
    fontSize: 17,
    fontWeight: '800',
    marginBottom: 4,
  },
  modalSubtitle: {
    fontSize: 13,
    marginBottom: 12,
  },
  reasonsList: {
    gap: 6,
    marginBottom: 14,
  },
  reasonOption: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#94A3B8',
  },
  reasonOptionSelected: {
    backgroundColor: '#0284C7',
    borderColor: '#0284C7',
  },
  reasonOptionText: {
    fontSize: 13,
    color: '#334155',
  },
  reasonOptionTextSelected: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  chipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 10,
  },
  chip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#CBD5E1',
    backgroundColor: 'transparent',
  },
  chipActive: {
    backgroundColor: '#0284C7',
    borderColor: '#0284C7',
  },
  chipText: {
    fontSize: 11,
    fontWeight: '600',
    color: '#64748B',
  },
  chipTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  notesLabel: {
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 4,
  },
  notesInput: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    fontSize: 13,
    textAlignVertical: 'top',
    marginBottom: 16,
  },
  modalButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
});
