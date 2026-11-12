import { useRef, useState } from 'react';

/**
 * CareerOS reading of Aceternity UI's TextHoverEffect (ui.aceternity.com):
 * an outlined display word that fills with a teal gradient under the pointer.
 * Native SVG, no motion dependency — the mask follows the cursor directly.
 * Reduced motion renders the static outline only. Decorative, aria-hidden.
 */

const GRADIENT_STOPS = [
  { offset: '0%', color: '#9fe9cd' },
  { offset: '45%', color: '#65e6c2' },
  { offset: '100%', color: '#2ac29a' },
] as const;

export const TextHoverEffect = ({ text = 'CareerOS' }: { text?: string }) => {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const [mask, setMask] = useState<{ cx: string; cy: string }>({ cx: '50%', cy: '50%' });
  const [hovered, setHovered] = useState(false);
  const interactive =
    typeof window !== 'undefined' &&
    typeof window.matchMedia === 'function' &&
    window.matchMedia('(prefers-reduced-motion: no-preference)').matches;

  const onMove = (event: React.MouseEvent<SVGSVGElement>) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    setMask({
      cx: `${(((event.clientX - rect.left) / rect.width) * 100).toFixed(2)}%`,
      cy: `${(((event.clientY - rect.top) / rect.height) * 100).toFixed(2)}%`,
    });
  };

  return (
    <svg
      ref={svgRef}
      viewBox="0 0 1200 250"
      className="l-wordmark__svg"
      role="presentation"
      aria-hidden="true"
      onMouseMove={interactive ? onMove : undefined}
      onMouseEnter={interactive ? () => setHovered(true) : undefined}
      onMouseLeave={interactive ? () => setHovered(false) : undefined}
    >
      <defs>
        <linearGradient
          id="l-wordmark-gradient"
          gradientUnits="userSpaceOnUse"
          x1="0"
          y1="0"
          x2="1200"
          y2="0"
        >
          {GRADIENT_STOPS.map((stop) => (
            <stop key={stop.offset} offset={stop.offset} stopColor={stop.color} />
          ))}
        </linearGradient>
        <radialGradient
          id="l-wordmark-reveal"
          gradientUnits="userSpaceOnUse"
          cx={mask.cx}
          cy={mask.cy}
          r="220"
        >
          <stop offset="0%" stopColor="white" />
          <stop offset="100%" stopColor="black" />
        </radialGradient>
        <mask id="l-wordmark-mask">
          <rect x="0" y="0" width="100%" height="100%" fill="url(#l-wordmark-reveal)" />
        </mask>
      </defs>
      <text
        x="600"
        y="136"
        textAnchor="middle"
        dominantBaseline="middle"
        className="l-wordmark__outline"
      >
        {text}
      </text>
      {interactive ? (
        <text
          x="600"
          y="136"
          textAnchor="middle"
          dominantBaseline="middle"
          mask="url(#l-wordmark-mask)"
          className="l-wordmark__fill"
          opacity={hovered ? 1 : 0}
        >
          {text}
        </text>
      ) : null}
    </svg>
  );
};
