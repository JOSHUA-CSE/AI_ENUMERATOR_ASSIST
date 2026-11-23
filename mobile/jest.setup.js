jest.mock('react-native-maps', () => {
  const React = require('react');
  const { View } = require('react-native');

  const MockMapView = (props) =>
    React.createElement(View, { testID: props.testID || 'mock-map-view' }, props.children);
  const MockPolygon = (props) =>
    React.createElement(View, { testID: props.testID || 'mock-polygon', ...props });
  const MockMarker = (props) =>
    React.createElement(View, { testID: props.testID || 'mock-marker', ...props }, props.children);
  const MockCallout = (props) =>
    React.createElement(View, { testID: props.testID || 'mock-callout', ...props }, props.children);

  const MockUrlTile = (props) =>
    React.createElement(View, { testID: props.testID || 'mock-url-tile', ...props });
  const MockCircle = (props) =>
    React.createElement(View, { testID: props.testID || 'mock-circle', ...props });

  return {
    __esModule: true,
    default: MockMapView,
    MapView: MockMapView,
    Polygon: MockPolygon,
    Marker: MockMarker,
    Callout: MockCallout,
    UrlTile: MockUrlTile,
    Circle: MockCircle,
  };
});

jest.mock('react-native-webview', () => {
  const React = require('react');
  const { View } = require('react-native');
  const MockWebView = React.forwardRef((props, ref) => {
    React.useImperativeHandle(ref, () => ({
      injectJavaScript: jest.fn(),
      reload: jest.fn(),
    }));
    return React.createElement(View, { testID: props.testID || 'mock-webview', ...props });
  });
  return {
    __esModule: true,
    default: MockWebView,
    WebView: MockWebView,
  };
});

// In-Memory SQLite Mock Store
const inMemoryTables = {
  schema_versions: [],
  offline_hlbs: [],
  offline_buildings: [],
  offline_household_records: [],
  offline_revisits: [],
  offline_gps_logs: [],
  sync_queue: [],
  offline_routes: [],
};

function parseColumns(sql) {
  const match = sql.match(/\(([^)]+)\)\s*VALUES/i);
  if (!match) return [];
  return match[1].split(',').map((c) => c.trim().replace(/^["`]|["`]$/g, ''));
}

function parseTableName(sql) {
  const insertMatch = sql.match(/INTO\s+([a-zA-Z0-9_]+)/i);
  if (insertMatch) return insertMatch[1];
  const updateMatch = sql.match(/UPDATE\s+([a-zA-Z0-9_]+)/i);
  if (updateMatch) return updateMatch[1];
  const fromMatch = sql.match(/FROM\s+([a-zA-Z0-9_]+)/i);
  if (fromMatch) return fromMatch[1];
  return null;
}

const mockDb = {
  execSync: jest.fn((sql) => {
    if (sql.includes('DELETE FROM')) {
      const deletes = sql.match(/DELETE FROM\s+([a-zA-Z0-9_]+)/gi) || [];
      for (const d of deletes) {
        const table = d.replace(/DELETE FROM\s+/i, '').trim();
        if (inMemoryTables[table]) {
          inMemoryTables[table] = [];
        }
      }
    }
  }),
  runSync: jest.fn((sql, params = []) => {
    const table = parseTableName(sql);
    if (!table || !inMemoryTables[table]) return { changes: 1, lastInsertRowId: 1 };

    if (/^INSERT/i.test(sql.trim())) {
      const cols = parseColumns(sql);
      const row = {};
      cols.forEach((col, idx) => {
        row[col] = params[idx] !== undefined ? params[idx] : null;
      });

      const pk = row.id !== undefined ? 'id' : row.version !== undefined ? 'version' : null;
      if (pk) {
        const existingIdx = inMemoryTables[table].findIndex((r) => r[pk] === row[pk]);
        if (existingIdx >= 0) {
          inMemoryTables[table][existingIdx] = { ...inMemoryTables[table][existingIdx], ...row };
        } else {
          inMemoryTables[table].push(row);
        }
      } else {
        inMemoryTables[table].push(row);
      }
      return { changes: 1, lastInsertRowId: inMemoryTables[table].length };
    }

    if (/^UPDATE/i.test(sql.trim())) {
      if (table === 'sync_queue') {
        if (sql.includes("status = 'SYNCING'")) {
          const now = params[0];
          const idemKey = params[1];
          const item = inMemoryTables.sync_queue.find((r) => r.idempotency_key === idemKey);
          if (item) {
            item.status = 'SYNCING';
            item.attempt_count = (item.attempt_count || 0) + 1;
            item.last_attempt_at = now;
          }
        } else if (sql.includes("status = 'SYNCED'")) {
          const serverId = params[0];
          const syncedAt = params[1];
          const idemKey = params[2];
          const item = inMemoryTables.sync_queue.find((r) => r.idempotency_key === idemKey);
          if (item) {
            item.status = 'SYNCED';
            if (serverId) item.server_entity_id = serverId;
            item.synced_at = syncedAt;
            item.last_error = null;
          }
        } else if (sql.includes("status = 'FAILED'")) {
          const err = params[0];
          const idemKey = params[1];
          const item = inMemoryTables.sync_queue.find((r) => r.idempotency_key === idemKey);
          if (item) {
            item.status = 'FAILED';
            item.last_error = err;
          }
        } else if (sql.includes("status = 'CONFLICT'")) {
          const err = params[0];
          const idemKey = params[1];
          const item = inMemoryTables.sync_queue.find((r) => r.idempotency_key === idemKey);
          if (item) {
            item.status = 'CONFLICT';
            item.last_error = err;
          }
        } else if (sql.includes("SET status = 'PENDING' WHERE status = 'FAILED'")) {
          inMemoryTables.sync_queue.forEach((r) => {
            if (r.status === 'FAILED') r.status = 'PENDING';
          });
        }
      } else if (table === 'offline_household_records') {
        if (sql.includes("SET server_id = ?")) {
          const serverId = params[0];
          const version = params[1];
          const updatedAt = params[2];
          const id = params[3];
          const item = inMemoryTables.offline_household_records.find((r) => r.id === id);
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
        const item = inMemoryTables.offline_buildings.find((r) => r.id === id);
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
        inMemoryTables[table] = inMemoryTables[table].filter((r) => r.id !== params[0]);
      } else {
        inMemoryTables[table] = [];
      }
      return { changes: 1, lastInsertRowId: 0 };
    }

    return { changes: 1, lastInsertRowId: 1 };
  }),

  getFirstSync: jest.fn((sql, params = []) => {
    const table = parseTableName(sql);

    if (sql.includes('MAX(version)')) {
      const rows = inMemoryTables.schema_versions || [];
      const maxVer = rows.reduce((max, r) => Math.max(max, Number(r.version) || 0), 0);
      return maxVer > 0 ? { version: maxVer } : null;
    }

    if (table === 'sync_queue' && sql.includes('SUM(CASE')) {
      const q = inMemoryTables.sync_queue || [];
      const syncedItems = q.filter((r) => r.synced_at);
      const lastSynced = syncedItems.reduce((latest, r) => (!latest || r.synced_at > latest ? r.synced_at : latest), null);
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

    if (table === 'offline_household_records' && sql.includes('COUNT(*) as total')) {
      const bldId = params[0];
      const items = (inMemoryTables.offline_household_records || []).filter((r) => r.building_id === bldId);
      return {
        total: items.length,
        completed: items.filter((r) => r.status === 'COMPLETED').length,
      };
    }

    if (table === 'offline_buildings' && sql.includes('COUNT(*) as total')) {
      const hlbId = params[0];
      const items = (inMemoryTables.offline_buildings || []).filter((r) => r.hlb_id === hlbId);
      return {
        total: items.length,
        completed: items.filter((r) => r.status === 'COMPLETED').length,
        pending: items.filter((r) => r.status === 'PENDING').length,
        in_progress: items.filter((r) => r.status === 'IN_PROGRESS').length,
        revisit: items.filter((r) => r.status === 'REVISIT_REQUIRED').length,
        locked: items.filter((r) => r.status === 'LOCKED').length,
      };
    }

    if (table === 'offline_gps_logs' && sql.includes('COUNT(*) as count')) {
      const hlbId = params[0];
      const count = (inMemoryTables.offline_gps_logs || []).filter((r) => r.hlb_id === hlbId).length;
      return { count };
    }

    if (!table || !inMemoryTables[table]) return null;
    const rows = inMemoryTables[table];

    if (table === 'offline_routes' && sql.includes('WHERE hlb_id = ?')) {
      return rows.find((r) => r.hlb_id === params[0]) || null;
    }
    if (sql.includes('WHERE id = ? AND enumerator_id = ?')) {
      return rows.find((r) => r.id === params[0] && r.enumerator_id === params[1]) || null;
    }
    if (sql.includes('WHERE id = ?')) {
      return rows.find((r) => r.id === params[0]) || null;
    }

    return rows[0] || null;
  }),

  getAllSync: jest.fn((sql, params = []) => {
    const table = parseTableName(sql);
    if (!table || !inMemoryTables[table]) return [];
    let rows = [...inMemoryTables[table]];

    if (table === 'sync_queue') {
      if (sql.includes("status IN ('PENDING', 'FAILED')")) {
        rows = rows.filter((r) => r.status === 'PENDING' || r.status === 'FAILED');
      }
      return rows;
    }

    if (table === 'offline_household_records') {
      if (sql.includes('WHERE building_id = ?')) {
        return rows.filter((r) => r.building_id === params[0]);
      }
      if (sql.includes('WHERE hlb_id = ?')) {
        return rows.filter((r) => r.hlb_id === params[0]);
      }
    }

    if (table === 'offline_buildings') {
      if (sql.includes('WHERE hlb_id = ?')) {
        return rows.filter((r) => r.hlb_id === params[0]);
      }
      if (sql.includes('WHERE id = ?')) {
        return rows.filter((r) => r.id === params[0]);
      }
    }

    if (table === 'offline_hlbs') {
      if (sql.includes('WHERE enumerator_id = ?')) {
        return rows.filter((r) => r.enumerator_id === params[0]);
      }
    }

    if (table === 'offline_revisits') {
      if (sql.includes('WHERE building_id = ?')) {
        return rows.filter((r) => r.building_id === params[0]);
      }
    }

    if (table === 'offline_gps_logs') {
      if (sql.includes('WHERE hlb_id = ?')) {
        return rows.filter((r) => r.hlb_id === params[0]);
      }
    }

    return rows;
  }),

  withTransactionSync: jest.fn((callback) => callback()),
};

jest.mock('expo-sqlite', () => ({
  openDatabaseSync: jest.fn(() => mockDb),
  openDatabaseAsync: jest.fn(async () => mockDb),
}));

jest.mock('expo-location', () => ({
  requestForegroundPermissionsAsync: jest.fn(async () => ({ status: 'granted' })),
  getForegroundPermissionsAsync: jest.fn(async () => ({ status: 'granted' })),
  hasServicesEnabledAsync: jest.fn(async () => true),
  getCurrentPositionAsync: jest.fn(async () => ({
    coords: {
      latitude: 11.6643,
      longitude: 78.146,
      accuracy: 5,
    },
    timestamp: Date.now(),
  })),
  Accuracy: {
    Balanced: 3,
    High: 4,
    Low: 2,
  },
}));
