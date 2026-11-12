import { Command } from 'lucide-react';

export const Brand = ({ compact = false }: { compact?: boolean }) => (
  <span className={`l-brand${compact ? ' l-brand--compact' : ''}`}>
    <span className="l-brand__mark" aria-hidden="true">
      <Command size={15} strokeWidth={2.2} />
    </span>
    <span className="l-brand__word">CareerOS</span>
  </span>
);
