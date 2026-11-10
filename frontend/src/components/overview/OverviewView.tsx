import React, { useState, useEffect, useCallback } from 'react';
import {
  Sparkles,
  FileText,
  Calendar,
  CheckSquare,
  TrendingUp,
  ArrowRight,
  RotateCw,
  Award,
  ChevronRight,
  ArrowUpRight,
  Activity,
  AlertTriangle,
  Clock,
  Briefcase,
  CheckCircle2
} from 'lucide-react';
import {
  CommandCenterData,
  PrioritizedActionItem,
  ActivityTimelineEvent
} from '../../types';
import { fetchCommandCenterData } from '../../services/api';
import {
  CountUp,
  PageHeader,
  Card,
  Button,
  Badge,
  EmptyState,
  Skeleton
} from '../ui';

interface OverviewViewProps {
  onNavigateTab: (tab: string) => void;
  onTailorResume: (oppId: number) => void;
  onPrepareApply: (oppId: number) => void;
  onSyncAll: () => Promise<void>;
  isSyncing: boolean;
}

function formatRelativeTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    if (isNaN(date.getTime())) return 'Recently';
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    if (diffMs < 0) return 'Just now';
    const diffMins = Math.floor(diffMs / (1000 * 60));
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return 'Recently';
  }
}

function getActivityIcon(type: string) {
  switch (type) {
    case 'resume_updated':
      return <FileText className="h-3.5 w-3.5 text-sky-300" aria-hidden="true" />;
    case 'stage_transition':
      return <CheckSquare className="h-3.5 w-3.5 text-[var(--color-accent)]" aria-hidden="true" />;
    case 'interview_logged':
      return <Calendar className="h-3.5 w-3.5 text-amber-400" aria-hidden="true" />;
    default:
      return <Activity className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />;
  }
}

export const OverviewView: React.FC<OverviewViewProps> = ({
  onNavigateTab,
  onTailorResume,
  onPrepareApply,
  onSyncAll,
  isSyncing
}) => {
  const [data, setData] = useState<CommandCenterData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = useCallback(() => {
    setLoading(true);
    setError(null);
    fetchCommandCenterData('30d')
      .then(res => {
        setData(res);
      })
      .catch(err => {
        console.error('Failed to load command center data:', err);
        setError('Unable to load overview dashboard data. Check network connection.');
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleActionClick = (action: PrioritizedActionItem) => {
    if (action.action_type === 'tailor_resume' && action.target_id) {
      onTailorResume(action.target_id);
    } else if (action.action_type === 'prepare_apply' && action.target_id) {
      onPrepareApply(action.target_id);
    } else if (action.target_tab) {
      onNavigateTab(action.target_tab);
    }
  };

  const handleTimelineClick = (event: ActivityTimelineEvent) => {
    if (event.target_tab) {
      onNavigateTab(event.target_tab);
    }
  };

  const getGreeting = () => {
    const hour = new Date().getHours();
    if (hour < 12) return 'Good morning';
    if (hour < 18) return 'Good afternoon';
    return 'Good evening';
  };

  // Skeleton Loading State
  if (loading && !data) {
    return (
      <div className="space-y-8 pb-10" aria-busy="true" aria-label="Loading overview dashboard">
        {/* Masthead Skeleton */}
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-white/[0.07] pb-5">
          <div className="space-y-2">
            <Skeleton className="h-3.5 w-24" />
            <Skeleton className="h-8 w-56" />
            <Skeleton className="h-4 w-96 max-w-full" />
          </div>
          <div className="flex items-center gap-2">
            <Skeleton className="h-8 w-24 rounded-lg" />
          </div>
        </div>

        {/* KPI Grid Skeleton */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {[...Array(4)].map((_, i) => (
            <Card key={i} className="p-4 space-y-3">
              <div className="flex items-center justify-between">
                <Skeleton className="h-3.5 w-24" />
                <Skeleton className="h-7 w-7 rounded-md" />
              </div>
              <Skeleton className="h-8 w-16" />
              <Skeleton className="h-3.5 w-32" />
            </Card>
          ))}
        </div>

        {/* Content Section Skeleton */}
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Card className="p-5 space-y-4">
            <Skeleton className="h-4 w-36" />
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-center justify-between gap-3 pt-3 border-t border-white/[0.05]">
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-3.5 w-20" />
                  <Skeleton className="h-4 w-48" />
                  <Skeleton className="h-3 w-64" />
                </div>
                <Skeleton className="h-7 w-24 rounded-md shrink-0" />
              </div>
            ))}
          </Card>
          <Card className="p-5 space-y-4">
            <Skeleton className="h-4 w-36" />
            {[...Array(3)].map((_, i) => (
              <div key={i} className="flex items-start gap-3 pt-3 border-t border-white/[0.05]">
                <Skeleton className="h-6 w-6 rounded-md shrink-0" />
                <div className="space-y-2 flex-1">
                  <Skeleton className="h-4 w-40" />
                  <Skeleton className="h-3 w-56" />
                </div>
                <Skeleton className="h-3 w-16 shrink-0" />
              </div>
            ))}
          </Card>
        </div>
      </div>
    );
  }

  // Error State
  if (error && !data) {
    return (
      <div className="py-16">
        <EmptyState
          icon={<AlertTriangle className="h-6 w-6 text-rose-400" aria-hidden="true" />}
          title="Overview Unavailable"
          description={error}
          action={
            <Button
              variant="secondary"
              leftIcon={<RotateCw className="h-3.5 w-3.5" />}
              onClick={loadData}
            >
              Retry loading
            </Button>
          }
        />
      </div>
    );
  }

  const pipeline = data?.pipeline_summary;
  const stages = pipeline?.stages_count || {};
  const prioritizedActions = (data?.prioritized_actions || []).slice(0, 4);
  const recommendedOpps = (data?.recently_discovered_relevant || []).slice(0, 3);
  const focus = data?.strategic_focus;
  const activityEvents = (data?.activity_timeline || []).slice(0, 6);
  const followUps = (data?.follow_ups_due || []).slice(0, 2);

  const responsesReceived =
    (stages['screening'] || 0) +
    (stages['interviewing'] || 0) +
    (stages['offered'] || 0) +
    (stages['rejected'] || 0);

  const totalPipelineApps = pipeline?.total_applications || 0;

  return (
    <div className="space-y-8 pb-12">
      {/* 1. Header Masthead */}
      <PageHeader
        eyebrow="Workspace"
        title={getGreeting()}
        description="Here is where your search stands today, and the few things worth doing next."
        meta={
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1.5 rounded-[var(--radius-xs)] border border-white/[0.07] bg-[var(--color-surface)] px-2 py-0.5 text-[11px] text-[var(--color-ink-secondary)]">
              <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-accent)] animate-pulse" aria-hidden="true" />
              Live
            </span>
            <span className="text-[11px] font-mono text-[var(--color-ink-tertiary)] hidden sm:inline">
              Last 30 days
            </span>
          </div>
        }
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={onSyncAll}
            disabled={isSyncing}
            isLoading={isSyncing}
            leftIcon={
              <RotateCw
                className={`h-3.5 w-3.5 ${isSyncing ? 'animate-spin text-[var(--color-accent)]' : ''}`}
                strokeWidth={1.75}
                aria-hidden="true"
              />
            }
            aria-label="Sync all job sources and applications"
          >
            <span>{isSyncing ? 'Syncing…' : 'Sync feeds'}</span>
          </Button>
        }
      />

      {/* 2. Follow-Ups Alert Callout (if active overdue applications exist) */}
      {followUps.length > 0 && (
        <div
          role="region"
          aria-label="Follow-up reminders"
          className="flex flex-col gap-2 rounded-[var(--radius-card)] border border-[var(--color-warn)]/30 border-[var(--color-rule)] bg-[var(--color-warn-bg)] p-3.5 sm:flex-row sm:items-center sm:justify-between"
        >
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-[var(--color-warn-bg)] text-amber-400">
              <Clock className="h-3.5 w-3.5" aria-hidden="true" />
            </div>
            <div>
              <p className="text-[12px] font-medium text-[var(--color-ink)]">
                {followUps.length === 1
                  ? `Follow-up recommended for ${followUps[0].company_name}`
                  : `${followUps.length} follow-ups recommended in your pipeline`}
              </p>
              <p className="text-[11px] text-[var(--color-ink-secondary)]">
                Waiting {followUps[0].days_waiting} days without recruiter status transition. A professional check-in improves recall.
              </p>
            </div>
          </div>
          <Button
            size="xs"
            variant="secondary"
            onClick={() => onNavigateTab('tracker')}
            rightIcon={<ChevronRight className="h-3 w-3" />}
            className="self-start sm:self-auto shrink-0"
          >
            Review in Tracker
          </Button>
        </div>
      )}

      {/* 3. Career Pipeline KPI Cards */}
      <section aria-label="Career pipeline metrics">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="section-title">Snapshot</h2>
          <span className="text-[11px] font-mono text-[var(--color-ink-tertiary)]">Interactive drill-down</span>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {/* Card 1: Active Applications */}
          <Card
            isInteractive
            onClick={() => onNavigateTab('tracker')}
            className="p-4 transition-colors hover:border-[var(--color-border-hover)] group"
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigateTab('tracker');
              }
            }}
            aria-label={`Active applications: ${totalPipelineApps}. Click to view in applications tracker.`}
          >
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">Active applications</span>
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-white/[0.04] text-[var(--color-ink-tertiary)] group-hover:text-[var(--color-accent)] transition-colors">
                <CheckSquare className="h-3.5 w-3.5" aria-hidden="true" />
              </div>
            </div>
            <div className="mt-2 text-[24px] font-semibold tracking-tight text-[var(--color-ink)] font-mono tnum">
              <CountUp to={totalPipelineApps} duration={0.8} />
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-[var(--color-ink-tertiary)]">
              <span>In active pipeline</span>
              <ArrowUpRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity text-[var(--color-accent)]" aria-hidden="true" />
            </div>
          </Card>

          {/* Card 2: Interviews */}
          <Card
            isInteractive
            onClick={() => onNavigateTab('interviews')}
            className="p-4 transition-colors hover:border-[var(--color-border-hover)] group"
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigateTab('interviews');
              }
            }}
            aria-label={`Interviews: ${stages['interviewing'] || 0}. Click to view in interviews.`}
          >
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">Interviews</span>
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-white/[0.04] text-[var(--color-ink-tertiary)] group-hover:text-amber-400 transition-colors">
                <Calendar className="h-3.5 w-3.5" aria-hidden="true" />
              </div>
            </div>
            <div className="mt-2 text-[24px] font-semibold tracking-tight text-[var(--color-ink)] font-mono tnum">
              <CountUp to={stages['interviewing'] || 0} duration={0.8} />
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-[var(--color-ink-tertiary)]">
              <span>Scheduled or active</span>
              <ArrowUpRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity text-amber-400" aria-hidden="true" />
            </div>
          </Card>

          {/* Card 3: Responses */}
          <Card
            className="p-4"
            aria-label={`Responses: ${responsesReceived}, response rate ${pipeline?.response_rate || 0} percent`}
          >
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">Responses</span>
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-white/[0.04] text-[var(--color-ink-tertiary)]">
                <TrendingUp className="h-3.5 w-3.5" aria-hidden="true" />
              </div>
            </div>
            <div className="mt-2 text-[24px] font-semibold tracking-tight text-[var(--color-ink)] font-mono tnum">
              <CountUp to={responsesReceived} duration={0.8} />
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px]">
              <span className="text-[var(--color-ink-tertiary)]">Conversion rate</span>
              <Badge variant="emerald" size="sm">
                {pipeline?.response_rate || 0}%
              </Badge>
            </div>
          </Card>

          {/* Card 4: Offers */}
          <Card
            isInteractive
            onClick={() => onNavigateTab('tracker')}
            className="p-4 transition-colors hover:border-[var(--color-border-hover)] group"
            role="button"
            tabIndex={0}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onNavigateTab('tracker');
              }
            }}
            aria-label={`Offers: ${stages['offered'] || 0}. Click to view in applications tracker.`}
          >
            <div className="flex items-start justify-between">
              <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">Offers</span>
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-white/[0.04] text-[var(--color-ink-tertiary)] group-hover:text-[var(--color-accent)] transition-colors">
                <Award className="h-3.5 w-3.5" aria-hidden="true" />
              </div>
            </div>
            <div className="mt-2 text-[24px] font-semibold tracking-tight text-[var(--color-ink)] font-mono tnum">
              <CountUp to={stages['offered'] || 0} duration={0.8} />
            </div>
            <div className="mt-2 flex items-center justify-between text-[11px] text-[var(--color-ink-tertiary)]">
              <span>{(stages['offered'] || 0) > 0 ? 'Active offers' : 'No active offers'}</span>
              <ArrowUpRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity text-[var(--color-accent)]" aria-hidden="true" />
            </div>
          </Card>
        </div>
      </section>

      {/* 3b. Career readiness — direct from /api/command-center readiness_diagnostics */}
      {data?.readiness_diagnostics && (
        <section aria-label="Career readiness overview" className="space-y-3">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="section-title">Career readiness</h2>
            <span className="text-[11px] text-[var(--color-ink-tertiary)]">From verified profile + resume + interviews</span>
          </div>
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
            {/* Resume */}
            <button
              type="button"
              onClick={() => onNavigateTab('resumes')}
              className="flex flex-col items-start gap-1.5 rounded-[var(--radius-control)] border border-white/[0.06] bg-[var(--color-paper-2)] p-4 text-left transition-colors hover:border-[var(--color-rule)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
              aria-label={`Resume readiness: ${data.readiness_diagnostics.resume.tailored_count} tailored resumes, ${data.readiness_diagnostics.resume.compiled_pdf_rate}% compiled. Open Resume Studio.`}
            >
              <div className="flex w-full items-center justify-between">
                <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">Resume</span>
                <FileText className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" aria-hidden="true" />
              </div>
              <span className="font-mono text-[24px] font-semibold leading-none text-[var(--color-ink)] tnum">
                {data.readiness_diagnostics.resume.tailored_count}
              </span>
              <span className="text-[11px] text-[var(--color-ink-tertiary)]">
                tailored · {data.readiness_diagnostics.resume.compiled_pdf_rate}% compiled
              </span>
              {data.readiness_diagnostics.resume.missing_resume_apps_count > 0 && (
                <span className="mt-1 inline-flex items-center gap-1 rounded border border-amber-400/25 bg-amber-400/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
                  {data.readiness_diagnostics.resume.missing_resume_apps_count} missing tailored
                </span>
              )}
            </button>

            {/* Interview */}
            <button
              type="button"
              onClick={() => onNavigateTab('interviews')}
              className="flex flex-col items-start gap-1.5 rounded-[var(--radius-control)] border border-white/[0.06] bg-[var(--color-paper-2)] p-4 text-left transition-colors hover:border-[var(--color-rule)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
              aria-label={`Interview readiness: ${data.readiness_diagnostics.interview.total_logged} logged, average performance ${data.readiness_diagnostics.interview.average_performance}. Open Interview journal.`}
            >
              <div className="flex w-full items-center justify-between">
                <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">Interview</span>
                <Calendar className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" aria-hidden="true" />
              </div>
              <span className="font-mono text-[24px] font-semibold leading-none text-[var(--color-ink)] tnum">
                {data.readiness_diagnostics.interview.total_logged}
              </span>
              <span className="text-[11px] text-[var(--color-ink-tertiary)]">
                rounds logged · avg {data.readiness_diagnostics.interview.average_performance?.toFixed(1) ?? '—'}/5
              </span>
              {data.readiness_diagnostics.interview.total_logged === 0 && (
                <span className="mt-1 inline-flex items-center gap-1 rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
                  Log your first round
                </span>
              )}
            </button>

            {/* Skills evidence */}
            <button
              type="button"
              onClick={() => onNavigateTab('profile')}
              className="flex flex-col items-start gap-1.5 rounded-[var(--radius-control)] border border-white/[0.06] bg-[var(--color-paper-2)] p-4 text-left transition-colors hover:border-[var(--color-rule)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)]"
              aria-label={`Skills evidence: ${data.readiness_diagnostics.skills.verified_skills_count} verified, ${data.readiness_diagnostics.skills.missing_high_roi_gaps.length} gap(s). Open Profile.`}
            >
              <div className="flex w-full items-center justify-between">
                <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">Skills evidence</span>
                <CheckSquare className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" aria-hidden="true" />
              </div>
              <span className="font-mono text-[24px] font-semibold leading-none text-[var(--color-ink)] tnum">
                {data.readiness_diagnostics.skills.verified_skills_count}
              </span>
              <span className="text-[11px] text-[var(--color-ink-tertiary)]">
                skills verified by projects or GitHub
              </span>
              {data.readiness_diagnostics.skills.market_demanded_mastered.length > 0 && (
                <span className="mt-1 inline-flex items-center gap-1 rounded border border-emerald-400/25 bg-emerald-400/[0.05] px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
                  {data.readiness_diagnostics.skills.market_demanded_mastered.length} market-mastered
                </span>
              )}
              {data.readiness_diagnostics.skills.missing_high_roi_gaps.length > 0 && (
                <span className="block text-[10px] text-slate-400">
                  Gaps: {data.readiness_diagnostics.skills.missing_high_roi_gaps.slice(0, 3).map(g => g.skill).join(', ')}
                </span>
              )}
            </button>
          </div>
        </section>
      )}
      {/* 4. Priority Actions & Recent Activity (2-Column Grid) */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
        {/* Left Column: Needs You Today (7 cols) */}
        <section aria-label="Priority actions" className="lg:col-span-7">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <div>
              <h2 className="section-title">Needs you today</h2>
              <p className="mt-0.5 text-[12px] text-[var(--color-ink-tertiary)]">High-leverage decisions, ordered by urgency.</p>
            </div>
            <button
              type="button"
              onClick={() => onNavigateTab('tracker')}
              className="inline-flex items-center gap-1 text-[12px] text-[var(--color-ink-secondary)] transition-colors hover:text-[var(--color-accent)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)] rounded px-1"
            >
              Pipeline <ArrowUpRight className="h-3 w-3" aria-hidden="true" />
            </button>
          </div>

          {prioritizedActions.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="h-5 w-5 text-[var(--color-accent)]" aria-hidden="true" />}
              title="All Caught Up"
              description="No urgent actions pending. New recommendations and follow-up deadlines will appear here automatically."
              compact
            />
          ) : (
            <Card className="overflow-hidden divide-y divide-white/[0.06]">
              {prioritizedActions.map((action) => {
                const isUrgent = action.priority === 'urgent';
                const isHigh = action.priority === 'high';
                const badgeVariant = isUrgent ? 'rose' : isHigh ? 'amber' : 'emerald';

                return (
                  <div
                    key={action.id}
                    className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between transition-colors hover:bg-white/[0.02]"
                  >
                    <div className="flex min-w-0 items-start gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[10px]">
                          <Badge variant={badgeVariant} dot size="sm">
                            {action.priority}
                          </Badge>
                          <span className="text-[var(--color-ink-tertiary)]" aria-hidden="true">·</span>
                          <span className="text-[var(--color-ink-secondary)] font-mono">
                            {action.category.replace('_', ' ')}
                          </span>
                        </div>
                        <h3 className="mt-1.5 text-[13px] font-medium leading-snug text-[var(--color-ink)]">
                          {action.title}
                        </h3>
                        <p className="mt-1 text-[12px] leading-relaxed text-[var(--color-ink-secondary)]">
                          {action.reason}
                        </p>
                      </div>
                    </div>

                    <div className="self-start sm:self-auto shrink-0">
                      <Button
                        size="sm"
                        variant={action.action_type === 'prepare_apply' ? 'primary' : 'secondary'}
                        onClick={() => handleActionClick(action)}
                        rightIcon={<ArrowRight className="h-3 w-3" />}
                        className="whitespace-nowrap"
                      >
                        {action.action_label}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </Card>
          )}
        </section>

        {/* Right Column: Recent Activity Feed (5 cols) */}
        <section aria-label="Recent activity stream" className="lg:col-span-5">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <div>
              <h2 className="section-title">Recent Activity</h2>
              <p className="mt-0.5 text-[12px] text-[var(--color-ink-tertiary)]">Real-time candidate log.</p>
            </div>
            <button
              type="button"
              onClick={() => onNavigateTab('tracker')}
              className="inline-flex items-center gap-1 text-[12px] text-[var(--color-ink-secondary)] transition-colors hover:text-[var(--color-accent)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)] rounded px-1"
            >
              History <ChevronRight className="h-3 w-3" aria-hidden="true" />
            </button>
          </div>

          {activityEvents.length === 0 ? (
            <EmptyState
              icon={<Activity className="h-5 w-5 text-[var(--color-ink-tertiary)]" aria-hidden="true" />}
              title="No Recent Activity"
              description="Application status changes, resume tailors, and interview notes will stream here."
              compact
            />
          ) : (
            <Card className="overflow-hidden divide-y divide-white/[0.05]">
              {activityEvents.map((evt, idx) => (
                <div
                  key={`${evt.timestamp}-${idx}`}
                  onClick={() => handleTimelineClick(evt)}
                  className="flex items-start gap-3 p-3.5 transition-colors hover:bg-white/[0.02] cursor-pointer group"
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleTimelineClick(evt);
                    }
                  }}
                  aria-label={`${evt.title}: ${evt.description}`}
                >
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-white/[0.04] mt-0.5">
                    {getActivityIcon(evt.type)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="truncate text-[12px] font-medium text-[var(--color-ink)] group-hover:text-[var(--color-accent)] transition-colors">
                        {evt.title}
                      </span>
                      <span className="shrink-0 text-[10px] font-mono text-[var(--color-ink-tertiary)]">
                        {formatRelativeTime(evt.timestamp)}
                      </span>
                    </div>
                    <p className="mt-0.5 truncate text-[11px] text-[var(--color-ink-secondary)]">
                      {evt.description}
                    </p>
                    {evt.badge && (
                      <div className="mt-1.5">
                        <Badge size="sm" variant="outline" className="text-[10px]">
                          {evt.badge}
                        </Badge>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </Card>
          )}
        </section>
      </div>

      {/* 5. Recommended Opportunities Preview */}
      <section aria-label="Recommended opportunities">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <div>
            <h2 className="section-title">Recommended</h2>
            <p className="mt-0.5 text-[12px] text-[var(--color-ink-tertiary)]">Strongest matches from your verified candidate profile.</p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTab('discover')}
            className="inline-flex items-center gap-1 whitespace-nowrap rounded px-1 text-[12px] text-[var(--color-ink-secondary)] transition-colors hover:text-[var(--color-accent)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)]"
          >
            View all in Discover <ChevronRight className="h-3 w-3" aria-hidden="true" />
          </button>
        </div>

        {recommendedOpps.length === 0 ? (
          <EmptyState
            icon={<Briefcase className="h-5 w-5 text-[var(--color-ink-tertiary)]" aria-hidden="true" />}
            title="No Matches Yet"
            description="Adjust your target roles, skills, or location preferences in Settings to generate personalized matches."
            compact
            action={
              <Button size="sm" variant="secondary" onClick={() => onNavigateTab('preferences')}>
                Update Preferences
              </Button>
            }
          />
        ) : (
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {recommendedOpps.map(opp => (
              <Card
                key={opp.id}
                className="flex flex-col p-4 transition-colors hover:border-[var(--color-border-hover)] justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <span className="truncate text-[11px] font-medium text-[var(--color-ink-secondary)]">
                      {opp.company_name}
                    </span>
                    <Badge variant="emerald" size="sm" className="font-mono font-semibold">
                      <CountUp to={Math.round(opp.match_score)} duration={0.7} />% match
                    </Badge>
                  </div>

                  <button
                    type="button"
                    onClick={() => onPrepareApply(opp.id)}
                    className="mt-1.5 block whitespace-nowrap text-left text-[13px] font-medium leading-snug text-[var(--color-ink)] transition-colors hover:text-[var(--color-accent)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)] rounded"
                  >
                    <span className="line-clamp-1">{opp.title}</span>
                  </button>

                  <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-[var(--color-ink-tertiary)]">
                    <span className="truncate">{opp.location || 'Remote'}</span>
                    {opp.stipend_text && opp.stipend_text !== 'Undisclosed' && (
                      <>
                        <span aria-hidden="true">·</span>
                        <span className="font-mono text-[var(--color-ink-secondary)]">{opp.stipend_text}</span>
                      </>
                    )}
                  </div>
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-white/[0.05] pt-3">
                  <Button
                    size="xs"
                    variant="ghost"
                    leftIcon={<FileText className="h-3 w-3" />}
                    onClick={() => onTailorResume(opp.id)}
                  >
                    Tailor resume
                  </Button>
                  <Button
                    size="xs"
                    variant="secondary"
                    rightIcon={<ArrowRight className="h-3 w-3" />}
                    onClick={() => onPrepareApply(opp.id)}
                  >
                    Prepare apply
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        )}
      </section>

      {/* 6. Career Progress & Pipeline Funnel */}
      <section aria-label="Application progress" className="rounded-[var(--radius-card)] border border-white/[0.07] bg-[var(--color-surface)]">
        <div className="flex flex-col gap-1 border-b border-white/[0.06] px-4 py-3.5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="section-title">Pipeline Funnel</h2>
            <p className="mt-0.5 text-[12px] text-[var(--color-ink-tertiary)]">
              Stage distribution across {totalPipelineApps} tracked {totalPipelineApps === 1 ? 'application' : 'applications'}.
            </p>
          </div>
          <button
            type="button"
            onClick={() => onNavigateTab('analytics')}
            className="inline-flex items-center gap-1 whitespace-nowrap self-start rounded px-1 text-[12px] text-[var(--color-ink-secondary)] transition-colors hover:text-[var(--color-accent)] sm:self-auto focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)]"
          >
            Full Analytics <ChevronRight className="h-3 w-3" aria-hidden="true" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Funnel Progress Bar */}
          <div className="flex h-2 w-full overflow-hidden rounded-full bg-white/[0.04]" aria-hidden="true">
            {[
              { key: 'ready_to_apply', count: stages['ready_to_apply'] || 0, color: 'bg-slate-500' },
              { key: 'applied', count: stages['applied'] || 0, color: 'bg-[var(--color-accent)]' },
              { key: 'screening', count: stages['screening'] || 0, color: 'bg-sky-400' },
              { key: 'interviewing', count: stages['interviewing'] || 0, color: 'bg-teal-400' },
              { key: 'offered', count: stages['offered'] || 0, color: 'bg-amber-400' },
              { key: 'rejected', count: stages['rejected'] || 0, color: 'bg-rose-400/70' },
            ].map(st => {
              const pct = totalPipelineApps > 0 ? (st.count / totalPipelineApps) * 100 : 0;
              if (pct === 0) return null;
              return (
                <div
                  key={st.key}
                  style={{ width: `${pct}%` }}
                  className={`${st.color} h-full transition-colors duration-300`}
                  title={`${st.key}: ${st.count} roles (${Math.round(pct)}%)`}
                />
              );
            })}
          </div>

          {/* Stage Buttons Grid */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
            {[
              { key: 'ready_to_apply', label: 'Ready', count: stages['ready_to_apply'] || 0, dotColor: 'bg-slate-400' },
              { key: 'applied', label: 'Applied', count: stages['applied'] || 0, dotColor: 'bg-[var(--color-accent)]' },
              { key: 'screening', label: 'Screening', count: stages['screening'] || 0, dotColor: 'bg-sky-400' },
              { key: 'interviewing', label: 'Interview', count: stages['interviewing'] || 0, dotColor: 'bg-teal-400' },
              { key: 'offered', label: 'Offer', count: stages['offered'] || 0, dotColor: 'bg-amber-400' },
              { key: 'rejected', label: 'Archived', count: stages['rejected'] || 0, dotColor: 'bg-rose-400' },
            ].map(st => {
              const percentage = totalPipelineApps > 0 ? Math.round((st.count / totalPipelineApps) * 100) : 0;
              return (
                <button
                  key={st.key}
                  type="button"
                  onClick={() => onNavigateTab('tracker')}
                  className="flex flex-col items-start p-3 rounded-[var(--radius-xs)] border border-white/[0.05] bg-white/[0.02] text-left transition-colors hover:bg-white/[0.04] hover:border-white/[0.10] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-accent)]"
                  aria-label={`${st.label}: ${st.count} roles (${percentage}% of pipeline). Click to view in tracker.`}
                >
                  <div className="flex items-center gap-1.5 w-full justify-between">
                    <span className="text-[11px] font-medium text-[var(--color-ink-secondary)]">{st.label}</span>
                    <span className={`h-1.5 w-1.5 rounded-full ${st.dotColor}`} aria-hidden="true" />
                  </div>
                  <span className="mt-1 block font-mono text-[18px] font-semibold text-[var(--color-ink)] tnum">
                    <CountUp to={st.count} duration={0.6} />
                  </span>
                  <span className="text-[10px] font-mono text-[var(--color-ink-tertiary)] mt-0.5">
                    {percentage}% of total
                  </span>
                </button>
              );
            })}
          </div>

          {/* Funnel Metrics Summary Bar */}
          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-white/[0.05] pt-3 text-[11px] text-[var(--color-ink-secondary)]">
            <div className="flex items-center gap-2">
              <span className="text-[var(--color-ink-tertiary)]">Response rate:</span>
              <span className="font-mono font-medium text-[var(--color-ink)]">{pipeline?.response_rate || 0}%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[var(--color-ink-tertiary)]">Interview rate:</span>
              <span className="font-mono font-medium text-[var(--color-ink)]">{pipeline?.interview_rate || 0}%</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-[var(--color-ink-tertiary)]">Offer rate:</span>
              <span className="font-mono font-medium text-[var(--color-ink)]">{pipeline?.offer_rate || 0}%</span>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Strategic Focus Card */}
      {focus && (
        <section
          aria-label="Career strategic focus"
          className="rounded-[var(--radius-card)] border border-[var(--color-accent)]/20 bg-[var(--color-accent)]/[0.03] p-4 sm:flex sm:items-center sm:justify-between sm:gap-6 sm:p-5"
        >
          <div className="min-w-0">
            <div className="flex items-center gap-1.5">
              <Sparkles className="h-3.5 w-3.5 text-[var(--color-accent)]" strokeWidth={1.75} aria-hidden="true" />
              <span className="eyebrow text-[var(--color-accent)]">Strategic recommendation</span>
            </div>
            <h3 className="mt-1.5 text-[14px] font-medium text-[var(--color-ink)]">
              {focus.focus_area}
            </h3>
            <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-[var(--color-ink-secondary)]">
              {focus.reason} {focus.milestone_project && `Suggested milestone: ${focus.milestone_project}`}
            </p>
            {focus.weekly_pace && (
              <p className="mt-1 text-[11px] font-mono text-[var(--color-accent)]/80">
                Pace: {focus.weekly_pace}
              </p>
            )}
          </div>

          <div className="mt-4 shrink-0 sm:mt-0">
            <Button
              size="sm"
              variant="primary"
              leftIcon={<Sparkles className="h-3.5 w-3.5" />}
              rightIcon={<ArrowRight className="h-3 w-3" />}
              onClick={() => onNavigateTab('chat')}
              className="whitespace-nowrap w-full sm:w-auto"
            >
              Build action plan
            </Button>
          </div>
        </section>
      )}
    </div>
  );
};
