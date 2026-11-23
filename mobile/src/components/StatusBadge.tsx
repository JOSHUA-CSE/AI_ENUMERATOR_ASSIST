import React from 'react';
import { StyleSheet, Text, View, ViewStyle, StyleProp } from 'react-native';

export type StatusType =
  | 'DEPUTY_TAHSILDAR'
  | 'SUPERVISOR'
  | 'ENUMERATOR'
  | 'COMPLETED'
  | 'LOCKED'
  | 'PENDING'
  | 'SYNCED'
  | 'OFFLINE'
  | 'ONLINE'
  | 'APPROVED'
  | 'ASSIGNED'
  | 'ACTIVE'
  | 'INACTIVE'
  | 'REQUIRED'
  | 'IN_REVIEW'
  | 'DRAFT'
  | 'CANDIDATE'
  | 'VALID'
  | 'WARNING'
  | 'INVALID'
  | 'VILLAGE'
  | 'WARD'
  | 'DEFAULT';

interface StatusBadgeProps {
  type?: StatusType;
  status?: string;
  label?: string;
  style?: StyleProp<ViewStyle>;
  testID?: string;
}

const statusConfig: Record<StatusType, { bg: string; text: string; defaultLabel: string }> = {
  DEPUTY_TAHSILDAR: { bg: '#D32F2F', text: '#FFFFFF', defaultLabel: 'Deputy Tahsildar' },
  SUPERVISOR: { bg: '#F57C00', text: '#FFFFFF', defaultLabel: 'Supervisor' },
  ENUMERATOR: { bg: '#2E7D32', text: '#FFFFFF', defaultLabel: 'Enumerator' },
  COMPLETED: { bg: '#2E7D32', text: '#FFFFFF', defaultLabel: '✓ COMPLETED' },
  LOCKED: { bg: '#E65100', text: '#FFFFFF', defaultLabel: '⚠ LOCKED' },
  PENDING: { bg: '#1565C0', text: '#FFFFFF', defaultLabel: '● PENDING' },
  SYNCED: { bg: '#2E7D32', text: '#FFFFFF', defaultLabel: '✓ SYNCED' },
  ONLINE: { bg: '#2E7D32', text: '#FFFFFF', defaultLabel: '● ONLINE' },
  OFFLINE: { bg: '#C62828', text: '#FFFFFF', defaultLabel: '● OFFLINE' },
  APPROVED: { bg: '#2E7D32', text: '#FFFFFF', defaultLabel: '✓ APPROVED' },
  ASSIGNED: { bg: '#0284C7', text: '#FFFFFF', defaultLabel: '📋 ASSIGNED' },
  ACTIVE: { bg: '#2E7D32', text: '#FFFFFF', defaultLabel: '● ACTIVE' },
  INACTIVE: { bg: '#757575', text: '#FFFFFF', defaultLabel: 'INACTIVE' },
  REQUIRED: { bg: '#EA580C', text: '#FFFFFF', defaultLabel: '⚠ REQUIRED' },
  IN_REVIEW: { bg: '#F57C00', text: '#FFFFFF', defaultLabel: '⏳ IN REVIEW' },
  DRAFT: { bg: '#757575', text: '#FFFFFF', defaultLabel: 'DRAFT' },
  CANDIDATE: { bg: '#0284C7', text: '#FFFFFF', defaultLabel: 'CANDIDATE' },
  VALID: { bg: '#2E7D32', text: '#FFFFFF', defaultLabel: 'VALID' },
  WARNING: { bg: '#F57C00', text: '#FFFFFF', defaultLabel: 'WARNING' },
  INVALID: { bg: '#D32F2F', text: '#FFFFFF', defaultLabel: 'INVALID' },
  VILLAGE: { bg: '#0284C7', text: '#FFFFFF', defaultLabel: 'VILLAGE' },
  WARD: { bg: '#7C3AED', text: '#FFFFFF', defaultLabel: 'WARD' },
  DEFAULT: { bg: '#616161', text: '#FFFFFF', defaultLabel: 'STATUS' },
};

export function StatusBadge({
  type = 'DEFAULT',
  status,
  label,
  style,
  testID,
}: StatusBadgeProps): React.JSX.Element {
  const resolvedType = (type !== 'DEFAULT' ? type : (status as StatusType)) || 'DEFAULT';
  const config = statusConfig[resolvedType as StatusType] || statusConfig.DEFAULT;
  const displayLabel = label || status || config.defaultLabel;

  return (
    <View style={[styles.badge, { backgroundColor: config.bg }, style]} testID={testID}>
      <Text style={[styles.badgeText, { color: config.text }]}>{displayLabel}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 14,
    alignSelf: 'flex-start',
    justifyContent: 'center',
    alignItems: 'center',
  },
  badgeText: {
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.4,
  },
});
