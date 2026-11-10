import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApplicationTrackerView } from '../components/applications/ApplicationTrackerView';
import * as api from '../services/api';
import { ApplicationRecord } from '../types';

vi.mock('../services/api', () => ({
  fetchApplications: vi.fn(),
  updateApplication: vi.fn(),
  deleteApplication: vi.fn(),
  fetchFollowUpAlerts: vi.fn(),
  fetchEmailIntelligenceMessages: vi.fn(),
  fetchApplicationAnalytics: vi.fn(),
  generateFollowUpEmail: vi.fn(),
  approveFollowUpEmail: vi.fn(),
  createInterviewSchedule: vi.fn(),
}));

const mockApplications: ApplicationRecord[] = [
  {
    id: 1,
    opportunity_id: 101,
    company_name: 'Stripe',
    job_title: 'Software Engineer Intern',
    status: 'applied',
    match_score: 95.5,
    applied_date: '2026-11-01T10:00:00Z',
    follow_up_date: '2026-11-08T10:00:00Z',
    salary_or_stipend: '$60/hr',
    recruiter_name: 'Sarah Connor',
    recruiter_position: 'Senior Technical Recruiter',
    recruiter_email: 'sarah@stripe.com',
    user_notes: 'Initial interview went well. Focus on distributed systems.',
    resume_id: 5,
    resume_version_number: 2,
    interview_schedule: [
      {
        round_name: 'Technical Architecture Round',
        date: '2026-11-15T14:00:00Z',
        format: 'Virtual Video',
        interviewer: 'Alex Tech Lead',
        meeting_link: 'https://meet.google.com/abc-xyz'
      }
    ]
  },
  {
    id: 2,
    opportunity_id: 102,
    company_name: 'Datadog',
    job_title: 'Backend Engineering Intern',
    status: 'screening',
    match_score: 88.0,
    applied_date: '2026-11-03T11:00:00Z',
    follow_up_date: null,
    salary_or_stipend: '$55/hr',
    recruiter_name: 'John Miller',
    recruiter_position: 'University Talent',
    recruiter_email: 'john@datadog.com',
    user_notes: 'Sent availability for next week.'
  },
  {
    id: 3,
    opportunity_id: 103,
    company_name: 'Figma',
    job_title: 'Full Stack Engineer Intern',
    status: 'ready_to_apply',
    match_score: 92.0,
    applied_date: null,
    follow_up_date: null,
    salary_or_stipend: '$65/hr',
    user_notes: ''
  }
];

const mockAnalyticsData = {
  pipeline_counts: {
    total_tracked: 3,
    ready_to_apply: 1,
    submitted_total: 2,
    applied_pending: 1,
    screening: 1,
    interviewing: 0,
    offered: 0,
    rejected: 0,
    withdrawn: 0
  },
  rates: {
    application_response_rate: 50.0,
    interview_conversion_rate: 0.0,
    offer_conversion_rate: 0.0,
    average_response_time_days: 2.5
  },
  formula_definitions: {
    response_rate: 'screening / submitted',
    interview_rate: 'interviewing / submitted',
    offer_rate: 'offered / submitted',
    response_time: 'days between apply and response'
  },
  source_performance: [],
  resume_performance: [],
  platform_efficacy: [],
  historical_trends: []
};

describe('ApplicationTrackerView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();

    vi.mocked(api.fetchApplications).mockResolvedValue({
      items: mockApplications,
      total: 3,
      page: 1,
      page_size: 50,
      total_pages: 1
    });

    vi.mocked(api.fetchFollowUpAlerts).mockResolvedValue({
      summary: {
        total_tracked_count: 3,
        unanswered_count: 1,
        follow_up_due_count: 1,
        upcoming_interviews_count: 1,
        approaching_deadlines_count: 0
      },
      unanswered: [],
      follow_ups_due: [],
      upcoming_interviews: [],
      approaching_deadlines: []
    } as any);

    vi.mocked(api.fetchEmailIntelligenceMessages).mockResolvedValue({
      messages: [],
      pending_review_count: 2,
      total: 2,
      page: 1,
      page_size: 1,
      total_pages: 1
    });

    vi.mocked(api.fetchApplicationAnalytics).mockResolvedValue(mockAnalyticsData as any);
  });

  it('renders page header, tracked total, and top action buttons with alert badges', async () => {
    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getByText('Applications')).toBeInTheDocument();
      expect(screen.getByText('3 tracked')).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /email intelligence/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /follow-ups/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /funnel analytics/i })).toBeInTheDocument();
    });

    // Alert badges
    expect(screen.getByText('2')).toBeInTheDocument(); // pending emails
    expect(screen.getByText('3')).toBeInTheDocument(); // urgent follow-up sum
  });

  it('renders Kanban board columns with cards and matching scores', async () => {
    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getByText('Ready to apply')).toBeInTheDocument();
      expect(screen.getByText('Applied')).toBeInTheDocument();
      expect(screen.getByText('Screening')).toBeInTheDocument();
      expect(screen.getByText('Interviewing')).toBeInTheDocument();
      expect(screen.getByText('Offer received')).toBeInTheDocument();
      expect(screen.getByText('Rejected')).toBeInTheDocument();
    });

    // Application cards rendered (using getAllByText because company appears in card and selected flyout)
    expect(screen.getAllByText('Stripe').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Datadog')).toBeInTheDocument();
    expect(screen.getByText('Figma')).toBeInTheDocument();
    expect(screen.getByText('96%')).toBeInTheDocument(); // 95.5 rounds to 96
  });

  it('switches between Board view and Table view cleanly', async () => {
    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getAllByText('Stripe').length).toBeGreaterThanOrEqual(1);
    });

    // Click Table tab
    const tableTab = screen.getByRole('tab', { name: /table/i });
    fireEvent.click(tableTab);

    // Verifies table header & search
    expect(screen.getByPlaceholderText(/search company, job title, recruiter/i)).toBeInTheDocument();
    expect(screen.getByText(/3 records/i)).toBeInTheDocument();
    expect(screen.getByText('Company & Position')).toBeInTheDocument();

    // Click Board tab to return
    const boardTab = screen.getByRole('tab', { name: /board/i });
    fireEvent.click(boardTab);
    expect(screen.getByText('Ready to apply')).toBeInTheDocument();
  });

  it('displays selected application inspection sheet with notes editor', async () => {
    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getAllByText('Stripe').length).toBeGreaterThanOrEqual(1);
    });

    // Stripe is initially selected (first item)
    expect(screen.getByText('Personal Application Notes & Key Insights')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Initial interview went well. Focus on distributed systems.')).toBeInTheDocument();

    // Verify recruiter and interview details
    expect(screen.getAllByText('Sarah Connor').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Technical Architecture Round').length).toBeGreaterThanOrEqual(1);
  });

  it('updates stage via status change dropdown in detailed inspector', async () => {
    vi.mocked(api.updateApplication).mockResolvedValue({
      ...mockApplications[0],
      status: 'screening'
    });

    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getByLabelText('Application Stage')).toBeInTheDocument();
    });

    const stageSelect = screen.getByLabelText('Application Stage');
    fireEvent.change(stageSelect, { target: { value: 'screening' } });

    await waitFor(() => {
      expect(api.updateApplication).toHaveBeenCalledWith(1, { status: 'screening' });
    });
  });

  it('updates and saves user notes in the application detail flyout', async () => {
    vi.mocked(api.updateApplication).mockResolvedValue({
      ...mockApplications[0],
      user_notes: 'Updated note: passed tech screening.'
    });

    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getByText('Save Notes')).toBeInTheDocument();
    });

    const notesTextarea = screen.getByPlaceholderText(/record recruiter comments/i);
    fireEvent.change(notesTextarea, { target: { value: 'Updated note: passed tech screening.' } });

    const saveBtn = screen.getByRole('button', { name: /save notes/i });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.updateApplication).toHaveBeenCalledWith(1, {
        user_notes: 'Updated note: passed tech screening.'
      });
    });
  });

  it('opens Follow-Up Intelligence modal when clicking Follow-ups button', async () => {
    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /follow-ups/i })).toBeInTheDocument();
    });

    const followUpBtn = screen.getByRole('button', { name: /follow-ups/i });
    fireEvent.click(followUpBtn);

    await waitFor(() => {
      expect(screen.getByText(/follow-up intelligence/i)).toBeInTheDocument();
    });
  });

  it('opens Funnel Analytics modal when clicking Funnel analytics button', async () => {
    render(<ApplicationTrackerView />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /funnel analytics/i })).toBeInTheDocument();
    });

    const analyticsBtn = screen.getByRole('button', { name: /funnel analytics/i });
    fireEvent.click(analyticsBtn);

    await waitFor(() => {
      expect(screen.getByText(/application performance & funnel analytics/i)).toBeInTheDocument();
    });
  });
});
