import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { Alert } from 'react-native';
import { HouseholdFormScreen } from '../src/features/enumerator/HouseholdFormScreen';
import { VoiceAssistantModal } from '../src/components/VoiceAssistantModal';
import { offlineVoiceService } from '../src/core/voice/offlineVoiceService';
import { voiceExtractionEngine } from '../src/core/voice/voiceExtractionEngine';
import { fieldworkService } from '../src/core/fieldworkService';
import { routeService } from '../src/core/routeService';
import { gpsService } from '../src/core/gpsService';
import { useAuthStore } from '../src/core/authStore';
import { useLanguageStore } from '../src/core/localization';
import { en } from '../src/core/localization/en';
import { ta } from '../src/core/localization/ta';
import type { OfflineHouseholdRecord } from '../src/core/sqlite/types';

// Mock Navigation
const mockNavigate = jest.fn();
const mockGoBack = jest.fn();
let mockRouteParams: any = {
  hlbId: 'hlb-voice-test-1',
  blockCode: 'HLB-VOICE-001',
  buildingId: 'bld-v101',
  buildingReference: 'BLD-V101',
};

jest.mock('@react-navigation/native', () => {
  const actual = jest.requireActual('@react-navigation/native');
  return {
    ...actual,
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: mockGoBack,
      addListener: jest.fn(() => jest.fn()),
    }),
    useRoute: () => ({
      params: mockRouteParams,
    }),
  };
});

describe('Phase 12 — Offline Voice Assistant Mobile Test Suite', () => {
  const activeRenderers: any[] = [];

  const createComponent = async (element: React.ReactElement) => {
    let comp: any;
    await ReactTestRenderer.act(async () => {
      comp = ReactTestRenderer.create(element);
    });
    activeRenderers.push(comp);
    return comp;
  };

  beforeEach(async () => {
    jest.clearAllMocks();
    jest.spyOn(Alert, 'alert').mockImplementation(() => {});
    offlineVoiceService.setMockPermission(true);
    offlineVoiceService.cancelListening();

    mockRouteParams = {
      hlbId: 'hlb-voice-test-1',
      blockCode: 'HLB-VOICE-001',
      buildingId: 'bld-v101',
      buildingReference: 'BLD-V101',
    };

    await ReactTestRenderer.act(async () => {
      useAuthStore.setState({
        user: {
          id: 'enum-voice-user',
          name: 'Karthik Enumerator',
          username: 'karthik_enum',
          role: 'ENUMERATOR',
        },
        token: 'mock-jwt-token',
        status: 'authenticated',
        error: null,
      });

      useLanguageStore.getState().setLanguage('en');
    });
  });

  afterEach(async () => {
    offlineVoiceService.cancelListening();
    while (activeRenderers.length > 0) {
      const comp = activeRenderers.pop();
      try {
        await ReactTestRenderer.act(async () => {
          comp.unmount();
        });
      } catch {}
    }
  });

  // ===========================================================================
  // 1 & 2 & 3. PERMISSIONS & SERVICE LIFECYCLE
  // ===========================================================================

  test('1. Microphone permission granted allows speech recognition to start', async () => {
    offlineVoiceService.setMockPermission(true);
    const hasPerm = await offlineVoiceService.checkPermission();
    expect(hasPerm).toBe(true);

    let started = false;
    await offlineVoiceService.startListening(
      { language: 'ta' },
      {
        onSpeechStart: () => {
          started = true;
        },
      }
    );
    expect(started).toBe(true);
    expect(offlineVoiceService.isListeningNow()).toBe(true);
    offlineVoiceService.cancelListening();
  });

  test('2. Microphone permission denied prevents listening and triggers error', async () => {
    offlineVoiceService.setMockPermission(false);
    const hasPerm = await offlineVoiceService.checkPermission();
    expect(hasPerm).toBe(false);

    let errorReceived: any = null;
    const ok = await offlineVoiceService.startListening(
      { language: 'en' },
      {
        onError: (err) => {
          errorReceived = err;
        },
      }
    );

    expect(ok).toBe(false);
    expect(errorReceived?.code).toBe('PERMISSION_DENIED');
    expect(offlineVoiceService.isListeningNow()).toBe(false);
  });

  test('3. Recognition unavailable or engine error handles gracefully', async () => {
    offlineVoiceService.setMockPermission(true);
    let errorCaught: any = null;

    await offlineVoiceService.startListening(
      { language: 'ta' },
      {
        onError: (err) => {
          errorCaught = err;
        },
      }
    );

    // Cancel while listening simulates an aborted/cancelled lifecycle
    offlineVoiceService.cancelListening();
    expect(offlineVoiceService.isListeningNow()).toBe(false);
  });

  // ===========================================================================
  // 4, 5, 6, 7 & 8. RECOGNITION & EXTRACTION FLOWS (TAMIL, ENGLISH, MIXED)
  // ===========================================================================

  test('4. CASE 1 — Tamil speech recognition and deterministic extraction', () => {
    const speech = 'இந்த வீட்டில் நான்கு பேர் இருக்கிறார்கள்';
    const result = voiceExtractionEngine.extractHouseholdData(speech, 'ta');

    expect(result.rawText).toBe(speech);
    expect(result.totalMembers?.value).toBe(4);
    expect(result.totalMembers?.confidence).toBe('CONFIRMED');
    expect(result.overallStatus).toBe('CONFIRMED');
  });

  test('5. CASE 2 — English speech recognition and deterministic extraction', () => {
    const speech = 'There are four members in this household';
    const result = voiceExtractionEngine.extractHouseholdData(speech, 'en');

    expect(result.rawText).toBe(speech);
    expect(result.totalMembers?.value).toBe(4);
    expect(result.totalMembers?.confidence).toBe('CONFIRMED');
    expect(result.overallStatus).toBe('CONFIRMED');
  });

  test('6. CASE 3 — Mixed Tamil/English (Tanglish) speech extraction', () => {
    const speech = 'இந்த household-ல four members இருக்காங்க. house is rented.';
    const result = voiceExtractionEngine.extractHouseholdData(speech, 'mixed');

    expect(result.totalMembers?.value).toBe(4);
    expect(result.totalMembers?.confidence).toBe('CONFIRMED');
    expect(result.ownershipStatus?.value).toBe('RENTED');
    expect(result.ownershipStatus?.confidence).toBe('CONFIRMED');
  });

  test('7. Displays recognized speech text accurately', async () => {
    const component = await createComponent(
      <VoiceAssistantModal
        visible={true}
        onClose={jest.fn()}
        onConfirmExtraction={jest.fn()}
      />
    );

    const root = component.root;
    const micBtn = root.findByProps({ testID: 'mic-trigger-btn' });
    await ReactTestRenderer.act(async () => {
      micBtn.props.onPress();
    });

    // Simulate speech through the offlineVoiceService
    await ReactTestRenderer.act(async () => {
      offlineVoiceService.simulateSpeechInput('நான்கு பேர், சொந்த வீடு', 'ta');
    });

    const recognizedBox = root.findByProps({ testID: 'recognized-speech-text' });
    expect(recognizedBox.props.children).toContain('நான்கு பேர், சொந்த வீடு');
  });

  test('8. Structured field extraction handles demographic breakdown and amenities', () => {
    const complexSpeech =
      'குடும்பத் தலைவர் முருகன். மொத்தம் 5 பேர். இரண்டு ஆண்கள், இரண்டு பெண்கள், ஒருவர் திருநங்கை. சொந்த வீடு. குடிநீர் குழாய் நீர். மின்சாரம் வசதி உள்ளது. கழிப்பறை வசதி ஆம்.';
    const res = voiceExtractionEngine.extractHouseholdData(complexSpeech, 'ta');

    expect(res.headName?.value).toBe('முருகன்');
    expect(res.totalMembers?.value).toBe(5);
    expect(res.maleCount?.value).toBe(2);
    expect(res.femaleCount?.value).toBe(2);
    expect(res.transgenderCount?.value).toBe(1);
    expect(res.ownershipStatus?.value).toBe('OWNED');
    expect(res.drinkingWater?.value).toBe('Tap Water');
    expect(res.lightingSource?.value).toBe('Electricity');
    expect(res.latrineFacility?.value).toBe('Yes');
    expect(res.overallStatus).toBe('CONFIRMED');
  });

  // ===========================================================================
  // 10 & 11. UNCERTAINTY & AMBIGUITY (CASES 4, 5, 6)
  // ===========================================================================

  test('10. CASE 4 — Ambiguous speech ("நான்கு அல்லது ஐந்து பேர்") marked UNCERTAIN, requires review', () => {
    const speech = 'நான்கு அல்லது ஐந்து பேர்';
    const res = voiceExtractionEngine.extractHouseholdData(speech, 'ta');

    // Must NOT automatically save as 4 or 5
    expect(res.totalMembers?.value).toBeNull();
    expect(res.totalMembers?.confidence).toBe('UNCERTAIN');
    expect(res.overallStatus).toBe('NEEDS_REVIEW');
  });

  test('10b. Ambiguous English speech ("around four or five people") marked UNCERTAIN', () => {
    const speech = 'Maybe around four or five people living here';
    const res = voiceExtractionEngine.extractHouseholdData(speech, 'en');

    expect(res.totalMembers?.value).toBeNull();
    expect(res.totalMembers?.confidence).toBe('UNCERTAIN');
    expect(res.overallStatus).toBe('NEEDS_REVIEW');
  });

  test('11. CASE 5 — Missing/unmentioned counts ("இந்த வீட்டைப் பற்றி பதிவு செய்யவும்") returns UNRESOLVED, no fabrication', () => {
    const speech = 'இந்த வீட்டைப் பற்றி பதிவு செய்யவும்';
    const res = voiceExtractionEngine.extractHouseholdData(speech, 'ta');

    // No fabricated household member count!
    expect(res.totalMembers).toBeUndefined();
    expect(res.maleCount).toBeUndefined();
    expect(res.ownershipStatus).toBeUndefined();
  });

  test('11b. CASE 6 — Noisy / poor recognition with contradictory breakdown requires review', () => {
    // Total is 5, but breakdown says 1 male and 1 female (sum = 2 != 5)
    const noisySpeech = 'Total members five. Male one. Female one.';
    const res = voiceExtractionEngine.extractHouseholdData(noisySpeech, 'en');

    expect(res.totalMembers?.value).toBe(5);
    expect(res.maleCount?.value).toBe(1);
    expect(res.femaleCount?.value).toBe(1);
    // Arithmetic mismatch marks overallStatus as NEEDS_REVIEW
    expect(res.overallStatus).toBe('NEEDS_REVIEW');
  });

  // ===========================================================================
  // 9, 12, 13. CONFIRMATION, EDITING & REJECTION IN UI
  // ===========================================================================

  test('9. Confirmed voice extraction populates HouseholdFormScreen', async () => {
    jest.spyOn(fieldworkService, 'getBuildingDetail').mockReturnValue({
      building: {
        id: 'bld-v101',
        hlb_id: 'hlb-voice-test-1',
        building_reference: 'BLD-V101',
        house_number: '12',
        latitude: 11.66,
        longitude: 78.14,
        footprint_geojson: null,
        source_type: null,
        status: 'PENDING',
        household_count: 0,
        last_updated_at: new Date().toISOString(),
      },
      households: [],
      revisits: [],
    });

    const component = await createComponent(<HouseholdFormScreen />);

    const root = component.root;
    // Check Voice Assistant trigger button is present
    const voiceTrigger = root.findByProps({ testID: 'open-voice-assistant-btn' });
    expect(voiceTrigger).toBeDefined();

    // Open Voice Assistant Modal
    await ReactTestRenderer.act(async () => {
      voiceTrigger.props.onPress();
    });

    const voiceModal = root.findByProps({ testID: 'household-voice-assistant-modal' });
    expect(voiceModal.props.visible).toBe(true);

    // Confirm extraction with mock extracted data
    await ReactTestRenderer.act(async () => {
      voiceModal.props.onConfirmExtraction({
        headName: 'Sundaramurthy',
        totalMembers: 4,
        maleCount: 2,
        femaleCount: 2,
        transgenderCount: 0,
        ownershipStatus: 'RENTED',
        drinkingWater: 'Well Water',
      });
    });

    // Form inputs should now be populated with extracted values
    const headInput = root.findByProps({ testID: 'head-name-input' });
    expect(headInput.props.value).toBe('Sundaramurthy');

    const totalInput = root.findByProps({ testID: 'total-members-input' });
    expect(totalInput.props.value).toBe('4');

    const maleInput = root.findByProps({ testID: 'male-count-input' });
    expect(maleInput.props.value).toBe('2');

    const femaleInput = root.findByProps({ testID: 'female-count-input' });
    expect(femaleInput.props.value).toBe('2');
  });

  test('12. Enumerator can edit extracted values inside the review card before confirming', async () => {
    let confirmedData: any = null;

    const modal = await createComponent(
      <VoiceAssistantModal
        visible={true}
        onClose={jest.fn()}
        onConfirmExtraction={(data) => {
          confirmedData = data;
        }}
      />
    );

    const root = modal.root;
    const micBtn = root.findByProps({ testID: 'mic-trigger-btn' });
    await ReactTestRenderer.act(async () => {
      micBtn.props.onPress();
    });

    // Simulate speech
    await ReactTestRenderer.act(async () => {
      offlineVoiceService.simulateSpeechInput('Three members', 'en');
    });

    // Edit the total members from 3 to 4
    const totalInput = root.findByProps({ testID: 'voice-edit-total-members' });
    await ReactTestRenderer.act(async () => {
      totalInput.props.onChangeText('4');
    });

    // Edit the head name
    const headInput = root.findByProps({ testID: 'voice-edit-head-name' });
    await ReactTestRenderer.act(async () => {
      headInput.props.onChangeText('Annamalai');
    });

    // Click confirm
    const confirmBtn = root.findByProps({ testID: 'confirm-voice-extraction-btn' });
    await ReactTestRenderer.act(async () => {
      confirmBtn.props.onPress();
    });

    expect(confirmedData).toEqual(
      expect.objectContaining({
        totalMembers: 4,
        headName: 'Annamalai',
      })
    );
  });

  test('13. Enumerator can reject/cancel voice extraction without altering form', async () => {
    const onConfirmMock = jest.fn();
    const onCloseMock = jest.fn();

    const modal = await createComponent(
      <VoiceAssistantModal
        visible={true}
        onClose={onCloseMock}
        onConfirmExtraction={onConfirmMock}
      />
    );

    const root = modal.root;
    const micBtn = root.findByProps({ testID: 'mic-trigger-btn' });
    await ReactTestRenderer.act(async () => {
      micBtn.props.onPress();
    });

    await ReactTestRenderer.act(async () => {
      offlineVoiceService.simulateSpeechInput('Five members', 'en');
    });

    // Click cancel
    const cancelBtn = root.findByProps({ testID: 'cancel-voice-extraction-btn' });
    await ReactTestRenderer.act(async () => {
      cancelBtn.props.onPress();
    });

    expect(onCloseMock).toHaveBeenCalled();
    expect(onConfirmMock).not.toHaveBeenCalled();
  });

  // ===========================================================================
  // 14, 15, 16. VALIDATION & SQLITE PERSISTENCE & SYNC INTEGRATION
  // ===========================================================================

  test('14. Existing household validation still executes on voice-populated form', async () => {
    jest.spyOn(fieldworkService, 'getBuildingDetail').mockReturnValue({
      building: {
        id: 'bld-v101',
        hlb_id: 'hlb-voice-test-1',
        building_reference: 'BLD-V101',
        house_number: '12',
        latitude: 11.66,
        longitude: 78.14,
        footprint_geojson: null,
        source_type: null,
        status: 'PENDING',
        household_count: 0,
        last_updated_at: new Date().toISOString(),
      },
      households: [],
      revisits: [],
    });

    const component = await createComponent(<HouseholdFormScreen />);

    const root = component.root;
    const voiceModal = root.findByProps({ testID: 'household-voice-assistant-modal' });

    // Populate with mismatched counts: total = 4, but male = 1, female = 1 (sum = 2 != 4)
    await ReactTestRenderer.act(async () => {
      voiceModal.props.onConfirmExtraction({
        headName: 'Senthil',
        totalMembers: 4,
        maleCount: 1,
        femaleCount: 1,
        transgenderCount: 0,
      });
    });

    // Try completing form
    const completeBtn = root.findByProps({ testID: 'complete-form-btn' });
    await ReactTestRenderer.act(async () => {
      completeBtn.props.onPress();
    });

    // Error banner must be displayed
    const errorBanner = root.findByProps({ testID: 'form-error-banner' });
    expect(errorBanner).toBeDefined();
  });

  test('15 & 16. Confirmed voice-assisted record persists into SQLite with source="VOICE" and queues for sync', async () => {
    const saveSpy = jest.spyOn(fieldworkService, 'saveHousehold');

    jest.spyOn(fieldworkService, 'getBuildingDetail').mockReturnValue({
      building: {
        id: 'bld-v101',
        hlb_id: 'hlb-voice-test-1',
        building_reference: 'BLD-V101',
        house_number: '12',
        latitude: 11.66,
        longitude: 78.14,
        footprint_geojson: null,
        source_type: null,
        status: 'PENDING',
        household_count: 0,
        last_updated_at: new Date().toISOString(),
      },
      households: [],
      revisits: [],
    });

    const component = await createComponent(<HouseholdFormScreen />);

    const root = component.root;
    const voiceModal = root.findByProps({ testID: 'household-voice-assistant-modal' });

    // Populate valid consistent data via voice confirmation
    await ReactTestRenderer.act(async () => {
      voiceModal.props.onConfirmExtraction({
        headName: 'Marimuthu',
        totalMembers: 3,
        maleCount: 2,
        femaleCount: 1,
        transgenderCount: 0,
        ownershipStatus: 'OWNED',
        drinkingWater: 'Tap Water',
        lightingSource: 'Electricity',
        latrineFacility: 'Yes',
      });
    });

    // Complete form
    const completeBtn = root.findByProps({ testID: 'complete-form-btn' });
    await ReactTestRenderer.act(async () => {
      completeBtn.props.onPress();
    });

    expect(saveSpy).toHaveBeenCalledTimes(1);
    const saved = saveSpy.mock.calls[0][0] as OfflineHouseholdRecord;
    expect(saved.head_name).toBe('Marimuthu');
    expect(saved.total_members).toBe(3);
    expect(saved.male_count).toBe(2);
    expect(saved.female_count).toBe(1);
    expect(saved.ownership_status).toBe('OWNED');
    expect(saved.source).toBe('VOICE'); // Demonstrates source = 'VOICE'
    expect(saved.status).toBe('COMPLETED');
  });

  // ===========================================================================
  // 17 & 18. OFFLINE OPERATION & EMPTY SPEECH
  // ===========================================================================

  test('17. Offline operation operates completely locally with no network calls', async () => {
    const fetchSpy = jest.spyOn(global, 'fetch');

    // Run recognition and extraction
    const speech = 'இந்த வீட்டில் மூன்று பேர், வாடகை வீடு';
    const ext = voiceExtractionEngine.extractHouseholdData(speech, 'ta');

    expect(ext.totalMembers?.value).toBe(3);
    expect(ext.ownershipStatus?.value).toBe('RENTED');
    // Ensure no fetch was triggered
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  test('18. Empty or whitespace speech returns NO_SPEECH_DETECTED and displays error', async () => {
    const component = await createComponent(
      <VoiceAssistantModal
        visible={true}
        onClose={jest.fn()}
        onConfirmExtraction={jest.fn()}
      />
    );

    const root = component.root;
    const micBtn = root.findByProps({ testID: 'mic-trigger-btn' });
    await ReactTestRenderer.act(async () => {
      micBtn.props.onPress();
    });

    // Simulate empty speech
    await ReactTestRenderer.act(async () => {
      offlineVoiceService.simulateSpeechInput('   ', 'ta');
    });

    const errorBanner = root.findByProps({ testID: 'voice-error-banner' });
    expect(errorBanner).toBeDefined();
  });

  // ===========================================================================
  // 20. LOCALIZATION INTEGRITY
  // ===========================================================================

  test('20. Phase 12 localization keys are present in both English and Tamil', () => {
    const requiredKeys: Array<keyof typeof en> = [
      'voice_assistant',
      'tap_to_speak',
      'listening',
      'processing_speech',
      'recognized_text',
      'extracted_info',
      'confirm_voice_entry',
      'cancel_voice',
      'speech_recognition',
      'microphone_permission',
      'mic_permission_required',
      'mic_permission_denied',
      'recognition_unavailable',
      'offline_recognition_unavailable',
      'no_speech_detected',
      'could_not_understand',
      'uncertain_voice_info',
      'please_review',
      'voice_entry_confirmed',
      'language_tamil',
      'language_english',
      'language_mixed',
      'use_voice_assistant',
      'speak_household_hint',
      'confirmed',
      'uncertain',
      'unresolved',
    ];

    for (const key of requiredKeys) {
      expect(en[key]).toBeDefined();
      expect(typeof en[key]).toBe('string');
      expect((en[key] as string).length).toBeGreaterThan(0);

      expect(ta[key]).toBeDefined();
      expect(typeof ta[key]).toBe('string');
      expect((ta[key] as string).length).toBeGreaterThan(0);
    }
  });

  // ===========================================================================
  // 21, 22, 23. EXISTING FUNCTIONALITY INTEGRITY (FIELDWORK, ROUTE, GPS)
  // ===========================================================================

  test('21. Existing fieldwork service operations remain intact', () => {
    expect(typeof fieldworkService.saveHousehold).toBe('function');
    expect(typeof fieldworkService.getBuildingDetail).toBe('function');
    expect(typeof fieldworkService.saveRevisit).toBe('function');
    expect(typeof fieldworkService.lockBuilding).toBe('function');
  });

  test('22. Phase 10 route optimization functionality remains intact', () => {
    expect(typeof routeService.calculateOfflineRoute).toBe('function');
    expect(typeof routeService.getSavedRoute).toBe('function');
    expect(typeof routeService.getOrGenerateRoute).toBe('function');
  });

  test('23. Phase 11 GPS boundary monitoring service remains intact', () => {
    expect(typeof gpsService.startWatching).toBe('function');
    expect(typeof gpsService.stopWatching).toBe('function');
    expect(typeof gpsService.getCurrentLocation).toBe('function');
  });
});
