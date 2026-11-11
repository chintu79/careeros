import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { AppHeader } from '../components/navigation/AppHeader';
import { NotificationItem } from '../types';

const mockNotifications: NotificationItem[] = [
  {
    id: 1,
    title: 'Match Score Updated',
    message: 'Your profile scored 94% on Google SWE Intern.',
    is_read: false,
    created_at: '2026-11-08T10:00:00Z',
    notification_type: 'match_update',
  },
];

describe('AppHeader Component', () => {
  const defaultProps = {
    currentTab: 'discover',
    onOpenMobileSidebar: vi.fn(),
    onOpenCommandPalette: vi.fn(),
    onOpenShortcuts: vi.fn(),
    onOpenImportModal: vi.fn(),
    onSyncAll: vi.fn().mockResolvedValue(undefined),
    isSyncing: false,
    notifications: mockNotifications,
    unreadCount: 1,
    onMarkNotificationRead: vi.fn(),
    onMarkAllRead: vi.fn(),
    activeUserId: 1,
    onSwitchCandidate: vi.fn(),
    onLogout: vi.fn(),
  };

  it('renders breadcrumb and active section label', () => {
    render(<AppHeader {...defaultProps} currentTab="discover" />);

    expect(screen.getByText('Discover')).toBeInTheDocument();
    expect(screen.getByText('CareerOS')).toBeInTheDocument();
  });

  it('opens account context menu and triggers onSwitchCandidate', () => {
    render(<AppHeader {...defaultProps} activeUserId={1} />);

    // Click candidate context dropdown button
    const userBtn = screen.getByTitle(/candidate profile context/i);
    fireEvent.click(userBtn);

    expect(screen.getByText(/Candidate Profile Context/i)).toBeInTheDocument();
    expect(screen.getByText('Candidate One')).toBeInTheDocument();
    expect(screen.getByText('Candidate B (Demo)')).toBeInTheDocument();

    // Click Candidate B
    const candidateBBtn = screen.getByRole('menuitem', { name: /candidate b/i });
    fireEvent.click(candidateBBtn);

    expect(defaultProps.onSwitchCandidate).toHaveBeenCalledWith(2);
  });

  it('triggers onLogout when Sign out button is clicked', () => {
    render(<AppHeader {...defaultProps} />);

    const userBtn = screen.getByTitle(/candidate profile context/i);
    fireEvent.click(userBtn);

    const logoutBtn = screen.getByRole('menuitem', { name: /sign out/i });
    fireEvent.click(logoutBtn);

    expect(defaultProps.onLogout).toHaveBeenCalledTimes(1);
  });

  it('displays unread notifications and marks notification read on click', () => {
    render(<AppHeader {...defaultProps} />);

    const notifBtn = screen.getByLabelText(/1 notifications/i);
    fireEvent.click(notifBtn);

    expect(screen.getByText('Match Score Updated')).toBeInTheDocument();
    expect(screen.getByText(/Your profile scored 94%/i)).toBeInTheDocument();

    const notifItem = screen.getByLabelText(/Match Score Updated/i);
    fireEvent.click(notifItem);

    expect(defaultProps.onMarkNotificationRead).toHaveBeenCalledWith(1);
  });
});
