import {
  Compass,
  FileText,
  MessagesSquare,
  SquareKanban,
  Sparkles,
  TrendingUp,
} from 'lucide-react';
import { ProductFrame } from './ProductFrame';
import { withScrollScene, gsap } from './motion';
import WebThreads from './fx/WebThreads';
import { trackSpotlight } from './fx/Spotlight';
import { useEffect, useRef } from 'react';

const MODULES_LEFT = [
  { href: '#discover', icon: Compass, label: 'Discover opportunities', body: 'Ranked against your profile' },
  { href: '#track', icon: SquareKanban, label: 'Track applications', body: 'One record, every stage' },
  { href: '#resume', icon: FileText, label: 'Resume Studio', body: 'LaTeX master, tailored variants' },
];
const MODULES_RIGHT = [
  { href: '#interviews', icon: MessagesSquare, label: 'Interview workflows', body: 'Prep attached to the role' },
  { href: '#insights', icon: TrendingUp, label: 'Career insights', body: 'Funnel, sources, activity' },
  { href: '#interviews', icon: Sparkles, label: 'Optional AI assistance', body: 'Groq or local Ollama, never required' },
];

export const ConnectedChapter = () => {
  const scope = useRef<HTMLElement | null>(null);

  useEffect(
    () =>
      withScrollScene(scope.current, () => {
        gsap.from('.ch02__head > *', {
          opacity: 0,
          y: 18,
          duration: 0.5,
          stagger: 0.08,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 68%' },
        });
        gsap.from('.ch02__frame', {
          opacity: 0,
          y: 24,
          scale: 0.97,
          duration: 0.6,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 62%' },
        });
        gsap.from('.ch02__module', {
          opacity: 0,
          y: 14,
          duration: 0.4,
          stagger: 0.12,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 62%' },
        });
        gsap.from('.ch02__link', {
          scaleX: 0,
          transformOrigin: 'center',
          duration: 0.34,
          stagger: 0.12,
          ease: 'power2.out',
          scrollTrigger: { trigger: scope.current, start: 'top 62%' },
        });
      }),
    [],
  );

  const renderModule = (module: { href: string; icon: typeof Compass; label: string; body: string }) => {
    const Icon = module.icon;
    return (
      <a key={module.label} href={module.href} className="ch02__module">
        <span className="ch02__link" aria-hidden="true" />
        <span className="ch02__module-icon">
          <Icon size={15} strokeWidth={1.7} aria-hidden="true" />
        </span>
        <span className="ch02__module-copy">
          <span className="ch02__module-label">{module.label}</span>
          <span className="ch02__module-body">{module.body}</span>
        </span>
      </a>
    );
  };

  return (
    <section id="workspace" ref={scope} className="l-chapter ch02" aria-labelledby="workspace-title">
      <div className="ch02__threads" aria-hidden="true">
        <WebThreads
          colors={['#7c3aed', '#b7a1ff']}
          coreColor="#efeaff"
          threadCount={7}
          speed={0.16}
          glow={0.03}
          brightness={0.55}
          opacity={0.6}
          pulses={1}
          fade={0.25}
        />
      </div>

      <div className="l-container ch02__head">
        <h2 id="workspace-title" className="l-h2">
          Everything starts making sense when it works together.
        </h2>
        <p className="l-lead">
          CareerOS is not a pile of features. The same role you discover is the role you track,
          tailor a resume for, prepare for and measure: one record from first search to signed offer.
        </p>
      </div>

      <div className="l-container ch02__grid">
        <div className="ch02__col ch02__col--left">{MODULES_LEFT.map(renderModule)}</div>
        <div className="ch02__center">
          <div className="ch02__frame" onPointerMove={trackSpotlight}>
            <ProductFrame />
          </div>
          <p className="ch02__caption">The workspace: one record per role, ranked and current.</p>
        </div>
        <div className="ch02__col ch02__col--right">{MODULES_RIGHT.map(renderModule)}</div>
      </div>
      <p className="l-container ch02__sample">Product frame: illustrative sample, not real account data.</p>
    </section>
  );
};
