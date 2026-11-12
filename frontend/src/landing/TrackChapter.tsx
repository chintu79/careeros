import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, NotebookPen } from 'lucide-react';
import { INITIAL_PIPELINE, PIPELINE_STAGES, type PipelineCard, type PipelineStage } from './content';
import { Flip, gsap, prefersReducedMotion, withScrollScene } from './motion';

const stageIndex = (stage: PipelineStage) => PIPELINE_STAGES.indexOf(stage);

export const TrackChapter = () => {
  const scope = useRef<HTMLElement | null>(null);
  const board = useRef<HTMLDivElement | null>(null);
  const pendingFlip = useRef<ReturnType<typeof Flip.getState> | null>(null);
  const [cards, setCards] = useState<PipelineCard[]>(INITIAL_PIPELINE);
  const [selectedId, setSelectedId] = useState('linear');

  const selected = cards.find((card) => card.id === selectedId) ?? cards[0];
  const progress = selected ? (stageIndex(selected.stage) / (PIPELINE_STAGES.length - 1)) * 100 : 0;

  useEffect(
    () =>
      withScrollScene(scope.current, () => {
        gsap.from('.board', {
          opacity: 0,
          y: 24,
          duration: 0.55,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 66%' },
        });
        gsap.from('.board__column', {
          opacity: 0,
          y: 14,
          duration: 0.4,
          stagger: 0.07,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 66%' },
        });
      }),
    [],
  );

  // Flip the moved card between columns; reduced motion and jsdom (no
  // matchMedia) keep the plain re-render.
  useEffect(() => {
    const state = pendingFlip.current;
    if (!state) return;
    pendingFlip.current = null;
    Flip.from(state, { duration: 0.45, ease: 'power2.out' });
  }, [cards]);

  const move = (id: string, direction: 1 | -1) => {
    if (
      board.current &&
      typeof window.matchMedia === 'function' &&
      !prefersReducedMotion()
    ) {
      pendingFlip.current = Flip.getState(board.current.querySelectorAll('.board__card'));
    }
    setCards((current) =>
      current.map((card) => {
        if (card.id !== id) return card;
        const next = Math.min(
          PIPELINE_STAGES.length - 1,
          Math.max(0, stageIndex(card.stage) + direction),
        );
        return { ...card, stage: PIPELINE_STAGES[next] };
      }),
    );
  };

  return (
    <section id="track" ref={scope} className="l-chapter" aria-labelledby="track-title">
      <div className="l-container l-chapter__grid">
        <div className="l-chapter__copy">
          <h2 id="track-title" className="l-h2">
            Never lose track of where you stand.
          </h2>
          <p className="l-lead">
            Every role keeps one record through Saved → Applied → Assessment → Interview → Offer.
            Update the stage, and every view (board, table, timeline, calendar) stays current.
          </p>
          <ul className="l-check-list">
            <li>Move any card with one click; nothing re-enters anywhere else</li>
            <li>Follow-up drafts and interview scheduling attached to the record</li>
            <li>A prep journal lives beside the role, not in another app</li>
          </ul>
        </div>

        <div className="board" ref={board} aria-label="Illustrative application board demonstration">
          <div className="board__bar">
            <span className="board__title">Pipeline</span>
            <span className="demo__chip demo__chip--quiet">Illustrative</span>
          </div>

          {selected ? (
            <div className="board__progress" aria-label={`Selected application: ${selected.company}, ${selected.stage}, progress ${Math.round(progress)} percent`}>
              <span className="board__progress-label">
                {selected.company} · {selected.stage}
              </span>
              <span className="board__progress-track">
                <span
                  className="board__progress-bar"
                  style={{ transform: `scaleX(${progress / 100})` }}
                />
              </span>
              <span className="board__progress-meta">Stage {stageIndex(selected.stage) + 1} of {PIPELINE_STAGES.length}</span>
            </div>
          ) : null}

          <div className="board__columns">
            {PIPELINE_STAGES.map((stage) => {
              const stageCards = cards.filter((card) => card.stage === stage);
              return (
                <div className="board__column" key={stage}>
                  <p className="board__column-label">
                    {stage}
                    <span className="board__count">{stageCards.length}</span>
                  </p>
                  {stageCards.map((card) => (
                    <div
                      key={card.id}
                      className={`board__card${selected?.id === card.id ? ' is-selected' : ''}`}
                    >
                      <button
                        type="button"
                        className="board__card-button"
                        aria-pressed={selected?.id === card.id}
                        onClick={() => setSelectedId(card.id)}
                      >
                        <span className="board__card-company">{card.company}</span>
                        <span className="board__card-role">{card.role}</span>
                        <span className="board__card-note">{card.note}</span>
                      </button>
                      <span className="board__card-foot">
                        <span className="board__card-updated">{card.updated}</span>
                        <span className="board__move">
                          <button
                            type="button"
                            className="board__move-button"
                            disabled={stage === 'Saved'}
                            aria-label={`Move ${card.company} back a stage`}
                            onClick={() => move(card.id, -1)}
                          >
                            <ChevronLeft size={14} aria-hidden="true" />
                          </button>
                          <button
                            type="button"
                            className="board__move-button"
                            disabled={stage === 'Offer'}
                            aria-label={`Move ${card.company} forward a stage`}
                            onClick={() => move(card.id, 1)}
                          >
                            <ChevronRight size={14} aria-hidden="true" />
                          </button>
                        </span>
                      </span>
                    </div>
                  ))}
                  {stageCards.length === 0 ? <p className="board__empty">Empty</p> : null}
                </div>
              );
            })}
          </div>

          {selected ? (
            <div className="board__detail" aria-live="polite">
              <NotebookPen size={13} aria-hidden="true" />
              <span>
                <strong>{selected.company}:</strong> {selected.note}. Record updates in every view the
                moment you move it.
              </span>
              <a className="l-text-link" href="/">
                Open record
              </a>
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
};
