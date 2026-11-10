import React from 'react';
import {
  FileText,
  Clock,
  User,
  Video,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { ApplicationRecord } from '../../types';

interface ApplicationKanbanViewProps {
  applications: ApplicationRecord[];
  selectedApp: ApplicationRecord | null;
  onSelectApp: (app: ApplicationRecord) => void;
  onStatusChange: (id: number, newStatus: string) => void;
  onOpenFollowUpModal: (app: ApplicationRecord) => void;
  onOpenScheduleModal: (app: ApplicationRecord) => void;
}

export const ApplicationKanbanView: React.FC<ApplicationKanbanViewProps> = ({
  applications,
  selectedApp,
  onSelectApp,
  onStatusChange,
}) => {
  const statusColumns = [
    { id: 'ready_to_apply', label: 'Ready to apply', dot: 'bg-slate-400' },
    { id: 'applied', label: 'Applied', dot: 'bg-emerald-400' },
    { id: 'screening', label: 'Screening', dot: 'bg-sky-400' },
    { id: 'interviewing', label: 'Interviewing', dot: 'bg-teal-400' },
    { id: 'offered', label: 'Offer received', dot: 'bg-amber-400' },
    { id: 'rejected', label: 'Rejected', dot: 'bg-rose-400/70' }
  ];

  const now = new Date();

  return (
    <div className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 snap-x">
      {statusColumns.map((col) => {
        const colApps = applications.filter((a) => {
          const s = (a.status || 'ready_to_apply').toLowerCase();
          if (col.id === 'interviewing') {
            return s === 'interviewing' || s.includes('interview');
          }
          return s === col.id;
        });

        return (
          <section
            key={col.id}
            aria-label={`${col.label} column`}
            className="flex w-[280px] shrink-0 snap-start flex-col rounded-xl border border-white/[0.07] bg-[var(--color-paper-quiet)] shadow-sm"
          >
            {/* Column header */}
            <div className="flex items-center justify-between border-b border-white/[0.06] bg-[var(--color-paper)]/50 px-3.5 py-2.5 rounded-t-xl">
              <span className="flex items-center gap-2 text-[12px] font-semibold text-[var(--color-ink)]">
                <span className={`h-2 w-2 rounded-full ${col.dot}`} aria-hidden="true" />
                {col.label}
              </span>
              <span className="rounded-full bg-white/[0.05] px-2 py-0.5 font-mono text-[11px] font-medium text-[var(--color-ink-muted)] tnum">
                {colApps.length}
              </span>
            </div>

            {/* Cards */}
            <div className="flex-1 space-y-2.5 p-2.5">
              {colApps.map((app) => {
                const isSelected = selectedApp?.id === app.id;
                const isFollowUpDue = app.follow_up_date && new Date(app.follow_up_date) <= now;
                const hasInterviews = app.interview_schedule && app.interview_schedule.length > 0;
                const currentColIndex = statusColumns.findIndex(c => c.id === (app.status || 'ready_to_apply'));

                return (
                  <article
                    key={app.id}
                    className={`group rounded-lg border p-3.5 transition-colors duration-150 ${
                      isSelected
                        ? 'border-[var(--color-primary)]/50 bg-[var(--color-primary)]/[0.03] shadow-[0_0_0_1px_var(--color-accent-border)]'
                        : 'border-white/[0.06] bg-[var(--color-paper-2)] hover:border-white/[0.12] hover:bg-[var(--color-paper-3)]'
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => onSelectApp(app)}
                      className="w-full rounded text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-focus)]"
                    >
                      <span className="flex items-start justify-between gap-2">
                        <span className="min-w-0">
                          <span className="block truncate text-[11px] font-medium text-[var(--color-ink-tertiary)]">
                            {app.company_name}
                          </span>
                          <span className="mt-0.5 block text-[13px] font-semibold leading-snug text-[var(--color-ink)] line-clamp-2">
                            {app.job_title}
                          </span>
                        </span>
                        <span className="shrink-0 font-mono text-[11px] font-semibold text-[var(--color-primary)] tnum">
                          {Math.round(app.match_score)}%
                        </span>
                      </span>
                    </button>

                    {app.salary_or_stipend && (
                      <p className="mt-2 inline-block rounded border border-white/[0.05] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-ink-secondary)]">
                        {app.salary_or_stipend}
                      </p>
                    )}

                    {(app.recruiter_name || app.recruiter_position) && (
                      <p className="mt-2 flex items-center gap-1.5 truncate text-[11px] text-[var(--color-ink-secondary)]">
                        <User className="h-3 w-3 shrink-0 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
                        <span className="truncate">
                          {app.recruiter_name} {app.recruiter_position ? `(${app.recruiter_position})` : ''}
                        </span>
                      </p>
                    )}

                    {hasInterviews && (
                      <p className="mt-1.5 flex items-center gap-1.5 truncate text-[11px] text-sky-400">
                        <Video className="h-3 w-3 shrink-0" strokeWidth={1.75} aria-hidden="true" />
                        <span className="truncate">
                          {app.interview_schedule![app.interview_schedule!.length - 1].round_name}
                        </span>
                      </p>
                    )}

                    <div className="mt-2.5 flex items-center justify-between gap-2 border-t border-white/[0.05] pt-2 text-[11px]">
                      {app.resume_id ? (
                        <span className="flex items-center gap-1 text-[var(--color-ink-secondary)]" title="Tailored resume linked">
                          <FileText className="h-3 w-3 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
                          <span>Resume {app.resume_version_number ? `v${app.resume_version_number}` : ''}</span>
                        </span>
                      ) : (
                        <span className="text-[var(--color-ink-tertiary)]">Master profile</span>
                      )}

                      {isFollowUpDue ? (
                        <span className="flex items-center gap-1 rounded bg-amber-400/10 px-1.5 py-0.5 font-medium text-amber-400 border border-amber-400/20" title="Follow-up reminder due">
                          <Clock className="h-2.5 w-2.5" strokeWidth={2} aria-hidden="true" />
                          <span>Due</span>
                        </span>
                      ) : app.applied_date ? (
                        <span className="font-mono text-[var(--color-ink-tertiary)]">
                          {new Date(app.applied_date).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                        </span>
                      ) : (
                        <span className="text-[var(--color-ink-tertiary)]">Draft</span>
                      )}
                    </div>

                    {/* Stage control */}
                    <div className="mt-2.5 space-y-1.5 border-t border-white/[0.05] pt-2">
                      <select
                        value={app.status || 'ready_to_apply'}
                        onChange={(e) => onStatusChange(app.id, e.target.value)}
                        onClick={(e) => e.stopPropagation()}
                        aria-label={`Change stage for ${app.company_name} - ${app.job_title}`}
                        className="w-full min-h-[28px] rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper)] px-2 py-1 text-[11px] font-medium text-[var(--color-ink-secondary)] outline-none transition-colors hover:border-white/[0.16] focus:border-[var(--color-primary)]"
                      >
                        {statusColumns.map((c) => (
                          <option key={c.id} value={c.id} className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">
                            Move to: {c.label}
                          </option>
                        ))}
                      </select>

                      <div className="flex items-center justify-between gap-1">
                        <button
                          type="button"
                          disabled={currentColIndex <= 0}
                          onClick={() => {
                            if (currentColIndex > 0) {
                              onStatusChange(app.id, statusColumns[currentColIndex - 1].id);
                            }
                          }}
                          aria-label={`Move ${app.company_name} to ${currentColIndex > 0 ? statusColumns[currentColIndex - 1].label : 'previous stage'}`}
                          className="inline-flex min-h-[24px] items-center gap-0.5 rounded px-2 text-[11px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)] disabled:pointer-events-none disabled:opacity-25"
                        >
                          <ChevronLeft className="h-3 w-3" />
                          <span>Prev</span>
                        </button>

                        <button
                          type="button"
                          disabled={currentColIndex >= statusColumns.length - 1}
                          onClick={() => {
                            if (currentColIndex < statusColumns.length - 1) {
                              onStatusChange(app.id, statusColumns[currentColIndex + 1].id);
                            }
                          }}
                          aria-label={`Move ${app.company_name} to ${currentColIndex < statusColumns.length - 1 ? statusColumns[currentColIndex + 1].label : 'next stage'}`}
                          className="inline-flex min-h-[24px] items-center gap-0.5 rounded px-2 text-[11px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)] disabled:pointer-events-none disabled:opacity-25"
                        >
                          <span>Advance stage</span>
                          <ChevronRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}

              {colApps.length === 0 && (
                <div className="flex h-24 items-center justify-center rounded-lg border border-dashed border-white/[0.07] text-[11px] text-[var(--color-ink-tertiary)]">
                  Empty
                </div>
              )}
            </div>
          </section>
        );
      })}
    </div>
  );
};
