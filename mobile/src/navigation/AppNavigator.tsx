import React, { useEffect } from 'react';
import { View, StyleSheet, useColorScheme } from 'react-native';
import { NavigationContainer, DefaultTheme, DarkTheme } from '@react-navigation/native';
import { useAuthStore } from '../core/authStore';
import { useTranslation } from '../core/localization';
import { LoadingIndicator } from '../components/LoadingIndicator';
import { AuthNavigator } from './AuthNavigator';
import { DeputyNavigator } from './DeputyNavigator';
import { SupervisorNavigator } from './SupervisorNavigator';
import { EnumeratorNavigator } from './EnumeratorNavigator';

export default function AppNavigator(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { status, user, restoreSession } = useAuthStore();
  const { t } = useTranslation();

  useEffect(() => {
    // Restore session on application startup
    restoreSession();
  }, [restoreSession]);

  const navTheme = isDarkMode ? DarkTheme : DefaultTheme;

  // 1. Initial Session Restoration State (no flickering to Login)
  if (status === 'idle' || status === 'initializing') {
    return (
      <View
        style={[
          styles.container,
          { backgroundColor: isDarkMode ? '#121212' : '#F5F5F7' },
        ]}
        testID="session-loading-view"
      >
        <LoadingIndicator
          message={t('restoring_session')}
          testID="loading-indicator"
        />
      </View>
    );
  }

  // 2. Unauthenticated State -> Auth Navigator (Login Screen)
  if (status === 'unauthenticated' || !user) {
    return (
      <NavigationContainer theme={navTheme}>
        <AuthNavigator />
      </NavigationContainer>
    );
  }

  // 3. Authenticated State -> Authoritative Role Resolution
  const renderRoleNavigator = () => {
    switch (user.role) {
      case 'DEPUTY_TAHSILDAR':
        return <DeputyNavigator />;
      case 'SUPERVISOR':
        return <SupervisorNavigator />;
      case 'ENUMERATOR':
        return <EnumeratorNavigator />;
      default:
        // Fallback for corrupted or unknown role
        return <AuthNavigator />;
    }
  };

  return (
    <NavigationContainer theme={navTheme}>
      {renderRoleNavigator()}
    </NavigationContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
