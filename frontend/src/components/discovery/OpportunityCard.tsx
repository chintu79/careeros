import React, { useState } from 'react';
import {
  MapPin,
  Calendar,
  Sparkles,
  Bookmark,
  X,
  ExternalLink,
  FileText,
  Send,
  Check,
  ChevronDown,
  ChevronUp,
  ShieldCheck,
  MoreHorizontal,
  RotateCw,
  AlertCircle
} from 'lucide-react';
import { OpportunityItem } from '../../types';
import { Button, CountUp, Badge, Card } from '../ui';

interface OpportunityCardProps {
  item: OpportunityItem;
  onViewDetail: (id: number) => void;
  onToggleSave: (id: number) => void;
  onDismiss: (id: number) => void;
  onDismissClick?: (item: OpportunityItem) => void;
  onHandoffTracker: (id: number) => void;
  onTailorResume: (id: number) => void;
  onPrepareApply: (id: number) => void;
  onCalculateMatch?: (id: number) => Promise<void> | void;
}

export const OpportunityCard: React.FC<OpportunityCardProps> = ({
  item,
  onViewDetail,
  onToggleSave,
  onDismiss,
  onDismissClick,
  onHandoffTracker,
  onTailorResume,
  onPrepareApply,
  onCalculateMatch
}) => {
  const [showFullMatch, setShowFullMatch] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [calculating, setCalculating] = useState(false);

  const getInitials = (name: string) => {
    return name
      .split(' ')
      .slice(0, 2)
      .map(part => part[0])
      .join('')
      .toUpperCase();
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Not disclosed';
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return 'Not disclosed';
    return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  const formatRelative = (dateStr?: string) => {
    if (!dateStr) return 'Recently';
    const diff = Date.now() - new Date(dateStr).getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days <= 0) return 'Today';
    if (days === 1) return '1d ago';
    if (days < 30) return `${days}d ago`;
    return formatDate(dateStr);
  };

  const isDisqualified = item.eligibility_status === 'disqualified';
  const deadlineInfo = item.deadline_info;
  const reliability = item.source_reliability;
  const whyMatches = item.why_it_matches || [];
  const matchingSkills = item.matching_skills || [];
  const missingSkills = item.missing_skills || [];

  // Evaluation & Freshness Semantics
  const isEvaluated = item.ranking_reasons?.is_evaluated ?? (item.match_score > 0);
  const isStale = Boolean(
    item.ranking_reasons?.is_stale ||
    item.ranking_reasons?.evaluation_state === 'stale' ||
    item.match_freshness?.is_stale
  );

  const categoryScores = item.category_scores || item.match_analysis?.category_scores || item.match_analysis?.score_breakdown || {};
  const categoryWeights = item.category_weights || item.match_analysis?.category_weights || {};
  const skillGaps = item.skill_gaps || item.match_analysis?.skill_gaps || [];
  const scoringExplanation = item.scoring_explanation || item.match_analysis?.scoring_explanation;

  const handleCalculate = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!onCalculateMatch || calculating) return;
    setCalculating(true);
    try {
      await onCalculateMatch(item.id);
    } catch (err) {
      console.error('Failed to calculate match:', err);
    } finally {
      setCalculating(false);
    }
  };

  return (
    <article
      className={`group rounded-[var(--radius-card)] border bg-[var(--color-surface)] shadow-card transition-colors duration-150 ${
        item.is_saved
          ? 'border-amber-400/30 bg-amber-500/[0.02]'
          : 'border-white/[0.07] hover:border-white/[0.14]'
      } ${isDisqualified ? 'opacity-75' : ''}`}
    >
      <div className="p-4 sm:p-5">
        {/* Header Row: Initials, Company, Title & Match Score */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-3.5">
            <div
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-white/[0.08] bg-white/[0.03] font-mono text-[12px] font-semibold text-[var(--color-ink-secondary)] shadow-sm"
              aria-hidden="true"
            >
              {getInitials(item.company_name)}
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px]">
                <span className="truncate font-semibold text-[var(--color-ink-secondary)]">{item.company_name}</span>
                <span className="text-[var(--color-ink-tertiary)]" aria-hidden="true">·</span>
                <span className="capitalize text-[var(--color-ink-tertiary)] font-mono text-[10px]">{item.source_platform}</span>
                {reliability && (
                  <span className="inline-flex items-center gap-1 text-[var(--color-ink-tertiary)]">
                    <ShieldCheck className="h-3 w-3 text-emerald-400/80" strokeWidth={1.75} aria-hidden="true" />
                    <span className="font-mono text-[10px]">{reliability.score}%</span>
                  </span>
                )}
                {(isDisqualified || item.is_applied) && (
                  <Badge
                    size="sm"
                    variant={isDisqualified ? 'rose' : 'neutral'}
                    className="font-mono"
                  >
                    {isDisqualified ? 'Not eligible' : 'Applied'}
                  </Badge>
                )}
              </div>

              <h3 className="mt-1 text-[15px] font-semibold leading-snug text-[var(--color-ink)]">
                <button
                  type="button"
                  onClick={() => onViewDetail(item.id)}
                  className="rounded text-left transition-colors hover:text-[var(--color-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
                  title={item.title}
                >
                  {item.title}
                </button>
              </h3>
            </div>
          </div>

          {/* Match Score Display / Evaluation Action */}
          <div className="shrink-0 text-right">
            {isEvaluated ? (
              <div>
                <div className={`font-mono text-[24px] font-bold leading-none tnum ${
                  isDisqualified ? 'text-rose-400' : 'text-[var(--color-primary)]'
                }`}>
                  <CountUp to={Math.round(item.match_score)} duration={0.7} />
                  <span className="text-[12px] font-normal text-[var(--color-ink-tertiary)]">%</span>
                </div>
                <div className="mt-1 flex items-center justify-end gap-1.5 text-[10px] text-[var(--color-ink-tertiary)] font-mono">
                  <span>match</span>
                  {isStale && (
                    <span className="rounded bg-amber-400/10 px-1 py-px font-mono text-[9px] text-amber-300" title="Profile updated since match evaluation">
                      stale
                    </span>
                  )}
                  {onCalculateMatch && (
                    <button
                      type="button"
                      onClick={handleCalculate}
                      disabled={calculating}
                      title="Recalculate match against latest profile"
                      className="text-[var(--color-ink-tertiary)] hover:text-[var(--color-primary)] transition-colors focus-visible:outline-none"
                      aria-label="Recalculate match score"
                    >
                      <RotateCw className={`h-2.5 w-2.5 ${calculating ? 'animate-spin text-[var(--color-primary)]' : ''}`} />
                    </button>
                  )}
                </div>
              </div>
            ) : (
              <div className="flex flex-col items-end gap-1.5">
                <span className="inline-flex items-center rounded-[var(--radius-xs)] border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-[var(--color-ink-secondary)]">
                  Unevaluated
                </span>
                {onCalculateMatch && (
                  <button
                    type="button"
                    onClick={handleCalculate}
                    disabled={calculating}
                    className="inline-flex items-center gap-1 rounded-[var(--radius-xs)] border border-[var(--color-primary)]/30 bg-[var(--color-primary)]/[0.08] px-2 py-0.5 text-[11px] font-medium text-[var(--color-primary)] transition-colors hover:bg-[var(--color-primary)]/[0.16] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] disabled:opacity-50"
                  >
                    <Sparkles className={`h-2.5 w-2.5 ${calculating ? 'animate-spin' : ''}`} aria-hidden="true" />
                    <span>{calculating ? 'Scoring…' : 'Calculate'}</span>
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Metadata Row */}
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-[var(--color-ink-secondary)]">
          <span className="inline-flex items-center gap-1.5">
            <MapPin className="h-3 w-3 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
            <span>{item.normalized_location || item.location}</span>
          </span>

          <span className="inline-flex items-center gap-1.5 capitalize">
            <span className={`h-1.5 w-1.5 rounded-full ${
              item.workplace_type === 'remote'
                ? 'bg-[var(--color-primary)]'
                : item.workplace_type === 'hybrid'
                ? 'bg-sky-400'
                : 'bg-slate-500'
            }`} aria-hidden="true" />
            <span>{item.workplace_type}</span>
          </span>

          {item.stipend_text && (
            <span className="font-mono text-[12px] text-[var(--color-ink)] font-medium">
              {item.stipend_text}
            </span>
          )}

          <span className="inline-flex items-center gap-1.5">
            <Calendar className="h-3 w-3 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
            <span>
              {deadlineInfo ? deadlineInfo.deadline_formatted : (item.deadline_at ? formatDate(item.deadline_at) : 'Rolling deadline')}
            </span>
            {deadlineInfo?.urgency === 'urgent' && (
              <span className="rounded bg-rose-400/[0.10] px-1 py-px text-[10px] font-medium text-rose-300 font-mono">
                closing soon
              </span>
            )}
          </span>

          <span className="ml-auto hidden font-mono text-[11px] text-[var(--color-ink-tertiary)] sm:inline">
            {formatRelative(item.posted_at)}
          </span>
        </div>

        {/* Match Intelligence Collapsible Drawer */}
        {(whyMatches.length > 0 || isEvaluated) && (
          <div className="mt-3 border-t border-white/[0.05] pt-2.5">
            <button
              type="button"
              onClick={() => setShowFullMatch(!showFullMatch)}
              aria-expanded={showFullMatch}
              className="inline-flex items-center gap-1.5 rounded text-[11px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:text-[var(--color-primary)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
            >
              <Sparkles className="h-3 w-3 text-[var(--color-primary)]" strokeWidth={1.75} aria-hidden="true" />
              <span>
                {showFullMatch
                  ? 'Hide match intelligence'
                  : isEvaluated
                  ? `Match Intelligence (${Math.round(item.match_score)}% compatibility)`
                  : `Why this matches${whyMatches.length > 1 ? ` (${whyMatches.length})` : ''}`}
              </span>
              {showFullMatch
                ? <ChevronUp className="h-3 w-3" aria-hidden="true" />
                : <ChevronDown className="h-3 w-3" aria-hidden="true" />}
            </button>

            {showFullMatch && (
              <div className="mt-2.5 space-y-3 rounded-[var(--radius-sm)] border border-white/[0.06] bg-black/25 p-3.5 text-[12px] animate-fadeIn">
                {/* Scoring Explanation */}
                {scoringExplanation && (
                  <p className="text-[var(--color-ink-secondary)] leading-relaxed text-[11px]">
                    {scoringExplanation}
                  </p>
                )}

                {/* Bullets */}
                {whyMatches.length > 0 && (
                  <ul className="space-y-1 pl-4 text-[var(--color-ink-secondary)] text-[11px]">
                    {whyMatches.map((bullet, idx) => (
                      <li key={idx} className="list-disc leading-relaxed">
                        {bullet}
                      </li>
                    ))}
                  </ul>
                )}

                {/* 5-Category Breakdown Bars */}
                {Object.keys(categoryScores).length > 0 && (
                  <div className="space-y-2 pt-2 border-t border-white/[0.05]">
                    <span className="text-[10px] font-semibold text-[var(--color-ink-tertiary)]">
                      5-Category Evaluation
                    </span>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 text-[11px]">
                      {Object.entries(categoryScores).map(([catKey, rawScore]) => {
                        const score = typeof rawScore === 'number' ? Math.round(rawScore) : 0;
                        const weight = categoryWeights[catKey] ? `${Math.round(categoryWeights[catKey] * 100)}%` : null;
                        const cleanLabel = catKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                        return (
                          <div key={catKey} className="space-y-1 rounded bg-white/[0.02] p-2 border border-white/[0.04]">
                            <div className="flex justify-between text-[10px] text-[var(--color-ink-secondary)]">
                              <span className="truncate">{cleanLabel}</span>
                              <span className="font-mono text-[var(--color-ink)] font-medium">
                                {score}% {weight && `(${weight})`}
                              </span>
                            </div>
                            <div className="h-1.5 w-full rounded-full bg-white/[0.06] overflow-hidden">
                              <div
                                className={`h-full rounded-full transition-colors duration-300 ${
                                  score >= 70 ? 'bg-[var(--color-primary)]' : score >= 50 ? 'bg-amber-400' : 'bg-slate-500'
                                }`}
                                style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                              />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {/* Skill Gaps & Actionable Advice */}
                {skillGaps.length > 0 && (
                  <div className="space-y-1.5 pt-2 border-t border-white/[0.05]">
                    <div className="flex items-center gap-1.5 text-[10px] font-semibold text-amber-400 ">
                      <AlertCircle className="h-3 w-3" />
                      <span>Skill Gaps & Suggestions ({skillGaps.length})</span>
                    </div>
                    <div className="space-y-1.5">
                      {skillGaps.slice(0, 2).map((gap, idx) => (
                        <div key={idx} className="rounded bg-white/[0.02] p-2 text-[11px] border border-white/[0.04]">
                          <div className="flex items-center justify-between font-medium text-[var(--color-ink)]">
                            <span>{gap.skill_name}</span>
                            <span className="rounded bg-amber-400/10 px-1 py-0.5 text-[9px] capitalize text-amber-300 font-mono">
                              {gap.priority}
                            </span>
                          </div>
                          <p className="mt-1 text-[10px] text-[var(--color-ink-secondary)] leading-relaxed">
                            {gap.suggested_learning_or_improvement}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Skills Chips */}
        {(matchingSkills.length > 0 || missingSkills.length > 0) && (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {matchingSkills.slice(0, 5).map((skill, idx) => (
              <Badge
                key={`match-${idx}`}
                variant="emerald"
                size="sm"
                icon={<Check className="h-2.5 w-2.5" strokeWidth={2.5} aria-hidden="true" />}
              >
                {skill}
              </Badge>
            ))}

            {missingSkills.slice(0, 3).map((skill, idx) => (
              <Badge
                key={`missing-${idx}`}
                variant="neutral"
                size="sm"
                dot
              >
                {skill}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Card Action Footer */}
      <div className="flex items-center justify-between gap-2 border-t border-white/[0.06] bg-white/[0.01] px-4 py-3 sm:px-5">
        <div className="flex items-center gap-2">
          <Button
            variant="primary"
            size="sm"
            onClick={() => onPrepareApply(item.id)}
            aria-label={`Prepare application for ${item.title} at ${item.company_name}`}
            leftIcon={<Send className="h-3 w-3" />}
          >
            Prepare application
          </Button>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => onViewDetail(item.id)}
            aria-label={`View full details for ${item.title} at ${item.company_name}`}
          >
            Details
          </Button>
        </div>

        <div className="relative flex items-center gap-1">
          {/* Bookmark Button */}
          <button
            type="button"
            onClick={() => onToggleSave(item.id)}
            className={`rounded-md p-2 transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] ${
              item.is_saved
                ? 'bg-amber-400/[0.10] text-amber-400'
                : 'text-[var(--color-ink-tertiary)] hover:bg-white/[0.05] hover:text-[var(--color-ink)]'
            }`}
            title={item.is_saved ? 'Remove from saved' : 'Save opportunity'}
            aria-label={item.is_saved ? `Remove ${item.title} at ${item.company_name} from saved` : `Save ${item.title} at ${item.company_name}`}
          >
            <Bookmark className={`h-4 w-4 ${item.is_saved ? 'fill-current' : ''}`} strokeWidth={1.75} aria-hidden="true" />
          </button>

          {/* More Options Dropdown Menu */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setShowMenu(prev => !prev)}
              aria-haspopup="true"
              aria-expanded={showMenu}
              aria-label={`More options for ${item.title} at ${item.company_name}`}
              className="rounded-md p-2 text-[var(--color-ink-tertiary)] transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
            >
              <MoreHorizontal className="h-4 w-4" strokeWidth={1.75} aria-hidden="true" />
            </button>

            {showMenu && (
              <>
                <div className="fixed inset-0 z-20" onClick={() => setShowMenu(false)} aria-hidden="true" />
                <div
                  role="menu"
                  className="absolute bottom-full right-0 z-30 mb-2 w-48 rounded-[var(--radius-sm)] border border-white/[0.10] bg-[var(--color-surface-raised)] p-1 shadow-overlay animate-fadeIn text-[12px]"
                >
                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setShowMenu(false);
                      onTailorResume(item.id);
                    }}
                    className="flex w-full items-center gap-2 rounded-[var(--radius-xs)] px-2.5 py-1.5 text-left text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                  >
                    <FileText className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
                    <span>Tailor resume</span>
                  </button>

                  {item.original_url && (
                    <a
                      href={item.original_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      role="menuitem"
                      onClick={() => setShowMenu(false)}
                      className="flex w-full items-center gap-2 rounded-[var(--radius-xs)] px-2.5 py-1.5 text-left text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                    >
                      <ExternalLink className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
                      <span>Original listing</span>
                    </a>
                  )}

                  <div className="my-1 h-px bg-white/[0.06]" aria-hidden="true" />

                  <button
                    type="button"
                    role="menuitem"
                    onClick={() => {
                      setShowMenu(false);
                      if (onDismissClick) {
                        onDismissClick(item);
                      } else {
                        onDismiss(item.id);
                      }
                    }}
                    className="flex w-full items-center gap-2 rounded-[var(--radius-xs)] px-2.5 py-1.5 text-left text-rose-400 transition-colors hover:bg-rose-500/10"
                  >
                    <X className="h-3.5 w-3.5" strokeWidth={1.75} aria-hidden="true" />
                    <span>Not interested</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      </div>
    </article>
  );
};
