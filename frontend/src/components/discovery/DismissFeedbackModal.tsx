import React, { useState, useEffect } from 'react';
import { X, AlertCircle, ThumbsDown, Check, Building2, MapPin, DollarSign, Wrench } from 'lucide-react';
import { OpportunityItem } from '../../types';

interface DismissFeedbackModalProps {
  item: OpportunityItem | null;
  isOpen: boolean;
  onClose: () => void;
  onSubmitFeedback: (id: number, feedbackType: string, note?: string) => void;
}

const REASONS = [
  { id: 'not_relevant', label: 'Not relevant to my interests or role goals', icon: AlertCircle },
  { id: 'wrong_location', label: 'Wrong location / Not remote-friendly', icon: MapPin },
  { id: 'skill_mismatch', label: 'Skill requirements are mismatched / too advanced', icon: Wrench },
  { id: 'low_stipend', label: 'Stipend / compensation is too low or unpaid', icon: DollarSign },
  { id: 'not_interested_company', label: 'Not interested in this specific employer', icon: Building2 },
  { id: 'already_applied', label: 'Already applied outside CareerOS', icon: Check }
];

export const DismissFeedbackModal: React.FC<DismissFeedbackModalProps> = ({
  item,
  isOpen,
  onClose,
  onSubmitFeedback
}) => {
  const [selectedReason, setSelectedReason] = useState<string>('not_relevant');
  const [note, setNote] = useState<string>('');

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (isOpen) {
      window.addEventListener('keydown', handleKeyDown);
    }
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !item) return null;

  const handleSubmit = () => {
    onSubmitFeedback(item.id, selectedReason, note.trim() || undefined);
    onClose();
  };

  const handleQuickDismiss = () => {
    onSubmitFeedback(item.id, 'dismiss');
    onClose();
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div 
        className="relative w-full max-w-lg bg-dark-900 border border-dark-700 rounded-xl p-6 text-slate-200"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-dark-750 pb-4 mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-rose-500/15 border border-rose-500/30 text-rose-400 flex items-center justify-center">
              <ThumbsDown className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[var(--color-ink)]">Dismiss Opportunity</h3>
              <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">
                {item.title} • {item.company_name}
              </p>
            </div>
          </div>
          <button 
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 rounded-lg text-slate-400 hover:text-[var(--color-ink)] hover:bg-dark-800 transition min-h-[28px] min-w-[28px] flex items-center justify-center focus-visible:ring-1 focus-visible:ring-emerald-500"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        <p className="text-xs text-slate-300 mb-3">
          Why are you dismissing this? Your feedback will adapt future AI matching and filter out similar unwanted roles.
        </p>

        <div className="space-y-2 mb-4">
          {REASONS.map(r => {
            const Icon = r.icon;
            const active = selectedReason === r.id;
            return (
              <button
                key={r.id}
                type="button"
                onClick={() => setSelectedReason(r.id)}
                className={`w-full p-2.5 rounded-xl text-left text-xs font-medium border flex items-center space-x-2.5 transition ${
                  active
                    ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
                    : 'bg-dark-800/80 border-dark-700/80 text-slate-300 hover:bg-dark-800 hover:border-dark-600'
                }`}
              >
                <Icon className={`w-4 h-4 flex-shrink-0 ${active ? 'text-emerald-400' : 'text-slate-400'}`} />
                <span className="flex-1">{r.label}</span>
                {active && <Check className="w-4 h-4 text-emerald-400" />}
              </button>
            );
          })}
        </div>

        <div className="mb-5">
          <label className="block text-xs text-slate-400 mb-1.5 font-medium">
            Additional notes (optional)
          </label>
          <input
            type="text"
            placeholder="e.g. Prefer backend roles with Go or Python, or looking for 6+ month internships"
            value={note}
            onChange={e => setNote(e.target.value)}
            className="w-full px-3 py-2 rounded-xl bg-dark-950 border border-dark-700 text-xs text-[var(--color-ink)] placeholder:text-slate-600 focus:outline-none focus:border-emerald-500"
          />
        </div>

        <div className="flex items-center justify-between pt-3 border-t border-dark-750">
          <button
            onClick={handleQuickDismiss}
            className="text-xs text-slate-400 hover:text-slate-200 transition underline underline-offset-4"
          >
            Dismiss without feedback
          </button>

          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 rounded-xl bg-dark-800 hover:bg-dark-750 text-slate-300 text-xs font-semibold transition border border-dark-700"
            >
              Cancel
            </button>
            <button
              onClick={handleSubmit}
              className="px-4 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-[var(--color-ink)] text-xs font-semibold transition"
            >
              Dismiss & Save Feedback
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
