import React, { useState } from 'react';
import { Sparkles, Check, ArrowRight, ShieldCheck, CheckCircle2, ChevronRight, AlertCircle, FileText } from 'lucide-react';
import { Opportunity, ResumeOptimizationProposal } from '../../types';
import { Modal } from '../ui/Modal';

interface AIOptimizeModalProps {
  isOpen: boolean;
  onClose: () => void;
  opportunities: Opportunity[];
  proposal: ResumeOptimizationProposal | null;
  isLoading: boolean;
  onRequestOptimization: (opportunityId: number) => void;
  onApplyOptimization: (acceptedBullets: Array<{ original: string; suggested: string }>) => void;
}

export const AIOptimizeModal: React.FC<AIOptimizeModalProps> = ({
  isOpen,
  onClose,
  opportunities,
  proposal,
  isLoading,
  onRequestOptimization,
  onApplyOptimization
}) => {
  const [selectedOppId, setSelectedOppId] = useState<number>(opportunities[0]?.id || 0);
  const [selectedBullets, setSelectedBullets] = useState<Record<number, boolean>>({});

  const handleSelectOpp = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const oppId = parseInt(e.target.value);
    setSelectedOppId(oppId);
    setSelectedBullets({});
    onRequestOptimization(oppId);
  };

  const toggleBullet = (index: number) => {
    setSelectedBullets(prev => ({ ...prev, [index]: !prev[index] }));
  };

  const handleApply = () => {
    if (!proposal) return;
    const accepted = proposal.bullet_refinements.filter((_, idx) => selectedBullets[idx] !== false);
    onApplyOptimization(accepted);
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="4xl"
      title="AI Resume Optimization & Tailoring"
      description="Target-specific alignment with verified candidate evidence & explicit user approval"
      footer={
        <div className="flex flex-wrap items-center justify-between gap-3 w-full">
          <div className="text-[11px] text-slate-400">
            Applying creates a new version checkpoint and re-compiles the PDF.
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-xs font-medium bg-white/[0.06] hover:bg-white/[0.10] text-slate-200 rounded-lg transition border border-white/[0.08]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleApply}
              disabled={isLoading || !proposal}
              className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] rounded-lg transition disabled:opacity-50 shadow-sm"
            >
              <Check className="w-3.5 h-3.5" />
              <span>Apply Approved Changes</span>
            </button>
          </div>
        </div>
      }
    >
      <div className="space-y-5">
        {/* Opportunity Selector Bar */}
        <div className="p-3.5 rounded-xl bg-[var(--color-paper-3)] border border-white/[0.08] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-slate-300 font-medium">
            <span className="text-[12px] text-slate-400">Target Opportunity:</span>
            <select
              value={selectedOppId || (proposal?.opportunity_id ?? '')}
              onChange={handleSelectOpp}
              className="bg-[var(--color-paper)] border border-white/[0.10] text-white rounded-lg px-3 py-1.5 text-xs focus:ring-1 focus:ring-emerald-400/60 focus:outline-none max-w-xs truncate"
            >
              {opportunities.map((opp) => (
                <option key={opp.id} value={opp.id}>
                  {opp.company_name}, {opp.title}
                </option>
              ))}
            </select>
          </div>

          {/* Zero-Fabrication Banner */}
          <div className="flex items-center gap-1.5 px-3 py-1 rounded-full bg-emerald-400/[0.10] border border-emerald-400/25 text-emerald-300 text-[11px] font-medium">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>Zero-Fabrication Guardrail Active</span>
          </div>
        </div>

        {/* Content Body */}
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-3">
            <Sparkles className="w-8 h-8 animate-spin text-emerald-400" />
            <p className="text-xs font-medium text-slate-300">Analyzing candidate profile evidence against target role requirements...</p>
          </div>
        ) : proposal ? (
          <div className="space-y-4">
            {/* Skills Alignment */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3.5 rounded-xl bg-[var(--color-paper-3)]/60 border border-white/[0.06]">
                <h4 className="text-[12px] font-semibold text-white mb-2 flex items-center gap-1.5">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span>Verified Matching Skills ({proposal.verified_matching_skills.length})</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {proposal.verified_matching_skills.length > 0 ? (
                    proposal.verified_matching_skills.map((s, i) => (
                      <span key={i} className="text-[11px] px-2 py-0.5 rounded-md bg-emerald-400/[0.10] text-emerald-300 border border-emerald-400/20 font-medium">
                        {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-400">No direct exact skill overlap found.</span>
                  )}
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-[var(--color-paper-3)]/60 border border-white/[0.06]">
                <h4 className="text-[12px] font-semibold text-white mb-2 flex items-center gap-1.5">
                  <AlertCircle className="w-4 h-4 text-amber-400" />
                  <span>Missing Job Keywords ({proposal.missing_job_keywords.length})</span>
                </h4>
                <div className="flex flex-wrap gap-1.5">
                  {proposal.missing_job_keywords.length > 0 ? (
                    proposal.missing_job_keywords.map((s, i) => (
                      <span key={i} className="text-[11px] px-2 py-0.5 rounded-md bg-amber-400/[0.10] text-amber-300 border border-amber-400/20 font-medium">
                        {s}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-slate-400">All target job keywords are covered in your profile!</span>
                  )}
                </div>
              </div>
            </div>

            {/* Highlight Candidate Evidence */}
            {proposal.highlight_projects.length > 0 && (
              <div className="p-3.5 rounded-xl bg-[var(--color-paper-3)]/60 border border-white/[0.06]">
                <h4 className="text-[12px] font-semibold text-white mb-2.5 flex items-center gap-1.5">
                  <FileText className="w-4 h-4 text-emerald-400" />
                  <span>Candidate Profile Evidence to Feature</span>
                </h4>
                <div className="grid grid-cols-1 gap-2">
                  {proposal.highlight_projects.map((proj, idx) => (
                    <div key={idx} className="p-3 rounded-lg bg-[var(--color-paper)] border border-white/[0.06] flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                      <div>
                        <span className="text-xs font-semibold text-white">{proj.title}</span>
                        <p className="text-[11px] text-slate-400 mt-0.5">{proj.recommended_focus}</p>
                      </div>
                      <div className="flex items-center gap-1 shrink-0 flex-wrap">
                        {proj.overlapping_skills.map((skill, sIdx) => (
                          <span key={sIdx} className="text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-slate-300 border border-white/[0.08] font-medium">
                            {skill}
                          </span>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Section Ordering Suggestion */}
            <div className="p-3.5 rounded-xl bg-[var(--color-paper-3)]/60 border border-white/[0.06]">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-[12px] font-semibold text-white">
                  Recommended Section Flow
                </h4>
                <span className="text-[11px] text-slate-400 italic">{proposal.section_order_rationale}</span>
              </div>
              <div className="flex flex-wrap items-center gap-1.5 pt-1">
                {proposal.suggested_section_order.map((sec, i) => (
                  <React.Fragment key={i}>
                    <span className="text-[11px] font-medium px-2.5 py-1 rounded-md bg-white/[0.06] text-slate-200 border border-white/[0.08]">
                      {i + 1}. {sec}
                    </span>
                    {i < proposal.suggested_section_order.length - 1 && (
                      <ChevronRight className="w-3 h-3 text-slate-600" />
                    )}
                  </React.Fragment>
                ))}
              </div>
            </div>

            {/* STAR Bullet Point Improvements */}
            {proposal.bullet_refinements.length > 0 && (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <h4 className="text-[12px] font-semibold text-white">
                    STAR Bullet Point Refinements (Review & Select)
                  </h4>
                  <span className="text-[11px] text-slate-400">Replaces passive phrasing with action verbs</span>
                </div>

                <div className="space-y-2.5">
                  {proposal.bullet_refinements.map((b, idx) => {
                    const isChecked = selectedBullets[idx] !== false;
                    return (
                      <div
                        key={idx}
                        onClick={() => toggleBullet(idx)}
                        className={`p-3.5 rounded-xl border cursor-pointer transition-colors ${
                          isChecked
                            ? 'bg-emerald-400/[0.04] border-emerald-400/40 ring-1 ring-emerald-400/20'
                            : 'bg-[var(--color-paper-3)]/40 border-white/[0.06] opacity-60'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            checked={isChecked}
                            onChange={() => toggleBullet(idx)}
                            className="mt-0.5 rounded border-white/[0.20] bg-[var(--color-paper)] text-emerald-400 focus:ring-emerald-400/40"
                          />
                          <div className="flex-1 space-y-1.5">
                            <div className="text-[11px] text-slate-400 line-through">
                              {b.original}
                            </div>
                            <div className="flex items-center gap-2 text-xs font-medium text-emerald-300">
                              <ArrowRight className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                              <span>{b.suggested}</span>
                            </div>
                            <div className="text-[10px] text-slate-400 italic">
                              {b.rationale}
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Trimmable Content Suggestion */}
            {proposal.content_trim_suggestions.length > 0 && (
              <div className="p-3 rounded-xl bg-[var(--color-paper-3)]/40 border border-white/[0.06] text-xs text-slate-300 space-y-1">
                <span className="font-semibold text-amber-400 text-[11px]">Single-Page Optimization Note:</span>
                {proposal.content_trim_suggestions.map((t, i) => (
                  <p key={i} className="text-[11px] text-slate-400 leading-relaxed">
                    • {t.section}: {t.suggestion}
                  </p>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="text-center py-16 text-slate-400">
            <p className="text-xs">Select a target opportunity to generate role-aligned optimization recommendations.</p>
          </div>
        )}
      </div>
    </Modal>
  );
};
