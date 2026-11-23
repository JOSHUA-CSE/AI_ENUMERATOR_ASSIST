import React, { useState, useEffect } from 'react';
import {
  StyleSheet,
  Text,
  View,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Alert,
  useColorScheme,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import {
  AppHeader,
  Card,
  PrimaryButton,
  SecondaryButton,
  ScreenContainer,
  StatusBadge,
  VoiceAssistantModal,
} from '../../components';
import { useAuthStore } from '../../core/authStore';
import { fieldworkService } from '../../core/fieldworkService';
import { useTranslation } from '../../core/localization';
import type {
  EnumeratorNavigationProp,
  EnumeratorStackParamList,
} from '../../navigation/navigationTypes';
import type {
  OfflineHouseholdRecord,
  OfflineCensusHouseRecord,
  OwnershipStatus,
} from '../../core/sqlite/types';

interface PersonDraft {
  id: string;
  name: string;
  person_number: number;
  relationship_to_head: string;
  sex: string;
  age: number | null;
}

export function HouseholdFormScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<EnumeratorNavigationProp>();
  const route = useRoute<RouteProp<EnumeratorStackParamList, 'HouseholdForm'>>();
  const { user } = useAuthStore();
  const { t, language } = useTranslation();

  const { buildingId, hlbId, householdId, censusHouseId, buildingReference } =
    route.params as any;

  const [voiceModalVisible, setVoiceModalVisible] = useState<boolean>(false);
  const [voiceUsed, setVoiceUsed] = useState<boolean>(false);

  const [recordId, setRecordId] = useState<string>(
    householdId || `hh-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`
  );
  const [selectedCensusHouseId, setSelectedCensusHouseId] = useState<string | null>(
    censusHouseId || null
  );
  const [censusHouses, setCensusHouses] = useState<OfflineCensusHouseRecord[]>([]);

  const [householdNumber, setHouseholdNumber] = useState<string>('HH-1');
  const [headName, setHeadName] = useState<string>('');
  const [totalMembers, setTotalMembers] = useState<string>('1');
  const [maleCount, setMaleCount] = useState<string>('1');
  const [femaleCount, setFemaleCount] = useState<string>('0');
  const [transgenderCount, setTransgenderCount] = useState<string>('0');
  const [ownershipStatus, setOwnershipStatus] = useState<OwnershipStatus>('OWNED');
  const [drinkingWater, setDrinkingWater] = useState<string>('Tap Water');
  const [lightingSource, setLightingSource] = useState<string>('Electricity');
  const [latrineFacility, setLatrineFacility] = useState<string>('Yes');
  const [currentStatus, setCurrentStatus] = useState<'DRAFT' | 'COMPLETED'>('DRAFT');

  // Phase II Person Demographic Roster
  const [persons, setPersons] = useState<PersonDraft[]>([]);

  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState<boolean>(false);

  // Load census houses & existing household / persons
  useEffect(() => {
    try {
      const chList = fieldworkService.getCensusHouses(buildingId);
      setCensusHouses(chList || []);
      if (!selectedCensusHouseId && chList && chList.length > 0) {
        setSelectedCensusHouseId(chList[0].id);
      }
    } catch {
      setCensusHouses([]);
    }

    if (householdId) {
      const detail = fieldworkService.getBuildingDetail(buildingId);
      const existing = detail.households.find((h) => h.id === householdId);
      if (existing) {
        setRecordId(existing.id);
        if (existing.census_house_id) {
          setSelectedCensusHouseId(existing.census_house_id);
        }
        setHouseholdNumber(existing.household_number);
        setHeadName(existing.head_name);
        setTotalMembers(String(existing.total_members));
        setMaleCount(String(existing.male_count));
        setFemaleCount(String(existing.female_count));
        setTransgenderCount(String(existing.transgender_count));
        setOwnershipStatus(existing.ownership_status);
        setDrinkingWater(existing.drinking_water_source || 'Tap Water');
        setLightingSource(existing.lighting_source || 'Electricity');
        setLatrineFacility(existing.latrine_facility || 'Yes');
        setCurrentStatus(existing.status);

        // Load persons
        try {
          const personList = fieldworkService.getPersons(householdId);
          if (personList && personList.length > 0) {
            setPersons(
              personList.map((p) => ({
                id: p.id,
                name: p.name,
                person_number: p.person_number,
                relationship_to_head: p.relationship_to_head,
                sex: p.sex,
                age: p.age ?? null,
              }))
            );
          }
        } catch {
          // fallback
        }
      }
    } else {
      // Auto-assign next household number for new records in this building
      const detail = fieldworkService.getBuildingDetail(buildingId);
      const count = detail.households.length;
      setHouseholdNumber(`HH-${count + 1}`);
    }
  }, [householdId, buildingId]);

  const handleAddPerson = () => {
    const nextNum = persons.length + 1;
    const newPerson: PersonDraft = {
      id: `p-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      name: nextNum === 1 && headName ? headName : `Member ${nextNum}`,
      person_number: nextNum,
      relationship_to_head: nextNum === 1 ? 'HEAD' : 'MEMBER',
      sex: 'MALE',
      age: 25,
    };
    setPersons([...persons, newPerson]);
  };

  const handleRemovePerson = (idx: number) => {
    const updated = persons.filter((_, i) => i !== idx);
    setPersons(updated);
  };

  const validateForm = (): boolean => {
    setErrorMessage(null);

    if (!headName.trim()) {
      setErrorMessage(t('head_name_required'));
      return false;
    }

    const total = parseInt(totalMembers, 10) || 0;
    const male = parseInt(maleCount, 10) || 0;
    const female = parseInt(femaleCount, 10) || 0;
    const trans = parseInt(transgenderCount, 10) || 0;

    if (total <= 0) {
      setErrorMessage('Total members must be at least 1.');
      return false;
    }

    if (male + female + trans !== total) {
      setErrorMessage(t('member_count_mismatch'));
      return false;
    }

    return true;
  };

  const handleSave = (asCompleted: boolean) => {
    if (asCompleted) {
      if (!validateForm()) {
        return;
      }
    } else {
      // For draft, at least require non-empty head name or household number
      if (!headName.trim() && !householdNumber.trim()) {
        setErrorMessage('Please enter at least the Head Name or Household Number to save a draft.');
        return;
      }
    }

    setSaving(true);
    try {
      const now = new Date().toISOString();
      const total = parseInt(totalMembers, 10) || 0;
      const male = parseInt(maleCount, 10) || 0;
      const female = parseInt(femaleCount, 10) || 0;
      const trans = parseInt(transgenderCount, 10) || 0;

      const record: OfflineHouseholdRecord = {
        id: recordId,
        building_id: buildingId,
        census_house_id: selectedCensusHouseId || null,
        hlb_id: hlbId,
        enumerator_id: user?.id || 'enumerator-local',
        household_number: householdNumber.trim() || 'HH-1',
        head_name: headName.trim() || 'Unknown Draft',
        total_members: total,
        male_count: male,
        female_count: female,
        transgender_count: trans,
        ownership_status: ownershipStatus,
        drinking_water_source: drinkingWater,
        lighting_source: lightingSource,
        latrine_facility: latrineFacility,
        data_json: null,
        questionnaire_version: '1.0',
        review_state: asCompleted ? 'SUBMITTED' : 'DRAFT',
        status: asCompleted ? 'COMPLETED' : 'DRAFT',
        source: voiceUsed ? 'VOICE' : 'FORM',
        created_at: now,
        updated_at: now,
      };

      fieldworkService.saveHousehold(record);

      // Save Phase II Persons
      if (persons.length > 0) {
        persons.forEach((p, idx) => {
          fieldworkService.savePerson({
            id: p.id,
            household_id: recordId,
            person_number: idx + 1,
            name: p.name || `Member ${idx + 1}`,
            relationship_to_head: p.relationship_to_head || (idx === 0 ? 'HEAD' : 'MEMBER'),
            sex: p.sex || 'MALE',
            age: p.age,
            questionnaire_version: '2.0',
            review_state: asCompleted ? 'SUBMITTED' : 'DRAFT',
            created_at: now,
            updated_at: now,
          });
        });
      }

      Alert.alert(
        asCompleted ? t('completed_badge') : t('draft_badge'),
        asCompleted ? t('household_completed') : t('draft_saved'),
        [{ text: 'OK', onPress: () => navigation.goBack() }]
      );
    } catch (err: any) {
      setErrorMessage(err?.message || 'Failed to save household record in SQLite.');
    } finally {
      setSaving(false);
    }
  };

  const themeStyles = {
    container: { backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC' },
    card: { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' },
    text: { color: isDarkMode ? '#F1F5F9' : '#0F172A' },
    subtext: { color: isDarkMode ? '#94A3B8' : '#64748B' },
    input: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F8FAFC',
      color: isDarkMode ? '#FFFFFF' : '#0F172A',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
    segmentActive: {
      backgroundColor: '#0284C7',
      borderColor: '#0284C7',
    },
    segmentInactive: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
    segmentTextActive: { color: '#FFFFFF', fontWeight: 'bold' as const },
    segmentTextInactive: { color: isDarkMode ? '#94A3B8' : '#475569' },
    rosterItem: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
  };

  return (
    <ScreenContainer testID="household-form-screen" style={themeStyles.container}>
      <AppHeader
        title={householdNumber}
        subtitle={`HOUSEHOLD QUESTIONNAIRE • ${buildingReference || 'BUILDING'}`}
        roleType="ENUMERATOR"
        roleLabel={t('role_enumerator')}
        showBack
        onBack={() => navigation.goBack()}
        testID="household-form-header"
      />

      <ScrollView
        style={styles.content}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {/* Status Indicator */}
        <View style={styles.topStatusRow}>
          <Text style={[styles.buildingRefText, themeStyles.subtext]}>
            {buildingReference ? `Structure: ${buildingReference}` : 'Fieldwork Questionnaire'}
          </Text>
          <StatusBadge
            type={currentStatus === 'COMPLETED' ? 'COMPLETED' : 'DRAFT'}
            label={currentStatus === 'COMPLETED' ? t('completed_badge') : t('draft_badge')}
          />
        </View>

        {errorMessage && (
          <View style={styles.errorBanner} testID="form-error-banner">
            <Text style={styles.errorIcon}>⚠️</Text>
            <Text style={styles.errorBannerText}>{errorMessage}</Text>
          </View>
        )}

        {/* Phase 12 — Offline Voice Assistant Input Trigger */}
        <TouchableOpacity
          style={styles.voiceAssistantBanner}
          onPress={() => setVoiceModalVisible(true)}
          testID="open-voice-assistant-btn"
          activeOpacity={0.85}
        >
          <View style={styles.voiceAssistantBannerInner}>
            <View style={styles.voiceAssistantIconWrap}>
              <Text style={styles.voiceAssistantMicIcon}>🎙️</Text>
            </View>
            <View style={styles.voiceAssistantTextGroup}>
              <Text style={styles.voiceAssistantTitle}>{t('use_voice_assistant')}</Text>
              <Text style={styles.voiceAssistantSubtitle}>
                {t('speak_household_hint')}
              </Text>
            </View>
            <Text style={styles.voiceAssistantChevron}>›</Text>
          </View>
        </TouchableOpacity>

        {/* Census House Link (if available) */}
        {censusHouses.length > 0 && (
          <Card title="Census House Selection" style={themeStyles.card}>
            <Text style={[styles.fieldLabelSmall, themeStyles.subtext]}>
              Link Household to Census House Unit
            </Text>
            <View style={styles.chSelectorRow}>
              {censusHouses.map((ch) => (
                <TouchableOpacity
                  key={ch.id}
                  style={[
                    styles.chSelectChip,
                    selectedCensusHouseId === ch.id && styles.chSelectChipActive,
                  ]}
                  onPress={() => setSelectedCensusHouseId(ch.id)}
                >
                  <Text
                    style={[
                      styles.chSelectChipText,
                      selectedCensusHouseId === ch.id && styles.chSelectChipTextActive,
                    ]}
                  >
                    {ch.census_house_number} ({ch.use_code.replace(/_/g, ' ')})
                  </Text>
                </TouchableOpacity>
              ))}
            </View>
          </Card>
        )}

        {/* 1. Identification Section */}
        <Card title="1. Identification & Head of Household" style={themeStyles.card}>
          <Text style={[styles.fieldLabel, themeStyles.text]}>
            {t('household_number_label')} *
          </Text>
          <TextInput
            style={[styles.input, themeStyles.input]}
            value={householdNumber}
            onChangeText={setHouseholdNumber}
            placeholder="e.g. HH-1"
            placeholderTextColor="#94A3B8"
            testID="household-number-input"
          />

          <Text style={[styles.fieldLabel, themeStyles.text, { marginTop: 12 }]}>
            {t('head_of_household')} *
          </Text>
          <TextInput
            style={[styles.input, themeStyles.input]}
            value={headName}
            onChangeText={setHeadName}
            placeholder={t('enter_head_name_placeholder')}
            placeholderTextColor="#94A3B8"
            testID="head-name-input"
          />
        </Card>

        {/* 2. Demographic Members Section */}
        <Card title="2. Household Members Breakdown" style={themeStyles.card}>
          <Text style={[styles.fieldLabel, themeStyles.text]}>
            {t('total_members_label')} *
          </Text>
          <TextInput
            style={[styles.input, themeStyles.input]}
            value={totalMembers}
            onChangeText={(v) => setTotalMembers(v.replace(/[^0-9]/g, ''))}
            keyboardType="number-pad"
            placeholder="Total Count"
            placeholderTextColor="#94A3B8"
            testID="total-members-input"
          />

          <View style={styles.breakdownGrid}>
            <View style={styles.breakdownItem}>
              <Text style={[styles.fieldLabelSmall, themeStyles.subtext]}>
                {t('male_members')}
              </Text>
              <TextInput
                style={[styles.input, themeStyles.input]}
                value={maleCount}
                onChangeText={(v) => setMaleCount(v.replace(/[^0-9]/g, ''))}
                keyboardType="number-pad"
                testID="male-count-input"
              />
            </View>

            <View style={styles.breakdownItem}>
              <Text style={[styles.fieldLabelSmall, themeStyles.subtext]}>
                {t('female_members')}
              </Text>
              <TextInput
                style={[styles.input, themeStyles.input]}
                value={femaleCount}
                onChangeText={(v) => setFemaleCount(v.replace(/[^0-9]/g, ''))}
                keyboardType="number-pad"
                testID="female-count-input"
              />
            </View>

            <View style={styles.breakdownItem}>
              <Text style={[styles.fieldLabelSmall, themeStyles.subtext]}>
                {t('transgender_members')}
              </Text>
              <TextInput
                style={[styles.input, themeStyles.input]}
                value={transgenderCount}
                onChangeText={(v) => setTransgenderCount(v.replace(/[^0-9]/g, ''))}
                keyboardType="number-pad"
                testID="trans-count-input"
              />
            </View>
          </View>
        </Card>

        {/* 3. Phase II Individual Person Demographics Roster */}
        <Card
          title={`3. Phase II Person Roster (${persons.length})`}
          style={themeStyles.card}
          testID="person-roster-card"
        >
          <Text style={[styles.fieldLabelSmall, themeStyles.subtext]}>
            Record individual demographic records (Phase II Enumeration)
          </Text>

          {persons.map((p, idx) => (
            <View
              key={p.id}
              style={[styles.rosterCard, themeStyles.rosterItem]}
              testID={`person-row-${idx}`}
            >
              <View style={styles.rosterHeader}>
                <Text style={[styles.rosterTitle, themeStyles.text]}>
                  #{idx + 1}: {p.name || 'Member'} ({p.relationship_to_head})
                </Text>
                <TouchableOpacity onPress={() => handleRemovePerson(idx)}>
                  <Text style={styles.deleteMemberText}>✕</Text>
                </TouchableOpacity>
              </View>

              <View style={styles.rosterInputsRow}>
                <TextInput
                  style={[styles.rosterInput, themeStyles.input, { flex: 2 }]}
                  value={p.name}
                  onChangeText={(val) => {
                    const updated = [...persons];
                    updated[idx].name = val;
                    setPersons(updated);
                  }}
                  placeholder="Full Name"
                  placeholderTextColor="#94A3B8"
                />
                <TextInput
                  style={[styles.rosterInput, themeStyles.input, { flex: 1 }]}
                  value={p.age != null ? String(p.age) : ''}
                  onChangeText={(val) => {
                    const updated = [...persons];
                    updated[idx].age = parseInt(val, 10) || null;
                    setPersons(updated);
                  }}
                  keyboardType="number-pad"
                  placeholder="Age"
                  placeholderTextColor="#94A3B8"
                />
              </View>

              <View style={styles.rosterChipsRow}>
                {['MALE', 'FEMALE', 'TRANSGENDER'].map((s) => (
                  <TouchableOpacity
                    key={s}
                    style={[
                      styles.rosterSexChip,
                      p.sex === s && styles.rosterSexChipActive,
                    ]}
                    onPress={() => {
                      const updated = [...persons];
                      updated[idx].sex = s;
                      setPersons(updated);
                    }}
                  >
                    <Text
                      style={[
                        styles.rosterSexChipText,
                        p.sex === s && styles.rosterSexChipTextActive,
                      ]}
                    >
                      {s[0]}
                    </Text>
                  </TouchableOpacity>
                ))}

                {['HEAD', 'SPOUSE', 'CHILD', 'PARENT', 'OTHER'].map((rel) => (
                  <TouchableOpacity
                    key={rel}
                    style={[
                      styles.rosterRelChip,
                      p.relationship_to_head === rel && styles.rosterRelChipActive,
                    ]}
                    onPress={() => {
                      const updated = [...persons];
                      updated[idx].relationship_to_head = rel;
                      setPersons(updated);
                    }}
                  >
                    <Text
                      style={[
                        styles.rosterRelChipText,
                        p.relationship_to_head === rel && styles.rosterRelChipTextActive,
                      ]}
                    >
                      {rel}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          ))}

          <TouchableOpacity
            style={styles.addPersonBtn}
            onPress={handleAddPerson}
            testID="add-person-btn"
          >
            <Text style={styles.addPersonBtnText}>+ Add Person to Roster</Text>
          </TouchableOpacity>
        </Card>

        {/* 4. Housing Amenities & Living Conditions */}
        <Card title="4. Housing Amenities & Living Conditions" style={themeStyles.card}>
          <Text style={[styles.fieldLabel, themeStyles.text]}>
            {t('ownership_type')}
          </Text>
          <View style={styles.segmentedRow}>
            {(['OWNED', 'RENTED', 'OTHER'] as OwnershipStatus[]).map((status) => (
              <TouchableOpacity
                key={status}
                style={[
                  styles.segmentButton,
                  ownershipStatus === status
                    ? themeStyles.segmentActive
                    : themeStyles.segmentInactive,
                ]}
                onPress={() => setOwnershipStatus(status)}
                testID={`ownership-${status.toLowerCase()}-btn`}
              >
                <Text
                  style={
                    ownershipStatus === status
                      ? themeStyles.segmentTextActive
                      : themeStyles.segmentTextInactive
                  }
                >
                  {status === 'OWNED'
                    ? t('owned')
                    : status === 'RENTED'
                    ? t('rented')
                    : t('other_ownership')}
                </Text>
              </TouchableOpacity>
            ))}
          </View>

          <Text style={[styles.fieldLabel, themeStyles.text, { marginTop: 14 }]}>
            {t('drinking_water')}
          </Text>
          <TextInput
            style={[styles.input, themeStyles.input]}
            value={drinkingWater}
            onChangeText={setDrinkingWater}
            placeholder={t('select_drinking_water_placeholder')}
            placeholderTextColor="#94A3B8"
            testID="drinking-water-input"
          />

          <Text style={[styles.fieldLabel, themeStyles.text, { marginTop: 14 }]}>
            {t('lighting_source_label')}
          </Text>
          <TextInput
            style={[styles.input, themeStyles.input]}
            value={lightingSource}
            onChangeText={setLightingSource}
            placeholder={t('select_lighting_placeholder')}
            placeholderTextColor="#94A3B8"
            testID="lighting-source-input"
          />

          <Text style={[styles.fieldLabel, themeStyles.text, { marginTop: 14 }]}>
            {t('latrine_facility_label')}
          </Text>
          <View style={styles.segmentedRow}>
            {['Yes', 'No'].map((opt) => (
              <TouchableOpacity
                key={opt}
                style={[
                  styles.segmentButton,
                  latrineFacility === opt
                    ? themeStyles.segmentActive
                    : themeStyles.segmentInactive,
                ]}
                onPress={() => setLatrineFacility(opt)}
                testID={`latrine-${opt.toLowerCase()}-btn`}
              >
                <Text
                  style={
                    latrineFacility === opt
                      ? themeStyles.segmentTextActive
                      : themeStyles.segmentTextInactive
                  }
                >
                  {opt === 'Yes' ? t('yes') : t('no')}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
        </Card>

        {/* Action Buttons */}
        <View style={styles.actionSection}>
          <PrimaryButton
            title={t('complete_form')}
            onPress={() => handleSave(true)}
            loading={saving}
            style={styles.primaryActionBtn}
            testID="complete-form-btn"
          />

          <SecondaryButton
            title={t('save_draft')}
            onPress={() => handleSave(false)}
            disabled={saving}
            variant="neutral"
            style={styles.draftActionBtn}
            testID="save-draft-btn"
          />
        </View>
      </ScrollView>

      {/* Phase 12 — Voice Assistant Modal */}
      <VoiceAssistantModal
        visible={voiceModalVisible}
        onClose={() => setVoiceModalVisible(false)}
        defaultLanguage={language === 'ta' ? 'ta' : 'en'}
        onConfirmExtraction={(data) => {
          setVoiceUsed(true);
          if (data.headName != null && data.headName.trim() !== '') {
            setHeadName(data.headName);
          }
          if (data.totalMembers != null) {
            setTotalMembers(String(data.totalMembers));
          }
          if (data.maleCount != null) {
            setMaleCount(String(data.maleCount));
          }
          if (data.femaleCount != null) {
            setFemaleCount(String(data.femaleCount));
          }
          if (data.transgenderCount != null) {
            setTransgenderCount(String(data.transgenderCount));
          }
          if (data.ownershipStatus != null) {
            setOwnershipStatus(data.ownershipStatus);
          }
          if (data.drinkingWater != null && data.drinkingWater.trim() !== '') {
            setDrinkingWater(data.drinkingWater);
          }
          if (data.lightingSource != null && data.lightingSource.trim() !== '') {
            setLightingSource(data.lightingSource);
          }
          if (data.latrineFacility != null && data.latrineFacility.trim() !== '') {
            setLatrineFacility(data.latrineFacility);
          }
        }}
        testID="household-voice-assistant-modal"
      />
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  content: {
    padding: 16,
  },
  topStatusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  buildingRefText: {
    fontSize: 13,
    fontWeight: '600',
  },
  errorBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#F87171',
    borderRadius: 8,
    padding: 12,
    marginBottom: 14,
    gap: 8,
  },
  errorIcon: {
    fontSize: 18,
  },
  errorBannerText: {
    color: '#991B1B',
    fontSize: 13,
    fontWeight: '600',
    flex: 1,
  },
  fieldLabel: {
    fontSize: 14,
    fontWeight: '700',
    marginBottom: 6,
  },
  fieldLabelSmall: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  input: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 15,
  },
  breakdownGrid: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 12,
  },
  breakdownItem: {
    flex: 1,
  },
  chSelectorRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 6,
    marginTop: 6,
  },
  chSelectChip: {
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#CBD5E1',
    backgroundColor: 'transparent',
  },
  chSelectChipActive: {
    backgroundColor: '#0284C7',
    borderColor: '#0284C7',
  },
  chSelectChipText: {
    fontSize: 12,
    color: '#64748B',
  },
  chSelectChipTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  rosterCard: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 8,
  },
  rosterHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 6,
  },
  rosterTitle: {
    fontSize: 13,
    fontWeight: '700',
  },
  deleteMemberText: {
    color: '#EF4444',
    fontSize: 14,
    fontWeight: '700',
    padding: 4,
  },
  rosterInputsRow: {
    flexDirection: 'row',
    gap: 8,
    marginBottom: 6,
  },
  rosterInput: {
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 6,
    fontSize: 13,
  },
  rosterChipsRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 4,
  },
  rosterSexChip: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#CBD5E1',
  },
  rosterSexChipActive: {
    backgroundColor: '#0284C7',
    borderColor: '#0284C7',
  },
  rosterSexChipText: {
    fontSize: 10,
    fontWeight: '700',
    color: '#64748B',
  },
  rosterSexChipTextActive: {
    color: '#FFFFFF',
  },
  rosterRelChip: {
    paddingVertical: 4,
    paddingHorizontal: 6,
    borderRadius: 4,
    borderWidth: 1,
    borderColor: '#CBD5E1',
  },
  rosterRelChipActive: {
    backgroundColor: '#6366F1',
    borderColor: '#6366F1',
  },
  rosterRelChipText: {
    fontSize: 10,
    fontWeight: '600',
    color: '#64748B',
  },
  rosterRelChipTextActive: {
    color: '#FFFFFF',
  },
  addPersonBtn: {
    marginTop: 10,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: '#0284C7',
    borderRadius: 6,
    alignItems: 'center',
    borderStyle: 'dashed',
  },
  addPersonBtnText: {
    color: '#0284C7',
    fontSize: 12,
    fontWeight: '700',
  },
  segmentedRow: {
    flexDirection: 'row',
    gap: 8,
  },
  segmentButton: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
    borderRadius: 8,
    borderWidth: 1,
  },
  actionSection: {
    marginTop: 16,
    marginBottom: 36,
    gap: 10,
  },
  primaryActionBtn: {
    backgroundColor: '#16A34A',
  },
  draftActionBtn: {
    marginTop: 2,
  },
  voiceAssistantBanner: {
    backgroundColor: '#0284C7',
    borderRadius: 12,
    padding: 14,
    marginBottom: 16,
    shadowColor: '#0284C7',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.25,
    shadowRadius: 4,
    elevation: 3,
  },
  voiceAssistantBannerInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  voiceAssistantIconWrap: {
    width: 42,
    height: 42,
    borderRadius: 21,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  voiceAssistantMicIcon: {
    fontSize: 22,
  },
  voiceAssistantTextGroup: {
    flex: 1,
  },
  voiceAssistantTitle: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  voiceAssistantSubtitle: {
    color: '#E0F2FE',
    fontSize: 11,
    marginTop: 2,
  },
  voiceAssistantChevron: {
    color: '#FFFFFF',
    fontSize: 24,
    fontWeight: '700',
    marginLeft: 4,
  },
});
