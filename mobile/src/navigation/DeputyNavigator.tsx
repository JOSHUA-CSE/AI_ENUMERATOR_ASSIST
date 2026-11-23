import React from 'react';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { DeputyDashboardScreen } from '../features/deputy/DeputyDashboardScreen';
import { AreaListScreen } from '../features/deputy/AreaListScreen';
import { AreaMapScreen } from '../features/deputy/AreaMapScreen';
import { LayoutListScreen } from '../features/deputy/LayoutListScreen';
import { HlbGenerationScreen } from '../features/deputy/HlbGenerationScreen';
import { HlbReviewScreen } from '../features/deputy/HlbReviewScreen';
import { DeputyLayoutDetailScreen } from '../features/deputy/DeputyLayoutDetailScreen';
import { DeputyChangeRequestsScreen } from '../features/deputy/DeputyChangeRequestsScreen';
import { DeputySupervisorsScreen } from '../features/deputy/DeputySupervisorsScreen';
import { DeputyProgressScreen } from '../features/deputy/DeputyProgressScreen';
import { PlaceholderScreen } from '../components/PlaceholderScreen';
import { useTranslation } from '../core/localization';
import type { DeputyStackParamList } from './navigationTypes';

const Stack = createNativeStackNavigator<DeputyStackParamList>();

export function DeputyNavigator(): React.JSX.Element {
  const { t } = useTranslation();

  return (
    <Stack.Navigator
      initialRouteName="DeputyDashboard"
      screenOptions={{
        headerShown: false,
        animation: 'slide_from_right',
      }}
    >
      <Stack.Screen name="DeputyDashboard" component={DeputyDashboardScreen} />
      <Stack.Screen name="AreaList" component={AreaListScreen} />
      <Stack.Screen name="AreaMap" component={AreaMapScreen} />
      <Stack.Screen name="LayoutList" component={LayoutListScreen} />
      <Stack.Screen name="HlbGeneration" component={HlbGenerationScreen} />
      <Stack.Screen name="HlbReview" component={HlbReviewScreen} />
      <Stack.Screen name="DeputyLayoutDetail" component={DeputyLayoutDetailScreen} />
      <Stack.Screen name="DeputyChangeRequests" component={DeputyChangeRequestsScreen} />


      <Stack.Screen name="LayoutsPlaceholder">
        {(props) => (
          <PlaceholderScreen
            title={t('layouts')}
            phaseInfo="Phase 3 & 4 — Layouts + HLB Generation"
            description={t('placeholder_layouts_desc')}
            onBack={() => props.navigation.goBack()}
            testID="layouts-placeholder-screen"
          />
        )}
      </Stack.Screen>

      <Stack.Screen name="SupervisorsPlaceholder" component={DeputySupervisorsScreen} />
      <Stack.Screen name="DeputySupervisors" component={DeputySupervisorsScreen} />

      <Stack.Screen name="ProgressPlaceholder" component={DeputyProgressScreen} />
      <Stack.Screen name="DeputyProgress" component={DeputyProgressScreen} />
    </Stack.Navigator>
  );
}
