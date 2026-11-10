import React, { useEffect, useState, useRef } from 'react';

export interface CountUpProps {
  to: number;
  from?: number;
  duration?: number;
  decimals?: number;
  separator?: string;
  prefix?: string;
  suffix?: string;
  className?: string;
}

export const CountUp: React.FC<CountUpProps> = ({
  to,
  from = 0,
  duration = 1.2,
  decimals = 0,
  separator = '',
  prefix = '',
  suffix = '',
  className = ''
}) => {
  const [value, setValue] = useState<number>(from);
  const rafRef = useRef<number | null>(null);

  useEffect(() => {
    // If user prefers reduced motion, jump straight to target
    if (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      setValue(to);
      return;
    }

    const startTime = performance.now();
    const durationMs = duration * 1000;
    const startVal = from;
    const change = to - from;

    const tick = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / durationMs, 1);
      // Smooth ease-out cubic curve
      const eased = 1 - Math.pow(1 - progress, 3);
      const currentVal = startVal + change * eased;

      setValue(currentVal);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        setValue(to);
      }
    };

    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [to, from, duration]);

  const formatNumber = (num: number) => {
    const fixed = num.toFixed(decimals);
    if (!separator) return fixed;
    const parts = fixed.split('.');
    parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, separator);
    return parts.join('.');
  };

  return (
    <span className={className}>
      {prefix}
      {formatNumber(value)}
      {suffix}
    </span>
  );
};

export default CountUp;
