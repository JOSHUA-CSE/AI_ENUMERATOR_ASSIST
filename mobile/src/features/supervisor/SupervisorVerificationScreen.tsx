import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  Modal,
  TextInput,
  Alert,
  ActivityIndicator,
  useColorScheme,
  RefreshControl,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import {
  ScreenContainer,
  AppHeader,
  Card,
  PrimaryButton,
  SecondaryButton,
  StatusBadge,
} from '../../components';
import { supervisorService } from '../../core/supervisorService';
import { useTranslation } from '../../core/localization';
import type {
  SupervisorNavigationProp,
  SupervisorStackParamList,
} from '../../navigation/navigationTypes';

export function SupervisorVerificationScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<SupervisorNavigationProp>();
  const route = useRoute<RouteProp<SupervisorStackParamList, 'SupervisorVerification'>>();
  const { t } = useTranslation();

  const layoutId = route.params?.layoutId;

  // Active Tab: 'SUBMISSIONS' | 'EDITS' | 'CHANGE_REQUESTS'
  const [activeTab, setActiveTab] = useState<'SUBMISSIONS' | 'EDITS' | 'CHANGE_REQUESTS'>(
    'SUBMISSIONS'
  );

  const [submissions, setSubmissions] = useState<any[]>([]);
  const [buildingEdits, setBuildingEdits] = useState<any[]>([]);
  const [changeRequests, setChangeRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // Return Household Modal
  const [returnModalVisible, setReturnModalVisible] = useState(false);
  const [selectedSubId, setSelectedSubId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [supervisorComment, setSupervisorComment] = useState('');

  // New Change Request Modal
  const [crModalVisible, setCrModalVisible] = useState(false);
  const [crType, setCrType] = useState('ADDITIONAL_ENUMERATOR');
  const [crDescription, setCrDescription] = useState('');
  const [crLayoutId, setCrLayoutId] = useState(layoutId || '');

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const [subsRes, editsRes, crRes] = await Promise.all([
        supervisorService.getSubmissions().catch(() => ({ items: [], total: 0 })),
        supervisorService.getBuildingEdits().catch(() => ({ items: [], total: 0 })),
        supervisorService.getChangeRequests(layoutId).catch(() => ({ items: [], total: 0 })),
      ]);

      setSubmissions(subsRes.items || []);
      setBuildingEdits(editsRes.items || []);
      setChangeRequests(crRes.items || []);
    } catch (err: any) {
      console.error('Failed to load supervisor verification data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [layoutId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleVerifySubmission = async (id: string) => {
    try {
      await supervisorService.verifySubmission(id, 'Fieldwork verified by supervisor');
      Alert.alert('Verified', 'Household record marked as SUPERVISOR_VERIFIED.');
      fetchData();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || err?.message || 'Verification failed');
    }
  };

  const handleOpenReturnModal = (id: string) => {
    setSelectedSubId(id);
    setRejectionReason('');
    setSupervisorComment('');
    setReturnModalVisible(true);
  };

  const handleSubmitReturn = async () => {
    if (!selectedSubId || !rejectionReason.trim()) {
      Alert.alert('Validation Error', 'Rejection reason is required.');
      return;
    }

    try {
      await supervisorService.returnSubmission(
        selectedSubId,
        rejectionReason.trim(),
        supervisorComment.trim() || undefined
      );
      setReturnModalVisible(false);
      Alert.alert('Returned', 'Household returned for enumerator correction.');
      fetchData();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || err?.message || 'Return failed');
    }
  };

  const handleReviewBuildingEdit = async (id: string, approved: boolean) => {
    try {
      await supervisorService.reviewBuildingEdit(
        id,
        approved,
        approved ? 'Approved by Supervisor' : 'Rejected by Supervisor'
      );
      Alert.alert(
        approved ? 'Approved' : 'Rejected',
        `Building edit marked as ${approved ? 'APPROVED' : 'REJECTED'}.`
      );
      fetchData();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || err?.message || 'Review failed');
    }
  };

  const handleCreateChangeRequest = async () => {
    if (!crLayoutId.trim() || !crDescription.trim()) {
      Alert.alert('Validation Error', 'Layout ID and Description are required.');
      return;
    }

    try {
      await supervisorService.createChangeRequest({
        layout_id: crLayoutId.trim(),
        request_type: crType,
        description: crDescription.trim(),
      });
      setCrModalVisible(false);
      setCrDescription('');
      Alert.alert('Submitted', 'Change request submitted to Deputy Tahsildar.');
      fetchData();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || err?.message || 'Submission failed');
    }
  };

  const themeStyles = {
    container: { backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC' },
    card: { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' },
    text: { color: isDarkMode ? '#F1F5F9' : '#0F172A' },
    subtext: { color: isDarkMode ? '#94A3B8' : '#64748B' },
    itemBox: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
    input: {
      backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC',
      color: isDarkMode ? '#FFFFFF' : '#0F172A',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
    modalContent: {
      backgroundColor: isDarkMode ? '#1E293B' : '#FFFFFF',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
  };

  return (
    <ScreenContainer testID="supervisor-verification-screen" style={themeStyles.container}>
      <AppHeader
        title="Fieldwork Verification"
        subtitle="SUPERVISOR AUDIT & CHANGE REQUESTS"
        roleType="SUPERVISOR"
        roleLabel="SUPERVISOR"
        showBack
        onBack={() => navigation.goBack()}
        testID="supervisor-verification-header"
      />

      {/* Tabs Row */}
      <View style={styles.tabsRow}>
        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'SUBMISSIONS' && styles.tabButtonActive]}
          onPress={() => setActiveTab('SUBMISSIONS')}
          testID="tab-submissions"
        >
          <Text style={[styles.tabText, activeTab === 'SUBMISSIONS' && styles.tabTextActive]}>
            Submissions ({submissions.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'EDITS' && styles.tabButtonActive]}
          onPress={() => setActiveTab('EDITS')}
          testID="tab-edits"
        >
          <Text style={[styles.tabText, activeTab === 'EDITS' && styles.tabTextActive]}>
            Building Edits ({buildingEdits.length})
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.tabButton, activeTab === 'CHANGE_REQUESTS' && styles.tabButtonActive]}
          onPress={() => setActiveTab('CHANGE_REQUESTS')}
          testID="tab-change-requests"
        >
          <Text
            style={[styles.tabText, activeTab === 'CHANGE_REQUESTS' && styles.tabTextActive]}
          >
            Change Requests ({changeRequests.length})
          </Text>
        </TouchableOpacity>
      </View>

      {loading ? (
        <View style={styles.centerContainer}>
          <ActivityIndicator size="large" color="#0284C7" />
          <Text style={[styles.loadingText, themeStyles.subtext]}>{t('loading')}</Text>
        </View>
      ) : (
        <ScrollView
          style={styles.content}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => fetchData(true)}
              colors={['#0284C7']}
            />
          }
        >
          {/* TAB 1: SUBMISSIONS */}
          {activeTab === 'SUBMISSIONS' && (
            <View>
              {submissions.length === 0 ? (
                <View style={[styles.emptyBox, themeStyles.itemBox]}>
                  <Text style={styles.emptyIcon}>📋</Text>
                  <Text style={[styles.emptyTitle, themeStyles.text]}>
                    No Submissions Awaiting Verification
                  </Text>
                  <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                    Submitted household records from enumerators will appear here.
                  </Text>
                </View>
              ) : (
                submissions.map((sub, idx) => (
                  <View
                    key={sub.id}
                    style={[styles.submissionCard, themeStyles.itemBox]}
                    testID={`submission-item-${idx}`}
                  >
                    <View style={styles.cardHeaderRow}>
                      <View>
                        <Text style={[styles.itemTitle, themeStyles.text]}>
                          {sub.household_number}: {sub.head_name}
                        </Text>
                        <Text style={[styles.itemSub, themeStyles.subtext]}>
                          Members: {sub.total_members} ({sub.male_count}M • {sub.female_count}F • {sub.transgender_count}T)
                        </Text>
                      </View>
                      <StatusBadge
                        type={
                          sub.review_state === 'SUPERVISOR_VERIFIED'
                            ? 'COMPLETED'
                            : sub.review_state === 'RETURNED_FOR_CORRECTION'
                            ? 'LOCKED'
                            : 'IN_REVIEW'
                        }
                        label={sub.review_state || 'SUBMITTED'}
                      />
                    </View>

                    <View style={styles.amenitiesRow}>
                      <Text style={[styles.chipText, themeStyles.subtext]}>
                        💧 {sub.drinking_water_source || 'Water'}
                      </Text>
                      <Text style={[styles.chipText, themeStyles.subtext]}>
                        💡 {sub.lighting_source || 'Lighting'}
                      </Text>
                      <Text style={[styles.chipText, themeStyles.subtext]}>
                        🏷️ {sub.ownership_status}
                      </Text>
                    </View>

                    {sub.rejection_reason && (
                      <View style={styles.rejectionNotice}>
                        <Text style={styles.rejectionText}>
                          Returned: {sub.rejection_reason}
                        </Text>
                      </View>
                    )}

                    {sub.review_state !== 'SUPERVISOR_VERIFIED' && (
                      <View style={styles.actionsRow}>
                        <TouchableOpacity
                          style={[styles.actionBtn, { backgroundColor: '#10B981' }]}
                          onPress={() => handleVerifySubmission(sub.id)}
                          testID={`verify-sub-btn-${idx}`}
                        >
                          <Text style={styles.actionBtnText}>✓ Verify</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          style={[styles.actionBtn, { backgroundColor: '#EF4444' }]}
                          onPress={() => handleOpenReturnModal(sub.id)}
                          testID={`return-sub-btn-${idx}`}
                        >
                          <Text style={styles.actionBtnText}>✕ Return for Correction</Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </View>
                ))
              )}
            </View>
          )}

          {/* TAB 2: BUILDING EDITS */}
          {activeTab === 'EDITS' && (
            <View>
              {buildingEdits.length === 0 ? (
                <View style={[styles.emptyBox, themeStyles.itemBox]}>
                  <Text style={styles.emptyIcon}>🏢</Text>
                  <Text style={[styles.emptyTitle, themeStyles.text]}>
                    No Building Edits Pending
                  </Text>
                  <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                    Enumerator field requests (ADD, MOVE, DELETE, RENUMBER) will appear here.
                  </Text>
                </View>
              ) : (
                buildingEdits.map((edit, idx) => (
                  <View
                    key={edit.id}
                    style={[styles.submissionCard, themeStyles.itemBox]}
                    testID={`edit-item-${idx}`}
                  >
                    <View style={styles.cardHeaderRow}>
                      <View>
                        <Text style={[styles.itemTitle, themeStyles.text]}>
                          Type: {edit.edit_type}
                        </Text>
                        <Text style={[styles.itemSub, themeStyles.subtext]}>
                          Reason: {edit.reason}
                        </Text>
                      </View>
                      <StatusBadge
                        type={
                          edit.review_status === 'APPROVED'
                            ? 'COMPLETED'
                            : edit.review_status === 'REJECTED'
                            ? 'LOCKED'
                            : 'IN_REVIEW'
                        }
                        label={edit.review_status}
                      />
                    </View>

                    {edit.proposed_changes && (
                      <Text style={[styles.changesText, themeStyles.subtext]}>
                        Changes: {JSON.stringify(edit.proposed_changes)}
                      </Text>
                    )}

                    {edit.review_status === 'PENDING' && (
                      <View style={styles.actionsRow}>
                        <TouchableOpacity
                          style={[styles.actionBtn, { backgroundColor: '#10B981' }]}
                          onPress={() => handleReviewBuildingEdit(edit.id, true)}
                        >
                          <Text style={styles.actionBtnText}>✓ Approve</Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          style={[styles.actionBtn, { backgroundColor: '#EF4444' }]}
                          onPress={() => handleReviewBuildingEdit(edit.id, false)}
                        >
                          <Text style={styles.actionBtnText}>✕ Reject</Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </View>
                ))
              )}
            </View>
          )}

          {/* TAB 3: CHANGE REQUESTS */}
          {activeTab === 'CHANGE_REQUESTS' && (
            <View>
              <PrimaryButton
                title="+ Create Change Request to Deputy"
                onPress={() => setCrModalVisible(true)}
                style={styles.newCrBtn}
                testID="create-cr-btn"
              />

              {changeRequests.length === 0 ? (
                <View style={[styles.emptyBox, themeStyles.itemBox]}>
                  <Text style={styles.emptyIcon}>📝</Text>
                  <Text style={[styles.emptyTitle, themeStyles.text]}>
                    No Change Requests Logged
                  </Text>
                  <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                    Submit HLB split, merge, or enumerator requests to Deputy Tahsildar.
                  </Text>
                </View>
              ) : (
                changeRequests.map((cr, idx) => (
                  <View
                    key={cr.id}
                    style={[styles.submissionCard, themeStyles.itemBox]}
                    testID={`cr-item-${idx}`}
                  >
                    <View style={styles.cardHeaderRow}>
                      <View>
                        <Text style={[styles.itemTitle, themeStyles.text]}>
                          {cr.request_type.replace(/_/g, ' ')}
                        </Text>
                        <Text style={[styles.itemSub, themeStyles.subtext]}>
                          {cr.description}
                        </Text>
                      </View>
                      <StatusBadge
                        type={
                          cr.status === 'RESOLVED'
                            ? 'COMPLETED'
                            : cr.status === 'REJECTED'
                            ? 'LOCKED'
                            : 'IN_REVIEW'
                        }
                        label={cr.status}
                      />
                    </View>

                    {cr.resolution_notes && (
                      <Text style={[styles.resolutionText, { color: '#0284C7' }]}>
                        Resolution: {cr.resolution_notes}
                      </Text>
                    )}
                  </View>
                ))
              )}
            </View>
          )}
        </ScrollView>
      )}

      {/* Return for Correction Modal */}
      <Modal
        visible={returnModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setReturnModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, themeStyles.modalContent]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              Return Record for Correction
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              Provide required corrections for the enumerator
            </Text>

            <Text style={[styles.inputLabel, themeStyles.text]}>
              Rejection Reason *
            </Text>
            <TextInput
              style={[styles.inputBox, themeStyles.input]}
              value={rejectionReason}
              onChangeText={setRejectionReason}
              placeholder="e.g. Member counts do not match gender breakdown"
              placeholderTextColor="#94A3B8"
              testID="return-reason-input"
            />

            <Text style={[styles.inputLabel, themeStyles.text, { marginTop: 8 }]}>
              Supervisor Instructions (Optional)
            </Text>
            <TextInput
              style={[styles.inputBox, themeStyles.input]}
              value={supervisorComment}
              onChangeText={setSupervisorComment}
              placeholder="e.g. Revisit household and verify age of head"
              placeholderTextColor="#94A3B8"
              multiline
              numberOfLines={3}
            />

            <View style={styles.modalButtonsRow}>
              <SecondaryButton
                title={t('cancel')}
                onPress={() => setReturnModalVisible(false)}
                variant="neutral"
                style={{ flex: 1 }}
              />
              <PrimaryButton
                title="Return Record"
                onPress={handleSubmitReturn}
                style={[{ flex: 1, backgroundColor: '#EF4444' }]}
                testID="confirm-return-btn"
              />
            </View>
          </View>
        </View>
      </Modal>

      {/* New Change Request Modal */}
      <Modal
        visible={crModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setCrModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, themeStyles.modalContent]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              Request Fieldwork Change
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              Submit administrative request to Deputy Tahsildar
            </Text>

            <Text style={[styles.inputLabel, themeStyles.text]}>
              Layout ID *
            </Text>
            <TextInput
              style={[styles.inputBox, themeStyles.input]}
              value={crLayoutId}
              onChangeText={setCrLayoutId}
              placeholder="Enter Layout UUID"
              placeholderTextColor="#94A3B8"
            />

            <Text style={[styles.inputLabel, themeStyles.text, { marginTop: 8 }]}>
              Request Type
            </Text>
            <View style={styles.crTypesRow}>
              {[
                'ADDITIONAL_ENUMERATOR',
                'HLB_SPLIT',
                'HLB_MERGE',
                'BOUNDARY_DISPUTE',
                'TECHNICAL_ISSUE',
              ].map((tCode) => (
                <TouchableOpacity
                  key={tCode}
                  style={[
                    styles.crTypeChip,
                    crType === tCode && styles.crTypeChipActive,
                  ]}
                  onPress={() => setCrType(tCode)}
                >
                  <Text
                    style={[
                      styles.crTypeChipText,
                      crType === tCode && styles.crTypeChipTextActive,
                    ]}
                  >
                    {tCode.replace(/_/g, ' ')}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={[styles.inputLabel, themeStyles.text, { marginTop: 8 }]}>
              Description / Justification *
            </Text>
            <TextInput
              style={[styles.inputBox, themeStyles.input]}
              value={crDescription}
              onChangeText={setCrDescription}
              placeholder="Explain reasons for this administrative change..."
              placeholderTextColor="#94A3B8"
              multiline
              numberOfLines={3}
            />

            <View style={styles.modalButtonsRow}>
              <SecondaryButton
                title={t('cancel')}
                onPress={() => setCrModalVisible(false)}
                variant="neutral"
                style={{ flex: 1 }}
              />
              <PrimaryButton
                title="Submit to Deputy"
                onPress={handleCreateChangeRequest}
                style={{ flex: 1 }}
                testID="submit-cr-btn"
              />
            </View>
          </View>
        </View>
      </Modal>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  tabsRow: {
    flexDirection: 'row',
    backgroundColor: '#0284C7',
    paddingHorizontal: 8,
    paddingVertical: 6,
    gap: 4,
  },
  tabButton: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 6,
  },
  tabButtonActive: {
    backgroundColor: 'rgba(255, 255, 255, 0.25)',
  },
  tabText: {
    color: 'rgba(255, 255, 255, 0.8)',
    fontSize: 12,
    fontWeight: '600',
  },
  tabTextActive: {
    color: '#FFFFFF',
    fontWeight: '800',
  },
  content: {
    padding: 16,
  },
  centerContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  emptyBox: {
    padding: 24,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    marginTop: 20,
  },
  emptyIcon: {
    fontSize: 32,
    marginBottom: 8,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 4,
    textAlign: 'center',
  },
  emptySubtitle: {
    fontSize: 12,
    textAlign: 'center',
  },
  submissionCard: {
    padding: 14,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 12,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 6,
  },
  itemTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  itemSub: {
    fontSize: 12,
    marginTop: 2,
  },
  amenitiesRow: {
    flexDirection: 'row',
    gap: 12,
    marginVertical: 6,
  },
  chipText: {
    fontSize: 12,
  },
  rejectionNotice: {
    backgroundColor: '#FEF2F2',
    padding: 6,
    borderRadius: 4,
    marginTop: 4,
  },
  rejectionText: {
    color: '#DC2626',
    fontSize: 12,
    fontWeight: '600',
  },
  changesText: {
    fontSize: 11,
    fontFamily: 'monospace',
    marginTop: 4,
  },
  resolutionText: {
    fontSize: 12,
    fontWeight: '700',
    marginTop: 6,
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.15)',
  },
  actionBtn: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  newCrBtn: {
    marginBottom: 14,
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
  inputLabel: {
    fontSize: 13,
    fontWeight: '700',
    marginBottom: 4,
  },
  inputBox: {
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    fontSize: 13,
    marginBottom: 10,
  },
  crTypesRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 10,
  },
  crTypeChip: {
    paddingVertical: 6,
    paddingHorizontal: 8,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#CBD5E1',
  },
  crTypeChipActive: {
    backgroundColor: '#0284C7',
    borderColor: '#0284C7',
  },
  crTypeChipText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#64748B',
  },
  crTypeChipTextActive: {
    color: '#FFFFFF',
  },
  modalButtonsRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 10,
  },
});

