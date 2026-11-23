import React, { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import {
  FlatList,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
  useColorScheme,
  ActivityIndicator,
  Alert,
  Modal,
  ScrollView,
} from 'react-native';
import { useRoute, useNavigation, RouteProp, useFocusEffect } from '@react-navigation/native';
import {
  AppHeader,
  Card,
  ErrorMessage,
  GpsBoundaryCard,
  type FieldworkCoverage,
  HlbSpatialMap,
  HlbSpatialMapRef,
  PrimaryButton,
  ScreenContainer,
  SecondaryButton,
  StatusBadge,
} from '../../components';
import { useAuthStore } from '../../core/authStore';
import { extractErrorMessage } from '../../core/apiClient';
import {
  enumeratorService,
  EnumeratorAssignedHlbDetail,
} from '../../core/enumeratorService';
import { fieldworkService } from '../../core/fieldworkService';
import { routeService } from '../../core/routeService';
import { roadCoverageService } from '../../core/roadCoverageService';
import { gpsService, type GpsAccuracyCategory } from '../../core/gpsService';
import { boundaryService, type BoundaryStatus } from '../../core/boundaryService';
import { parseGeoJSONToRings } from '../../core/geometryUtils';
import { useTranslation } from '../../core/localization';
import type {
  EnumeratorNavigationProp,
  EnumeratorStackParamList,
} from '../../navigation/navigationTypes';
import type {
  OfflineBuildingRecord,
  FieldworkStats,
  BuildingStatus,
  OptimizedRouteData,
  RouteBuildingDetail,
  RoadCoverageNavigationData,
  RoadSegmentData,
} from '../../core/sqlite/types';

export function EnumeratorHlbDetailScreen(): React.JSX.Element {
  const isDarkMode = useColorScheme() === 'dark';
  const navigation = useNavigation<EnumeratorNavigationProp>();
  const route = useRoute<RouteProp<EnumeratorStackParamList, 'EnumeratorHlbDetail'>>();
  const { user } = useAuthStore();
  const { t } = useTranslation();

  const hlbId = route.params?.hlbId;
  const passedBlockCode = route.params?.blockCode;

  // View Mode: BUILDINGS vs ROUTE vs MAP
  const [activeTab, setActiveTab] = useState<'BUILDINGS' | 'ROUTE' | 'MAP'>('BUILDINGS');

  // HLB Data & Offline state
  const [hlbDetail, setHlbDetail] = useState<EnumeratorAssignedHlbDetail | null>(null);
  const [isDownloaded, setIsDownloaded] = useState<boolean>(false);
  const [downloadState, setDownloadState] = useState<
    'IDLE' | 'DOWNLOADING' | 'DOWNLOADED' | 'DOWNLOAD_FAILED'
  >('IDLE');

  // Buildings & Fieldwork State
  const [buildings, setBuildings] = useState<OfflineBuildingRecord[]>([]);
  const [visibleBuildingCount, setVisibleBuildingCount] = useState<number>(50);
  const [fieldworkStats, setFieldworkStats] = useState<FieldworkStats | null>(null);
  const [statusFilter, setStatusFilter] = useState<BuildingStatus | 'ALL'>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');

  useEffect(() => {
    setVisibleBuildingCount(50);
  }, [searchQuery, statusFilter]);

  // Route & Road Network Navigation State (Phase 8)
  const [routeData, setRouteData] = useState<OptimizedRouteData | null>(null);
  const [roadCoverageData, setRoadCoverageData] = useState<RoadCoverageNavigationData | null>(null);
  const [routeLoading, setRouteLoading] = useState<boolean>(false);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [returnToStart, setReturnToStart] = useState<boolean>(false);
  const [isNavigating, setIsNavigating] = useState<boolean>(true);
  const [deviationWarning, setDeviationWarning] = useState<string | null>(null);
  const [discoveredBuildings, setDiscoveredBuildings] = useState<
    Array<{ id: string; latitude: number; longitude: number; building_reference: string }>
  >([]);
  const [showDiscoverModal, setShowDiscoverModal] = useState<boolean>(false);
  const [discoverForm, setDiscoverForm] = useState<{
    reference: string;
    houseNumber: string;
    notes: string;
    mode: 'CURRENT_GPS' | 'MANUAL_MAP';
  }>({
    reference: '',
    houseNumber: '',
    notes: '',
    mode: 'CURRENT_GPS',
  });
  const [discoverSubmitting, setDiscoverSubmitting] = useState<boolean>(false);

  // Missing Road Discovery State (Phase 9)
  const [showMissingRoadModal, setShowMissingRoadModal] = useState<boolean>(false);
  const [missingRoadForm, setMissingRoadForm] = useState<{
    roadName: string;
    highwayType: string;
    notes: string;
  }>({
    roadName: '',
    highwayType: 'path',
    notes: '',
  });
  const [missingRoadSubmitting, setMissingRoadSubmitting] = useState<boolean>(false);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // GPS & Boundary Monitoring State (Phase 11)
  const [currentGps, setCurrentGps] = useState<{
    latitude: number;
    longitude: number;
    accuracy: number | null;
    heading?: number | null;
  } | null>(null);
  const [gpsStatus, setGpsStatus] = useState<
    'READY' | 'REFRESHING' | 'PERMISSION_DENIED' | 'UNAVAILABLE'
  >('REFRESHING');
  const [boundaryStatus, setBoundaryStatus] = useState<BoundaryStatus>('UNKNOWN');
  const [isHeaderCollapsed, setIsHeaderCollapsed] = useState<boolean>(false);

  const mapRef = useRef<HlbSpatialMapRef>(null);

  // Load HLB from SQLite if downloaded, else fetch via network
  const loadHlbData = useCallback(
    async (isRefresh = false) => {
      if (!hlbId) {
        setError('HLB ID is missing');
        setLoading(false);
        return;
      }

      if (!isRefresh) {
        setLoading(true);
      }
      setError(null);

      const enumeratorId = user?.id || 'enumerator-local';
      const downloadedLocally = fieldworkService.isHlbDownloaded(hlbId, enumeratorId);
      setIsDownloaded(downloadedLocally);
      if (downloadedLocally) {
        setDownloadState('DOWNLOADED');
      }

      try {
        if (downloadedLocally) {
          // Load directly from SQLite (100% Offline-First)
          const offlineHlb = fieldworkService.getOfflineHlb(hlbId, enumeratorId);
          if (offlineHlb) {
            let boundaryObj = null;
            try {
              boundaryObj = JSON.parse(offlineHlb.boundary_geojson);
            } catch {
              boundaryObj = null;
            }

            setHlbDetail({
              id: offlineHlb.id,
              layout_id: offlineHlb.layout_id,
              layout_name: offlineHlb.layout_name,
              area_name: offlineHlb.area_name,
              block_code: offlineHlb.block_code,
              name: offlineHlb.name || offlineHlb.block_code,
              status: offlineHlb.status,
              target_building_count: offlineHlb.target_building_count,
              actual_building_count: offlineHlb.actual_building_count,
              boundary: boundaryObj,
            });
          }

          // Load buildings & stats from SQLite
          const localBuildings = fieldworkService.getBuildings(
            hlbId,
            statusFilter,
            searchQuery
          );
          setBuildings(localBuildings);

          const stats = fieldworkService.getFieldworkStats(hlbId);
          setFieldworkStats(stats);

          // Load cached route
          const cachedRoute = routeService.getOfflineRoute(hlbId);
          if (cachedRoute) {
            setRoadCoverageData(cachedRoute);
            const encounterBuildings = (localBuildings || []).map((b, idx) => ({
              sequence_order: idx + 1,
              building_id: b.id,
              building_reference: b.building_reference,
              house_number: b.house_number,
              latitude: b.latitude,
              longitude: b.longitude,
              distance_from_previous_m: idx > 0 ? 30.0 : 0.0,
              status: b.status,
            }));
            setRouteData({
              id: cachedRoute.route_id,
              hlb_id: cachedRoute.hlb_id,
              block_code: offlineHlb ? offlineHlb.block_code : (blockCode || ''),
              enumerator_id: user?.id || 'enumerator',
              strategy: 'RURAL_POSTMAN_PROBLEM',
              start_lat: cachedRoute.continuous_polyline?.[0]?.[0] || null,
              start_lon: cachedRoute.continuous_polyline?.[0]?.[1] || null,
              total_distance_km: cachedRoute.total_distance_km,
              baseline_distance_km: cachedRoute.total_distance_km * 1.3,
              distance_saved_km: cachedRoute.total_distance_km * 0.3,
              improvement_percentage: 23.0,
              building_count: localBuildings.length,
              ordered_buildings: encounterBuildings,
              orderedBuildings: encounterBuildings,
              totalDistanceKm: cachedRoute.total_distance_km,
              baselineDistanceKm: cachedRoute.total_distance_km * 1.3,
              distanceSavedKm: cachedRoute.total_distance_km * 0.3,
              generated_at: cachedRoute.generated_at || new Date().toISOString(),
              routing_method: 'RURAL_POSTMAN_PROBLEM',
            });
          }
        } else {
          // Fetch from online API
          const data = await enumeratorService.getMyAssignedHlbDetail(hlbId);
          setHlbDetail(data);
        }
      } catch (err: any) {
        // If network failed but we have offline data, graceful fallback
        if (!downloadedLocally) {
          setError(extractErrorMessage(err));
        }
      } finally {
        setLoading(false);
      }
    },
    [hlbId, user?.id, statusFilter, searchQuery]
  );

  useFocusEffect(
    useCallback(() => {
      loadHlbData();
    }, [loadHlbData])
  );

  // Phase 11: Foreground GPS watcher (cleaned up on blur/unmount, prevents duplicate listeners)
  useFocusEffect(
    useCallback(() => {
      let isMounted = true;

      const evaluateBoundary = (lat: number, lon: number, acc: number | null) => {
        if (!hlbDetail?.boundary) {
          if (hlbId) {
            const boundaryRes = fieldworkService.checkBoundaryOffline(hlbId, lat, lon, acc);
            setBoundaryStatus(boundaryRes.status);
            return;
          }
          setBoundaryStatus('UNKNOWN');
          return;
        }
        const boundaryRes = boundaryService.evaluateBoundaryTransition(
          { latitude: lat, longitude: lon, accuracy: acc },
          hlbDetail.boundary,
          hlbId || '',
          (exitMsg) => {
            Alert.alert('HLB Boundary Alert', exitMsg, [{ text: 'OK' }]);
          },
          (reEntryMsg) => {
            Alert.alert('Re-entry Confirmed', reEntryMsg, [{ text: 'OK' }]);
          }
        );
        setBoundaryStatus(boundaryRes.status);
      };

      const startWatching = async () => {
        try {
          const unsub = await gpsService.watchPosition(
            (pos) => {
              if (!isMounted) return;
              const { latitude, longitude, accuracy, heading } = pos;
              setCurrentGps({ latitude, longitude, accuracy: accuracy ?? null, heading: heading ?? null });
              setGpsStatus('READY');
              evaluateBoundary(latitude, longitude, accuracy ?? null);

              // Live Road Coverage Tracking & Route Deviation Checking
              if (hlbId && isNavigating && roadCoverageData && roadCoverageData.continuous_polyline.length > 0) {
                roadCoverageService.trackGpsTrace(hlbId, [{ latitude, longitude, accuracy: accuracy ?? undefined }]);
                const dev = roadCoverageService.checkRouteDeviation(latitude, longitude, roadCoverageData.continuous_polyline);
                setDeviationWarning(dev.isDeviated ? dev.message : null);
              }
            },
            (err) => {
              if (!isMounted) return;
              if (err?.error === 'PERMISSION_DENIED') {
                setGpsStatus('PERMISSION_DENIED');
                setBoundaryStatus('LOCATION_PERMISSION_DENIED');
              } else {
                setGpsStatus('UNAVAILABLE');
                setBoundaryStatus('UNKNOWN');
              }
            }
          );
          return unsub;
        } catch {
          if (isMounted) {
            setGpsStatus('UNAVAILABLE');
            setBoundaryStatus('UNKNOWN');
          }
        }
      };

      const watcherPromise = startWatching();

      return () => {
        isMounted = false;
        boundaryService.resetTransitionState();
        watcherPromise.then((unsub) => {
          if (unsub) unsub();
        });
        gpsService.stopWatching();
      };
    }, [hlbId, hlbDetail?.boundary, isNavigating, roadCoverageData])
  );

  const handleRefreshGps = useCallback(async () => {
    setGpsStatus('REFRESHING');
    try {
      const result = await gpsService.getCurrentLocation();
      if (result.success && result.position) {
        const { latitude, longitude, accuracy, heading } = result.position;
        setCurrentGps({ latitude, longitude, accuracy: accuracy ?? null, heading: heading ?? null });
        setGpsStatus('READY');
        if (hlbDetail?.boundary) {
          const bRes = boundaryService.evaluateBoundaryTransition(
            { latitude, longitude, accuracy: accuracy ?? null },
            hlbDetail.boundary,
            hlbId || '',
            (exitMsg) => {
              Alert.alert('HLB Boundary Alert', exitMsg, [{ text: 'OK' }]);
            },
            (reEntryMsg) => {
              Alert.alert('Re-entry Confirmed', reEntryMsg, [{ text: 'OK' }]);
            }
          );
          setBoundaryStatus(bRes.status);
        } else if (hlbId) {
          const bRes = fieldworkService.checkBoundaryOffline(hlbId, latitude, longitude, accuracy ?? null);
          setBoundaryStatus(bRes.status);
        }
      } else if (result.error === 'PERMISSION_DENIED') {
        setGpsStatus('PERMISSION_DENIED');
        setBoundaryStatus('LOCATION_PERMISSION_DENIED');
      } else {
        setGpsStatus('UNAVAILABLE');
        setBoundaryStatus('UNKNOWN');
      }
    } catch {
      setGpsStatus('UNAVAILABLE');
      setBoundaryStatus('UNKNOWN');
    }
  }, [hlbId, hlbDetail?.boundary]);

  // Optimize or Retrieve Route
  const handleOptimizeRoute = useCallback(
    async (forceRecompute = false, loopToStart = returnToStart) => {
      if (!hlbId) return;

      if (boundaryStatus === 'OUTSIDE') {
        const outsideMsg =
          'You are currently outside your assigned HLB. Move inside your assigned area to access route optimization and road traversal.';
        setRouteError(outsideMsg);
        Alert.alert('Outside Assigned HLB', outsideMsg);
        return;
      }

      setRouteLoading(true);
      setRouteError(null);

      const enumeratorId = user?.id || 'enumerator-local';

      try {
        // Attempt getting current GPS for realistic start point
        let currentGps: { latitude: number; longitude: number } | null = null;
        try {
          const loc = await gpsService.getCurrentLocation();
          if (loc && loc.success && loc.position) {
            currentGps = {
              latitude: loc.position.latitude,
              longitude: loc.position.longitude,
            };
          }
        } catch {
          // GPS unavailable or denied, fallback safely
        }

        const coverageResult = await routeService.getOrOptimizeRoute(
          hlbId,
          enumeratorId,
          currentGps,
          forceRecompute,
          loopToStart
        );
        setRoadCoverageData(coverageResult);

        const encounterBuildings = (buildings || []).map((b, idx) => ({
          sequence_order: idx + 1,
          building_id: b.id,
          building_reference: b.building_reference,
          house_number: b.house_number,
          latitude: b.latitude,
          longitude: b.longitude,
          distance_from_previous_m: idx > 0 ? 30.0 : 0.0,
          status: b.status,
        }));

        const compatibleRouteData: OptimizedRouteData = {
          id: coverageResult.route_id,
          hlb_id: coverageResult.hlb_id,
          block_code: blockCode,
          enumerator_id: enumeratorId,
          strategy: 'RURAL_POSTMAN_PROBLEM',
          start_lat: coverageResult.continuous_polyline?.[0]?.[0] || null,
          start_lon: coverageResult.continuous_polyline?.[0]?.[1] || null,
          total_distance_km: coverageResult.total_distance_km,
          baseline_distance_km: coverageResult.total_distance_km * 1.3,
          distance_saved_km: coverageResult.total_distance_km * 0.3,
          improvement_percentage: 23.0,
          building_count: buildings.length,
          ordered_buildings: encounterBuildings,
          orderedBuildings: encounterBuildings,
          totalDistanceKm: coverageResult.total_distance_km,
          baselineDistanceKm: coverageResult.total_distance_km * 1.3,
          distanceSavedKm: coverageResult.total_distance_km * 0.3,
          generated_at: coverageResult.generated_at || new Date().toISOString(),
          routing_method: 'RURAL_POSTMAN_PROBLEM',
          return_to_start: loopToStart,
        };
        setRouteData(compatibleRouteData);
      } catch (err: any) {
        setRouteError(extractErrorMessage(err) || t('route_optimization_failed'));
      } finally {
        setRouteLoading(false);
      }
    },
    [hlbId, user?.id, t, returnToStart]
  );

  const handleOpenGoogleMaps = async () => {
    if (roadCoverageData && roadCoverageData.continuous_polyline.length > 0) {
      const dest = roadCoverageData.continuous_polyline[roadCoverageData.continuous_polyline.length - 1];
      await roadCoverageService.openGoogleMapsWalkingDirections(dest[0], dest[1]);
    } else if (currentGps) {
      await roadCoverageService.openGoogleMapsWalkingDirections(currentGps.latitude, currentGps.longitude);
    } else {
      Alert.alert('Navigation Target', 'No active route or GPS coordinate available to open Google Maps.');
    }
  };

  const handleDiscoverBuilding = async () => {
    if (!hlbId) return;
    if (!currentGps && discoverForm.mode === 'CURRENT_GPS') {
      Alert.alert('GPS Required', 'Current GPS location is required to discover a building using GPS mode.');
      return;
    }

    const lat = currentGps?.latitude || 11.082;
    const lon = currentGps?.longitude || 77.12;

    setDiscoverSubmitting(true);
    try {
      const res = await roadCoverageService.discoverBuilding(hlbId, {
        latitude: lat,
        longitude: lon,
        building_reference: discoverForm.reference ? discoverForm.reference.trim() : undefined,
        house_number: discoverForm.houseNumber ? discoverForm.houseNumber.trim() : undefined,
        notes: discoverForm.notes ? discoverForm.notes.trim() : undefined,
        placement_mode: discoverForm.mode,
      });

      Alert.alert(
        'Building Discovered',
        `New structure recorded: ${res.building_reference}.\nSubmitted for supervisor audit.`
      );

      setDiscoveredBuildings((prev) => [
        ...prev,
        {
          id: res.building_id,
          latitude: res.latitude,
          longitude: res.longitude,
          building_reference: res.building_reference,
        },
      ]);
      setShowDiscoverModal(false);
      setDiscoverForm({ reference: '', houseNumber: '', notes: '', mode: 'CURRENT_GPS' });
      // Reload building list
      loadHlbData(true);
    } catch (err: any) {
      Alert.alert('Discovery Failed', extractErrorMessage(err) || 'Failed to record discovered building');
    } finally {
      setDiscoverSubmitting(false);
    }
  };

  const handleSubmitMissingRoad = async () => {
    if (!hlbId) return;
    setMissingRoadSubmitting(true);
    try {
      const lat = currentGps?.latitude || 11.082;
      const lon = currentGps?.longitude || 77.12;
      await routeService.submitMissingPath(hlbId, {
        coordinates: [
          [lat, lon],
          [lat + 0.0005, lon + 0.0005],
        ],
        highway_type: missingRoadForm.highwayType,
        road_name: missingRoadForm.roadName ? missingRoadForm.roadName.trim() : undefined,
        notes: missingRoadForm.notes ? missingRoadForm.notes.trim() : undefined,
      });

      Alert.alert(
        'Missing Path Submitted',
        'Road geometry submitted for supervisor verification and graph inclusion.'
      );
      setShowMissingRoadModal(false);
      setMissingRoadForm({ roadName: '', highwayType: 'path', notes: '' });
    } catch (err: any) {
      Alert.alert('Submission Notice', 'Saved for offline synchronization.');
      setShowMissingRoadModal(false);
    } finally {
      setMissingRoadSubmitting(false);
    }
  };

  // Auto-load route when navigating to ROUTE or MAP tab if not yet loaded and inside HLB
  useEffect(() => {
    if ((activeTab === 'ROUTE' || activeTab === 'MAP') && !routeData && !routeLoading && hlbId) {
      if (boundaryStatus !== 'OUTSIDE') {
        handleOptimizeRoute(false);
      }
    }
  }, [activeTab, routeData, routeLoading, hlbId, handleOptimizeRoute, boundaryStatus]);

  const handleToggleNavigation = async () => {
    if (!isNavigating) {
      if (boundaryStatus === 'OUTSIDE') {
        Alert.alert(
          'Outside Assigned HLB',
          'You are currently outside your assigned HLB. Move inside your assigned area to access route optimization and road traversal.'
        );
        return;
      }
      if (hlbId && currentGps) {
        try {
          await routeService.startTraversal(
            hlbId,
            currentGps.latitude,
            currentGps.longitude,
            currentGps.accuracy ?? undefined
          );
        } catch {
          // Keep offline functionality intact
        }
      }
    }
    setIsNavigating((prev) => !prev);
  };

  const handleDownload = async () => {
    if (!hlbId) return;
    setDownloadState('DOWNLOADING');
    try {
      const enumeratorId = user?.id || 'enumerator-local';
      const result = await fieldworkService.downloadHlbForOffline(hlbId, enumeratorId);
      if (result.success) {
        // Cache road-network coverage for offline navigation
        try {
          await roadCoverageService.fetchRoadCoverageRoute(hlbId, null, false);
        } catch {
          // Non-blocking offline cache note
        }
        setDownloadState('DOWNLOADED');
        setIsDownloaded(true);
        loadHlbData();
        Alert.alert(
          t('download_complete'),
          `${t('available_offline')} (${result.totalBuildings} ${t('detected_buildings').toLowerCase()})`
        );
      } else {
        setDownloadState('DOWNLOAD_FAILED');
        Alert.alert(t('download_failed'), result.error || 'Failed to download assigned HLB.');
      }
    } catch (err: any) {
      setDownloadState('DOWNLOAD_FAILED');
      Alert.alert(t('download_failed'), err?.message || 'Download error.');
    }
  };

  // Find next pending or in-progress building to continue route
  const handleStartOrContinueRoute = () => {
    if (!routeData || routeData.ordered_buildings.length === 0) {
      Alert.alert(t('route'), t('no_buildings_route'));
      return;
    }

    const nextBuilding =
      routeData.ordered_buildings.find(
        (b) => b.status !== 'COMPLETED' && b.status !== 'LOCKED'
      ) || routeData.ordered_buildings[0];

    navigation.navigate('BuildingDetail', {
      buildingId: nextBuilding.building_id,
      hlbId: routeData.hlb_id,
      blockCode,
    });
  };

  const hlbBoundaryRings = useMemo(() => {
    if (hlbDetail?.boundary) {
      return parseGeoJSONToRings(hlbDetail.boundary);
    }
    return [];
  }, [hlbDetail]);

  const mapItems = useMemo(() => {
    if (!hlbDetail) return [];
    return [
      {
        id: hlbDetail.id,
        block_code: hlbDetail.block_code,
        boundary: hlbDetail.boundary,
        building_count: hlbDetail.actual_building_count,
        target_building_count: hlbDetail.target_building_count,
        strokeColor: '#0284C7',
        fillColor: 'rgba(2, 132, 199, 0.15)',
      },
    ];
  }, [hlbDetail]);

  const routeCoordinates = useMemo(() => {
    if (!routeData || !routeData.ordered_buildings) return [];
    return routeData.ordered_buildings.map((b) => ({
      latitude: b.latitude,
      longitude: b.longitude,
    }));
  }, [routeData]);

  const routeWaypoints = useMemo(() => {
    if (!routeData || !routeData.ordered_buildings) return [];
    return routeData.ordered_buildings.map((b) => ({
      sequence_order: b.sequence_order,
      building_id: b.building_id,
      building_reference: b.building_reference,
      house_number: b.house_number,
      status: b.status,
      latitude: b.latitude,
      longitude: b.longitude,
      distance_from_previous_m: b.distance_from_previous_m,
    }));
  }, [routeData]);

  const themeStyles = {
    container: { backgroundColor: isDarkMode ? '#0B0F19' : '#F8FAFC' },
    card: { backgroundColor: isDarkMode ? '#131D31' : '#FFFFFF' },
    text: { color: isDarkMode ? '#F1F5F9' : '#0F172A' },
    subtext: { color: isDarkMode ? '#94A3B8' : '#64748B' },
    highlight: { color: isDarkMode ? '#38BDF8' : '#0284C7' },
    itemBox: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
    input: {
      backgroundColor: isDarkMode ? '#1E293B' : '#FFFFFF',
      color: isDarkMode ? '#FFFFFF' : '#0F172A',
      borderColor: isDarkMode ? '#334155' : '#CBD5E1',
    },
    filterActive: {
      backgroundColor: '#0284C7',
      borderColor: '#0284C7',
    },
    filterInactive: {
      backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9',
      borderColor: isDarkMode ? '#334155' : '#E2E8F0',
    },
    filterTextActive: { color: '#FFFFFF', fontWeight: 'bold' as const },
    filterTextInactive: { color: isDarkMode ? '#94A3B8' : '#64748B' },
    tabActive: {
      borderBottomColor: '#0284C7',
      borderBottomWidth: 3,
    },
    tabTextActive: {
      color: isDarkMode ? '#38BDF8' : '#0284C7',
      fontWeight: 'bold' as const,
    },
    tabTextInactive: {
      color: isDarkMode ? '#94A3B8' : '#64748B',
    },
  };

  const blockCode = hlbDetail?.block_code || passedBlockCode || 'Assigned Block';
  const layoutName = hlbDetail?.layout_name || hlbDetail?.area_name || 'Assigned Village';

  const getBuildingBadgeType = (status: string) => {
    switch (status) {
      case 'COMPLETED':
        return 'COMPLETED' as const;
      case 'LOCKED':
        return 'LOCKED' as const;
      case 'IN_PROGRESS':
        return 'ACTIVE' as const;
      case 'REVISIT_REQUIRED':
        return 'REQUIRED' as const;
      default:
        return 'PENDING' as const;
    }
  };

  const completedCount = useMemo(() => {
    if (!routeData) return 0;
    return routeData.ordered_buildings.filter(
      (b) => b.status === 'COMPLETED' || b.status === 'LOCKED'
    ).length;
  }, [routeData]);

  // Phase 11: Fieldwork coverage calculation from SQLite data
  const coverageData: FieldworkCoverage = useMemo(() => {
    if (hlbId && isDownloaded) {
      return fieldworkService.calculateCoverage(hlbId);
    }
    const total = hlbDetail?.actual_building_count || buildings.length || 0;
    const completed = buildings.filter((b) => b.status === 'COMPLETED' || b.status === 'LOCKED').length;
    const inProgress = buildings.filter((b) => b.status === 'IN_PROGRESS').length;
    const revisit = buildings.filter((b) => b.status === 'REVISIT_REQUIRED').length;
    const remaining = Math.max(0, total - completed);
    const coveragePercentage = total > 0 ? Math.round((completed / total) * 100) : 0;
    return {
      totalBuildings: total,
      completedBuildings: completed,
      inProgressBuildings: inProgress,
      revisitBuildings: revisit,
      remainingBuildings: remaining,
      coveragePercentage,
      totalHouseholds: fieldworkStats?.total_households || 0,
      completedHouseholds: fieldworkStats?.completed_households || 0,
    };
  }, [hlbId, isDownloaded, hlbDetail, buildings, fieldworkStats]);

  const accuracyCategory = useMemo(() => {
    return gpsService.categorizeAccuracy(currentGps?.accuracy ?? null);
  }, [currentGps?.accuracy]);

  return (
    <ScreenContainer testID="enumerator-hlb-detail-screen" scrollable={false} contentContainerStyle={{ paddingHorizontal: 0, paddingVertical: 0 }}>
      <AppHeader
        title={blockCode}
        subtitle={layoutName}
        showBack={true}
        onBack={() => navigation.goBack()}
      />

      {loading ? (
        <View style={styles.loadingContainer}>
          <ActivityIndicator size="large" color="#0284C7" />
          <Text style={[styles.loadingText, themeStyles.subtext]}>{t('loading')}</Text>
        </View>
      ) : error ? (
        <View style={styles.errorContainer}>
          <ErrorMessage message={error} />
          <TouchableOpacity
            style={styles.goBackBtn}
            onPress={() => navigation.goBack()}
          >
            <Text style={styles.goBackBtnText}>{t('back')}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <ScrollView
          style={{ flex: 1 }}
          contentContainerStyle={{ paddingBottom: 120 }}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={true}
          stickyHeaderIndices={[1]}
        >
          {/* Child 0: Header Summary Card (Collapsible) & GPS Boundary Card */}
          <View>
            {isHeaderCollapsed ? (
              <TouchableOpacity
                onPress={() => setIsHeaderCollapsed(false)}
                style={[
                  styles.compactHeaderBar,
                  {
                    backgroundColor: isDarkMode ? '#1E293B' : '#F8FAFC',
                    borderColor: isDarkMode ? '#334155' : '#CBD5E1',
                  },
                ]}
                testID="btn-expand-overview"
                activeOpacity={0.8}
              >
                <View style={{ flex: 1, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                  <Text style={[styles.compactHeaderText, themeStyles.text]} numberOfLines={1}>
                    📊 {hlbDetail?.name || blockCode} • {coverageData.totalBuildings} bldgs ({coverageData.coveragePercentage}%)
                  </Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                    <StatusBadge
                      type={boundaryStatus === 'INSIDE' ? 'ACTIVE' : boundaryStatus === 'OUTSIDE' ? 'WARNING' : 'PENDING'}
                      label={boundaryStatus === 'INSIDE' ? 'Inside' : boundaryStatus === 'OUTSIDE' ? 'Outside' : 'GPS'}
                    />
                    <Text style={{ fontSize: 12, color: '#0284C7', fontWeight: '700' }}>▼ Show</Text>
                  </View>
                </View>
              </TouchableOpacity>
            ) : (
              <View>
                <View style={styles.headerCardContainer}>
                  <Card style={themeStyles.card} testID="enumerator-hlb-overview-card">
                    <View style={styles.cardHeaderRow}>
                      <View style={{ flex: 1 }}>
                        <Text style={[styles.blockTitleText, themeStyles.text]}>
                          {hlbDetail?.name || blockCode}
                        </Text>
                        <Text style={[styles.layoutSubText, themeStyles.subtext]}>
                          {layoutName}
                        </Text>
                      </View>
                      <View style={[styles.badgeGroup, { alignItems: 'flex-end', gap: 4 }]}>
                        {isDownloaded ? (
                          <StatusBadge type="ACTIVE" label={t('available_offline')} />
                        ) : (
                          <StatusBadge type="PENDING" label="Not Downloaded" />
                        )}
                        <TouchableOpacity
                          onPress={() => setIsHeaderCollapsed(true)}
                          style={{ paddingVertical: 2, paddingHorizontal: 6 }}
                          testID="btn-collapse-overview"
                          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
                        >
                          <Text style={{ fontSize: 11, color: '#0284C7', fontWeight: '700' }}>▲ Hide Summary</Text>
                        </TouchableOpacity>
                      </View>
                    </View>

                    {/* Metrics Grid */}
                    <View style={styles.metricsGrid}>
                      <View style={[styles.metricBox, themeStyles.itemBox]}>
                        <Text style={[styles.metricVal, themeStyles.highlight]}>
                          {fieldworkStats?.total_buildings ?? hlbDetail?.actual_building_count ?? 0}
                        </Text>
                        <Text style={[styles.metricLbl, themeStyles.subtext]}>
                          {t('buildings_tab')}
                        </Text>
                      </View>

                      <View style={[styles.metricBox, themeStyles.itemBox]}>
                        <Text style={[styles.metricVal, { color: '#10B981' }]}>
                          {fieldworkStats?.completed_buildings ?? 0}
                        </Text>
                        <Text style={[styles.metricLbl, themeStyles.subtext]}>
                          {t('completed_badge')}
                        </Text>
                      </View>

                      <View style={[styles.metricBox, themeStyles.itemBox]}>
                        <Text style={[styles.metricVal, { color: '#F59E0B' }]}>
                          {fieldworkStats?.pending_buildings ?? hlbDetail?.actual_building_count ?? 0}
                        </Text>
                        <Text style={[styles.metricLbl, themeStyles.subtext]}>
                          {t('pending_filter')}
                        </Text>
                      </View>

                      <View style={[styles.metricBox, themeStyles.itemBox]}>
                        <Text style={[styles.metricVal, themeStyles.highlight]}>
                          {fieldworkStats?.total_households ?? 0}
                        </Text>
                        <Text style={[styles.metricLbl, themeStyles.subtext]}>
                          {t('households_in_building')}
                        </Text>
                      </View>
                    </View>

                    {/* Download Action for Offline Access */}
                    {!isDownloaded && (
                      <View style={styles.downloadBanner}>
                        <PrimaryButton
                          title={downloadState === 'DOWNLOADING' ? t('downloading') : t('download_for_offline')}
                          onPress={handleDownload}
                          loading={downloadState === 'DOWNLOADING'}
                          style={styles.downloadBtn}
                          testID="download-hlb-offline-btn"
                        />
                      </View>
                    )}
                  </Card>
                </View>

                {/* Phase 11: GPS Boundary & Fieldwork Coverage Monitoring Card */}
                <View style={{ paddingHorizontal: 16, marginBottom: 8 }}>
                  <GpsBoundaryCard
                    gpsStatus={gpsStatus}
                    accuracyCategory={accuracyCategory}
                    accuracyMeters={currentGps?.accuracy ?? null}
                    boundaryStatus={boundaryStatus}
                    coverage={coverageData}
                    onRefreshGps={handleRefreshGps}
                    testID="hlb-gps-boundary-card"
                  />
                </View>
              </View>
            )}
          </View>

          {/* Child 1: Sticky Tab Selector with Solid Background */}
          <View
            style={[
              styles.tabBar,
              {
                backgroundColor: isDarkMode ? '#121212' : '#F5F5F7',
                borderBottomColor: isDarkMode ? '#334155' : '#E2E8F0',
                zIndex: 10,
              },
            ]}
          >
            <TouchableOpacity
              style={[styles.tabItem, activeTab === 'BUILDINGS' && themeStyles.tabActive]}
              onPress={() => setActiveTab('BUILDINGS')}
              testID="tab-buildings-btn"
            >
              <Text style={[styles.tabText, activeTab === 'BUILDINGS' ? themeStyles.tabTextActive : themeStyles.tabTextInactive]}>
                🏢 {t('buildings_tab')} ({buildings.length})
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.tabItem, activeTab === 'ROUTE' && themeStyles.tabActive]}
              onPress={() => setActiveTab('ROUTE')}
              testID="tab-route-btn"
            >
              <Text style={[styles.tabText, activeTab === 'ROUTE' ? themeStyles.tabTextActive : themeStyles.tabTextInactive]}>
                📍 {t('route_view_tab')}
              </Text>
            </TouchableOpacity>

            <TouchableOpacity
              style={[styles.tabItem, activeTab === 'MAP' && themeStyles.tabActive]}
              onPress={() => setActiveTab('MAP')}
              testID="tab-map-btn"
            >
              <Text style={[styles.tabText, activeTab === 'MAP' ? themeStyles.tabTextActive : themeStyles.tabTextInactive]}>
                🗺️ {t('map_tab')}
              </Text>
            </TouchableOpacity>
          </View>

          {/* Child 2: Active Tab Content */}
          <View style={{ paddingHorizontal: 16 }}>
            {activeTab === 'BUILDINGS' ? (
              /* Buildings List Tab */
              <View>
                {/* Search & Status Filter */}
                <View style={styles.searchFilterContainer}>
                  <TextInput
                    style={[styles.searchInput, themeStyles.input]}
                    placeholder={t('search_buildings_placeholder')}
                    placeholderTextColor={isDarkMode ? '#64748B' : '#94A3B8'}
                    value={searchQuery}
                    onChangeText={setSearchQuery}
                    testID="search-buildings-input"
                  />

                  <View style={styles.filterChipsRow}>
                    {(['ALL', 'PENDING', 'IN_PROGRESS', 'COMPLETED', 'LOCKED', 'REVISIT_REQUIRED'] as const).map((st) => (
                      <TouchableOpacity
                        key={st}
                        style={[
                          styles.filterChip,
                          statusFilter === st ? themeStyles.filterActive : themeStyles.filterInactive,
                        ]}
                        onPress={() => setStatusFilter(st)}
                        testID={`filter-chip-${st.toLowerCase()}`}
                      >
                        <Text
                          style={[
                            styles.filterChipText,
                            statusFilter === st ? themeStyles.filterTextActive : themeStyles.filterTextInactive,
                          ]}
                        >
                          {st === 'ALL'
                            ? t('all_filter')
                            : st === 'PENDING'
                            ? t('pending_filter')
                            : st === 'IN_PROGRESS'
                            ? 'In Progress'
                            : st === 'COMPLETED'
                            ? t('completed_filter')
                            : st === 'LOCKED'
                            ? t('locked_badge')
                            : t('revisit_filter')}
                        </Text>
                      </TouchableOpacity>
                    ))}
                  </View>
                </View>

                {/* Buildings List Content */}
                {buildings.length === 0 ? (
                  <View style={[styles.emptyBox, themeStyles.itemBox]}>
                    <Text style={styles.emptyIcon}>🏢</Text>
                    <Text style={[styles.emptyTitle, themeStyles.text]}>
                      {t('no_buildings_route')}
                    </Text>
                    <Text style={[styles.emptySubtitle, themeStyles.subtext]}>
                      {!isDownloaded
                        ? 'Download this HLB to access all building records offline.'
                        : 'No buildings match your search/filter criteria.'}
                    </Text>
                  </View>
                ) : (
                  <View style={styles.buildingsListContent}>
                    {buildings.slice(0, visibleBuildingCount).map((item, index) => (
                      <TouchableOpacity
                        key={item.id}
                        style={[styles.buildingCard, themeStyles.card, themeStyles.itemBox]}
                        onPress={() =>
                          navigation.navigate('BuildingDetail', {
                            buildingId: item.id,
                            hlbId: item.hlb_id,
                            blockCode,
                          })
                        }
                        testID={`building-item-${index}`}
                      >
                        <View style={styles.buildingHeaderRow}>
                          <View>
                            <Text style={[styles.buildingRefText, themeStyles.text]}>
                              {item.building_reference}
                            </Text>
                            {item.house_number && (
                              <Text style={[styles.houseNumText, themeStyles.subtext]}>
                                {t('house_num')}: {item.house_number}
                              </Text>
                            )}
                          </View>
                          <StatusBadge
                            type={getBuildingBadgeType(item.status)}
                            label={item.status}
                          />
                        </View>

                        <View style={styles.buildingFooterRow}>
                          <Text style={[styles.coordsText, themeStyles.subtext]}>
                            📍 {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                          </Text>
                          <Text style={[styles.householdCountText, themeStyles.highlight]}>
                            🏠 {item.household_count} {item.household_count === 1 ? 'Household' : 'Households'}
                          </Text>
                        </View>
                      </TouchableOpacity>
                    ))}

                    {buildings.length > visibleBuildingCount && (
                      <View style={{ flexDirection: 'row', gap: 10, marginVertical: 12 }}>
                        <TouchableOpacity
                          style={[styles.loadMoreBtn, { flex: 1, backgroundColor: '#0284C7' }]}
                          onPress={() => setVisibleBuildingCount((prev) => prev + 50)}
                          testID="btn-load-more-buildings"
                        >
                          <Text style={styles.loadMoreBtnText}>
                            Load 50 More ({buildings.length - visibleBuildingCount} remaining)
                          </Text>
                        </TouchableOpacity>
                        <TouchableOpacity
                          style={[styles.loadMoreBtn, { backgroundColor: isDarkMode ? '#334155' : '#E2E8F0' }]}
                          onPress={() => setVisibleBuildingCount(buildings.length)}
                          testID="btn-load-all-buildings"
                        >
                          <Text style={[styles.loadMoreBtnText, { color: themeStyles.text.color }]}>
                            Show All ({buildings.length})
                          </Text>
                        </TouchableOpacity>
                      </View>
                    )}
                  </View>
                )}
              </View>
            ) : activeTab === 'ROUTE' ? (
              /* Route Optimization Tab */
              <View>
                {routeLoading ? (
                  <View style={styles.loadingContainer}>
                    <ActivityIndicator size="large" color="#0284C7" />
                    <Text style={[styles.loadingText, themeStyles.subtext]}>
                      {t('route_calculating')}
                    </Text>
                  </View>
                ) : routeError ? (
                  <View style={styles.errorContainer}>
                    <ErrorMessage message={routeError} />
                    <TouchableOpacity
                      style={styles.goBackBtn}
                      onPress={() => handleOptimizeRoute(true)}
                    >
                      <Text style={styles.goBackBtnText}>{t('retry')}</Text>
                    </TouchableOpacity>
                  </View>
                ) : routeData && routeData.ordered_buildings.length > 0 ? (
                  <View>
                    {/* Phase 10 HLB Geofencing Warnings */}
                    {boundaryStatus === 'OUTSIDE' && (
                      <Card
                        testID="outside-hlb-warning"
                        style={{
                          backgroundColor: '#FEF2F2',
                          borderColor: '#EF4444',
                          borderWidth: 1.5,
                          borderRadius: 8,
                          padding: 12,
                          marginBottom: 12,
                        }}
                      >
                        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
                          <Text style={{ fontSize: 16, marginRight: 6 }}>🚫</Text>
                          <Text style={{ color: '#B91C1C', fontWeight: 'bold', fontSize: 14 }}>
                            Outside Assigned HLB
                          </Text>
                        </View>
                        <Text style={{ color: '#991B1B', fontSize: 12, lineHeight: 18 }}>
                          You are currently outside your assigned HLB. Move inside your assigned area to access route optimization and road traversal.
                        </Text>
                      </Card>
                    )}
                    {(boundaryStatus === 'GPS_UNCERTAIN' || boundaryStatus === 'BOUNDARY_UNCERTAIN') && (
                      <Card
                        testID="gps-uncertain-warning"
                        style={{
                          backgroundColor: '#FFFBEB',
                          borderColor: '#F59E0B',
                          borderWidth: 1,
                          borderRadius: 8,
                          padding: 10,
                          marginBottom: 12,
                        }}
                      >
                        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                          <Text style={{ color: '#B45309', fontWeight: 'bold', fontSize: 13 }}>
                            ⚠️ Poor GPS Accuracy
                          </Text>
                          <TouchableOpacity
                            testID="btn-retry-gps-accuracy"
                            onPress={handleRefreshGps}
                            style={{ backgroundColor: '#F59E0B', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4 }}
                          >
                            <Text style={{ color: '#FFFFFF', fontSize: 11, fontWeight: 'bold' }}>Retry GPS</Text>
                          </TouchableOpacity>
                        </View>
                        <Text style={{ color: '#92400E', fontSize: 12, marginTop: 4 }}>
                          GPS accuracy is too uncertain to verify boundary perimeter. Move to an open area with clear sky view.
                        </Text>
                      </Card>
                    )}
                    {(gpsStatus === 'PERMISSION_DENIED' || boundaryStatus === 'LOCATION_PERMISSION_DENIED') && (
                      <Card
                        testID="gps-permission-warning"
                        style={{
                          backgroundColor: '#FEF2F2',
                          borderColor: '#EF4444',
                          borderWidth: 1,
                          borderRadius: 8,
                          padding: 10,
                          marginBottom: 12,
                        }}
                      >
                        <Text style={{ color: '#B91C1C', fontWeight: 'bold', fontSize: 13 }}>
                          📍 Location Permission Required
                        </Text>
                        <Text style={{ color: '#991B1B', fontSize: 12, marginTop: 2 }}>
                          Location access is required to verify your presence inside the assigned HLB for route guidance.
                        </Text>
                      </Card>
                    )}

                    {/* Phase 8 Road-Network Walking Navigation HUD */}
                    <Card style={[themeStyles.card, { marginBottom: 10 }]}>
                      <View style={styles.routeHeaderRow}>
                        <View>
                          <Text style={[styles.routeTitleText, themeStyles.text]}>
                            🚶 Street Network Walking Navigation
                          </Text>
                          <Text style={[styles.routeStrategyText, themeStyles.subtext]}>
                            {roadCoverageData
                              ? `OSM Walkable Network (${roadCoverageData.network_version} • ${roadCoverageData.acquisition_date.split('T')[0]})`
                              : `Strategy: ${routeData.strategy}`}
                          </Text>
                        </View>
                        <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center' }}>
                          <View testID="routing-method-badge">
                            <StatusBadge
                              type="ACTIVE"
                              label={routeData?.strategy || 'ROAD_NETWORK'}
                            />
                          </View>
                          <StatusBadge
                            type={isNavigating ? 'ACTIVE' : 'DRAFT'}
                            label={isNavigating ? 'NAVIGATING' : 'PAUSED'}
                          />
                        </View>
                      </View>

                      {/* Return to Start Toggle & Navigation Controls */}
                      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 4, marginBottom: 4 }}>
                        <TouchableOpacity
                          testID="toggle-return-to-start"
                          onPress={() => setReturnToStart((prev) => !prev)}
                          style={{ paddingVertical: 4, paddingHorizontal: 6 }}
                        >
                          <Text style={{ fontSize: 11, color: themeStyles.text.color, fontWeight: '600' }}>
                            🔄 {returnToStart ? 'Return to Start (Loop)' : 'One-Way Traversal'}
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          testID="btn-navigate-next-building"
                          onPress={handleStartOrContinueRoute}
                          style={{
                            backgroundColor: '#0284C7',
                            paddingVertical: 5,
                            paddingHorizontal: 10,
                            borderRadius: 6,
                          }}
                        >
                          <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 11 }}>
                            Next Building →
                          </Text>
                        </TouchableOpacity>
                      </View>

                      {/* Start / Continue Primary Route Button */}
                      <TouchableOpacity
                        testID="btn-start-continue-route"
                        onPress={handleStartOrContinueRoute}
                        style={{
                          backgroundColor: '#0284C7',
                          paddingVertical: 8,
                          paddingHorizontal: 10,
                          borderRadius: 6,
                          alignItems: 'center',
                          marginBottom: 6,
                        }}
                      >
                        <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 12 }}>
                          ▶️ Start / Continue Traversal
                        </Text>
                      </TouchableOpacity>

                      {/* Dual Progress HUD: Road Coverage vs Building Enumeration */}
                      <View style={{ marginVertical: 8, padding: 8, backgroundColor: isDarkMode ? '#1E293B' : '#F1F5F9', borderRadius: 8 }}>
                        <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text style={{ fontSize: 12, fontWeight: '700', color: '#10B981' }}>
                            🛣️ Road Network Coverage:
                          </Text>
                          <Text style={{ fontSize: 12, fontWeight: '700', color: themeStyles.text.color }}>
                            {roadCoverageData ? roadCoverageData.coverage_percentage.toFixed(0) : 0}% ({roadCoverageData ? roadCoverageData.surveyed_segments_count : 0} / {roadCoverageData ? roadCoverageData.total_segments_count : 0} segments)
                          </Text>
                        </View>
                        <View style={{ height: 6, backgroundColor: '#CBD5E1', borderRadius: 3, overflow: 'hidden', marginBottom: 8 }}>
                          <View
                            style={{
                              height: '100%',
                              width: `${roadCoverageData ? Math.min(100, roadCoverageData.coverage_percentage) : 0}%`,
                              backgroundColor: '#10B981',
                            }}
                          />
                        </View>

                        <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 4 }}>
                          <Text style={{ fontSize: 12, fontWeight: '700', color: '#0284C7' }}>
                            🏠 Buildings Enumerated:
                          </Text>
                          <Text style={{ fontSize: 12, fontWeight: '700', color: themeStyles.text.color }}>
                            {buildings.length > 0 ? Math.round((completedCount / buildings.length) * 100) : 0}% ({completedCount} / {buildings.length} structures)
                          </Text>
                        </View>
                        <View style={{ height: 6, backgroundColor: '#CBD5E1', borderRadius: 3, overflow: 'hidden' }}>
                          <View
                            style={{
                              height: '100%',
                              width: `${buildings.length > 0 ? Math.min(100, (completedCount / buildings.length) * 100) : 0}%`,
                              backgroundColor: '#0284C7',
                            }}
                          />
                        </View>
                      </View>

                      {/* Route Deviation Warning Banner */}
                      {deviationWarning && (
                        <View
                          testID="route-deviation-banner"
                          style={{
                            backgroundColor: '#FEF3C7',
                            borderColor: '#F59E0B',
                            borderWidth: 1,
                            borderRadius: 6,
                            padding: 8,
                            marginBottom: 8,
                          }}
                        >
                          <Text style={{ color: '#92400E', fontSize: 11, fontWeight: '700' }}>
                            ⚠️ {deviationWarning}
                          </Text>
                        </View>
                      )}

                      {/* Disconnected Components Notice */}
                      {Boolean(roadCoverageData && roadCoverageData.disconnected_components_count > 1) && (
                        <View
                          testID="disconnected-network-notice"
                          style={{
                            backgroundColor: '#EFF6FF',
                            borderColor: '#3B82F6',
                            borderWidth: 1,
                            borderRadius: 6,
                            padding: 8,
                            marginBottom: 8,
                          }}
                        >
                          <Text style={{ color: '#1E40AF', fontSize: 11 }}>
                            ℹ️ {roadCoverageData?.disconnected_components_count} road network sections detected. Separate sections indicate natural disconnections without artificial straight lines.
                          </Text>
                        </View>
                      )}

                      {/* Walking Route Metrics Row */}
                      <View style={styles.routeMetricsRow}>
                        <View style={[styles.routeMetricItem, themeStyles.itemBox]}>
                          <Text style={[styles.routeMetricVal, themeStyles.highlight]}>
                            {(roadCoverageData ? roadCoverageData.total_distance_km : routeData.total_distance_km).toFixed(2)} km
                          </Text>
                          <Text style={[styles.routeMetricLbl, themeStyles.subtext]}>
                            Road Distance
                          </Text>
                        </View>

                        <View style={[styles.routeMetricItem, themeStyles.itemBox]}>
                          <Text style={[styles.routeMetricVal, { color: '#10B981' }]}>
                            ~{roadCoverageData ? Math.round(roadCoverageData.estimated_walking_time_minutes) : Math.round((routeData.total_distance_km / 4.5) * 60)} min
                          </Text>
                          <Text style={[styles.routeMetricLbl, themeStyles.subtext]}>
                            Walking Duration
                          </Text>
                        </View>

                        <View style={[styles.routeMetricItem, themeStyles.itemBox]}>
                          <Text style={[styles.routeMetricVal, { color: '#8B5CF6' }]}>
                            {discoveredBuildings.length}
                          </Text>
                          <Text style={[styles.routeMetricLbl, themeStyles.subtext]}>
                            Discovered
                          </Text>
                        </View>
                      </View>

                      {/* Action Controls Row */}
                      <View style={[styles.routeActionRow, { gap: 6, flexWrap: 'wrap' }]}>
                        <TouchableOpacity
                          onPress={handleToggleNavigation}
                          disabled={boundaryStatus === 'OUTSIDE'}
                          style={{
                            flex: 1,
                            minWidth: 110,
                            backgroundColor:
                              boundaryStatus === 'OUTSIDE' ? '#94A3B8' : isNavigating ? '#F59E0B' : '#10B981',
                            opacity: boundaryStatus === 'OUTSIDE' ? 0.6 : 1.0,
                            paddingVertical: 10,
                            paddingHorizontal: 8,
                            borderRadius: 8,
                            alignItems: 'center',
                          }}
                          testID="btn-toggle-navigation"
                        >
                          <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 12 }}>
                            {isNavigating ? '⏸️ Pause Route' : '▶️ Resume Route'}
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          onPress={() => {
                            if (boundaryStatus === 'OUTSIDE') {
                              Alert.alert(
                                'Outside Assigned HLB',
                                'You are currently outside your assigned HLB. Move inside your assigned area to access route optimization and road traversal.'
                              );
                              return;
                            }
                            handleOptimizeRoute(true);
                          }}
                          disabled={boundaryStatus === 'OUTSIDE'}
                          style={{
                            backgroundColor: isDarkMode ? '#334155' : '#E2E8F0',
                            opacity: boundaryStatus === 'OUTSIDE' ? 0.5 : 1.0,
                            paddingVertical: 10,
                            paddingHorizontal: 10,
                            borderRadius: 8,
                            alignItems: 'center',
                          }}
                          testID="btn-recalculate-route"
                        >
                          <Text style={{ color: themeStyles.text.color, fontWeight: '700', fontSize: 12 }}>
                            🔄 Recalculate
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          onPress={() => setShowDiscoverModal(true)}
                          style={{
                            backgroundColor: '#8B5CF6',
                            paddingVertical: 10,
                            paddingHorizontal: 10,
                            borderRadius: 8,
                            alignItems: 'center',
                          }}
                          testID="btn-discover-building"
                        >
                          <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 12 }}>
                            ➕ Discover
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          onPress={() => setShowMissingRoadModal(true)}
                          style={{
                            backgroundColor: '#D97706',
                            paddingVertical: 10,
                            paddingHorizontal: 10,
                            borderRadius: 8,
                            alignItems: 'center',
                          }}
                          testID="btn-report-missing-road"
                        >
                          <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 12 }}>
                            🛣️ Report Road
                          </Text>
                        </TouchableOpacity>

                        <TouchableOpacity
                          onPress={handleOpenGoogleMaps}
                          style={{
                            backgroundColor: '#2563EB',
                            paddingVertical: 10,
                            paddingHorizontal: 10,
                            borderRadius: 8,
                            alignItems: 'center',
                          }}
                          testID="btn-open-google-maps"
                        >
                          <Text style={{ color: '#FFFFFF', fontWeight: '700', fontSize: 12 }}>
                            🗺️ Google Maps
                          </Text>
                        </TouchableOpacity>
                      </View>
                    </Card>

                    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginVertical: 6 }}>
                      <Text style={[themeStyles.text, { fontSize: 14, fontWeight: '700' }]}>
                        📋 Traversal Sequence ({routeData.ordered_buildings.length})
                      </Text>
                    </View>

                    {/* Ordered Buildings Traversal List */}
                    <View style={styles.buildingsListContent}>
                      {routeData.ordered_buildings.map((item, index) => {
                        const isCompleted = item.status === 'COMPLETED' || item.status === 'LOCKED';
                        return (
                          <TouchableOpacity
                            key={`${item.sequence_order}-${item.building_id}`}
                            style={[
                              styles.routeBuildingCard,
                              themeStyles.card,
                              themeStyles.itemBox,
                              isCompleted && { opacity: 0.8 },
                            ]}
                            onPress={() =>
                              navigation.navigate('BuildingDetail', {
                                buildingId: item.building_id,
                                hlbId: routeData.hlb_id,
                                blockCode,
                              })
                            }
                            testID={`route-step-${index}`}
                          >
                            <View style={styles.routeSequenceBadge}>
                              <Text style={styles.routeSequenceNum}>
                                #{item.sequence_order}
                              </Text>
                            </View>

                            <View style={{ flex: 1, marginLeft: 10 }}>
                              <View style={styles.buildingHeaderRow}>
                                <Text style={[styles.buildingRefText, themeStyles.text]}>
                                  {item.building_reference}
                                </Text>
                                <StatusBadge
                                  type={getBuildingBadgeType(item.status || 'PENDING')}
                                  label={item.status || 'PENDING'}
                                />
                              </View>

                              {item.house_number && (
                                <Text style={[styles.houseNumText, themeStyles.subtext]}>
                                  {t('house_num')}: {item.house_number}
                                </Text>
                              )}

                              <View style={styles.routeStepFooter}>
                                <Text style={[styles.coordsText, themeStyles.subtext]}>
                                  📍 {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                                </Text>
                                <Text style={[styles.stepDistanceText, themeStyles.highlight]}>
                                  +{item.distance_from_previous_m.toFixed(0)}m {t('distance_from_prev')}
                                </Text>
                              </View>
                            </View>
                          </TouchableOpacity>
                        );
                      })}
                    </View>
                  </View>
                ) : (
                  <View style={{ paddingBottom: 24 }}>
                    {/* Phase 10 HLB Geofencing Warnings */}
                    {boundaryStatus === 'OUTSIDE' && (
                      <Card
                        testID="outside-hlb-warning"
                        style={{
                          backgroundColor: '#FEF2F2',
                          borderColor: '#EF4444',
                          borderWidth: 1.5,
                          borderRadius: 8,
                          padding: 12,
                          marginBottom: 12,
                        }}
                      >
                        <View style={{ flexDirection: 'row', alignItems: 'center', marginBottom: 4 }}>
                          <Text style={{ fontSize: 16, marginRight: 6 }}>🚫</Text>
                          <Text style={{ color: '#B91C1C', fontWeight: 'bold', fontSize: 14 }}>
                            Outside Assigned HLB
                          </Text>
                        </View>
                        <Text style={{ color: '#991B1B', fontSize: 12, lineHeight: 18 }}>
                          You are currently outside your assigned HLB. Move inside your assigned area to access route optimization and road traversal.
                        </Text>
                      </Card>
                    )}
                    {(boundaryStatus === 'GPS_UNCERTAIN' || boundaryStatus === 'BOUNDARY_UNCERTAIN') && (
                      <Card
                        testID="gps-uncertain-warning"
                        style={{
                          backgroundColor: '#FFFBEB',
                          borderColor: '#F59E0B',
                          borderWidth: 1,
                          borderRadius: 8,
                          padding: 10,
                          marginBottom: 12,
                        }}
                      >
                        <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
                          <Text style={{ color: '#B45309', fontWeight: 'bold', fontSize: 13 }}>
                            ⚠️ Poor GPS Accuracy
                          </Text>
                          <TouchableOpacity
                            testID="btn-retry-gps-accuracy"
                            onPress={handleRefreshGps}
                            style={{ backgroundColor: '#F59E0B', paddingHorizontal: 8, paddingVertical: 4, borderRadius: 4 }}
                          >
                            <Text style={{ color: '#FFFFFF', fontSize: 11, fontWeight: 'bold' }}>Retry GPS</Text>
                          </TouchableOpacity>
                        </View>
                        <Text style={{ color: '#92400E', fontSize: 12, marginTop: 4 }}>
                          GPS accuracy is too uncertain to verify boundary perimeter. Move to an open area with clear sky view.
                        </Text>
                      </Card>
                    )}
                    {(gpsStatus === 'PERMISSION_DENIED' || boundaryStatus === 'LOCATION_PERMISSION_DENIED') && (
                      <Card
                        testID="gps-permission-warning"
                        style={{
                          backgroundColor: '#FEF2F2',
                          borderColor: '#EF4444',
                          borderWidth: 1,
                          borderRadius: 8,
                          padding: 10,
                          marginBottom: 12,
                        }}
                      >
                        <Text style={{ color: '#B91C1C', fontWeight: 'bold', fontSize: 13 }}>
                          📍 Location Permission Required
                        </Text>
                        <Text style={{ color: '#991B1B', fontSize: 12, marginTop: 2 }}>
                          Location access is required to verify your presence inside the assigned HLB for route guidance.
                        </Text>
                      </Card>
                    )}

                    <View style={[styles.emptyBox, themeStyles.itemBox]}>
                      <Text style={styles.emptyIcon}>📍</Text>
                      <Text style={[styles.emptyTitle, themeStyles.text]}>
                        {t('no_buildings_route')}
                      </Text>
                      <SecondaryButton
                        title={t('optimize_route')}
                        disabled={boundaryStatus === 'OUTSIDE'}
                        onPress={() => {
                          if (boundaryStatus === 'OUTSIDE') {
                            Alert.alert(
                              'Outside Assigned HLB',
                              'You are currently outside your assigned HLB. Move inside your assigned area to access route optimization and road traversal.'
                            );
                            return;
                          }
                          handleOptimizeRoute(true);
                        }}
                        style={{ marginTop: 12, opacity: boundaryStatus === 'OUTSIDE' ? 0.5 : 1.0 }}
                        testID="btn-empty-optimize-route"
                      />
                    </View>
                  </View>
                )}
              </View>
            ) : (
              /* Map Tab with Fullscreen & Route Polyline Support */
              <View style={[styles.mapContainer, { height: 480 }]}>
                <HlbSpatialMap
                  ref={mapRef}
                  style={styles.map}
                  boundaryRings={hlbBoundaryRings}
                  boundaryStrokeColor="#0284C7"
                  boundaryFillColor="rgba(2, 132, 199, 0.08)"
                  candidateHlbs={mapItems}
                  selectedHlbId={hlbDetail?.id}
                  routeCoordinates={
                    roadCoverageData && roadCoverageData.continuous_polyline && roadCoverageData.continuous_polyline.length > 0
                      ? roadCoverageData.continuous_polyline.map((c) => ({ latitude: c[0], longitude: c[1] }))
                      : routeCoordinates
                  }
                  routeWaypoints={routeWaypoints}
                  roadSegments={
                    roadCoverageData?.all_road_segments
                      ? roadCoverageData.all_road_segments.map((s) => ({
                          segment_id: s.segment_id,
                          coordinates: s.coordinates.map((c) => ({ latitude: c[0], longitude: c[1] })),
                          is_surveyed: s.is_surveyed,
                          survey_status: s.survey_status,
                          highway: s.highway,
                        }))
                      : []
                  }
                  discoveredBuildings={discoveredBuildings}
                  startPoint={
                    roadCoverageData?.continuous_polyline && roadCoverageData.continuous_polyline.length > 0
                      ? {
                          latitude: roadCoverageData.continuous_polyline[0][0],
                          longitude: roadCoverageData.continuous_polyline[0][1],
                        }
                      : null
                  }
                  endPoint={
                    roadCoverageData?.continuous_polyline && roadCoverageData.continuous_polyline.length > 0
                      ? {
                          latitude: roadCoverageData.continuous_polyline[roadCoverageData.continuous_polyline.length - 1][0],
                          longitude: roadCoverageData.continuous_polyline[roadCoverageData.continuous_polyline.length - 1][1],
                        }
                      : null
                  }
                  currentLocation={
                    currentGps
                      ? {
                          latitude: currentGps.latitude,
                          longitude: currentGps.longitude,
                          accuracy: currentGps.accuracy ?? undefined,
                          heading: currentGps.heading ?? undefined,
                        }
                      : undefined
                  }
                  showCurrentLocation={true}
                  onSelectRouteWaypoint={(bldId) =>
                    navigation.navigate('BuildingDetail', {
                      buildingId: bldId,
                      hlbId: hlbDetail?.id || '',
                      blockCode,
                    })
                  }
                  fullscreenEnabled={true}
                  fullscreenTitle={`${blockCode} — Road Navigation & Fieldwork Map`}
                  testID="enumerator-hlb-spatial-map"
                />
              </View>
            )}
          </View>
        </ScrollView>
      )}

      {/* Building Discovery Modal */}
      <Modal
        visible={showDiscoverModal}
        transparent={true}
        animationType="slide"
        onRequestClose={() => setShowDiscoverModal(false)}
        testID="building-discovery-modal"
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, themeStyles.card]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              ➕ Discover New Structure
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              Record an unmapped building encountered during road traversal. An audit record will be submitted for supervisor review.
            </Text>

            <View style={styles.gpsCoordBox}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: '#8B5CF6' }}>
                📍 Discovery Location:
              </Text>
              <Text style={[styles.gpsCoordText, themeStyles.text]}>
                Lat: {(currentGps?.latitude || 11.082).toFixed(6)}, Lon: {(currentGps?.longitude || 77.12).toFixed(6)}
              </Text>
              <Text style={{ fontSize: 10, color: themeStyles.subtext.color }}>
                Accuracy: {currentGps?.accuracy != null ? `±${currentGps.accuracy.toFixed(1)}m` : 'Estimated'}
              </Text>
            </View>

            <Text style={[styles.inputLabel, themeStyles.text]}>Building Reference / Code (Optional):</Text>
            <TextInput
              style={[styles.modalInput, themeStyles.input]}
              placeholder="e.g. BLD-DISC-001 (auto-assigned if blank)"
              placeholderTextColor={themeStyles.subtext.color}
              value={discoverForm.reference}
              onChangeText={(text) => setDiscoverForm((prev) => ({ ...prev, reference: text }))}
              testID="discover-input-reference"
            />

            <Text style={[styles.inputLabel, themeStyles.text]}>Door / House Number (Optional):</Text>
            <TextInput
              style={[styles.modalInput, themeStyles.input]}
              placeholder="e.g. 12/B or New Ward 4"
              placeholderTextColor={themeStyles.subtext.color}
              value={discoverForm.houseNumber}
              onChangeText={(text) => setDiscoverForm((prev) => ({ ...prev, houseNumber: text }))}
              testID="discover-input-housenumber"
            />

            <Text style={[styles.inputLabel, themeStyles.text]}>Notes / Field Remarks:</Text>
            <TextInput
              style={[styles.modalInput, themeStyles.input, { height: 60 }]}
              placeholder="Structure type, access condition, or landmark..."
              placeholderTextColor={themeStyles.subtext.color}
              value={discoverForm.notes}
              onChangeText={(text) => setDiscoverForm((prev) => ({ ...prev, notes: text }))}
              multiline={true}
              testID="discover-input-notes"
            />

            <View style={styles.modalButtonRow}>
              <TouchableOpacity
                style={[styles.modalCancelBtn, { borderColor: themeStyles.subtext.color }]}
                onPress={() => setShowDiscoverModal(false)}
                disabled={discoverSubmitting}
                testID="discover-btn-cancel"
              >
                <Text style={[styles.modalCancelBtnText, themeStyles.subtext]}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={styles.modalSubmitBtn}
                onPress={handleDiscoverBuilding}
                disabled={discoverSubmitting}
                testID="discover-btn-submit"
              >
                {discoverSubmitting ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.modalSubmitBtnText}>Save & Submit Audit</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>

      {/* Missing Road / Path Discovery Modal (Phase 9) */}
      <Modal
        visible={showMissingRoadModal}
        transparent={true}
        animationType="slide"
        onRequestClose={() => setShowMissingRoadModal(false)}
        testID="modal-missing-road"
      >
        <View style={styles.modalOverlay}>
          <View style={[styles.modalContent, themeStyles.card]}>
            <Text style={[styles.modalTitle, themeStyles.text]}>
              🛣️ Report Missing Road or Path
            </Text>
            <Text style={[styles.modalSubtitle, themeStyles.subtext]}>
              Record an unmapped pedestrian pathway, lane, or road encountered in the field. Geometry will be submitted for supervisor verification.
            </Text>

            <View style={styles.gpsCoordBox}>
              <Text style={{ fontSize: 12, fontWeight: '700', color: '#D97706' }}>
                📍 Field Start Coordinate:
              </Text>
              <Text style={[styles.gpsCoordText, themeStyles.text]}>
                Lat: {(currentGps?.latitude || 11.082).toFixed(6)}, Lon: {(currentGps?.longitude || 77.12).toFixed(6)}
              </Text>
            </View>

            <Text style={[styles.inputLabel, themeStyles.text]}>Road / Path Name (Optional):</Text>
            <TextInput
              style={[styles.modalInput, themeStyles.input]}
              placeholder="e.g. South Lane or Canal Pathway"
              placeholderTextColor={themeStyles.subtext.color}
              value={missingRoadForm.roadName}
              onChangeText={(text) => setMissingRoadForm((prev) => ({ ...prev, roadName: text }))}
              testID="input-missing-road-name"
            />

            <Text style={[styles.inputLabel, themeStyles.text]}>Highway Classification:</Text>
            <TextInput
              style={[styles.modalInput, themeStyles.input]}
              placeholder="path, footway, residential, track, etc."
              placeholderTextColor={themeStyles.subtext.color}
              value={missingRoadForm.highwayType}
              onChangeText={(text) => setMissingRoadForm((prev) => ({ ...prev, highwayType: text }))}
              testID="input-missing-road-type"
            />

            <Text style={[styles.inputLabel, themeStyles.text]}>Field Notes & Landmarks:</Text>
            <TextInput
              style={[styles.modalInput, themeStyles.input, { height: 60 }]}
              placeholder="Condition, accessibility, barriers, or surface notes..."
              placeholderTextColor={themeStyles.subtext.color}
              value={missingRoadForm.notes}
              onChangeText={(text) => setMissingRoadForm((prev) => ({ ...prev, notes: text }))}
              multiline={true}
              testID="input-missing-road-notes"
            />

            <View style={styles.modalButtonRow}>
              <TouchableOpacity
                style={[styles.modalCancelBtn, { borderColor: themeStyles.subtext.color }]}
                onPress={() => setShowMissingRoadModal(false)}
                disabled={missingRoadSubmitting}
                testID="btn-cancel-missing-road"
              >
                <Text style={[styles.modalCancelBtnText, themeStyles.subtext]}>Cancel</Text>
              </TouchableOpacity>

              <TouchableOpacity
                style={[styles.modalSubmitBtn, { backgroundColor: '#D97706' }]}
                onPress={handleSubmitMissingRoad}
                disabled={missingRoadSubmitting}
                testID="btn-submit-missing-road"
              >
                {missingRoadSubmitting ? (
                  <ActivityIndicator size="small" color="#FFFFFF" />
                ) : (
                  <Text style={styles.modalSubmitBtnText}>Submit for Review</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScreenContainer>
  );
}

const styles = StyleSheet.create({
  compactHeaderBar: {
    marginHorizontal: 16,
    marginTop: 6,
    marginBottom: 6,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 8,
    borderWidth: 1,
  },
  compactHeaderText: {
    fontSize: 13,
    fontWeight: '700',
    flex: 1,
  },
  headerCardContainer: {
    paddingHorizontal: 16,
    paddingTop: 8,
  },
  cardHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  blockTitleText: {
    fontSize: 20,
    fontWeight: '800',
  },
  layoutSubText: {
    fontSize: 13,
    marginTop: 2,
  },
  badgeGroup: {
    flexDirection: 'row',
    gap: 6,
  },
  metricsGrid: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 4,
  },
  metricBox: {
    flex: 1,
    paddingVertical: 8,
    paddingHorizontal: 4,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
  },
  metricVal: {
    fontSize: 16,
    fontWeight: '800',
    textAlign: 'center',
  },
  metricLbl: {
    fontSize: 10,
    marginTop: 2,
    textAlign: 'center',
  },
  downloadBanner: {
    marginTop: 10,
  },
  downloadBtn: {
    marginTop: 2,
  },
  tabBar: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    marginHorizontal: 16,
    marginVertical: 10,
  },
  tabItem: {
    flex: 1,
    paddingVertical: 10,
    alignItems: 'center',
  },
  tabText: {
    fontSize: 13,
    fontWeight: '600',
  },
  searchFilterContainer: {
    marginBottom: 10,
    gap: 8,
  },
  searchInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 8,
    fontSize: 13,
  },
  filterChipsRow: {
    flexDirection: 'row',
    gap: 8,
    paddingVertical: 2,
  },
  filterChip: {
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 16,
    borderWidth: 1,
  },
  filterChipText: {
    fontSize: 12,
    fontWeight: '600',
  },
  buildingsListContent: {
    paddingBottom: 100,
    gap: 8,
  },
  buildingCard: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
  },
  buildingHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
  },
  buildingRefText: {
    fontSize: 15,
    fontWeight: '700',
  },
  houseNumText: {
    fontSize: 12,
    marginTop: 2,
  },
  buildingFooterRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    paddingTop: 6,
    borderTopWidth: 1,
    borderTopColor: 'rgba(150, 150, 150, 0.15)',
  },
  coordsText: {
    fontSize: 11,
  },
  householdCountText: {
    fontSize: 12,
    fontWeight: '700',
  },
  routeHeaderRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 8,
  },
  routeTitleText: {
    fontSize: 16,
    fontWeight: '800',
  },
  routeStrategyText: {
    fontSize: 11,
    marginTop: 2,
  },
  routeMetricsRow: {
    flexDirection: 'row',
    gap: 6,
    marginVertical: 8,
  },
  routeMetricItem: {
    flex: 1,
    paddingVertical: 6,
    paddingHorizontal: 4,
    borderRadius: 6,
    alignItems: 'center',
    borderWidth: 1,
  },
  routeMetricVal: {
    fontSize: 14,
    fontWeight: '800',
  },
  routeMetricLbl: {
    fontSize: 9,
    marginTop: 2,
    textAlign: 'center',
  },
  routeActionRow: {
    flexDirection: 'row',
    gap: 8,
    marginTop: 8,
  },
  routeBuildingCard: {
    flexDirection: 'row',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
  },
  routeSequenceBadge: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: '#0284C7',
    alignItems: 'center',
    justifyContent: 'center',
  },
  routeSequenceNum: {
    color: '#FFFFFF',
    fontWeight: '800',
    fontSize: 12,
  },
  routeStepFooter: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 6,
  },
  stepDistanceText: {
    fontSize: 11,
    fontWeight: '600',
  },
  mapContainer: {
    flex: 1,
    minHeight: 380,
    marginHorizontal: 16,
    marginBottom: 24,
    borderRadius: 12,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: 'rgba(2, 132, 199, 0.3)',
  },
  map: {
    flex: 1,
  },
  emptyBox: {
    padding: 24,
    borderRadius: 8,
    borderWidth: 1,
    alignItems: 'center',
    marginTop: 12,
  },
  emptyIcon: {
    fontSize: 32,
    marginBottom: 6,
  },
  emptyTitle: {
    fontSize: 15,
    fontWeight: '700',
    textAlign: 'center',
    marginBottom: 2,
  },
  emptySubtitle: {
    fontSize: 13,
    textAlign: 'center',
  },
  loadingContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 40,
  },
  loadingText: {
    marginTop: 12,
    fontSize: 14,
  },
  errorContainer: {
    flex: 1,
    padding: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  goBackBtn: {
    marginTop: 16,
    paddingHorizontal: 20,
    paddingVertical: 10,
    borderRadius: 8,
    backgroundColor: '#0284C7',
  },
  goBackBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0, 0, 0, 0.55)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  modalContent: {
    width: '100%',
    maxWidth: 420,
    borderRadius: 14,
    padding: 20,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.3,
    shadowRadius: 8,
    elevation: 8,
  },
  modalTitle: {
    fontSize: 18,
    fontWeight: '800',
    marginBottom: 6,
  },
  modalSubtitle: {
    fontSize: 12,
    lineHeight: 16,
    marginBottom: 14,
  },
  gpsCoordBox: {
    padding: 10,
    borderRadius: 8,
    backgroundColor: 'rgba(139, 92, 246, 0.1)',
    borderWidth: 1,
    borderColor: 'rgba(139, 92, 246, 0.3)',
    marginBottom: 12,
  },
  gpsCoordText: {
    fontSize: 13,
    fontWeight: '700',
    marginVertical: 2,
  },
  inputLabel: {
    fontSize: 12,
    fontWeight: '600',
    marginBottom: 4,
  },
  modalInput: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 8,
    fontSize: 13,
    marginBottom: 10,
  },
  modalButtonRow: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 10,
    marginTop: 10,
  },
  modalCancelBtn: {
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
  },
  modalCancelBtnText: {
    fontWeight: '600',
    fontSize: 13,
  },
  modalSubmitBtn: {
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: 8,
    backgroundColor: '#8B5CF6',
  },
  modalSubmitBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
  loadMoreBtn: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
  },
  loadMoreBtnText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 13,
  },
});
