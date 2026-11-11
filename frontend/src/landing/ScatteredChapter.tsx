import { useEffect, useRef } from 'react';
import {
  Calendar,
  Command,
  FileSpreadsheet,
  FileText,
  Link2,
  ListChecks,
  StickyNote,
} from 'lucide-react';
import { withScrollScene, gsap } from './motion';

const FRAGMENTS = [
  { icon: Link2, label: 'Greenhouse', sub: 'Backend Eng · 92', className: 'ch-f1', dx: 190, dy: 120 },
  { icon: Link2, label: 'Lever', sub: 'Platform · 87', className: 'ch-f2', dx: -210, dy: 140 },
  { icon: FileText, label: 'resume_final_v9.tex', sub: 'third copy in Documents/', className: 'ch-f3', dx: 195, dy: 60 },
  { icon: FileSpreadsheet, label: 'applications.xlsx', sub: '43 rows, three views', className: 'ch-f4', dx: -185, dy: 45 },
  { icon: StickyNote, label: 'notes.md', sub: 'system design, then behavioural', className: 'ch-f5', dx: 150, dy: -110 },
  { icon: Calendar, label: 'Calendar', sub: 'Thu 14:00 · system design', className: 'ch-f6', dx: -155, dy: -100 },
  { icon: ListChecks, label: 'Reminders', sub: '3 follow-ups, all overdue', className: 'ch-f7', dx: 0, dy: -165 },
] as const;

export const ScatteredChapter = () => {
  const scope = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && !window.matchMedia('(min-width: 1024px)').matches) {
      return () => {};
    }
    return withScrollScene(scope.current, () => {
        const items = gsap.utils.toArray<HTMLElement>('.ch-frag', scope.current);
        gsap.set(items, { x: 0, y: 0, clearProps: 'transform,opacity' });

        const tl = gsap.timeline({
          scrollTrigger: {
            trigger: scope.current,
            start: 'top 62%',
            end: 'bottom 42%',
            scrub: 1,
          },
        });

        tl.from('.ch-frag-copy', { y: 28, opacity: 0, duration: 0.35, ease: 'power2.out' }, 0);

        items.forEach((node, index) => {
          const target = FRAGMENTS[index];
          tl.from(
            node,
            { x: target.dx * 0.55, y: target.dy * 0.55, opacity: 0, scale: 0.92, duration: 0.32, ease: 'power2.out' },
            0.03 + index * 0.035,
          );
        });

        items.forEach((node, index) => {
          const target = FRAGMENTS[index];
          tl.to(
            node,
            { x: target.dx, y: target.dy, opacity: 0, scale: 0.25, duration: 0.4, ease: 'power1.in' },
            0.52 + index * 0.05,
          );
        });

        tl.fromTo(
          '.ch-hub',
          { opacity: 0, scale: 0.72 },
          { opacity: 1, scale: 1, duration: 0.45, ease: 'power2.out' },
          0.74,
        );
        tl.fromTo(
          '.ch-hub-caption',
          { opacity: 0, y: 12 },
          { opacity: 1, y: 0, duration: 0.3 },
          0.88,
        );
    });
  }, []);

  return (
    <section
      id="problem"
      ref={scope}
      className="l-chapter ch01"
      aria-labelledby="problem-title"
    >
      <div className="l-container l-chapter__grid">
        <div className="ch-frag-copy">
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

        <div className="ch-frag" role="img" aria-label="Illustrative example: job listings, a resume file, a tracking spreadsheet, interview notes and calendar events scattered across tools, converging into one workspace.">
          {FRAGMENTS.map((fragment) => {
            const Icon = fragment.icon;
            return (
              <span key={fragment.label} className={`ch-frag-item ${fragment.className}`}>
                <Icon size={13} strokeWidth={1.8} aria-hidden="true" />
                <span className="ch-frag-item__copy">
                  <span className="ch-frag-item__label">{fragment.label}</span>
                  <span className="ch-frag-item__sub">{fragment.sub}</span>
                </span>
              </span>
            );
          })}
          <div className="ch-hub">
            <span className="ch-hub__mark">
              <Command size={17} strokeWidth={2.1} aria-hidden="true" />
            </span>
            <span className="ch-hub__label">One workspace, one record</span>
          </div>
          <p className="ch-hub-caption">The same role, tracked from posting to offer.</p>
        </div>
      </div>
    </section>
  );
};
