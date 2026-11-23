import * as Location from 'expo-location';

export const GPS_ACCURACY_GOOD_THRESHOLD_M = 25;
export const GPS_ACCURACY_POOR_THRESHOLD_M = 75;
export const GPS_ACCURACY_MAX_RELIABLE_THRESHOLD_M = 150;

export type GpsAccuracyCategory = 'GOOD' | 'POOR' | 'UNKNOWN';

export interface GpsPositionResult {
  latitude: number;
  longitude: number;
  accuracy: number | null;
  heading?: number | null;
  timestamp: string;
}

export interface GpsCaptureResponse {
  success: boolean;
  position?: GpsPositionResult;
  error?: 'PERMISSION_DENIED' | 'LOCATION_UNAVAILABLE' | 'TIMEOUT' | 'UNKNOWN';
  errorMessage?: string;
}

let activeSubscription: Location.LocationSubscription | null = null;
let activeListenersCount = 0;

export const gpsService = {
  /**
   * Request GPS foreground permission.
   */
  async requestPermission(): Promise<boolean> {
    try {
      const { status } = await Location.requestForegroundPermissionsAsync();
      return status === 'granted';
    } catch {
      return false;
    }
  },

  /**
   * Check current GPS permission status.
   */
  async checkPermission(): Promise<boolean> {
    try {
      const { status } = await Location.getForegroundPermissionsAsync();
      return status === 'granted';
    } catch {
      return false;
    }
  },

  /**
   * Categorize horizontal GPS accuracy into clear operational tiers.
   * GOOD (<= 25m), POOR (> 25m), UNKNOWN (unavailable/null).
   */
  categorizeAccuracy(accuracy: number | null): GpsAccuracyCategory {
    if (accuracy === null || accuracy === undefined || isNaN(accuracy) || accuracy < 0) {
      return 'UNKNOWN';
    }
    if (accuracy <= GPS_ACCURACY_GOOD_THRESHOLD_M) {
      return 'GOOD';
    }
    return 'POOR';
  },

  /**
   * Capture honest device GPS coordinates.
   * Returns error states gracefully without crashing or fabricating fake coordinates.
   */
  async getCurrentLocation(): Promise<GpsCaptureResponse> {
    try {
      const hasPermission = await this.requestPermission();
      if (!hasPermission) {
        return {
          success: false,
          error: 'PERMISSION_DENIED',
          errorMessage: 'Location permission was denied',
        };
      }

      const isEnabled = await Location.hasServicesEnabledAsync();
      if (!isEnabled) {
        return {
          success: false,
          error: 'LOCATION_UNAVAILABLE',
          errorMessage: 'Location services are disabled on this device',
        };
      }

      const location = await Location.getCurrentPositionAsync({
        accuracy: Location.Accuracy.Balanced,
      });

      return {
        success: true,
        position: {
          latitude: location.coords.latitude,
          longitude: location.coords.longitude,
          accuracy: location.coords.accuracy || null,
          heading: location.coords.heading ?? null,
          timestamp: new Date(location.timestamp).toISOString(),
        },
      };
    } catch (err: any) {
      return {
        success: false,
        error: 'LOCATION_UNAVAILABLE',
        errorMessage: err?.message || 'Failed to obtain current GPS location',
      };
    }
  },

  /**
   * Start watching device location with balanced accuracy and battery-conservative update frequency.
   * Automatically replaces any active watcher to prevent duplicate listeners.
   * Returns an unsubscribe cleanup callback.
   */
  async watchPosition(
    onLocation: (pos: GpsPositionResult) => void,
    onError?: (err: any) => void
  ): Promise<() => void> {
    const hasPermission = await this.requestPermission();
    if (!hasPermission) {
      onError?.({
        error: 'PERMISSION_DENIED',
        message: 'Location permission was denied',
      });
      return () => {};
    }

    const isEnabled = await Location.hasServicesEnabledAsync();
    if (!isEnabled) {
      onError?.({
        error: 'LOCATION_UNAVAILABLE',
        message: 'Location services are disabled on this device',
      });
      return () => {};
    }

    // Clean up any existing subscription to ensure single active watcher
    this.stopWatching();

    try {
      activeSubscription = await Location.watchPositionAsync(
        {
          accuracy: Location.Accuracy.Balanced,
          timeInterval: 8000, // 8-second interval
          distanceInterval: 10, // 10-meter movement threshold
        },
        (loc) => {
          onLocation({
            latitude: loc.coords.latitude,
            longitude: loc.coords.longitude,
            accuracy: loc.coords.accuracy || null,
            heading: loc.coords.heading ?? null,
            timestamp: new Date(loc.timestamp).toISOString(),
          });
        }
      );
      activeListenersCount = 1;
    } catch (err: any) {
      onError?.(err);
      return () => {};
    }

    return () => {
      this.stopWatching();
    };
  },

  /**
   * Stop active GPS watching and release device listeners.
   */
  stopWatching(): void {
    if (activeSubscription) {
      activeSubscription.remove();
      activeSubscription = null;
      activeListenersCount = 0;
    }
  },

  /**
   * Start watching alias for watchPosition.
   */
  startWatching(
    onLocation: (pos: GpsPositionResult) => void,
    onError?: (err: any) => void
  ): Promise<() => void> {
    return this.watchPosition(onLocation, onError);
  },

  /**
   * Check whether GPS watcher is currently running.
   */
  isWatching(): boolean {
    return activeSubscription !== null;
  },

  /**
   * Get active listener count (guaranteed <= 1 to avoid duplicate listeners).
   */
  getActiveListenersCount(): number {
    return activeListenersCount;
  },
};
