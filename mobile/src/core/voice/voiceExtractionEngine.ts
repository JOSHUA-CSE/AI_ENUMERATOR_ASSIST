import type { OwnershipStatus } from '../sqlite/types';
import type {
  ExtractedField,
  HouseholdVoiceExtraction,
  VoiceLanguage,
} from './voiceTypes';

// Tamil number word mappings
const TAMIL_NUMBER_MAP: Record<string, number> = {
  ஒன்று: 1,
  ஒரு: 1,
  ஒருவர்: 1,
  ஒண்ணு: 1,
  இரண்டு: 2,
  இருவர்: 2,
  ரெண்டு: 2,
  இரு: 2,
  மூன்று: 3,
  மூவர்: 3,
  மூணு: 3,
  நான்கு: 4,
  நால்வர்: 4,
  நாலு: 4,
  ஐந்து: 5,
  ஐவர்: 5,
  அஞ்சு: 5,
  ஆறு: 6,
  ஏழு: 7,
  எட்டு: 8,
  ஒன்பது: 9,
  பத்து: 10,
  பதினொன்று: 11,
  பதினோரு: 11,
  பன்னிரண்டு: 12,
  பன்னிரண்டுக்கும்: 12,
  பதின்மூன்று: 13,
  பதினான்கு: 14,
  பதினைந்து: 15,
};

// English number word mappings
const ENGLISH_NUMBER_MAP: Record<string, number> = {
  one: 1,
  two: 2,
  three: 3,
  four: 4,
  five: 5,
  six: 6,
  seven: 7,
  eight: 8,
  nine: 9,
  ten: 10,
  eleven: 11,
  twelve: 12,
  thirteen: 13,
  fourteen: 14,
  fifteen: 15,
  sixteen: 16,
  seventeen: 17,
  eighteen: 18,
  nineteen: 19,
  twenty: 20,
};

function parseWordOrDigitNumber(token: string): number | null {
  const clean = token.toLowerCase().trim();
  if (/^\d+$/.test(clean)) {
    return parseInt(clean, 10);
  }
  if (TAMIL_NUMBER_MAP[clean] !== undefined) {
    return TAMIL_NUMBER_MAP[clean];
  }
  if (ENGLISH_NUMBER_MAP[clean] !== undefined) {
    return ENGLISH_NUMBER_MAP[clean];
  }
  return null;
}

/**
 * Detect language of input speech text: Tamil, English, or Mixed.
 */
export function detectVoiceLanguage(text: string): VoiceLanguage {
  const hasTamil = /[\u0B80-\u0BFF]/.test(text);
  const hasEnglishWords = /[a-zA-Z]{2,}/.test(text);

  if (hasTamil && hasEnglishWords) {
    return 'mixed';
  }
  if (hasTamil) {
    return 'ta';
  }
  return 'en';
}

/**
 * Check if the text contains ambiguity or approximation markers around counts.
 */
function hasAmbiguityMarkers(text: string): boolean {
  const lower = text.toLowerCase();
  // Tamil ambiguity markers: அல்லது (or), சுமார் (around), இருக்கலாம் (maybe), சில (some)
  if (
    /அல்லது/.test(lower) ||
    /சுமார்/.test(lower) ||
    /இருக்கலாம்/.test(lower) ||
    /ஏறக்குறைய/.test(lower) ||
    /சில\s+(பேர்|நபர்கள்|உறுப்பினர்கள்)/.test(lower)
  ) {
    return true;
  }

  // English ambiguity markers: or, maybe, around, approximately, about, some
  if (
    /\b(or|maybe|around|approximately|about|several|some)\b/.test(lower)
  ) {
    return true;
  }

  // Range patterns: "4 or 5", "4 அல்லது 5", "நான்கு ஐந்து", "நாலு அஞ்சு", "four or five"
  if (
    /(\d+|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|பத்து|one|two|three|four|five|six)\s+(அல்லது|or|-|to)\s+(\d+|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|பத்து|one|two|three|four|five|six)/i.test(
      lower
    )
  ) {
    return true;
  }

  // Consecutive numbers without conjunction: e.g. "நாலு அஞ்சு பேர்" or "four five people"
  if (
    /(நான்கு|நாலு|மூன்று|மூணு|இரண்டு|ரெண்டு|ஐந்து|அஞ்சு)\s+(ஐந்து|அஞ்சு|ஆறு|நான்கு|நாலு)\s*(பேர்|நபர்கள்|members|people)/i.test(
      lower
    )
  ) {
    return true;
  }

  if (
    /\b(three|four|five|six)\s+(four|five|six|seven)\s+(members|people|persons)\b/i.test(
      lower
    )
  ) {
    return true;
  }

  return false;
}

/**
 * Extract total household member count.
 */
function extractTotalMembers(
  text: string
): ExtractedField<number> | undefined {
  const isAmbiguous = hasAmbiguityMarkers(text);

  // If text has ambiguity markers regarding member counts
  if (isAmbiguous) {
    // Check if the ambiguity is specifically in the context of people/members
    if (
      /பேர்|நபர்கள்|உறுப்பினர்கள்|members|people|persons|family/i.test(text)
    ) {
      return {
        value: null,
        rawMatch: text,
        confidence: 'UNCERTAIN',
        reason: 'Ambiguous or approximate member count detected (e.g. range or uncertain estimate)',
      };
    }
  }

  // Family composite patterns (e.g. "mother father and two children", "அப்பா அம்மா இரண்டு குழந்தைகள்")
  const compositeLower = text.toLowerCase();
  let compositeCount = 0;
  let compositeFound = false;

  if (/\b(mother|wife|mom|அம்மா|மனைவி|தாய்)\b/i.test(compositeLower)) {
    compositeCount += 1;
    compositeFound = true;
  }
  if (/\b(father|husband|dad|அப்பா|கணவர்|தந்தை)\b/i.test(compositeLower)) {
    compositeCount += 1;
    compositeFound = true;
  }
  const childrenMatch = compositeLower.match(
    /(\d+|one|two|three|four|five|six|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஒரு|ரெண்டு|மூணு|நாலு|அஞ்சு)\s*(children|kids|குழந்தைகள்|பிள்ளைகள்)/i
  );
  if (childrenMatch) {
    const numKids = parseWordOrDigitNumber(childrenMatch[1]);
    if (numKids !== null) {
      compositeCount += numKids;
      compositeFound = true;
    }
  }

  if (compositeFound && compositeCount > 0 && !isAmbiguous) {
    return {
      value: compositeCount,
      rawMatch: text,
      confidence: 'CONFIRMED',
    };
  }

  // Direct count patterns
  // Pattern 1: e.g. "four members", "4 members", "நான்கு பேர்", "4 பேர்"
  const directPatterns = [
    // Tamil: [number] பேர் / நபர்கள் / உறுப்பினர்கள்
    /(\d+|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|பத்து|பதினொன்று|பன்னிரண்டு|ஒரு|ரெண்டு|மூணு|நாலு|அஞ்சு)\s*(?:பேர்|நபர்கள்|உறுப்பினர்கள்|ஆட்கள்)/i,
    // English / Mixed: [number] members / people / persons
    /(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(?:members|people|persons)/i,
    // Tamil reverse: பேர் / உறுப்பினர்கள் [number]
    /(?:உறுப்பினர்கள்|நபர்கள்)\s*[:=]?\s*(\d+|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|பத்து|ஒரு|ரெண்டு|மூணு|நாலு|அஞ்சு)/i,
    // English reverse: total members [number]
    /(?:total\s*members|household\s*members|family\s*members)\s*(?:is|are|=|:)?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)/i,
  ];

  for (const pat of directPatterns) {
    const match = text.match(pat);
    if (match) {
      const num = parseWordOrDigitNumber(match[1]);
      if (num !== null && num > 0) {
        return {
          value: num,
          rawMatch: match[0],
          confidence: 'CONFIRMED',
        };
      }
    }
  }

  return undefined;
}

/**
 * Extract male member count.
 */
function extractMaleCount(text: string): ExtractedField<number> | undefined {
  const patterns = [
    /(\d+|one|two|three|four|five|six|seven|eight|nine|ten|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|பத்து|ஒரு|ஒருவர்|இருவர்|மூவர்|நால்வர்|ஐவர்|ரெண்டு|மூணு|நாலு|அஞ்சு)\s*(?:ஆண்கள்|ஆண்|ஆம்பளை|males?|men|man|boys?)/i,
    /(?:ஆண்கள்|males?|men)\s*[:=]?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஒரு|ஒருவர்|இருவர்|மூவர்|நால்வர்|ஐவர்|ரெண்டு|மூணு|நாலு|அஞ்சு)/i,
  ];

  for (const pat of patterns) {
    const match = text.match(pat);
    if (match) {
      const num = parseWordOrDigitNumber(match[1]);
      if (num !== null) {
        return {
          value: num,
          rawMatch: match[0],
          confidence: 'CONFIRMED',
        };
      }
    }
  }
  return undefined;
}

/**
 * Extract female member count.
 */
function extractFemaleCount(text: string): ExtractedField<number> | undefined {
  const patterns = [
    /(\d+|one|two|three|four|five|six|seven|eight|nine|ten|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஆறு|ஏழு|எட்டு|ஒன்பது|பத்து|ஒரு|ஒருவர்|இருவர்|மூவர்|நால்வர்|ஐவர்|ரெண்டு|மூணு|நாலு|அஞ்சு)\s*(?:பெண்கள்|பெண்|பொம்பளை|females?|women|woman|girls?)/i,
    /(?:பெண்கள்|females?|women)\s*[:=]?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஒரு|ஒருவர்|இருவர்|மூவர்|நால்வர்|ஐவர்|ரெண்டு|மூணு|நாலு|அஞ்சு)/i,
  ];

  for (const pat of patterns) {
    const match = text.match(pat);
    if (match) {
      const num = parseWordOrDigitNumber(match[1]);
      if (num !== null) {
        return {
          value: num,
          rawMatch: match[0],
          confidence: 'CONFIRMED',
        };
      }
    }
  }
  return undefined;
}

/**
 * Extract transgender member count.
 */
function extractTransgenderCount(
  text: string
): ExtractedField<number> | undefined {
  const patterns = [
    /(\d+|one|two|three|four|five|six|seven|eight|nine|ten|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஒரு|ஒருவர்|இருவர்|மூவர்|நால்வர்|ஐவர்|ரெண்டு|மூணு|நாலு|அஞ்சு)\s*(?:திருநங்கை|திருநங்கைகள்|மூன்றாம்\s*பாலினம்|transgender|trans)/i,
    /(?:திருநங்கை|திருநங்கைகள்|மூன்றாம்\s*பாலினம்|transgender|trans)\s*[:=]?\s*(\d+|one|two|three|four|five|six|seven|eight|nine|ten|ஒன்று|இரண்டு|மூன்று|நான்கு|ஐந்து|ஒரு|ஒருவர்|இருவர்|மூவர்|நால்வர்|ஐவர்|ரெண்டு|மூணு|நாலு|அஞ்சு)/i,
  ];

  for (const pat of patterns) {
    const match = text.match(pat);
    if (match) {
      const num = parseWordOrDigitNumber(match[1]);
      if (num !== null) {
        return {
          value: num,
          rawMatch: match[0],
          confidence: 'CONFIRMED',
        };
      }
    }
  }
  return undefined;
}

/**
 * Extract Head of Household Name.
 */
function extractHeadName(text: string): ExtractedField<string> | undefined {
  // Tamil patterns
  const tamilMatch = text.match(
    /(?:குடும்பத்\s*தலைவர்|குடும்ப\s*தலைவர்|தலைவர்)\s*(?:பெயர்\s*)?(?:என்பது\s*|ஆகும்\s*|:)?\s*([^\s,.:;]+(?:\s+[^\s,.:;]+)?)/i
  );
  if (tamilMatch && tamilMatch[1]) {
    const name = tamilMatch[1].trim();
    if (name.length > 1 && !/^(பேர்|நபர்கள்|வீடு|ஆண்|பெண்)$/.test(name)) {
      return {
        value: name,
        rawMatch: tamilMatch[0],
        confidence: 'CONFIRMED',
      };
    }
  }

  // English patterns
  const englishMatch = text.match(
    /(?:head\s*of\s*(?:the\s*)?household|household\s*head|head\s*name)\s*(?:is|:|=)?\s*([A-Za-z]+(?:\s+[A-Za-z]+)?)/i
  );
  if (englishMatch && englishMatch[1]) {
    const name = englishMatch[1].trim();
    if (name.length > 1 && !/^(is|are|the|four|three|two|one|rented|owned)$/i.test(name)) {
      return {
        value: name,
        rawMatch: englishMatch[0],
        confidence: 'CONFIRMED',
      };
    }
  }

  return undefined;
}

/**
 * Extract Housing Ownership Status: OWNED | RENTED | OTHER.
 */
function extractOwnershipStatus(
  text: string
): ExtractedField<OwnershipStatus> | undefined {
  const lower = text.toLowerCase();

  // OWNED
  if (/சொந்த\s*வீடு|சொந்தம்|சொந்தமாக|owned|own\s*house|own\s*home/.test(lower)) {
    return {
      value: 'OWNED',
      rawMatch: 'OWNED',
      confidence: 'CONFIRMED',
    };
  }

  // RENTED
  if (/வாடகை\s*வீடு|வாடகை|வாடகைக்கு|rented|rental|rent/.test(lower)) {
    return {
      value: 'RENTED',
      rawMatch: 'RENTED',
      confidence: 'CONFIRMED',
    };
  }

  // OTHER
  if (
    /பிற\s*உரிமை|அரசு\s*வீடு|இலவச\s*வீடு|மற்றவை|other\s*ownership|government\s*quarters/.test(
      lower
    )
  ) {
    return {
      value: 'OTHER',
      rawMatch: 'OTHER',
      confidence: 'CONFIRMED',
    };
  }

  return undefined;
}

/**
 * Extract Drinking Water Source.
 */
function extractDrinkingWater(text: string): ExtractedField<string> | undefined {
  const lower = text.toLowerCase();

  if (/குடிநீர்\s*குழாய்|குழாய்\s*நீர்|குழாய்|tap\s*water|pipe\s*water|piped\s*water|tap/.test(lower)) {
    return {
      value: 'Tap Water',
      rawMatch: 'Tap Water',
      confidence: 'CONFIRMED',
    };
  }

  if (/கிணற்று\s*நீர்|கிணறு|well\s*water|well/.test(lower)) {
    return {
      value: 'Well Water',
      rawMatch: 'Well Water',
      confidence: 'CONFIRMED',
    };
  }

  if (/ஆழ்துளை\s*கிணறு|போர்வெல்|போர்|tube\s*well|borewell|handpump/.test(lower)) {
    return {
      value: 'Tube Well',
      rawMatch: 'Tube Well',
      confidence: 'CONFIRMED',
    };
  }

  if (/வண்டி\s*நீர்|லாரி\s*நீர்|tanker|bottled\s*water|mineral\s*water/.test(lower)) {
    return {
      value: 'Tanker Truck',
      rawMatch: 'Tanker Truck',
      confidence: 'CONFIRMED',
    };
  }

  return undefined;
}

/**
 * Extract Lighting Source.
 */
function extractLightingSource(text: string): ExtractedField<string> | undefined {
  const lower = text.toLowerCase();

  if (/மின்சாரம்|மின்\s*இணைப்பு|கரண்ட்|electricity|electric|power/.test(lower)) {
    return {
      value: 'Electricity',
      rawMatch: 'Electricity',
      confidence: 'CONFIRMED',
    };
  }

  if (/சூரிய\s*சக்தி|சோலார்|solar|solar\s*power/.test(lower)) {
    return {
      value: 'Solar',
      rawMatch: 'Solar',
      confidence: 'CONFIRMED',
    };
  }

  if (/மண்ணெண்ணெய்|விளக்கு|kerosene|oil\s*lamp/.test(lower)) {
    return {
      value: 'Kerosene',
      rawMatch: 'Kerosene',
      confidence: 'CONFIRMED',
    };
  }

  return undefined;
}

/**
 * Extract Latrine Facility Availability: 'Yes' | 'No'.
 */
function extractLatrineFacility(
  text: string
): ExtractedField<string> | undefined {
  const lower = text.toLowerCase();

  // Negative mentions
  if (
    /கழிப்பறை\s*(?:வசதி\s*)?(?:இல்லை|இல்ல)|டாய்லெட்\s*(?:இல்லை|இல்ல)|latrine\s*(?:facility\s*)?no|toilet\s*(?:facility\s*)?no|no\s*latrine|no\s*toilet|latrine\s*not\s*available|toilet\s*not\s*available/.test(
      lower
    )
  ) {
    return {
      value: 'No',
      rawMatch: 'No',
      confidence: 'CONFIRMED',
    };
  }

  // Positive mentions
  if (
    /கழிப்பறை\s*(?:வசதி\s*)?(?:ஆம்|உள்ளது|உண்டு|இருக்கிறது|இருக்கு)|டாய்லெட்\s*(?:ஆம்|இருக்கு|உள்ளது)|latrine\s*(?:facility\s*)?(?:yes|available)|toilet\s*(?:facility\s*)?(?:yes|available)|has\s*latrine|has\s*toilet/.test(
      lower
    )
  ) {
    return {
      value: 'Yes',
      rawMatch: 'Yes',
      confidence: 'CONFIRMED',
    };
  }

  return undefined;
}

/**
 * Main offline extraction function: parses recognized speech into structured household fields.
 * Strictly avoids guessing or silently saving ambiguous data.
 */
export function extractHouseholdFieldsFromSpeech(
  speechText: string
): HouseholdVoiceExtraction {
  const trimmed = speechText.trim();
  if (!trimmed) {
    return {
      rawText: speechText,
      language: 'en',
      overallStatus: 'EMPTY',
      uncertainFieldsCount: 0,
      extractedFieldsCount: 0,
    };
  }

  const language = detectVoiceLanguage(trimmed);

  const headName = extractHeadName(trimmed);
  const totalMembers = extractTotalMembers(trimmed);
  const maleCount = extractMaleCount(trimmed);
  const femaleCount = extractFemaleCount(trimmed);
  const transgenderCount = extractTransgenderCount(trimmed);
  const ownershipStatus = extractOwnershipStatus(trimmed);
  const drinkingWater = extractDrinkingWater(trimmed);
  const lightingSource = extractLightingSource(trimmed);
  const latrineFacility = extractLatrineFacility(trimmed);

  // Validate arithmetic consistency across gender breakdown and total count if both are extracted
  let isArithmeticMismatch = false;
  if (
    totalMembers &&
    totalMembers.value !== null &&
    (maleCount || femaleCount || transgenderCount)
  ) {
    const male = maleCount?.value || 0;
    const female = femaleCount?.value || 0;
    const trans = transgenderCount?.value || 0;
    const sum = male + female + trans;

    if (maleCount && femaleCount && sum !== totalMembers.value) {
      isArithmeticMismatch = true;
      totalMembers.confidence = 'UNCERTAIN';
      totalMembers.reason = `Gender breakdown sum (${sum}) does not match total members count (${totalMembers.value}).`;
    }
  }

  // Count extracted and uncertain fields
  const fields = [
    headName,
    totalMembers,
    maleCount,
    femaleCount,
    transgenderCount,
    ownershipStatus,
    drinkingWater,
    lightingSource,
    latrineFacility,
  ].filter(Boolean);

  const extractedFieldsCount = fields.filter((f) => f!.value !== null).length;
  const uncertainFieldsCount = fields.filter(
    (f) => f!.confidence === 'UNCERTAIN'
  ).length;

  // Determine overall extraction status
  let overallStatus: 'CONFIRMED' | 'NEEDS_REVIEW' | 'EMPTY' = 'CONFIRMED';

  if (extractedFieldsCount === 0) {
    overallStatus = 'NEEDS_REVIEW';
  } else if (uncertainFieldsCount > 0 || isArithmeticMismatch) {
    overallStatus = 'NEEDS_REVIEW';
  }

  return {
    rawText: trimmed,
    language,
    headName,
    totalMembers,
    maleCount,
    femaleCount,
    transgenderCount,
    ownershipStatus,
    drinkingWater,
    lightingSource,
    latrineFacility,
    overallStatus,
    uncertainFieldsCount,
    extractedFieldsCount,
  };
}

export const voiceExtractionEngine = {
  extractHouseholdData: (text: string, language?: VoiceLanguage) =>
    extractHouseholdFieldsFromSpeech(text),
  extractHouseholdFieldsFromSpeech,
};
