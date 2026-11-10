import React, { useState } from 'react';
import {
  ExternalLink,
  Search,
  ArrowUpDown,
  FileText,
  Mail,
  Calendar,
  Sparkles,
  Trash2,
  Clock,
  Video
} from 'lucide-react';
import { ApplicationRecord } from '../../types';

const Linkedin = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
    <rect width="4" height="12" x="2" y="9" />
    <circle cx="4" cy="4" r="2" />
  </svg>
);

interface ApplicationTableViewProps {
  applications: ApplicationRecord[];
  onSelectApp: (app: ApplicationRecord) => void;
  onStatusChange: (id: number, newStatus: string) => void;
  onDeleteApp: (id: number) => void;
  onOpenFollowUpModal: (app: ApplicationRecord) => void;
  onOpenScheduleModal: (app: ApplicationRecord) => void;
}

export const ApplicationTableView: React.FC<ApplicationTableViewProps> = ({
  applications,
  onSelectApp,
  onStatusChange,
  onDeleteApp,
  onOpenFollowUpModal,
  onOpenScheduleModal
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'applied_date' | 'match_score' | 'company_name' | 'follow_up_date'>('applied_date');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  const statusOptions = [
    { id: 'all', label: 'All Stages' },
    { id: 'ready_to_apply', label: 'Ready to Apply' },
    { id: 'applied', label: 'Applied' },
    { id: 'screening', label: 'Screening' },
    { id: 'interviewing', label: 'Interviewing' },
    { id: 'offered', label: 'Offer Received' },
    { id: 'rejected', label: 'Rejected' },
    { id: 'withdrawn', label: 'Withdrawn' }
  ];

  // Filtering
  const filteredApps = applications.filter((app) => {
    const matchesSearch =
      searchTerm === '' ||
      app.company_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      app.job_title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (app.recruiter_name && app.recruiter_name.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesStatus =
      statusFilter === 'all' ||
      (statusFilter === 'interviewing' ? (app.status.includes('interview') || app.status === 'interviewing') : app.status === statusFilter);

    return matchesSearch && matchesStatus;
  });

  // Sorting
  const sortedApps = [...filteredApps].sort((a, b) => {
    let aVal: any = a[sortBy];
    let bVal: any = b[sortBy];

    if (sortBy === 'applied_date' || sortBy === 'follow_up_date') {
      aVal = aVal ? new Date(aVal).getTime() : 0;
      bVal = bVal ? new Date(bVal).getTime() : 0;
    }

    if (aVal === bVal) return 0;
    if (sortOrder === 'asc') {
      return aVal > bVal ? 1 : -1;
    } else {
      return aVal < bVal ? 1 : -1;
    }
  });

  const toggleSort = (field: 'applied_date' | 'match_score' | 'company_name' | 'follow_up_date') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  const now = new Date();

  return (
    <div className="space-y-4">
      {/* Controls Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper-quiet)] p-3.5">
        <div className="relative flex-1 w-full sm:max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-ink-tertiary)]" aria-hidden="true" />
          <input
            type="text"
            aria-label="Search applications table"
            placeholder="Search company, job title, recruiter..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="w-full min-h-[36px] rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper)] pl-9 pr-3 py-1.5 text-xs text-[var(--color-ink)] placeholder-[var(--color-ink-tertiary)] outline-none transition-colors focus:border-[var(--color-primary)]"
          />
        </div>

        <div className="flex items-center space-x-2.5 w-full sm:w-auto">
          <select
            aria-label="Filter applications by stage"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="min-h-[36px] rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper)] px-3 py-1.5 text-xs font-medium text-[var(--color-ink-secondary)] outline-none transition-colors hover:border-white/[0.16] focus:border-[var(--color-primary)]"
          >
            {statusOptions.map((opt) => (
              <option key={opt.id} value={opt.id} className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">
                {opt.label}
              </option>
            ))}
          </select>
          <span className="font-mono text-xs text-[var(--color-ink-muted)] whitespace-nowrap tnum">
            {sortedApps.length} records
          </span>
        </div>
      </div>

      {/* Data Table */}
      <div className="overflow-hidden rounded-xl border border-white/[0.07] bg-[var(--color-paper-quiet)] shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs text-[var(--color-ink-secondary)]">
            <thead className="border-b border-white/[0.07] bg-[var(--color-paper)]/70 text-[11px] font-semibold text-[var(--color-ink-muted)]">
              <tr>
                <th className="p-3.5 cursor-pointer select-none transition-colors hover:text-[var(--color-ink)]" onClick={() => toggleSort('company_name')}>
                  <div className="flex items-center space-x-1.5">
                    <span>Company & Position</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th className="p-3.5">Stage</th>
                <th className="p-3.5 cursor-pointer select-none transition-colors hover:text-[var(--color-ink)]" onClick={() => toggleSort('match_score')}>
                  <div className="flex items-center space-x-1.5">
                    <span>Match</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th className="p-3.5">Salary / Stipend</th>
                <th className="p-3.5">Recruiter</th>
                <th className="p-3.5 cursor-pointer select-none transition-colors hover:text-[var(--color-ink)]" onClick={() => toggleSort('follow_up_date')}>
                  <div className="flex items-center space-x-1.5">
                    <span>Follow-Up</span>
                    <ArrowUpDown className="h-3 w-3" />
                  </div>
                </th>
                <th className="p-3.5">Interviews</th>
                <th className="p-3.5 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-white/[0.05]">
              {sortedApps.map((app) => {
                const isFollowUpDue = app.follow_up_date && new Date(app.follow_up_date) <= now;
                const hasInterviews = app.interview_schedule && app.interview_schedule.length > 0;
                const companyInitials = (app.company_name || 'CO')
                  .split(' ')
                  .map(w => w[0])
                  .filter(Boolean)
                  .slice(0, 2)
                  .join('')
                  .toUpperCase();

                return (
                  <tr
                    key={app.id}
                    onClick={() => onSelectApp(app)}
                    className="group transition-colors hover:bg-white/[0.03] cursor-pointer"
                  >
                    {/* Company & Position */}
                    <td className="p-3.5 min-w-[200px]">
                      <div className="flex items-center gap-2.5">
                        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-white/[0.08] bg-white/[0.04] text-[10px] font-bold text-[var(--color-ink-muted)]">
                          {companyInitials}
                        </div>
                        <div className="min-w-0">
                          <span className="block text-xs font-semibold text-[var(--color-ink)] leading-tight">{app.company_name}</span>
                          <span className="block text-[11px] text-[var(--color-ink-secondary)] mt-0.5 line-clamp-1">{app.job_title}</span>
                          {app.resume_id && (
                            <span className="mt-1 inline-flex items-center gap-1 font-mono text-[10px] text-teal-400">
                              <FileText className="h-2.5 w-2.5" />
                              <span>Resume {app.resume_version_number ? `v${app.resume_version_number}` : 'Attached'}</span>
                            </span>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Stage Dropdown */}
                    <td className="p-3.5" onClick={(e) => e.stopPropagation()}>
                      <select
                        aria-label={`Change stage for ${app.company_name} - ${app.job_title}`}
                        value={app.status}
                        onChange={(e) => onStatusChange(app.id, e.target.value)}
                        className="min-h-[28px] rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-2)] px-2 py-1 text-xs font-medium text-[var(--color-primary)] outline-none transition-colors hover:border-white/[0.16] focus:border-[var(--color-primary)] capitalize"
                      >
                        <option value="ready_to_apply" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Ready to Apply</option>
                        <option value="applied" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Applied</option>
                        <option value="screening" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Screening</option>
                        <option value="interviewing" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Interviewing</option>
                        <option value="offered" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Offer Received</option>
                        <option value="rejected" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Rejected</option>
                        <option value="withdrawn" className="bg-[var(--color-paper-2)] text-[var(--color-ink)]">Withdrawn</option>
                      </select>
                    </td>

                    {/* Match Score */}
                    <td className="p-3.5 font-mono text-xs font-semibold text-[var(--color-primary)] tnum">
                      {Math.round(app.match_score)}%
                    </td>

                    {/* Salary / Stipend */}
                    <td className="p-3.5 whitespace-nowrap">
                      {app.salary_or_stipend ? (
                        <span className="rounded border border-emerald-500/20 bg-emerald-500/[0.08] px-2 py-0.5 font-mono text-[11px] font-medium text-emerald-400">
                          {app.salary_or_stipend}
                        </span>
                      ) : (
                        <span className="text-[var(--color-ink-tertiary)] text-xs">-</span>
                      )}
                    </td>

                    {/* Recruiter */}
                    <td className="p-3.5 min-w-[150px]">
                      {app.recruiter_name ? (
                        <div>
                          <span className="block text-xs font-medium text-[var(--color-ink)]">{app.recruiter_name}</span>
                          {app.recruiter_position && (
                            <span className="block text-[10px] text-[var(--color-ink-tertiary)]">{app.recruiter_position}</span>
                          )}
                          <div className="mt-1 flex items-center space-x-2">
                            {app.recruiter_email && (
                              <a
                                href={`mailto:${app.recruiter_email}`}
                                onClick={(e) => e.stopPropagation()}
                                className="text-[var(--color-ink-tertiary)] transition-colors hover:text-[var(--color-primary)]"
                                title={app.recruiter_email}
                              >
                                <Mail className="h-3 w-3" />
                              </a>
                            )}
                            {app.recruiter_linkedin && (
                              <a
                                href={app.recruiter_linkedin}
                                target="_blank"
                                rel="noopener noreferrer"
                                onClick={(e) => e.stopPropagation()}
                                className="text-[var(--color-ink-tertiary)] transition-colors hover:text-sky-400"
                                title="LinkedIn Profile"
                              >
                                <Linkedin className="h-3 w-3" />
                              </a>
                            )}
                          </div>
                        </div>
                      ) : (
                        <span className="text-[var(--color-ink-tertiary)] text-xs">-</span>
                      )}
                    </td>

                    {/* Follow-Up */}
                    <td className="p-3.5 whitespace-nowrap">
                      {app.follow_up_date ? (
                        <div className="flex items-center space-x-1.5">
                          <span className={`text-xs ${isFollowUpDue ? 'font-semibold text-amber-400' : 'text-[var(--color-ink-secondary)]'}`}>
                            {new Date(app.follow_up_date).toLocaleDateString([], { month: 'short', day: 'numeric' })}
                          </span>
                          {isFollowUpDue && (
                            <span className="rounded border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.2 text-[9px] font-bold text-amber-300">
                              Due
                            </span>
                          )}
                        </div>
                      ) : (
                        <span className="text-[var(--color-ink-tertiary)] text-xs">Not set</span>
                      )}
                    </td>

                    {/* Interviews */}
                    <td className="p-3.5 whitespace-nowrap">
                      {hasInterviews ? (
                        <span className="inline-flex items-center gap-1 rounded border border-sky-400/25 bg-sky-400/[0.06] px-2 py-0.5 text-[11px] font-medium text-sky-300">
                          <Video className="h-3 w-3 text-sky-400" />
                          <span>{app.interview_schedule!.length} round(s)</span>
                        </span>
                      ) : (
                        <span className="text-[var(--color-ink-tertiary)] text-xs">0 rounds</span>
                      )}
                    </td>

                    {/* Actions */}
                    <td className="p-3.5 text-right whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                      <div className="flex items-center justify-end space-x-1">
                        <button
                          type="button"
                          onClick={() => onOpenFollowUpModal(app)}
                          className="rounded p-1.5 text-[var(--color-ink-tertiary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-primary)]"
                          title="Generate Follow-Up Draft"
                          aria-label={`Generate follow up for ${app.company_name}`}
                        >
                          <Sparkles className="h-3.5 w-3.5" />
                        </button>

                        <button
                          type="button"
                          onClick={() => onOpenScheduleModal(app)}
                          className="rounded p-1.5 text-[var(--color-ink-tertiary)] transition-colors hover:bg-white/[0.06] hover:text-sky-400"
                          title="Schedule Interview Round"
                          aria-label={`Schedule interview for ${app.company_name}`}
                        >
                          <Calendar className="h-3.5 w-3.5" />
                        </button>

                        {app.original_url && (
                          <a
                            href={app.original_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="rounded p-1.5 text-[var(--color-ink-tertiary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                            title="Open Job Listing"
                            aria-label={`Open job listing for ${app.company_name}`}
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                          </a>
                        )}

                        <button
                          type="button"
                          onClick={() => onDeleteApp(app.id)}
                          className="rounded p-1.5 text-[var(--color-ink-tertiary)] transition-colors hover:bg-rose-500/10 hover:text-rose-400"
                          title="Remove from tracking"
                          aria-label={`Remove application for ${app.company_name}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}

              {sortedApps.length === 0 && (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-xs text-[var(--color-ink-tertiary)]">
                    No matching applications found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
