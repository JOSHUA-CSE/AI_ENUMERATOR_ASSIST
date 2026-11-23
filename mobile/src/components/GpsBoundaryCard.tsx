import React from 'react';
import {
  StyleSheet,
  View,
  Text,
  TouchableOpacity,
  ActivityIndicator,
  useColorScheme,
} from 'react-native';
import { useTranslation } from '../core/localization';
import type { BoundaryStatus } from '../core/boundaryService';
import type { GpsAccuracyCategory } from '../core/gpsService';

export interface FieldworkCoverage {
  totalBuildings: number;
  completedBuildings: number;
  inProgressBuildings?: number;
  revisitBuildings?: number;
  remainingBuildings: number;
  coveragePercentage: number;
  totalHouseholds?: number;
  completedHouseholds?: number;
}

export interface GpsBoundaryCardProps {
  gpsStatus: 'READY' | 'REFRESHING' | 'PERMISSION_DENIED' | 'UNAVAILABLE';
  accuracyCategory: GpsAccuracyCategory;
  accuracyMeters: number | null;
  boundaryStatus: BoundaryStatus;
  boundaryDistanceMeters?: number | null;
  coverage?: FieldworkCoverage | null;
  onRefreshGps?: () => void;
  style?: any;
  testID?: string;
}

export function GpsBoundaryCard({
  gpsStatus,
  accuracyCategory,
  accuracyMeters,
  boundaryStatus,
  boundaryDistanceMeters,
  coverage,
  onRefreshGps,
  style,
  testID = 'gps-boundary-card',
}: GpsBoundaryCardProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { t } = useTranslation();

  // GPS indicator styling
  const isGpsAvailable = gpsStatus === 'READY' && accuracyCategory !== 'UNKNOWN';
  const isGpsDenied = gpsStatus === 'PERMISSION_DENIED';
  const isGpsDisabled = gpsStatus === 'UNAVAILABLE';

  const gpsBadgeColor = isGpsDenied || isGpsDisabled
    ? '#EF4444'
    : accuracyCategory === 'GOOD'
    ? '#10B981'
    : '#F59E0B';

  const gpsStatusText = isGpsDenied
    ? t('gps_permission_required')
    : isGpsDisabled
    ? t('location_services_disabled')
    : accuracyCategory === 'GOOD'
    ? t('good_accuracy')
    : accuracyCategory === 'POOR'
    ? t('low_accuracy')
    : t('location_unavailable');

  // Boundary indicator styling
  let boundaryColor = '#94A3B8';
  let boundaryIcon = '?';
  let boundaryText = t('boundary_uncertain');

  if (boundaryStatus === 'INSIDE') {
    boundaryColor = '#10B981';
    boundaryIcon = '✓';
    boundaryText = t('inside_assigned_hlb');
  } else if (boundaryStatus === 'OUTSIDE') {
    boundaryColor = '#EF4444';
    boundaryIcon = '⚠';
    boundaryText = t('outside_assigned_hlb');
  } else if (boundaryStatus === 'BOUNDARY_UNCERTAIN') {
    boundaryColor = '#F59E0B';
    boundaryIcon = '⚡';
    boundaryText = t('boundary_uncertain');
  } else {
    boundaryColor = '#64748B';
    boundaryIcon = '?';
    boundaryText = t('location_unavailable');
  }

  return (
    <View
      style={[
        styles.cardContainer,
        isDarkMode ? styles.darkCard : styles.lightCard,
        boundaryStatus === 'OUTSIDE' && styles.outsideCardBorder,
        style,
      ]}
      testID={testID}
    >
      {/* Outside Warning Banner (Informational & Non-Blocking) */}
      {boundaryStatus === 'OUTSIDE' && (
        <View
          style={[styles.outsideWarningBanner, isDarkMode ? styles.outsideDarkBanner : styles.outsideLightBanner]}
          testID="outside-hlb-warning-banner"
        >
          <Text style={styles.outsideWarningIcon}>⚠</Text>
          <Text style={styles.outsideWarningText} testID="outside-hlb-warning-text">
            {t('outside_assigned_hlb')}
          </Text>
        </View>
      )}

      {/* Main Grid: GPS Status + Boundary Status */}
      <View style={styles.statusGridRow}>
        {/* GPS Box */}
        <View style={styles.statusColumn} testID="gps-status-section">
          <Text style={[styles.columnLabel, isDarkMode ? styles.darkLabel : styles.lightLabel]}>
            {t('gps')}
          </Text>

          <View style={styles.indicatorRow}>
            <View style={[styles.statusDot, { backgroundColor: gpsBadgeColor }]} />
            <Text
              style={[styles.indicatorText, { color: gpsBadgeColor }]}
              testID="gps-accuracy-tier-text"
            >
              {gpsStatusText}
            </Text>
          </View>

          <Text
            style={[styles.subValueText, isDarkMode ? styles.darkSubtext : styles.lightSubtext]}
            testID="gps-accuracy-meters-text"
          >
            {accuracyMeters !== null && accuracyMeters !== undefined
              ? t('accuracy_meters_fmt').replace('{meters}', Math.round(accuracyMeters).toString())
              : '±— m'}
          </Text>
        </View>

        <View style={[styles.verticalDivider, isDarkMode ? styles.darkDivider : styles.lightDivider]} />

        {/* Boundary Box */}
        <View style={styles.statusColumn} testID="boundary-status-section">
          <Text style={[styles.columnLabel, isDarkMode ? styles.darkLabel : styles.lightLabel]}>
            {t('boundary_status_label')}
          </Text>

          <View style={styles.indicatorRow}>
            <Text style={[styles.boundaryIconText, { color: boundaryColor }]}>
              {boundaryIcon}
            </Text>
            <Text
              style={[styles.indicatorText, { color: boundaryColor }]}
              testID="boundary-status-text"
              numberOfLines={1}
            >
              {boundaryText}
            </Text>
          </View>

          <Text
            style={[styles.subValueText, isDarkMode ? styles.darkSubtext : styles.lightSubtext]}
            testID="boundary-distance-text"
          >
            {boundaryDistanceMeters !== null && boundaryDistanceMeters !== undefined
              ? `${boundaryDistanceMeters}m from edge`
              : ' '}
          </Text>
        </View>

        {/* Action Button: Refresh GPS */}
        {onRefreshGps && (
          <TouchableOpacity
            style={[styles.refreshButton, isDarkMode ? styles.darkRefreshBtn : styles.lightRefreshBtn]}
            onPress={onRefreshGps}
            disabled={gpsStatus === 'REFRESHING'}
            testID="btn-refresh-gps"
            accessibilityLabel={t('refresh_gps')}
          >
            {gpsStatus === 'REFRESHING' ? (
              <ActivityIndicator size="small" color="#0284C7" />
            ) : (
              <Text style={styles.refreshIconText}>🔄</Text>
            )}
          </TouchableOpacity>
        )}
      </View>

      {/* Fieldwork Coverage Row (Building Status Progress) */}
      {coverage && (
        <View
          style={[styles.coverageContainer, isDarkMode ? styles.darkCoverageBox : styles.lightCoverageBox]}
          testID="coverage-indicator-section"
        >
          <View style={styles.coverageHeaderRow}>
            <Text style={[styles.coverageTitleText, isDarkMode ? styles.darkLabel : styles.lightLabel]}>
              {t('coverage')}
            </Text>
            <Text style={styles.coveragePercentText} testID="coverage-percentage-text">
              {coverage.coveragePercentage}%
            </Text>
          </View>

          {/* Progress Bar */}
          <View style={[styles.progressBarTrack, isDarkMode ? styles.darkTrack : styles.lightTrack]}>
            <View
              style={[
                styles.progressBarFill,
                { width: `${Math.min(100, Math.max(0, coverage.coveragePercentage))}%` },
              ]}
              testID="coverage-progress-bar"
            />
          </View>

          {/* Counts: 42 of 100 buildings completed */}
          <View style={styles.coverageCountsRow}>
            <Text
              style={[styles.coverageCountsText, isDarkMode ? styles.darkSubtext : styles.lightSubtext]}
              testID="coverage-buildings-completed-text"
            >
              {t('coverage_progress_fmt')
                .replace('{completed}', coverage.completedBuildings.toString())
                .replace('{total}', coverage.totalBuildings.toString())}
            </Text>
            <Text
              style={[styles.coverageRemainingText, isDarkMode ? styles.darkSubtext : styles.lightSubtext]}
              testID="coverage-buildings-remaining-text"
            >
              {coverage.remainingBuildings} {t('buildings_remaining').toLowerCase()}
            </Text>
          </View>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  cardContainer: {
    borderRadius: 12,
    borderWidth: 1,
    padding: 12,
    marginBottom: 12,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 3,
    elevation: 2,
  },
  lightCard: {
    backgroundColor: '#FFFFFF',
    borderColor: '#E2E8F0',
  },
  darkCard: {
    backgroundColor: '#1E293B',
    borderColor: '#334155',
  },
  outsideCardBorder: {
    borderColor: '#EF4444',
  },
  outsideWarningBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 6,
    marginBottom: 10,
  },
  outsideLightBanner: {
    backgroundColor: '#FEF2F2',
    borderWidth: 1,
    borderColor: '#FECACA',
  },
  outsideDarkBanner: {
    backgroundColor: '#450A0A',
    borderWidth: 1,
    borderColor: '#7F1D1D',
  },
  outsideWarningIcon: {
    fontSize: 14,
    marginRight: 6,
    color: '#EF4444',
  },
  outsideWarningText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#DC2626',
    flex: 1,
  },
  statusGridRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusColumn: {
    flex: 1,
  },
  verticalDivider: {
    width: 1,
    height: 38,
    marginHorizontal: 10,
  },
  lightDivider: {
    backgroundColor: '#E2E8F0',
  },
  darkDivider: {
    backgroundColor: '#334155',
  },
  columnLabel: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  lightLabel: {
    color: '#64748B',
  },
  darkLabel: {
    color: '#94A3B8',
  },
  indicatorRow: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginRight: 6,
  },
  boundaryIconText: {
    fontSize: 12,
    fontWeight: '800',
    marginRight: 4,
  },
  indicatorText: {
    fontSize: 13,
    fontWeight: '700',
    flexShrink: 1,
  },
  subValueText: {
    fontSize: 11,
    marginTop: 2,
  },
  lightSubtext: {
    color: '#64748B',
  },
  darkSubtext: {
    color: '#94A3B8',
  },
  refreshButton: {
    padding: 8,
    borderRadius: 8,
    marginLeft: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  lightRefreshBtn: {
    backgroundColor: '#F1F5F9',
  },
  darkRefreshBtn: {
    backgroundColor: '#334155',
  },
  refreshIconText: {
    fontSize: 16,
  },
  coverageContainer: {
    marginTop: 10,
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(148, 163, 184, 0.2)',
  },
  lightCoverageBox: {},
  darkCoverageBox: {},
  coverageHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  coverageTitleText: {
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  coveragePercentText: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0284C7',
  },
  progressBarTrack: {
    height: 6,
    borderRadius: 3,
    overflow: 'hidden',
    marginBottom: 4,
  },
  lightTrack: {
    backgroundColor: '#E2E8F0',
  },
  darkTrack: {
    backgroundColor: '#334155',
  },
  progressBarFill: {
    height: '100%',
    backgroundColor: '#0284C7',
    borderRadius: 3,
  },
  coverageCountsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  coverageCountsText: {
    fontSize: 11,
  },
  coverageRemainingText: {
    fontSize: 11,
  },
});
