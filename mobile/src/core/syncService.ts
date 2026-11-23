import { apiClient, extractErrorMessage } from './apiClient';
import { offlineRepository } from './sqlite/offlineRepositories';
import { syncQueueRepository } from './sqlite/syncQueueRepository';
import type { SyncQueueItem, SyncQueueStats } from './sqlite/types';

export interface SyncBatchResult {
  success: boolean;
  processedCount: number;
  successCount: number;
  failedCount: number;
  conflictCount: number;
  error?: string;
}

export interface SyncOperationResultPayload {
  idempotency_key: string;
  status: 'SUCCESS' | 'FAILED' | 'CONFLICT';
  entity_type: string;
  local_entity_id: string;
  server_entity_id?: string | null;
  version?: number | null;
  server_timestamp: string;
  error_message?: string | null;
  conflict_data?: any;
}

export interface SyncBatchApiResponse {
  results: SyncOperationResultPayload[];
  processed_count: number;
  success_count: number;
  failed_count: number;
  conflict_count: number;
  synced_at: string;
}

let isSyncing = false;

export const syncService = {
  /**
   * Check whether a sync run is currently active.
   */
  isSyncInProgress(): boolean {
    return isSyncing;
  },

  /**
   * Get sync queue summary metrics from SQLite.
   */
  getSyncStats(): SyncQueueStats {
    return syncQueueRepository.getSyncQueueStats();
  },

  /**
   * Trigger synchronization of all pending queue items in batches.
   */
  async syncBatch(limit = 50): Promise<SyncBatchResult> {
    if (isSyncing) {
      const stats = syncQueueRepository.getSyncQueueStats();
      return {
        success: true,
        processedCount: 0,
        successCount: stats.syncedCount,
        failedCount: stats.failedCount,
        conflictCount: stats.conflictCount,
      };
    }

    const pendingItems = syncQueueRepository.getPendingOperations(limit);
    if (pendingItems.length === 0) {
      return {
        success: true,
        processedCount: 0,
        successCount: 0,
        failedCount: 0,
        conflictCount: 0,
      };
    }

    isSyncing = true;
    try {
      // 1. Mark items as actively syncing in SQLite
      for (const item of pendingItems) {
        syncQueueRepository.markOperationSyncing(item.idempotency_key);
      }

      // 2. Prepare payload for batch API
      const operationsPayload = pendingItems.map((item) => {
        let payloadObj = {};
        try {
          payloadObj = JSON.parse(item.payload_json);
        } catch {
          payloadObj = {};
        }

        return {
          idempotency_key: item.idempotency_key,
          operation_type: item.operation_type,
          entity_type: item.entity_type,
          local_entity_id: item.local_entity_id,
          server_entity_id: item.server_entity_id || null,
          client_timestamp: item.created_at,
          payload: payloadObj,
        };
      });

      // 3. Post to /api/v1/sync
      const data = await apiClient.post<SyncBatchApiResponse>('/sync', {
        device_id: 'mobile-app',
        operations: operationsPayload,
      });

      // 4. Process acknowledgements per operation
      for (const res of data.results) {
        if (res.status === 'SUCCESS') {
          syncQueueRepository.markOperationSynced(
            res.idempotency_key,
            res.server_entity_id || null,
            res.server_timestamp
          );

          // Update local household record with server-assigned UUID
          if (res.entity_type === 'HOUSEHOLD' && res.server_entity_id) {
            offlineRepository.updateHouseholdServerId(
              res.local_entity_id,
              res.server_entity_id,
              res.version || 1
            );
          }
        } else if (res.status === 'CONFLICT') {
          syncQueueRepository.markOperationConflict(
            res.idempotency_key,
            res.error_message || 'Conflict detected between local and server version'
          );
        } else {
          syncQueueRepository.markOperationFailed(
            res.idempotency_key,
            res.error_message || 'Operation failed on server'
          );
        }
      }

      return {
        success: true,
        processedCount: data.processed_count,
        successCount: data.success_count,
        failedCount: data.failed_count,
        conflictCount: data.conflict_count,
      };
    } catch (err: any) {
      const errMsg = extractErrorMessage(err);
      // Mark all in-flight items as FAILED for retry
      for (const item of pendingItems) {
        syncQueueRepository.markOperationFailed(item.idempotency_key, errMsg);
      }
      return {
        success: false,
        processedCount: pendingItems.length,
        successCount: 0,
        failedCount: pendingItems.length,
        conflictCount: 0,
        error: errMsg,
      };
    } finally {
      isSyncing = false;
    }
  },

  /**
   * Reset failed items and re-trigger synchronization.
   */
  async retryFailed(): Promise<SyncBatchResult> {
    syncQueueRepository.retryFailedOperations();
    return this.syncBatch();
  },
};
