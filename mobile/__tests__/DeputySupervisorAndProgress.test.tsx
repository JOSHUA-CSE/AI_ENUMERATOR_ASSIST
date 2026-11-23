import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { DeputySupervisorsScreen } from '../src/features/deputy/DeputySupervisorsScreen';
import { DeputyProgressScreen } from '../src/features/deputy/DeputyProgressScreen';
import { LayoutListScreen } from '../src/features/deputy/LayoutListScreen';
import { supervisorService } from '../src/core/supervisorService';
import { layoutService } from '../src/core/layoutService';
import { deputyService } from '../src/core/deputyService';
import { areaService } from '../src/core/areaService';
import { useAuthStore } from '../src/core/authStore';
import { useLanguageStore } from '../src/core/localization';

const mockNavigate = jest.fn();
const mockGoBack = jest.fn();

// Mock react-navigation
jest.mock('@react-navigation/native', () => {
  const actual = jest.requireActual('@react-navigation/native');
  return {
    ...actual,
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: mockGoBack,
    }),
    useRoute: () => ({
      params: {},
    }),
  };
});

function getAllText(root: any): string {
  try {
    const textNodes = root.findAllByType('Text');
    return textNodes
      .map((n: any) => {
        const c = n.props?.children;
        if (Array.isArray(c)) {
          return c
            .map((item: any) => (typeof item === 'object' && item?.props?.children ? item.props.children : item))
            .join(' ');
        }
        return String(c ?? '');
      })
      .join(' ')
      .replace(/\s+/g, ' ');
  } catch {
    return '';
  }
}

describe('Deputy Supervisors and Progress Screens (Phase 6.1)', () => {
  beforeEach(async () => {
    jest.clearAllMocks();
    await ReactTestRenderer.act(async () => {
      useLanguageStore.setState({ language: 'en' });
      useAuthStore.setState({
        user: {
          id: 'deputy-1',
          username: 'deputy_arasur',
          name: 'Deputy Tahsildar',
          role: 'DEPUTY_TAHSILDAR',
        } as any,
        token: 'jwt-token',
        status: 'authenticated',
      });
    });
  });

  describe('DeputySupervisorsScreen', () => {
    it('renders list of supervisors with assigned layout details', async () => {
      jest.spyOn(supervisorService, 'getSupervisors').mockResolvedValue({
        items: [
          {
            id: 'sup-1',
            name: 'Rajesh Kumar',
            username: 'rajesh_sup',
            phone: '9876543210',
            role: 'SUPERVISOR',
            status: 'ACTIVE',
            assigned_layouts_count: 1,
          },
          {
            id: 'sup-2',
            name: 'Priya Sundaram',
            username: 'priya_sup',
            phone: '9876543211',
            role: 'SUPERVISOR',
            status: 'ACTIVE',
            assigned_layouts_count: 0,
          },
        ],
        total: 2,
      });

      jest.spyOn(layoutService, 'getLayouts').mockResolvedValue({
        items: [
          {
            id: 'layout-1',
            name: 'Arasur Master Layout',
            supervisor_id: 'sup-1',
            assigned_supervisor_name: 'Rajesh Kumar',
            hlb_count: 8,
            total_buildings: 2000,
            status: 'ASSIGNED',
            area_id: 'area-1',
            administrative_area_id: 'area-1',
            target_buildings_per_hlb: 250,
            active_version_number: 1,
            active_version_status: 'APPROVED',
            created_at: '2026-11-12T10:00:00Z',
            updated_at: '2026-11-12T10:00:00Z',
          },
        ],
        total: 1,
      });

      let component: any;
      await ReactTestRenderer.act(async () => {
        component = ReactTestRenderer.create(<DeputySupervisorsScreen />);
      });

      const root = component.root;
      expect(root.findByProps({ testID: 'deputy-supervisors-screen' })).toBeDefined();

      const text = getAllText(root);
      expect(text).toContain('Rajesh Kumar');
      expect(text).toContain('Priya Sundaram');
      expect(text).toContain('Arasur Master Layout');
      expect(text).toContain('8 HLBs');
      expect(text).toContain('2000 Buildings');
    });
  });

  describe('DeputyProgressScreen', () => {
    it('renders overall KPI summary and layout fieldwork progress', async () => {
      jest.spyOn(deputyService, 'getOverallProgress').mockResolvedValue({
        total_layouts: 2,
        total_hlbs: 10,
        active_hlbs: 8,
        completed_hlbs: 2,
        remaining_hlbs: 0,
        total_houses: 2500,
        completed_houses: 1800,
        remaining_houses: 700,
        locked_houses: 15,
        revisit_count: 8,
        overall_progress_percentage: 72.0,
        layouts: [
          {
            layout_id: 'l-1',
            layout_name: 'Arasur North',
            village_name: 'Arasur',
            status: 'ACTIVE',
            supervisor: { name: 'Rajesh Kumar', is_assigned: true },
            total_hlbs: 5,
            active_hlbs: 4,
            completed_hlbs: 1,
            remaining_hlbs: 0,
            total_houses: 1250,
            completed_houses: 950,
            remaining_houses: 300,
            locked_houses: 8,
            revisit_count: 5,
            overall_progress_percentage: 76.0,
          },
        ],
        last_updated: '2026-11-12T10:00:00Z',
      });

      let component: any;
      await ReactTestRenderer.act(async () => {
        component = ReactTestRenderer.create(<DeputyProgressScreen />);
      });

      const root = component.root;
      expect(root.findByProps({ testID: 'deputy-progress-screen' })).toBeDefined();

      const text = getAllText(root);
      expect(text).toContain('72% Completed');
      expect(text).toContain('Arasur North');
      expect(text).toContain('Rajesh Kumar');
      expect(text).toContain('Done');
    });
  });

  describe('LayoutListScreen Supervisor Card Button State', () => {
    it('displays assigned supervisor name and CHANGE SUPERVISOR button', async () => {
      jest.spyOn(layoutService, 'getLayouts').mockResolvedValue({
        items: [
          {
            id: 'layout-assigned-1',
            name: 'Assigned Village Layout',
            status: 'ASSIGNED',
            area_id: 'area-1',
            administrative_area_id: 'area-1',
            supervisor_id: 'sup-1',
            assigned_supervisor_name: 'Kavitha Devi',
            total_buildings: 500,
            hlb_count: 2,
            target_buildings_per_hlb: 250,
            active_version_number: 1,
            active_version_status: 'APPROVED',
            created_at: '2026-11-12T10:00:00Z',
            updated_at: '2026-11-12T10:00:00Z',
          },
        ],
        total: 1,
      });

      jest.spyOn(areaService, 'getAreas').mockResolvedValue({
        items: [{ id: 'area-1', name: 'Arasur', code: 'TN-ARA-01' } as any],
        total: 1,
        skip: 0,
        limit: 50,
      });

      let component: any;
      await ReactTestRenderer.act(async () => {
        component = ReactTestRenderer.create(<LayoutListScreen />);
      });

      const root = component.root;
      expect(root.findByProps({ testID: 'layout-list-screen' })).toBeDefined();

      const text = getAllText(root);
      expect(text).toContain('Assigned Village Layout');
      expect(text).toContain('Supervisor: Kavitha Devi');
      expect(text).toContain('CHANGE SUPERVISOR');
    });
  });
});
