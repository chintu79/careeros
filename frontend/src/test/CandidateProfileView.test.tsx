import React from 'react';
import { render, screen, fireEvent, within, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CandidateProfileView } from '../components/candidate/CandidateProfileView';
import * as api from '../services/api';
import { CandidateProfile, ProfileCompletenessAssessment } from '../types';

vi.mock('../services/api', () => ({
  fetchCandidateProfile: vi.fn(),
  updateCandidateProfile: vi.fn(),
  fetchProfileCompleteness: vi.fn(),
  addCandidateSkill: vi.fn(),
  deleteCandidateSkill: vi.fn(),
  syncGitHubProfile: vi.fn(),
  syncPortfolio: vi.fn(),
  importLinkedInData: vi.fn(),
  approveIntegrations: vi.fn(),
  parseResumeUpload: vi.fn(),
}));

const pythonSkill = { name: 'Python', level: 'advanced', category: 'Languages' };
const linuxSkill = { name: 'Linux', level: 'intermediate', category: 'Tools' };

const baseCandidate = (): CandidateProfile => ({
  id: 1,
  name: 'Shreekrishna Chinta',
  email: 'synthetic.candidate@example.test',
  degree: 'B.Tech AI & DS',
  graduation_year: 2028,
  college: 'AISSMS-IOIT',
  cgpa: 8.16,
  skills: [pythonSkill, linuxSkill],
  projects: [],
  experience: [],
  preferred_locations: ['Remote, India'],
  work_authorization: 'Requires Sponsorship',
  evidence_version: 44,
  updated_at: '2026-11-09T10:00:00',
});

const completeness = (): ProfileCompletenessAssessment => ({
  completeness_score: 100,
  readiness_stage: 'high_confidence_readiness',
  is_onboarded: false,
  onboarding_status: 'in_progress',
  onboarding_step: 5,
  category_scores: { technical_skills: { score: 25, max: 25 } },
  verified_evidence: ['14 skill(s) verified by project code'],
  unverified_evidence: [],
  missing_evidence: [],
  actionable_recommendations: [],
  skills_summary: {
    total: 2,
    verified: 1,
    unverified: 1,
    items: [
      { name: 'Python', raw_name: 'Python', category: 'Languages', level: 'advanced', status: 'verified', verification_source: 'project_code' },
      { name: 'Linux', raw_name: 'Linux', category: 'Tools', level: 'intermediate', status: 'unverified', verification_source: '' },
    ],
  },
});

const getSkillsRegion = () => screen.getByRole('region', { name: /Skills list/i });

describe('Candidate Profile skill lifecycle', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.fetchCandidateProfile).mockResolvedValue(baseCandidate());
    vi.mocked(api.fetchProfileCompleteness).mockResolvedValue(completeness());
    vi.mocked(api.addCandidateSkill).mockResolvedValue({
      ...baseCandidate(),
      skills: [...baseCandidate().skills, { name: 'Rust', level: 'advanced', category: 'General' }],
    });
    vi.mocked(api.deleteCandidateSkill).mockResolvedValue({
      ...baseCandidate(),
      skills: [linuxSkill],
    });
  });

  it('renders existing skills with verification provenance', async () => {
    render(<CandidateProfileView />);
    const region = await within(await screen.findByRole('region', { name: /Skills list/i }));
    expect(region.getByText('Python')).toBeInTheDocument();
    expect(region.getByText('Linux')).toBeInTheDocument();
  });

  it('adds a new skill with the typed level and trims whitespace', async () => {
    render(<CandidateProfileView />);
    await screen.findByRole('region', { name: /Skills list/i });

    fireEvent.change(screen.getByLabelText('Add a skill'), { target: { value: '   Rust   ' } });
    fireEvent.change(screen.getByLabelText('Skill level'), { target: { value: 'advanced' } });
    fireEvent.click(screen.getByRole('button', { name: /Add skill/ }));

    await waitFor(() => expect(api.addCandidateSkill).toHaveBeenCalledTimes(1));
    expect(api.addCandidateSkill).toHaveBeenCalledWith({ name: 'Rust', category: 'General', level: 'advanced' });
    expect(await screen.findByText('Rust')).toBeInTheDocument();
  });

  it('persists the intermediate level by default', async () => {
    render(<CandidateProfileView />);
    await screen.findByRole('region', { name: /Skills list/i });
    fireEvent.change(screen.getByLabelText('Add a skill'), { target: { value: 'GraphQL' } });
    fireEvent.keyDown(screen.getByLabelText('Add a skill'), { key: 'Enter', preventDefault: vi.fn() });
    await waitFor(() => expect(api.addCandidateSkill).toHaveBeenCalledWith({ name: 'GraphQL', category: 'General', level: 'intermediate' }));
  });

  it('rejects duplicate skills case-insensitively without calling the API', async () => {
    render(<CandidateProfileView />);
    await screen.findByRole('region', { name: /Skills list/i });
    fireEvent.change(screen.getByLabelText('Add a skill'), { target: { value: 'PYTHON' } });
    fireEvent.click(screen.getByRole('button', { name: /Add skill/ }));
    expect(api.addCandidateSkill).not.toHaveBeenCalled();
    expect(screen.getByRole('alert')).toHaveTextContent('already in your profile');
  });

  it('adds Expert level when selected', async () => {
    render(<CandidateProfileView />);
    await screen.findByRole('region', { name: /Skills list/i });
    fireEvent.change(screen.getByLabelText('Add a skill'), { target: { value: 'Rust' } });
    fireEvent.change(screen.getByLabelText('Skill level'), { target: { value: 'expert' } });
    fireEvent.click(screen.getByRole('button', { name: /Add skill/ }));
    await waitFor(() => expect(api.addCandidateSkill).toHaveBeenCalledWith({ name: 'Rust', category: 'General', level: 'expert' }));
  });

  it('asks for confirmation before removing a skill and cancels cleanly', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<CandidateProfileView />);
    await screen.findByRole('region', { name: /Skills list/i });

    fireEvent.click(screen.getByRole('button', { name: 'Remove Python' }));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(String(confirmSpy.mock.calls[0][0])).toContain('Python');
    expect(api.deleteCandidateSkill).not.toHaveBeenCalled();
    expect(screen.getByText('Python')).toBeInTheDocument();
    confirmSpy.mockRestore();
  });

  it('removing confirmed skill refreshes profile and completeness', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<CandidateProfileView />);
    await screen.findByRole('region', { name: /Skills list/i });
    vi.mocked(api.fetchProfileCompleteness).mockClear();

    fireEvent.click(screen.getByRole('button', { name: 'Remove Python' }));
    await waitFor(() => expect(api.deleteCandidateSkill).toHaveBeenCalledWith('Python'));
    await waitFor(() => expect(api.fetchProfileCompleteness).toHaveBeenCalled());
    expect(screen.queryByText('Python')).not.toBeInTheDocument();
    expect(screen.getByText('Linux')).toBeInTheDocument();
    confirmSpy.mockRestore();
  });

  it('preserves unrelated skills when deletion fails and shows an error', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.mocked(api.deleteCandidateSkill).mockRejectedValue(new Error('HTTP 500: database locked'));
    render(<CandidateProfileView />);
    await screen.findByRole('region', { name: /Skills list/i });

    fireEvent.click(screen.getByRole('button', { name: 'Remove Python' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('database locked');
    // unrelated skill still present
    expect(screen.getByText('Linux')).toBeInTheDocument();
    expect(screen.getByText('Python')).toBeInTheDocument();
    confirmSpy.mockRestore();
  });
});
