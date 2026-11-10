import React, { useState } from 'react';
import { GitCompare, Plus, Minus, ArrowRight } from 'lucide-react';
import { ResumeDiffComparison, ResumeVersionItem } from '../../types';
import { Modal } from '../ui/Modal';

interface ResumeCompareModalProps {
  isOpen: boolean;
  onClose: () => void;
  diff: ResumeDiffComparison | null;
  versions: ResumeVersionItem[];
  isLoading: boolean;
  onSelectCompareTarget: (target: { target_version_id?: number; compare_with_master?: boolean }) => void;
}

export const ResumeCompareModal: React.FC<ResumeCompareModalProps> = ({
  isOpen,
  onClose,
  diff,
  versions,
  isLoading,
  onSelectCompareTarget
}) => {
  const [compareMode, setCompareMode] = useState<'master' | 'version'>('master');
  const [selectedVersionId, setSelectedVersionId] = useState<number>(versions[0]?.id || 0);

  const handleModeChange = (mode: 'master' | 'version') => {
    setCompareMode(mode);
    if (mode === 'master') {
      onSelectCompareTarget({ compare_with_master: true });
    } else if (versions.length > 0) {
      onSelectCompareTarget({ target_version_id: selectedVersionId || versions[0].id });
    }
  };

  const handleVersionSelect = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const vId = parseInt(e.target.value);
    setSelectedVersionId(vId);
    onSelectCompareTarget({ target_version_id: vId });
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="5xl"
      title="Resume Comparison & Change Audit"
      description="Detailed diff analysis comparing current document with Master or previous checkpoints"
      footer={
        <div className="flex items-center justify-between w-full text-xs text-slate-400">
          <span className="text-[11px] text-slate-500">Non-destructive diff viewer across LaTeX AST structure</span>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-xs font-medium bg-white/[0.06] hover:bg-white/[0.10] text-slate-200 rounded-lg transition border border-white/[0.08]"
          >
            Close Diff
          </button>
        </div>
      }
    >
      <div className="space-y-4">
        {/* Comparison Selector Bar */}
        <div className="p-3 rounded-xl bg-[var(--color-paper-3)] border border-white/[0.08] flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-slate-400 font-medium">Compare Against:</span>
            <div className="flex items-center rounded-lg bg-[var(--color-paper)] p-0.5 border border-white/[0.08]">
              <button
                type="button"
                onClick={() => handleModeChange('master')}
                className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                  compareMode === 'master'
                    ? 'bg-white/[0.10] text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Master Resume
              </button>
              <button
                type="button"
                onClick={() => handleModeChange('version')}
                className={`px-3 py-1 text-xs font-medium rounded-md transition ${
                  compareMode === 'version'
                    ? 'bg-white/[0.10] text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                Version Snapshot
              </button>
            </div>

            {compareMode === 'version' && (
              <select
                value={selectedVersionId}
                onChange={handleVersionSelect}
                className="bg-[var(--color-paper)] border border-white/[0.08] text-white rounded-lg px-2.5 py-1 text-xs focus:ring-1 focus:ring-emerald-400/60 focus:outline-none"
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} — {v.change_summary || 'Checkpoint'} ({new Date(v.created_at).toLocaleDateString()})
                  </option>
                ))}
              </select>
            )}
          </div>

          {diff && (
            <div className="flex items-center gap-3 text-xs">
              <span className="flex items-center gap-1 text-emerald-400 font-medium">
                <Plus className="w-3.5 h-3.5" /> {diff.added_lines} Added
              </span>
              <span className="flex items-center gap-1 text-rose-400 font-medium">
                <Minus className="w-3.5 h-3.5" /> {diff.removed_lines} Modified/Cut
              </span>
            </div>
          )}
        </div>

        {/* Content Body */}
        {isLoading ? (
          <div className="py-20 flex flex-col items-center justify-center text-slate-400 gap-3">
            <GitCompare className="w-8 h-8 animate-spin text-emerald-400" />
            <p className="text-xs font-medium text-slate-300">Computing line-by-line diff and semantic section analysis...</p>
          </div>
        ) : diff ? (
          <div className="space-y-4">
            {/* Section Impact Cards */}
            {diff.section_changes.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-slate-400">
                  Section Structural Evolution
                </h4>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                  {diff.section_changes.map((sc, i) => (
                    <div key={i} className="p-3 rounded-lg bg-[var(--color-paper-3)]/60 border border-white/[0.06] flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-xs font-semibold text-white">{sc.section}</span>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${
                              sc.status === 'added'
                                ? 'bg-emerald-400/20 text-emerald-300 border border-emerald-400/30'
                                : sc.status === 'reordered'
                                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                                : sc.status === 'removed'
                                ? 'bg-rose-500/20 text-rose-300 border border-rose-500/30'
                                : 'bg-blue-500/20 text-blue-300 border border-blue-500/30'
                            }`}
                          >
                            {sc.status.replace('_', ' ')}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400">{sc.rationale}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Code Diff Table */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-300 text-xs">
                  LaTeX Source Code Diff
                </span>
                <div className="flex items-center gap-2 text-[11px]">
                  <span className="text-slate-400">{diff.base_label}</span>
                  <ArrowRight className="w-3.5 h-3.5 text-slate-500" />
                  <span className="text-white font-medium">{diff.target_label}</span>
                </div>
              </div>

              <div className="rounded-xl border border-white/[0.08] bg-[var(--color-paper)] font-mono text-[11px] overflow-x-auto max-h-[420px] divide-y divide-white/[0.04]">
                {diff.diff_lines.map((line, idx) => {
                  const isAdded = line.type === 'added';
                  const isRemoved = line.type === 'removed';
                  return (
                    <div
                      key={idx}
                      className={`flex items-start py-0.5 px-3 leading-relaxed ${
                        isAdded
                          ? 'bg-emerald-400/[0.08] text-emerald-300'
                          : isRemoved
                          ? 'bg-rose-500/[0.10] text-rose-300 line-through opacity-80'
                          : 'text-slate-400 hover:bg-white/[0.02]'
                      }`}
                    >
                      <span className="w-9 text-right pr-2 select-none text-slate-600 shrink-0">
                        {line.base_line_no || ''}
                      </span>
                      <span className="w-9 text-right pr-2 select-none text-slate-600 shrink-0">
                        {line.target_line_no || ''}
                      </span>
                      <span className="w-5 text-center select-none shrink-0 font-bold">
                        {isAdded ? '+' : isRemoved ? '-' : ' '}
                      </span>
                      <span className="whitespace-pre flex-1 pl-1">{line.content}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center py-16 text-slate-400">
            <p className="text-xs">Select a version snapshot to compute diff analysis.</p>
          </div>
        )}
      </div>
    </Modal>
  );
};
