import { useState } from 'react';
import { Check, MessagesSquare } from 'lucide-react';
import { PREP_CHECKLIST } from './content';

export const InterviewChapter = () => {
  const [done, setDone] = useState<ReadonlySet<string>>(() => new Set());
  const total = PREP_CHECKLIST.length;
  const finished = done.size;

  const toggle = (id: string) =>
    setDone((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  return (
    <section id="interviews" className="l-chapter" aria-labelledby="interviews-title">
      <div className="l-container l-chapter__grid">
        <div className="l-chapter__copy">
          <h2 id="interviews-title" className="l-h2">
            Be ready when the opportunity calls.
          </h2>
          <p className="l-lead">
            Prep lives beside the role that needs it. The checklist counts your practice before it
            counts on the call, and local AI evaluation stays on your machine.
          </p>
          <ul className="l-check-list">
            <li>Practice questions tied to the actual role</li>
            <li>Answers evaluated against your own Ollama instance, if configured</li>
            <li>No simulation is invented here; a journal logs what you cover</li>
          </ul>
        </div>

        <div className="interview" aria-label="Illustrative interview preparation demonstration">
          <div className="demo__bar">
            <span className="demo__title">
              <MessagesSquare size={13} aria-hidden="true" />
              Prep journal
            </span>
            <span className="demo__chip demo__chip--quiet">Illustrative</span>
          </div>

          <div className="interview__context">
            <p className="interview__context-label">Linear · Backend Engineering Intern</p>
            <p className="interview__context-meta">Interview, Thu 14:00, system design round</p>
            <p className="interview__context-note">Answers evaluated locally with Ollama when configured</p>
          </div>

          <div className="interview__progress" aria-label={`${finished} of ${total} preparation tasks complete`}>
            <span className="interview__progress-label">Preparation checklist</span>
            <span className="interview__progress-track">
              <span
                className="interview__progress-bar"
                style={{ transform: `scaleX(${finished / total})` }}
              />
            </span>
            <span className="interview__progress-meta">
              {finished} of {total} ready
            </span>
          </div>

          <ul className="interview__list">
            {PREP_CHECKLIST.map((item) => {
              const checked = done.has(item.id);
              return (
                <li key={item.id}>
                  <button
                    type="button"
                    className={`interview__item${checked ? ' is-done' : ''}`}
                    aria-pressed={checked}
                    onClick={() => toggle(item.id)}
                  >
                    <span className="interview__check" aria-hidden="true">
                      {checked ? <Check size={11} strokeWidth={2.7} /> : null}
                    </span>
                    <span className="interview__item-copy">
                      <span>{item.label}</span>
                      <span className="interview__minutes">{item.minutes} min</span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          <ol className="interview__timeline" aria-label="Preparation timeline">
            <li><span>Jun 9</span>Take-home submitted, 3 self-review questions logged</li>
            <li><span>Jun 12</span>Assessment passed, system design scheduled</li>
            <li><span>Thu 14:00</span>Interview, system design; focus on the ingest pipeline</li>
          </ol>
        </div>
      </div>
    </section>
  );
};
