import React, { useRef, useImperativeHandle, forwardRef, useMemo, useEffect } from 'react';
import { StyleSheet, View, StyleProp, ViewStyle, Platform } from 'react-native';
import { WebView } from 'react-native-webview';

const WebViewComponent = WebView as any;

export interface LatLng {
  latitude: number;
  longitude: number;
}

export interface MapBuilding {
  id: string;
  ref: string;
  house_number?: string | null;
  latitude: number;
  longitude: number;
  source_type?: string;
  detection_confidence?: number | null;
  imagery_source?: string | null;
  area_in_meters?: number | null;
  footprintRings?: LatLng[][];
}

export interface MapHlb {
  id: string;
  block_code: string;
  boundary: any;
  centroid?: any;
  building_count?: number;
  actual_building_count?: number;
  quality_score?: number;
  strokeColor?: string;
  fillColor?: string;
}

export interface MapCluster {
  latitude: number;
  longitude: number;
  count: number;
  colorClass: string;
}

export interface InteractiveMapRef {
  zoomIn: () => void;
  zoomOut: () => void;
  fitToCoordinates: (coords: LatLng[], options?: { padding?: number }) => void;
  animateToRegion: (region: { latitude: number; longitude: number; latitudeDelta?: number; longitudeDelta?: number }) => void;
}

export interface InteractiveMapProps {
  testID?: string;
  style?: StyleProp<ViewStyle>;
  initialCenter?: LatLng;
  initialZoom?: number;
  initialRegion?: { latitude: number; longitude: number; latitudeDelta: number; longitudeDelta: number };
  onRegionChangeComplete?: (region: { latitude: number; longitude: number; latitudeDelta: number; longitudeDelta: number }) => void;
  mapLayer?: 'satellite' | 'standard';
  showBoundary?: boolean;
  boundaryRings?: LatLng[][];
  boundaryStrokeColor?: string;
  boundaryFillColor?: string;
  candidateHlbs?: MapHlb[];
  selectedHlbId?: string | null;
  onSelectHlb?: (hlb: MapHlb) => void;
  buildings?: MapBuilding[];
  showBuildings?: boolean;
  selectedBuildingId?: string | null;
  onSelectBuilding?: (building: MapBuilding) => void;
  clusters?: MapCluster[];
  areaName?: string;
  fitCoordinates?: LatLng[];
  children?: React.ReactNode;
}

export const InteractiveMap = forwardRef<InteractiveMapRef, InteractiveMapProps>((props, ref) => {
  const {
    testID = 'interactive-map',
    style,
    initialCenter = { latitude: 11.082, longitude: 77.12 },
    initialZoom = 14,
    initialRegion,
    onRegionChangeComplete,
    mapLayer = 'standard',
    showBoundary = true,
    boundaryRings = [],
    boundaryStrokeColor = '#38BDF8',
    boundaryFillColor = 'rgba(2, 132, 199, 0.22)',
    candidateHlbs = [],
    selectedHlbId = null,
    onSelectHlb,
    buildings = [],
    showBuildings = true,
    selectedBuildingId = null,
    onSelectBuilding,
    clusters = [],
    areaName = '',
    fitCoordinates = [],
    children,
  } = props;

  const webViewRef = useRef<WebView>(null);

  // Imperative ref methods
  useImperativeHandle(ref, () => ({
    zoomIn: () => {
      webViewRef.current?.injectJavaScript('if (window.map) { window.map.zoomIn(); } true;');
    },
    zoomOut: () => {
      webViewRef.current?.injectJavaScript('if (window.map) { window.map.zoomOut(); } true;');
    },
    fitToCoordinates: (coords: LatLng[]) => {
      if (!coords || coords.length === 0) return;
      const boundsStr = JSON.stringify(coords.map((c) => [c.latitude, c.longitude]));
      webViewRef.current?.injectJavaScript(`if (window.map) { window.map.fitBounds(${boundsStr}, { padding: [30, 30] }); } true;`);
    },
    animateToRegion: (region) => {
      webViewRef.current?.injectJavaScript(`if (window.map) { window.map.setView([${region.latitude}, ${region.longitude}], window.map.getZoom(), { animate: true }); } true;`);
    },
  }));

  // Generate payload for the Leaflet WebView
  const mapData = useMemo(() => {
    return {
      center: [initialCenter.latitude, initialCenter.longitude],
      zoom: initialZoom,
      mapLayer,
      showBoundary,
      boundaryRings: boundaryRings.map((ring) => ring.map((c) => [c.latitude, c.longitude])),
      boundaryStrokeColor,
      boundaryFillColor,
      candidateHlbs: candidateHlbs.map((h) => ({
        id: h.id,
        code: h.block_code || (h as any).hlb_code || 'HLB',
        boundary: h.boundary,
        centroid: h.centroid,
        count: h.actual_building_count ?? h.building_count ?? 0,
        score: h.quality_score ?? 0,
        strokeColor: h.strokeColor || '#0284C7',
        fillColor: h.fillColor || 'rgba(2, 132, 199, 0.05)',
        isSelected: h.id === selectedHlbId,
      })),
      selectedHlbId,
      showBuildings,
      buildings: showBuildings
        ? buildings.slice(0, 500).map((b) => ({
            id: b.id,
            ref: b.ref,
            lat: b.latitude,
            lng: b.longitude,
            source: b.imagery_source || (b.source_type === 'SATELLITE_DETECTED' ? 'Google Open Buildings V3' : 'Development Dataset'),
            conf: b.detection_confidence,
            area: b.area_in_meters,
            footprint: b.footprintRings ? b.footprintRings.map((r) => r.map((c) => [c.latitude, c.longitude])) : [],
            isSelected: b.id === selectedBuildingId,
          }))
        : [],
      selectedBuildingId,
      clusters: clusters.map((c) => ({
        lat: c.latitude,
        lng: c.longitude,
        count: c.count,
        color: c.colorClass,
      })),
      areaName,
      fitBounds: fitCoordinates.length > 0 ? fitCoordinates.map((c) => [c.latitude, c.longitude]) : null,
    };
  }, [
    initialCenter,
    initialZoom,
    mapLayer,
    showBoundary,
    boundaryRings,
    boundaryStrokeColor,
    boundaryFillColor,
    candidateHlbs,
    selectedHlbId,
    showBuildings,
    buildings,
    selectedBuildingId,
    clusters,
    areaName,
    fitCoordinates,
  ]);

  // Update map data inside WebView dynamically
  useEffect(() => {
    const dataStr = JSON.stringify(mapData);
    webViewRef.current?.injectJavaScript(`if (window.updateMapData) { window.updateMapData(${dataStr}); } true;`);
  }, [mapData]);

  // Handle messages from WebView
  const handleMessage = (event: any) => {
    try {
      const data = JSON.parse(event.nativeEvent.data);
      if (data.type === 'SELECT_HLB' && onSelectHlb) {
        const found = candidateHlbs.find((h) => h.id === data.id);
        if (found) onSelectHlb(found);
      } else if (data.type === 'SELECT_BUILDING' && onSelectBuilding) {
        const found = buildings.find((b) => b.id === data.id);
        if (found) onSelectBuilding(found);
      }
    } catch {
      // Ignore parse errors
    }
  };

  const htmlContent = useMemo(() => {
    const initialDataJson = JSON.stringify(mapData);
    return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <style>
    * { box-sizing: border-box; }
    html, body, #map { margin: 0; padding: 0; width: 100%; height: 100%; background: #0F172A; }
    .leaflet-control-attribution { display: none !important; }
    .leaflet-container { background: #0F172A !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    
    .hlb-marker-badge {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 3px 8px;
      border-radius: 8px;
      color: #FFFFFF;
      font-weight: 800;
      font-size: 11px;
      border: 1.5px solid #FFFFFF;
      box-shadow: 0 3px 8px rgba(0,0,0,0.6);
      white-space: nowrap;
      cursor: pointer;
    }
    .hlb-marker-badge .bld-count {
      font-size: 9px;
      font-weight: 600;
      opacity: 0.95;
    }

    .bld-pin {
      width: 22px;
      height: 22px;
      border-radius: 6px;
      background: #0284C7;
      border: 1.5px solid #FFFFFF;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 11px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.5);
      cursor: pointer;
    }

    .cluster-pin {
      border-radius: 50%;
      color: #FFFFFF;
      font-weight: 800;
      font-size: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 2px solid #FFFFFF;
      box-shadow: 0 3px 10px rgba(0,0,0,0.6);
      cursor: pointer;
    }

    .area-badge {
      background: rgba(15, 23, 42, 0.92);
      border: 1.5px solid #38BDF8;
      border-radius: 14px;
      padding: 5px 12px;
      color: #FFFFFF;
      font-weight: 700;
      font-size: 12px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.5);
      white-space: nowrap;
    }

    .leaflet-popup-content-wrapper {
      background: rgba(15, 23, 42, 0.95) !important;
      color: #FFFFFF !important;
      border-radius: 12px !important;
      border: 1px solid #38BDF8 !important;
      box-shadow: 0 8px 24px rgba(0,0,0,0.6) !important;
      padding: 0 !important;
    }
    .leaflet-popup-content {
      margin: 10px 14px !important;
      line-height: 1.4 !important;
    }
    .leaflet-popup-tip {
      background: rgba(15, 23, 42, 0.95) !important;
    }
    .popup-title {
      font-size: 13px;
      font-weight: 800;
      color: #38BDF8;
      margin-bottom: 4px;
      border-bottom: 1px solid rgba(148, 163, 184, 0.2);
      padding-bottom: 4px;
    }
    .popup-meta {
      font-size: 11px;
      color: #CBD5E1;
    }
    .popup-meta b {
      color: #FFFFFF;
    }
  </style>
</head>
<body>
  <div id="map"></div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    var currentData = ${initialDataJson};
    var map;
    var osmLayer;
    var satelliteLayer;
    var boundaryLayerGroup = L.layerGroup();
    var hlbLayerGroup = L.layerGroup();
    var buildingLayerGroup = L.layerGroup();
    var clusterLayerGroup = L.layerGroup();

    function initMap() {
      var center = currentData.center || [11.082, 77.12];
      var zoom = currentData.zoom || 14;

      map = L.map('map', {
        center: center,
        zoom: zoom,
        zoomControl: false,
        attributionControl: false
      });

      // Standard OpenStreetMap tiles
      osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        subdomains: ['a', 'b', 'c']
      });

      // High-resolution Esri Satellite imagery
      satelliteLayer = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: 19
      });

      if (currentData.mapLayer === 'satellite') {
        satelliteLayer.addTo(map);
      } else {
        osmLayer.addTo(map);
      }

      boundaryLayerGroup.addTo(map);
      hlbLayerGroup.addTo(map);
      buildingLayerGroup.addTo(map);
      clusterLayerGroup.addTo(map);

      renderData(currentData, true);
    }

    function renderData(data, isInitial) {
      // 1. Tile layer toggle
      if (data.mapLayer === 'satellite') {
        if (map.hasLayer(osmLayer)) map.removeLayer(osmLayer);
        if (!map.hasLayer(satelliteLayer)) satelliteLayer.addTo(map);
      } else {
        if (map.hasLayer(satelliteLayer)) map.removeLayer(satelliteLayer);
        if (!map.hasLayer(osmLayer)) osmLayer.addTo(map);
      }

      // 2. Clear previous dynamic layers
      boundaryLayerGroup.clearLayers();
      hlbLayerGroup.clearLayers();
      buildingLayerGroup.clearLayers();
      clusterLayerGroup.clearLayers();

      var allCoords = [];

      // 3. Boundary Polygons
      if (data.showBoundary && data.boundaryRings && data.boundaryRings.length > 0) {
        data.boundaryRings.forEach(function(ring) {
          var poly = L.polygon(ring, {
            color: data.boundaryStrokeColor || '#38BDF8',
            weight: 3,
            fillColor: data.boundaryFillColor || '#0284C7',
            fillOpacity: 0.22
          }).addTo(boundaryLayerGroup);

          ring.forEach(function(c) { allCoords.push(c); });
        });

        if (data.areaName) {
          var bounds = L.latLngBounds(data.boundaryRings[0]);
          var center = bounds.getCenter();
          var areaIcon = L.divIcon({
            className: '',
            html: '<div class="area-badge">📍 ' + data.areaName + '</div>',
            iconSize: [120, 30],
            iconAnchor: [60, 15]
          });
          L.marker(center, { icon: areaIcon }).addTo(boundaryLayerGroup);
        }
      }

      // 4. Candidate HLBs
      if (data.candidateHlbs && data.candidateHlbs.length > 0) {
        data.candidateHlbs.forEach(function(hlb) {
          var isSelected = hlb.isSelected;
          var strokeColor = isSelected ? '#FFFFFF' : hlb.strokeColor;
          var fillColor = isSelected ? '#FFFFFF' : hlb.fillColor;
          var fillOpacity = isSelected ? 0.45 : 0.35;
          var weight = isSelected ? 3.5 : 2;

          if (hlb.boundary && hlb.boundary.coordinates) {
            var rings = [];
            if (hlb.boundary.type === 'Polygon') {
              rings = hlb.boundary.coordinates.map(function(r) {
                return r.map(function(c) { return [c[1], c[0]]; });
              });
            } else if (hlb.boundary.type === 'MultiPolygon') {
              hlb.boundary.coordinates.forEach(function(poly) {
                poly.forEach(function(r) {
                  rings.push(r.map(function(c) { return [c[1], c[0]]; }));
                });
              });
            }

            rings.forEach(function(ring) {
              var poly = L.polygon(ring, {
                color: strokeColor,
                weight: weight,
                fillColor: fillColor,
                fillOpacity: fillOpacity
              }).addTo(hlbLayerGroup);

              poly.on('click', function() {
                if (window.ReactNativeWebView) {
                  window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'SELECT_HLB', id: hlb.id }));
                }
              });

              ring.forEach(function(c) { allCoords.push(c); });
            });

            // HLB Centroid Marker Badge
            var centroidLat, centroidLng;
            if (hlb.centroid && hlb.centroid.coordinates) {
              centroidLat = hlb.centroid.coordinates[1];
              centroidLng = hlb.centroid.coordinates[0];
            } else if (rings.length > 0 && rings[0].length > 0) {
              var b = L.latLngBounds(rings[0]);
              var c = b.getCenter();
              centroidLat = c.lat;
              centroidLng = c.lng;
            }

            if (centroidLat && centroidLng) {
              var badgeHtml = '<div class="hlb-marker-badge" style="background-color:' + hlb.strokeColor + ';">' +
                '<span>' + hlb.code + '</span>' +
                '<span class="bld-count">' + hlb.count + ' bldgs</span>' +
                '</div>';
              var badgeIcon = L.divIcon({
                className: '',
                html: badgeHtml,
                iconSize: [80, 36],
                iconAnchor: [40, 18]
              });

              var m = L.marker([centroidLat, centroidLng], { icon: badgeIcon }).addTo(hlbLayerGroup);
              m.on('click', function() {
                if (window.ReactNativeWebView) {
                  window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'SELECT_HLB', id: hlb.id }));
                }
              });
            }
          }
        });
      }

      // 5. Buildings
      if (data.showBuildings && data.buildings && data.buildings.length > 0) {
        data.buildings.forEach(function(b) {
          // Footprints
          if (b.footprint && b.footprint.length > 0) {
            b.footprint.forEach(function(ring) {
              var p = L.polygon(ring, {
                color: '#38BDF8',
                weight: b.isSelected ? 3 : 1.5,
                fillColor: '#0284C7',
                fillOpacity: b.isSelected ? 0.6 : 0.45
              }).addTo(buildingLayerGroup);

              p.on('click', function() {
                if (window.ReactNativeWebView) {
                  window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'SELECT_BUILDING', id: b.id }));
                }
              });
            });
          }

          // Building Pin
          var pinIcon = L.divIcon({
            className: '',
            html: '<div class="bld-pin">🏢</div>',
            iconSize: [22, 22],
            iconAnchor: [11, 11]
          });
          var bMarker = L.marker([b.lat, b.lng], { icon: pinIcon }).addTo(buildingLayerGroup);
          
          var popupContent = '<div class="popup-title">🏢 Building ' + b.ref + '</div>' +
            '<div class="popup-meta">Source: <b>' + b.source + '</b></div>' +
            '<div class="popup-meta">Confidence: <b>' + (b.conf ? b.conf.toFixed(2) : 'N/A') + '</b></div>' +
            '<div class="popup-meta">Area: <b>' + (b.area ? Math.round(b.area) + ' m²' : 'N/A') + '</b></div>' +
            '<div class="popup-meta">Coordinates: ' + b.lat.toFixed(5) + ', ' + b.lng.toFixed(5) + '</div>';
          bMarker.bindPopup(popupContent);

          bMarker.on('click', function() {
            if (window.ReactNativeWebView) {
              window.ReactNativeWebView.postMessage(JSON.stringify({ type: 'SELECT_BUILDING', id: b.id }));
            }
          });
        });
      }

      // 6. Density Clusters (Medium zoom)
      if (data.clusters && data.clusters.length > 0 && (!data.buildings || data.buildings.length === 0)) {
        data.clusters.forEach(function(c) {
          var clusterIcon = L.divIcon({
            className: '',
            html: '<div class="cluster-pin" style="width:34px;height:34px;background-color:' + c.color + ';">' + c.count + '</div>',
            iconSize: [34, 34],
            iconAnchor: [17, 17]
          });
          var cMarker = L.marker([c.lat, c.lng], { icon: clusterIcon }).addTo(clusterLayerGroup);
          cMarker.on('click', function() {
            map.setView([c.lat, c.lng], map.getZoom() + 2, { animate: true });
          });
        });
      }

      // Initial Fit Bounds
      if (isInitial && allCoords.length > 0) {
        map.fitBounds(L.latLngBounds(allCoords), { padding: [30, 30] });
      }
    }

    window.updateMapData = function(newData) {
      currentData = newData;
      renderData(newData, false);
    };

    window.onload = initMap;
  </script>
</body>
</html>
    `;
  }, []);

  return (
    <View testID={testID} style={[styles.container, style]}>
      <WebViewComponent
        ref={webViewRef}
        testID={`${testID}-webview`}
        style={styles.webview}
        originWhitelist={['*']}
        source={{ html: htmlContent }}
        onMessage={handleMessage}
        javaScriptEnabled={true}
        domStorageEnabled={true}
        startInLoadingState={false}
        scalesPageToFit={true}
        scrollEnabled={false}
      />
      {children}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    width: '100%',
    height: '100%',
    backgroundColor: '#0F172A',
  },
  webview: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    width: '100%',
    height: '100%',
    backgroundColor: '#0F172A',
  },
});
