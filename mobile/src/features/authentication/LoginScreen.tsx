import React, { useState, useEffect, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  ActivityIndicator,
  useColorScheme,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  Modal,
} from 'react-native';
import { sessionService } from '../../core/sessionService';
import { healthService } from '../../core/healthService';
import { useTranslation } from '../../core/localization';
import { getApiBaseUrl, setBaseUrl, resolveApiBaseUrl } from '../../core/networkConfig';

interface LoginScreenProps {
  onLoginSuccess?: () => void;
}

export default function LoginScreen({ onLoginSuccess }: LoginScreenProps): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const { t, language, toggleLanguage } = useTranslation();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(true);

  // Server settings modal state
  const [showServerModal, setShowServerModal] = useState(false);
  const [serverUrlInput, setServerUrlInput] = useState(getApiBaseUrl());
  const [testStatus, setTestStatus] = useState<'idle' | 'testing' | 'success' | 'failed'>('idle');
  const [testMessage, setTestMessage] = useState<string | null>(null);

  const checkNetwork = useCallback(async () => {
    try {
      await healthService.getHealth();
      setIsOnline(true);
      return true;
    } catch {
      setIsOnline(false);
      return false;
    }
  }, []);

  // Poll backend health to determine online/offline status
  useEffect(() => {
    let isMounted = true;
    const runCheck = async () => {
      const ok = await checkNetwork();
      if (isMounted) {
        setIsOnline(ok);
      }
    };
    runCheck();
    const interval = setInterval(runCheck, 10000);
    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [checkNetwork]);

  const handleLogin = async () => {
    if (!username.trim() || !password.trim()) {
      setError(t('login_required_fields'));
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await sessionService.login(username.trim(), password);
      if (onLoginSuccess) {
        onLoginSuccess();
      }
    } catch (err: any) {
      if (err.status === 401 || err.status === 400) {
        setError(t('invalid_credentials'));
      } else if (err.message && err.message.includes('Network')) {
        setError(t('network_error'));
      } else {
        setError(err.message || t('unexpected_error'));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleOpenServerModal = () => {
    setServerUrlInput(getApiBaseUrl());
    setTestStatus('idle');
    setTestMessage(null);
    setShowServerModal(true);
  };

  const handleTestConnection = async () => {
    const trimmed = serverUrlInput.trim().replace(/\/+$/, '');
    if (!trimmed) return;
    setTestStatus('testing');
    setTestMessage(null);
    try {
      const res = await fetch(`${trimmed}/health`, { method: 'GET' });
      if (res.ok) {
        setTestStatus('success');
        setTestMessage('Successfully connected to backend API!');
      } else {
        setTestStatus('failed');
        setTestMessage(`Server returned HTTP ${res.status}: ${res.statusText}`);
      }
    } catch (err: any) {
      setTestStatus('failed');
      setTestMessage(err.message || 'Unable to connect to server.');
    }
  };

  const handleSaveServerUrl = async () => {
    const trimmed = serverUrlInput.trim().replace(/\/+$/, '');
    if (trimmed) {
      setBaseUrl(trimmed);
      setShowServerModal(false);
      await checkNetwork();
    }
  };

  const handleAutoDetectHost = () => {
    const detected = resolveApiBaseUrl({ envUrl: undefined });
    setServerUrlInput(detected);
    setTestStatus('idle');
    setTestMessage('Detected development host.');
  };

  const themeStyles = {
    container: { backgroundColor: isDarkMode ? '#121212' : '#F5F5F7' },
    title: { color: isDarkMode ? '#FFFFFF' : '#1A1A1A' },
    label: { color: isDarkMode ? '#E0E0E0' : '#444444' },
    input: {
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
      color: isDarkMode ? '#FFFFFF' : '#000000',
      borderColor: isDarkMode ? '#444444' : '#CCCCCC',
    },
    statusBar: {
      backgroundColor: isDarkMode ? '#1E1E1E' : '#EFEFEF',
      borderTopColor: isDarkMode ? '#333333' : '#DDDDDD',
    },
    statusText: { color: isDarkMode ? '#CCCCCC' : '#555555' },
    modalContent: {
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
    },
    modalTitle: {
      color: isDarkMode ? '#FFFFFF' : '#1A1A1A',
    },
    modalSub: {
      color: isDarkMode ? '#AAAAAA' : '#666666',
    },
    langBtn: {
      borderColor: isDarkMode ? '#555555' : '#CCCCCC',
    },
    langBtnText: {
      color: isDarkMode ? '#90CAF9' : '#0066CC',
    },
  };

  return (
    <KeyboardAvoidingView
      style={[styles.container, themeStyles.container]}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      testID="login-screen"
    >
      <ScrollView contentContainerStyle={styles.scrollContainer} keyboardShouldPersistTaps="handled">
        {/* Language Switcher Button */}
        <View style={styles.topBar}>
          <TouchableOpacity
            style={[styles.langToggle, themeStyles.langBtn]}
            onPress={toggleLanguage}
            activeOpacity={0.7}
            testID="language-toggle-button"
          >
            <Text style={[styles.langToggleText, themeStyles.langBtnText]}>
              {language === 'en' ? 'தமிழ்' : 'English'}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.header}>
          <Text style={[styles.title, themeStyles.title]}>
            {t('app_title')}
          </Text>
          <Text style={styles.subtitle}>{t('gov_subtitle')}</Text>
        </View>

        <View style={styles.form}>
          <Text style={[styles.label, themeStyles.label]}>{t('user_id')}</Text>
          <TextInput
            testID="username-input"
            style={[styles.input, themeStyles.input]}
            placeholder={t('user_id_placeholder')}
            placeholderTextColor={isDarkMode ? '#666666' : '#999999'}
            value={username}
            onChangeText={setUsername}
            autoCapitalize="none"
            autoCorrect={false}
            editable={!loading}
          />

          <Text style={[styles.label, themeStyles.label]}>{t('password')}</Text>
          <TextInput
            testID="password-input"
            style={[styles.input, themeStyles.input]}
            placeholder={t('password_placeholder')}
            placeholderTextColor={isDarkMode ? '#666666' : '#999999'}
            secureTextEntry
            value={password}
            onChangeText={setPassword}
            autoCapitalize="none"
            autoCorrect={false}
            editable={!loading}
          />

          {error && <Text style={styles.errorText} testID="error-message">{error}</Text>}

          <TouchableOpacity
            testID="login-button"
            style={[styles.button, loading && styles.buttonDisabled]}
            onPress={handleLogin}
            disabled={loading}
          >
            {loading ? (
              <ActivityIndicator color="#FFFFFF" size="small" />
            ) : (
              <Text style={styles.buttonText}>{t('login')}</Text>
            )}
          </TouchableOpacity>
        </View>
      </ScrollView>

      {/* Network Status Footer */}
      <TouchableOpacity
        style={[styles.statusBar, themeStyles.statusBar]}
        onPress={handleOpenServerModal}
        activeOpacity={0.8}
        testID="network-status-bar"
      >
        <Text style={[styles.statusText, themeStyles.statusText]}>
          {t('network')}:{' '}
          <Text style={isOnline ? styles.onlineIndicator : styles.offlineIndicator}>
            ● {isOnline ? t('online') : t('offline')}
          </Text>
          <Text style={styles.serverInfoText}> • ⚙ Server Settings</Text>
        </Text>
      </TouchableOpacity>

      {/* Server Configuration Modal */}
      <Modal
        visible={showServerModal}
        transparent
        animationType="fade"
        onRequestClose={() => setShowServerModal(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalCard, themeStyles.modalContent]}>
            <Text style={[styles.modalHeading, themeStyles.modalTitle]}>
              ⚙ Backend Server Configuration
            </Text>
            <Text style={[styles.modalHint, themeStyles.modalSub]}>
              Set the FastAPI backend API URL. Make sure your device is on the same Wi-Fi as your laptop.
            </Text>

            <Text style={[styles.modalInputLabel, themeStyles.label]}>API Base URL</Text>
            <TextInput
              style={[styles.modalInput, themeStyles.input]}
              value={serverUrlInput}
              onChangeText={setServerUrlInput}
              placeholder="http://192.168.1.100:8000/api/v1"
              placeholderTextColor={isDarkMode ? '#666666' : '#999999'}
              autoCapitalize="none"
              autoCorrect={false}
            />

            {testMessage && (
              <View
                style={[
                  styles.testStatusBox,
                  testStatus === 'success'
                    ? styles.testStatusSuccess
                    : styles.testStatusError,
                ]}
              >
                <Text
                  style={[
                    styles.testStatusText,
                    testStatus === 'success'
                      ? styles.testStatusSuccessText
                      : styles.testStatusErrorText,
                  ]}
                >
                  {testMessage}
                </Text>
              </View>
            )}

            <View style={styles.modalActionsRow}>
              <TouchableOpacity
                style={styles.modalSecBtn}
                onPress={handleAutoDetectHost}
              >
                <Text style={styles.modalSecBtnText}>Auto-Detect</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.modalSecBtn, testStatus === 'testing' && styles.buttonDisabled]}
                onPress={handleTestConnection}
                disabled={testStatus === 'testing'}
              >
                {testStatus === 'testing' ? (
                  <ActivityIndicator size="small" color="#0066CC" />
                ) : (
                  <Text style={styles.modalSecBtnText}>Test Ping</Text>
                )}
              </TouchableOpacity>
            </View>

            <View style={styles.modalFooterRow}>
              <TouchableOpacity
                style={styles.modalCancelBtn}
                onPress={() => setShowServerModal(false)}
              >
                <Text style={styles.modalCancelBtnText}>{t('cancel')}</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.modalSaveBtn}
                onPress={handleSaveServerUrl}
              >
                <Text style={styles.modalSaveBtnText}>{t('save')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  scrollContainer: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
  },
  topBar: {
    alignItems: 'flex-end',
    marginBottom: 16,
  },
  langToggle: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 14,
    borderWidth: 1,
  },
  langToggleText: {
    fontSize: 13,
    fontWeight: '700',
  },
  header: {
    alignItems: 'center',
    marginBottom: 40,
  },
  title: {
    fontSize: 26,
    fontWeight: 'bold',
    textAlign: 'center',
    letterSpacing: 0.5,
  },
  subtitle: {
    fontSize: 11,
    color: '#0066CC',
    fontWeight: '700',
    marginTop: 8,
    letterSpacing: 1.5,
    textAlign: 'center',
  },
  form: {
    width: '100%',
  },
  label: {
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 8,
  },
  input: {
    height: 54,
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 16,
    fontSize: 16,
    marginBottom: 20,
  },
  button: {
    backgroundColor: '#0066CC',
    height: 54,
    borderRadius: 6,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 10,
    ...Platform.select({
      web: {
        boxShadow: '0px 2px 4px rgba(0, 0, 0, 0.2)',
      },
      default: {
        elevation: 2,
        shadowColor: '#000000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.2,
        shadowRadius: 2,
      },
    }),
  },
  buttonDisabled: {
    backgroundColor: '#80B3E6',
  },
  buttonText: {
    color: '#FFFFFF',
    fontSize: 16,
    fontWeight: 'bold',
    letterSpacing: 1,
  },
  errorText: {
    color: '#D32F2F',
    fontSize: 14,
    fontWeight: '500',
    marginBottom: 16,
  },
  statusBar: {
    height: 48,
    borderTopWidth: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 20,
  },
  statusText: {
    fontSize: 13,
    fontWeight: '500',
  },
  serverInfoText: {
    fontSize: 12,
    color: '#0066CC',
    fontWeight: '600',
  },
  onlineIndicator: {
    color: '#2E7D32',
    fontWeight: 'bold',
  },
  offlineIndicator: {
    color: '#C62828',
    fontWeight: 'bold',
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalCard: {
    width: '100%',
    maxWidth: 420,
    borderRadius: 12,
    padding: 20,
    ...Platform.select({
      web: {
        boxShadow: '0px 4px 12px rgba(0, 0, 0, 0.3)',
      },
      default: {
        elevation: 6,
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.3,
        shadowRadius: 6,
      },
    }),
  },
  modalHeading: {
    fontSize: 18,
    fontWeight: '700',
    marginBottom: 8,
  },
  modalHint: {
    fontSize: 13,
    lineHeight: 18,
    marginBottom: 16,
  },
  modalInputLabel: {
    fontSize: 13,
    fontWeight: '600',
    marginBottom: 6,
  },
  modalInput: {
    height: 46,
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 12,
    fontSize: 14,
    marginBottom: 12,
  },
  testStatusBox: {
    padding: 10,
    borderRadius: 6,
    marginBottom: 12,
  },
  testStatusSuccess: {
    backgroundColor: '#E8F5E9',
    borderColor: '#A5D6A7',
    borderWidth: 1,
  },
  testStatusError: {
    backgroundColor: '#FFEBEE',
    borderColor: '#FFCDD2',
    borderWidth: 1,
  },
  testStatusText: {
    fontSize: 12,
    fontWeight: '500',
  },
  testStatusSuccessText: {
    color: '#2E7D32',
  },
  testStatusErrorText: {
    color: '#C62828',
  },
  modalActionsRow: {
    flexDirection: 'row',
    gap: 10,
    marginBottom: 16,
  },
  modalSecBtn: {
    flex: 1,
    height: 40,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: '#0066CC',
    alignItems: 'center',
    justifyContent: 'center',
  },
  modalSecBtnText: {
    color: '#0066CC',
    fontWeight: '600',
    fontSize: 13,
  },
  modalFooterRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
  },
  modalCancelBtn: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 6,
  },
  modalCancelBtnText: {
    color: '#666666',
    fontWeight: '600',
  },
  modalSaveBtn: {
    backgroundColor: '#0066CC',
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 6,
  },
  modalSaveBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
});
