import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  useColorScheme,
  ViewStyle,
  StyleProp,
} from 'react-native';

import { extractErrorMessage } from '../core/apiClient';

interface ErrorMessageProps {
  message: string | any;
  onRetry?: () => void;
  retryText?: string;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function ErrorMessage({
  message,
  onRetry,
  retryText = 'RETRY',
  style,
  testID = 'error-message',
}: ErrorMessageProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const rawMsg = extractErrorMessage(message);
  const displayMessage =
    typeof rawMsg === 'string' &&
    rawMsg !== '[object Object]' &&
    rawMsg.trim() !== '{}' &&
    rawMsg.trim() !== ''
      ? rawMsg
      : 'An unexpected error occurred. Please try again.';

  return (
    <View
      style={[
        styles.container,
        {
          backgroundColor: isDarkMode ? '#2D1212' : '#FFEBEE',
          borderColor: isDarkMode ? '#C62828' : '#FFCDD2',
        },
        style,
      ]}
      testID={testID}
    >
      <View style={styles.textContainer}>
        <Text style={[styles.iconText, { color: isDarkMode ? '#EF5350' : '#D32F2F' }]}>⚠</Text>
        <Text
          style={[styles.message, { color: isDarkMode ? '#FFCDD2' : '#C62828' }]}
          testID="error-text"
        >
          {displayMessage}
        </Text>
      </View>

      {onRetry && (
        <TouchableOpacity
          style={[
            styles.retryButton,
            { backgroundColor: isDarkMode ? '#C62828' : '#D32F2F' },
          ]}
          onPress={onRetry}
          activeOpacity={0.8}
          testID="retry-button"
        >
          <Text style={styles.retryButtonText}>{retryText}</Text>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    borderWidth: 1,
    borderRadius: 6,
    padding: 14,
    marginVertical: 10,
    flexDirection: 'column',
  },
  textContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  iconText: {
    fontSize: 18,
    marginRight: 8,
    fontWeight: 'bold',
  },
  message: {
    fontSize: 14,
    fontWeight: '500',
    flex: 1,
    lineHeight: 20,
  },
  retryButton: {
    alignSelf: 'flex-start',
    marginTop: 10,
    paddingHorizontal: 16,
    paddingVertical: 6,
    borderRadius: 4,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontSize: 13,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
});
