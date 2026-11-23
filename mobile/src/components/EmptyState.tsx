import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  useColorScheme,
  ViewStyle,
  StyleProp,
} from 'react-native';
import { PrimaryButton } from './PrimaryButton';

interface EmptyStateProps {
  title: string;
  description?: string;
  actionTitle?: string;
  onAction?: () => void;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

export function EmptyState({
  title,
  description,
  actionTitle,
  onAction,
  style,
  testID = 'empty-state',
}: EmptyStateProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';

  return (
    <View style={[styles.container, style]} testID={testID}>
      <Text style={[styles.title, { color: isDarkMode ? '#FFFFFF' : '#333333' }]}>
        {title}
      </Text>
      {description && (
        <Text style={[styles.description, { color: isDarkMode ? '#A0A0A0' : '#666666' }]}>
          {description}
        </Text>
      )}
      {actionTitle && onAction && (
        <PrimaryButton
          title={actionTitle}
          onPress={onAction}
          style={styles.actionButton}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 32,
    alignItems: 'center',
    justifyContent: 'center',
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 8,
  },
  description: {
    fontSize: 14,
    textAlign: 'center',
    lineHeight: 20,
    marginBottom: 16,
  },
  actionButton: {
    marginTop: 8,
    minWidth: 160,
  },
});
