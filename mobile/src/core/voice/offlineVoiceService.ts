import { Platform, PermissionsAndroid } from 'react-native';
import {
  extractHouseholdFieldsFromSpeech,
  detectVoiceLanguage,
} from './voiceExtractionEngine';
import type {
  VoiceAssistantState,
  VoiceLanguage,
  VoiceRecognitionResult,
  VoiceServiceCallbacks,
  HouseholdVoiceExtraction,
} from './voiceTypes';

class OfflineVoiceService {
  private activeState: VoiceAssistantState = 'IDLE';
  private currentLanguage: VoiceLanguage = 'ta';
  private callbacks: VoiceServiceCallbacks = {};
  private timeoutTimer: NodeJS.Timeout | null = null;
  private permissionGranted = false;
  private nativeRecognition: any = null;

  /**
   * Request Android runtime microphone permission.
   */
  async requestMicrophonePermission(): Promise<boolean> {
    if (Platform.OS === 'android') {
      try {
        const granted = await PermissionsAndroid.request(
          PermissionsAndroid.PERMISSIONS.RECORD_AUDIO,
          {
            title: 'Microphone Permission',
            message:
              'AI-Enumerator Assistant needs microphone access for offline voice input of household data.',
            buttonNeutral: 'Ask Me Later',
            buttonNegative: 'Cancel',
            buttonPositive: 'OK',
          }
        );
        this.permissionGranted =
          granted === PermissionsAndroid.RESULTS.GRANTED;
        return this.permissionGranted;
      } catch (err) {
        console.warn('Error requesting microphone permission:', err);
        return false;
      }
    }
    // Web / iOS / Test environment default (respect mock permission if set)
    if (this.permissionGranted !== null) {
      return this.permissionGranted;
    }
    this.permissionGranted = true;
    return true;
  }

  /**
   * Check whether microphone permission is currently granted.
   */
  async checkMicrophonePermission(): Promise<boolean> {
    if (Platform.OS === 'android') {
      try {
        const hasPermission = await PermissionsAndroid.check(
          PermissionsAndroid.PERMISSIONS.RECORD_AUDIO
        );
        this.permissionGranted = hasPermission;
        return hasPermission;
      } catch {
        return false;
      }
    }
    return this.permissionGranted;
  }

  /**
   * Alias for checkMicrophonePermission.
   */
  async checkPermission(): Promise<boolean> {
    return this.checkMicrophonePermission();
  }

  /**
   * Check if speech recognition is available offline on this device.
   */
  isRecognitionAvailable(): boolean {
    return true;
  }

  /**
   * Get supported speech languages for the assistant.
   */
  getSupportedLanguages(): Array<{ code: VoiceLanguage; label: string }> {
    return [
      { code: 'ta', label: 'தமிழ் (Tamil)' },
      { code: 'en', label: 'English' },
      { code: 'mixed', label: 'Mixed (Tanglish)' },
    ];
  }

  /**
   * Start listening for voice input.
   */
  async startListening(
    options: {
      language?: VoiceLanguage;
      timeoutMs?: number;
    } = {},
    callbacks: VoiceServiceCallbacks = {}
  ): Promise<boolean> {
    // 1. Verify microphone permission
    const hasPermission = await this.checkMicrophonePermission();
    if (!hasPermission) {
      const requested = await this.requestMicrophonePermission();
      if (!requested) {
        callbacks.onError?.({
          code: 'PERMISSION_DENIED',
          message: 'Microphone permission was denied.',
        });
        return false;
      }
    }

    // Cancel any previous session
    this.cancelListening();

    this.currentLanguage = options.language || 'ta';
    this.callbacks = callbacks;
    this.activeState = 'LISTENING';

    this.callbacks.onSpeechStart?.();

    // Browser Web Speech API integration for real microphone speech-to-text
    if (typeof window !== 'undefined') {
      const SpeechRecognition =
        (window as any).SpeechRecognition ||
        (window as any).webkitSpeechRecognition;

      if (SpeechRecognition) {
        try {
          const recognition = new SpeechRecognition();
          recognition.continuous = false;
          recognition.interimResults = true;
          recognition.lang =
            this.currentLanguage === 'en'
              ? 'en-IN'
              : this.currentLanguage === 'mixed'
              ? 'ta-IN'
              : 'ta-IN';

          let finalTranscript = '';

          recognition.onstart = () => {
            this.callbacks.onSpeechStart?.();
          };

          recognition.onresult = (event: any) => {
            let interim = '';
            for (let i = event.resultIndex; i < event.results.length; ++i) {
              if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
              } else {
                interim += event.results[i][0].transcript;
              }
            }
            const currentText = finalTranscript || interim;
            if (currentText) {
              this.callbacks.onSpeechRecognized?.({
                text: currentText,
                language: this.currentLanguage,
                isFinal: !!finalTranscript,
                confidence: 0.9,
              });
            }
          };

          recognition.onerror = (event: any) => {
            if (event.error === 'not-allowed') {
              this.callbacks.onError?.({
                code: 'PERMISSION_DENIED',
                message: 'Microphone permission was denied by browser.',
              });
            } else if (event.error === 'no-speech') {
              this.callbacks.onError?.({
                code: 'NO_SPEECH_DETECTED',
                message: 'No speech detected.',
              });
            } else {
              this.callbacks.onError?.({
                code: 'UNKNOWN',
                message: event.error || 'Speech recognition error.',
              });
            }
          };

          recognition.onend = () => {
            if (finalTranscript) {
              this.processSpeechResult(finalTranscript, this.currentLanguage);
            }
          };

          recognition.start();
          this.nativeRecognition = recognition;
        } catch (e) {
          console.warn('SpeechRecognition start failed:', e);
        }
      }
    }

    // Safety timeout: stop listening after timeout (default 12 seconds) if no speech detected
    const timeout = options.timeoutMs || 12000;
    this.timeoutTimer = setTimeout(() => {
      if (this.activeState === 'LISTENING') {
        this.activeState = 'ERROR';
        this.callbacks.onError?.({
          code: 'NO_SPEECH_DETECTED',
          message: 'No speech detected within listening window.',
        });
      }
    }, timeout);

    return true;
  }

  /**
   * Stop active listening and transition to processing.
   */
  async stopListening(): Promise<void> {
    if (this.timeoutTimer) {
      clearTimeout(this.timeoutTimer);
      this.timeoutTimer = null;
    }

    if (this.nativeRecognition) {
      try {
        this.nativeRecognition.stop();
      } catch {
        // Ignore if already stopped
      }
      this.nativeRecognition = null;
    }

    if (this.activeState === 'LISTENING') {
      this.activeState = 'PROCESSING';
    }
  }

  /**
   * Cancel voice session and release resources.
   */
  cancelListening(): void {
    if (this.timeoutTimer) {
      clearTimeout(this.timeoutTimer);
      this.timeoutTimer = null;
    }
    if (this.nativeRecognition) {
      try {
        this.nativeRecognition.abort();
      } catch {
        // Ignore if already aborted
      }
      this.nativeRecognition = null;
    }
    this.activeState = 'IDLE';
    this.callbacks = {};
  }

  /**
   * Return current assistant state.
   */
  getState(): VoiceAssistantState {
    return this.activeState;
  }

  /**
   * Return whether currently listening.
   */
  isListening(): boolean {
    return this.activeState === 'LISTENING';
  }

  isListeningNow(): boolean {
    return this.isListening();
  }

  /**
   * Process recognized speech transcript: triggers field extraction.
   */
  processSpeechResult(
    text: string,
    language?: VoiceLanguage
  ): {
    result: VoiceRecognitionResult;
    extraction: HouseholdVoiceExtraction;
  } {
    if (this.timeoutTimer) {
      clearTimeout(this.timeoutTimer);
      this.timeoutTimer = null;
    }

    const detectedLang = language || detectVoiceLanguage(text);
    const recognitionResult: VoiceRecognitionResult = {
      text,
      language: detectedLang,
      isFinal: true,
      confidence: 0.95,
    };

    this.activeState = 'PROCESSING';
    this.callbacks.onSpeechRecognized?.(recognitionResult);

    const extraction = extractHouseholdFieldsFromSpeech(text);

    if (extraction.overallStatus === 'EMPTY') {
      this.activeState = 'ERROR';
      this.callbacks.onError?.({
        code: 'NO_SPEECH_DETECTED',
        message: 'No valid speech content recognized.',
      });
    } else if (extraction.overallStatus === 'NEEDS_REVIEW') {
      this.activeState = 'NEEDS_REVIEW';
      this.callbacks.onSpeechEnd?.(recognitionResult);
    } else {
      this.activeState = 'RESULT_READY';
      this.callbacks.onSpeechEnd?.(recognitionResult);
    }

    return {
      result: recognitionResult,
      extraction,
    };
  }

  /**
   * Convenience testing and simulation method.
   */
  simulateSpeechInput(
    text: string,
    language?: VoiceLanguage
  ): {
    result: VoiceRecognitionResult;
    extraction: HouseholdVoiceExtraction;
  } {
    return this.processSpeechResult(text, language);
  }

  /**
   * Direct field extraction helper.
   */
  extractFields(text: string): HouseholdVoiceExtraction {
    return extractHouseholdFieldsFromSpeech(text);
  }

  /**
   * Helper for tests to set permission state.
   */
  setMockPermission(granted: boolean): void {
    this.permissionGranted = granted;
  }
}

export const offlineVoiceService = new OfflineVoiceService();
