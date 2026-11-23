import React from 'react';
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
  StyleProp,
  useColorScheme,
} from 'react-native';

interface SecondaryButtonProps {
  title: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  textStyle?: StyleProp<TextStyle>;
  testID?: string;
  variant?: 'outline' | 'neutral';
}

export function SecondaryButton({
  title,
  onPress,
  loading = false,
  disabled = false,
  style,
  textStyle,
  testID,
  variant = 'outline',
}: SecondaryButtonProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const isActionDisabled = disabled || loading;

  const getBorderColor = () => {
    if (variant === 'neutral') {
      return isDarkMode ? '#555555' : '#CCCCCC';
    }
    return '#0066CC';
  };

  const getTextColor = () => {
    if (variant === 'neutral') {
      return isDarkMode ? '#E0E0E0' : '#444444';
    }
    return '#0066CC';
  };

  return (
    <TouchableOpacity
      style={[
        styles.button,
        {
          borderColor: getBorderColor(),
          backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
        },
        isActionDisabled && styles.disabled,
        style,
      ]}
      onPress={onPress}
      disabled={isActionDisabled}
      activeOpacity={0.7}
      testID={testID}
    >
      {loading ? (
        <ActivityIndicator color={getTextColor()} size="small" />
      ) : (
        <Text style={[styles.buttonText, { color: getTextColor() }, textStyle]}>
          {title}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    height: 52,
    borderRadius: 6,
    borderWidth: 1.5,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  buttonText: {
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.6,
  },
  disabled: {
    opacity: 0.5,
  },
});
