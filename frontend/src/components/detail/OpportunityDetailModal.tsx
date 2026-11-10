import React, { useEffect, useState } from 'react';
import {
  ExternalLink,
  Sparkles,
  CheckCircle2,
  AlertCircle,
  FileText,
  MapPin,
  Calendar,
  DollarSign,
  Clock,
  Bookmark,
  Send,
  Briefcase,
  RotateCw
} from 'lucide-react';
import { OpportunityDetail } from '../../types';
import { fetchOpportunityDetail, evaluateOpportunityMatch } from '../../services/api';
import { Modal } from '../ui/Modal';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';

interface OpportunityDetailModalProps {
  opportunityId: number | null;
  onClose: () => void;
  onToggleSave: (id: number) => void;
  onHandoffTracker: (id: number) => void;
}

export const OpportunityDetailModal: React.FC<OpportunityDetailModalProps> = ({
  opportunityId,
  onClose,
  onToggleSave,
  onHandoffTracker
}) => {
  const [detail, setDetail] = useState<OpportunityDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [recalculating, setRecalculating] = useState(false);
  const [activeTab, setActiveTab] = useState<'analysis' | 'description' | 'handoff'>('analysis');

  useEffect(() => {
    if (!opportunityId) return;
    setLoading(true);
    fetchOpportunityDetail(opportunityId)
      .then(data => setDetail(data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, [opportunityId]);

  const handleRecalculate = async () => {
    if (!opportunityId || recalculating) return;
    setRecalculating(true);
    try {
      await evaluateOpportunityMatch(opportunityId, true);
      const updated = await fetchOpportunityDetail(opportunityId);
      setDetail(updated);
    } catch (err) {
      console.error('Failed to recalculate match:', err);
    } finally {
      setRecalculating(false);
    }
  };

  if (!opportunityId) return null;

  const match = detail?.match_analysis;
  const extracted = detail?.extracted_data;

  return (
    <Modal
      isOpen={Boolean(opportunityId)}
      onClose={onClose}
      size="4xl"
      title={
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-[var(--radius-sm)] bg-[var(--color-surface-raised)] border border-white/[0.09] flex items-center justify-center text-[var(--color-ink)] font-bold text-sm shrink-0">
            {detail?.company_name?.slice(0, 2).toUpperCase() || 'CO'}
          </div>
          <div>
            <div className="flex items-center space-x-2 text-xs">
              <span className="font-semibold text-[var(--color-primary)]">
                {detail?.company_name}
              </span>
              <span className="text-[var(--color-ink-tertiary)]" aria-hidden="true">•</span>
              <span className="text-[var(--color-ink-tertiary)] capitalize font-mono text-[11px]">{detail?.source_platform}</span>
            </div>
            <h2 className="text-base sm:text-lg font-semibold text-[var(--color-ink)] tracking-tight line-clamp-1">
              {detail?.title || 'Loading opportunity...'}
            </h2>
          </div>
        </div>
      }
      headerAction={
        detail?.original_url ? (
          <Button
            variant="primary"
            size="sm"
            onClick={() => window.open(detail.original_url, '_blank')}
            rightIcon={<ExternalLink className="w-3.5 h-3.5" />}
          >
            Apply on Portal
          </Button>
        ) : undefined
      }
    >
      {/* Overview Metadata Bar */}
      <div className="px-5 py-3 bg-[var(--color-paper-quiet)] border-b border-white/[0.07] flex flex-wrap items-center gap-4 text-xs text-[var(--color-ink-secondary)]">
        <div className="flex items-center space-x-1.5">
          <MapPin className="w-3.5 h-3.5 text-[var(--color-ink-tertiary)]" />
          <span>{detail?.normalized_location || detail?.location}</span>
        </div>
        <div className="flex items-center space-x-1.5 capitalize">
          <Briefcase className="w-3.5 h-3.5 text-[var(--color-ink-tertiary)]" />
          <span>{detail?.workplace_type} ({detail?.employment_type})</span>
        </div>
        {detail?.stipend_text && (
          <div className="flex items-center space-x-1 text-[var(--color-primary)] font-mono font-medium">
            <DollarSign className="w-3.5 h-3.5" />
            <span>{detail.stipend_text}</span>
          </div>
        )}
        {detail?.duration_months && (
          <div className="flex items-center space-x-1.5 text-[var(--color-ink-secondary)]">
            <Clock className="w-3.5 h-3.5 text-[var(--color-ink-tertiary)]" />
            <span>{detail.duration_months} Months</span>
          </div>
        )}
        {detail?.deadline_at && (
          <div className="flex items-center space-x-1.5 text-rose-300 font-medium font-mono text-[11px]">
            <Calendar className="w-3.5 h-3.5 text-rose-400" />
            <span>Deadline: {new Date(detail.deadline_at).toLocaleDateString()}</span>
          </div>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="px-5 pt-2 border-b border-white/[0.07] bg-[var(--color-surface)] flex space-x-4" role="tablist" aria-label="Opportunity Details">
        {[
          { id: 'analysis', label: 'Requirements & Match Analysis', icon: Sparkles },
          { id: 'description', label: 'Full Job Description', icon: FileText },
          { id: 'handoff', label: 'Application Handoff & Strategy', icon: Send },
        ].map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setActiveTab(tab.id as any)}
              className={`pb-2.5 text-xs font-semibold transition border-b-2 flex items-center space-x-1.5 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] rounded-t ${
                active
                  ? 'border-[var(--color-primary)] text-[var(--color-primary)]'
                  : 'border-transparent text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)]'
              }`}
            >
              <Icon className="w-3.5 h-3.5" aria-hidden="true" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Content Body */}
      <div className="p-5 sm:p-6 space-y-5 text-xs text-[var(--color-ink-secondary)] bg-[var(--color-paper)]">
        {loading ? (
          <div className="p-16 text-center text-[var(--color-ink-tertiary)] flex flex-col items-center gap-3">
            <RotateCw className="w-5 h-5 animate-spin text-[var(--color-primary)]" />
            <span>Loading opportunity analysis...</span>
          </div>
        ) : detail ? (
          <>
            {activeTab === 'analysis' && (
              <div className="space-y-5">
                {/* Score Card Banner */}
                <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 shadow-sm">
                  <div>
                    <div className="flex items-center space-x-2.5">
                      <span className="text-3xl font-bold text-[var(--color-ink)] font-mono tnum">
                        {Math.round(detail.match_score)}%
                      </span>
                      <Badge
                        variant={detail.eligibility_status === 'disqualified' ? 'rose' : 'emerald'}
                        size="md"
                      >
                        {detail.eligibility_status === 'disqualified' ? 'Disqualified' : 'Compatibility Score'}
                      </Badge>
                      {detail.match_freshness?.is_stale && (
                        <Badge variant="amber" size="sm" className="font-mono text-[10px]">
                          Profile modified · Stale
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-[var(--color-ink-tertiary)] mt-1.5 leading-relaxed">
                      Computed via deterministic 5-category weighted evaluation and eligibility validation against verified profile evidence.
                    </p>
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleRecalculate}
                      disabled={recalculating}
                      leftIcon={<RotateCw className={`w-3.5 h-3.5 ${recalculating ? 'animate-spin text-[var(--color-primary)]' : ''}`} />}
                    >
                      {recalculating ? 'Recalculating…' : 'Recalculate Match'}
                    </Button>
                  </div>
                </div>

                {/* Scoring Explanation */}
                {(detail.scoring_explanation || match?.scoring_explanation) && (
                  <div className="p-3.5 rounded-[var(--radius-card)] bg-[var(--color-surface-raised)] border border-white/[0.07] text-xs leading-relaxed space-y-1">
                    <div className="flex items-center gap-1.5 font-semibold text-[var(--color-ink)]">
                      <Sparkles className="w-3.5 h-3.5 text-[var(--color-primary)]" />
                      <span>Matching Intelligence Rationale</span>
                    </div>
                    <p className="text-[var(--color-ink-secondary)] pl-5 text-[11px] leading-relaxed">
                      {detail.scoring_explanation || match?.scoring_explanation}
                    </p>
                  </div>
                )}

                {/* Category Factor Progress Bars */}
                {detail.category_scores && Object.keys(detail.category_scores).length > 0 && (
                  <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-3">
                    <div className="flex items-center justify-between text-xs font-semibold text-[var(--color-ink)]">
                      <span>Evaluation Breakdown by Category</span>
                      <span className="font-mono text-[10px] text-[var(--color-ink-tertiary)]">Weight Normalized</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px]">
                      {Object.entries(detail.category_scores).map(([catKey, rawScore]) => {
                        const score = typeof rawScore === 'number' ? Math.round(rawScore) : 0;
                        const weight = detail.category_weights?.[catKey] 
                          ? `${Math.round(detail.category_weights[catKey] * 100)}% weight` 
                          : null;
                        const cleanLabel = catKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        return (
                          <div key={catKey} className="space-y-1 rounded-[var(--radius-xs)] bg-white/[0.02] p-2.5 border border-white/[0.05]">
                            <div className="flex justify-between text-[var(--color-ink)]">
                              <span className="font-medium truncate">{cleanLabel}</span>
                              <span className="font-mono text-[var(--color-primary)] font-bold">{score}%</span>
                            </div>
                            <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-colors duration-300 ${
                                  score >= 70 ? 'bg-[var(--color-primary)]' : score >= 50 ? 'bg-amber-400' : 'bg-slate-500'
                                }`}
                                style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                              />
                            </div>
                            {weight && (
                              <div className="text-[10px] text-[var(--color-ink-tertiary)] font-mono">{weight}</div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Disqualification Warnings */}
                {match?.disqualifying_reasons && match.disqualifying_reasons.length > 0 && (
                  <div className="p-3.5 rounded-[var(--radius-card)] bg-rose-500/10 border border-rose-500/25 text-rose-300 text-xs space-y-1">
                    <div className="flex items-center space-x-1.5 font-bold text-rose-400">
                      <AlertCircle className="w-4 h-4 shrink-0" />
                      <span>Eligibility Warnings</span>
                    </div>
                    <ul className="list-disc list-inside space-y-0.5 pl-1">
                      {match.disqualifying_reasons.map((reason, i) => (
                        <li key={i}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Requirement Matches & Evidence Strength */}
                {detail.requirement_matches && detail.requirement_matches.length > 0 && (
                  <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-3">
                    <div className="flex items-center space-x-1.5 text-xs font-bold text-[var(--color-ink)]">
                      <CheckCircle2 className="w-4 h-4 text-[var(--color-primary)]" />
                      <span>Extracted Requirements & Profile Evidence ({detail.requirement_matches.length})</span>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                      {detail.requirement_matches.map((reqMatch, i) => {
                        const isStrong = reqMatch.status === 'strong_match';
                        const isPartial = reqMatch.status === 'partial_match';
                        return (
                          <div key={i} className="p-2.5 rounded-[var(--radius-xs)] bg-white/[0.02] border border-white/[0.05] text-xs space-y-1">
                            <div className="flex items-center justify-between">
                              <span className="font-semibold text-[var(--color-ink)]">{reqMatch.requirement?.name}</span>
                              <Badge
                                size="sm"
                                variant={isStrong ? 'emerald' : isPartial ? 'amber' : 'neutral'}
                                className="capitalize font-mono text-[10px]"
                              >
                                {reqMatch.status.replace(/_/g, ' ')}
                              </Badge>
                            </div>
                            <p className="text-[11px] text-[var(--color-ink-secondary)] leading-relaxed">
                              {reqMatch.explanation || reqMatch.missing_evidence_description || 'Matched against profile evidence'}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Actionable Skill Gaps */}
                {detail.skill_gaps && detail.skill_gaps.length > 0 && (
                  <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-3">
                    <div className="flex items-center space-x-1.5 text-xs font-bold text-amber-400">
                      <AlertCircle className="w-4 h-4" />
                      <span>Actionable Skill Gaps & Interview Preparation ({detail.skill_gaps.length})</span>
                    </div>
                    <div className="space-y-2">
                      {detail.skill_gaps.map((gap, i) => (
                        <div key={i} className="p-2.5 rounded-[var(--radius-xs)] bg-white/[0.02] border border-white/[0.05] text-xs space-y-1">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-[var(--color-ink)]">{gap.skill_name}</span>
                            <Badge variant="amber" size="sm" className="font-mono text-[10px] capitalize">
                              {gap.priority}
                            </Badge>
                          </div>
                          <p className="text-[11px] text-[var(--color-ink-secondary)] leading-relaxed">
                            {gap.suggested_learning_or_improvement}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Skills Matrix */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Verified Matches */}
                  <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-2.5">
                    <div className="flex items-center space-x-1.5 text-xs font-bold text-[var(--color-primary)]">
                      <CheckCircle2 className="w-4 h-4" />
                      <span>Verified Profile Matches ({match?.skill_compatibility?.strong?.length || 0})</span>
                    </div>
                    <div className="space-y-1.5">
                      {match?.skill_compatibility?.strong?.map((item, i) => (
                        <div key={i} className="p-2 rounded-[var(--radius-xs)] bg-white/[0.02] border border-white/[0.05] text-xs">
                          <span className="font-semibold text-[var(--color-ink)]">{item.skill}</span>
                          <span className="text-[11px] text-[var(--color-ink-tertiary)] block mt-0.5">{item.evidence}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  {/* Transferable Skills */}
                  <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-2.5">
                    <div className="flex items-center space-x-1.5 text-xs font-bold text-amber-400">
                      <Sparkles className="w-4 h-4" />
                      <span>Transferable Competencies ({match?.skill_compatibility?.partial?.length || 0})</span>
                    </div>
                    <div className="space-y-1.5">
                      {match?.skill_compatibility?.partial?.map((item, i) => (
                        <div key={i} className="p-2 rounded-[var(--radius-xs)] bg-white/[0.02] border border-white/[0.05] text-xs">
                          <div className="flex items-center justify-between">
                            <span className="font-semibold text-[var(--color-ink)]">{item.skill}</span>
                            <span className="text-[10px] text-amber-400 font-medium font-mono">via {item.transferable_from}</span>
                          </div>
                          <span className="text-[11px] text-[var(--color-ink-tertiary)] block mt-0.5">{item.reason}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Missing Skills & Key Responsibilities */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-2">
                    <h3 className="text-xs font-bold text-[var(--color-ink-secondary)]">
                      Missing Keywords ({match?.skill_compatibility?.missing?.length || 0})
                    </h3>
                    <div className="flex flex-wrap gap-1.5">
                      {match?.skill_compatibility?.missing?.map((skill, i) => (
                        <Badge key={i} variant="neutral" size="sm">
                          {skill}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {extracted?.responsibilities && extracted.responsibilities.length > 0 && (
                    <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-2">
                      <h3 className="text-xs font-bold text-[var(--color-ink-secondary)]">Key Responsibilities</h3>
                      <ul className="space-y-1 list-disc list-inside text-[var(--color-ink-secondary)]">
                        {extracted.responsibilities.slice(0, 3).map((r, i) => (
                          <li key={i} className="leading-relaxed">{r}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            )}

            {activeTab === 'description' && (
              <div className="prose prose-invert max-w-none text-xs leading-relaxed font-sans whitespace-pre-wrap bg-[var(--color-surface)] p-5 rounded-[var(--radius-card)] border border-white/[0.07] text-[var(--color-ink)]">
                {detail.description}
              </div>
            )}

            {activeTab === 'handoff' && (
              <div className="space-y-4">
                <div className="p-4 rounded-[var(--radius-card)] bg-[var(--color-surface)] border border-white/[0.07] space-y-2">
                  <h3 className="text-sm font-bold text-[var(--color-ink)]">Application Handoff & Dossier Strategy</h3>
                  <p className="text-xs text-[var(--color-ink-secondary)]">
                    Prepare a job-specific LaTeX resume and application package based on your verified background.
                  </p>

                  <div className="mt-3 p-3 rounded-[var(--radius-xs)] bg-[var(--color-paper-quiet)] border border-white/[0.05] font-mono text-xs text-[var(--color-primary)] whitespace-pre-line leading-relaxed">
                    {`Target Dossier Focus for ${detail.company_name}:\n`}
                    {`• Emphasize verified skills: ${match?.skill_compatibility?.strong?.map(s => s.skill).slice(0, 4).join(', ') || 'Python, REST API, Git'}\n`}
                    {`• Highlight project: '${match?.relevant_projects?.[0]?.title || 'CareerOS Project'}'\n`}
                    {`• Transferable skills: ${match?.transferable_skills?.slice(0, 2).join(', ') || 'Systems Engineering'}`}
                  </div>
                </div>

                <div className="flex items-center space-x-3 pt-2">
                  <Button
                    variant="primary"
                    size="md"
                    disabled={detail.is_applied}
                    onClick={() => onHandoffTracker(detail.id)}
                    leftIcon={<Send className="w-4 h-4" />}
                  >
                    {detail.is_applied ? 'Already in Tracker' : 'Add to Application Tracker'}
                  </Button>

                  {detail.original_url && (
                    <Button
                      variant="outline"
                      size="md"
                      onClick={() => window.open(detail.original_url, '_blank')}
                      rightIcon={<ExternalLink className="w-4 h-4" />}
                    >
                      Open Application Link
                    </Button>
                  )}
                </div>
              </div>
            )}
          </>
        ) : null}
      </div>

      {/* Footer Controls */}
      <div className="p-3.5 border-t border-white/[0.07] bg-[var(--color-surface)] flex items-center justify-between">
        <Button
          variant={detail?.is_saved ? 'secondary' : 'outline'}
          size="sm"
          onClick={() => onToggleSave(detail?.id || 0)}
          leftIcon={<Bookmark className={`w-3.5 h-3.5 ${detail?.is_saved ? 'text-amber-400 fill-current' : ''}`} />}
        >
          {detail?.is_saved ? 'Saved in Watchlist' : 'Save Opportunity'}
        </Button>

        <Button variant="ghost" size="sm" onClick={onClose}>
          Close
        </Button>
      </div>
    </Modal>
  );
};
