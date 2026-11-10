import React, { useState, useEffect } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Calendar as CalendarIcon,
  Video,
  Clock,
  AlertTriangle,
  Send,
  Building,
  Sparkles,
  ExternalLink,
  Plus
} from 'lucide-react';
import { ApplicationCalendarEvent, ApplicationRecord } from '../../types';
import { fetchApplicationCalendar } from '../../services/api';

interface ApplicationCalendarViewProps {
  applications?: ApplicationRecord[];
  onSelectApp?: (app: ApplicationRecord) => void;
  onOpenFollowUpModal?: (app: ApplicationRecord) => void;
  onOpenScheduleModal?: (app: ApplicationRecord) => void;
  onNavigateToInterviewPrep?: (company?: string, role?: string) => void;
}

export const ApplicationCalendarView: React.FC<ApplicationCalendarViewProps> = ({
  applications = [],
  onSelectApp,
  onOpenFollowUpModal,
  onOpenScheduleModal,
  onNavigateToInterviewPrep
}) => {
  const [currentDate, setCurrentDate] = useState<Date>(new Date());
  const [events, setEvents] = useState<ApplicationCalendarEvent[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [selectedDayEvents, setSelectedDayEvents] = useState<{ dateStr: string; events: ApplicationCalendarEvent[] } | null>(null);

  // Month navigation
  const year = currentDate.getFullYear();
  const month = currentDate.getMonth(); // 0-indexed

  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);

  // Range for API query (include padding days)
  const startQueryDate = new Date(year, month, 1 - firstDayOfMonth.getDay());
  const endQueryDate = new Date(year, month + 1, 6 - lastDayOfMonth.getDay());

  // loadCalendar is only consumed by the effect; defining it (and the range it
  // depends on) inside keeps the closure provably current with [year, month].
  useEffect(() => {
    const loadCalendar = () => {
      setLoading(true);
      const firstDayOfMonth2 = new Date(year, month, 1);
      const lastDayOfMonth2 = new Date(year, month + 1, 0);
      const start = new Date(year, month, 1 - firstDayOfMonth2.getDay());
      const end = new Date(year, month + 1, 6 - lastDayOfMonth2.getDay());
      const startStr = start.toISOString().split('T')[0];
      const endStr = end.toISOString().split('T')[0];

      fetchApplicationCalendar(startStr, endStr)
        .then((data) => {
          const list = Array.isArray(data) ? data : (data as any)?.events || [];
          setEvents(list);
        })
        .catch((err) => {
          console.error('Failed to load calendar events:', err);
        })
        .finally(() => setLoading(false));
    };

    loadCalendar();
  }, [year, month]);

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const goToday = () => {
    setCurrentDate(new Date());
  };

  // Generate day grid
  const daysInGrid: { date: Date; isCurrentMonth: boolean; dateStr: string }[] = [];
  const curr = new Date(startQueryDate);
  while (curr <= endQueryDate) {
    daysInGrid.push({
      date: new Date(curr),
      isCurrentMonth: curr.getMonth() === month,
      dateStr: curr.toISOString().split('T')[0]
    });
    curr.setDate(curr.getDate() + 1);
  }

  const todayStr = new Date().toISOString().split('T')[0];

  const getEventBadgeClass = (eventType: string) => {
    switch (eventType) {
      case 'applied':
        return 'border border-sky-400/25 bg-sky-400/[0.06] text-sky-300';
      case 'follow_up_due':
        return 'border border-amber-400/25 bg-amber-400/[0.06] text-amber-300';
      case 'interview':
        return 'border border-sky-400/25 bg-sky-400/[0.07] text-sky-300';
      case 'deadline':
        return 'border border-rose-400/25 bg-rose-400/[0.06] text-rose-300';
      default:
        return 'border border-white/[0.08] bg-white/[0.03] text-slate-400';
    }
  };

  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'applied':
        return <Send className="w-2.5 h-2.5 shrink-0" />;
      case 'follow_up_due':
        return <Clock className="w-2.5 h-2.5 shrink-0" />;
      case 'interview':
        return <Video className="w-2.5 h-2.5 shrink-0" />;
      case 'deadline':
        return <AlertTriangle className="w-2.5 h-2.5 shrink-0" />;
      default:
        return <CalendarIcon className="w-2.5 h-2.5 shrink-0" />;
    }
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  return (
    <div className="space-y-4">
      {/* Header controls & Legend */}
      <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3 border border-white/[0.07] bg-[var(--color-paper)] p-3.5 rounded-xl">
        <div className="flex items-center space-x-3">
          <div className="flex items-center gap-0.5 rounded-lg border border-white/[0.07] bg-black/20 p-0.5">
            <button
              onClick={prevMonth}
              className="rounded p-1.5 text-slate-400 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
              title="Previous Month"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={goToday}
              className="rounded px-2.5 py-1 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
            >
              Today
            </button>
            <button
              onClick={nextMonth}
              className="rounded p-1.5 text-slate-400 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
              title="Next Month"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>

          <h3 className="flex items-center gap-2 text-[15px] font-semibold text-[var(--color-ink)]">
            <CalendarIcon className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
            <span>
              {monthNames[month]} {year}
            </span>
          </h3>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-2 text-[11px]">
          <span className="inline-flex items-center gap-1.5 rounded border border-sky-400/20 bg-sky-400/[0.05] px-1.5 py-0.5 text-[10px] font-medium text-sky-300">
            <span className="h-1 w-1 rounded-full bg-sky-400"></span>
            <span>Applied</span>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded border border-amber-400/20 bg-amber-400/[0.05] px-1.5 py-0.5 text-[10px] font-medium text-amber-300">
            <span className="h-1 w-1 rounded-full bg-amber-400"></span>
            <span>Follow-up Due</span>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded border border-sky-400/20 bg-sky-400/[0.05] px-1.5 py-0.5 text-[10px] font-medium text-sky-300">
            <span className="h-1 w-1 rounded-full bg-sky-400"></span>
            <span>Interview</span>
          </span>
          <span className="inline-flex items-center gap-1.5 rounded border border-rose-400/20 bg-rose-400/[0.05] px-1.5 py-0.5 text-[10px] font-medium text-rose-300">
            <span className="h-1 w-1 rounded-full bg-rose-400"></span>
            <span>Deadline</span>
          </span>
        </div>
      </div>

      {/* Calendar Grid */}
      <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl overflow-hidden">
        {/* Days of week header */}
        <div className="grid grid-cols-7 border-b border-white/[0.06] bg-black/20 py-2 text-center text-[10px] font-medium text-slate-500">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => (
            <div key={d}>{d}</div>
          ))}
        </div>

        {/* Days cells */}
        <div className="grid grid-cols-7 auto-rows-fr divide-x divide-y divide-white/[0.05]">
          {daysInGrid.map((dayItem, idx) => {
            const dayEvents = events.filter((e) => e.date === dayItem.dateStr);
            const isToday = dayItem.dateStr === todayStr;
            const isSelected = selectedDayEvents?.dateStr === dayItem.dateStr;

            return (
              <div
                key={idx}
                onClick={() => setSelectedDayEvents({ dateStr: dayItem.dateStr, events: dayEvents })}
                className={`flex min-h-[96px] cursor-pointer flex-col justify-between p-1.5 transition-colors ${
                  !dayItem.isCurrentMonth
                    ? 'bg-black/20 text-slate-600'
                    : isSelected
                    ? 'bg-emerald-400/[0.05] outline outline-1 -outline-offset-1 outline-emerald-400/40'
                    : isToday
                    ? 'bg-white/[0.04] hover:bg-white/[0.06]'
                    : 'bg-transparent hover:bg-white/[0.03]'
                }`}
              >
                {/* Day Number */}
                <div className="flex items-center justify-between mb-1">
                  <span
                    className={`inline-flex items-center justify-center text-xs font-semibold rounded-full w-5 h-5 ${
                      isToday
                        ? 'bg-emerald-400 text-[var(--color-accent-ink)] font-bold'
                        : dayItem.isCurrentMonth
                        ? 'text-slate-300'
                        : 'text-slate-600'
                    }`}
                  >
                    {dayItem.date.getDate()}
                  </span>
                  {dayEvents.length > 0 && (
                    <span className="font-mono text-[10px] text-slate-500 tnum">
                      {dayEvents.length}
                    </span>
                  )}
                </div>

                {/* Event Pills */}
                <div className="space-y-1 overflow-hidden flex-1">
                  {dayEvents.slice(0, 3).map((ev) => (
                    <div
                      key={ev.id}
                      title={`${ev.company}: ${ev.title}`}
                      className={`truncate text-[10px] px-1.5 py-0.5 rounded border flex items-center space-x-1 ${getEventBadgeClass(
                        ev.event_type
                      )}`}
                    >
                      {getEventIcon(ev.event_type)}
                      <span className="truncate font-medium">{ev.company}</span>
                    </div>
                  ))}
                  {dayEvents.length > 3 && (
                    <div className="text-center text-[9px] font-medium text-slate-500">
                      +{dayEvents.length - 3} more
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Selected Day Drawer / Flyout */}
      {selectedDayEvents && (
        <div className="space-y-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
          <div className="flex items-center justify-between">
            <h4 className="flex items-center gap-2 text-[13px] font-semibold text-[var(--color-ink)]">
              <CalendarIcon className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              <span>
                Schedule for{' '}
                {new Date(selectedDayEvents.dateStr + 'T00:00:00').toLocaleDateString(undefined, {
                  weekday: 'short',
                  month: 'short',
                  day: 'numeric',
                  year: 'numeric'
                })}
              </span>
            </h4>
            <button
              onClick={() => setSelectedDayEvents(null)}
              className="rounded px-1.5 py-0.5 text-[11px] text-slate-400 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
            >
              Close
            </button>
          </div>

          {selectedDayEvents.events.length === 0 ? (
            <p className="py-2 text-[12px] text-slate-500">
              No applications, interviews, follow-ups, or deadlines on this day.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
              {selectedDayEvents.events.map((ev) => {
                const linkedApp = applications.find((a) => a.id === ev.application_id);

                return (
                  <div
                    key={ev.id}
                    className="flex flex-col justify-between space-y-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3"
                  >
                    <div>
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className={`rounded border px-1.5 py-0.5 text-[10px] font-medium ${getEventBadgeClass(
                            ev.event_type
                          )}`}
                        >
                          {ev.event_type.replace('_', ' ')}
                        </span>
                        {ev.time && (
                          <span className="text-[11px] text-slate-400 font-mono flex items-center space-x-1">
                            <Clock className="w-3 h-3 text-slate-500" />
                            <span>{ev.time}</span>
                          </span>
                        )}
                      </div>

                      <h5 className="text-[12px] font-medium text-[var(--color-ink)]">{ev.title}</h5>
                      <div className="mt-1 flex flex-wrap items-center gap-x-2 text-[11px] text-slate-500">
                        <span className="flex items-center space-x-1">
                          <Building className="w-3.5 h-3.5 text-slate-500" />
                          <span>{ev.company}</span>
                        </span>
                        {ev.time_zone && (
                          <span className="text-[10px] text-slate-500 font-mono">
                            ({ev.time_zone})
                          </span>
                        )}
                      </div>

                      {ev.meeting_link && (
                        <div className="mt-2">
                          <a
                            href={ev.meeting_link}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex min-h-[26px] items-center gap-1 rounded-md border border-emerald-400/25 bg-emerald-400/[0.06] px-2 text-[10px] font-medium text-emerald-300 transition-colors hover:bg-emerald-400/[0.10]"
                          >
                            <Video className="w-2.5 h-2.5 text-emerald-400" />
                            <span>Join {ev.meeting_platform || 'Call'}</span>
                            <ExternalLink className="w-2.5 h-2.5 text-emerald-400" />
                          </a>
                        </div>
                      )}

                      {ev.details && (
                        <p className="mt-2 rounded border border-white/[0.06] bg-white/[0.02] p-2 text-[11px] text-slate-400">
                          {typeof ev.details === 'string' ? ev.details : JSON.stringify(ev.details)}
                        </p>
                      )}
                    </div>

                    <div className="mt-2 flex flex-wrap items-center justify-end gap-1.5 border-t border-white/[0.06] pt-2">
                      {(ev.event_type === 'interview' || Boolean(ev.meeting_link)) && onNavigateToInterviewPrep && (
                        <button
                          type="button"
                          onClick={() => onNavigateToInterviewPrep(ev.company, ev.title)}
                          className="inline-flex min-h-[26px] items-center gap-1 rounded border border-sky-400/25 bg-sky-400/[0.06] px-2 text-[10px] font-medium text-sky-300 transition-colors hover:bg-sky-400/[0.10]"
                        >
                          <Sparkles className="w-2.5 h-2.5 text-sky-300" />
                          <span>Interview Prep</span>
                        </button>
                      )}

                      {linkedApp && onOpenFollowUpModal && (
                        <button
                          onClick={() => onOpenFollowUpModal(linkedApp)}
                          className="inline-flex min-h-[26px] items-center gap-1 rounded border border-white/[0.09] bg-white/[0.03] px-2 text-[10px] font-medium text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                        >
                          <Sparkles className="w-2.5 h-2.5" />
                          <span>Follow-up</span>
                        </button>
                      )}
                      {linkedApp && onOpenScheduleModal && (
                        <button
                          onClick={() => onOpenScheduleModal(linkedApp)}
                          className="inline-flex min-h-[26px] items-center gap-1 rounded border border-sky-400/20 bg-sky-400/[0.05] px-2 text-[10px] font-medium text-sky-300 transition-colors hover:bg-sky-400/[0.09]"
                        >
                          <Video className="w-2.5 h-2.5" />
                          <span>Schedule</span>
                        </button>
                      )}
                      {linkedApp && onSelectApp && (
                        <button
                          onClick={() => onSelectApp(linkedApp)}
                          className="inline-flex min-h-[26px] items-center gap-1 rounded border border-white/[0.07] bg-white/[0.04] px-2 text-[10px] font-medium text-slate-300 transition-colors hover:bg-white/[0.07]"
                        >
                          <span>App</span>
                          <ExternalLink className="w-2.5 h-2.5 text-slate-400" />
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
