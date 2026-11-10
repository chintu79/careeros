import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { OverviewView } from '../components/overview/OverviewView';
import * as api from '../services/api';
import { CommandCenterData } from '../types';

vi.mock('../services/api', () => ({
  fetchCommandCenterData: vi.fn(),
}));

const mockCommandCenterData: CommandCenterData = {
  date_range: '30d',
  pipeline_summary: {
    total_applications: 25,
    stages_count: {
      ready_to_apply: 1,
      applied: 18,
      screening: 2,
      interviewing: 2,
      offered: 0,
      rejected: 2,
    },
    response_rate: 26.1,
    interview_rate: 8.7,
    offer_rate: 0.0,
    overdue_follow_ups_count: 1,
  },
  prioritized_actions: [
    {
      id: 101,
      title: 'Deadline Approaching: PadosiAgent Flutter Intern',
      reason: 'Application portal closes in 3 day(s). Match score is 97%.',
      priority: 'urgent',
      category: 'deadline',
      action_type: 'prepare_apply',
      action_label: 'Prepare Application',
      target_id: 110,
    },
    {
      id: 102,
      title: 'Generate ATS Resume for NayePankh Foundation',
      reason: 'Application is marked as applied but has no job-specific tailored LaTeX resume.',
      priority: 'high',
      category: 'resume',
      action_type: 'tailor_resume',
      action_label: 'Tailor Resume Now',
      target_id: 123,
    },
  ],
  upcoming_deadlines: [],
  follow_ups_due: [
    {
      application_id: 6,
      opportunity_id: 198,
      company_name: 'Kasphyn',
      job_title: 'React Native Development Intern',
      status: 'applied',
      days_waiting: 7,
    },
  ],
  recently_discovered_relevant: [
    {
      id: 201,
      title: 'Python Programmer (DevOps Model)',
      normalized_title: 'python programmer',
      company_name: 'Cognivance Inc',
      location: 'Hyderabad, India',
      normalized_location: 'hyderabad, india',
      workplace_type: 'onsite',
      employment_type: 'internship',
      source_platform: 'linkedin',
      status: 'active',
      discovered_at: '2026-11-08T00:00:00Z',
      match_score: 98,
      stipend_text: 'Competitive Industry Stipend',
      is_saved: false,
      is_applied: false,
    },
  ],
  readiness_diagnostics: {
    interview: {
      total_logged: 3,
      average_performance: 4.0,
      average_difficulty: 3.0,
      strengths: [],
      weaknesses: [],
    },
    resume: {
      total_resumes: 2,
      tailored_count: 1,
      compiled_pdf_rate: 100.0,
      missing_resume_apps_count: 17,
    },
    skills: {
      verified_skills_count: 20,
      market_demanded_mastered: [{ skill: 'Python', frequency: 18 }],
      missing_high_roi_gaps: [{ skill: 'REST API', frequency: 17 }],
    },
  },
  strategic_focus: {
    focus_area: 'Acquire REST API',
    reason: 'Required in 17 active database listings not currently verified on your profile.',
    milestone_project: 'Build a focused micro-service incorporating REST API into your portfolio.',
    weekly_pace: 'Aim for 3-5 verified applications with >=75% match score per week.',
  },
  activity_timeline: [
    {
      type: 'resume_updated',
      timestamp: '2026-11-08T12:59:57.333539',
      title: 'Tailored Resume: Master Candidate Resume',
      description: 'Target: General • PDF Ready',
      target_tab: 'resumes',
      target_id: 1,
      badge: 'Master Resume',
    },
    {
      type: 'stage_transition',
      timestamp: '2026-11-08T12:57:18.454709',
      title: 'Moved to Applied',
      description: 'Kasphyn - React Native Development Intern',
      target_tab: 'tracker',
      target_id: 6,
      badge: 'applied',
    },
  ],
};

describe('OverviewView Component', () => {
  const mockProps = {
    onNavigateTab: vi.fn(),
    onTailorResume: vi.fn(),
    onPrepareApply: vi.fn(),
    onSyncAll: vi.fn().mockResolvedValue(undefined),
    isSyncing: false,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders skeleton loading state while fetching', () => {
    vi.mocked(api.fetchCommandCenterData).mockReturnValue(new Promise(() => {}));
    render(<OverviewView {...mockProps} />);

    expect(screen.getByLabelText(/loading overview dashboard/i)).toBeInTheDocument();
  });

  it('renders KPI metrics and snapshot section once loaded', async () => {
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /active applications/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /interviews:/i })).toBeInTheDocument();
      expect(screen.getByText(/conversion rate/i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /offers:/i })).toBeInTheDocument();
    });

    expect(screen.getAllByText('26.1%').length).toBeGreaterThanOrEqual(1);
  });

  it('navigates to applications tracker when clicking Active Applications KPI card', async () => {
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /active applications/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /active applications/i }));
    expect(mockProps.onNavigateTab).toHaveBeenCalledWith('tracker');
  });

  it('navigates to interviews workspace when clicking Interviews KPI card', async () => {
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /interviews:/i })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: /interviews:/i }));
    expect(mockProps.onNavigateTab).toHaveBeenCalledWith('interviews');
  });

  it('renders prioritized action items with urgency badges and triggers callbacks', async () => {
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/deadline approaching: padosiagent/i)).toBeInTheDocument();
      expect(screen.getByText(/generate ats resume for nayepankh/i)).toBeInTheDocument();
    });

    // Check urgency badge
    expect(screen.getByText('urgent')).toBeInTheDocument();
    expect(screen.getByText('high')).toBeInTheDocument();

    // Click "Prepare Application" button
    const prepBtn = screen.getByRole('button', { name: /prepare application/i });
    fireEvent.click(prepBtn);
    expect(mockProps.onPrepareApply).toHaveBeenCalledWith(110);

    // Click "Tailor Resume Now" button
    const tailorBtn = screen.getByRole('button', { name: /tailor resume now/i });
    fireEvent.click(tailorBtn);
    expect(mockProps.onTailorResume).toHaveBeenCalledWith(123);
  });

  it('renders recent activity stream and dispatches click to relevant tab', async () => {
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText(/tailored resume: master candidate resume/i)).toBeInTheDocument();
      expect(screen.getByText(/kasphyn - react native development intern/i)).toBeInTheDocument();
    });

    const resumeActivity = screen.getByText(/tailored resume: master candidate resume/i);
    fireEvent.click(resumeActivity);
    expect(mockProps.onNavigateTab).toHaveBeenCalledWith('resumes');
  });

  it('renders pipeline stage distribution and navigates on stage click', async () => {
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Pipeline Funnel')).toBeInTheDocument();
    });

    const appliedStageBtn = screen.getByRole('button', { name: /applied: 18 roles/i });
    fireEvent.click(appliedStageBtn);
    expect(mockProps.onNavigateTab).toHaveBeenCalledWith('tracker');
  });

  it('renders strategic recommendation and triggers AI Assistant navigation', async () => {
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Acquire REST API')).toBeInTheDocument();
    });

    const actionPlanBtn = screen.getByRole('button', { name: /build action plan/i });
    fireEvent.click(actionPlanBtn);
    expect(mockProps.onNavigateTab).toHaveBeenCalledWith('chat');
  });

  it('renders empty state when prioritized actions are empty', async () => {
    const emptyData: CommandCenterData = {
      ...mockCommandCenterData,
      prioritized_actions: [],
    };
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(emptyData);
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('All Caught Up')).toBeInTheDocument();
    });
  });

  it('renders error state with retry button on API failure', async () => {
    vi.mocked(api.fetchCommandCenterData).mockRejectedValue(new Error('Network Error'));
    render(<OverviewView {...mockProps} />);

    await waitFor(() => {
      expect(screen.getByText('Overview Unavailable')).toBeInTheDocument();
    });

    const retryBtn = screen.getByRole('button', { name: /retry loading/i });
    expect(retryBtn).toBeInTheDocument();

    // Clicking retry invokes fetchCommandCenterData again
    vi.mocked(api.fetchCommandCenterData).mockResolvedValue(mockCommandCenterData);
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText(/active applications/i)).toBeInTheDocument();
    });
  });
});
