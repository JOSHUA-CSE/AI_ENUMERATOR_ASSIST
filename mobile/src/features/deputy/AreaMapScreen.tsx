import React, { useEffect, useState, useMemo, useRef, useCallback } from 'react';
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
  useColorScheme,
  Platform,
} from 'react-native';

import { useRoute, useNavigation } from '@react-navigation/native';
import {
  AppHeader,
  ErrorMessage,
  HlbSpatialMap,
  HlbSpatialMapRef,
  LoadingIndicator,
  PrimaryButton,
  ScreenContainer,
} from '../../components';
import {
  AreaBoundaryResponse,
  BuildingEstimationResponse,
  GeoJSONGeometry,
  House,
  areaService,
} from '../../core/areaService';
import { useTranslation } from '../../core/localization';
import { extractErrorMessage } from '../../core/apiClient';
import type { DeputyNavigationProp, DeputyScreenProps } from '../../navigation/navigationTypes';

interface LatLng {
  latitude: number;
  longitude: number;
}

/**
 * Convert GeoJSON Polygon or MultiPolygon coordinates into LatLng rings
 */
function parseGeoJSONToLatLngRings(geom: GeoJSONGeometry | null | undefined): LatLng[][] {
  if (!geom || !geom.coordinates) return [];
  const rings: LatLng[][] = [];

  if (geom.type === 'Polygon' && Array.isArray(geom.coordinates)) {
    for (const ring of geom.coordinates) {
      if (Array.isArray(ring)) {
        rings.push(
          ring.map((coord: [number, number]) => ({
            latitude: Number(coord[1]),
            longitude: Number(coord[0]),
          }))
        );
      }
    }
  } else if (geom.type === 'MultiPolygon' && Array.isArray(geom.coordinates)) {
    for (const poly of geom.coordinates) {
      if (Array.isArray(poly)) {
        for (const ring of poly) {
          if (Array.isArray(ring)) {
            rings.push(
              ring.map((coord: [number, number]) => ({
                latitude: Number(coord[1]),
                longitude: Number(coord[0]),
              }))
            );
          }
        }
      }
    }
  }
  return rings;
}

export function AreaMapScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<DeputyNavigationProp>();
  const route = useRoute<DeputyScreenProps<'AreaMap'>['route']>();
  const { areaId, areaName, areaCode } = route.params;
  const { t } = useTranslation();

  const mapRef = useRef<HlbSpatialMapRef>(null);

  const [boundary, setBoundary] = useState<AreaBoundaryResponse | null>(null);
  const [houses, setHouses] = useState<House[]>([]);
  const [estimation, setEstimation] = useState<BuildingEstimationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Top Controls State
  const [showBoundary, setShowBoundary] = useState(true);
  const [mapLayer, setMapLayer] = useState<'satellite' | 'standard'>('satellite');

  // Region Tracking
  const [region, setRegion] = useState({
    latitude: 11.082,
    longitude: 77.12,
    latitudeDelta: 0.04,
    longitudeDelta: 0.04,
  });

  const loadMapData = async () => {
    if (!areaId || areaId === 'undefined') {
      setError('Administrative area could not be identified. Please return and select the area again.');
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [boundaryRes, housesRes, estimationRes] = await Promise.all([
        areaService.getAreaBoundary(areaId),
        areaService.getAreaHouses(areaId, { limit: 1000 }),
        areaService.getBuildingEstimation(areaId).catch(() => null),
      ]);
      setBoundary(boundaryRes);
      setHouses(housesRes.items || []);
      setEstimation(estimationRes);
    } catch (err: any) {
      setError(extractErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMapData();
  }, [areaId]);

  // Convert boundary GeoJSON into coordinates
  const boundaryRings = useMemo(() => {
    return parseGeoJSONToLatLngRings(boundary?.boundary);
  }, [boundary]);

  // Flattened boundary points for fitToCoordinates
  const allBoundaryCoords = useMemo(() => {
    return boundaryRings.flat();
  }, [boundaryRings]);

  // Initial region calculation from boundary
  useEffect(() => {
    if (allBoundaryCoords.length > 0) {
      let minLat = 90;
      let maxLat = -90;
      let minLng = 180;
      let maxLng = -180;

      for (const pt of allBoundaryCoords) {
        minLat = Math.min(minLat, pt.latitude);
        maxLat = Math.max(maxLat, pt.latitude);
        minLng = Math.min(minLng, pt.longitude);
        maxLng = Math.max(maxLng, pt.longitude);
      }

      const centerLat = (minLat + maxLat) / 2;
      const centerLng = (minLng + maxLng) / 2;
      const latDelta = Math.max((maxLat - minLat) * 1.3, 0.03);
      const lngDelta = Math.max((maxLng - minLng) * 1.3, 0.03);

      const newRegion = {
        latitude: centerLat,
        longitude: centerLng,
        latitudeDelta: latDelta,
        longitudeDelta: lngDelta,
      };
      setRegion(newRegion);
      mapRef.current?.fitToCoordinates(allBoundaryCoords);
    }
  }, [allBoundaryCoords]);

  // Map Controls
  const handleZoomIn = useCallback(() => {
    mapRef.current?.zoomIn();
  }, []);

  const handleZoomOut = useCallback(() => {
    mapRef.current?.zoomOut();
  }, []);

  const handleFitBoundary = useCallback(() => {
    if (allBoundaryCoords.length > 0) {
      mapRef.current?.fitToCoordinates(allBoundaryCoords);
    }
  }, [allBoundaryCoords]);

  const handleToggleLayer = useCallback(() => {
    setMapLayer((prev) => (prev === 'satellite' ? 'standard' : 'satellite'));
  }, []);

  const handleToggleBoundary = useCallback(() => {
    setShowBoundary((prev) => !prev);
  }, []);

  const totalBuildings = estimation?.total_buildings ?? houses.length;
  const isSatelliteSource =
    estimation?.source_type === 'SATELLITE_DETECTED' ||
    houses.some((h) => h.source_type === 'SATELLITE_DETECTED');

  return (
    <ScreenContainer
      testID="area-map-screen"
      style={styles.container}
      contentContainerStyle={{ paddingHorizontal: 0, paddingVertical: 0 }}
    >
      <AppHeader
        title={areaName || t('administrative_areas')}
        subtitle={areaCode}
        showBack
        onBack={() => navigation.goBack()}
      />

      {loading ? (
        <LoadingIndicator message={t('loading_area_data')} />
      ) : error ? (
        <View style={styles.errorContainer}>
          <ErrorMessage message={error} />
          <TouchableOpacity style={styles.retryButton} onPress={loadMapData}>
            <Text style={styles.retryButtonText}>{t('retry')}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.mapWrapper}>
          <HlbSpatialMap
            ref={mapRef}
            testID="area-map-view"
            style={styles.map}
            initialRegion={region}
            mapType={mapLayer}
            showBoundary={showBoundary}
            boundaryRings={boundaryRings}
            boundaryStrokeColor="#38BDF8"
            boundaryFillColor="rgba(2, 132, 199, 0.05)"
            candidateHlbs={[]}
            fitCoordinates={allBoundaryCoords}
            fullscreenEnabled={true}
            fullscreenTitle={`${areaName || 'Administrative Area'} (${areaCode})`}
          />

          {/* Top Pill Controls */}
          <View style={styles.topPillsContainer}>
            <TouchableOpacity
              testID="toggle-boundary-button"
              style={[styles.pillButton, showBoundary && styles.pillButtonActive]}
              onPress={handleToggleBoundary}
            >
              <Text style={[styles.pillButtonText, showBoundary && styles.pillButtonTextActive]}>
                🔷 Boundary
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              testID="toggle-layer-button"
              style={[styles.pillButton, styles.pillButtonActive]}
              onPress={handleToggleLayer}
            >
              <Text style={[styles.pillButtonText, styles.pillButtonTextActive]}>
                {mapLayer === 'satellite' ? '🗺️ Satellite' : '🗺️ Map'}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Right Floating Map Tools */}
          <View style={styles.rightToolsContainer}>
            <TouchableOpacity
              testID="map-tool-location"
              style={styles.toolButton}
              onPress={handleFitBoundary}
            >
              <Text style={styles.toolButtonIcon}>🎯</Text>
            </TouchableOpacity>

            <TouchableOpacity
              testID="map-tool-zoomin"
              style={styles.toolButton}
              onPress={handleZoomIn}
            >
              <Text style={styles.toolButtonIcon}>＋</Text>
            </TouchableOpacity>

            <TouchableOpacity
              testID="map-tool-zoomout"
              style={styles.toolButton}
              onPress={handleZoomOut}
            >
              <Text style={styles.toolButtonIcon}>−</Text>
            </TouchableOpacity>

            <TouchableOpacity
              testID="map-tool-fit"
              style={styles.toolButton}
              onPress={handleFitBoundary}
            >
              <Text style={styles.toolButtonIcon}>🗖</Text>
            </TouchableOpacity>
          </View>

          {/* Bottom Information Card */}
          <View style={styles.bottomCard}>
            <View style={styles.bottomCardHeader}>
              <View>
                <Text style={styles.bottomAreaName}>{areaName.toUpperCase()}</Text>
                <Text style={styles.bottomAreaCode}>{areaCode}</Text>
              </View>
              <View
                style={[
                  styles.sourceBadge,
                  isSatelliteSource ? styles.sourceBadgeSatellite : styles.sourceBadgeDev,
                ]}
              >
                <Text
                  style={[
                    styles.sourceBadgeText,
                    isSatelliteSource ? styles.sourceBadgeTextSatellite : styles.sourceBadgeTextDev,
                  ]}
                >
                  {isSatelliteSource ? 'SATELLITE-DERIVED' : 'DEVELOPMENT DATA'}
                </Text>
              </View>
            </View>

            <View style={styles.bottomStatsRow}>
              <View style={styles.statItem}>
                <Text style={styles.statLabel}>Estimated Buildings</Text>
                <Text style={styles.statValue}>{totalBuildings}</Text>
              </View>

              <View style={styles.statDivider} />

              <View style={styles.statItem}>
                <Text style={styles.statLabel}>Area</Text>
                <Text style={styles.statValue}>2.46 km²</Text>
              </View>

              <View style={styles.statDivider} />

              <View style={styles.statItem}>
                <Text style={styles.statLabel}>Status</Text>
                <Text style={styles.statValueActive}>Active</Text>
              </View>
            </View>

            {/* Proceed to HLB Generation Action */}
            <View style={styles.cardActionRow}>
              <PrimaryButton
                title="⚡ GENERATE HLBs"
                onPress={() =>
                  navigation.navigate('HlbGeneration', {
                    areaId: areaId,
                    areaName: areaName,
                  })
                }
                testID="generate-hlbs-from-map-btn"
              />
            </View>
          </View>
        </View>
      )}
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0F172A',
  },
  mapWrapper: {
    flex: 1,
    width: '100%',
    height: '100%',
    position: 'relative',
  },
  map: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    width: '100%',
    height: '100%',
  },
  cardActionRow: {
    marginTop: 12,
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  retryButton: {
    marginTop: 16,
    paddingHorizontal: 24,
    paddingVertical: 12,
    backgroundColor: '#2563EB',
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#FFFFFF',
    fontWeight: '600',
  },
  topPillsContainer: {
    position: 'absolute',
    top: 16,
    left: 16,
    right: 16,
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    zIndex: 10,
  },
  pillButton: {
    backgroundColor: 'rgba(15, 23, 42, 0.82)',
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 20,
    borderWidth: 1,
    borderColor: 'rgba(56, 189, 248, 0.4)',
  },
  pillButtonActive: {
    backgroundColor: 'rgba(2, 132, 199, 0.9)',
    borderColor: '#38BDF8',
  },
  pillButtonText: {
    color: '#94A3B8',
    fontSize: 12,
    fontWeight: '600',
  },
  pillButtonTextActive: {
    color: '#FFFFFF',
    fontWeight: '700',
  },
  rightToolsContainer: {
    position: 'absolute',
    right: 16,
    top: 70,
    gap: 8,
    zIndex: 10,
  },
  toolButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    borderWidth: 1,
    borderColor: 'rgba(56, 189, 248, 0.4)',
    alignItems: 'center',
    justifyContent: 'center',
    ...Platform.select({
      web: {
        boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.3)',
      },
      default: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.3,
        shadowRadius: 4,
        elevation: 4,
      },
    }),
  },
  toolButtonIcon: {
    fontSize: 16,
    color: '#FFFFFF',
  },
  areaBadge: {
    backgroundColor: 'rgba(15, 23, 42, 0.85)',
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: '#38BDF8',
  },
  areaBadgeText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  clusterMarker: {
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 2,
    borderColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
    ...Platform.select({
      web: {
        boxShadow: '0px 2px 8px rgba(0, 0, 0, 0.4)',
      },
      default: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 2 },
        shadowOpacity: 0.4,
        shadowRadius: 4,
        elevation: 5,
      },
    }),
  },
  clusterMarkerText: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 13,
  },
  buildingPin: {
    width: 24,
    height: 24,
    borderRadius: 6,
    backgroundColor: '#0284C7',
    borderWidth: 1.5,
    borderColor: '#FFFFFF',
    alignItems: 'center',
    justifyContent: 'center',
  },
  buildingPinIcon: {
    fontSize: 11,
  },
  calloutCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 10,
    padding: 10,
    width: 200,
    ...Platform.select({
      web: {
        boxShadow: '0px 3px 10px rgba(0, 0, 0, 0.3)',
      },
      default: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 3 },
        shadowOpacity: 0.3,
        shadowRadius: 6,
        elevation: 6,
      },
    }),
  },
  calloutHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottomWidth: 1,
    borderBottomColor: '#E2E8F0',
    paddingBottom: 4,
    marginBottom: 4,
  },
  calloutTitle: {
    fontSize: 12,
    fontWeight: '700',
    color: '#0F172A',
  },
  calloutIcon: {
    fontSize: 12,
  },
  calloutRef: {
    fontSize: 12,
    fontWeight: '700',
    color: '#2563EB',
    marginBottom: 2,
  },
  calloutMeta: {
    fontSize: 10,
    color: '#64748B',
    lineHeight: 14,
  },
  calloutBold: {
    fontWeight: '700',
    color: '#334155',
  },
  bottomCard: {
    position: 'absolute',
    bottom: 16,
    left: 16,
    right: 16,
    backgroundColor: 'rgba(15, 23, 42, 0.92)',
    borderRadius: 16,
    padding: 16,
    borderWidth: 1,
    borderColor: 'rgba(56, 189, 248, 0.3)',
    ...Platform.select({
      web: {
        boxShadow: '0px 4px 16px rgba(0, 0, 0, 0.4)',
      },
      default: {
        shadowColor: '#000',
        shadowOffset: { width: 0, height: 4 },
        shadowOpacity: 0.4,
        shadowRadius: 8,
        elevation: 8,
      },
    }),
  },
  bottomCardHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 12,
  },
  bottomAreaName: {
    fontSize: 16,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  bottomAreaCode: {
    fontSize: 12,
    color: '#94A3B8',
    marginTop: 2,
  },
  sourceBadge: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
  },
  sourceBadgeSatellite: {
    backgroundColor: 'rgba(16, 185, 129, 0.2)',
    borderWidth: 1,
    borderColor: '#10B981',
  },
  sourceBadgeDev: {
    backgroundColor: 'rgba(245, 158, 11, 0.2)',
    borderWidth: 1,
    borderColor: '#F59E0B',
  },
  sourceBadgeText: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
  },
  sourceBadgeTextSatellite: {
    color: '#34D399',
  },
  sourceBadgeTextDev: {
    color: '#FBBF24',
  },
  bottomStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingTop: 8,
    borderTopWidth: 1,
    borderTopColor: 'rgba(148, 163, 184, 0.2)',
  },
  statItem: {
    alignItems: 'center',
    flex: 1,
  },
  statDivider: {
    width: 1,
    height: 28,
    backgroundColor: 'rgba(148, 163, 184, 0.2)',
  },
  statLabel: {
    fontSize: 11,
    color: '#94A3B8',
    marginBottom: 2,
  },
  statValue: {
    fontSize: 15,
    fontWeight: '800',
    color: '#FFFFFF',
  },
  statValueActive: {
    fontSize: 15,
    fontWeight: '800',
    color: '#34D399',
  },
  selectedBuildingPanel: {
    marginTop: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: 'rgba(148, 163, 184, 0.2)',
  },
  selectedBuildingHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 4,
  },
  selectedBuildingTitle: {
    fontSize: 13,
    fontWeight: '700',
    color: '#38BDF8',
  },
  closeButtonText: {
    color: '#94A3B8',
    fontSize: 14,
    fontWeight: 'bold',
    padding: 2,
  },
  selectedBuildingMeta: {
    fontSize: 11,
    color: '#CBD5E1',
    lineHeight: 16,
  },
});
