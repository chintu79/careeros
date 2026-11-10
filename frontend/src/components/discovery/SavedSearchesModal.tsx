import React, { useState } from 'react';
import { X, Bookmark, Check } from 'lucide-react';

interface SavedSearchesModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (name: string) => void;
  query: string;
  searchMode: string;
  filters: Record<string, any>;
}

export const SavedSearchesModal: React.FC<SavedSearchesModalProps> = ({
  isOpen,
  onClose,
  onSave,
  query,
  searchMode,
  filters
}) => {
  const [name, setName] = useState('');

  if (!isOpen) return null;

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    onSave(name.trim());
    setName('');
    onClose();
  };

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div 
        className="relative w-full max-w-md bg-dark-900 border border-dark-700 rounded-xl p-6 text-slate-200"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-start justify-between border-b border-dark-750 pb-4 mb-4">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 text-amber-400 flex items-center justify-center">
              <Bookmark className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-[var(--color-ink)]">Save Current Search</h3>
              <p className="text-xs text-slate-400 mt-0.5">Quickly re-run this exact search anytime</p>
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

        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="block text-xs text-slate-300 mb-1.5 font-medium">Search Name</label>
            <input
              type="text"
              autoFocus
              required
              placeholder="e.g. Remote AI/ML Internships > 20k"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full px-3.5 py-2.5 rounded-xl bg-dark-950 border border-dark-700 text-xs text-[var(--color-ink)] placeholder:text-slate-600 focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div className="p-3 rounded-xl bg-dark-800/60 border border-dark-750 space-y-1.5 text-xs text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-400">Query:</span>
              <span className="font-semibold text-[var(--color-ink)]">{query || '(All opportunities)'}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Search Mode:</span>
              <span className="font-semibold text-emerald-400 capitalize">{searchMode}</span>
            </div>
            {filters.location && (
              <div className="flex justify-between">
                <span className="text-slate-400">Location:</span>
                <span className="text-[var(--color-ink)]">{filters.location}</span>
              </div>
            )}
            {filters.workplace_type && (
              <div className="flex justify-between">
                <span className="text-slate-400">Workplace:</span>
                <span className="text-[var(--color-ink)] capitalize">{filters.workplace_type}</span>
              </div>
            )}
            {filters.min_stipend && (
              <div className="flex justify-between">
                <span className="text-slate-400">Min Stipend:</span>
                <span className="text-[var(--color-ink)]">₹{filters.min_stipend}</span>
              </div>
            )}
          </div>

          <div className="flex items-center justify-end space-x-2 pt-2 border-t border-dark-750">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-750 text-slate-300 text-xs font-semibold transition border border-dark-700"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!name.trim()}
              className="px-4 py-2 rounded-xl bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 text-[var(--color-accent-ink)] text-xs font-semibold transition flex items-center space-x-1.5"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Save Search</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
