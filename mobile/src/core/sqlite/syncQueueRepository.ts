import { getDatabase } from './database';
import type {
  SyncQueueItem,
  SyncQueueStats,
  SyncEntityType,
  SyncOperationType,
  SyncQueueStatus,
} from './types';

export const syncQueueRepository = {
  /**
   * Enqueue an operation into the persistent SQLite sync_queue.
   * If an un-synced operation already exists for the same local entity and operation type,
   * updates the payload and resets status to PENDING.
   */
  enqueueOperation(params: {
    idempotencyKey?: string;
    entityType: SyncEntityType;
    localEntityId: string;
    serverEntityId?: string | null;
    operationType: SyncOperationType;
    payload: any;
  }): SyncQueueItem {
    const db = getDatabase();
    const now = new Date().toISOString();
    const id = `queue-${Date.now()}-${Math.random().toString(36).substr(2, 8)}`;
    const idempotencyKey =
      params.idempotencyKey ||
      `idem-${params.localEntityId}-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
    const payloadJson = JSON.stringify(params.payload || {});

    db.runSync(
      `INSERT OR REPLACE INTO sync_queue (
        id, idempotency_key, entity_type, local_entity_id, server_entity_id,
        operation_type, payload_json, status, attempt_count, last_attempt_at,
        last_error, created_at, synced_at
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
      [
        id,
        idempotencyKey,
        params.entityType,
        params.localEntityId,
        params.serverEntityId || null,
        params.operationType,
        payloadJson,
        'PENDING',
        0,
        null,
        null,
        now,
        null,
      ]
    );

    return {
      id,
      idempotency_key: idempotencyKey,
      entity_type: params.entityType,
      local_entity_id: params.localEntityId,
      server_entity_id: params.serverEntityId || null,
      operation_type: params.operationType,
      payload_json: payloadJson,
      status: 'PENDING',
      attempt_count: 0,
      last_attempt_at: null,
      last_error: null,
      created_at: now,
      synced_at: null,
    };
  },

  /**
   * Fetch pending or retryable sync queue items.
   */
  getPendingOperations(limit = 50): SyncQueueItem[] {
    const db = getDatabase();
    return db.getAllSync<SyncQueueItem>(
      `SELECT * FROM sync_queue 
       WHERE status IN ('PENDING', 'FAILED') 
       ORDER BY created_at ASC 
       LIMIT ?;`,
      [limit]
    );
  },

  /**
   * Mark a queue item as actively syncing.
   */
  markOperationSyncing(idempotencyKey: string): void {
    const db = getDatabase();
    const now = new Date().toISOString();
    db.runSync(
      `UPDATE sync_queue 
       SET status = 'SYNCING', 
           attempt_count = attempt_count + 1, 
           last_attempt_at = ? 
       WHERE idempotency_key = ?;`,
      [now, idempotencyKey]
    );
  },

  /**
   * Mark a queue item as SYNCED upon valid server acknowledgement.
   */
  markOperationSynced(
    idempotencyKey: string,
    serverEntityId?: string | null,
    syncedAt?: string
  ): void {
    const db = getDatabase();
    const now = syncedAt || new Date().toISOString();
    db.runSync(
      `UPDATE sync_queue 
       SET status = 'SYNCED', 
           server_entity_id = COALESCE(?, server_entity_id), 
           synced_at = ?, 
           last_error = NULL 
       WHERE idempotency_key = ?;`,
      [serverEntityId || null, now, idempotencyKey]
    );
  },

  /**
   * Mark a queue item as FAILED with error message.
   */
  markOperationFailed(idempotencyKey: string, error: string): void {
    const db = getDatabase();
    db.runSync(
      `UPDATE sync_queue 
       SET status = 'FAILED', 
           last_error = ? 
       WHERE idempotency_key = ?;`,
      [error, idempotencyKey]
    );
  },

  /**
   * Mark a queue item as CONFLICT.
   */
  markOperationConflict(idempotencyKey: string, error: string): void {
    const db = getDatabase();
    db.runSync(
      `UPDATE sync_queue 
       SET status = 'CONFLICT', 
           last_error = ? 
       WHERE idempotency_key = ?;`,
      [error, idempotencyKey]
    );
  },

  /**
   * Reset all FAILED operations back to PENDING for manual or network retry.
   */
  retryFailedOperations(): void {
    const db = getDatabase();
    db.runSync(
      `UPDATE sync_queue 
       SET status = 'PENDING' 
       WHERE status = 'FAILED';`
    );
  },

  /**
   * Get aggregate synchronization statistics.
   */
  getSyncQueueStats(): SyncQueueStats {
    const db = getDatabase();
    const counts = db.getFirstSync<{
      pending: number;
      syncing: number;
      synced: number;
      failed: number;
      conflict: number;
      total: number;
      last_synced: string | null;
    }>(
      `SELECT 
        SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
        SUM(CASE WHEN status = 'SYNCING' THEN 1 ELSE 0 END) as syncing,
        SUM(CASE WHEN status = 'SYNCED' THEN 1 ELSE 0 END) as synced,
        SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed,
        SUM(CASE WHEN status = 'CONFLICT' THEN 1 ELSE 0 END) as conflict,
        COUNT(*) as total,
        MAX(synced_at) as last_synced
      FROM sync_queue;`
    );

    return {
      pendingCount: counts?.pending || 0,
      syncingCount: counts?.syncing || 0,
      syncedCount: counts?.synced || 0,
      failedCount: counts?.failed || 0,
      conflictCount: counts?.conflict || 0,
      totalCount: counts?.total || 0,
      lastSyncedAt: counts?.last_synced || null,
    };
  },

  /**
   * Get all sync queue items (for inspection/debugging).
   */
  getAllQueueItems(): SyncQueueItem[] {
    const db = getDatabase();
    return db.getAllSync<SyncQueueItem>(
      'SELECT * FROM sync_queue ORDER BY created_at DESC;'
    );
  },
};
