import type { OwnershipStatus } from '../sqlite/types';

export type VoiceAssistantState =
  | 'IDLE'
  | 'LISTENING'
  | 'PROCESSING'
  | 'RESULT_READY'
  | 'NEEDS_REVIEW'
  | 'ERROR';

export type VoiceLanguage = 'ta' | 'en' | 'mixed';

export type FieldConfidence = 'CONFIRMED' | 'UNCERTAIN' | 'UNRESOLVED';

export interface ExtractedField<T> {
  value: T | null;
  rawMatch: string | null;
  confidence: FieldConfidence;
  reason?: string;
}

export interface HouseholdVoiceExtraction {
  rawText: string;
  language: VoiceLanguage;
  headName?: ExtractedField<string>;
  totalMembers?: ExtractedField<number>;
  maleCount?: ExtractedField<number>;
  femaleCount?: ExtractedField<number>;
  transgenderCount?: ExtractedField<number>;
  ownershipStatus?: ExtractedField<OwnershipStatus>;
  drinkingWater?: ExtractedField<string>;
  lightingSource?: ExtractedField<string>;
  latrineFacility?: ExtractedField<string>;
  overallStatus: 'CONFIRMED' | 'NEEDS_REVIEW' | 'EMPTY';
  uncertainFieldsCount: number;
  extractedFieldsCount: number;
}

export interface VoiceRecognitionResult {
  text: string;
  language: VoiceLanguage;
  isFinal: boolean;
  confidence?: number;
}

export interface VoiceServiceCallbacks {
  onSpeechStart?: () => void;
  onSpeechRecognized?: (result: VoiceRecognitionResult) => void;
  onSpeechEnd?: (result: VoiceRecognitionResult) => void;
  onError?: (error: { code: string; message: string }) => void;
}
