import { getDatabase } from './database';
import { syncQueueRepository } from './syncQueueRepository';
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
  CensusHouseListingState,
  CensusHouseUseCode,
  FieldworkStats,
  BuildingStatus,
} from './types';

export const offlineRepository = {
  /**
   * Completely clear all locally stored offline application records.
   */
  clearAllOfflineData(): void {
    const db = getDatabase();
    db.withTransactionSync(() => {
      db.execSync(`
        DELETE FROM offline_building_edits;
        DELETE FROM offline_persons;
        DELETE FROM offline_census_houses;
        DELETE FROM offline_routes;
        DELETE FROM sync_queue;
        DELETE FROM offline_gps_logs;
        DELETE FROM offline_revisits;
        DELETE FROM offline_household_records;
        DELETE FROM offline_buildings;
        DELETE FROM offline_hlbs;
      `);
    });
  },

  /**
   * Save a complete downloaded HLB along with its assigned buildings inside a single atomic transaction.
   * If a building already exists locally with fieldwork modifications, local status and households are preserved.
   */
  saveDownloadedHlb(
    hlb: {
      id: string;
      layout_id: string;
      layout_name?: string | null;
      area_name?: string | null;
      block_code: string;
      name?: string | null;
      status: string;
      target_building_count: number;
      actual_building_count: number;
      boundary?: any;
    },
    buildings: Array<{
      id: string;
      building_reference: string;
      house_number?: string | null;
      latitude: number;
      longitude: number;
      footprint?: any;
      source_type?: string | null;
      status?: string;
    }>,
    enumeratorId: string
  ): void {
    const db = getDatabase();
    const now = new Date().toISOString();
    const boundaryGeoJson = JSON.stringify(hlb.boundary || {});

    db.withTransactionSync(() => {
      // 1. Insert or replace HLB
      db.runSync(
        `INSERT OR REPLACE INTO offline_hlbs (
          id, layout_id, layout_name, area_name, block_code, name, status,
          target_building_count, actual_building_count, boundary_geojson,
          downloaded_at, enumerator_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          hlb.id,
          hlb.layout_id,
          hlb.layout_name || null,
          hlb.area_name || null,
          hlb.block_code,
          hlb.name || null,
          hlb.status,
          hlb.target_building_count,
          hlb.actual_building_count,
          boundaryGeoJson,
          now,
          enumeratorId,
        ]
      );

      // 2. Insert buildings while preserving existing local fieldwork status if any
      for (const b of buildings) {
        const existing = db.getFirstSync<{
          status: string;
          household_count: number;
        }>(
          'SELECT status, household_count FROM offline_buildings WHERE id = ?;',
          [b.id]
        );

        const currentStatus = existing?.status || b.status || 'PENDING';
        const currentHhCount = existing?.household_count || 0;
        const footprintGeoJson = b.footprint ? JSON.stringify(b.footprint) : null;

        db.runSync(
          `INSERT OR REPLACE INTO offline_buildings (
            id, hlb_id, building_reference, house_number, latitude, longitude,
            footprint_geojson, source_type, status, household_count, last_updated_at
          ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
          [
            b.id,
            hlb.id,
            b.building_reference,
            b.house_number || null,
            b.latitude,
            b.longitude,
            footprintGeoJson,
            b.source_type || null,
            currentStatus,
            currentHhCount,
            now,
          ]
        );
      }
    });
  },

  /**
   * Check if an HLB is already downloaded locally for the authenticated enumerator.
   */
  isHlbDownloaded(hlbId: string, enumeratorId: string): boolean {
    const db = getDatabase();
    const row = db.getFirstSync<{ id: string }>(
      'SELECT id FROM offline_hlbs WHERE id = ? AND enumerator_id = ?;',
      [hlbId, enumeratorId]
    );
    return Boolean(row);
  },

  /**
   * Get all HLBs downloaded for this enumerator.
   */
  getOfflineHlbs(enumeratorId: string): OfflineHlbRecord[] {
    const db = getDatabase();
    return db.getAllSync<OfflineHlbRecord>(
      'SELECT * FROM offline_hlbs WHERE enumerator_id = ? ORDER BY downloaded_at DESC;',
      [enumeratorId]
    );
  },

  /**
   * Get a specific downloaded HLB.
   */
  getOfflineHlbById(
    hlbId: string,
    enumeratorId?: string
  ): OfflineHlbRecord | null {
    const db = getDatabase();
    if (enumeratorId) {
      return (
        db.getFirstSync<OfflineHlbRecord>(
          'SELECT * FROM offline_hlbs WHERE id = ? AND enumerator_id = ?;',
          [hlbId, enumeratorId]
        ) || null
      );
    }
    return (
      db.getFirstSync<OfflineHlbRecord>(
        'SELECT * FROM offline_hlbs WHERE id = ?;',
        [hlbId]
      ) || null
    );
  },

  /**
   * Delete an offline HLB and its associated local records.
   */
  deleteOfflineHlb(hlbId: string): void {
    const db = getDatabase();
    db.withTransactionSync(() => {
      db.runSync('DELETE FROM sync_queue WHERE payload_json LIKE ?;', [`%"hlb_id":"${hlbId}"%`]);
      db.runSync('DELETE FROM offline_gps_logs WHERE hlb_id = ?;', [hlbId]);
      db.runSync('DELETE FROM offline_revisits WHERE hlb_id = ?;', [hlbId]);
      db.runSync('DELETE FROM offline_household_records WHERE hlb_id = ?;', [
        hlbId,
      ]);
      db.runSync('DELETE FROM offline_buildings WHERE hlb_id = ?;', [hlbId]);
      db.runSync('DELETE FROM offline_hlbs WHERE id = ?;', [hlbId]);
    });
  },

  /**
   * Get all buildings belonging to an HLB, optionally filtered by status or search.
   */
  getOfflineBuildings(
    hlbId: string,
    statusFilter?: BuildingStatus | 'ALL',
    searchQuery?: string
  ): OfflineBuildingRecord[] {
    const db = getDatabase();
    let query = 'SELECT * FROM offline_buildings WHERE hlb_id = ?';
    const params: (string | number)[] = [hlbId];

    if (statusFilter && statusFilter !== 'ALL') {
      query += ' AND status = ?';
      params.push(statusFilter);
    }

    if (searchQuery && searchQuery.trim().length > 0) {
      query +=
        ' AND (building_reference LIKE ? OR house_number LIKE ?)';
      params.push(`%${searchQuery.trim()}%`, `%${searchQuery.trim()}%`);
    }

    query += ' ORDER BY building_reference ASC, id ASC;';
    return db.getAllSync<OfflineBuildingRecord>(query, params);
  },

  /**
   * Get detail for a specific building including its households and revisits.
   */
  getOfflineBuildingDetail(buildingId: string): {
    building: OfflineBuildingRecord | null;
    households: OfflineHouseholdRecord[];
    revisits: OfflineRevisitRecord[];
  } {
    const db = getDatabase();
    const building =
      db.getFirstSync<OfflineBuildingRecord>(
        'SELECT * FROM offline_buildings WHERE id = ?;',
        [buildingId]
      ) || null;

    if (!building) {
      return { building: null, households: [], revisits: [] };
    }

    const households = db.getAllSync<OfflineHouseholdRecord>(
      'SELECT * FROM offline_household_records WHERE building_id = ? ORDER BY created_at ASC;',
      [buildingId]
    );

    const revisits = db.getAllSync<OfflineRevisitRecord>(
      'SELECT * FROM offline_revisits WHERE building_id = ? ORDER BY created_at DESC;',
      [buildingId]
    );

    return { building, households, revisits };
  },

  /**
   * Save or update a household questionnaire record and enqueue sync operation atomically.
   */
  saveHouseholdRecord(record: OfflineHouseholdRecord): void {
    const db = getDatabase();
    const now = new Date().toISOString();
    const isUpdate = Boolean(record.server_id);
    const opType = isUpdate ? 'UPDATE' : 'CREATE';

    db.withTransactionSync(() => {
      // 1. Upsert household record
      db.runSync(
        `INSERT OR REPLACE INTO offline_household_records (
          id, server_id, building_id, census_house_id, hlb_id, enumerator_id, household_number, head_name,
          total_members, male_count, female_count, transgender_count, ownership_status,
          drinking_water_source, lighting_source, latrine_facility, data_json,
          questionnaire_version, review_state, rejection_reason, supervisor_comment,
          status, source, version, sync_status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          record.id,
          record.server_id || null,
          record.building_id,
          record.census_house_id || null,
          record.hlb_id,
          record.enumerator_id,
          record.household_number,
          record.head_name,
          record.total_members,
          record.male_count,
          record.female_count,
          record.transgender_count,
          record.ownership_status,
          record.drinking_water_source || null,
          record.lighting_source || null,
          record.latrine_facility || null,
          record.data_json || null,
          record.questionnaire_version || '1.0',
          record.review_state || 'DRAFT',
          record.rejection_reason || null,
          record.supervisor_comment || null,
          record.status,
          record.source || 'FORM',
          record.version || 1,
          record.sync_status || 'PENDING',
          record.created_at || now,
          now,
        ]
      );

      // 2. Count total households and completed households for this building
      const countRow = db.getFirstSync<{ total: number; completed: number }>(
        `SELECT 
          COUNT(*) as total,
          SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed
        FROM offline_household_records WHERE building_id = ?;`,
        [record.building_id]
      );

      const totalHh = countRow?.total || 0;
      const completedHh = countRow?.completed || 0;

      // Determine building status
      let newBuildingStatus: BuildingStatus = 'IN_PROGRESS';
      if (completedHh > 0 && completedHh === totalHh) {
        newBuildingStatus = 'COMPLETED';
      } else if (totalHh === 0) {
        newBuildingStatus = 'PENDING';
      }

      // 3. Update building status & count
      db.runSync(
        `UPDATE offline_buildings 
         SET status = ?, household_count = ?, last_updated_at = ? 
         WHERE id = ?;`,
        [newBuildingStatus, totalHh, now, record.building_id]
      );

      // 4. Enqueue into sync_queue
      syncQueueRepository.enqueueOperation({
        entityType: 'HOUSEHOLD',
        localEntityId: record.id,
        serverEntityId: record.server_id || null,
        operationType: opType,
        payload: {
          hlb_id: record.hlb_id,
          building_id: record.building_id,
          census_house_id: record.census_house_id || null,
          household_number: record.household_number,
          head_name: record.head_name,
          total_members: record.total_members,
          male_count: record.male_count,
          female_count: record.female_count,
          transgender_count: record.transgender_count,
          ownership_status: record.ownership_status,
          drinking_water_source: record.drinking_water_source,
          lighting_source: record.lighting_source,
          latrine_facility: record.latrine_facility,
          questionnaire_version: record.questionnaire_version || '1.0',
          review_state: record.review_state || 'SUBMITTED',
          status: record.status,
          source: record.source || 'FORM',
        },
      });
    });
  },

  /**
   * Update server_id, version and sync_status on an offline household record after acknowledgement.
   */
  updateHouseholdServerId(
    localId: string,
    serverId: string,
    version = 1
  ): void {
    const db = getDatabase();
    const now = new Date().toISOString();
    db.runSync(
      `UPDATE offline_household_records 
       SET server_id = ?, version = ?, sync_status = 'SYNCED', updated_at = ? 
       WHERE id = ?;`,
      [serverId, version, now, localId]
    );
  },

  /**
   * Delete a household record.
   */
  deleteHouseholdRecord(householdId: string, buildingId: string): void {
    const db = getDatabase();
    const now = new Date().toISOString();

    db.withTransactionSync(() => {
      db.runSync('DELETE FROM offline_household_records WHERE id = ?;', [
        householdId,
      ]);
      db.runSync('DELETE FROM sync_queue WHERE local_entity_id = ?;', [
        householdId,
      ]);

      const countRow = db.getFirstSync<{ total: number; completed: number }>(
        `SELECT 
          COUNT(*) as total,
          SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed
        FROM offline_household_records WHERE building_id = ?;`,
        [buildingId]
      );

      const totalHh = countRow?.total || 0;
      const completedHh = countRow?.completed || 0;

      let newBuildingStatus: BuildingStatus = 'PENDING';
      if (completedHh > 0 && completedHh === totalHh) {
        newBuildingStatus = 'COMPLETED';
      } else if (totalHh > 0) {
        newBuildingStatus = 'IN_PROGRESS';
      }

      db.runSync(
        `UPDATE offline_buildings 
         SET status = ?, household_count = ?, last_updated_at = ? 
         WHERE id = ?;`,
        [newBuildingStatus, totalHh, now, buildingId]
      );
    });
  },

  /**
   * Save a revisit observation for a building and enqueue sync operation.
   */
  saveRevisitRecord(revisit: OfflineRevisitRecord): void {
    const db = getDatabase();
    const now = new Date().toISOString();

    db.withTransactionSync(() => {
      db.runSync(
        `INSERT OR REPLACE INTO offline_revisits (
          id, building_id, hlb_id, enumerator_id, reason, notes,
          status, created_at, resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          revisit.id,
          revisit.building_id,
          revisit.hlb_id,
          revisit.enumerator_id,
          revisit.reason,
          revisit.notes || null,
          revisit.status || 'PENDING',
          revisit.created_at || now,
          revisit.resolved_at || null,
        ]
      );

      // Update building status to REVISIT_REQUIRED
      db.runSync(
        `UPDATE offline_buildings 
         SET status = 'REVISIT_REQUIRED', last_updated_at = ? 
         WHERE id = ?;`,
        [now, revisit.building_id]
      );

      // Enqueue sync operation
      syncQueueRepository.enqueueOperation({
        entityType: 'REVISIT',
        localEntityId: revisit.id,
        operationType: 'CREATE',
        payload: {
          hlb_id: revisit.hlb_id,
          building_id: revisit.building_id,
          reason: revisit.reason,
          notes: revisit.notes,
          status: revisit.status || 'PENDING',
        },
      });
    });
  },

  /**
   * Lock a building when fieldwork is finalized and enqueue status update.
   */
  lockBuilding(buildingId: string, hlbId?: string): void {
    const db = getDatabase();
    const now = new Date().toISOString();
    db.withTransactionSync(() => {
      db.runSync(
        `UPDATE offline_buildings 
         SET status = 'LOCKED', last_updated_at = ? 
         WHERE id = ?;`,
        [now, buildingId]
      );

      const bld = db.getFirstSync<{ hlb_id: string; household_count: number }>(
        'SELECT hlb_id, household_count FROM offline_buildings WHERE id = ?;',
        [buildingId]
      );
      const targetHlbId = hlbId || bld?.hlb_id;

      if (targetHlbId) {
        syncQueueRepository.enqueueOperation({
          entityType: 'BUILDING_STATUS',
          localEntityId: buildingId,
          operationType: 'STATUS_UPDATE',
          payload: {
            hlb_id: targetHlbId,
            building_id: buildingId,
            status: 'LOCKED',
            household_count: bld?.household_count || 0,
          },
        });
      }
    });
  },

  /**
   * Save a GPS tracking observation and enqueue sync operation.
   */
  saveGpsLog(gpsLog: OfflineGpsLogRecord): void {
    const db = getDatabase();
    db.withTransactionSync(() => {
      db.runSync(
        `INSERT INTO offline_gps_logs (
          id, hlb_id, building_id, enumerator_id, latitude, longitude, accuracy, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          gpsLog.id,
          gpsLog.hlb_id,
          gpsLog.building_id || null,
          gpsLog.enumerator_id,
          gpsLog.latitude,
          gpsLog.longitude,
          gpsLog.accuracy || null,
          gpsLog.timestamp,
        ]
      );

      syncQueueRepository.enqueueOperation({
        entityType: 'GPS_LOG',
        localEntityId: gpsLog.id,
        operationType: 'CREATE',
        payload: {
          hlb_id: gpsLog.hlb_id,
          building_id: gpsLog.building_id,
          latitude: gpsLog.latitude,
          longitude: gpsLog.longitude,
          accuracy: gpsLog.accuracy,
          timestamp: gpsLog.timestamp,
        },
      });
    });
  },

  /**
   * Retrieve all GPS observations recorded for an HLB.
   */
  getGpsLogs(hlbId: string): OfflineGpsLogRecord[] {
    const db = getDatabase();
    return db.getAllSync<OfflineGpsLogRecord>(
      'SELECT * FROM offline_gps_logs WHERE hlb_id = ? ORDER BY timestamp DESC;',
      [hlbId]
    );
  },

  /**
   * Retrieve the most recent GPS observation recorded for an HLB.
   */
  getLatestGpsLog(hlbId: string): OfflineGpsLogRecord | null {
    const db = getDatabase();
    return (
      db.getFirstSync<OfflineGpsLogRecord>(
        'SELECT * FROM offline_gps_logs WHERE hlb_id = ? ORDER BY timestamp DESC LIMIT 1;',
        [hlbId]
      ) || null
    );
  },

  /**
   * Retrieve total number of GPS observations recorded for an HLB.
   */
  getGpsLogCount(hlbId: string): number {
    const db = getDatabase();
    const row = db.getFirstSync<{ count: number }>(
      'SELECT COUNT(*) as count FROM offline_gps_logs WHERE hlb_id = ?;',
      [hlbId]
    );
    return row?.count || 0;
  },

  /**
   * Get aggregate fieldwork statistics for an HLB.
   */
  getHlbFieldworkStats(hlbId: string): FieldworkStats {
    const db = getDatabase();

    const buildingStats = db.getFirstSync<{
      total: number;
      completed: number;
      pending: number;
      in_progress: number;
      revisit: number;
      locked: number;
    }>(
      `SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) as pending,
        SUM(CASE WHEN status = 'IN_PROGRESS' THEN 1 ELSE 0 END) as in_progress,
        SUM(CASE WHEN status = 'REVISIT_REQUIRED' THEN 1 ELSE 0 END) as revisit,
        SUM(CASE WHEN status = 'LOCKED' THEN 1 ELSE 0 END) as locked
      FROM offline_buildings WHERE hlb_id = ?;`,
      [hlbId]
    );

    const hhStats = db.getFirstSync<{
      total: number;
      completed: number;
      draft: number;
    }>(
      `SELECT 
        COUNT(*) as total,
        SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed,
        SUM(CASE WHEN status = 'DRAFT' THEN 1 ELSE 0 END) as draft
      FROM offline_household_records WHERE hlb_id = ?;`,
      [hlbId]
    );

    return {
      total_buildings: buildingStats?.total || 0,
      completed_buildings: buildingStats?.completed || 0,
      pending_buildings: buildingStats?.pending || 0,
      in_progress_buildings: buildingStats?.in_progress || 0,
      revisit_buildings: buildingStats?.revisit || 0,
      locked_buildings: buildingStats?.locked || 0,
      total_households: hhStats?.total || 0,
      completed_households: hhStats?.completed || 0,
      draft_households: hhStats?.draft || 0,
    };
  },

  /**
   * Save or update an offline census house record and enqueue sync operation.
   */
  saveCensusHouse(record: OfflineCensusHouseRecord): void {
    const db = getDatabase();
    const now = new Date().toISOString();
    const isUpdate = Boolean(record.server_id);
    const opType = isUpdate ? 'UPDATE' : 'CREATE';

    db.withTransactionSync(() => {
      db.runSync(
        `INSERT OR REPLACE INTO offline_census_houses (
          id, server_id, building_id, hlb_id, census_house_number, use_code,
          listing_state, latitude, longitude, geotag_accuracy_m, visited_at,
          locked_attempts, notes, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          record.id,
          record.server_id || null,
          record.building_id,
          record.hlb_id,
          record.census_house_number,
          record.use_code,
          record.listing_state,
          record.latitude ?? null,
          record.longitude ?? null,
          record.geotag_accuracy_m ?? null,
          record.visited_at || null,
          record.locked_attempts || 0,
          record.notes || null,
          record.created_at || now,
          now,
        ]
      );

      // Enqueue sync operation
      syncQueueRepository.enqueueOperation({
        entityType: 'CENSUS_HOUSE',
        localEntityId: record.id,
        serverEntityId: record.server_id || null,
        operationType: opType,
        payload: {
          id: record.id,
          building_id: record.building_id,
          hlb_id: record.hlb_id,
          census_house_number: record.census_house_number,
          use_code: record.use_code,
          listing_state: record.listing_state,
          latitude: record.latitude,
          longitude: record.longitude,
          geotag_accuracy_m: record.geotag_accuracy_m,
          visited_at: record.visited_at,
          locked_attempts: record.locked_attempts,
          notes: record.notes,
        },
      });
    });
  },

  /**
   * Get all census houses inside a building.
   */
  getCensusHouses(buildingId: string): OfflineCensusHouseRecord[] {
    const db = getDatabase();
    return db.getAllSync<OfflineCensusHouseRecord>(
      'SELECT * FROM offline_census_houses WHERE building_id = ? ORDER BY census_house_number ASC;',
      [buildingId]
    );
  },

  /**
   * Get census house by ID.
   */
  getCensusHouse(id: string): OfflineCensusHouseRecord | null {
    const db = getDatabase();
    return (
      db.getFirstSync<OfflineCensusHouseRecord>(
        'SELECT * FROM offline_census_houses WHERE id = ?;',
        [id]
      ) || null
    );
  },

  /**
   * Save or update an individual Person demographic record (Phase II).
   */
  savePerson(person: OfflinePersonRecord): void {
    const db = getDatabase();
    const now = new Date().toISOString();
    const isUpdate = Boolean(person.server_id);
    const opType = isUpdate ? 'UPDATE' : 'CREATE';

    db.withTransactionSync(() => {
      db.runSync(
        `INSERT OR REPLACE INTO offline_persons (
          id, server_id, household_id, person_number, name, relationship_to_head,
          sex, age, date_of_birth, marital_status, answers_json, questionnaire_version,
          review_state, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          person.id,
          person.server_id || null,
          person.household_id,
          person.person_number,
          person.name,
          person.relationship_to_head,
          person.sex,
          person.age ?? null,
          person.date_of_birth || null,
          person.marital_status || null,
          person.answers_json || null,
          person.questionnaire_version || '2.0',
          person.review_state || 'DRAFT',
          person.created_at || now,
          now,
        ]
      );

      syncQueueRepository.enqueueOperation({
        entityType: 'PERSON',
        localEntityId: person.id,
        serverEntityId: person.server_id || null,
        operationType: opType,
        payload: {
          id: person.id,
          household_id: person.household_id,
          person_number: person.person_number,
          name: person.name,
          relationship_to_head: person.relationship_to_head,
          sex: person.sex,
          age: person.age,
          date_of_birth: person.date_of_birth,
          marital_status: person.marital_status,
          answers: person.answers_json ? JSON.parse(person.answers_json) : null,
          questionnaire_version: person.questionnaire_version,
        },
      });
    });
  },

  /**
   * Get all persons belonging to a household.
   */
  getPersons(householdId: string): OfflinePersonRecord[] {
    const db = getDatabase();
    return db.getAllSync<OfflinePersonRecord>(
      'SELECT * FROM offline_persons WHERE household_id = ? ORDER BY person_number ASC;',
      [householdId]
    );
  },

  /**
   * Save building field edit (ADD, DELETE, MERGE, MOVE, RENUMBER).
   */
  saveBuildingEdit(edit: OfflineBuildingEditRecord): void {
    const db = getDatabase();
    const now = new Date().toISOString();

    db.withTransactionSync(() => {
      db.runSync(
        `INSERT OR REPLACE INTO offline_building_edits (
          id, hlb_id, building_id, edit_type, proposed_changes_json, reason,
          review_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);`,
        [
          edit.id,
          edit.hlb_id,
          edit.building_id || null,
          edit.edit_type,
          edit.proposed_changes_json,
          edit.reason,
          edit.review_status || 'PENDING',
          edit.created_at || now,
        ]
      );

      syncQueueRepository.enqueueOperation({
        entityType: 'BUILDING_EDIT',
        localEntityId: edit.id,
        serverEntityId: null,
        operationType: 'CREATE',
        payload: {
          id: edit.id,
          hlb_id: edit.hlb_id,
          building_id: edit.building_id,
          edit_type: edit.edit_type,
          proposed_changes: JSON.parse(edit.proposed_changes_json),
          reason: edit.reason,
        },
      });
    });
  },

  /**
   * Close census house listing for a building.
   */
  closeBuildingListing(buildingId: string): void {
    const db = getDatabase();
    const now = new Date().toISOString();

    db.withTransactionSync(() => {
      db.runSync(
        `UPDATE offline_buildings 
         SET listing_closed = 1, listing_closed_at = ?, last_updated_at = ? 
         WHERE id = ?;`,
        [now, now, buildingId]
      );

      const building = db.getFirstSync<OfflineBuildingRecord>(
        'SELECT * FROM offline_buildings WHERE id = ?;',
        [buildingId]
      );

      if (building) {
        syncQueueRepository.enqueueOperation({
          entityType: 'BUILDING_STATUS',
          localEntityId: buildingId,
          serverEntityId: building.id,
          operationType: 'STATUS_UPDATE',
          payload: {
            building_id: buildingId,
            hlb_id: building.hlb_id,
            listing_closed: true,
            listing_closed_at: now,
          },
        });
      }
    });
  },

  /**
   * Update building field status (CONFIRMED, FALSE_DETECTION, etc.).
   */
  setBuildingFieldStatus(buildingId: string, fieldStatus: BuildingFieldStatus): void {
    const db = getDatabase();
    const now = new Date().toISOString();

    db.withTransactionSync(() => {
      db.runSync(
        `UPDATE offline_buildings 
         SET field_status = ?, last_updated_at = ? 
         WHERE id = ?;`,
        [fieldStatus, now, buildingId]
      );

      const building = db.getFirstSync<OfflineBuildingRecord>(
        'SELECT * FROM offline_buildings WHERE id = ?;',
        [buildingId]
      );

      if (building) {
        syncQueueRepository.enqueueOperation({
          entityType: 'BUILDING_STATUS',
          localEntityId: buildingId,
          serverEntityId: building.id,
          operationType: 'STATUS_UPDATE',
          payload: {
            building_id: buildingId,
            hlb_id: building.hlb_id,
            field_status: fieldStatus,
          },
        });
      }
    });
  },
};
