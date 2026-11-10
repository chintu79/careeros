import React from 'react';
import { Check, Sparkles } from 'lucide-react';
import { ResumeTemplateItem } from '../../types';
import { Modal } from '../ui/Modal';

interface TemplateSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  templates: ResumeTemplateItem[];
  selectedTemplateId: string;
  onSelectTemplate: (templateId: string) => void;
}

export const TemplateSelectorModal: React.FC<TemplateSelectorModalProps> = ({
  isOpen,
  onClose,
  templates,
  selectedTemplateId,
  onSelectTemplate
}) => {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="4xl"
      title="ATS-Optimized LaTeX Templates"
      description="Choose from 6 verified single-column templates designed for 99%+ ATS parser pass rate"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3 w-full">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <Sparkles className="w-4 h-4 text-emerald-400" aria-hidden="true" />
            <span className="text-[11px]">Switching template re-renders structure without modifying your verified candidate profile facts.</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-semibold bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] rounded-lg transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
          >
            Apply Template
          </button>
        </div>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5" role="list" aria-label="Available resume templates">
        {templates.map((tpl) => {
          const isSelected = tpl.id === selectedTemplateId;
          return (
            <div
              key={tpl.id}
              role="button"
              tabIndex={0}
              aria-pressed={isSelected}
              aria-label={`Select template: ${tpl.name}. ${tpl.description}`}
              onClick={() => onSelectTemplate(tpl.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  onSelectTemplate(tpl.id);
                }
              }}
              className={`relative flex flex-col justify-between p-4 rounded-xl border cursor-pointer transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 ${
                isSelected
                  ? 'bg-emerald-400/[0.06] border-emerald-400/40 ring-1 ring-emerald-400/30'
                  : 'bg-[var(--color-paper-3)]/60 border-white/[0.08] hover:border-white/[0.16] hover:bg-[var(--color-paper-3)]'
              }`}
            >
              <div>
                <div className="flex items-start justify-between gap-3 mb-1.5">
                  <h3 className="font-semibold text-white text-sm flex items-center gap-2">
                    {tpl.name}
                    {isSelected && (
                      <span className="inline-flex items-center gap-1 text-[10px] font-medium bg-emerald-400/20 text-emerald-300 px-2 py-0.5 rounded-full border border-emerald-400/30">
                        <Check className="w-3 h-3" aria-hidden="true" /> Active
                      </span>
                    )}
                  </h3>
                </div>
                <p className="text-[11px] text-slate-300 leading-relaxed mb-3">
                  {tpl.description}
                </p>
              </div>

              <div>
                <div className="flex flex-wrap gap-1 mb-2.5">
                  {tpl.tags.map((tag, i) => (
                    <span
                      key={i}
                      className="text-[10px] font-medium px-2 py-0.5 rounded-md bg-[var(--color-paper)] text-slate-400 border border-white/[0.06]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>

                <div className="pt-2 border-t border-white/[0.06] flex items-center justify-between text-[11px]">
                  <span className="text-slate-400">Target Role:</span>
                  <span className="text-slate-200 font-medium truncate max-w-[220px]" title={tpl.recommended_for}>
                    {tpl.recommended_for}
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </Modal>
  );
};
