import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import LoginScreen from '../src/features/authentication/LoginScreen';
import { sessionService } from '../src/core/sessionService';
import { useLanguageStore } from '../src/core/localization';

// Mock dependencies
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

describe('LoginScreen', () => {
  beforeAll(() => {
    jest.useFakeTimers();
  });

  afterAll(() => {
    jest.useRealTimers();
  });

  beforeEach(async () => {
    jest.clearAllMocks();
    await ReactTestRenderer.act(async () => {
      useLanguageStore.getState().setLanguage('en');
    });
  });

  test('1. renders correctly with labels, inputs and login button', async () => {
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<LoginScreen onLoginSuccess={jest.fn()} />);
    });
    const root = component.root;

    // Check title
    const titleText = root.findAllByProps({ children: 'AI-Enumerator Assistant' });
    expect(titleText.length).toBeGreaterThan(0);

    // Check input presence
    const usernameInput = root.findByProps({ testID: 'username-input' });
    const passwordInput = root.findByProps({ testID: 'password-input' });
    expect(usernameInput).toBeDefined();
    expect(passwordInput).toBeDefined();

    // Check login button
    const loginButton = root.findByProps({ testID: 'login-button' });
    expect(loginButton).toBeDefined();
  });

  test('2. allows user to enter credentials', async () => {
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<LoginScreen onLoginSuccess={jest.fn()} />);
    });
    const root = component.root;

    const usernameInput = root.findByProps({ testID: 'username-input' });
    const passwordInput = root.findByProps({ testID: 'password-input' });

    await ReactTestRenderer.act(async () => {
      usernameInput.props.onChangeText('testuser');
      passwordInput.props.onChangeText('password123');
    });

    expect(usernameInput.props.value).toBe('testuser');
    expect(passwordInput.props.value).toBe('password123');
  });

  test('3. triggers login success flow', async () => {
    const loginMock = jest.spyOn(sessionService, 'login').mockResolvedValue({
      token: 'valid_token',
      user: {
        id: '1',
        name: 'Test User',
        username: 'testuser',
        role: 'ENUMERATOR',
      },
    });

    const onLoginSuccessMock = jest.fn();
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<LoginScreen onLoginSuccess={onLoginSuccessMock} />);
    });
    const root = component.root;

    const usernameInput = root.findByProps({ testID: 'username-input' });
    const passwordInput = root.findByProps({ testID: 'password-input' });
    const loginButton = root.findByProps({ testID: 'login-button' });

    await ReactTestRenderer.act(async () => {
      usernameInput.props.onChangeText('testuser');
      passwordInput.props.onChangeText('password123');
    });

    await ReactTestRenderer.act(async () => {
      await loginButton.props.onPress();
    });

    expect(loginMock).toHaveBeenCalledTimes(1);
    expect(loginMock).toHaveBeenCalledWith('testuser', 'password123');
    expect(onLoginSuccessMock).toHaveBeenCalledTimes(1);
  });

  test('4. handles login failure and displays error message', async () => {
    const loginMock = jest.spyOn(sessionService, 'login').mockRejectedValue({
      status: 401,
      message: 'Invalid user ID or password.',
    });

    const onLoginSuccessMock = jest.fn();
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<LoginScreen onLoginSuccess={onLoginSuccessMock} />);
    });
    const root = component.root;

    const usernameInput = root.findByProps({ testID: 'username-input' });
    const passwordInput = root.findByProps({ testID: 'password-input' });
    const loginButton = root.findByProps({ testID: 'login-button' });

    await ReactTestRenderer.act(async () => {
      usernameInput.props.onChangeText('testuser');
      passwordInput.props.onChangeText('wrong_password');
    });

    await ReactTestRenderer.act(async () => {
      await loginButton.props.onPress();
    });

    expect(loginMock).toHaveBeenCalledTimes(1);
    expect(onLoginSuccessMock).toHaveBeenCalledTimes(0);

    const errorMsg = root.findByProps({ testID: 'error-message' });
    expect(errorMsg.props.children).toBe('Invalid user ID or password.');
  });

  test('5. language toggle switches text between English and Tamil', async () => {
    let component: any;
    await ReactTestRenderer.act(async () => {
      component = ReactTestRenderer.create(<LoginScreen onLoginSuccess={jest.fn()} />);
    });
    const root = component.root;

    const langToggle = root.findByProps({ testID: 'language-toggle-button' });
    expect(langToggle).toBeDefined();

    // Toggle to Tamil
    await ReactTestRenderer.act(async () => {
      langToggle.props.onPress();
    });

    expect(useLanguageStore.getState().language).toBe('ta');
    const tamilTitle = root.findAllByProps({ children: 'AI-கணக்கெடுப்பாளர் உதவியாளர்' });
    expect(tamilTitle.length).toBeGreaterThan(0);
  });
});
