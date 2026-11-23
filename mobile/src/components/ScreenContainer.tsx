import React from 'react';
import {
  StyleSheet,
  View,
  ScrollView,
  useColorScheme,
  ViewStyle,
  StyleProp,
  RefreshControlProps,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

interface ScreenContainerProps {
  children: React.ReactNode;
  scrollable?: boolean;
  style?: StyleProp<ViewStyle>;
  contentContainerStyle?: StyleProp<ViewStyle>;
  refreshControl?: React.ReactElement<RefreshControlProps>;
  testID?: string;
}

export function ScreenContainer({
  children,
  scrollable = false,
  style,
  contentContainerStyle,
  refreshControl,
  testID,
}: ScreenContainerProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';

  const containerStyle = {
    backgroundColor: isDarkMode ? '#121212' : '#F5F5F7',
    flex: 1,
  };

  if (scrollable) {
    return (
      <SafeAreaView style={[containerStyle, style]} edges={['top', 'left', 'right', 'bottom']} testID={testID}>
        <ScrollView
          contentContainerStyle={[styles.scrollContent, contentContainerStyle]}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
          refreshControl={refreshControl}
        >
          {children}
        </ScrollView>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={[containerStyle, style]} edges={['top', 'left', 'right', 'bottom']} testID={testID}>
      <View style={[styles.staticContent, contentContainerStyle]}>{children}</View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  scrollContent: {
    flexGrow: 1,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  staticContent: {
    flex: 1,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
});
