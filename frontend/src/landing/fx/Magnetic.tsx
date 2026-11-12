import { useRef, type ReactNode } from 'react';
import { gsap, prefersReducedMotion } from '../motion';

// React Bits-style magnetic pull, scaled down so it reads as polish, not a toy.
export const Magnetic = ({
  children,
  strength = 10,
}: {
  children: ReactNode;
  strength?: number;
}) => {
  const ref = useRef<HTMLSpanElement>(null);

  const onMove = (event: React.PointerEvent<HTMLSpanElement>) => {
    const node = ref.current;
    if (!node || prefersReducedMotion()) return;
    const rect = node.getBoundingClientRect();
    gsap.to(node, {
      x: ((event.clientX - rect.left - rect.width / 2) / rect.width) * strength,
      y: ((event.clientY - rect.top - rect.height / 2) / rect.height) * strength,
      duration: 0.4,
      ease: 'power2.out',
    });
  };

  const onLeave = () => {
    if (!ref.current || prefersReducedMotion()) return;
    gsap.to(ref.current, { x: 0, y: 0, duration: 0.6, ease: 'elastic.out(1, 0.45)' });
  };

  return (
    <span ref={ref} className="l-magnetic" onPointerMove={onMove} onPointerLeave={onLeave}>
      {children}
    </span>
  );
};
