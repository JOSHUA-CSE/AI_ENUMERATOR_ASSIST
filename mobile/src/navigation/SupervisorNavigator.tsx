import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { SupervisorDashboardScreen } from '../features/supervisor/SupervisorDashboardScreen';
import { SupervisorLayoutDetailScreen } from '../features/supervisor/SupervisorLayoutDetailScreen';
import { SupervisorVerificationScreen } from '../features/supervisor/SupervisorVerificationScreen';
import { PlaceholderScreen } from '../components/PlaceholderScreen';
import { useTranslation } from '../core/localization';
import type { SupervisorStackParamList } from './navigationTypes';

const Stack = createNativeStackNavigator<SupervisorStackParamList>();

export function SupervisorNavigator(): React.JSX.Element {
  const { t } = useTranslation();

  return (
    <Stack.Navigator
      initialRouteName="SupervisorDashboard"
      screenOptions={{
        headerShown: false,
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="SupervisorDashboard" component={SupervisorDashboardScreen} />
      <Stack.Screen name="SupervisorLayoutDetail" component={SupervisorLayoutDetailScreen} />
      <Stack.Screen name="SupervisorVerification" component={SupervisorVerificationScreen} />

      <Stack.Screen name="AssignedLayoutsPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('assigned_layouts')}
            phaseInfo="Phase 6 — Supervisor Layout & HLB Assignment"
            description={t('placeholder_supervisors_desc')}
            onBack={() => props.navigation.goBack()}
            testID="assigned-layouts-placeholder-screen"
          />
        )}
      </Stack.Screen>

      <Stack.Screen name="EnumeratorsPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('enumerators')}
            phaseInfo="Phase 6 — Enumerator Block Assignment"
            description={t('placeholder_supervisors_desc')}
            onBack={() => props.navigation.goBack()}
            testID="enumerators-placeholder-screen"
          />
        )}
      </Stack.Screen>

      <Stack.Screen name="ProgressPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('progress')}
            phaseInfo="Phase 12 — Supervisor Fieldwork Monitoring"
            description={t('placeholder_progress_desc')}
            onBack={() => props.navigation.goBack()}
            testID="progress-placeholder-screen"
          />
        )}
      </Stack.Screen>
    </Stack.Navigator>
  );
}
