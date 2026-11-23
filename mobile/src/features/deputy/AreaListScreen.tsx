import React, { useEffect, useState, useCallback } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  useColorScheme,
  BackHandler,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import {
  AppHeader,
  Card,
  EmptyState,
  ErrorMessage,
  LoadingIndicator,
  PrimaryButton,
  SecondaryButton,
  ScreenContainer,
  StatusBadge,
} from '../../components';
import { AdministrativeArea, areaService } from '../../core/areaService';
import { useTranslation } from '../../core/localization';
import type { DeputyNavigationProp } from '../../navigation/navigationTypes';

export function AreaListScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const { t } = useTranslation();

  const [areas, setAreas] = useState<AdministrativeArea[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAreas = useCallback(async (isRefresh = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const response = await areaService.getAreas();
      setAreas(response.items || []);
    } catch (err: any) {
      setError(err.message || t('unexpected_error'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadAreas();
  }, [loadAreas]);

  useEffect(() => {
    const backAction = () => {
      navigation.goBack();
      return true;
    };
    const backHandler = BackHandler.addEventListener('hardwareBackPress', backAction);
    return () => backHandler.remove();
  }, [navigation]);

  const filteredAreas = areas.filter(
    (a) =>
      a.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      a.code.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const themeStyles = {
    searchContainer: {
      backgroundColor: isDarkMode ? '#1E1E1E' : '#FFFFFF',
      borderColor: isDarkMode ? '#333333' : '#D0DBE5',
    },
    searchInput: {
      color: isDarkMode ? '#FFFFFF' : '#1A202C',
    },
    text: { color: isDarkMode ? '#FFFFFF' : '#1A202C' },
    subtext: { color: isDarkMode ? '#A0AEC0' : '#718096' },
    badgeContainer: {
      backgroundColor: isDarkMode ? '#2D3748' : '#EDF2F7',
    },
  };

  const renderAreaItem = ({ item }: { item: AdministrativeArea }) => (
    <Card style={styles.areaCard} testID={`area-card-${item.code}`}>
      <View style={styles.cardHeader}>
        <View style={styles.titleContainer}>
          <Text style={[styles.areaName, themeStyles.text]}>{item.name}</Text>
          <Text style={[styles.areaCode, themeStyles.subtext]}>
            {t('area_code_label')}: {item.code}
          </Text>
        </View>
        <StatusBadge
          type={item.type as any}
          label={item.type}
        />
      </View>

      <View style={styles.detailsRow}>
        <View style={[styles.statBadge, themeStyles.badgeContainer]}>
          <Text style={[styles.statValue, themeStyles.text]}>
            🏠 {item.house_count} {t('house_count')}
          </Text>
        </View>
      </View>

      <View style={styles.cardBtnRow}>
        <PrimaryButton
          title={`🗺 ${t('view_map')}`}
          onPress={() =>
            navigation.navigate('AreaMap', {
              areaId: item.id,
              areaName: item.name,
              areaCode: item.code,
            })
          }
          style={{ flex: 1, marginRight: 6 }}
          testID={`view-map-button-${item.code}`}
        />
        <SecondaryButton
          title="📑 Layouts / HLBs"
          onPress={() =>
            navigation.navigate('LayoutList', {
              areaId: item.id,
              areaName: item.name,
            })
          }
          style={{ flex: 1, marginLeft: 6 }}
          testID={`view-layouts-button-${item.code}`}
        />
      </View>
    </Card>
  );

  return (
    <ScreenContainer testID="area-list-screen">
      <AppHeader
        roleType="DEPUTY_TAHSILDAR"
        roleLabel={t('role_deputy')}
        title={t('administrative_areas')}
        showBack
        onBack={() => navigation.goBack()}
      />

      <View style={styles.container}>
        {/* Search Bar */}
        <View style={[styles.searchBox, themeStyles.searchContainer]}>
          <Text style={styles.searchIcon}>🔍</Text>
          <TextInput
            style={[styles.searchInput, themeStyles.searchInput]}
            placeholder={t('search_areas')}
            placeholderTextColor={isDarkMode ? '#718096' : '#A0AEC0'}
            value={searchQuery}
            onChangeText={setSearchQuery}
            autoCapitalize="none"
            testID="area-search-input"
          />
          {searchQuery.length > 0 && (
            <TouchableOpacity onPress={() => setSearchQuery('')} testID="clear-search-button">
              <Text style={styles.clearIcon}>✕</Text>
            </TouchableOpacity>
          )}
        </View>

        {/* Content States */}
        {loading && !refreshing ? (
          <LoadingIndicator message={t('loading_area_data')} />
        ) : error ? (
          <ErrorMessage
            message={error}
            onRetry={() => loadAreas()}
            retryText={t('retry')}
          />
        ) : filteredAreas.length === 0 ? (
          <EmptyState
            title={t('no_areas_found')}
            description={searchQuery ? `No results for "${searchQuery}"` : t('placeholder_desc')}
            actionTitle={t('retry')}
            onAction={() => loadAreas(true)}
          />
        ) : (
          <FlatList
            data={filteredAreas}
            keyExtractor={(item) => item.id}
            renderItem={renderAreaItem}
            contentContainerStyle={styles.listContent}
            refreshControl={
              <RefreshControl
                refreshing={refreshing}
                onRefresh={() => loadAreas(true)}
                colors={['#0066CC']}
                tintColor="#0066CC"
              />
            }
            testID="area-flat-list"
          />
        )}
      </View>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    height: 48,
    marginBottom: 12,
  },
  searchIcon: {
    fontSize: 16,
    marginRight: 8,
  },
  searchInput: {
    flex: 1,
    fontSize: 15,
    paddingVertical: 0,
  },
  clearIcon: {
    fontSize: 16,
    color: '#718096',
    padding: 4,
  },
  listContent: {
    paddingBottom: 24,
  },
  areaCard: {
    marginBottom: 12,
  },
  cardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  titleContainer: {
    flex: 1,
    marginRight: 8,
  },
  areaName: {
    fontSize: 17,
    fontWeight: 'bold',
    marginBottom: 2,
  },
  areaCode: {
    fontSize: 13,
  },
  detailsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 12,
  },
  statBadge: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 6,
  },
  statValue: {
    fontSize: 13,
    fontWeight: '600',
  },
  viewMapButton: {
    marginTop: 4,
  },
  cardBtnRow: {
    flexDirection: 'row',
    marginTop: 8,
  },
});
