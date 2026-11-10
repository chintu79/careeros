import React, { useState, useEffect } from 'react';
import {
  Clock,
  Calendar,
  Video,
  Mail,
  ArrowRight,
  Search,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
  Building,
  Sparkles,
  RefreshCw,
  AlertTriangle
} from 'lucide-react';
import { ApplicationTimelineEvent, ApplicationRecord } from '../../types';
import { fetchApplicationTimeline } from '../../services/api';

interface ApplicationTimelineViewProps {
  applications?: ApplicationRecord[];
  onSelectApp?: (app: ApplicationRecord) => void;
  onOpenFollowUpModal?: (app: ApplicationRecord) => void;
  onNavigateToInterviewPrep?: (company?: string, role?: string) => void;
}

export const ApplicationTimelineView: React.FC<ApplicationTimelineViewProps> = ({
  applications = [],
  onSelectApp,
  onOpenFollowUpModal,
  onNavigateToInterviewPrep
}) => {
  const [events, setEvents] = useState<ApplicationTimelineEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const loadTimeline = (cat = activeCategory) => {
    setLoading(true);
    setError(null);
    fetchApplicationTimeline(100, cat)
      .then((data) => {
        const list = Array.isArray(data) ? data : (data as any)?.events || [];
        setEvents(list);
      })
      .catch((err) => {
        console.error('Failed to load timeline:', err);
        setError('Failed to load application timeline. Please try again.');
      })
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadTimeline(activeCategory);
  }, [activeCategory]);

  const getSourceIcon = (sourceType?: string, eventCat?: string) => {
    if (sourceType === 'email' || eventCat === 'email') {
      return <Mail className="w-4 h-4 text-blue-400" />;
    }
    if (sourceType === 'calendar' || sourceType === 'interview_schedule' || eventCat?.includes('interview')) {
      return <Video className="w-4 h-4 text-sky-300" />;
    }
    if (sourceType === 'deadline' || eventCat?.includes('deadline')) {
      return <AlertTriangle className="w-4 h-4 text-rose-400" />;
    }
    if (sourceType === 'follow_up' || eventCat?.includes('follow_up')) {
      return <Clock className="w-4 h-4 text-amber-400" />;
    }
    if (sourceType === 'stage_transition' || eventCat === 'stage_change') {
      return <ArrowRight className="w-4 h-4 text-emerald-400" />;
    }
    return <Clock className="w-4 h-4 text-slate-400" />;
  };

  const getSourceBadge = (sourceType?: string, eventCat?: string) => {
    if (sourceType === 'email') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30">
          Email
        </span>
      );
    }
    if (sourceType === 'calendar' || sourceType === 'interview_schedule' || eventCat?.includes('interview')) {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-semibold border border-sky-400/25 bg-sky-400/[0.06] text-sky-300">
          Interview
        </span>
      );
    }
    if (sourceType === 'deadline') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30">
          Deadline
        </span>
      );
    }
    if (sourceType === 'follow_up') {
      return (
        <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
          Follow-up Due
        </span>
      );
    }
    if (sourceType === 'stage_transition' || eventCat === 'stage_change') {
      return (
        <span className="rounded border border-emerald-400/25 bg-emerald-400/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
          Stage Update
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-700/50 text-slate-300 border border-slate-600/30">
        Activity
      </span>
    );
  };

  const filteredEvents = events.filter((ev) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      ev.company_name?.toLowerCase().includes(query) ||
      ev.job_title?.toLowerCase().includes(query) ||
      ev.title?.toLowerCase().includes(query) ||
      ev.description?.toLowerCase().includes(query) ||
      ev.details?.toLowerCase().includes(query) ||
      ev.sender?.toLowerCase().includes(query)
    );
  });

  return (
    <div className="space-y-4">
      {/* Control bar: Search + Category Pills */}
      <div className="flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3 border border-white/[0.07] bg-[var(--color-paper)] p-3.5 rounded-xl">
        <div className="relative flex-1 sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search activities, companies, emails..."
            className="w-full bg-slate-950 border border-white/[0.09] rounded-lg pl-9 pr-3 py-1.5 text-xs text-[var(--color-ink)] placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="flex items-center space-x-1.5 overflow-x-auto text-xs pb-1 sm:pb-0">
          {[
            { id: 'all', label: 'All Activity' },
            { id: 'emails', label: 'Synced Emails' },
            { id: 'interviews', label: 'Interviews' },
            { id: 'deadlines', label: 'Deadlines' },
            { id: 'follow_ups', label: 'Follow-ups' },
            { id: 'updates', label: 'Stage Updates' }
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveCategory(tab.id)}
              className={`inline-flex min-h-[28px] items-center whitespace-nowrap rounded-md border px-2.5 text-[11px] font-medium transition-colors ${
                activeCategory === tab.id
                  ? 'border-white/[0.10] bg-white/[0.08] text-[var(--color-ink)]'
                  : 'border-transparent text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
              }`}
            >
              {tab.label}
            </button>
          ))}

          <button
            type="button"
            onClick={() => loadTimeline(activeCategory)}
            aria-label="Refresh timeline"
            className="p-1.5 text-slate-400 hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-3)] rounded-lg transition"
            title="Refresh Timeline"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Main content */}
      {loading ? (
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-12 text-center text-slate-400">
          <Clock className="w-6 h-6 text-slate-500 mx-auto animate-spin mb-2" />
          <p className="text-sm">Loading activity center...</p>
        </div>
      ) : error ? (
        <div className="bg-rose-500/10 border border-rose-500/20 rounded-xl p-6 text-center text-rose-400">
          <AlertCircle className="w-6 h-6 mx-auto mb-2" />
          <p className="text-sm font-semibold">{error}</p>
          <button
            type="button"
            onClick={() => loadTimeline(activeCategory)}
            className="mt-3 px-3 py-1 bg-white/[0.04] hover:bg-white/[0.07] text-[var(--color-ink)] rounded text-xs"
          >
            Retry
          </button>
        </div>
      ) : filteredEvents.length === 0 ? (
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-12 text-center text-slate-400 space-y-2">
          <Calendar className="w-8 h-8 text-slate-600 mx-auto" />
          <h3 className="text-sm font-semibold text-[var(--color-ink)]">No activity events found</h3>
          <p className="text-xs text-slate-500 max-w-sm mx-auto">
            {activeCategory === 'all'
              ? 'As you submit applications, update pipeline stages, receive career emails, and schedule interviews, your chronological journey will appear here.'
              : `No events found in "${activeCategory}". Select "All Activity" or connect an account in Settings.`}
          </p>
        </div>
      ) : (
        <div className="relative pl-6 sm:pl-8 before:absolute before:left-3 before:top-2 before:bottom-2 before:w-0.5 before:bg-[var(--color-paper-3)] space-y-4">
          {filteredEvents.map((event) => {
            const formattedDate = event.timestamp
              ? new Date(event.timestamp).toLocaleString(undefined, {
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric',
                  hour: '2-digit',
                  minute: '2-digit'
                })
              : 'Unknown date';

            const linkedApp = applications.find((a) => a.id === event.application_id);
            const contentText = event.description || event.details;
            const isInterview = event.source_type === 'calendar' || event.source_type === 'interview_schedule' || Boolean(event.meeting_link);

            return (
              <div key={event.id} className="relative group">
                {/* Timeline node icon */}
                <div className="absolute -left-6 sm:-left-8 top-1.5 w-6 h-6 rounded-full bg-[var(--color-paper-2)] border border-white/[0.09] flex items-center justify-center">
                  {getSourceIcon(event.source_type, event.event_category)}
                </div>

                {/* Event card */}
                <div className="border border-white/[0.07] bg-[var(--color-paper)] hover:border-white/[0.13] rounded-xl p-4 transition space-y-2.5">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
                    <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                      <span className="font-semibold text-[var(--color-ink)] text-sm">{event.title}</span>
                      {getSourceBadge(event.source_type, event.event_category)}
                      {event.review_status === 'pending_review' && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-bold bg-amber-500/20 text-amber-300 border border-amber-500/30">
                          Pending Review
                        </span>
                      )}
                    </div>
                    <span className="text-[11px] text-slate-500 font-mono">{formattedDate}</span>
                  </div>

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
                    <span className="flex items-center space-x-1 text-slate-300 font-medium">
                      <Building className="w-3.5 h-3.5 text-slate-500" />
                      <span>{event.company_name}</span>
                    </span>
                    <span className="text-slate-600">•</span>
                    <span>{event.job_title}</span>
                    {event.sender && (
                      <>
                        <span className="text-slate-600">•</span>
                        <span className="text-slate-400 font-mono">From: {event.sender}</span>
                      </>
                    )}
                  </div>

                  {contentText && (
                    <div className="text-xs text-slate-300 bg-slate-950/70 p-2.5 rounded-lg border border-white/[0.07]/80 leading-relaxed font-sans">
                      {contentText}
                    </div>
                  )}

                  {/* Meeting link badge if present */}
                  {event.meeting_link && (
                    <div className="pt-0.5">
                      <a
                        href={event.meeting_link}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex min-h-[28px] items-center gap-1.5 rounded-md border border-white/[0.09] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Video className="w-3.5 h-3.5 text-emerald-400" />
                        <span>Join {event.meeting_platform || 'Video Meeting'}</span>
                        <ExternalLink className="w-3 h-3 text-emerald-400" />
                      </a>
                    </div>
                  )}

                  {event.notes && (
                    <div className="text-[11px] text-slate-400 italic">
                      Note: {event.notes}
                    </div>
                  )}

                  {/* Action buttons */}
                  <div className="pt-2 flex items-center justify-end space-x-2 border-t border-white/[0.07]/60">
                    {isInterview && onNavigateToInterviewPrep && (
                      <button
                        type="button"
                        onClick={() => onNavigateToInterviewPrep(event.company_name, event.job_title)}
                        className="px-2.5 py-1 text-[11px] font-semibold border border-sky-400/25 bg-sky-400/[0.06] text-sky-300 hover:bg-sky-400/[0.10] rounded flex items-center space-x-1 transition"
                      >
                        <Sparkles className="w-3 h-3 text-sky-300" />
                        <span>Prepare for Interview</span>
                      </button>
                    )}

                    {linkedApp && onOpenFollowUpModal && (
                      <button
                        type="button"
                        onClick={() => onOpenFollowUpModal(linkedApp)}
                        className="inline-flex min-h-[26px] items-center gap-1 rounded border border-white/[0.09] bg-white/[0.03] px-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Sparkles className="w-3 h-3" />
                        <span>Follow-up</span>
                      </button>
                    )}

                    {linkedApp && onSelectApp && (
                      <button
                        type="button"
                        onClick={() => onSelectApp(linkedApp)}
                        className="px-2.5 py-1 text-[11px] font-medium bg-white/[0.04] hover:bg-white/[0.07] text-slate-200 rounded flex items-center space-x-1 transition"
                      >
                        <span>View Details</span>
                        <ExternalLink className="w-3 h-3 text-slate-400" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
