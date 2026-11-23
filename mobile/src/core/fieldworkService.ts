import { boundaryService } from './boundaryService';
import { enumeratorService } from './enumeratorService';
import { gpsService, GpsCaptureResponse } from './gpsService';
import { calculateAuthoritativeProgress, BuildingProgressInput } from './progressService';
import { initDatabase } from './sqlite/database';
import { offlineRepository } from './sqlite/offlineRepositories';
import { syncQueueRepository } from './sqlite/syncQueueRepository';
import { syncService, SyncBatchResult } from './syncService';
import type {
  OfflineHlbRecord,
  OfflineBuildingRecord,
  OfflineHouseholdRecord,
  OfflineRevisitRecord,
  OfflineGpsLogRecord,
  OfflineCensusHouseRecord,
  OfflinePersonRecord,
  OfflineBuildingEditRecord,
  BuildingFieldStatus,
  FieldworkStats,
  BuildingStatus,
  SyncQueueStats,
  SyncQueueItem,
} from './sqlite/types';

export interface DownloadResult {
  success: boolean;
  totalBuildings?: number;
  error?: string;
}

export const fieldworkService = {
  /**
   * Initialize SQLite database schema and migrations.
   */
  init(): void {
    initDatabase();
  },

  /**
   * Check whether an HLB is available locally in SQLite.
   */
  isHlbDownloaded(hlbId: string, enumeratorId: string): boolean {
    this.init();
    return offlineRepository.isHlbDownloaded(hlbId, enumeratorId);
  },

  /**
   * Download HLB and all associated buildings from the backend into SQLite.
   */
  async downloadHlbForOffline(
    hlbId: string,
    enumeratorId: string
  ): Promise<DownloadResult> {
    this.init();
    try {
      const downloadData = await enumeratorService.downloadAssignedHlb(hlbId);

      // Save to SQLite inside transaction
      offlineRepository.saveDownloadedHlb(
        downloadData.hlb,
        downloadData.buildings,
        enumeratorId
      );

      return {
        success: true,
        totalBuildings: downloadData.total_buildings,
      };
    } catch (err: any) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        'Failed to download HLB for offline fieldwork';
      return {
        success: false,
        error: typeof msg === 'string' ? msg : JSON.stringify(msg),
      };
    }
  },

  /**
   * Get all downloaded HLBs for this enumerator.
   */
  getDownloadedHlbs(enumeratorId: string): OfflineHlbRecord[] {
    this.init();
    return offlineRepository.getOfflineHlbs(enumeratorId);
  },

  /**
   * Get downloaded HLB details from SQLite.
   */
  getOfflineHlb(
    hlbId: string,
    enumeratorId?: string
  ): OfflineHlbRecord | null {
    this.init();
    return offlineRepository.getOfflineHlbById(hlbId, enumeratorId);
  },

  /**
   * Delete downloaded HLB from local storage.
   */
  removeOfflineHlb(hlbId: string): void {
    this.init();
    offlineRepository.deleteOfflineHlb(hlbId);
  },

  /**
   * Get buildings for an HLB from SQLite.
   */
  getBuildings(
    hlbId: string,
    statusFilter?: BuildingStatus | 'ALL',
    searchQuery?: string
  ): OfflineBuildingRecord[] {
    this.init();
    return offlineRepository.getOfflineBuildings(
      hlbId,
      statusFilter,
      searchQuery
    );
  },

  /**
   * Get detail for an individual building including its household records and revisits.
   */
  getBuildingDetail(buildingId: string): {
    building: OfflineBuildingRecord | null;
    households: OfflineHouseholdRecord[];
    revisits: OfflineRevisitRecord[];
  } {
    this.init();
    return offlineRepository.getOfflineBuildingDetail(buildingId);
  },

  /**
   * Save or update a household record in SQLite. Automatically queues sync operation.
   */
  saveHousehold(record: OfflineHouseholdRecord): void {
    this.init();
    offlineRepository.saveHouseholdRecord(record);
  },

  /**
   * Delete a household record from SQLite.
   */
  deleteHousehold(householdId: string, buildingId: string): void {
    this.init();
    offlineRepository.deleteHouseholdRecord(householdId, buildingId);
  },

  /**
   * Save a revisit record in SQLite and mark building as REVISIT_REQUIRED.
   */
  saveRevisit(revisit: OfflineRevisitRecord): void {
    this.init();
    offlineRepository.saveRevisitRecord(revisit);
  },

  /**
   * Lock a building record in SQLite.
   */
  lockBuilding(buildingId: string, hlbId?: string): void {
    this.init();
    offlineRepository.lockBuilding(buildingId, hlbId);
  },

  /**
   * Get aggregate fieldwork stats for an HLB from SQLite.
   */
  getFieldworkStats(hlbId: string): FieldworkStats {
    this.init();
    return offlineRepository.getHlbFieldworkStats(hlbId);
  },

  /**
   * Capture device GPS location and record observation in SQLite.
   */
  async captureAndLogGps(
    hlbId: string,
    enumeratorId: string,
    buildingId?: string
  ): Promise<GpsCaptureResponse> {
    this.init();
    const result = await gpsService.getCurrentLocation();
    if (result.success && result.position) {
      offlineRepository.saveGpsLog({
        id: `gps-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
        hlb_id: hlbId,
        building_id: buildingId || null,
        enumerator_id: enumeratorId,
        latitude: result.position.latitude,
        longitude: result.position.longitude,
        accuracy: result.position.accuracy,
        timestamp: result.position.timestamp,
      });
    }
    return result;
  },

  /**
   * Get the most recent GPS observation recorded for an HLB.
   */
  getLatestGpsObservation(hlbId: string): OfflineGpsLogRecord | null {
    this.init();
    return offlineRepository.getLatestGpsLog(hlbId);
  },

  /**
   * Get total number of GPS observations recorded for an HLB.
   */
  getGpsObservationCount(hlbId: string): number {
    this.init();
    return offlineRepository.getGpsLogCount(hlbId);
  },

  /**
   * Get all GPS observations recorded for an HLB.
   */
  getGpsLogs(hlbId: string): OfflineGpsLogRecord[] {
    this.init();
    return offlineRepository.getGpsLogs(hlbId);
  },

  /**
   * Calculate basic fieldwork coverage indicators from SQLite records.
   * Coverage is strictly based on building fieldwork status, not GPS presence.
   */
  calculateCoverage(hlbId: string): {
    totalBuildings: number;
    completedBuildings: number;
    inProgressBuildings: number;
    revisitBuildings: number;
    remainingBuildings: number;
    coveragePercentage: number;
    totalHouseholds: number;
    completedHouseholds: number;
  } {
    this.init();
    const stats = offlineRepository.getHlbFieldworkStats(hlbId);
    const blds = offlineRepository.getOfflineBuildings(hlbId);
    if (blds && blds.length > 0) {
      const progressInputs: BuildingProgressInput[] = blds.map((b) => {
        const chs = offlineRepository.getCensusHouses(b.id);
        return {
          id: b.id,
          listing_closed: Boolean(b.listing_closed),
          field_status: b.field_status || (b.status === 'COMPLETED' ? 'CONFIRMED' : 'UNVERIFIED'),
          census_houses: chs.map((c) => ({
            id: c.id,
            listing_state: c.listing_state,
          })),
        };
      });
      const hasAnyCensusHouses = progressInputs.some(
        (p) => p.census_houses && p.census_houses.length > 0
      );
      if (hasAnyCensusHouses) {
        const authProg = calculateAuthoritativeProgress(progressInputs);
        return {
          totalBuildings: authProg.total_eligible_buildings,
          completedBuildings: authProg.completed_buildings,
          inProgressBuildings: authProg.pending_buildings,
          revisitBuildings: authProg.locked_census_houses,
          remainingBuildings: authProg.pending_buildings,
          coveragePercentage: Math.round(authProg.completion_percentage),
          totalHouseholds: stats.total_households,
          completedHouseholds: stats.completed_households,
        };
      }
    }

    const total = stats.total_buildings;
    const completed = stats.completed_buildings + stats.locked_buildings;
    const inProgress = stats.in_progress_buildings;
    const revisit = stats.revisit_buildings;
    const remaining = Math.max(0, total - completed);
    const coveragePercentage = total > 0 ? Math.round((completed / total) * 100) : 0;

    return {
      totalBuildings: total,
      completedBuildings: completed,
      inProgressBuildings: inProgress,
      revisitBuildings: revisit,
      remainingBuildings: remaining,
      coveragePercentage,
      totalHouseholds: stats.total_households,
      completedHouseholds: stats.completed_households,
    };
  },

  /**
   * Evaluate GPS coordinates against the cached HLB boundary completely offline.
   */
  checkBoundaryOffline(
    hlbId: string,
    latitude: number,
    longitude: number,
    accuracy: number | null
  ) {
    this.init();
    const hlb = offlineRepository.getOfflineHlbById(hlbId);
    if (!hlb) {
      return {
        status: 'UNKNOWN' as const,
        distanceToBoundaryMeters: null,
        accuracyMeters: accuracy,
        message: 'HLB record not found offline',
      };
    }

    return boundaryService.checkBoundaryStatus(
      hlb.boundary_geojson,
      latitude,
      longitude,
      accuracy
    );
  },

  /**
   * Get sync queue summary statistics.
   */
  getSyncStats(): SyncQueueStats {
    this.init();
    return syncQueueRepository.getSyncQueueStats();
  },

  /**
   * Trigger batch synchronization with the backend.
   */
  async syncNow(): Promise<SyncBatchResult> {
    this.init();
    return syncService.syncBatch();
  },

  /**
   * Retry failed synchronization operations.
   */
  async retrySync(): Promise<SyncBatchResult> {
    this.init();
    return syncService.retryFailed();
  },

  /**
   * Get pending sync queue items.
   */
  getPendingSyncItems(limit = 50): SyncQueueItem[] {
    this.init();
    return syncQueueRepository.getPendingOperations(limit);
  },

  /**
   * Save or update a census house inside a building.
   */
  saveCensusHouse(record: OfflineCensusHouseRecord): void {
    this.init();
    offlineRepository.saveCensusHouse(record);
  },

  /**
   * Get census houses for a building.
   */
  getCensusHouses(buildingId: string): OfflineCensusHouseRecord[] {
    this.init();
    return offlineRepository.getCensusHouses(buildingId);
  },

  /**
   * Get census house by ID.
   */
  getCensusHouse(id: string): OfflineCensusHouseRecord | null {
    this.init();
    return offlineRepository.getCensusHouse(id);
  },

  /**
   * Save individual person record.
   */
  savePerson(person: OfflinePersonRecord): void {
    this.init();
    offlineRepository.savePerson(person);
  },

  /**
   * Get person records for a household.
   */
  getPersons(householdId: string): OfflinePersonRecord[] {
    this.init();
    return offlineRepository.getPersons(householdId);
  },

  /**
   * Submit building field edit.
   */
  saveBuildingEdit(edit: OfflineBuildingEditRecord): void {
    this.init();
    offlineRepository.saveBuildingEdit(edit);
  },

  /**
   * Close census house listing for a building.
   */
  closeBuildingListing(buildingId: string): void {
    this.init();
    offlineRepository.closeBuildingListing(buildingId);
  },

  /**
   * Set building field status.
   */
  setBuildingFieldStatus(buildingId: string, status: BuildingFieldStatus): void {
    this.init();
    offlineRepository.setBuildingFieldStatus(buildingId, status);
  },
};
