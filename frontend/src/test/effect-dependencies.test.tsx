import React, { StrictMode } from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as api from '../services/api';
import { ApplicationTrackerView } from '../components/applications/ApplicationTrackerView';
import { ApplicationTimelineView } from '../components/applications/ApplicationTimelineView';
import { PracticeModeView } from '../components/interviews/PracticeModeView';
import { AnalyticsView } from '../components/analytics/AnalyticsView';
import { ResumeStudioView } from '../components/resumes/ResumeStudioView';
import { ApplicationRecord } from '../types';

vi.mock('../services/api', () => ({
  getAuthToken: vi.fn(() => 'ci-test-token'),
  // Tracker
  fetchApplications: vi.fn(),
  updateApplication: vi.fn(),
  deleteApplication: vi.fn(),
  fetchFollowUpAlerts: vi.fn(),
  fetchEmailIntelligenceMessages: vi.fn(),
  fetchApplicationAnalytics: vi.fn(),
  generateFollowUpEmail: vi.fn(),
  approveFollowUpEmail: vi.fn(),
  createInterviewSchedule: vi.fn(),
  // Timeline
  fetchApplicationTimeline: vi.fn(),
  // Practice mode
  fetchPracticeSessions: vi.fn(),
  fetchPracticeSessionDetail: vi.fn(),
  createPracticeSession: vi.fn(),
  evaluatePracticeQuestion: vi.fn(),
  completePracticeSession: vi.fn(),
  savePracticeAnswer: vi.fn(),
  // Analytics
  fetchAnalytics: vi.fn(),
  fetchSankeyData: vi.fn(),
  fetchSourceEfficacyAnalytics: vi.fn(),
  // Resume studio
  fetchResumes: vi.fn(),
  fetchMasterResume: vi.fn(),
  createResume: vi.fn(),
  updateResume: vi.fn(),
  renameResume: vi.fn(),
  duplicateResume: vi.fn(),
  deleteResume: vi.fn(),
  compileResumePdf: vi.fn(),
  fetchResumeTemplates: vi.fn(),
  fetchResumeVersions: vi.fn(),
  createResumeVersionSnapshot: vi.fn(),
  restoreResumeVersion: vi.fn(),
  compareResumeVersions: vi.fn(),
  auditResumeQuality: vi.fn(),
  requestResumeOptimization: vi.fn(),
  applyResumeOptimization: vi.fn(),
  // Shared
  fetchOpportunities: vi.fn(),
  fetchCandidateProfile: vi.fn(),
}));

const mockApplications: ApplicationRecord[] = [
  {
    id: 1,
    opportunity_id: 101,
    company_name: 'Stripe',
    job_title: 'SWE Intern',
    status: 'applied',
    match_score: 95.5,
    applied_date: '2026-11-01T10:00:00Z',
    follow_up_date: null,
    salary_or_stipend: '$60/hr',
    recruiter_name: 'Sarah',
    recruiter_position: 'Recruiter',
    recruiter_email: 'sarah@stripe.com',
    user_notes: 'Notes from round one.',
    resume_id: 5,
    resume_version_number: 2,
  },
  {
    id: 2,
    opportunity_id: 102,
    company_name: 'Datadog',
    job_title: 'Backend Intern',
    status: 'screening',
    match_score: 88.0,
    applied_date: '2026-11-03T11:00:00Z',
    follow_up_date: null,
    salary_or_stipend: '$55/hr',
    user_notes: 'Second-round notes.',
  },
];

const mockPracticeSession = {
  id: 42,
  session_title: 'STRIPE TECHNICAL Drill',
  session_type: 'technical',
  status: 'in_progress',
  current_question_index: 0,
  opportunity_id: 101,
  company_name: 'Stripe',
  role_title: 'SWE Intern',
  created_at: '2026-11-10T00:00:00Z',
  questions: [
    { id: 7, question_text: 'Explain a deadlock.', user_answer: '', ai_feedback: null, hint: '' },
  ],
};

const mocks = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fetchApplications.mockResolvedValue({ items: mockApplications, total: 2, page: 1, total_pages: 1 });
  mocks.fetchFollowUpAlerts.mockResolvedValue({ summary: { unanswered_count: 0, follow_up_due_count: 0, upcoming_interviews_count: 0, approaching_deadlines_count: 0 } });
  mocks.fetchEmailIntelligenceMessages.mockResolvedValue({ items: [], pending_review_count: 0 });
  mocks.fetchApplicationAnalytics.mockResolvedValue({});
  mocks.fetchApplicationTimeline.mockResolvedValue([]);
  mocks.fetchPracticeSessions.mockResolvedValue({ items: [], total: 0 });
  mocks.fetchPracticeSessionDetail.mockResolvedValue(mockPracticeSession);
  mocks.createPracticeSession.mockResolvedValue(mockPracticeSession);
  mocks.evaluatePracticeQuestion.mockResolvedValue({ session: mockPracticeSession });
  mocks.completePracticeSession.mockResolvedValue({});
  mocks.fetchOpportunities.mockResolvedValue({ items: [] });
  mocks.fetchAnalytics.mockResolvedValue({ summary: {} });
  mocks.fetchSankeyData.mockResolvedValue({ empty: true, nodes: [], links: [] });
  mocks.fetchSourceEfficacyAnalytics.mockResolvedValue([]);
  mocks.fetchResumes.mockResolvedValue({ items: [], total: 0 });
  mocks.fetchMasterResume.mockResolvedValue({ id: 1, title: 'Master Resume', is_master: true, latex_content: '\\documentclass{article}', version: 78, user_id: 1 });
  mocks.fetchResumeVersions.mockResolvedValue([]);
  mocks.auditResumeQuality.mockResolvedValue({
    ats_score: 88,
    grade: 'A',
    summary: 'Synthetic audit pass.',
    checks: [{ title: 'Single-Column Layout', passed: true, score: 100, details: ['No multicolumn detected'] }],
  });
  mocks.fetchResumeTemplates.mockResolvedValue([]);
  mocks.fetchCandidateProfile.mockResolvedValue(null);
});

describe('effect dependency regressions (3.0.8)', () => {
  it('ApplicationTrackerView loads once on mount and auto-selects the first record without losing notes', async () => {
    render(<ApplicationTrackerView />);
    await waitFor(() => expect(api.fetchApplications).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByDisplayValue('Notes from round one.')).toBeInTheDocument());
    expect(api.fetchFollowUpAlerts).toHaveBeenCalledTimes(1);
    expect(api.fetchEmailIntelligenceMessages).toHaveBeenCalledTimes(1);
  });

  it('ApplicationTrackerView does not refetch on unrelated re-renders', async () => {
    const { rerender } = render(<ApplicationTrackerView />);
    await waitFor(() => expect(api.fetchApplications).toHaveBeenCalledTimes(1));
    rerender(<ApplicationTrackerView />);
    rerender(<ApplicationTrackerView />);
    expect(api.fetchApplications).toHaveBeenCalledTimes(1);
  });

  it('ApplicationTimelineView loads timeline exactly once on mount', async () => {
    render(<ApplicationTimelineView />);
    await waitFor(() => expect(api.fetchApplicationTimeline).toHaveBeenCalledTimes(1));
    expect(api.fetchApplicationTimeline).toHaveBeenCalledWith(100, 'all');
  });

  it('PracticeModeView without a trigger loads sessions once and never creates a session', async () => {
    render(<PracticeModeView />);
    await waitFor(() => expect(api.fetchPracticeSessions).toHaveBeenCalledTimes(1));
    expect(api.createPracticeSession).not.toHaveBeenCalled();
    expect(api.fetchOpportunities).toHaveBeenCalledTimes(1);
  });

  it('PracticeModeView under StrictMode creates exactly one drill for one trigger', async () => {
    const onClear = vi.fn();
    render(
      <StrictMode>
        <PracticeModeView
          initialPrepTrigger={{ category: 'technical', question: 'Q?', hint: 'h', company: 'Stripe', oppId: 101 }}
          onClearInitialTrigger={onClear}
        />
      </StrictMode>
    );
    await waitFor(() => expect(mocks.fetchPracticeSessions).toHaveBeenCalled());
    // StrictMode mounts effects twice in development; the in-flight dedup must
    // collapse both invocations into a single session creation request.
    expect(mocks.createPracticeSession).toHaveBeenCalledTimes(1);
  });

  it('PracticeModeView with a prep trigger creates exactly one drill and clears the trigger exactly once', async () => {
    const onClear = vi.fn();
    render(
      <PracticeModeView
        initialPrepTrigger={{ category: 'technical', question: 'Q?', hint: 'h', company: 'Stripe', oppId: 101 }}
        onClearInitialTrigger={onClear}
      />
    );
    await waitFor(() => expect(api.createPracticeSession).toHaveBeenCalledTimes(1));
    expect(api.createPracticeSession).toHaveBeenCalledTimes(1);
    expect(onClear).toHaveBeenCalledTimes(1);
  });

  it('AnalyticsView fetches on mount and refetches sankey only when the source filter changes', async () => {
    render(<AnalyticsView />);
    await waitFor(() => expect(api.fetchSankeyData).toHaveBeenCalledTimes(1));
    expect(api.fetchAnalytics).toHaveBeenCalledTimes(1);

    const sourceSelect = screen.getByLabelText('Filter pipeline by source platform');
    fireEvent.change(sourceSelect, { target: { value: 'internshala' } });
    await waitFor(() => expect(api.fetchSankeyData).toHaveBeenCalledTimes(2));
    expect(api.fetchSankeyData).toHaveBeenLastCalledWith('internshala', 'all');
  });

  it('ResumeStudioView loads resumes exactly once on mount and resolves versions for the master', async () => {
    const master = { id: 1, title: 'Master Resume', is_master: true, latex_content: '\\documentclass{article}', version: 78, user_id: 1, template_id: 'minimal_professional', target_role: 'General', created_at: '2026-11-10T00:00:00Z', updated_at: '2026-11-10T00:00:00Z' } as const;
    mocks.fetchResumes.mockResolvedValue({ items: [master], total: 1 });
    render(<ResumeStudioView />);
    await waitFor(() => expect(api.fetchResumes).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(api.fetchResumeVersions).toHaveBeenCalledWith(1));
  });
});
