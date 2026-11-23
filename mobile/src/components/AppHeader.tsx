import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  useColorScheme,
  ViewStyle,
  StyleProp,
  Platform,
} from 'react-native';
import { StatusBadge, StatusType } from './StatusBadge';
import { useTranslation } from '../core/localization';

interface AppHeaderProps {
  title?: string;
  subtitle?: string;
  roleType?: StatusType;
  roleLabel?: string;
  userName?: string;
  showBack?: boolean;
  onBack?: () => void;
  showLanguageToggle?: boolean;
  rightAction?: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function AppHeader({
  title,
  subtitle,
  roleType,
  roleLabel,
  userName,
  showBack = false,
  onBack,
  showLanguageToggle = true,
  rightAction,
  style,
  testID = 'app-header',
}: AppHeaderProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { t, language, toggleLanguage } = useTranslation();

  const displayTitle = title || t('app_title');
  const displaySubtitle = subtitle || t('gov_subtitle');

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
          borderBottomColor: isDarkMode ? '#333333' : '#E5E5E5',
        },
        style,
      ]}
      testID={testID}
    >
      {/* Top Bar: Back button, Title & Language / Action */}
      <View style={styles.topRow}>
        <View style={styles.leftGroup}>
          {(showBack || Boolean(onBack)) && (
            <TouchableOpacity
              onPress={onBack}
              style={styles.backButton}
              activeOpacity={0.7}
              testID="header-back-button"
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Text style={[styles.backButtonText, { color: isDarkMode ? '#38BDF8' : '#0066CC' }]}>
                ← {t('back')}
              </Text>
            </TouchableOpacity>
          )}
        </View>

        <View style={styles.rightGroup}>
          {showLanguageToggle && (
            <TouchableOpacity
              onPress={toggleLanguage}
              style={[
                styles.langButton,
                { borderColor: isDarkMode ? '#555555' : '#CCCCCC' },
              ]}
              activeOpacity={0.7}
              testID="language-toggle-button"
            >
              <Text
                style={[
                  styles.langButtonText,
                  { color: isDarkMode ? '#90CAF9' : '#0066CC' },
                ]}
              >
                {language === 'en' ? 'தமிழ்' : 'English'}
              </Text>
            </TouchableOpacity>
          )}
          {rightAction}
        </View>
      </View>

      {/* Main Title & Subtitle */}
      <View style={styles.titleContainer}>
        <Text
          style={[styles.title, { color: isDarkMode ? '#FFFFFF' : '#1A1A1A' }]}
          numberOfLines={1}
          testID="header-title"
        >
          {displayTitle}
        </Text>
        <Text
          style={[
            styles.subtitle,
            { color: isDarkMode ? '#90CAF9' : '#0066CC' },
          ]}
          testID="header-subtitle"
        >
          {displaySubtitle}
        </Text>
      </View>

      {/* Optional User & Role Info Row */}
      {(roleType || userName) && (
        <View style={styles.infoRow}>
          {userName && (
            <Text
              style={[
                styles.userNameText,
                { color: isDarkMode ? '#CCCCCC' : '#555555' },
              ]}
            >
              👤 {userName}
            </Text>
          )}
          {roleType && (
            <StatusBadge
              type={roleType}
              label={roleLabel}
              style={styles.roleBadge}
              testID="header-role-badge"
            />
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
    borderBottomWidth: 1,
    ...Platform.select({
      web: {
        boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.1)',
      },
      default: {
        elevation: 2,
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 1.5,
      },
    }),
  },
  topRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
    minHeight: 32,
  },
  leftGroup: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  rightGroup: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  backButton: {
    paddingVertical: 4,
    paddingHorizontal: 8,
    borderRadius: 4,
  },
  backButtonText: {
    fontSize: 14,
    fontWeight: '700',
    color: '#0066CC',
  },
  langButton: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 14,
    borderWidth: 1,
    marginLeft: 8,
  },
  langButtonText: {
    fontSize: 12,
    fontWeight: '700',
  },
  titleContainer: {
    alignItems: 'flex-start',
    marginVertical: 2,
  },
  title: {
    fontSize: 20,
    fontWeight: 'bold',
    letterSpacing: 0.3,
  },
  subtitle: {
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 1.2,
    marginTop: 2,
  },
  infoRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: '#EEEEEE',
  },
  userNameText: {
    fontSize: 13,
    fontWeight: '600',
  },
  roleBadge: {
    marginLeft: 'auto',
  },
});
