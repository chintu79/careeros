import React, { useState, useEffect } from 'react';
import {
  Kanban,
  List,
  Clock,
  Calendar,
  Users,
  BarChart3,
  Sparkles,
  ExternalLink,
  Video,
  User,
  FileText,
  Mail,
  Plus,
  X
} from 'lucide-react';
import { ApplicationRecord } from '../../types';
import { PageHeader } from '../ui/PageHeader';
import { useUnsavedChangesGuard } from '../../context/unsavedChanges';
import { Button } from '../ui/Button';

const Linkedin = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
    <rect width="4" height="12" x="2" y="9" />
    <circle cx="4" cy="4" r="2" />
  </svg>
);

import {
  fetchApplications,
  updateApplication,
  deleteApplication,
  fetchFollowUpAlerts,
  fetchEmailIntelligenceMessages
} from '../../services/api';
import { ApplicationKanbanView } from './ApplicationKanbanView';
import { ApplicationTableView } from './ApplicationTableView';
import { ApplicationTimelineView } from './ApplicationTimelineView';
import { ApplicationCalendarView } from './ApplicationCalendarView';
import { RecruiterCRMView } from './RecruiterCRMView';
import { FollowUpIntelligenceModal } from './FollowUpIntelligenceModal';
import { ApplicationAnalyticsModal } from './ApplicationAnalyticsModal';
import { ScheduleInterviewModal } from './ScheduleInterviewModal';
import { EmailIntelligenceReviewModal } from './EmailIntelligenceReviewModal';

type ViewMode = 'kanban' | 'table' | 'timeline' | 'calendar' | 'recruiters';

interface ApplicationTrackerViewProps {
  onNavigateToInterviews?: (company?: string, role?: string) => void;
}

export const ApplicationTrackerView: React.FC<ApplicationTrackerViewProps> = ({
  onNavigateToInterviews
}) => {
  const [apps, setApps] = useState<ApplicationRecord[]>([]);
  const [total, setTotal] = useState<number>(0);
  const [page, setPage] = useState<number>(1);
  const [pageSize, setPageSize] = useState<number>(50);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedApp, setSelectedApp] = useState<ApplicationRecord | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('kanban');

  // Modals state
  const [isFollowUpModalOpen, setIsFollowUpModalOpen] = useState<boolean>(false);
  const [followUpAppTarget, setFollowUpAppTarget] = useState<ApplicationRecord | null>(null);
  const [isAnalyticsModalOpen, setIsAnalyticsModalOpen] = useState<boolean>(false);
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState<boolean>(false);
  const [scheduleAppTarget, setScheduleAppTarget] = useState<ApplicationRecord | null>(null);
  const [isEmailModalOpen, setIsEmailModalOpen] = useState<boolean>(false);

  // Badge alert counter
  const [urgentAlertsCount, setUrgentAlertsCount] = useState<number>(0);
  const [pendingEmailCount, setPendingEmailCount] = useState<number>(0);

  // Notes editing state
  const [editingNotes, setEditingNotes] = useState<string>('');
  const [savingNotes, setSavingNotes] = useState<boolean>(false);
  const notesDirty = Boolean(selectedApp) && editingNotes !== (selectedApp?.user_notes ?? '');
  useUnsavedChangesGuard('tracker:notes', notesDirty, 'Application notes are not saved');

  const loadApps = (p = page, ps = pageSize) => {
    setLoading(true);
    fetchApplications({ page: p, page_size: ps })
      .then((res) => {
        const items = res.items || [];
        setApps(items);
        setTotal(res.total || 0);
        if (items.length > 0 && !selectedApp) {
          setSelectedApp(items[0]);
          setEditingNotes(items[0].user_notes || '');
        }
      })
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  const loadAlertsSummary = () => {
    fetchFollowUpAlerts(7)
      .then((res) => {
        const sum =
          (res.summary?.unanswered_count || 0) +
          (res.summary?.follow_up_due_count || 0) +
          (res.summary?.upcoming_interviews_count || 0) +
          (res.summary?.approaching_deadlines_count || 0);
        setUrgentAlertsCount(sum);
      })
      .catch((err) => console.error(err));
  };

  const loadEmailCount = () => {
    fetchEmailIntelligenceMessages({ page_size: 1 })
      .then((res) => {
        setPendingEmailCount(res.pending_review_count || 0);
      })
      .catch((err) => console.error(err));
  };

  useEffect(() => {
    loadApps(page, pageSize);
    loadAlertsSummary();
    loadEmailCount();
  }, [page, pageSize]);

  useEffect(() => {
    if (selectedApp) {
      setEditingNotes(selectedApp.user_notes || '');
    }
  }, [selectedApp]);

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      const updated = await updateApplication(id, { status: newStatus });
      setApps(apps.map((a) => (a.id === id ? updated : a)));
      if (selectedApp && selectedApp.id === id) {
        setSelectedApp(updated);
      }
      loadAlertsSummary();
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteApp = async (id: number) => {
    if (!window.confirm('Are you sure you want to delete this tracked application?')) return;
    try {
      await deleteApplication(id);
      const remaining = apps.filter((a) => a.id !== id);
      setApps(remaining);
      if (selectedApp?.id === id) {
        setSelectedApp(remaining[0] || null);
      }
      loadAlertsSummary();
    } catch (err) {
      console.error(err);
    }
  };

  const handleSaveNotes = async () => {
    if (!selectedApp) return;
    setSavingNotes(true);
    try {
      const updated = await updateApplication(selectedApp.id, { user_notes: editingNotes });
      setApps(apps.map((a) => (a.id === selectedApp.id ? updated : a)));
      setSelectedApp(updated);
    } catch (err) {
      console.error(err);
    } finally {
      setSavingNotes(false);
    }
  };

  const requestSelectApp = (app: ApplicationRecord) => {
    if (notesDirty && !window.confirm('Application notes are not saved. Discard them and switch?')) return;
    setSelectedApp(app);
  };
  const openFollowUpModal = (app?: ApplicationRecord) => {
    setFollowUpAppTarget(app || null);
    setIsFollowUpModalOpen(true);
  };

  const openScheduleModal = (app: ApplicationRecord) => {
    setScheduleAppTarget(app);
    setIsScheduleModalOpen(true);
  };

  const selectedAppInitials = selectedApp
    ? (selectedApp.company_name || 'CO')
        .split(' ')
        .map(w => w[0])
        .filter(Boolean)
        .slice(0, 2)
        .join('')
        .toUpperCase()
    : 'CO';

  return (
    <div className="space-y-6">
      {/* Page header */}
      <PageHeader
        eyebrow="Workspace"
        title="Applications"
        description="Track every role from first save to signed offer — board, table, timeline, calendar and recruiter relationships."
        meta={
          <span className="font-mono text-[11px] text-[var(--color-ink-muted)] tnum">{total} tracked</span>
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setIsEmailModalOpen(true)}
              className="relative inline-flex min-h-[32px] items-center gap-1.5 rounded-[var(--radius-control)] border border-white/[0.09] bg-white/[0.03] px-3 text-[12px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
            >
              <Mail className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
              <span>Email intelligence</span>
              {pendingEmailCount > 0 && (
                <span className="rounded bg-emerald-400/15 px-1.5 font-mono text-[10px] font-semibold text-emerald-300 tnum">
                  {pendingEmailCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => openFollowUpModal()}
              className="relative inline-flex min-h-[32px] items-center gap-1.5 rounded-[var(--radius-control)] border border-white/[0.09] bg-white/[0.03] px-3 text-[12px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
            >
              <Sparkles className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
              <span>Follow-ups</span>
              {urgentAlertsCount > 0 && (
                <span className="rounded bg-amber-400/15 px-1.5 font-mono text-[10px] font-semibold text-amber-300 tnum">
                  {urgentAlertsCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setIsAnalyticsModalOpen(true)}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-[var(--radius-control)] border border-white/[0.09] bg-white/[0.03] px-3 text-[12px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
            >
              <BarChart3 className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
              <span>Funnel analytics</span>
            </button>
          </div>
        }
      />

      {/* View switcher */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="tablist" aria-label="Application tracker views" className="inline-flex flex-wrap items-center gap-1 rounded-xl border border-white/[0.07] bg-[var(--color-paper-quiet)] p-1">
          {[
            { id: 'kanban', label: 'Board', icon: Kanban },
            { id: 'table', label: 'Table', icon: List },
            { id: 'timeline', label: 'Timeline', icon: Clock },
            { id: 'calendar', label: 'Calendar', icon: Calendar },
            { id: 'recruiters', label: 'Recruiters', icon: Users },
          ].map((view) => {
            const Icon = view.icon;
            const active = viewMode === view.id;
            return (
              <button
                key={view.id}
                type="button"
                role="tab"
                aria-selected={active}
                onClick={() => setViewMode(view.id as ViewMode)}
                className={`inline-flex min-h-[30px] items-center gap-1.5 rounded-[var(--radius-control)] px-3 text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] ${
                  active
                    ? 'bg-[var(--color-paper-3)] text-[var(--color-ink)] shadow-xs font-semibold'
                    : 'text-[var(--color-ink-tertiary)] hover:bg-white/[0.03] hover:text-[var(--color-ink-secondary)]'
                }`}
              >
                <Icon className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
                <span>{view.label}</span>
              </button>
            );
          })}
        </div>

        <span className="font-mono text-[11px] text-[var(--color-ink-muted)]">
          {viewMode === 'kanban' ? 'Drag-free stage controls on every card' : 'Sorted by most recent activity'}
        </span>
      </div>

      {/* Main View Render */}
      {viewMode === 'kanban' && (
        <ApplicationKanbanView
          applications={apps}
          selectedApp={selectedApp}
          onSelectApp={requestSelectApp}
          onStatusChange={handleStatusChange}
          onOpenFollowUpModal={(app) => openFollowUpModal(app)}
          onOpenScheduleModal={(app) => openScheduleModal(app)}
        />
      )}

      {viewMode === 'table' && (
        <ApplicationTableView
          applications={apps}
          onSelectApp={requestSelectApp}
          onStatusChange={handleStatusChange}
          onDeleteApp={handleDeleteApp}
          onOpenFollowUpModal={(app) => openFollowUpModal(app)}
          onOpenScheduleModal={(app) => openScheduleModal(app)}
        />
      )}

      {viewMode === 'timeline' && (
        <ApplicationTimelineView
          applications={apps}
          onSelectApp={requestSelectApp}
          onOpenFollowUpModal={(app) => openFollowUpModal(app)}
          onNavigateToInterviewPrep={onNavigateToInterviews}
        />
      )}

      {viewMode === 'calendar' && (
        <ApplicationCalendarView
          applications={apps}
          onSelectApp={requestSelectApp}
          onOpenFollowUpModal={(app) => openFollowUpModal(app)}
          onOpenScheduleModal={(app) => openScheduleModal(app)}
          onNavigateToInterviewPrep={onNavigateToInterviews}
        />
      )}

      {viewMode === 'recruiters' && <RecruiterCRMView />}

      {/* Selected Application Detailed Flyout / Bottom Sheet (when viewing Kanban or Table) */}
      {selectedApp && (viewMode === 'kanban' || viewMode === 'table') && (
        <div className="rounded-xl border border-white/[0.08] bg-[var(--color-paper-quiet)] p-4 sm:p-5 space-y-4 shadow-modal">
          {/* Header */}
          <div className="flex flex-col gap-3 border-b border-white/[0.06] pb-3.5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-[12px] font-bold text-[var(--color-ink-muted)]">
                {selectedAppInitials}
              </div>
              <div>
                <div className="flex items-center space-x-2">
                  <span className="text-[12px] font-medium text-[var(--color-ink-secondary)]">
                    {selectedApp.company_name}
                  </span>
                  <span className="text-[var(--color-ink-tertiary)]">•</span>
                  <span className="font-mono text-[11px] font-semibold text-[var(--color-primary)]">
                    {Math.round(selectedApp.match_score)}% match
                  </span>
                </div>
                <h3 className="text-[16px] font-semibold text-[var(--color-ink)] leading-snug">{selectedApp.job_title}</h3>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => openFollowUpModal(selectedApp)}
                leftIcon={<Sparkles className="h-3.5 w-3.5" />}
              >
                Follow-Up AI
              </Button>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => openScheduleModal(selectedApp)}
                leftIcon={<Video className="h-3.5 w-3.5" />}
              >
                Schedule Interview
              </Button>

              {selectedApp.original_url && (
                <a
                  href={selectedApp.original_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex min-h-[32px] items-center gap-1.5 rounded-[var(--radius-control)] border border-white/[0.09] bg-white/[0.03] px-2.5 text-[12px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                >
                  <span>Listing</span>
                  <ExternalLink className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" />
                </a>
              )}

              <button
                type="button"
                onClick={() => setSelectedApp(null)}
                aria-label="Close details"
                className="flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-[var(--color-ink-tertiary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </div>

          {/* Quick Metrics / Status Row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3 space-y-1">
              <label htmlFor="selected-app-stage" className="block text-[11px] font-medium text-[var(--color-ink-tertiary)]">Stage</label>
              <select
                id="selected-app-stage"
                aria-label="Application Stage"
                value={selectedApp.status}
                onChange={(e) => handleStatusChange(selectedApp.id, e.target.value)}
                className="min-h-[28px] w-full rounded border border-white/[0.09] bg-[var(--color-paper)] px-2 py-1 text-[12px] font-medium text-[var(--color-ink)] focus:border-[var(--color-primary)] focus:outline-none"
              >
                <option value="ready_to_apply" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Ready to Apply</option>
                <option value="applied" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Applied</option>
                <option value="screening" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Screening</option>
                <option value="interviewing" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Interviewing</option>
                <option value="offered" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Offer Received</option>
                <option value="rejected" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Rejected</option>
                <option value="withdrawn" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Withdrawn</option>
              </select>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3 space-y-1">
              <span className="block text-[11px] font-medium text-[var(--color-ink-tertiary)]">Applied Date</span>
              <span className="font-semibold text-[var(--color-ink)] block">
                {selectedApp.applied_date
                  ? new Date(selectedApp.applied_date).toLocaleDateString()
                  : 'Pending submission'}
              </span>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3 space-y-1">
              <span className="block text-[11px] font-medium text-[var(--color-ink-tertiary)]">Follow-Up Target</span>
              <span className="font-semibold text-amber-400 block">
                {selectedApp.follow_up_date
                  ? new Date(selectedApp.follow_up_date).toLocaleDateString()
                  : '7 days post-apply'}
              </span>
            </div>

            <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3 space-y-1">
              <span className="block text-[11px] font-medium text-[var(--color-ink-tertiary)]">Compensation</span>
              <span className="font-semibold text-emerald-400 block font-mono">
                {selectedApp.salary_or_stipend || 'Competitive / Unspecified'}
              </span>
            </div>
          </div>

          {/* Recruiter Details & Resume Details */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
            {/* Recruiter block */}
            <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5 space-y-2">
              <h4 className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--color-ink-tertiary)]">
                <User className="w-3.5 h-3.5 text-blue-400" />
                <span>Recruiter & Point of Contact</span>
              </h4>

              {selectedApp.recruiter_name ? (
                <div className="space-y-1.5 text-[var(--color-ink-secondary)]">
                  <div className="font-semibold text-[var(--color-ink)]">{selectedApp.recruiter_name}</div>
                  {selectedApp.recruiter_position && (
                    <div className="text-[var(--color-ink-tertiary)] text-[11px]">{selectedApp.recruiter_position}</div>
                  )}
                  <div className="flex items-center space-x-3 pt-1">
                    {selectedApp.recruiter_email && (
                      <a
                        href={`mailto:${selectedApp.recruiter_email}`}
                        className="text-emerald-400 hover:underline flex items-center space-x-1"
                      >
                        <Mail className="w-3 h-3" />
                        <span>{selectedApp.recruiter_email}</span>
                      </a>
                    )}
                    {selectedApp.recruiter_linkedin && (
                      <a
                        href={selectedApp.recruiter_linkedin}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sky-400 hover:underline flex items-center space-x-1"
                      >
                        <Linkedin className="w-3 h-3" />
                        <span>LinkedIn</span>
                      </a>
                    )}
                  </div>
                </div>
              ) : (
                <p className="text-[var(--color-ink-tertiary)] italic text-[11px]">
                  No recruiter linked. You can link contacts via the Recruiter CRM tab.
                </p>
              )}
            </div>

            {/* Resume version & Tailored summary */}
            <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5 space-y-2">
              <h4 className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--color-ink-tertiary)]">
                <FileText className="w-3.5 h-3.5 text-teal-400" />
                <span>Resume & Cover Letter Version</span>
              </h4>

              <div className="space-y-1.5 text-[var(--color-ink-secondary)]">
                <div className="flex items-center space-x-2">
                  <span className="text-[var(--color-ink-tertiary)]">Attached Resume:</span>
                  <span className="font-semibold text-[var(--color-ink)]">
                    {selectedApp.resume_version_number
                      ? `Version v${selectedApp.resume_version_number}`
                      : selectedApp.resume_id
                      ? `Resume #${selectedApp.resume_id}`
                      : 'Master Resume'}
                  </span>
                </div>

                {selectedApp.tailored_resume_summary && (
                  <p className="rounded border border-white/[0.06] bg-[var(--color-paper)] p-2 text-[11px] text-[var(--color-ink-tertiary)] line-clamp-2">
                    {selectedApp.tailored_resume_summary}
                  </p>
                )}

                {selectedApp.cover_letter_text && (
                  <div className="pt-1 text-[11px] text-teal-400">
                    ✓ Custom cover letter drafted for this application
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Interview Schedule List */}
          {selectedApp.interview_schedule && selectedApp.interview_schedule.length > 0 && (
            <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5 space-y-2.5">
              <div className="flex items-center justify-between">
                <h4 className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--color-ink-tertiary)]">
                  <Video className="w-3.5 h-3.5" />
                  <span>Scheduled Interview Rounds ({selectedApp.interview_schedule.length})</span>
                </h4>
                <button
                  type="button"
                  onClick={() => openScheduleModal(selectedApp)}
                  className="flex items-center gap-1 text-[11px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:text-emerald-300"
                >
                  <Plus className="w-3 h-3" />
                  <span>Add Round</span>
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
                {selectedApp.interview_schedule.map((item, idx) => (
                  <div
                    key={idx}
                    className="rounded-md border border-white/[0.06] bg-[var(--color-paper)] p-2.5 space-y-1"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-[var(--color-ink)]">{item.round_name}</span>
                      <span className="font-mono text-[10px] text-[var(--color-ink-tertiary)]">
                        {item.date ? new Date(item.date).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : 'TBD'}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2 text-[11px] text-[var(--color-ink-tertiary)]">
                      <span>Format: {item.format || 'Virtual Video'}</span>
                      {item.interviewer && <span>• Interviewer: {item.interviewer}</span>}
                    </div>
                    {item.meeting_link && (
                      <a
                        href={item.meeting_link}
                        target="_blank"
                        rel="noreferrer"
                        className="text-[11px] text-emerald-400 hover:underline flex items-center space-x-1 pt-0.5"
                      >
                        <Video className="w-3 h-3" />
                        <span>Join Meeting Link</span>
                      </a>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* User Notes editor */}
          <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5 space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-[11px] font-medium text-[var(--color-ink-tertiary)]">
                Personal Application Notes & Key Insights
              </h4>
              <Button
                variant="primary"
                size="sm"
                onClick={handleSaveNotes}
                disabled={savingNotes}
              >
                {savingNotes ? 'Saving...' : 'Save Notes'}
              </Button>
            </div>
            <textarea
              rows={3}
              value={editingNotes}
              onChange={(e) => setEditingNotes(e.target.value)}
              placeholder="Record recruiter comments, key technical requirements emphasized, salary discussion notes..."
              className="w-full rounded-lg border border-white/[0.09] bg-[var(--color-paper)] p-2.5 text-[12px] text-[var(--color-ink)] placeholder:text-[var(--color-ink-tertiary)] transition-colors focus:border-[var(--color-primary)] focus:outline-none"
            />
          </div>
        </div>
      )}

      {/* Global Modals */}
      <FollowUpIntelligenceModal
        isOpen={isFollowUpModalOpen}
        onClose={() => setIsFollowUpModalOpen(false)}
        preselectedApp={followUpAppTarget}
        onActionComplete={() => {
          loadApps();
          loadAlertsSummary();
        }}
      />

      <ApplicationAnalyticsModal
        isOpen={isAnalyticsModalOpen}
        onClose={() => setIsAnalyticsModalOpen(false)}
      />

      <ScheduleInterviewModal
        isOpen={isScheduleModalOpen}
        onClose={() => setIsScheduleModalOpen(false)}
        application={scheduleAppTarget}
        onSuccess={() => {
          loadApps();
          loadAlertsSummary();
        }}
      />

      <EmailIntelligenceReviewModal
        isOpen={isEmailModalOpen}
        onClose={() => setIsEmailModalOpen(false)}
        applications={apps}
        onApplicationUpdated={() => {
          loadApps();
          loadAlertsSummary();
          loadEmailCount();
        }}
        onNavigateToInterviewPrep={onNavigateToInterviews}
      />
    </div>
  );
};
