import { useEffect, useRef, useState } from 'react';
import { Check, FileText } from 'lucide-react';
import { RESUME_BULLETS, RESUME_SKILLS } from './content';
import { gsap, prefersReducedMotion, withScrollScene } from './motion';

const ALL_BULLETS = Object.fromEntries(RESUME_BULLETS.map((bullet) => [bullet.id, bullet.focus]));

export const ResumeChapter = () => {
  const scope = useRef<HTMLElement | null>(null);
  const preview = useRef<HTMLDivElement | null>(null);
  const mounted = useRef(false);
  const [name, setName] = useState('A. Khan');
  const [headline, setHeadline] = useState('Computer Science, third year');
  const [selectedBullets, setSelectedBullets] = useState<Record<string, boolean>>(ALL_BULLETS);
  const [skills, setSkills] = useState<string[]>(['TypeScript', 'PostgreSQL']);
  const [tailored, setTailored] = useState(false);

  useEffect(
    () =>
      withScrollScene(scope.current, () => {
        gsap.from('.resume__editor', {
          opacity: 0,
          x: -18,
          duration: 0.5,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 66%' },
        });
        gsap.from('.resume__preview', {
          opacity: 0,
          x: 18,
          duration: 0.5,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 66%' },
        });
      }),
    [],
  );

  // The preview pulses once when the master is swapped for the tailored variant.
  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true;
      return;
    }
    if (!preview.current || prefersReducedMotion()) return;
    gsap.fromTo(
      preview.current,
      { opacity: 0.55, y: 6 },
      { opacity: 1, y: 0, duration: 0.35, ease: 'power2.out' },
    );
  }, [tailored]);

  const activeBullets = RESUME_BULLETS.filter((bullet) => selectedBullets[bullet.id]);
  const toggleBullet = (id: string) =>
    setSelectedBullets((current) => ({ ...current, [id]: !current[id] }));
  const toggleSkill = (skill: string) =>
    setSkills((current) =>
      current.includes(skill) ? current.filter((entry) => entry !== skill) : [...current, skill],
    );

  return (
    <section id="resume" ref={scope} className="l-chapter" aria-labelledby="resume-title">
      <div className="l-container l-chapter__grid">
        <div className="l-chapter__copy">
          <h2 id="resume-title" className="l-h2">
            Make every application count.
          </h2>
          <p className="l-lead">
            One LaTeX master resume, tailored variants per role. The 6-factor ATS audit reports what
            a recruiter’s parser sees: it cannot promise outcomes, and it does not pretend to.
          </p>
          <ul className="l-check-list">
            <li>Rebuild the PDF against your profile in one action</li>
            <li>Per-application variant, diffable like any document</li>
            <li>Audit flags structure, keywords, sections, length and formatting</li>
          </ul>
        </div>

        <div className="resume" aria-label="Illustrative resume studio demonstration">
          <div className="demo__bar">
            <span className="demo__title">
              <FileText size={13} aria-hidden="true" />
              Resume Studio
            </span>
            <span className="demo__chip demo__chip--quiet">Illustrative</span>
          </div>

          <div className="resume__grid">
            <div className="resume__editor">
              <label className="resume__field">
                <span>Name</span>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  autoComplete="off"
                />
              </label>
              <label className="resume__field">
                <span>Headline</span>
                <input
                  type="text"
                  value={headline}
                  onChange={(event) => setHeadline(event.target.value)}
                  autoComplete="off"
                />
              </label>

              <fieldset className="resume__group">
                <legend>Experience</legend>
                {RESUME_BULLETS.map((bullet) => (
                  <label key={bullet.id} className="resume__bullet">
                    <input
                      type="checkbox"
                      checked={selectedBullets[bullet.id]}
                      onChange={() => toggleBullet(bullet.id)}
                    />
                    <span className="resume__box" aria-hidden="true">
                      {selectedBullets[bullet.id] ? <Check size={11} strokeWidth={2.6} /> : null}
                    </span>
                    <span>{bullet.text}</span>
                  </label>
                ))}
              </fieldset>

              <fieldset className="resume__group">
                <legend>Skills</legend>
                <div className="resume__skills">
                  {RESUME_SKILLS.map((skill) => (
                    <button
                      key={skill}
                      type="button"
                      className={`resume__skill${skills.includes(skill) ? ' is-active' : ''}`}
                      aria-pressed={skills.includes(skill)}
                      onClick={() => toggleSkill(skill)}
                    >
                      {skill}
                    </button>
                  ))}
                </div>
              </fieldset>

              <button type="button" className="demo__save resume__tailor" onClick={() => setTailored((value) => !value)}>
                {tailored ? 'Reset to master' : 'Tailor to Linear · Backend Intern'}
              </button>
            </div>

            <div className="resume__preview" ref={preview} aria-hidden="true">
              <div className="resume__sheet">
                <p className="resume__name">{name || 'Your name'}</p>
                <p className="resume__headline">{headline}</p>
                {tailored ? (
                  <p className="resume__target">Targeting the Backend Intern role at Linear, matched on TypeScript and PostgreSQL</p>
                ) : (
                  <p className="resume__target resume__target--quiet">Master resume · one page</p>
                )}
                <div className="resume__section">
                  <p className="resume__section-title">Experience</p>
                  <ul
                    className="resume__bullet-list"
                    key={activeBullets.map((bullet) => bullet.id).join('-') || 'empty'}
                  >
                    {activeBullets.map((bullet) => (
                      <li key={bullet.id}>{bullet.text}</li>
                    ))}
                    {activeBullets.length === 0 ? <li className="resume__none">Select at least one line.</li> : null}
                  </ul>
                </div>
                <div className="resume__section">
                  <p className="resume__section-title">Skills</p>
                  <p className="resume__skill-line">
                    {skills.length > 0 ? skills.join(', ') : 'Select skills from the editor'}
                  </p>
                </div>
              </div>
              <p className="demo__footnote resume__footnote">Illustrative preview. Your data stays on your instance.</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
