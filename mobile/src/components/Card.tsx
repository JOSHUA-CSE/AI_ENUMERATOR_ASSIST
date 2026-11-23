import React from 'react';
import {
  StyleSheet,
  Text,
  View,
  useColorScheme,
  ViewStyle,
  TextStyle,
  StyleProp,
  Platform,
} from 'react-native';

interface CardProps {
  title?: string;
  subtitle?: string;
  rightHeader?: React.ReactNode;
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  titleStyle?: StyleProp<TextStyle>;
  testID?: string;
}

export function Card({
  title,
  subtitle,
  rightHeader,
  children,
  style,
  titleStyle,
  testID,
}: CardProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';

  const themeStyles = {
    card: {
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
      borderColor: isDarkMode ? '#333333' : '#E0E0E0',
    },
    title: { color: isDarkMode ? '#FFFFFF' : '#1A1A1A' },
    subtitle: { color: isDarkMode ? '#A0A0A0' : '#666666' },
  };

  return (
    <View style={[styles.card, themeStyles.card, style]} testID={testID}>
      {(title || rightHeader) && (
        <View style={styles.headerRow}>
          <View style={styles.titleContainer}>
            {title && <Text style={[styles.title, themeStyles.title, titleStyle]}>{title}</Text>}
            {subtitle && <Text style={[styles.subtitle, themeStyles.subtitle]}>{subtitle}</Text>}
          </View>
          {rightHeader && <View style={styles.rightHeader}>{rightHeader}</View>}
        </View>
      )}
      <View style={styles.content}>{children}</View>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    borderRadius: 8,
    borderWidth: 1,
    padding: 16,
    marginBottom: 16,
    ...Platform.select({
      web: {
        boxShadow: '0px 1px 3px rgba(0, 0, 0, 0.1)',
      },
      default: {
        elevation: 1,
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 1 },
        shadowOpacity: 0.1,
        shadowRadius: 2,
      },
    }),
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    borderBottomWidth: 1,
    borderBottomColor: '#ECECEC',
    paddingBottom: 10,
    marginBottom: 12,
  },
  titleContainer: {
    flex: 1,
  },
  title: {
    fontSize: 17,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  subtitle: {
    fontSize: 12,
    marginTop: 2,
  },
  rightHeader: {
    marginLeft: 8,
  },
  content: {
    width: '100%',
  },
});
