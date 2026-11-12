import { useEffect, useState } from 'react';
import { CHAPTERS } from './content';

/**
 * Discreet chapter rail: eight links, one per narrative section. The current
 * chapter follows an IntersectionObserver; the rail hides labels under
 * 1100px and disappears entirely on small screens.
 */
export const ChapterProgress = () => {
  const [active, setActive] = useState<string>(CHAPTERS[0].id);

  useEffect(() => {
    if (typeof IntersectionObserver !== 'function') return;
    const nodes = CHAPTERS.map((chapter) => document.getElementById(chapter.id)).filter(
      (node): node is HTMLElement => node !== null,
    );
    if (nodes.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActive(entry.target.id);
          }
        }
      },
      { rootMargin: '-35% 0px -55% 0px', threshold: 0 },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  return (
    <nav className="l-chapters" aria-label="Story chapters">
      <ol>
        {CHAPTERS.map((chapter) => (
          <li key={chapter.id}>
            <a
              href={`#${chapter.id}`}
              className={`l-chapters__dot${active === chapter.id ? ' is-active' : ''}`}
              aria-current={active === chapter.id ? 'true' : undefined}
              title={`${chapter.index} · ${chapter.label}`}
            >
              <span className="l-chapters__num" aria-hidden="true">
                {chapter.index}
              </span>
              <span className="l-chapters__label">{chapter.label}</span>
            </a>
          </li>
        ))}
      </ol>
    </nav>
  );
};
