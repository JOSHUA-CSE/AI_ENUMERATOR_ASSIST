import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  View,
  Text,
  Modal,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  useColorScheme,
} from 'react-native';
import { useTranslation } from '../core/localization';
import { offlineVoiceService } from '../core/voice/offlineVoiceService';
import type {
  VoiceAssistantState,
  VoiceLanguage,
  HouseholdVoiceExtraction,
  ExtractedField,
} from '../core/voice/voiceTypes';
import type { OwnershipStatus } from '../core/sqlite/types';

export interface VoiceAssistantModalProps {
  visible: boolean;
  onClose: () => void;
  onConfirmExtraction: (data: {
    totalMembers?: number;
    maleCount?: number;
    femaleCount?: number;
    transgenderCount?: number;
    ownershipStatus?: OwnershipStatus;
    drinkingWater?: string;
    lightingSource?: string;
    latrineFacility?: string;
    headName?: string;
  }) => void;
  defaultLanguage?: VoiceLanguage;
  testID?: string;
}

export function VoiceAssistantModal({
  visible,
  onClose,
  onConfirmExtraction,
  defaultLanguage = 'ta',
  testID = 'voice-assistant-modal',
}: VoiceAssistantModalProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { t } = useTranslation();

  const [language, setLanguage] = useState<VoiceLanguage>(defaultLanguage);
  const [state, setState] = useState<VoiceAssistantState>('IDLE');
  const [recognizedText, setRecognizedText] = useState<string>('');
  const [extraction, setExtraction] = useState<HouseholdVoiceExtraction | null>(
    null
  );
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Editable fields in review card
  const [editTotal, setEditTotal] = useState<string>('');
  const [editMale, setEditMale] = useState<string>('');
  const [editFemale, setEditFemale] = useState<string>('');
  const [editTrans, setEditTrans] = useState<string>('');
  const [editOwnership, setEditOwnership] = useState<OwnershipStatus | null>(null);
  const [editWater, setEditWater] = useState<string>('');
  const [editLighting, setEditLighting] = useState<string>('');
  const [editLatrine, setEditLatrine] = useState<string>('');
  const [editHeadName, setEditHeadName] = useState<string>('');

  // Sync extraction result into editable state
  const syncExtractionToEditableState = useCallback(
    (ext: HouseholdVoiceExtraction) => {
      setExtraction(ext);
      setEditTotal(ext.totalMembers?.value != null ? String(ext.totalMembers.value) : '');
      setEditMale(ext.maleCount?.value != null ? String(ext.maleCount.value) : '');
      setEditFemale(ext.femaleCount?.value != null ? String(ext.femaleCount.value) : '');
      setEditTrans(ext.transgenderCount?.value != null ? String(ext.transgenderCount.value) : '');
      setEditOwnership(ext.ownershipStatus?.value || null);
      setEditWater(ext.drinkingWater?.value || '');
      setEditLighting(ext.lightingSource?.value || '');
      setEditLatrine(ext.latrineFacility?.value || '');
      setEditHeadName(ext.headName?.value || '');
    },
    []
  );

  // Clean up on modal hide
  useEffect(() => {
    if (!visible) {
      offlineVoiceService.cancelListening();
      setState('IDLE');
      setRecognizedText('');
      setExtraction(null);
      setErrorMsg(null);
    }
  }, [visible]);

  const handleStartListening = async () => {
    setErrorMsg(null);
    setState('LISTENING');

    const started = await offlineVoiceService.startListening(
      { language, timeoutMs: 12000 },
      {
        onSpeechStart: () => {
          setState('LISTENING');
        },
        onSpeechRecognized: (res) => {
          setRecognizedText(res.text);
        },
        onSpeechEnd: (res) => {
          setRecognizedText(res.text);
          const ext = offlineVoiceService.extractFields(res.text);
          syncExtractionToEditableState(ext);
          setState(
            ext.overallStatus === 'NEEDS_REVIEW'
              ? 'NEEDS_REVIEW'
              : 'RESULT_READY'
          );
        },
        onError: (err) => {
          setState('ERROR');
          if (err.code === 'PERMISSION_DENIED') {
            setErrorMsg(t('mic_permission_denied'));
          } else if (err.code === 'NO_SPEECH_DETECTED') {
            setErrorMsg(t('no_speech_detected'));
          } else {
            setErrorMsg(t('could_not_understand'));
          }
        },
      }
    );

    if (!started) {
      setState('ERROR');
      setErrorMsg(t('mic_permission_required'));
    }
  };

  const handleStopListening = async () => {
    await offlineVoiceService.stopListening();
  };

  const handleConfirm = () => {
    const payload: {
      totalMembers?: number;
      maleCount?: number;
      femaleCount?: number;
      transgenderCount?: number;
      ownershipStatus?: OwnershipStatus;
      drinkingWater?: string;
      lightingSource?: string;
      latrineFacility?: string;
      headName?: string;
    } = {};

    if (editTotal.trim()) payload.totalMembers = parseInt(editTotal, 10);
    if (editMale.trim()) payload.maleCount = parseInt(editMale, 10);
    if (editFemale.trim()) payload.femaleCount = parseInt(editFemale, 10);
    if (editTrans.trim()) payload.transgenderCount = parseInt(editTrans, 10);
    if (editOwnership) payload.ownershipStatus = editOwnership;
    if (editWater.trim()) payload.drinkingWater = editWater.trim();
    if (editLighting.trim()) payload.lightingSource = editLighting.trim();
    if (editLatrine.trim()) payload.latrineFacility = editLatrine.trim();
    if (editHeadName.trim()) payload.headName = editHeadName.trim();

    onConfirmExtraction(payload);
    onClose();
  };

  const getConfidenceBadgeColor = (conf?: string) => {
    if (conf === 'CONFIRMED') return '#10B981'; // Green
    if (conf === 'UNCERTAIN') return '#F59E0B'; // Amber
    return '#94A3B8'; // Slate grey
  };

  const theme = {
    bg: isDarkMode ? '#0F172A' : '#FFFFFF',
    card: isDarkMode ? '#1E293B' : '#F8FAFC',
    border: isDarkMode ? '#334155' : '#E2E8F0',
    text: isDarkMode ? '#F8FAFC' : '#0F172A',
    subtext: isDarkMode ? '#94A3B8' : '#64748B',
    accent: '#0284C7',
    inputBg: isDarkMode ? '#0F172A' : '#FFFFFF',
  };

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent={true}
      onRequestClose={onClose}
      testID={testID}
    >
      <View style={styles.modalOverlay}>
        <View style={[styles.modalContainer, { backgroundColor: theme.bg }]}>
          {/* Header */}
          <View style={[styles.headerRow, { borderBottomColor: theme.border }]}>
            <View style={styles.headerTitleGroup}>
              <Text style={styles.headerMicIcon}>🎙️</Text>
              <Text style={[styles.headerTitle, { color: theme.text }]}>
                {t('voice_assistant')}
              </Text>
            </View>
            <TouchableOpacity
              onPress={onClose}
              style={styles.closeBtn}
              testID="close-voice-modal-btn"
            >
              <Text style={[styles.closeBtnText, { color: theme.subtext }]}>
                ✕
              </Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.scrollArea} showsVerticalScrollIndicator={false}>
            {/* Language Selector */}
            <View style={styles.langSelectorRow} testID="voice-language-selector">
              {(
                [
                  { code: 'ta', label: 'தமிழ்' },
                  { code: 'en', label: 'English' },
                  { code: 'mixed', label: 'Tanglish' },
                ] as const
              ).map((lang) => (
                <TouchableOpacity
                  key={lang.code}
                  style={[
                    styles.langChip,
                    language === lang.code
                      ? styles.langChipActive
                      : { backgroundColor: theme.card, borderColor: theme.border },
                  ]}
                  onPress={() => setLanguage(lang.code)}
                  testID={`lang-chip-${lang.code}`}
                >
                  <Text
                    style={[
                      styles.langChipText,
                      language === lang.code
                        ? styles.langChipTextActive
                        : { color: theme.subtext },
                    ]}
                  >
                    {lang.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            {/* Microphone Interaction Box */}
            <View style={[styles.micCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
              <TouchableOpacity
                style={[
                  styles.micButton,
                  state === 'LISTENING' && styles.micButtonListening,
                  state === 'PROCESSING' && styles.micButtonProcessing,
                ]}
                onPress={
                  state === 'LISTENING'
                    ? handleStopListening
                    : handleStartListening
                }
                testID="mic-trigger-btn"
              >
                {state === 'PROCESSING' ? (
                  <ActivityIndicator size="large" color="#FFFFFF" />
                ) : (
                  <Text style={styles.micButtonIcon}>
                    {state === 'LISTENING' ? '⏹' : '🎤'}
                  </Text>
                )}
              </TouchableOpacity>

              <Text style={[styles.stateLabel, { color: theme.text }]} testID="voice-state-label">
                {state === 'LISTENING'
                  ? t('listening')
                  : state === 'PROCESSING'
                  ? t('processing_speech')
                  : state === 'RESULT_READY' || state === 'NEEDS_REVIEW'
                  ? t('review')
                  : t('tap_to_speak')}
              </Text>

              <Text style={[styles.hintText, { color: theme.subtext }]}>
                {t('speak_household_hint')}
              </Text>
            </View>

            {/* Error Message Banner */}
            {errorMsg && (
              <View style={styles.errorBox} testID="voice-error-banner">
                <Text style={styles.errorIcon}>⚠️</Text>
                <Text style={styles.errorText}>{errorMsg}</Text>
              </View>
            )}

            {/* Recognized Speech Box */}
            {recognizedText ? (
              <View style={[styles.recognizedCard, { backgroundColor: theme.card, borderColor: theme.border }]}>
                <Text style={[styles.sectionHeading, { color: theme.subtext }]}>
                  {t('recognized_text')}
                </Text>
                <Text style={[styles.recognizedTextContent, { color: theme.text }]} testID="recognized-speech-text">
                  "{recognizedText}"
                </Text>
              </View>
            ) : null}

            {/* Extracted Information Review */}
            {extraction && (
              <View style={[styles.reviewCard, { backgroundColor: theme.card, borderColor: theme.border }]} testID="extracted-fields-card">
                <View style={styles.reviewHeaderRow}>
                  <Text style={[styles.reviewTitle, { color: theme.text }]}>
                    {t('extracted_info')}
                  </Text>
                  <View
                    style={[
                      styles.statusPill,
                      {
                        backgroundColor:
                          extraction.overallStatus === 'CONFIRMED'
                            ? 'rgba(16, 185, 129, 0.15)'
                            : 'rgba(245, 158, 11, 0.15)',
                      },
                    ]}
                  >
                    <Text
                      style={[
                        styles.statusPillText,
                        {
                          color:
                            extraction.overallStatus === 'CONFIRMED'
                              ? '#10B981'
                              : '#F59E0B',
                        },
                      ]}
                      testID="overall-extraction-status"
                    >
                      {extraction.overallStatus === 'CONFIRMED'
                        ? `✓ ${t('confirmed')}`
                        : `⚠️ ${t('uncertain')}`}
                    </Text>
                  </View>
                </View>

                {extraction.overallStatus === 'NEEDS_REVIEW' && (
                  <View style={styles.warningNotice} testID="uncertain-warning-banner">
                    <Text style={styles.warningNoticeText}>
                      ⚠️ {t('uncertain_voice_info')}
                    </Text>
                  </View>
                )}

                {/* Field: Head Name */}
                <View style={styles.fieldRow}>
                  <View style={styles.fieldMeta}>
                    <Text style={[styles.fieldTitle, { color: theme.text }]}>
                      {t('head_of_household')}
                    </Text>
                    {extraction.headName && (
                      <Text
                        style={[
                          styles.confTag,
                          { color: getConfidenceBadgeColor(extraction.headName.confidence) },
                        ]}
                      >
                        {extraction.headName.confidence}
                      </Text>
                    )}
                  </View>
                  <TextInput
                    style={[styles.fieldInput, { backgroundColor: theme.inputBg, color: theme.text, borderColor: theme.border }]}
                    value={editHeadName}
                    onChangeText={setEditHeadName}
                    placeholder="Head Name"
                    placeholderTextColor="#94A3B8"
                    testID="voice-edit-head-name"
                  />
                </View>

                {/* Field: Total Members */}
                <View style={styles.fieldRow}>
                  <View style={styles.fieldMeta}>
                    <Text style={[styles.fieldTitle, { color: theme.text }]}>
                      {t('total_members_label')}
                    </Text>
                    {extraction.totalMembers && (
                      <Text
                        style={[
                          styles.confTag,
                          { color: getConfidenceBadgeColor(extraction.totalMembers.confidence) },
                        ]}
                        testID="total-members-confidence-tag"
                      >
                        {extraction.totalMembers.confidence}
                      </Text>
                    )}
                  </View>
                  <TextInput
                    style={[styles.fieldInput, { backgroundColor: theme.inputBg, color: theme.text, borderColor: theme.border }]}
                    value={editTotal}
                    onChangeText={setEditTotal}
                    keyboardType="number-pad"
                    placeholder="Total"
                    placeholderTextColor="#94A3B8"
                    testID="voice-edit-total-members"
                  />
                </View>

                {/* Breakdown: Male / Female / Transgender */}
                <View style={styles.genderGrid}>
                  <View style={styles.genderCol}>
                    <Text style={[styles.genderLabel, { color: theme.subtext }]}>
                      {t('male_members')}
                    </Text>
                    <TextInput
                      style={[styles.fieldInput, { backgroundColor: theme.inputBg, color: theme.text, borderColor: theme.border }]}
                      value={editMale}
                      onChangeText={setEditMale}
                      keyboardType="number-pad"
                      placeholder="0"
                      placeholderTextColor="#94A3B8"
                      testID="voice-edit-male-count"
                    />
                  </View>
                  <View style={styles.genderCol}>
                    <Text style={[styles.genderLabel, { color: theme.subtext }]}>
                      {t('female_members')}
                    </Text>
                    <TextInput
                      style={[styles.fieldInput, { backgroundColor: theme.inputBg, color: theme.text, borderColor: theme.border }]}
                      value={editFemale}
                      onChangeText={setEditFemale}
                      keyboardType="number-pad"
                      placeholder="0"
                      placeholderTextColor="#94A3B8"
                      testID="voice-edit-female-count"
                    />
                  </View>
                  <View style={styles.genderCol}>
                    <Text style={[styles.genderLabel, { color: theme.subtext }]}>
                      {t('transgender_members')}
                    </Text>
                    <TextInput
                      style={[styles.fieldInput, { backgroundColor: theme.inputBg, color: theme.text, borderColor: theme.border }]}
                      value={editTrans}
                      onChangeText={setEditTrans}
                      keyboardType="number-pad"
                      placeholder="0"
                      placeholderTextColor="#94A3B8"
                      testID="voice-edit-trans-count"
                    />
                  </View>
                </View>

                {/* Field: Ownership Status */}
                <View style={styles.fieldRow}>
                  <View style={styles.fieldMeta}>
                    <Text style={[styles.fieldTitle, { color: theme.text }]}>
                      {t('ownership_type')}
                    </Text>
                    {extraction.ownershipStatus && (
                      <Text
                        style={[
                          styles.confTag,
                          { color: getConfidenceBadgeColor(extraction.ownershipStatus.confidence) },
                        ]}
                      >
                        {extraction.ownershipStatus.confidence}
                      </Text>
                    )}
                  </View>
                  <View style={styles.segmentedRow}>
                    {(['OWNED', 'RENTED', 'OTHER'] as OwnershipStatus[]).map((st) => (
                      <TouchableOpacity
                        key={st}
                        style={[
                          styles.segBtn,
                          editOwnership === st
                            ? styles.segBtnActive
                            : { backgroundColor: theme.inputBg, borderColor: theme.border },
                        ]}
                        onPress={() => setEditOwnership(st)}
                        testID={`voice-ownership-${st.toLowerCase()}-btn`}
                      >
                        <Text
                          style={[
                            styles.segBtnText,
                            editOwnership === st
                              ? styles.segBtnTextActive
                              : { color: theme.subtext },
                          ]}
                        >
                          {st === 'OWNED' ? t('owned') : st === 'RENTED' ? t('rented') : t('other_ownership')}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                {/* Field: Drinking Water */}
                {editWater ? (
                  <View style={styles.fieldRow}>
                    <Text style={[styles.fieldTitle, { color: theme.text }]}>
                      {t('drinking_water')}
                    </Text>
                    <TextInput
                      style={[styles.fieldInput, { backgroundColor: theme.inputBg, color: theme.text, borderColor: theme.border }]}
                      value={editWater}
                      onChangeText={setEditWater}
                      testID="voice-edit-water"
                    />
                  </View>
                ) : null}

                {/* Field: Latrine Facility */}
                {editLatrine ? (
                  <View style={styles.fieldRow}>
                    <Text style={[styles.fieldTitle, { color: theme.text }]}>
                      {t('latrine_facility_label')}
                    </Text>
                    <TextInput
                      style={[styles.fieldInput, { backgroundColor: theme.inputBg, color: theme.text, borderColor: theme.border }]}
                      value={editLatrine}
                      onChangeText={setEditLatrine}
                      testID="voice-edit-latrine"
                    />
                  </View>
                ) : null}
              </View>
            )}
          </ScrollView>

          {/* Action Footer */}
          <View style={[styles.footerRow, { borderTopColor: theme.border }]}>
            {extraction ? (
              <>
                <TouchableOpacity
                  style={styles.confirmButton}
                  onPress={handleConfirm}
                  testID="confirm-voice-extraction-btn"
                >
                  <Text style={styles.confirmButtonText}>
                    ✓ {t('confirm_voice_entry')}
                  </Text>
                </TouchableOpacity>

                <TouchableOpacity
                  style={[styles.cancelButton, { borderColor: theme.border }]}
                  onPress={onClose}
                  testID="cancel-voice-extraction-btn"
                >
                  <Text style={[styles.cancelButtonText, { color: theme.subtext }]}>
                    {t('cancel_voice')}
                  </Text>
                </TouchableOpacity>
              </>
            ) : (
              <TouchableOpacity
                style={[styles.cancelButtonFull, { borderColor: theme.border }]}
                onPress={onClose}
                testID="close-voice-modal-btn-bottom"
              >
                <Text style={[styles.cancelButtonText, { color: theme.subtext }]}>
                  {t('cancel_voice')}
                </Text>
              </TouchableOpacity>
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
    backgroundColor: 'rgba(0, 0, 0, 0.65)',
    justifyContent: 'flex-end',
  },
  modalContainer: {
    borderTopLeftRadius: 20,
    borderTopRightRadius: 20,
    maxHeight: '90%',
    minHeight: '60%',
    paddingBottom: 20,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingVertical: 16,
    borderBottomWidth: 1,
  },
  headerTitleGroup: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  headerMicIcon: {
    fontSize: 22,
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: '700',
  },
  closeBtn: {
    padding: 6,
  },
  closeBtnText: {
    fontSize: 18,
    fontWeight: 'bold',
  },
  scrollArea: {
    paddingHorizontal: 20,
    paddingTop: 14,
  },
  langSelectorRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 10,
    marginBottom: 16,
  },
  langChip: {
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 20,
    borderWidth: 1,
  },
  langChipActive: {
    backgroundColor: '#0284C7',
    borderColor: '#0284C7',
  },
  langChipText: {
    fontSize: 13,
    fontWeight: '600',
  },
  langChipTextActive: {
    color: '#FFFFFF',
  },
  micCard: {
    alignItems: 'center',
    paddingVertical: 20,
    paddingHorizontal: 16,
    borderRadius: 16,
    borderWidth: 1,
    marginBottom: 16,
  },
  micButton: {
    width: 76,
    height: 76,
    borderRadius: 38,
    backgroundColor: '#0284C7',
    justifyContent: 'center',
    alignItems: 'center',
    shadowColor: '#0284C7',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.35,
    shadowRadius: 8,
    elevation: 6,
    marginBottom: 12,
  },
  micButtonListening: {
    backgroundColor: '#EF4444',
    shadowColor: '#EF4444',
  },
  micButtonProcessing: {
    backgroundColor: '#F59E0B',
  },
  micButtonIcon: {
    fontSize: 32,
    color: '#FFFFFF',
  },
  stateLabel: {
    fontSize: 16,
    fontWeight: '700',
    marginBottom: 4,
  },
  hintText: {
    fontSize: 12,
    textAlign: 'center',
  },
  errorBox: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderColor: '#F87171',
    borderWidth: 1,
    borderRadius: 10,
    padding: 12,
    marginBottom: 14,
    gap: 8,
  },
  errorIcon: {
    fontSize: 18,
  },
  errorText: {
    color: '#DC2626',
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  recognizedCard: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 14,
    marginBottom: 14,
  },
  sectionHeading: {
    fontSize: 11,
    fontWeight: '700',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 6,
  },
  recognizedTextContent: {
    fontSize: 14,
    fontStyle: 'italic',
    lineHeight: 20,
  },
  reviewCard: {
    borderRadius: 14,
    borderWidth: 1,
    padding: 16,
    marginBottom: 20,
  },
  reviewHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  reviewTitle: {
    fontSize: 15,
    fontWeight: '700',
  },
  statusPill: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
  },
  statusPillText: {
    fontSize: 12,
    fontWeight: '700',
  },
  warningNotice: {
    backgroundColor: 'rgba(245, 158, 11, 0.1)',
    borderColor: 'rgba(245, 158, 11, 0.3)',
    borderWidth: 1,
    borderRadius: 8,
    padding: 10,
    marginBottom: 14,
  },
  warningNoticeText: {
    color: '#D97706',
    fontSize: 12,
    fontWeight: '600',
  },
  fieldRow: {
    marginBottom: 12,
  },
  fieldMeta: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  fieldTitle: {
    fontSize: 13,
    fontWeight: '600',
  },
  confTag: {
    fontSize: 11,
    fontWeight: '700',
  },
  fieldInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 14,
  },
  genderGrid: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 12,
  },
  genderCol: {
    flex: 1,
  },
  genderLabel: {
    fontSize: 11,
    fontWeight: '600',
    marginBottom: 4,
  },
  segmentedRow: {
    flexDirection: 'row',
    gap: 8,
  },
  segBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  segBtnActive: {
    backgroundColor: '#0284C7',
    borderColor: '#0284C7',
  },
  segBtnText: {
    fontSize: 12,
    fontWeight: '600',
  },
  segBtnTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  footerRow: {
    flexDirection: 'row',
    paddingHorizontal: 20,
    paddingTop: 14,
    borderTopWidth: 1,
    gap: 12,
  },
  confirmButton: {
    flex: 2,
    backgroundColor: '#0284C7',
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  confirmButtonText: {
    color: '#FFFFFF',
    fontSize: 14,
    fontWeight: '700',
  },
  cancelButton: {
    flex: 1,
    borderWidth: 1,
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelButtonFull: {
    flex: 1,
    borderWidth: 1,
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
  },
  cancelButtonText: {
    fontSize: 14,
    fontWeight: '600',
  },
});
