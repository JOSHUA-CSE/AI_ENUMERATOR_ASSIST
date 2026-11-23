import { t, useLanguageStore, en, ta } from '../src/core/localization';

describe('Localization System', () => {
  beforeEach(() => {
    useLanguageStore.getState().setLanguage('en');
  });

  test('1. English dictionary contains all required keys', () => {
    expect(en.app_title).toBe('AI-Enumerator Assistant');
    expect(en.role_deputy).toBe('Deputy Tahsildar');
    expect(en.role_supervisor).toBe('Supervisor');
    expect(en.role_enumerator).toBe('Enumerator');
    expect(en.login).toBe('LOGIN');
    expect(en.logout).toBe('LOGOUT');
    expect(en.coming_in_later_phase).toBe('Coming in a later phase');
  });

  test('2. Tamil dictionary contains translations for all English keys', () => {
    const enKeys = Object.keys(en) as (keyof typeof en)[];
    enKeys.forEach((key) => {
      expect(ta[key]).toBeDefined();
      expect(typeof ta[key]).toBe('string');
      expect(ta[key].length).toBeGreaterThan(0);
    });
    expect(ta.role_deputy).toBe('துணை வட்டாட்சியர்');
    expect(ta.role_supervisor).toBe('மேற்பார்வையாளர்');
    expect(ta.role_enumerator).toBe('கணக்கெடுப்பாளர்');
    expect(ta.login).toBe('உள்நுழைவு');
    expect(ta.logout).toBe('வெளியேறு');
  });

  test('3. t() helper resolves key in active language', () => {
    useLanguageStore.getState().setLanguage('en');
    expect(t('role_deputy')).toBe('Deputy Tahsildar');

    useLanguageStore.getState().setLanguage('ta');
    expect(t('role_deputy')).toBe('துணை வட்டாட்சியர்');
  });

  test('4. language switching toggle works', () => {
    expect(useLanguageStore.getState().language).toBe('en');
    useLanguageStore.getState().toggleLanguage();
    expect(useLanguageStore.getState().language).toBe('ta');
    useLanguageStore.getState().toggleLanguage();
    expect(useLanguageStore.getState().language).toBe('en');
  });
});
