import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { SupervisorVerificationScreen } from '../src/features/supervisor/SupervisorVerificationScreen';
import { DeputyChangeRequestsScreen } from '../src/features/deputy/DeputyChangeRequestsScreen';
import { supervisorService } from '../src/core/supervisorService';
import { deputyService } from '../src/core/deputyService';
import { useAuthStore } from '../src/core/authStore';

const mockNavigate = jest.fn();
const mockGoBack = jest.fn();

jest.mock('@react-navigation/native', () => {
  const actual = jest.requireActual('@react-navigation/native');
  return {
    ...actual,
    useNavigation: () => ({
      navigate: mockNavigate,
      goBack: mockGoBack,
    }),
    useRoute: () => ({
      params: {
        layoutId: 'layout-test-1',
      },
    }),
  };
});

describe('Supervisor Verification & Deputy Change Requests Flow', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    useAuthStore.setState({
      user: {
        id: 'sup-user-1',
        name: 'Supervisor User',
        username: 'supervisor1',
        role: 'SUPERVISOR',
      },
      token: 'mock-token',
    });
  });

  test('1. SupervisorVerificationScreen renders submissions, verifies and returns records', async () => {
    const mockSubmissions = [
      {
        id: 'sub-1',
        house_id: 'bld-1',
        hlb_id: 'hlb-1',
        enumerator_id: 'enum-1',
        household_number: 'HH-1',
        head_name: 'Murugan',
        total_members: 4,
        male_count: 2,
        female_count: 2,
        transgender_count: 0,
        ownership_status: 'OWNED',
        drinking_water_source: 'Tap Water',
        lighting_source: 'Electricity',
        latrine_facility: 'Yes',
        status: 'COMPLETED',
        review_state: 'SUBMITTED',
        created_at: '2026-11-10T10:00:00Z',
      },
    ];

    const getSubsSpy = jest.spyOn(supervisorService, 'getSubmissions').mockResolvedValue({
      items: mockSubmissions,
      total: 1,
    });
    const verifySpy = jest.spyOn(supervisorService, 'verifySubmission').mockResolvedValue({
      id: 'sub-1',
      review_state: 'SUPERVISOR_VERIFIED',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<SupervisorVerificationScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-verification-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'tab-submissions' })).toBeDefined();
    expect(root.findByProps({ testID: 'tab-edits' })).toBeDefined();
    expect(root.findByProps({ testID: 'tab-change-requests' })).toBeDefined();
    expect(root.findByProps({ testID: 'submission-item-0' })).toBeDefined();

    // Verify submission button
    const verifyBtn = root.findByProps({ testID: 'verify-sub-btn-0' });
    await ReactTestRenderer.act(async () => {
      verifyBtn.props.onPress();
    });

    expect(verifySpy).toHaveBeenCalledWith('sub-1', expect.any(String));
  });

  test('2. DeputyChangeRequestsScreen renders requests and allows approval', async () => {
    const mockRequests = [
      {
        id: 'cr-1',
        layout_id: 'layout-test-1',
        requesting_user_id: 'sup-user-1',
        request_type: 'ADDITIONAL_ENUMERATOR',
        description: 'Need extra enumerator due to high building density',
        status: 'OPEN',
        created_at: '2026-11-10T11:00:00Z',
      },
    ];

    const getCrSpy = jest.spyOn(deputyService, 'getChangeRequests').mockResolvedValue({
      items: mockRequests,
      total: 1,
    });
    const resolveSpy = jest.spyOn(deputyService, 'resolveChangeRequest').mockResolvedValue({
      id: 'cr-1',
      status: 'RESOLVED',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<DeputyChangeRequestsScreen />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'deputy-change-requests-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'deputy-cr-item-0' })).toBeDefined();

    // Open resolve modal
    const approveBtn = root.findByProps({ testID: 'approve-cr-btn-0' });
    ReactTestRenderer.act(() => {
      approveBtn.props.onPress();
    });

    // Confirm resolve
    const confirmBtn = root.findByProps({ testID: 'confirm-resolve-btn' });
    await ReactTestRenderer.act(async () => {
      confirmBtn.props.onPress();
    });

    expect(resolveSpy).toHaveBeenCalledWith('cr-1', {
      approved: true,
      resolution_notes: expect.any(String),
    });
  });
});

