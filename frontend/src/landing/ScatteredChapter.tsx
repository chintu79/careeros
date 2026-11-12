import { useEffect, useRef } from 'react';
import {
  Calendar,
  FileSpreadsheet,
  FileText,
  Inbox,
  Link2,
  ListChecks,
  StickyNote,
} from 'lucide-react';
import { withScrollScene, gsap } from './motion';

const FRAGMENTS = [
  { icon: Link2, label: 'Greenhouse', sub: 'Backend Eng · 92', className: 'ch-f1' },
  { icon: Link2, label: 'Lever', sub: 'Platform · 87', className: 'ch-f2' },
  { icon: FileText, label: 'resume_final_v9.tex', sub: 'third copy in Documents/', className: 'ch-f3' },
  { icon: FileSpreadsheet, label: 'applications.xlsx', sub: '43 rows, three views', className: 'ch-f4' },
  { icon: StickyNote, label: 'notes.md', sub: 'system design, then behavioural', className: 'ch-f5' },
  { icon: Calendar, label: 'Calendar', sub: 'Thu 14:00 · system design', className: 'ch-f6' },
  { icon: ListChecks, label: 'Reminders', sub: '3 follow-ups, all overdue', className: 'ch-f7' },
  { icon: Inbox, label: 'Inbox', sub: '3 recruiter threads unread', className: 'ch-f8' },
] as const;

export const ScatteredChapter = () => {
  const scope = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && !window.matchMedia('(min-width: 1025px)').matches) {
      return;
    }
    return withScrollScene(scope.current, () => {
      const items = gsap.utils.toArray<HTMLElement>('.ch-frag-item', scope.current);

      // The copy stays centred; scrolling peels the surrounding fragments away
      // one at a time until only the statement remains.
      gsap.to(items, {
        opacity: 0,
        y: -16,
        scale: 0.94,
        duration: 0.3,
        stagger: 0.07,
        ease: 'power1.in',
        scrollTrigger: {
          trigger: scope.current,
          start: 'top 62%',
          end: 'bottom 52%',
          scrub: 0.8,
        },
      });
    });
  }, []);

  return (
    <section
      id="problem"
      ref={scope}
      className="l-chapter ch01"
      aria-labelledby="problem-title"
    >
      <div className="l-container ch01__stage">
        <div className="ch01__copy">
          <h2 id="problem-title" className="l-h2">
            Your career shouldn’t live in 17 tabs.
          </h2>
          <p className="l-lead">
            Listings scatter across ATS boards. Resumes fork across folders. Applications
            drift through spreadsheets and inboxes. Nothing knows how the same role moved from
            post to offer, so every decision costs you an hour of archaeology.
          </p>
          <p className="l-chapter__note">
            This scene uses illustrative examples. No user data is involved.
          </p>
        </div>

        <div
          className="ch01__orbit"
          aria-hidden="true"
        >
          {FRAGMENTS.map((fragment) => {
            const Icon = fragment.icon;
            return (
              <span key={fragment.label} className={`ch-frag-item ${fragment.className}`}>
                <Icon size={13} strokeWidth={1.8} />
                <span className="ch-frag-item__copy">
                  <span className="ch-frag-item__label">{fragment.label}</span>
                  <span className="ch-frag-item__sub">{fragment.sub}</span>
                </span>
              </span>
            );
          })}
        </div>
      </div>
    </section>
  );
};
