import React, { useState, useEffect } from 'react';
import {
  Modal,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  ScrollView,
  useColorScheme,
  ActivityIndicator,
} from 'react-native';
import {
  Card,
  PrimaryButton,
  SecondaryButton,
  StatusBadge,
  ErrorMessage,
} from '../../components';
import { extractErrorMessage } from '../../core/apiClient';
import { LayoutSummary } from '../../core/layoutService';
import {
  supervisorService,
  SupervisorSummary,
  SupervisorAssignment,
} from '../../core/supervisorService';
import { useTranslation } from '../../core/localization';

interface SupervisorAssignmentModalProps {
  visible: boolean;
  layout: LayoutSummary | null;
  areaName?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function SupervisorAssignmentModal({
  visible,
  layout,
  areaName,
  onClose,
  onSuccess,
}: SupervisorAssignmentModalProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { t } = useTranslation();

  const [supervisors, setSupervisors] = useState<SupervisorSummary[]>([]);
  const [currentAssignment, setCurrentAssignment] = useState<SupervisorAssignment | null>(null);
  const [selectedSupervisorId, setSelectedSupervisorId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'SELECT' | 'CONFIRM' | 'SUCCESS'>('SELECT');
  const [assignedResult, setAssignedResult] = useState<SupervisorAssignment | null>(null);

  useEffect(() => {
    if (visible && layout) {
      setStep('SELECT');
      setError(null);
      setSelectedSupervisorId(null);
      setAssignedResult(null);
      loadModalData();
    }
  }, [visible, layout]);

  const loadModalData = async () => {
    if (!layout) return;
    setLoading(true);
    setError(null);
    try {
      const [supRes, assignRes] = await Promise.all([
        supervisorService.getSupervisors(),
        supervisorService.getSupervisorAssignment(layout.id),
      ]);
      setSupervisors(supRes.items || []);
      setCurrentAssignment(assignRes);
      if (assignRes?.supervisor_id) {
        setSelectedSupervisorId(assignRes.supervisor_id);
      }
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSupervisor = (id: string) => {
    setSelectedSupervisorId(id);
    setError(null);
  };

  const handleProceedToConfirm = () => {
    if (!selectedSupervisorId) {
      setError('Please select a supervisor');
      return;
    }
    setStep('CONFIRM');
  };

  const handleConfirmAssignment = async () => {
    if (!layout || !selectedSupervisorId) return;
    setAssigning(true);
    setError(null);
    try {
      const result = await supervisorService.assignSupervisor(
        layout.id,
        selectedSupervisorId
      );
      setAssignedResult(result);
      setStep('SUCCESS');
      onSuccess();
    } catch (err: any) {
      setError(extractErrorMessage(err));
      setStep('SELECT');
    } finally {
      setAssigning(false);
    }
  };

  const selectedSupervisor = supervisors.find(
    (s) => s.id === selectedSupervisorId
  );

  const themeStyles = {
    overlay: { backgroundColor: 'rgba(0, 0, 0, 0.7)' },
    container: { backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF' },
    text: { color: isDarkMode ? '#FFFFFF' : '#333333' },
    subtext: { color: isDarkMode ? '#A0A0A0' : '#666666' },
    highlight: { color: isDarkMode ? '#90CAF9' : '#0066CC' },
    itemBox: {
      backgroundColor: isDarkMode ? '#2A2A2A' : '#F5F7FA',
      borderColor: isDarkMode ? '#444444' : '#E0E0E0',
    },
    selectedItemBox: {
      backgroundColor: isDarkMode ? '#1A365D' : '#E3F2FD',
      borderColor: isDarkMode ? '#64B5F6' : '#0066CC',
    },
    divider: { borderBottomColor: isDarkMode ? '#333333' : '#EEEEEE' },
    noticeBox: {
      backgroundColor: isDarkMode ? '#1E293B' : '#E8F4FD',
      borderColor: isDarkMode ? '#3B82F6' : '#90CAF9',
    },
  };

  if (!layout) return <></>;

  const detectedBuildings =
    layout.total_buildings || layout.actual_building_count || 0;
  const hlbCount = layout.hlb_count || layout.expected_hlb_count || 0;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      testID="supervisor-assignment-modal"
    >
      <View style={[styles.modalOverlay, themeStyles.overlay]}>
        <View style={[styles.modalContent, themeStyles.container]}>
          {/* Header */}
          <View style={[styles.modalHeader, themeStyles.divider]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              {step === 'CONFIRM'
                ? t('confirm_assignment')
                : step === 'SUCCESS'
                ? t('assignment_success')
                : t('assign_supervisor')}
            </Text>
            <TouchableOpacity
              onPress={onClose}
              style={styles.closeBtn}
              testID="close-assignment-modal-btn"
            >
              <Text style={[styles.closeBtnText, themeStyles.subtext]}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
            {error && <ErrorMessage message={error} testID="assignment-modal-error" />}

            {loading ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#0066CC" />
                <Text style={[styles.loadingText, themeStyles.subtext]}>
                  Loading supervisors...
                </Text>
              </View>
            ) : step === 'SUCCESS' ? (
              /* Success Step */
              <View style={styles.successContainer} testID="assignment-success-container">
                <Text style={styles.successIcon}>✓</Text>
                <Text style={[styles.successTitle, themeStyles.text]}>
                  {t('assignment_success')}
                </Text>

                <View style={[styles.summaryCard, themeStyles.itemBox]}>
                  <Text style={[styles.summaryRow, themeStyles.text]}>
                    <Text style={styles.bold}>{t('village_label')}: </Text>
                    {areaName || layout.name}
                  </Text>
                  <Text style={[styles.summaryRow, themeStyles.text]}>
                    <Text style={styles.bold}>{t('supervisor_label')}: </Text>
                    {assignedResult?.supervisor_name || selectedSupervisor?.name}
                  </Text>
                  <Text style={[styles.summaryRow, themeStyles.text]}>
                    <Text style={styles.bold}>{t('status_label')}: </Text>
                    <Text style={{ color: '#2E7D32', fontWeight: 'bold' }}>ACTIVE</Text>
                  </Text>
                </View>

                <PrimaryButton
                  title={t('close')}
                  onPress={onClose}
                  style={{ marginTop: 20 }}
                  testID="assignment-success-close-btn"
                />
              </View>
            ) : step === 'CONFIRM' ? (
              /* Confirmation Step */
              <View style={styles.confirmContainer} testID="assignment-confirm-container">
                <Card title="Assignment Details" testID="assignment-confirm-card">
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>{t('village_label')}:</Text>
                    <Text style={[styles.detailValue, themeStyles.text]}>{areaName || layout.name}</Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>Layout ID:</Text>
                    <Text style={[styles.detailValue, themeStyles.highlight]}>
                      {layout.id.substring(0, 8).toUpperCase()}
                    </Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>{t('hlbs_label')}:</Text>
                    <Text style={[styles.detailValue, themeStyles.text]}>{hlbCount}</Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>{t('detected_buildings')}:</Text>
                    <Text style={[styles.detailValue, themeStyles.text]}>{detectedBuildings}</Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>{t('status_label')}:</Text>
                    <StatusBadge type="APPROVED" label="APPROVED" />
                  </View>
                  <View style={[styles.detailRow, { marginTop: 10, borderTopWidth: 1, borderTopColor: '#EEEEEE', paddingTop: 10 }]}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>{t('supervisor_label')}:</Text>
                    <Text style={[styles.detailValue, { fontWeight: 'bold', color: '#0066CC' }]}>
                      {selectedSupervisor?.name}
                    </Text>
                  </View>
                </Card>

                {/* Important Notice */}
                <View style={[styles.noticeContainer, themeStyles.noticeBox]}>
                  <Text style={styles.noticeIcon}>ℹ️</Text>
                  <Text style={[styles.noticeText, themeStyles.text]}>
                    {t('supervisor_access_notice')}
                  </Text>
                </View>

                <View style={styles.actionButtons}>
                  <View style={{ flex: 1 }}>
                    <SecondaryButton
                      title={t('back')}
                      onPress={() => setStep('SELECT')}
                      disabled={assigning}
                      testID="assignment-confirm-back-btn"
                    />
                  </View>
                  <View style={{ flex: 1.5 }}>
                    <PrimaryButton
                      title={assigning ? 'ASSIGNING...' : t('confirm_assignment')}
                      onPress={handleConfirmAssignment}
                      loading={assigning}
                      disabled={assigning}
                      testID="confirm-assignment-submit-btn"
                    />
                  </View>
                </View>
              </View>
            ) : (
              /* Selection Step */
              <View testID="assignment-select-container">
                {/* Layout Context Card */}
                <View style={[styles.layoutSummaryBox, themeStyles.itemBox]}>
                  <View style={styles.summaryTopRow}>
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.layoutTitle, themeStyles.text]}>
                        {layout.name}
                      </Text>
                      <Text style={[styles.areaCodeSubtitle, themeStyles.subtext]}>
                        📍 {areaName || 'Administrative Area'} • ID: {layout.id.substring(0, 8).toUpperCase()}
                      </Text>
                    </View>
                    <StatusBadge
                      type={layout.status === 'APPROVED' ? 'APPROVED' : 'IN_REVIEW'}
                      label={layout.status}
                    />
                  </View>

                  <View style={styles.quickMetricsRow}>
                    <View style={styles.quickMetric}>
                      <Text style={[styles.quickMetricVal, themeStyles.text]}>{hlbCount}</Text>
                      <Text style={[styles.quickMetricLbl, themeStyles.subtext]}>HLBs</Text>
                    </View>
                    <View style={styles.quickMetric}>
                      <Text style={[styles.quickMetricVal, themeStyles.text]}>{detectedBuildings}</Text>
                      <Text style={[styles.quickMetricLbl, themeStyles.subtext]}>Buildings</Text>
                    </View>
                    <View style={styles.quickMetric}>
                      <Text style={[styles.quickMetricVal, { color: '#2E7D32' }]}>
                        {layout.active_version_number ? `v${layout.active_version_number}` : 'Approved'}
                      </Text>
                      <Text style={[styles.quickMetricLbl, themeStyles.subtext]}>Version</Text>
                    </View>
                  </View>
                </View>

                {/* Current Active Assignment Status (if already assigned) */}
                {currentAssignment && (
                  <View style={[styles.currentSupervisorBox, themeStyles.noticeBox]} testID="current-assignment-card">
                    <View style={{ flex: 1 }}>
                      <Text style={[styles.currentSupervisorTitle, themeStyles.subtext]}>
                        {t('current_supervisor')}
                      </Text>
                      <Text style={[styles.currentSupervisorName, themeStyles.text]}>
                        👤 {currentAssignment.supervisor_name || 'Supervisor'}
                      </Text>
                    </View>
                    <StatusBadge type="ACTIVE" label={currentAssignment.status} />
                  </View>
                )}

                {/* Important Access Notice */}
                <View style={[styles.noticeContainer, themeStyles.noticeBox]}>
                  <Text style={styles.noticeIcon}>ℹ️</Text>
                  <Text style={[styles.noticeText, themeStyles.text]}>
                    {t('supervisor_access_notice')}
                  </Text>
                </View>

                {/* Supervisor Selector List */}
                <Text style={[styles.sectionTitle, themeStyles.text]}>
                  {currentAssignment ? t('change_supervisor') : t('select_supervisor')}
                </Text>

                {supervisors.length === 0 ? (
                  <Text style={[styles.emptyText, themeStyles.subtext]}>
                    {t('no_supervisors_found')}
                  </Text>
                ) : (
                  supervisors.map((supervisor) => {
                    const isSelected = selectedSupervisorId === supervisor.id;
                    const isCurrent = currentAssignment?.supervisor_id === supervisor.id;

                    return (
                      <TouchableOpacity
                        key={supervisor.id}
                        style={[
                          styles.supervisorOption,
                          themeStyles.itemBox,
                          isSelected && themeStyles.selectedItemBox,
                        ]}
                        onPress={() => handleSelectSupervisor(supervisor.id)}
                        testID={`supervisor-option-${supervisor.id}`}
                      >
                        <View style={styles.radioContainer}>
                          <View
                            style={[
                              styles.radioOuter,
                              isSelected && styles.radioOuterSelected,
                            ]}
                          >
                            {isSelected && <View style={styles.radioInner} />}
                          </View>
                        </View>

                        <View style={styles.supervisorInfo}>
                          <View style={styles.supervisorNameRow}>
                            <Text
                              style={[
                                styles.supervisorName,
                                themeStyles.text,
                                isSelected && { fontWeight: '700' },
                              ]}
                            >
                              {supervisor.name}
                            </Text>
                            {isCurrent && (
                              <View style={styles.currentBadge}>
                                <Text style={styles.currentBadgeText}>CURRENT</Text>
                              </View>
                            )}
                          </View>
                          <Text style={[styles.supervisorMeta, themeStyles.subtext]}>
                            ID: {supervisor.username} • Assigned Layouts: {supervisor.assigned_layouts_count}
                          </Text>
                        </View>

                        <StatusBadge type="ACTIVE" label={supervisor.status} />
                      </TouchableOpacity>
                    );
                  })
                )}

                {/* Bottom Actions */}
                <View style={styles.actionButtons}>
                  <View style={{ flex: 1 }}>
                    <SecondaryButton
                      title={t('cancel')}
                      onPress={onClose}
                      testID="assignment-select-cancel-btn"
                    />
                  </View>
                  <View style={{ flex: 1.5 }}>
                    <PrimaryButton
                      title={currentAssignment ? t('change_supervisor') : t('assign_layout_btn')}
                      onPress={handleProceedToConfirm}
                      disabled={!selectedSupervisorId}
                      testID="proceed-to-confirm-assignment-btn"
                    />
                  </View>
                </View>
              </View>
            )}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 16,
  },
  modalContent: {
    width: '100%',
    maxHeight: '90%',
    borderRadius: 16,
    overflow: 'hidden',
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 10,
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  closeBtn: {
    padding: 6,
  },
  closeBtnText: {
    fontSize: 20,
    fontWeight: '600',
  },
  modalBody: {
    padding: 20,
  },
  loadingContainer: {
    paddingVertical: 40,
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  layoutSummaryBox: {
    borderRadius: 12,
    padding: 14,
    marginBottom: 14,
    borderWidth: 1,
  },
  summaryTopRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  layoutTitle: {
    fontSize: 16,
    fontWeight: '700',
  },
  areaCodeSubtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  quickMetricsRow: {
    flexDirection: 'row',
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.2)',
    paddingTop: 8,
  },
  quickMetric: {
    flex: 1,
    alignItems: 'center',
  },
  quickMetricVal: {
    fontSize: 15,
    fontWeight: '700',
  },
  quickMetricLbl: {
    fontSize: 11,
    marginTop: 1,
  },
  currentSupervisorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 14,
  },
  currentSupervisorTitle: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  currentSupervisorName: {
    fontSize: 14,
    fontWeight: '700',
    marginTop: 2,
  },
  noticeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 10,
    borderWidth: 1,
    marginBottom: 16,
  },
  noticeIcon: {
    fontSize: 18,
    marginRight: 10,
  },
  noticeText: {
    flex: 1,
    fontSize: 13,
    lineHeight: 18,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 10,
  },
  emptyText: {
    fontSize: 13,
    fontStyle: 'italic',
    paddingVertical: 12,
  },
  supervisorOption: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    borderRadius: 12,
    borderWidth: 1.5,
    marginBottom: 10,
  },
  radioContainer: {
    marginRight: 12,
  },
  radioOuter: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#9E9E9E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioOuterSelected: {
    borderColor: '#0066CC',
  },
  radioInner: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#0066CC',
  },
  supervisorInfo: {
    flex: 1,
  },
  supervisorNameRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  supervisorName: {
    fontSize: 15,
  },
  currentBadge: {
    backgroundColor: '#E8F5E9',
    borderRadius: 4,
    paddingHorizontal: 6,
    paddingVertical: 2,
    marginLeft: 8,
  },
  currentBadgeText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#2E7D32',
  },
  supervisorMeta: {
    fontSize: 12,
    marginTop: 2,
  },
  actionButtons: {
    flexDirection: 'row',
    gap: 12,
    marginTop: 18,
    marginBottom: 10,
  },
  confirmContainer: {
    paddingVertical: 4,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  detailLabel: {
    fontSize: 14,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '600',
  },
  bold: {
    fontWeight: '700',
  },
  successContainer: {
    alignItems: 'center',
    paddingVertical: 20,
  },
  successIcon: {
    fontSize: 48,
    color: '#2E7D32',
    marginBottom: 12,
  },
  successTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 16,
    textAlign: 'center',
  },
  summaryCard: {
    width: '100%',
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
  },
  summaryRow: {
    fontSize: 14,
    lineHeight: 22,
  },
});
