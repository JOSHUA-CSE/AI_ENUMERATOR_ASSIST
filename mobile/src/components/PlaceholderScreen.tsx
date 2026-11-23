import React from 'react';
import { StyleSheet, Text, View, useColorScheme } from 'react-native';
import { ScreenContainer } from './ScreenContainer';
import { AppHeader } from './AppHeader';
import { Card } from './Card';
import { PrimaryButton } from './PrimaryButton';
import { useTranslation } from '../core/localization';

interface PlaceholderScreenProps {
  title: string;
  phaseInfo?: string;
  description?: string;
  onBack: () => void;
  testID?: string;
}

export function PlaceholderScreen({
  title,
  phaseInfo,
  description,
  onBack,
  testID = 'placeholder-screen',
}: PlaceholderScreenProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { t } = useTranslation();

  const themeStyles = {
    title: { color: isDarkMode ? '#FFFFFF' : '#1A1A1A' },
    subtext: { color: isDarkMode ? '#B0B0B0' : '#555555' },
    phaseBadge: {
      backgroundColor: isDarkMode ? '#0D47A1' : '#E3F2FD',
      borderColor: isDarkMode ? '#1976D2' : '#90CAF9',
    },
    phaseText: { color: isDarkMode ? '#90CAF9' : '#0D47A1' },
  };

  return (
    <ScreenContainer scrollable={false} testID={testID}>
      <AppHeader title={title} showBack onBack={onBack} />

      <View style={styles.bodyContainer}>
        <Card title={title} style={styles.card}>
          <View style={[styles.phaseBadge, themeStyles.phaseBadge]}>
            <Text style={[styles.phaseText, themeStyles.phaseText]}>
              ⏳ {phaseInfo || t('coming_in_later_phase')}
            </Text>
          </View>

          <Text style={[styles.mainNotice, themeStyles.title]}>
            {t('coming_in_later_phase')}
          </Text>

          <Text style={[styles.description, themeStyles.subtext]}>
            {description || t('placeholder_desc')}
          </Text>

          <PrimaryButton
            title={`← ${t('back')}`}
            onPress={onBack}
            style={styles.backButton}
            testID="placeholder-back-button"
          />
        </Card>
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  bodyContainer: {
    flex: 1,
    justifyContent: 'center',
    paddingVertical: 20,
  },
  card: {
    padding: 24,
    alignItems: 'center',
  },
  phaseBadge: {
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    marginBottom: 16,
  },
  phaseText: {
    fontSize: 13,
    fontWeight: '700',
  },
  mainNotice: {
    fontSize: 20,
    fontWeight: 'bold',
    textAlign: 'center',
    marginBottom: 12,
  },
  description: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 22,
    marginBottom: 24,
    paddingHorizontal: 12,
  },
  backButton: {
    width: '100%',
    maxWidth: 260,
  },
});
