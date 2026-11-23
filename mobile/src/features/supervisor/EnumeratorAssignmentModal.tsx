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
import {
  enumeratorService,
  EnumeratorSummary,
  EnumeratorAssignment,
} from '../../core/enumeratorService';
import { useTranslation } from '../../core/localization';

export interface HlbTargetInfo {
  id: string;
  block_code: string;
  name?: string;
  actual_building_count: number;
  target_building_count?: number;
}

interface EnumeratorAssignmentModalProps {
  visible: boolean;
  hlb: HlbTargetInfo | null;
  layoutId: string;
  layoutName?: string;
  onClose: () => void;
  onSuccess: () => void;
}

export function EnumeratorAssignmentModal({
  visible,
  hlb,
  layoutId,
  layoutName,
  onClose,
  onSuccess,
}: EnumeratorAssignmentModalProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { t } = useTranslation();

  const [enumerators, setEnumerators] = useState<EnumeratorSummary[]>([]);
  const [currentAssignment, setCurrentAssignment] = useState<EnumeratorAssignment | null>(null);
  const [selectedEnumeratorId, setSelectedEnumeratorId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [assigning, setAssigning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [step, setStep] = useState<'SELECT' | 'CONFIRM' | 'SUCCESS'>('SELECT');
  const [assignedResult, setAssignedResult] = useState<EnumeratorAssignment | null>(null);

  useEffect(() => {
    if (visible && hlb) {
      setStep('SELECT');
      setError(null);
      setSelectedEnumeratorId(null);
      setAssignedResult(null);
      loadModalData();
    }
  }, [visible, hlb]);

  const loadModalData = async () => {
    if (!hlb) return;
    setLoading(true);
    setError(null);
    try {
      const [enumRes, assignRes] = await Promise.all([
        enumeratorService.getEnumerators(),
        enumeratorService.getHlbEnumeratorAssignment(hlb.id),
      ]);
      setEnumerators(enumRes.items || []);
      setCurrentAssignment(assignRes);
      if (assignRes?.enumerator_id) {
        setSelectedEnumeratorId(assignRes.enumerator_id);
      }
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSelectEnumerator = (id: string, isAvailable: boolean) => {
    if (!isAvailable && id !== currentAssignment?.enumerator_id) return;
    setSelectedEnumeratorId(id);
    setError(null);
  };

  const handleProceedToConfirm = () => {
    if (!selectedEnumeratorId) {
      setError('Please select an enumerator');
      return;
    }
    setStep('CONFIRM');
  };

  const handleConfirmAssignment = async () => {
    if (!hlb || !selectedEnumeratorId) return;
    setAssigning(true);
    setError(null);
    try {
      const result = await enumeratorService.assignEnumerator(
        hlb.id,
        selectedEnumeratorId
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

  const selectedEnumerator = enumerators.find(
    (e) => e.id === selectedEnumeratorId
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
    disabledItemBox: {
      backgroundColor: isDarkMode ? '#1F1F1F' : '#F0F0F0',
      borderColor: isDarkMode ? '#333333' : '#E0E0E0',
      opacity: 0.6,
    },
    divider: { borderBottomColor: isDarkMode ? '#333333' : '#EEEEEE' },
    noticeBox: {
      backgroundColor: isDarkMode ? '#1E293B' : '#E8F4FD',
      borderColor: isDarkMode ? '#3B82F6' : '#90CAF9',
    },
  };

  if (!hlb) return <></>;

  return (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={onClose}
      testID="enumerator-assignment-modal"
    >
      <View style={[styles.modalOverlay, themeStyles.overlay]}>
        <View style={[styles.modalContent, themeStyles.container]}>
          {/* Header */}
          <View style={[styles.modalHeader, themeStyles.divider]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              {step === 'CONFIRM'
                ? t('confirm_enumerator_assignment')
                : step === 'SUCCESS'
                ? t('enumerator_assigned_success')
                : currentAssignment
                ? t('change_enumerator')
                : t('assign_enumerator')}
            </Text>
            <TouchableOpacity
              onPress={onClose}
              style={styles.closeBtn}
              testID="close-enumerator-modal-btn"
            >
              <Text style={[styles.closeBtnText, themeStyles.subtext]}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.modalBody} showsVerticalScrollIndicator={false}>
            {error && <ErrorMessage message={error} testID="assignment-modal-error" />}

            {/* Target HLB Summary Card */}
            <Card style={styles.hlbSummaryCard}>
              <View style={styles.hlbHeaderRow}>
                <View>
                  <Text style={styles.hlbCodeText}>{hlb.block_code}</Text>
                  {layoutName ? (
                    <Text style={styles.layoutSubText}>{layoutName}</Text>
                  ) : null}
                </View>
                <View style={styles.buildingsBadge}>
                  <Text style={styles.buildingsBadgeText}>
                    {hlb.actual_building_count} {t('detected_buildings')}
                  </Text>
                </View>
              </View>

              {hlb.target_building_count ? (
                <View style={styles.targetRow}>
                  <Text style={[styles.targetLabel, themeStyles.subtext]}>
                    {t('target_buildings_label')}: {hlb.target_building_count}
                  </Text>
                </View>
              ) : null}

              {currentAssignment?.enumerator_name && step === 'SELECT' && (
                <View style={styles.currentAssignRow}>
                  <Text style={[styles.currentAssignLabel, themeStyles.subtext]}>
                    Current:
                  </Text>
                  <Text style={[styles.currentAssignName, themeStyles.text]}>
                    {currentAssignment.enumerator_name} ({currentAssignment.enumerator_username})
                  </Text>
                  <StatusBadge type="ACTIVE" label={t('assigned')} />
                </View>
              )}
            </Card>

            {loading ? (
              <View style={styles.loadingContainer}>
                <ActivityIndicator size="large" color="#0066CC" />
                <Text style={[styles.loadingText, themeStyles.subtext]}>
                  {t('loading')}
                </Text>
              </View>
            ) : step === 'SELECT' ? (
              /* STEP 1: Select Enumerator */
              <View style={styles.selectStepContainer}>
                <Text style={[styles.sectionTitle, themeStyles.text]}>
                  {t('select_enumerator')}
                </Text>
                <Text style={[styles.sectionDesc, themeStyles.subtext]}>
                  {t('select_enumerator_desc')}
                </Text>

                {enumerators.length === 0 ? (
                  <View style={styles.emptyContainer}>
                    <Text style={[styles.emptyText, themeStyles.subtext]}>
                      {t('no_eligible_enumerators')}
                    </Text>
                  </View>
                ) : (
                  <View style={styles.listContainer}>
                    {enumerators.map((enumItem) => {
                      const isSelected = selectedEnumeratorId === enumItem.id;
                      const isCurrentlyAssignedHere =
                        currentAssignment?.enumerator_id === enumItem.id;
                      const isAvailable =
                        enumItem.availability === 'AVAILABLE' ||
                        isCurrentlyAssignedHere;

                      return (
                        <TouchableOpacity
                          key={enumItem.id}
                          style={[
                            styles.enumeratorItem,
                            themeStyles.itemBox,
                            isSelected && themeStyles.selectedItemBox,
                            !isAvailable && themeStyles.disabledItemBox,
                          ]}
                          onPress={() =>
                            handleSelectEnumerator(enumItem.id, isAvailable)
                          }
                          disabled={!isAvailable}
                          testID={`enumerator-option-${enumItem.username}`}
                        >
                          <View style={styles.radioContainer}>
                            <View
                              style={[
                                styles.radioCircle,
                                isSelected && styles.radioCircleSelected,
                              ]}
                            >
                              {isSelected && <View style={styles.radioDot} />}
                            </View>
                          </View>

                          <View style={styles.enumInfo}>
                            <Text style={[styles.enumName, themeStyles.text]}>
                              {enumItem.name}
                            </Text>
                            <Text style={[styles.enumUsername, themeStyles.subtext]}>
                              @{enumItem.username}
                              {enumItem.phone ? ` • ${enumItem.phone}` : ''}
                            </Text>
                            {enumItem.assigned_hlb_code && !isCurrentlyAssignedHere && (
                              <Text style={styles.assignedToText}>
                                Assigned to {enumItem.assigned_hlb_code}
                              </Text>
                            )}
                          </View>

                          <View style={styles.badgeContainer}>
                            {enumItem.availability === 'AVAILABLE' ? (
                              <StatusBadge
                                type="ACTIVE"
                                label={t('available')}
                              />
                            ) : enumItem.availability === 'INACTIVE' ? (
                              <StatusBadge
                                type="INACTIVE"
                                label={t('inactive')}
                              />
                            ) : (
                              <StatusBadge
                                type="ASSIGNED"
                                label={t('assigned')}
                              />
                            )}
                          </View>
                        </TouchableOpacity>
                      );
                    })}
                  </View>
                )}
              </View>
            ) : step === 'CONFIRM' ? (
              /* STEP 2: Confirm Assignment */
              <View style={styles.confirmStepContainer}>
                <View style={[styles.noticeBox, themeStyles.noticeBox]}>
                  <Text style={styles.noticeTitle}>
                    {t('confirm_enumerator_assignment')}
                  </Text>
                  <Text style={styles.noticeText}>
                    {t('confirm_assignment_notice')}
                  </Text>
                </View>

                <Card style={styles.confirmCard}>
                  <Text style={[styles.confirmSectionLabel, themeStyles.subtext]}>
                    Target HLB
                  </Text>
                  <Text style={[styles.confirmMainValue, themeStyles.text]}>
                    {hlb.block_code}
                  </Text>
                  <Text style={[styles.confirmSubValue, themeStyles.subtext]}>
                    {hlb.actual_building_count} {t('detected_buildings')}
                  </Text>

                  <View style={[styles.cardDivider, themeStyles.divider]} />

                  <Text style={[styles.confirmSectionLabel, themeStyles.subtext]}>
                    Primary Enumerator
                  </Text>
                  <Text style={[styles.confirmMainValue, themeStyles.text]}>
                    {selectedEnumerator?.name}
                  </Text>
                  <Text style={[styles.confirmSubValue, themeStyles.subtext]}>
                    @{selectedEnumerator?.username}
                    {selectedEnumerator?.phone ? ` • ${selectedEnumerator.phone}` : ''}
                  </Text>

                  {currentAssignment &&
                    currentAssignment.enumerator_id !== selectedEnumeratorId && (
                      <View style={styles.reassignAlertBox}>
                        <Text style={styles.reassignAlertText}>
                          Note: Previous assignment to{' '}
                          {currentAssignment.enumerator_name || 'former enumerator'}{' '}
                          will be CANCELLED and archived in assignment history.
                        </Text>
                      </View>
                    )}
                </Card>
              </View>
            ) : (
              /* STEP 3: Success Screen */
              <View style={styles.successStepContainer}>
                <View style={styles.successIconCircle}>
                  <Text style={styles.successCheckmark}>✓</Text>
                </View>
                <Text style={[styles.successTitle, themeStyles.text]}>
                  {t('enumerator_assigned_success')}
                </Text>
                <Text style={[styles.successDesc, themeStyles.subtext]}>
                  {assignedResult?.enumerator_name} has been assigned as Primary Enumerator for {hlb.block_code}.
                </Text>

                <Card style={styles.successDetailsCard}>
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>HLB Code:</Text>
                    <Text style={[styles.detailValue, themeStyles.text]}>
                      {hlb.block_code}
                    </Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>Enumerator:</Text>
                    <Text style={[styles.detailValue, themeStyles.text]}>
                      {assignedResult?.enumerator_name}
                    </Text>
                  </View>
                  <View style={styles.detailRow}>
                    <Text style={[styles.detailLabel, themeStyles.subtext]}>Status:</Text>
                    <StatusBadge type="ACTIVE" label={t('assigned')} />
                  </View>
                </Card>
              </View>
            )}
          </ScrollView>

          {/* Action Buttons */}
          <View style={[styles.modalFooter, themeStyles.divider]}>
            {step === 'SELECT' ? (
              <View style={styles.footerBtnRow}>
                <SecondaryButton
                  title={t('cancel')}
                  onPress={onClose}
                  style={styles.halfBtn}
                  testID="cancel-assignment-btn"
                />
                <PrimaryButton
                  title="CONTINUE"
                  onPress={handleProceedToConfirm}
                  disabled={!selectedEnumeratorId || loading}
                  style={styles.halfBtn}
                  testID="proceed-confirm-assignment-btn"
                />
              </View>
            ) : step === 'CONFIRM' ? (
              <View style={styles.footerBtnRow}>
                <SecondaryButton
                  title={t('back')}
                  onPress={() => setStep('SELECT')}
                  disabled={assigning}
                  style={styles.halfBtn}
                  testID="back-to-select-btn"
                />
                <PrimaryButton
                  title={assigning ? 'ASSIGNING...' : 'CONFIRM ASSIGNMENT'}
                  onPress={handleConfirmAssignment}
                  loading={assigning}
                  disabled={assigning}
                  style={styles.halfBtn}
                  testID="confirm-assignment-btn"
                />
              </View>
            ) : (
              <PrimaryButton
                title={t('close')}
                onPress={onClose}
                testID="done-assignment-btn"
              />
            )}
          </View>
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
    maxWidth: 520,
    maxHeight: '88%',
    borderRadius: 12,
    overflow: 'hidden',
    elevation: 8,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 12,
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
    padding: 4,
  },
  closeBtnText: {
    fontSize: 18,
    fontWeight: '600',
  },
  modalBody: {
    paddingHorizontal: 20,
    paddingVertical: 16,
  },
  hlbSummaryCard: {
    padding: 14,
    marginBottom: 16,
    borderRadius: 8,
    borderLeftWidth: 4,
    borderLeftColor: '#0066CC',
  },
  hlbHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  hlbCodeText: {
    fontSize: 18,
    fontWeight: '800',
    color: '#0066CC',
  },
  layoutSubText: {
    fontSize: 13,
    color: '#666666',
    marginTop: 2,
  },
  buildingsBadge: {
    backgroundColor: '#E8F5E9',
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  buildingsBadgeText: {
    color: '#2E7D32',
    fontWeight: '700',
    fontSize: 12,
  },
  targetRow: {
    marginTop: 6,
  },
  targetLabel: {
    fontSize: 12,
  },
  currentAssignRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: '#EEEEEE',
  },
  currentAssignLabel: {
    fontSize: 12,
    marginRight: 6,
  },
  currentAssignName: {
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  loadingContainer: {
    paddingVertical: 40,
    alignItems: 'center',
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  selectStepContainer: {
    marginBottom: 8,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  sectionDesc: {
    fontSize: 13,
    marginBottom: 12,
  },
  emptyContainer: {
    padding: 24,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: 14,
    textAlign: 'center',
  },
  listContainer: {
    gap: 8,
  },
  enumeratorItem: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1.5,
  },
  radioContainer: {
    marginRight: 12,
  },
  radioCircle: {
    width: 20,
    height: 20,
    borderRadius: 10,
    borderWidth: 2,
    borderColor: '#9E9E9E',
    alignItems: 'center',
    justifyContent: 'center',
  },
  radioCircleSelected: {
    borderColor: '#0066CC',
  },
  radioDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: '#0066CC',
  },
  enumInfo: {
    flex: 1,
  },
  enumName: {
    fontSize: 15,
    fontWeight: '700',
  },
  enumUsername: {
    fontSize: 12,
    marginTop: 2,
  },
  assignedToText: {
    fontSize: 11,
    color: '#E65100',
    marginTop: 2,
    fontWeight: '600',
  },
  badgeContainer: {
    marginLeft: 8,
  },
  confirmStepContainer: {
    marginBottom: 8,
  },
  noticeBox: {
    padding: 14,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 16,
  },
  noticeTitle: {
    fontSize: 15,
    fontWeight: '700',
    color: '#0066CC',
    marginBottom: 4,
  },
  noticeText: {
    fontSize: 13,
    color: '#333333',
    lineHeight: 18,
  },
  confirmCard: {
    padding: 16,
  },
  confirmSectionLabel: {
    fontSize: 12,
    textTransform: 'uppercase',
    fontWeight: '600',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  confirmMainValue: {
    fontSize: 17,
    fontWeight: '800',
  },
  confirmSubValue: {
    fontSize: 13,
    marginTop: 2,
  },
  cardDivider: {
    borderBottomWidth: 1,
    marginVertical: 12,
  },
  reassignAlertBox: {
    marginTop: 12,
    padding: 10,
    backgroundColor: '#FFF3E0',
    borderRadius: 6,
    borderLeftWidth: 3,
    borderLeftColor: '#F57C00',
  },
  reassignAlertText: {
    fontSize: 12,
    color: '#E65100',
    fontWeight: '600',
  },
  successStepContainer: {
    alignItems: 'center',
    paddingVertical: 16,
  },
  successIconCircle: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#E8F5E9',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  successCheckmark: {
    fontSize: 32,
    color: '#2E7D32',
    fontWeight: 'bold',
  },
  successTitle: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 8,
    textAlign: 'center',
  },
  successDesc: {
    fontSize: 14,
    textAlign: 'center',
    marginBottom: 20,
    lineHeight: 20,
  },
  successDetailsCard: {
    width: '100%',
    padding: 14,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 6,
  },
  detailLabel: {
    fontSize: 13,
  },
  detailValue: {
    fontSize: 14,
    fontWeight: '700',
  },
  modalFooter: {
    paddingHorizontal: 20,
    paddingVertical: 14,
    borderTopWidth: 1,
  },
  footerBtnRow: {
    flexDirection: 'row',
    gap: 12,
  },
  halfBtn: {
    flex: 1,
  },
});
