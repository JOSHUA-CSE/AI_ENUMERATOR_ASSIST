import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  ActivityIndicator,
  useColorScheme,
  ViewStyle,
  StyleProp,
} from 'react-native';

interface LoadingIndicatorProps {
  message?: string;
  size?: 'small' | 'large';
  color?: string;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function LoadingIndicator({
  message,
  size = 'large',
  color = '#0066CC',
  style,
  testID = 'loading-indicator',
}: LoadingIndicatorProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';

  return (
    <View style={[styles.container, style]} testID={testID}>
      <ActivityIndicator size={size} color={color} />
      {message && (
        <Text style={[styles.message, { color: isDarkMode ? '#FFFFFF' : '#333333' }]}>
          {message}
        </Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  message: {
    marginTop: 16,
    fontSize: 15,
    fontWeight: '600',
    textAlign: 'center',
    letterSpacing: 0.2,
  },
});
