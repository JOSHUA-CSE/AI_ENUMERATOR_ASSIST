import { create } from 'zustand';
import { en, TranslationKey } from './en';
import { ta } from './ta';

export type Language = 'en' | 'ta';

interface LanguageState {
  language: Language;
  setLanguage: (lang: Language) => void;
  toggleLanguage: () => void;
}

export const useLanguageStore = create<LanguageState>((set) => ({
  language: 'en',
  setLanguage: (language: Language) => set({ language }),
  toggleLanguage: () =>
    set((state) => ({ language: state.language === 'en' ? 'ta' : 'en' })),
}));

const translations: Record<Language, Record<TranslationKey, string>> = {
  en,
  ta,
};

/**
 * Get translation for key in current or specified language.
 */
export function t(key: TranslationKey, lang?: Language): string {
  const currentLang = lang || useLanguageStore.getState().language;
  const dict = translations[currentLang] || translations.en;
  return dict[key] || en[key] || key;
}

/**
 * Hook to get current language and translation function with auto-re-render.
 */
export function useTranslation() {
  const language = useLanguageStore((state) => state.language);
  const toggleLanguage = useLanguageStore((state) => state.toggleLanguage);
  const setLanguage = useLanguageStore((state) => state.setLanguage);

  const translate = (key: TranslationKey): string => {
    return t(key, language);
  };

  return {
    t: translate,
    language,
    toggleLanguage,
    setLanguage,
  };
}

export { en, ta };
export type { TranslationKey };
