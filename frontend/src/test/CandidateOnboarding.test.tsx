import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CandidateOnboardingView } from '../components/onboarding/CandidateOnboardingView';
import * as api from '../services/api';
import { CandidateProfile, ProfileCompletenessAssessment } from '../types';

const mockCandidate: CandidateProfile = {
  id: 1,
  name: 'Alex River',
  email: 'alex@example.com',
  degree: 'B.S. in Computer Science',
  college: 'Stanford University',
  graduation_year: 2026,
  cgpa: 3.8,
  skills: [
    { name: 'Python', level: 'advanced', category: 'Languages', evidence: 'Project code' },
    { name: 'TypeScript', level: 'intermediate', category: 'Languages', evidence: 'Frontend' }
  ],
  projects: [
    {
      title: 'Distributed System',
      description: 'Async task engine',
      tech_stack: ['Python', 'Redis'],
      url: 'https://github.com/alex/dist'
    }
  ],
  experience: [],
  preferred_locations: ['Remote', 'San Francisco, CA'],
  work_authorization: 'US Citizen',
  onboarding_status: 'in_progress',
  onboarding_step: 1,
  career_goals: {
    target_roles: ['Software Engineer'],
    target_locations: ['Remote'],
    workplace_preference: 'remote'
  }
};

const mockCompleteness: ProfileCompletenessAssessment = {
  completeness_score: 85,
  readiness_stage: 'high_confidence_readiness',
  is_onboarded: false,
  onboarding_status: 'in_progress',
  onboarding_step: 1,
  category_scores: {
    basic_info: { score: 15, max: 15 },
    education: { score: 15, max: 15 },
    technical_skills: { score: 25, max: 25 },
    projects: { score: 20, max: 25 },
    resume: { score: 10, max: 15 },
    career_goals: { score: 5, max: 5 }
  },
  verified_evidence: [
    'Identity confirmed: Alex River',
    'Education: B.S. in Computer Science from Stanford University',
    '1 technical project(s) documented with technology stacks',
    '2 skill(s) verified by project code or external repositories'
  ],
  unverified_evidence: [],
  missing_evidence: ['Resume: No master resume document initialized'],
  actionable_recommendations: [
    {
      priority: 'high',
      title: 'Upload or generate your Master Resume',
      description: 'A master resume unlocks 1-click tailored ATS exports.',
      action_target: 'resumes'
    }
  ],
  skills_summary: {
    total: 2,
    verified: 2,
    unverified: 0,
    items: [
      { name: 'Python', raw_name: 'Python', category: 'Languages', level: 'advanced', status: 'verified', verification_source: 'project_code' },
      { name: 'TypeScript', raw_name: 'TypeScript', category: 'Languages', level: 'intermediate', status: 'verified', verification_source: 'project_code' }
    ]
  },
  has_master_resume: false,
  master_resume_version: 0,
  projects_count: 1,
  disclaimer: 'Profile readiness measures available evidence density for opportunity matching, not candidate qualifications.'
};

describe('CandidateOnboardingView Component', () => {
  beforeEach(() => {
    vi.spyOn(api, 'fetchCandidateProfile').mockResolvedValue(mockCandidate);
    vi.spyOn(api, 'fetchProfileCompleteness').mockResolvedValue(mockCompleteness);
    vi.spyOn(api, 'fetchSkillsTaxonomy').mockResolvedValue({
      categories: { Languages: ['Python', 'TypeScript', 'Go'] },
      canonical_aliases: { py: 'Python', ts: 'TypeScript' }
    });
    vi.spyOn(api, 'updateOnboardingProgress').mockResolvedValue({
      status: 'success',
      onboarding_step: 2,
      onboarding_status: 'in_progress',
      candidate: mockCandidate
    });
    vi.spyOn(api, 'completeOnboarding').mockResolvedValue({
      status: 'completed',
      message: 'Candidate profile successfully activated.',
      evidence_version: 2,
      readiness: { ...mockCompleteness, is_onboarded: true, completeness_score: 95 }
    });
  });

  it('renders Step 1 (Career Goals) with initial profile data', async () => {
    const handleComplete = vi.fn();
    const handleExit = vi.fn();

    render(<CandidateOnboardingView onComplete={handleComplete} onExit={handleExit} />);

    await waitFor(() => {
      expect(screen.getByText('Target Roles & Career Goals')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('Alex River')).toBeInTheDocument();
    expect(screen.getByDisplayValue('alex@example.com')).toBeInTheDocument();
    expect(screen.getByText('Software Engineer')).toBeInTheDocument();
  });

  it('validates required fields before allowing progression', async () => {
    const handleComplete = vi.fn();
    const handleExit = vi.fn();

    render(<CandidateOnboardingView onComplete={handleComplete} onExit={handleExit} />);

    await waitFor(() => {
      expect(screen.getByDisplayValue('Alex River')).toBeInTheDocument();
    });

    // Clear name
    const nameInput = screen.getByDisplayValue('Alex River');
    fireEvent.change(nameInput, { target: { value: '' } });

    // Click Save & Continue
    const nextBtn = screen.getByText('Save & Continue');
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(screen.getByText('Please enter your full name.')).toBeInTheDocument();
    });
  });

  it('navigates to Step 2 when clicking Education step button', async () => {
    const handleComplete = vi.fn();
    const handleExit = vi.fn();

    render(<CandidateOnboardingView onComplete={handleComplete} onExit={handleExit} />);

    await waitFor(() => {
      expect(screen.getByText('2. Education')).toBeInTheDocument();
    });

    const eduStepBtn = screen.getByText('2. Education');
    fireEvent.click(eduStepBtn);

    await waitFor(() => {
      expect(screen.getByText('Education & Background')).toBeInTheDocument();
    });

    expect(screen.getByDisplayValue('Stanford University')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2026')).toBeInTheDocument();
  });

  it('navigates to Step 3 and allows adding a technical skill', async () => {
    const handleComplete = vi.fn();
    const handleExit = vi.fn();

    vi.spyOn(api, 'addCandidateSkill').mockResolvedValue({
      ...mockCandidate,
      skills: [...mockCandidate.skills, { name: 'Go', level: 'intermediate', category: 'Languages', evidence: '' }]
    });

    render(<CandidateOnboardingView onComplete={handleComplete} onExit={handleExit} />);

    await waitFor(() => {
      expect(screen.getByText('3. Technical Skills')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('3. Technical Skills'));

    await waitFor(() => {
      expect(screen.getByText('Technical Skills Management')).toBeInTheDocument();
    });

    const skillInput = screen.getByPlaceholderText('Skill name (e.g. Python, React, PostgreSQL)');
    fireEvent.change(skillInput, { target: { value: 'Go' } });

    const addBtn = screen.getByText('Add Skill');
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(api.addCandidateSkill).toHaveBeenCalledWith({
        name: 'Go',
        category: 'Languages',
        level: 'intermediate',
        evidence: ''
      });
    });
  });

  it('navigates to Step 6 (Readiness & Launch) and renders readiness score', async () => {
    const handleComplete = vi.fn();
    const handleExit = vi.fn();

    render(<CandidateOnboardingView onComplete={handleComplete} onExit={handleExit} />);

    await waitFor(() => {
      expect(screen.getByText('6. Readiness & Launch')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('6. Readiness & Launch'));

    await waitFor(() => {
      expect(screen.getByText('Profile Readiness & Verification Review')).toBeInTheDocument();
    });

    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByText('High-Confidence Match Ready')).toBeInTheDocument();
    expect(screen.getByText('Identity confirmed: Alex River')).toBeInTheDocument();
  });

  it('triggers onComplete when activating profile on Step 6', async () => {
    const handleComplete = vi.fn();
    const handleExit = vi.fn();

    render(<CandidateOnboardingView onComplete={handleComplete} onExit={handleExit} />);

    await waitFor(() => {
      expect(screen.getByText('6. Readiness & Launch')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('6. Readiness & Launch'));

    await waitFor(() => {
      expect(screen.getByText('Activate Profile & Discover Matches')).toBeInTheDocument();
    });

    const activateBtn = screen.getByText('Activate Profile & Discover Matches');
    fireEvent.click(activateBtn);

    await waitFor(() => {
      expect(api.completeOnboarding).toHaveBeenCalled();
      expect(handleComplete).toHaveBeenCalled();
    });
  });
});
