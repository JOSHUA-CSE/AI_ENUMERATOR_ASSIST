import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { BuildingDetailScreen } from '../features/enumerator/BuildingDetailScreen';
import { EnumeratorDashboardScreen } from '../features/enumerator/EnumeratorDashboardScreen';
import { EnumeratorHlbDetailScreen } from '../features/enumerator/EnumeratorHlbDetailScreen';
import { HouseholdFormScreen } from '../features/enumerator/HouseholdFormScreen';
import { PlaceholderScreen } from '../components/PlaceholderScreen';
import { useTranslation } from '../core/localization';
import type { EnumeratorStackParamList } from './navigationTypes';

const Stack = createNativeStackNavigator<EnumeratorStackParamList>();

export function EnumeratorNavigator(): React.JSX.Element {
  const { t } = useTranslation();

  return (
    <Stack.Navigator
      initialRouteName="EnumeratorDashboard"
      screenOptions={{
        headerShown: false,
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="EnumeratorDashboard" component={EnumeratorDashboardScreen} />
      <Stack.Screen name="EnumeratorHlbDetail" component={EnumeratorHlbDetailScreen} />
      <Stack.Screen name="BuildingDetail" component={BuildingDetailScreen} />
      <Stack.Screen name="HouseholdForm" component={HouseholdFormScreen} />


      <Stack.Screen name="MyHLBPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('my_hlb')}
            phaseInfo="Phase 7 — SQLite Offline Fieldwork (expo-sqlite)"
            description={t('placeholder_hlb_desc')}
            onBack={() => props.navigation.goBack()}
            testID="my-hlb-placeholder-screen"
          />
        )}
      </Stack.Screen>

      <Stack.Screen name="TodaysProgressPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('todays_progress')}
            phaseInfo="Phase 7 & 8 — Field Progress & Questionnaire"
            description={t('placeholder_progress_desc')}
            onBack={() => props.navigation.goBack()}
            testID="todays-progress-placeholder-screen"
          />
        )}
      </Stack.Screen>

      <Stack.Screen name="PendingHousesPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('pending_houses')}
            phaseInfo="Phase 7 & 11 — House Listing & Revisit Management"
            description={t('placeholder_houses_desc')}
            onBack={() => props.navigation.goBack()}
            testID="pending-houses-placeholder-screen"
          />
        )}
      </Stack.Screen>

      <Stack.Screen name="SyncStatusPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('sync_status')}
            phaseInfo="Phase 8 — SQLite Offline Sync Engine"
            description={t('placeholder_sync_desc')}
            onBack={() => props.navigation.goBack()}
            testID="sync-status-placeholder-screen"
          />
        )}
      </Stack.Screen>
    </Stack.Navigator>
  );
}
