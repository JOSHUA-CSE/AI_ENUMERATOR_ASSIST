import React from 'react';
import {
  Modal,
  StyleSheet,
  Text,
  View,
  TouchableOpacity,
  ScrollView,
  useColorScheme,
} from 'react-native';
import { Card, StatusBadge, PrimaryButton } from '../../components';
import { useTranslation } from '../../core/localization';
import type { SupervisorHlbProgress } from '../../core/supervisorService';

export interface SupervisorHlbDetailModalProps {
  visible: boolean;
  hlb: SupervisorHlbProgress | null;
  onClose: () => void;
}

export function SupervisorHlbDetailModal({
  visible,
  hlb,
  onClose,
}: SupervisorHlbDetailModalProps): React.JSX.Element | null {
  const isDarkMode = useColorScheme() === 'dark';
  const { t } = useTranslation();

  if (!visible || !hlb) return null;

  const progressPercent = Math.min(100, Math.max(0, hlb.progress_percentage || 0));
  const hasAlerts = (hlb.boundary_alert_count || 0) > 0 || (hlb.boundary_alerts && hlb.boundary_alerts.length > 0);
  const alerts = hlb.boundary_alerts || [];

  const themeStyles = {
    overlay: { backgroundColor: 'rgba(0, 0, 0, 0.6)' },
    container: { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' },
    card: { backgroundColor: isDarkMode ? '#1E293B' : '#F8FAFC' },
    text: { color: isDarkMode ? '#F1F5F9' : '#0F172A' },
    subtext: { color: isDarkMode ? '#94A3B8' : '#64748B' },
    divider: { borderBottomColor: isDarkMode ? '#334155' : '#E2E8F0' },
    statBox: {
      backgroundColor: isDarkMode ? '#0F172A' : '#EDF2F7',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
    alertCard: {
      backgroundColor: isDarkMode ? '#2D1F1A' : '#FFF7ED',
      borderColor: isDarkMode ? '#9A3412' : '#FDBA74',
    },
    alertText: { color: isDarkMode ? '#FDBA74' : '#C2410C' },
    noAlertsBox: {
      backgroundColor: isDarkMode ? '#14291F' : '#F0FDF4',
      borderColor: isDarkMode ? '#166534' : '#86EFAC',
    },
    progressBarTrack: { backgroundColor: isDarkMode ? '#334155' : '#E2E8F0' },
  };

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
      testID="supervisor-hlb-detail-modal"
    >
      <View style={[styles.modalOverlay, themeStyles.overlay]}>
        <View style={[styles.modalContainer, themeStyles.container]}>
          {/* Header */}
          <View style={[styles.headerRow, themeStyles.divider]}>
            <View style={{ flex: 1 }}>
              <Text style={[styles.blockCodeTitle, themeStyles.text]}>
                {hlb.block_code}
              </Text>
              <Text style={[styles.hlbNameSubtitle, themeStyles.subtext]}>
                {hlb.name || t('hlb_details_title')}
              </Text>
            </View>
            <TouchableOpacity
              onPress={onClose}
              style={styles.closeIconBtn}
              testID="close-hlb-detail-modal-btn"
            >
              <Text style={styles.closeIconText}>✕</Text>
            </TouchableOpacity>
          </View>

          <ScrollView style={styles.scrollContent} showsVerticalScrollIndicator={false}>
            {/* 1. Progress Bar & Core Percent */}
            <View style={[styles.sectionCard, themeStyles.card]}>
              <View style={styles.progressHeaderRow}>
                <Text style={[styles.sectionTitle, themeStyles.text]}>
                  {t('progress')}
                </Text>
                <Text style={[styles.progressPercentText, { color: progressPercent >= 100 ? '#16A34A' : '#0284C7' }]}>
                  {progressPercent.toFixed(1)}%
                </Text>
              </View>

              <View style={[styles.progressBarTrack, themeStyles.progressBarTrack]}>
                <View
                  style={[
                    styles.progressBarFill,
                    {
                      width: `${progressPercent}%`,
                      backgroundColor: progressPercent >= 100 ? '#16A34A' : '#0284C7',
                    },
                  ]}
                />
              </View>

              {/* Progress Count Grid */}
              <View style={styles.statsGrid}>
                <View style={[styles.statBox, themeStyles.statBox]}>
                  <Text style={[styles.statVal, { color: '#0284C7' }]}>{hlb.total_houses}</Text>
                  <Text style={[styles.statLbl, themeStyles.subtext]}>{t('total_houses')}</Text>
                </View>
                <View style={[styles.statBox, themeStyles.statBox]}>
                  <Text style={[styles.statVal, { color: '#16A34A' }]}>{hlb.completed_houses}</Text>
                  <Text style={[styles.statLbl, themeStyles.subtext]}>{t('completed')}</Text>
                </View>
                <View style={[styles.statBox, themeStyles.statBox]}>
                  <Text style={[styles.statVal, { color: '#EA580C' }]}>{hlb.remaining_houses}</Text>
                  <Text style={[styles.statLbl, themeStyles.subtext]}>{t('remaining')}</Text>
                </View>
                <View style={[styles.statBox, themeStyles.statBox]}>
                  <Text style={[styles.statVal, { color: '#DC2626' }]}>{hlb.locked_houses}</Text>
                  <Text style={[styles.statLbl, themeStyles.subtext]}>{t('locked')}</Text>
                </View>
              </View>

              {/* Revisits */}
              <View style={[styles.metaRow, { marginTop: 10 }]}>
                <Text style={[styles.metaLabel, themeStyles.subtext]}>{t('revisit_count')}:</Text>
                <Text style={[styles.metaValue, themeStyles.text]}>{hlb.revisit_count}</Text>
              </View>

              {/* GPS Coverage */}
              <View style={styles.metaRow}>
                <Text style={[styles.metaLabel, themeStyles.subtext]}>{t('gps_coverage')}:</Text>
                <Text style={[styles.metaValue, { color: '#0284C7', fontWeight: 'bold' }]}>
                  {hlb.gps_coverage != null ? `${hlb.gps_coverage.toFixed(1)}%` : '0.0%'}
                </Text>
              </View>

              {/* Last Sync */}
              <View style={styles.metaRow}>
                <Text style={[styles.metaLabel, themeStyles.subtext]}>{t('last_sync')}:</Text>
                <Text style={[styles.metaValue, themeStyles.text]}>
                  {hlb.last_sync ? new Date(hlb.last_sync).toLocaleString() : t('never_synced')}
                </Text>
              </View>
            </View>

            {/* 2. Assigned Enumerator Details */}
            <View style={[styles.sectionCard, themeStyles.card]}>
              <Text style={[styles.sectionTitle, themeStyles.text]}>
                {t('assigned_enumerator')}
              </Text>
              {hlb.enumerator ? (
                <View style={styles.enumeratorBox}>
                  <Text style={[styles.enumName, themeStyles.text]}>
                    {hlb.enumerator.name}
                  </Text>
                  {hlb.enumerator.username && (
                    <Text style={[styles.enumSub, themeStyles.subtext]}>
                      @{hlb.enumerator.username}
                    </Text>
                  )}
                  {hlb.enumerator.phone && (
                    <Text style={[styles.enumSub, themeStyles.subtext]}>
                      📞 {hlb.enumerator.phone}
                    </Text>
                  )}
                </View>
              ) : (
                <Text style={[styles.enumUnassigned, { color: '#EA580C' }]}>
                  {t('no_enumerator_assigned')}
                </Text>
              )}
            </View>

            {/* 3. Boundary Alerts Section */}
            <View style={[styles.sectionCard, themeStyles.card]}>
              <View style={styles.progressHeaderRow}>
                <Text style={[styles.sectionTitle, themeStyles.text]}>
                  {t('boundary_alerts')}
                </Text>
                <StatusBadge
                  type={hasAlerts ? 'WARNING' : 'ACTIVE'}
                  label={
                    hasAlerts
                      ? `⚠ ${hlb.boundary_alert_count || alerts.length} ${t('boundary_alerts_count')}`
                      : `✓ ${t('no_boundary_alerts')}`
                  }
                />
              </View>

              {!hasAlerts ? (
                <View style={[styles.noAlertsBox, themeStyles.noAlertsBox]}>
                  <Text style={[styles.noAlertsText, { color: '#16A34A' }]}>
                    ✓ {t('no_boundary_alerts')}
                  </Text>
                </View>
              ) : (
                <View style={styles.alertsList}>
                  {alerts.map((alert, idx) => (
                    <View
                      key={alert.track_id || `alert-${idx}`}
                      style={[styles.alertItem, themeStyles.alertCard]}
                      testID={`boundary-alert-item-${idx}`}
                    >
                      <View style={styles.alertHeaderRow}>
                        <Text style={[styles.alertTitle, themeStyles.alertText]}>
                          ⚠ {t('alert_outside_boundary')}
                        </Text>
                        <Text style={[styles.alertTime, themeStyles.subtext]}>
                          {alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : ''}
                        </Text>
                      </View>
                      <Text style={[styles.alertCoord, themeStyles.subtext]}>
                        Lat: {alert.latitude.toFixed(6)}, Lon: {alert.longitude.toFixed(6)}
                      </Text>
                      {alert.distance_meters != null && (
                        <Text style={[styles.alertDistance, themeStyles.alertText]}>
                          {alert.distance_meters.toFixed(1)}m from boundary
                        </Text>
                      )}
                      {alert.message && (
                        <Text style={[styles.alertMsg, themeStyles.subtext]}>
                          {alert.message}
                        </Text>
                      )}
                    </View>
                  ))}
                </View>
              )}
            </View>
          </ScrollView>

          {/* Footer Close Button */}
          <View style={styles.footerRow}>
            <PrimaryButton
              title={t('close')}
              onPress={onClose}
              style={styles.closeBtn}
              testID="modal-close-btn"
            />
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  modalOverlay: {
    flex: 1,
    justifyContent: 'center',
    padding: 16,
  },
  modalContainer: {
    borderRadius: 16,
    maxHeight: '85%',
    padding: 18,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.25,
    shadowRadius: 8,
    elevation: 6,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingBottom: 12,
    borderBottomWidth: 1,
  },
  blockCodeTitle: {
    fontSize: 20,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  hlbNameSubtitle: {
    fontSize: 13,
    marginTop: 2,
  },
  closeIconBtn: {
    padding: 6,
  },
  closeIconText: {
    fontSize: 18,
    fontWeight: '700',
    color: '#94A3B8',
  },
  scrollContent: {
    marginTop: 12,
  },
  sectionCard: {
    borderRadius: 12,
    padding: 14,
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 15,
    fontWeight: '700',
    marginBottom: 8,
  },
  progressHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 8,
  },
  progressPercentText: {
    fontSize: 18,
    fontWeight: '800',
  },
  progressBarTrack: {
    height: 8,
    borderRadius: 4,
    overflow: 'hidden',
    marginBottom: 12,
  },
  progressBarFill: {
    height: '100%',
    borderRadius: 4,
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 6,
    marginTop: 4,
  },
  statBox: {
    flex: 1,
    padding: 8,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  statVal: {
    fontSize: 16,
    fontWeight: '800',
  },
  statLbl: {
    fontSize: 10,
    fontWeight: '600',
    marginTop: 2,
    textAlign: 'center',
  },
  metaRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 4,
  },
  metaLabel: {
    fontSize: 13,
  },
  metaValue: {
    fontSize: 13,
    fontWeight: '600',
  },
  enumeratorBox: {
    marginTop: 4,
  },
  enumName: {
    fontSize: 15,
    fontWeight: '700',
  },
  enumSub: {
    fontSize: 12,
    marginTop: 2,
  },
  enumUnassigned: {
    fontSize: 13,
    fontWeight: '600',
    marginTop: 4,
  },
  noAlertsBox: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 4,
  },
  noAlertsText: {
    fontSize: 13,
    fontWeight: '600',
    textAlign: 'center',
  },
  alertsList: {
    marginTop: 6,
  },
  alertItem: {
    padding: 10,
    borderRadius: 8,
    borderWidth: 1,
    marginBottom: 8,
  },
  alertHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  alertTitle: {
    fontSize: 13,
    fontWeight: '700',
  },
  alertTime: {
    fontSize: 11,
  },
  alertCoord: {
    fontSize: 11,
    marginTop: 3,
    fontFamily: 'monospace',
  },
  alertDistance: {
    fontSize: 12,
    fontWeight: '600',
    marginTop: 2,
  },
  alertMsg: {
    fontSize: 11,
    marginTop: 2,
  },
  footerRow: {
    paddingTop: 10,
  },
  closeBtn: {
    width: '100%',
  },
});
