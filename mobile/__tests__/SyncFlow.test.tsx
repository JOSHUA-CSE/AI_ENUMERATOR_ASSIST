import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { resetDatabaseForTesting, initDatabase } from '../src/core/sqlite/database';
import { offlineRepository } from '../src/core/sqlite/offlineRepositories';
import { syncQueueRepository } from '../src/core/sqlite/syncQueueRepository';
import { syncService } from '../src/core/syncService';
import { fieldworkService } from '../src/core/fieldworkService';
import { apiClient } from '../src/core/apiClient';
import { useAuthStore } from '../src/core/authStore';
import { EnumeratorDashboardScreen } from '../src/features/enumerator/EnumeratorDashboardScreen';

// Mock navigation
const mockNavigate = jest.fn();
jest.mock('@react-navigation/native', () => {
  const actualNav = jest.requireActual('@react-navigation/native');
  return {
    ...actualNav,
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: jest.fn(),
      addListener: jest.fn(() => jest.fn()),
    }),
    useRoute: () => ({
      params: {
        hlbId: 'hlb-sync-1',
        blockCode: 'HLB-SYNC-001',
      },
    }),
    useFocusEffect: (cb: any) => {
      const React = require('react');
      React.useEffect(() => {
        const cleanup = cb();
        return () => {
          if (typeof cleanup === 'function') cleanup();
        };
      }, []);
    },
  };
});

jest.mock('../src/components/HlbSpatialMap', () => {
  const React = require('react');
  const { View } = require('react-native');
  return {
    HlbSpatialMap: (props: any) => <View testID={props.testID || 'hlb-spatial-map'} />,
  };
});

describe('Phase 9 — Offline Data Synchronization Test Suite', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    resetDatabaseForTesting();

    useAuthStore.setState({
      user: {
        id: 'enum-test-user-1',
        name: 'Ravi Kumar',
        username: 'ravi_enum',
        role: 'ENUMERATOR',
      },
      token: 'mock-jwt-token',
      status: 'authenticated',
      error: null,
    });

    // Seed downloaded HLB & building
    offlineRepository.saveDownloadedHlb(
      {
        id: 'hlb-sync-1',
        layout_id: 'layout-sync-1',
        layout_name: 'Ward 5',
        area_name: 'Salem North',
        block_code: 'HLB-SYNC-001',
        name: 'Block 1',
        status: 'ASSIGNED',
        target_building_count: 150,
        actual_building_count: 2,
        boundary: { type: 'Polygon', coordinates: [] },
      },
      [
        {
          id: 'bld-s-101',
          building_reference: 'BLD-S-101',
          house_number: '101',
          latitude: 13.01,
          longitude: 80.01,
        },
      ],
      'enum-test-user-1'
    );
  });

  test('1. Fieldwork operations automatically enqueue into SQLite sync_queue', () => {
    // 1. Save Household
    offlineRepository.saveHouseholdRecord({
      id: 'hh-sync-local-1',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      household_number: 'HH-1',
      head_name: 'Ravi Kumar',
      total_members: 4,
      male_count: 2,
      female_count: 2,
      transgender_count: 0,
      ownership_status: 'OWNED',
      drinking_water_source: 'Tap Water',
      lighting_source: 'Electricity',
      latrine_facility: 'Yes',
      data_json: null,
      status: 'COMPLETED',
      source: 'FORM',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    // 2. Save Revisit
    offlineRepository.saveRevisitRecord({
      id: 'rev-sync-local-1',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      reason: 'LOCKED',
      notes: 'Front gate locked',
      status: 'PENDING',
      created_at: new Date().toISOString(),
      resolved_at: null,
    });

    // 3. Save GPS Log
    offlineRepository.saveGpsLog({
      id: 'gps-sync-local-1',
      hlb_id: 'hlb-sync-1',
      building_id: 'bld-s-101',
      enumerator_id: 'enum-test-user-1',
      latitude: 13.012,
      longitude: 80.012,
      accuracy: 5.0,
      timestamp: new Date().toISOString(),
    });

    // Check Sync Queue
    const pending = syncQueueRepository.getPendingOperations();
    expect(pending.length).toBe(3);

    const types = pending.map((p) => p.entity_type);
    expect(types).toContain('HOUSEHOLD');
    expect(types).toContain('REVISIT');
    expect(types).toContain('GPS_LOG');

    const stats = syncQueueRepository.getSyncQueueStats();
    expect(stats.pendingCount).toBe(3);
    expect(stats.syncedCount).toBe(0);
  });

  test('2. Successful syncBatch updates sync_queue to SYNCED and stores server_id', async () => {
    // Seed a household
    offlineRepository.saveHouseholdRecord({
      id: 'hh-sync-local-2',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      household_number: 'HH-1',
      head_name: 'Lakshmi Narayanan',
      total_members: 3,
      male_count: 1,
      female_count: 2,
      transgender_count: 0,
      ownership_status: 'OWNED',
      drinking_water_source: 'Tap Water',
      lighting_source: 'Electricity',
      latrine_facility: 'Yes',
      data_json: null,
      status: 'COMPLETED',
      source: 'FORM',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    const pending = syncQueueRepository.getPendingOperations();
    expect(pending.length).toBe(1);

    const idempotencyKey = pending[0].idempotency_key;

    // Mock successful backend response
    jest.spyOn(apiClient, 'post').mockResolvedValueOnce({
      results: [
        {
          idempotency_key: idempotencyKey,
          status: 'SUCCESS',
          entity_type: 'HOUSEHOLD',
          local_entity_id: 'hh-sync-local-2',
          server_entity_id: 'server-uuid-999',
          version: 1,
          server_timestamp: new Date().toISOString(),
        },
      ],
      processed_count: 1,
      success_count: 1,
      failed_count: 0,
      conflict_count: 0,
      synced_at: new Date().toISOString(),
    } as any);

    const result = await syncService.syncBatch();
    expect(result.success).toBe(true);
    expect(result.successCount).toBe(1);

    // Verify queue item updated in SQLite
    const stats = syncQueueRepository.getSyncQueueStats();
    expect(stats.pendingCount).toBe(0);
    expect(stats.syncedCount).toBe(1);

    // Verify local household updated with server_id
    const bldDetail = offlineRepository.getOfflineBuildingDetail('bld-s-101');
    const hh = bldDetail.households.find((h) => h.id === 'hh-sync-local-2');
    expect(hh?.server_id).toBe('server-uuid-999');
    expect(hh?.sync_status).toBe('SYNCED');
  });

  test('3. Failed sync marks queue items FAILED and preserves local data', async () => {
    offlineRepository.saveHouseholdRecord({
      id: 'hh-sync-fail-1',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      household_number: 'HH-1',
      head_name: 'Test Name',
      total_members: 1,
      male_count: 1,
      female_count: 0,
      transgender_count: 0,
      ownership_status: 'OWNED',
      drinking_water_source: 'Tap',
      lighting_source: 'Electricity',
      latrine_facility: 'Yes',
      data_json: null,
      status: 'DRAFT',
      source: 'FORM',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    // Mock network failure
    jest.spyOn(apiClient, 'post').mockRejectedValueOnce(new Error('Network request failed'));

    const result = await syncService.syncBatch();
    expect(result.success).toBe(false);

    // Verify stats show FAILED
    const stats = syncQueueRepository.getSyncQueueStats();
    expect(stats.failedCount).toBe(1);

    // Verify local data is still safely stored in SQLite
    const bldDetail = offlineRepository.getOfflineBuildingDetail('bld-s-101');
    expect(bldDetail.households.length).toBe(1);
    expect(bldDetail.households[0].head_name).toBe('Test Name');
  });

  test('4. retryFailed resets FAILED items to PENDING and re-runs sync', async () => {
    offlineRepository.saveHouseholdRecord({
      id: 'hh-sync-retry-1',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      household_number: 'HH-1',
      head_name: 'Retry Name',
      total_members: 1,
      male_count: 1,
      female_count: 0,
      transgender_count: 0,
      ownership_status: 'OWNED',
      drinking_water_source: 'Tap',
      lighting_source: 'Electricity',
      latrine_facility: 'Yes',
      data_json: null,
      status: 'DRAFT',
      source: 'FORM',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    // Fail first
    jest.spyOn(apiClient, 'post').mockRejectedValueOnce(new Error('Timeout'));
    await syncService.syncBatch();

    let stats = syncQueueRepository.getSyncQueueStats();
    expect(stats.failedCount).toBe(1);

    // Mock success on retry
    const pending = syncQueueRepository.getPendingOperations();
    const idemKey = pending[0].idempotency_key;
    jest.spyOn(apiClient, 'post').mockResolvedValueOnce({
      results: [
        {
          idempotency_key: idemKey,
          status: 'SUCCESS',
          entity_type: 'HOUSEHOLD',
          local_entity_id: 'hh-sync-retry-1',
          server_entity_id: 'server-uuid-retry-ok',
          version: 1,
          server_timestamp: new Date().toISOString(),
        },
      ],
      processed_count: 1,
      success_count: 1,
      failed_count: 0,
      conflict_count: 0,
      synced_at: new Date().toISOString(),
    } as any);

    const retryResult = await syncService.retryFailed();
    expect(retryResult.success).toBe(true);
    expect(retryResult.successCount).toBe(1);

    stats = syncQueueRepository.getSyncQueueStats();
    expect(stats.failedCount).toBe(0);
    expect(stats.syncedCount).toBe(1);
  });

  test('5. Conflict response marks queue item as CONFLICT without losing local data', async () => {
    offlineRepository.saveHouseholdRecord({
      id: 'hh-conflict-local-1',
      server_id: 'server-uuid-exist',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      household_number: 'HH-1',
      head_name: 'Local Modified Name',
      total_members: 2,
      male_count: 1,
      female_count: 1,
      transgender_count: 0,
      ownership_status: 'OWNED',
      drinking_water_source: 'Tap',
      lighting_source: 'Electricity',
      latrine_facility: 'Yes',
      data_json: null,
      status: 'COMPLETED',
      source: 'FORM',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    const pending = syncQueueRepository.getPendingOperations();
    const idemKey = pending[0].idempotency_key;

    jest.spyOn(apiClient, 'post').mockResolvedValueOnce({
      results: [
        {
          idempotency_key: idemKey,
          status: 'CONFLICT',
          entity_type: 'HOUSEHOLD',
          local_entity_id: 'hh-conflict-local-1',
          server_entity_id: 'server-uuid-exist',
          version: 3,
          server_timestamp: new Date().toISOString(),
          error_message: 'Conflict: Server record has a newer version.',
          conflict_data: { server_version: 3, server_head_name: 'Server Head' },
        },
      ],
      processed_count: 1,
      success_count: 0,
      failed_count: 0,
      conflict_count: 1,
      synced_at: new Date().toISOString(),
    } as any);

    const res = await syncService.syncBatch();
    expect(res.success).toBe(true);
    expect(res.conflictCount).toBe(1);

    const stats = syncQueueRepository.getSyncQueueStats();
    expect(stats.conflictCount).toBe(1);

    // Local data preserved
    const bldDetail = offlineRepository.getOfflineBuildingDetail('bld-s-101');
    expect(bldDetail.households[0].head_name).toBe('Local Modified Name');
  });

  test('6. App restart recovery preserves sync queue in SQLite', () => {
    // Add item to queue
    offlineRepository.saveHouseholdRecord({
      id: 'hh-restart-1',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      household_number: 'HH-1',
      head_name: 'Surviving Restart',
      total_members: 1,
      male_count: 1,
      female_count: 0,
      transgender_count: 0,
      ownership_status: 'OWNED',
      drinking_water_source: 'Tap',
      lighting_source: 'Electricity',
      latrine_facility: 'Yes',
      data_json: null,
      status: 'DRAFT',
      source: 'FORM',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    expect(syncQueueRepository.getPendingOperations().length).toBe(1);

    // Simulate App Restart by re-initializing DB
    initDatabase();

    const pendingAfterRestart = syncQueueRepository.getPendingOperations();
    expect(pendingAfterRestart.length).toBe(1);
    expect(pendingAfterRestart[0].local_entity_id).toBe('hh-restart-1');
  });

  test('7. EnumeratorDashboardScreen renders sync card and triggers manual sync', async () => {
    // Queue an item
    offlineRepository.saveHouseholdRecord({
      id: 'hh-ui-sync-1',
      building_id: 'bld-s-101',
      hlb_id: 'hlb-sync-1',
      enumerator_id: 'enum-test-user-1',
      household_number: 'HH-1',
      head_name: 'UI Test',
      total_members: 1,
      male_count: 1,
      female_count: 0,
      transgender_count: 0,
      ownership_status: 'OWNED',
      drinking_water_source: 'Tap',
      lighting_source: 'Electricity',
      latrine_facility: 'Yes',
      data_json: null,
      status: 'DRAFT',
      source: 'FORM',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    const syncSpy = jest.spyOn(fieldworkService, 'syncNow').mockResolvedValueOnce({
      success: true,
      processedCount: 1,
      successCount: 1,
      failedCount: 0,
      conflictCount: 0,
    });

    let renderer: any;
    await ReactTestRenderer.act(async () => {
      renderer = ReactTestRenderer.create(<EnumeratorDashboardScreen />);
    });

    const syncCard = renderer.root.findAll((node: any) => node.props?.testID === 'enumerator-sync-card');
    expect(syncCard.length).toBeGreaterThan(0);

    const syncButton = renderer.root.find((node: any) => node.props?.testID === 'sync-now-button');
    expect(syncButton).toBeTruthy();

    await ReactTestRenderer.act(async () => {
      syncButton.props.onPress();
    });

    expect(syncSpy).toHaveBeenCalled();
  });
});
