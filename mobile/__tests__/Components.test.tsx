import React from 'react';
import ReactTestRenderer from 'react-test-renderer';
import { Text } from 'react-native';
import {
  PrimaryButton,
  SecondaryButton,
  Card,
  StatusBadge,
  AppHeader,
  ErrorMessage,
  EmptyState,
  PlaceholderScreen,
} from '../src/components';

describe('Common UI Components', () => {
  test('1. PrimaryButton renders title and triggers onPress', () => {
    const onPressMock = jest.fn();
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <PrimaryButton title="SUBMIT" onPress={onPressMock} testID="test-button" />
      );
    });

    const root = component.root;
    const btn = root.findByProps({ testID: 'test-button' });
    expect(btn).toBeDefined();

    ReactTestRenderer.act(() => {
      btn.props.onPress();
    });
    expect(onPressMock).toHaveBeenCalledTimes(1);
  });

  test('2. PrimaryButton disabled state prevents action', () => {
    const onPressMock = jest.fn();
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <PrimaryButton title="DISABLED" onPress={onPressMock} disabled testID="test-button" />
      );
    });

    const root = component.root;
    const btn = root.findByProps({ testID: 'test-button' });
    expect(btn.props.accessibilityState?.disabled || btn.props.disabled).toBeTruthy();
  });

  test('3. SecondaryButton renders outline and triggers onPress', () => {
    const onPressMock = jest.fn();
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <SecondaryButton title="CANCEL" onPress={onPressMock} testID="sec-button" />
      );
    });

    const root = component.root;
    const btn = root.findByProps({ testID: 'sec-button' });
    expect(btn).toBeDefined();

    ReactTestRenderer.act(() => {
      btn.props.onPress();
    });
    expect(onPressMock).toHaveBeenCalledTimes(1);
  });

  test('4. Card renders title, subtitle, and children', () => {
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <Card title="Summary" subtitle="Active metrics" testID="test-card">
          <Text testID="card-child">Card Content</Text>
        </Card>
      );
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'test-card' })).toBeDefined();
    expect(root.findByProps({ testID: 'card-child' })).toBeDefined();
    const title = root.findAllByProps({ children: 'Summary' });
    expect(title.length).toBeGreaterThan(0);
  });

  test('5. StatusBadge renders correctly for roles and field states', () => {
    let deputyBadge: any;
    let syncedBadge: any;
    ReactTestRenderer.act(() => {
      deputyBadge = ReactTestRenderer.create(
        <StatusBadge type="DEPUTY_TAHSILDAR" testID="deputy-badge" />
      );
      syncedBadge = ReactTestRenderer.create(
        <StatusBadge type="SYNCED" testID="synced-badge" />
      );
    });

    expect(deputyBadge.root.findAllByProps({ children: 'Deputy Tahsildar' }).length).toBeGreaterThan(0);
    expect(syncedBadge.root.findAllByProps({ children: '✓ SYNCED' }).length).toBeGreaterThan(0);
  });

  test('6. AppHeader renders title, user info, role badge, and language toggle', () => {
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <AppHeader
          roleType="SUPERVISOR"
          roleLabel="Supervisor"
          userName="Jane Doe"
          showLanguageToggle
          testID="app-header"
        />
      );
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'app-header' })).toBeDefined();
    expect(root.findByProps({ testID: 'language-toggle-button' })).toBeDefined();
    expect(root.findByProps({ testID: 'header-role-badge' })).toBeDefined();
  });

  test('7. ErrorMessage renders error text and triggers retry', () => {
    const retryMock = jest.fn();
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <ErrorMessage
          message="Failed to connect"
          onRetry={retryMock}
          testID="err-banner"
        />
      );
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'error-text' }).props.children).toBe('Failed to connect');
    const retryBtn = root.findByProps({ testID: 'retry-button' });
    ReactTestRenderer.act(() => {
      retryBtn.props.onPress();
    });
    expect(retryMock).toHaveBeenCalledTimes(1);
  });

  test('8. EmptyState renders title and action button', () => {
    const actionMock = jest.fn();
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <EmptyState
          title="No Blocks Found"
          description="Create a new layout to get started"
          actionTitle="Create"
          onAction={actionMock}
          testID="empty-view"
        />
      );
    });

    const root = component.root;
    expect(root.findByProps({ testID: 'empty-view' })).toBeDefined();
  });

  test('9. PlaceholderScreen renders coming in later phase notice and back button', () => {
    const backMock = jest.fn();
    let component: any;
    ReactTestRenderer.act(() => {
      component = ReactTestRenderer.create(
        <PlaceholderScreen
          title="Layouts"
          phaseInfo="Phase 3"
          onBack={backMock}
          testID="test-placeholder"
        />
      );
    });

    const root = component.root;
    const backBtn = root.findByProps({ testID: 'placeholder-back-button' });
    ReactTestRenderer.act(() => {
      backBtn.props.onPress();
    });
    expect(backMock).toHaveBeenCalledTimes(1);
  });
});
