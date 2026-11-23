import { Platform } from 'react-native';
import * as SQLite from 'expo-sqlite';

const DB_NAME = 'enumerator_fieldwork.db';
const SCHEMA_VERSION = 4;

let dbInstance: any = null;

// In-Memory SQLite Fallback for Web / Environments where SharedArrayBuffer is unavailable
const webTables: Record<string, any[]> = {
  schema_versions: [],
  offline_hlbs: [],
  offline_buildings: [],
  offline_census_houses: [],
  offline_household_records: [],
  offline_persons: [],
  offline_building_edits: [],
  offline_revisits: [],
  offline_gps_logs: [],
  sync_queue: [],
  offline_routes: [],
};

function parseColumns(sql: string): string[] {
  const match = sql.match(/\(([^)]+)\)\s*VALUES/i);
  if (!match) return [];
  return match[1].split(',').map((c) => c.trim().replace(/^["`]|["`]$/g, ''));
}

function parseTableName(sql: string): string | null {
  const insertMatch = sql.match(/INTO\s+([a-zA-Z0-9_]+)/i);
  if (insertMatch) return insertMatch[1];
  const updateMatch = sql.match(/UPDATE\s+([a-zA-Z0-9_]+)/i);
  if (updateMatch) return updateMatch[1];
  const fromMatch = sql.match(/FROM\s+([a-zA-Z0-9_]+)/i);
  if (fromMatch) return fromMatch[1];
  return null;
}

function createWebDatabase(): any {
  return {
    execSync: (sql: string) => {
      if (sql.includes('DELETE FROM')) {
        const deletes = sql.match(/DELETE FROM\s+([a-zA-Z0-9_]+)/gi) || [];
        for (const d of deletes) {
          const table = d.replace(/DELETE FROM\s+/i, '').trim();
          if (webTables[table]) {
            webTables[table] = [];
          }
        }
      }
    },
    runSync: (sql: string, params: any[] = []) => {
      const table = parseTableName(sql);
      if (!table) return { changes: 1, lastInsertRowId: 1 };
      if (!webTables[table]) webTables[table] = [];

      if (/^INSERT/i.test(sql.trim())) {
        const cols = parseColumns(sql);
        const row: Record<string, any> = {};
        cols.forEach((col, idx) => {
          row[col] = params[idx] !== undefined ? params[idx] : null;
        });

        const pk =
          row.id !== undefined
            ? 'id'
            : row.version !== undefined
            ? 'version'
            : row.hlb_id !== undefined
            ? 'hlb_id'
            : null;
        if (pk) {
          const existingIdx = webTables[table].findIndex((r) => r[pk] === row[pk]);
          if (existingIdx >= 0) {
            webTables[table][existingIdx] = {
              ...webTables[table][existingIdx],
              ...row,
            };
          } else {
            webTables[table].push(row);
          }
        } else {
          webTables[table].push(row);
        }
        return { changes: 1, lastInsertRowId: webTables[table].length };
      }

      if (/^UPDATE/i.test(sql.trim())) {
        if (table === 'sync_queue') {
          if (sql.includes("status = 'SYNCING'")) {
            const now = params[0];
            const idemKey = params[1];
            const item = webTables.sync_queue.find(
              (r) => r.idempotency_key === idemKey
            );
            if (item) {
              item.status = 'SYNCING';
              item.attempt_count = (item.attempt_count || 0) + 1;
              item.last_attempt_at = now;
            }
          } else if (sql.includes("status = 'SYNCED'")) {
            const serverId = params[0];
            const syncedAt = params[1];
            const idemKey = params[2];
            const item = webTables.sync_queue.find(
              (r) => r.idempotency_key === idemKey
            );
            if (item) {
              item.status = 'SYNCED';
              if (serverId) item.server_entity_id = serverId;
              item.synced_at = syncedAt;
              item.last_error = null;
            }
          } else if (sql.includes("status = 'FAILED'")) {
            const err = params[0];
            const idemKey = params[1];
            const item = webTables.sync_queue.find(
              (r) => r.idempotency_key === idemKey
            );
            if (item) {
              item.status = 'FAILED';
              item.last_error = err;
            }
          } else if (sql.includes("status = 'CONFLICT'")) {
            const err = params[0];
            const idemKey = params[1];
            const item = webTables.sync_queue.find(
              (r) => r.idempotency_key === idemKey
            );
            if (item) {
              item.status = 'CONFLICT';
              item.last_error = err;
            }
          } else if (
            sql.includes("SET status = 'PENDING' WHERE status = 'FAILED'")
          ) {
            webTables.sync_queue.forEach((r) => {
              if (r.status === 'FAILED') r.status = 'PENDING';
            });
          }
        } else if (table === 'offline_household_records') {
          if (sql.includes('SET server_id = ?')) {
            const serverId = params[0];
            const version = params[1];
            const updatedAt = params[2];
            const id = params[3];
            const item = webTables.offline_household_records.find(
              (r) => r.id === id
            );
            if (item) {
              item.server_id = serverId;
              item.version = version;
              item.sync_status = 'SYNCED';
              item.updated_at = updatedAt;
            }
          }
        } else if (table === 'offline_buildings') {
          const status = params[0];
          const hhCount = params[1];
          const updatedAt = params[2];
          const id = params[3];
          const item = webTables.offline_buildings.find((r) => r.id === id);
          if (item) {
            item.status = status;
            item.household_count = hhCount;
            item.last_updated_at = updatedAt;
          }
        }
        return { changes: 1, lastInsertRowId: 1 };
      }

      if (/^DELETE/i.test(sql.trim())) {
        if (params.length > 0 && sql.includes('WHERE id = ?')) {
          webTables[table] = webTables[table].filter((r) => r.id !== params[0]);
        } else {
          webTables[table] = [];
        }
        return { changes: 1, lastInsertRowId: 0 };
      }

      return { changes: 1, lastInsertRowId: 1 };
    },
    getFirstSync: (sql: string, params: any[] = []) => {
      const table = parseTableName(sql);

      if (sql.includes('MAX(version)')) {
        const rows = webTables.schema_versions || [];
        const maxVer = rows.reduce(
          (max, r) => Math.max(max, Number(r.version) || 0),
          0
        );
        return maxVer > 0 ? { version: maxVer } : null;
      }

      if (table === 'sync_queue' && sql.includes('SUM(CASE')) {
        const q = webTables.sync_queue || [];
        const syncedItems = q.filter((r) => r.synced_at);
        const lastSynced = syncedItems.reduce(
          (latest, r) => (!latest || r.synced_at > latest ? r.synced_at : latest),
          null
        );
        return {
          pending: q.filter((r) => r.status === 'PENDING').length,
          syncing: q.filter((r) => r.status === 'SYNCING').length,
          synced: q.filter((r) => r.status === 'SYNCED').length,
          failed: q.filter((r) => r.status === 'FAILED').length,
          conflict: q.filter((r) => r.status === 'CONFLICT').length,
          total: q.length,
          last_synced: lastSynced,
        };
      }

      if (table === 'offline_buildings') {
        if (sql.includes('COUNT(*) as total')) {
          const hlbId = params[0];
          const rows = (webTables.offline_buildings || []).filter(
            (r) => r.hlb_id === hlbId
          );
          return {
            total: rows.length,
            completed: rows.filter((r) => r.status === 'COMPLETED').length,
            in_progress: rows.filter((r) => r.status === 'IN_PROGRESS').length,
            pending: rows.filter((r) => r.status === 'PENDING').length,
            locked: rows.filter((r) => r.status === 'LOCKED').length,
            revisit: rows.filter((r) => r.status === 'REVISIT_REQUIRED').length,
          };
        }
        if (params.length > 0 && sql.includes('WHERE id = ?')) {
          return (
            webTables.offline_buildings.find((r) => r.id === params[0]) || null
          );
        }
      }

      if (table === 'offline_hlbs') {
        if (params.length > 0 && sql.includes('WHERE id = ?')) {
          return webTables.offline_hlbs.find((r) => r.id === params[0]) || null;
        }
      }

      if (table === 'offline_routes') {
        if (params.length > 0 && sql.includes('WHERE hlb_id = ?')) {
          return (
            webTables.offline_routes.find((r) => r.hlb_id === params[0]) || null
          );
        }
      }

      if (table === 'offline_gps_logs') {
        if (sql.includes('COUNT(*) as count')) {
          const hlbId = params[0];
          const count = (webTables.offline_gps_logs || []).filter(
            (r) => r.hlb_id === hlbId
          ).length;
          return { count };
        }
        if (params.length > 0 && sql.includes('WHERE hlb_id = ?')) {
          const rows = (webTables.offline_gps_logs || []).filter(
            (r) => r.hlb_id === params[0]
          );
          return rows.length > 0 ? rows[rows.length - 1] : null;
        }
      }

      if (table && webTables[table]) {
        return webTables[table][0] || null;
      }
      return null;
    },
    getAllSync: (sql: string, params: any[] = []) => {
      const table = parseTableName(sql);
      if (!table || !webTables[table]) return [];

      if (table === 'sync_queue') {
        if (sql.includes("status IN ('PENDING', 'FAILED', 'CONFLICT')")) {
          return webTables.sync_queue.filter((r) =>
            ['PENDING', 'FAILED', 'CONFLICT'].includes(r.status)
          );
        }
        return [...webTables.sync_queue];
      }

      if (table === 'offline_hlbs') {
        if (params.length > 0 && sql.includes('WHERE enumerator_id = ?')) {
          return webTables.offline_hlbs.filter(
            (r) => r.enumerator_id === params[0]
          );
        }
        return [...webTables.offline_hlbs];
      }

      if (table === 'offline_buildings') {
        if (params.length > 0 && sql.includes('WHERE hlb_id = ?')) {
          return webTables.offline_buildings.filter(
            (r) => r.hlb_id === params[0]
          );
        }
        return [...webTables.offline_buildings];
      }

      if (table === 'offline_household_records') {
        if (params.length > 0 && sql.includes('WHERE building_id = ?')) {
          return webTables.offline_household_records.filter(
            (r) => r.building_id === params[0]
          );
        }
        if (params.length > 0 && sql.includes('WHERE census_house_id = ?')) {
          return webTables.offline_household_records.filter(
            (r) => r.census_house_id === params[0]
          );
        }
        return [...webTables.offline_household_records];
      }

      if (table === 'offline_census_houses') {
        if (params.length > 0 && sql.includes('WHERE building_id = ?')) {
          return webTables.offline_census_houses.filter(
            (r) => r.building_id === params[0]
          );
        }
        if (params.length > 0 && sql.includes('WHERE hlb_id = ?')) {
          return webTables.offline_census_houses.filter(
            (r) => r.hlb_id === params[0]
          );
        }
        return [...webTables.offline_census_houses];
      }

      if (table === 'offline_persons') {
        if (params.length > 0 && sql.includes('WHERE household_id = ?')) {
          return webTables.offline_persons.filter(
            (r) => r.household_id === params[0]
          );
        }
        return [...webTables.offline_persons];
      }

      if (table === 'offline_building_edits') {
        if (params.length > 0 && sql.includes('WHERE hlb_id = ?')) {
          return webTables.offline_building_edits.filter(
            (r) => r.hlb_id === params[0]
          );
        }
        return [...webTables.offline_building_edits];
      }

      if (table === 'offline_revisits') {
        if (params.length > 0 && sql.includes('WHERE building_id = ?')) {
          return webTables.offline_revisits.filter(
            (r) => r.building_id === params[0]
          );
        }
        return [...webTables.offline_revisits];
      }

      if (table === 'offline_gps_logs') {
        if (params.length > 0 && sql.includes('WHERE hlb_id = ?')) {
          return webTables.offline_gps_logs.filter(
            (r) => r.hlb_id === params[0]
          );
        }
        return [...webTables.offline_gps_logs];
      }

      return [...webTables[table]];
    },
    withTransactionSync: (fn: () => any) => {
      return fn();
    },
  };
}

export function getDatabase(): SQLite.SQLiteDatabase {
  if (!dbInstance) {
    if (Platform.OS === 'web' || typeof SharedArrayBuffer === 'undefined') {
      dbInstance = createWebDatabase();
    } else {
      try {
        dbInstance = SQLite.openDatabaseSync(DB_NAME);
      } catch {
        dbInstance = createWebDatabase();
      }
    }
  }
  return dbInstance;
}

export function initDatabase(): void {
  const db = getDatabase();

  // 1. Create schema_versions table if not exists
  db.execSync(`
    CREATE TABLE IF NOT EXISTS schema_versions (
      version INTEGER PRIMARY KEY,
      applied_at TEXT NOT NULL
    );
  `);

  // 2. Check current applied version
  const currentVersionRow = db.getFirstSync<{ version: number }>(
    'SELECT MAX(version) as version FROM schema_versions;'
  );
  const currentVersion = currentVersionRow?.version || 0;

  if (currentVersion < 1) {
    applyMigrationV1(db);
  }

  if (currentVersion < 2) {
    applyMigrationV2(db);
  }

  if (currentVersion < 3) {
    applyMigrationV3(db);
  }

  if (currentVersion < 4) {
    applyMigrationV4(db);
  }
}

function applyMigrationV1(db: SQLite.SQLiteDatabase): void {
  db.withTransactionSync(() => {
    // 1. Offline HLBs Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_hlbs (
        id TEXT PRIMARY KEY,
        layout_id TEXT NOT NULL,
        layout_name TEXT,
        area_name TEXT,
        block_code TEXT NOT NULL,
        name TEXT,
        status TEXT NOT NULL,
        target_building_count INTEGER NOT NULL,
        actual_building_count INTEGER NOT NULL,
        boundary_geojson TEXT NOT NULL,
        downloaded_at TEXT NOT NULL,
        enumerator_id TEXT NOT NULL
      );
    `);

    // 2. Offline Buildings Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_buildings (
        id TEXT PRIMARY KEY,
        hlb_id TEXT NOT NULL,
        building_reference TEXT NOT NULL,
        house_number TEXT,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        footprint_geojson TEXT,
        source_type TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING',
        household_count INTEGER NOT NULL DEFAULT 0,
        last_updated_at TEXT NOT NULL,
        FOREIGN KEY (hlb_id) REFERENCES offline_hlbs(id) ON DELETE CASCADE
      );
    `);

    // 3. Offline Household Records Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_household_records (
        id TEXT PRIMARY KEY,
        server_id TEXT,
        building_id TEXT NOT NULL,
        census_house_id TEXT,
        hlb_id TEXT NOT NULL,
        enumerator_id TEXT NOT NULL,
        household_number TEXT NOT NULL,
        head_name TEXT NOT NULL,
        total_members INTEGER NOT NULL,
        male_count INTEGER NOT NULL,
        female_count INTEGER NOT NULL,
        transgender_count INTEGER NOT NULL DEFAULT 0,
        ownership_status TEXT NOT NULL,
        drinking_water_source TEXT,
        lighting_source TEXT,
        latrine_facility TEXT,
        data_json TEXT,
        questionnaire_version TEXT DEFAULT '1.0',
        review_state TEXT DEFAULT 'DRAFT',
        rejection_reason TEXT,
        supervisor_comment TEXT,
        status TEXT NOT NULL DEFAULT 'DRAFT',
        source TEXT NOT NULL DEFAULT 'FORM',
        version INTEGER NOT NULL DEFAULT 1,
        sync_status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (building_id) REFERENCES offline_buildings(id) ON DELETE CASCADE,
        FOREIGN KEY (hlb_id) REFERENCES offline_hlbs(id) ON DELETE CASCADE
      );
    `);

    // 4. Offline Revisits Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_revisits (
        id TEXT PRIMARY KEY,
        building_id TEXT NOT NULL,
        hlb_id TEXT NOT NULL,
        enumerator_id TEXT NOT NULL,
        reason TEXT NOT NULL,
        notes TEXT,
        status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        resolved_at TEXT,
        FOREIGN KEY (building_id) REFERENCES offline_buildings(id) ON DELETE CASCADE,
        FOREIGN KEY (hlb_id) REFERENCES offline_hlbs(id) ON DELETE CASCADE
      );
    `);

    // 5. Offline GPS Logs Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_gps_logs (
        id TEXT PRIMARY KEY,
        hlb_id TEXT NOT NULL,
        building_id TEXT,
        enumerator_id TEXT NOT NULL,
        latitude REAL NOT NULL,
        longitude REAL NOT NULL,
        accuracy REAL,
        timestamp TEXT NOT NULL
      );
    `);

    // 6. Indexes for Fast Field Querying
    db.execSync(`
      CREATE INDEX IF NOT EXISTS idx_offline_buildings_hlb_id ON offline_buildings(hlb_id);
      CREATE INDEX IF NOT EXISTS idx_offline_buildings_status ON offline_buildings(status);
      CREATE INDEX IF NOT EXISTS idx_offline_hh_building_id ON offline_household_records(building_id);
      CREATE INDEX IF NOT EXISTS idx_offline_hh_hlb_id ON offline_household_records(hlb_id);
      CREATE INDEX IF NOT EXISTS idx_offline_revisits_building_id ON offline_revisits(building_id);
      CREATE INDEX IF NOT EXISTS idx_offline_revisits_hlb_id ON offline_revisits(hlb_id);
      CREATE INDEX IF NOT EXISTS idx_offline_gps_hlb_id ON offline_gps_logs(hlb_id);
    `);

    // 7. Record Migration
    const now = new Date().toISOString();
    db.runSync(
      'INSERT INTO schema_versions (version, applied_at) VALUES (?, ?);',
      [1, now]
    );
  });
}

function applyMigrationV2(db: SQLite.SQLiteDatabase): void {
  db.withTransactionSync(() => {
    // 1. Sync Queue Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS sync_queue (
        id TEXT PRIMARY KEY,
        idempotency_key TEXT NOT NULL UNIQUE,
        entity_type TEXT NOT NULL,
        local_entity_id TEXT NOT NULL,
        server_entity_id TEXT,
        operation_type TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'PENDING',
        attempt_count INTEGER NOT NULL DEFAULT 0,
        last_attempt_at TEXT,
        last_error TEXT,
        created_at TEXT NOT NULL,
        synced_at TEXT
      );
    `);

    // 2. Indexes for Sync Queue
    db.execSync(`
      CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status);
      CREATE INDEX IF NOT EXISTS idx_sync_queue_entity ON sync_queue(entity_type, local_entity_id);
      CREATE INDEX IF NOT EXISTS idx_sync_queue_idempotency ON sync_queue(idempotency_key);
    `);

    // 3. Record Migration V2
    const now = new Date().toISOString();
    db.runSync(
      'INSERT INTO schema_versions (version, applied_at) VALUES (?, ?);',
      [2, now]
    );
  });
}

function applyMigrationV3(db: SQLite.SQLiteDatabase): void {
  db.withTransactionSync(() => {
    // 1. Offline Routes Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_routes (
        id TEXT PRIMARY KEY,
        hlb_id TEXT NOT NULL UNIQUE,
        enumerator_id TEXT NOT NULL,
        strategy TEXT NOT NULL,
        start_lat REAL,
        start_lon REAL,
        total_distance_km REAL NOT NULL,
        baseline_distance_km REAL NOT NULL,
        building_count INTEGER NOT NULL,
        ordered_buildings_json TEXT NOT NULL,
        generated_at TEXT NOT NULL,
        FOREIGN KEY (hlb_id) REFERENCES offline_hlbs(id) ON DELETE CASCADE
      );
    `);

    // 2. Indexes for Offline Routes
    db.execSync(`
      CREATE INDEX IF NOT EXISTS idx_offline_routes_hlb_id ON offline_routes(hlb_id);
      CREATE INDEX IF NOT EXISTS idx_offline_routes_enum_id ON offline_routes(enumerator_id);
    `);

    // 3. Record Migration V3
    const now = new Date().toISOString();
    db.runSync(
      'INSERT INTO schema_versions (version, applied_at) VALUES (?, ?);',
      [3, now]
    );
  });
}

function applyMigrationV4(db: SQLite.SQLiteDatabase): void {
  db.withTransactionSync(() => {
    // 1. Alter offline_buildings to add domain fields if not already present
    try {
      db.execSync(`ALTER TABLE offline_buildings ADD COLUMN field_status TEXT DEFAULT 'UNVERIFIED';`);
    } catch {
      // Column may already exist
    }
    try {
      db.execSync(`ALTER TABLE offline_buildings ADD COLUMN listing_closed INTEGER DEFAULT 0;`);
    } catch {
      // Column may already exist
    }
    try {
      db.execSync(`ALTER TABLE offline_buildings ADD COLUMN listing_closed_at TEXT;`);
    } catch {
      // Column may already exist
    }

    // 2. Alter offline_household_records to add domain fields
    try {
      db.execSync(`ALTER TABLE offline_household_records ADD COLUMN census_house_id TEXT;`);
    } catch {
      // Column may already exist
    }
    try {
      db.execSync(`ALTER TABLE offline_household_records ADD COLUMN questionnaire_version TEXT DEFAULT '1.0';`);
    } catch {
      // Column may already exist
    }
    try {
      db.execSync(`ALTER TABLE offline_household_records ADD COLUMN review_state TEXT DEFAULT 'DRAFT';`);
    } catch {
      // Column may already exist
    }
    try {
      db.execSync(`ALTER TABLE offline_household_records ADD COLUMN rejection_reason TEXT;`);
    } catch {
      // Column may already exist
    }
    try {
      db.execSync(`ALTER TABLE offline_household_records ADD COLUMN supervisor_comment TEXT;`);
    } catch {
      // Column may already exist
    }

    // 3. Offline Census Houses Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_census_houses (
        id TEXT PRIMARY KEY,
        server_id TEXT,
        building_id TEXT NOT NULL,
        hlb_id TEXT NOT NULL,
        census_house_number TEXT NOT NULL,
        use_code TEXT NOT NULL DEFAULT 'RESIDENTIAL',
        listing_state TEXT NOT NULL DEFAULT 'NOT_VISITED',
        latitude REAL,
        longitude REAL,
        geotag_accuracy_m REAL,
        visited_at TEXT,
        locked_attempts INTEGER NOT NULL DEFAULT 0,
        notes TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (building_id) REFERENCES offline_buildings(id) ON DELETE CASCADE,
        FOREIGN KEY (hlb_id) REFERENCES offline_hlbs(id) ON DELETE CASCADE
      );
    `);

    // 4. Offline Persons Table (Phase II)
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_persons (
        id TEXT PRIMARY KEY,
        server_id TEXT,
        household_id TEXT NOT NULL,
        person_number INTEGER NOT NULL,
        name TEXT NOT NULL,
        relationship_to_head TEXT NOT NULL DEFAULT 'HEAD',
        sex TEXT NOT NULL,
        age INTEGER,
        date_of_birth TEXT,
        marital_status TEXT,
        answers_json TEXT,
        questionnaire_version TEXT NOT NULL DEFAULT '2.0',
        review_state TEXT NOT NULL DEFAULT 'DRAFT',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (household_id) REFERENCES offline_household_records(id) ON DELETE CASCADE
      );
    `);

    // 5. Offline Building Edits Table
    db.execSync(`
      CREATE TABLE IF NOT EXISTS offline_building_edits (
        id TEXT PRIMARY KEY,
        hlb_id TEXT NOT NULL,
        building_id TEXT,
        edit_type TEXT NOT NULL,
        proposed_changes_json TEXT NOT NULL,
        reason TEXT NOT NULL,
        review_status TEXT NOT NULL DEFAULT 'PENDING',
        created_at TEXT NOT NULL,
        FOREIGN KEY (hlb_id) REFERENCES offline_hlbs(id) ON DELETE CASCADE
      );
    `);

    // 6. Indexes
    db.execSync(`
      CREATE INDEX IF NOT EXISTS idx_offline_ch_building ON offline_census_houses(building_id);
      CREATE INDEX IF NOT EXISTS idx_offline_ch_hlb ON offline_census_houses(hlb_id);
      CREATE INDEX IF NOT EXISTS idx_offline_ch_state ON offline_census_houses(listing_state);
      CREATE INDEX IF NOT EXISTS idx_offline_persons_hh ON offline_persons(household_id);
      CREATE INDEX IF NOT EXISTS idx_offline_edits_hlb ON offline_building_edits(hlb_id);
      CREATE INDEX IF NOT EXISTS idx_offline_hh_ch ON offline_household_records(census_house_id);
    `);

    // 7. Record Migration V4
    const now = new Date().toISOString();
    db.runSync(
      'INSERT INTO schema_versions (version, applied_at) VALUES (?, ?);',
      [4, now]
    );
  });
}

/**
 * Testing helper: resets tables cleanly for unit/integration tests.
 */
export function resetDatabaseForTesting(): void {
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
      DELETE FROM schema_versions;
    `);
  });
  initDatabase();
}
