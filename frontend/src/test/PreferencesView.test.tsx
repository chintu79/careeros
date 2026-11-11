import React from 'react';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PreferencesView } from '../components/preferences/PreferencesView';
import * as api from '../services/api';
import { UserPreferences, CandidateProfile } from '../types';

vi.mock('../services/api', () => ({
  fetchPreferences: vi.fn(),
  updatePreferences: vi.fn(),
  fetchCandidateProfile: vi.fn(),
}));

vi.mock('../components/sources/SourcesView', () => ({ SourcesView: () => <div>Sources panel mock</div> }));
vi.mock('../components/companies/CompanyDirectoryView', () => ({ CompanyDirectoryView: () => <div>Companies panel mock</div> }));
vi.mock('../components/preferences/IntegrationsSettingsTab', () => ({ IntegrationsSettingsTab: () => <div>Accounts panel mock</div> }));
vi.mock('../components/preferences/AIDiagnosticsCard', () => ({ AIDiagnosticsCard: () => <div>Diagnostics panel mock</div> }));

const prefs: UserPreferences = {
  id: 1,
  preferred_categories: ['Machine Learning'],
  search_priorities: [],
  preferred_locations: ['Remote, India'],
  paid_only: true,
  allow_unpaid: false,
  min_stipend: 25000,
  preferred_duration_months: 3,
  workplace_types: ['remote'],
  max_experience_years: 1,
  student_only: true,
  graduation_year: 2028,
  excluded_keywords: [],
  excluded_companies: ['BannedCorp'],
};

const candidate: CandidateProfile = {
  id: 1,
  name: 'Candidate One',
  email: 'synthetic.candidate@example.test',
  degree: 'B.Tech AI & Data Science',
  graduation_year: 2028,
  college: 'Regional University',
  cgpa: 8.5,
  location: 'Pune',
  skills: [],
  projects: [],
  experience: [],
  preferred_locations: ['Remote, India'],
  work_authorization: 'Indian Citizen',
  evidence_version: 34,
  updated_at: '2026-11-02T10:00:00',
};

describe('Settings & Account workspace', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchPreferences).mockResolvedValue({ ...prefs });
    vi.mocked(api.fetchCandidateProfile).mockResolvedValue({ ...candidate });
    vi.mocked(api.updatePreferences).mockResolvedValue({ ...prefs });
  });

  it('renders loaded criteria and account identity', async () => {
    render(<PreferencesView />);
    expect(await screen.findByText('Target Job Roles & Categories')).toBeInTheDocument();
    expect(screen.getByText('Machine Learning')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /^Account/ }));
    expect(await screen.findByText('Candidate One')).toBeInTheDocument();
    expect(screen.getByText('synthetic.candidate@example.test')).toBeInTheDocument();
    expect(screen.getByText('evidence v34')).toBeInTheDocument();
  });

  it('marks edits as unsaved and persists on Save', async () => {
    render(<PreferencesView />);
    expect(await screen.findByText('Target Job Roles & Categories')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove Machine Learning' }));
    expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();

    const save = screen.getByRole('button', { name: /Save preferences/ });
    fireEvent.click(save);
    await waitFor(() => expect(vi.mocked(api.updatePreferences)).toHaveBeenCalledTimes(1));
    expect(vi.mocked(api.updatePreferences).mock.calls[0][0].preferred_categories).toEqual([]);
    await waitFor(() => expect(screen.queryByText(/Unsaved changes/)).not.toBeInTheDocument());
  });

  it('shows an explicit error banner when save fails and keeps edits', async () => {
    vi.mocked(api.updatePreferences).mockRejectedValue(new Error('PUT /preferences 500'));
    render(<PreferencesView />);
    expect(await screen.findByText('Target Job Roles & Categories')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove Machine Learning' }));
    fireEvent.click(screen.getByRole('button', { name: /Save preferences/ }));

    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('Save failed');
    expect(alert.textContent).toContain('500');
    expect(screen.getByText(/Unsaved changes/)).toBeInTheDocument();
  });

  it('confirms before leaving criteria with unsaved changes', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<PreferencesView />);
    expect(await screen.findByText('Target Job Roles & Categories')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Remove Machine Learning' }));
    fireEvent.click(screen.getByRole('button', { name: /Connected accounts/ }));
    expect(confirmSpy).toHaveBeenCalled();
    expect(screen.getByText('Target Job Roles & Categories')).toBeInTheDocument(); // stayed put
    expect(screen.queryByText('Accounts panel mock')).not.toBeInTheDocument();

    confirmSpy.mockReturnValue(true);
    fireEvent.click(screen.getByRole('button', { name: /Connected accounts/ }));
    expect(await screen.findByText('Accounts panel mock')).toBeInTheDocument();
    confirmSpy.mockRestore();
  });

  it('links account section to Candidate Profile navigation', async () => {
    const onNavigateTab = vi.fn();
    render(<PreferencesView onNavigateTab={onNavigateTab} />);
    fireEvent.click(await screen.findByRole('button', { name: /^Account/ }));
    const card = await screen.findByRole('button', { name: /Identity & evidence/ });
    fireEvent.click(card);
    expect(onNavigateTab).toHaveBeenCalledWith('profile');
  });

  it('switches to criteria with initialSubTab mapping for Accounts', async () => {
    render(<PreferencesView initialSubTab="integrations" />);
    expect(await screen.findByText('Accounts panel mock')).toBeInTheDocument();
  });
});
