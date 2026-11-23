import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import App from '../App';

// Mock Expo and network dependencies
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

describe('App Root', () => {
  beforeAll(() => {
    jest.useFakeTimers();
  });

  afterAll(() => {
    jest.useRealTimers();
  });

  test('renders correctly', async () => {
    await ReactTestRenderer.act(async () => {
      ReactTestRenderer.create(<App />);
    });
  });
});
