import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import AppNavigator from '../src/navigation/AppNavigator';
import { useAuthStore } from '../src/core/authStore';
import { secureStore } from '../src/core/secureStore';
import { apiClient } from '../src/core/apiClient';

// Mock Expo, secure-store and health dependencies
jest.mock('expo-secure-store', () => ({
  setItemAsync: jest.fn().mockResolvedValue(undefined),
  getItemAsync: jest.fn().mockResolvedValue(null),
  deleteItemAsync: jest.fn().mockResolvedValue(undefined),
}));

jest.mock('../src/core/healthService', () => ({
  healthService: {
    getHealth: jest.fn().mockResolvedValue({ status: 'ok' }),
  },
}));

describe('AppNavigator & Role-Based Navigation Architecture', () => {
  beforeAll(() => {
    jest.useFakeTimers();
  });

  afterAll(() => {
    jest.useRealTimers();
  });

  beforeEach(async () => {
    await ReactTestRenderer.act(async () => {
      useAuthStore.getState().reset();
    });
    jest.clearAllMocks();
  });

  test('1. unauthenticated user redirected to AuthNavigator / Login screen', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue(null);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    const usernameInput = root.findByProps({ testID: 'username-input' });
    expect(usernameInput).toBeDefined();
  });

  test('2. session restoration and routing to DeputyNavigator (DEPUTY_TAHSILDAR)', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue('deputy_token');
    jest.spyOn(apiClient, 'get').mockResolvedValue({
      id: 'deputy-123',
      name: 'Deputy Officer',
      username: 'deputy',
      role: 'DEPUTY_TAHSILDAR',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'deputy-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'nav-layouts-button' })).toBeDefined();
    expect(root.findByProps({ testID: 'nav-supervisors-button' })).toBeDefined();
    expect(root.findByProps({ testID: 'nav-progress-button' })).toBeDefined();
  });

  test('3. session restoration and routing to SupervisorNavigator (SUPERVISOR)', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue('supervisor_token');
    jest.spyOn(apiClient, 'get').mockResolvedValue({
      id: 'sup-123',
      name: 'Field Supervisor',
      username: 'supervisor',
      role: 'SUPERVISOR',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'supervisor-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'user-profile-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'layouts-summary-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'assigned-layouts-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'logout-button' })).toBeDefined();
  });

  test('4. session restoration and routing to EnumeratorNavigator (ENUMERATOR)', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue('enum_token');
    jest.spyOn(apiClient, 'get').mockResolvedValue({
      id: 'enum-123',
      name: 'Field Enumerator',
      username: 'enumerator',
      role: 'ENUMERATOR',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-dashboard-screen' })).toBeDefined();
    expect(root.findByProps({ testID: 'user-profile-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'enumerator-assignment-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'fieldwork-status-card' })).toBeDefined();
  });

  test('5. logout clears session and resets navigation state to Login', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue('enum_token');
    jest.spyOn(apiClient, 'get').mockResolvedValue({
      id: 'enum-123',
      name: 'Field Enumerator',
      username: 'enumerator',
      role: 'ENUMERATOR',
    });
    const logoutApiMock = jest.spyOn(apiClient, 'post').mockResolvedValue({ status: 'ok' });
    const clearTokenMock = jest.spyOn(secureStore, 'clearToken').mockResolvedValue(true);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'enumerator-dashboard-screen' })).toBeDefined();

    const logoutBtn = root.findByProps({ testID: 'logout-button' });
    await ReactTestRenderer.act(async () => {
      await logoutBtn.props.onPress();
    });

    expect(logoutApiMock).toHaveBeenCalledTimes(1);
    expect(clearTokenMock).toHaveBeenCalledTimes(1);

    const usernameInput = root.findByProps({ testID: 'username-input' });
    expect(usernameInput).toBeDefined();
  });

  test('6. invalid/expired session clears local token and redirects to Login', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue('expired_token');
    jest.spyOn(apiClient, 'get').mockRejectedValue({
      status: 401,
      message: 'Token expired or invalid',
    });
    const clearTokenMock = jest.spyOn(secureStore, 'clearToken').mockResolvedValue(true);

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    expect(clearTokenMock).toHaveBeenCalled();
    const usernameInput = root.findByProps({ testID: 'username-input' });
    expect(usernameInput).toBeDefined();
  });

  test('7. navigating to placeholder screen within role navigator works', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue('deputy_token');
    jest.spyOn(apiClient, 'get').mockResolvedValue({
      id: 'deputy-123',
      name: 'Deputy Officer',
      username: 'deputy',
      role: 'DEPUTY_TAHSILDAR',
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    const supervisorsBtn = root.findByProps({ testID: 'nav-supervisors-button' });

    await ReactTestRenderer.act(async () => {
      supervisorsBtn.props.onPress();
    });

    expect(root.findByProps({ testID: 'supervisors-placeholder-screen' })).toBeDefined();
  });

  test('8. corrupted or unknown role falls back safely to AuthNavigator', async () => {
    jest.spyOn(secureStore, 'getToken').mockResolvedValue('unknown_token');
    jest.spyOn(apiClient, 'get').mockResolvedValue({
      id: 'unknown-123',
      name: 'Unknown Role User',
      username: 'unknown',
      role: 'UNKNOWN_ROLE' as any,
    });

    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<AppNavigator />);
    });

    const root = component.root;
    const usernameInput = root.findByProps({ testID: 'username-input' });
    expect(usernameInput).toBeDefined();
  });
});
