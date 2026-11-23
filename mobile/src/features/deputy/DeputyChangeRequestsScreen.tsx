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
import { useNavigation } from '@react-navigation/native';
import {
  ScreenContainer,
  AppHeader,
  Card,
  PrimaryButton,
  SecondaryButton,
  StatusBadge,
} from '../../components';
import { deputyService } from '../../core/deputyService';
import { useTranslation } from '../../core/localization';
import type { DeputyNavigationProp } from '../../navigation/navigationTypes';

export function DeputyChangeRequestsScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const { t } = useTranslation();

  const [requests, setRequests] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState<'ALL' | 'OPEN' | 'RESOLVED' | 'REJECTED'>('ALL');

  // Resolution Modal State
  const [resolveModalVisible, setResolveModalVisible] = useState(false);
  const [selectedRequest, setSelectedRequest] = useState<any | null>(null);
  const [isApproving, setIsApproving] = useState(true);
  const [resolutionNotes, setResolutionNotes] = useState('');

  const fetchRequests = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);

    try {
      const param = statusFilter === 'ALL' ? undefined : statusFilter;
      const res = await deputyService.getChangeRequests(param);
      setRequests(res.items || []);
    } catch (err: any) {
      console.error('Failed to load deputy change requests:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchRequests();
  }, [fetchRequests]);

  const handleOpenResolveModal = (req: any, approve: boolean) => {
    setSelectedRequest(req);
    setIsApproving(approve);
    setResolutionNotes(approve ? 'Approved by Deputy Tahsildar' : 'Request rejected');
    setResolveModalVisible(true);
  };

  const handleConfirmResolution = async () => {
    if (!selectedRequest) return;

    try {
      await deputyService.resolveChangeRequest(selectedRequest.id, {
        approved: isApproving,
        resolution_notes: resolutionNotes.trim() || undefined,
      });

      setResolveModalVisible(false);
      Alert.alert(
        isApproving ? 'Approved' : 'Rejected',
        `Change request has been ${isApproving ? 'APPROVED' : 'REJECTED'}.`
      );
      fetchRequests();
    } catch (err: any) {
      Alert.alert('Error', err?.response?.data?.detail || err?.message || 'Resolution failed');
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
    <ScreenContainer testID="deputy-change-requests-screen" style={themeStyles.container}>
      <AppHeader
        title="Supervisor Change Requests"
        subtitle="JURISDICTION ADMINISTRATIVE DECISIONS"
        roleType="DEPUTY_TAHSILDAR"
        roleLabel="DEPUTY TAHSILDAR"
        showBack
        onBack={() => navigation.goBack()}
        testID="deputy-cr-header"
      />

      {/* Filter Row */}
      <View style={styles.filterRow}>
        {(['ALL', 'OPEN', 'RESOLVED', 'REJECTED'] as const).map((st) => (
          <TouchableOpacity
            key={st}
            style={[styles.filterChip, statusFilter === st && styles.filterChipActive]}
            onPress={() => setStatusFilter(st)}
            testID={`filter-chip-${st.toLowerCase()}`}
          >
            <Text
              style={[
                styles.filterChipText,
                statusFilter === st && styles.filterChipTextActive,
              ]}
            >
              {st}
            </Text>
          </TouchableOpacity>
        ))}
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
              onRefresh={() => fetchRequests(true)}
              colors={['#0284C7']}
            />
          }
        >
          {requests.length === 0 ? (
            <View style={[styles.emptyBox, themeStyles.itemBox]}>
              <Text style={styles.emptyIcon}>📂</Text>
              <Text style={[styles.emptyTitle, themeStyles.text]}>
                No Change Requests Found
              </Text>
              <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                Administrative change requests submitted by Supervisors will appear here.
              </Text>
            </View>
          ) : (
            requests.map((req, idx) => (
              <View
                key={req.id}
                style={[styles.requestCard, themeStyles.itemBox]}
                testID={`deputy-cr-item-${idx}`}
              >
                <View style={styles.cardHeaderRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={[styles.reqTypeTitle, themeStyles.text]}>
                      {req.request_type.replace(/_/g, ' ')}
                    </Text>
                    <Text style={[styles.reqDate, themeStyles.subtext]}>
                      {new Date(req.created_at).toLocaleString()}
                    </Text>
                  </View>
                  <StatusBadge
                    type={
                      req.status === 'RESOLVED'
                        ? 'COMPLETED'
                        : req.status === 'REJECTED'
                        ? 'LOCKED'
                        : 'IN_REVIEW'
                    }
                    label={req.status}
                  />
                </View>

                <Text style={[styles.descText, themeStyles.text]}>
                  {req.description}
                </Text>

                {req.resolution_notes && (
                  <View style={styles.resolutionBox}>
                    <Text style={styles.resolutionLabel}>Resolution Notes:</Text>
                    <Text style={styles.resolutionNotesText}>{req.resolution_notes}</Text>
                  </View>
                )}

                {req.status === 'OPEN' && (
                  <View style={styles.actionsRow}>
                    <TouchableOpacity
                      style={[styles.actionBtn, { backgroundColor: '#10B981' }]}
                      onPress={() => handleOpenResolveModal(req, true)}
                      testID={`approve-cr-btn-${idx}`}
                    >
                      <Text style={styles.actionBtnText}>✓ Approve Request</Text>
                    </TouchableOpacity>

                    <TouchableOpacity
                      style={[styles.actionBtn, { backgroundColor: '#EF4444' }]}
                      onPress={() => handleOpenResolveModal(req, false)}
                      testID={`reject-cr-btn-${idx}`}
                    >
                      <Text style={styles.actionBtnText}>✕ Reject</Text>
                    </TouchableOpacity>
                  </View>
                )}
              </View>
            ))
          )}
        </ScrollView>
      )}

      {/* Resolution Notes Modal */}
      <Modal
        visible={resolveModalVisible}
        transparent
        animationType="fade"
        onRequestClose={() => setResolveModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalBox, themeStyles.modalContent]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              {isApproving ? 'Approve Change Request' : 'Reject Change Request'}
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              {selectedRequest?.request_type.replace(/_/g, ' ')}
            </Text>

            <Text style={[styles.inputLabel, themeStyles.text]}>
              Resolution Notes / Orders *
            </Text>
            <TextInput
              style={[styles.inputBox, themeStyles.input]}
              value={resolutionNotes}
              onChangeText={setResolutionNotes}
              placeholder="Enter official resolution details..."
              placeholderTextColor="#94A3B8"
              multiline
              numberOfLines={3}
              testID="resolution-notes-input"
            />

            <View style={styles.modalButtonsRow}>
              <SecondaryButton
                title={t('cancel')}
                onPress={() => setResolveModalVisible(false)}
                variant="neutral"
                style={{ flex: 1 }}
              />
              <PrimaryButton
                title={isApproving ? 'Confirm Approval' : 'Confirm Rejection'}
                onPress={handleConfirmResolution}
                style={[
                  { flex: 1 },
                  !isApproving && { backgroundColor: '#EF4444' },
                ]}
                testID="confirm-resolve-btn"
              />
            </View>
          </View>
        </View>
      </Modal>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  filterRow: {
    flexDirection: 'row',
    backgroundColor: '#0284C7',
    paddingHorizontal: 12,
    paddingVertical: 8,
    gap: 8,
  },
  filterChip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 6,
    backgroundColor: 'rgba(255, 255, 255, 0.15)',
  },
  filterChipActive: {
    backgroundColor: '#FFFFFF',
  },
  filterChipText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
  },
  filterChipTextActive: {
    color: '#0284C7',
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
  requestCard: {
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
  reqTypeTitle: {
    fontSize: 15,
    fontWeight: '800',
  },
  reqDate: {
    fontSize: 11,
    marginTop: 2,
  },
  descText: {
    fontSize: 13,
    lineHeight: 18,
    marginVertical: 6,
  },
  resolutionBox: {
    backgroundColor: 'rgba(2, 132, 199, 0.1)',
    borderRadius: 6,
    padding: 8,
    marginTop: 6,
  },
  resolutionLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: '#0284C7',
    marginBottom: 2,
  },
  resolutionNotesText: {
    fontSize: 12,
    color: '#0284C7',
  },
  actionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.15)',
  },
  actionBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 6,
    flex: 1,
    alignItems: 'center',
  },
  actionBtnText: {
    color: '#FFFFFF',
    fontSize: 12,
    fontWeight: '700',
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
    marginBottom: 14,
  },
  modalButtonsRow: {
    flexDirection: 'row',
    gap: 10,
  },
});

