import React, { useState, useEffect } from 'react';
import {
  Code,
  Binary,
  Layers,
  Users,
  Compass,
  Building,
  Sparkles,
  Play,
  CheckCircle2,
  AlertCircle,
  Lightbulb,
  ExternalLink,
  ChevronRight,
  ShieldCheck,
  RefreshCw
} from 'lucide-react';
import { InterviewPrepPack, OpportunityItem } from '../../types';
import { fetchInterviewPrep, fetchOpportunities } from '../../services/api';

interface InterviewPrepTabProps {
  onStartPractice?: (category: string, question: string, hint: string, company?: string, role?: string, oppId?: number) => void;
}

export const InterviewPrepTab: React.FC<InterviewPrepTabProps> = ({ onStartPractice }) => {
  const [opportunities, setOpportunities] = useState<OpportunityItem[]>([]);
  const [selectedOppId, setSelectedOppId] = useState<number | null>(null);
  const [prepPack, setPrepPack] = useState<InterviewPrepPack | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeSubTab, setActiveSubTab] = useState<'technical' | 'dsa' | 'projects' | 'behavioral' | 'hr' | 'company'>('technical');
  const [error, setError] = useState<string | null>(null);

  // Load opportunities for the dropdown
  useEffect(() => {
    async function initOpps() {
      try {
        const res = await fetchOpportunities({ page: 1, pageSize: 20 });
        if (res.items && res.items.length > 0) {
          setOpportunities(res.items);
          setSelectedOppId(res.items[0].id);
        }
      } catch (e: any) {
        // Aborting on exit/navigation is not a failure — only surface genuine errors.
        if (e?.name !== 'AbortError') console.error('Failed to load opportunities for prep', e);
      }
    }
    initOpps();
  }, []);

  // Fetch prep when selectedOppId changes
  useEffect(() => {
    if (!selectedOppId) return;
    loadPrep(selectedOppId);
  }, [selectedOppId]);

  const loadPrep = async (oppId: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInterviewPrep(oppId);
      setPrepPack(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to generate interview preparation materials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header & Opportunity Selector */}
      <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/[0.08] bg-white/[0.03] text-slate-400">
                <Sparkles className="h-4 w-4" aria-hidden="true" />
              </span>
              <div>
                <h3 className="text-[15px] font-semibold text-[var(--color-ink)]">Role-Specific Interview Preparation</h3>
                <p className="text-xs text-slate-400">
                  Targeted questions, STAR behavioral frameworks, and candidate project deep-dives tailored to the job description.
                </p>
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <div className="text-xs text-slate-400 font-medium">Select Target Opportunity:</div>
            <select
              value={selectedOppId || ''}
              onChange={(e) => setSelectedOppId(Number(e.target.value))}
              className="input-base max-w-xs"
            >
              {opportunities.map((opp) => (
                <option key={opp.id} value={opp.id}>
                  {opp.company_name} - {opp.title}
                </option>
              ))}
            </select>

            <button
              onClick={() => selectedOppId && loadPrep(selectedOppId)}
              disabled={loading || !selectedOppId}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-md border border-white/[0.09] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
              title="Regenerate Preparation Pack"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
              <span className="hidden sm:inline">Refresh</span>
            </button>
          </div>
        </div>

        {prepPack && (
          <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-4 text-[12px] text-slate-400">
            <div className="flex items-center space-x-2">
              <Building className="h-3.5 w-3.5 text-slate-500" />
              <span className="font-semibold text-slate-200">{prepPack.company_name}</span>
              <span className="text-slate-600">•</span>
              <span className="text-emerald-300">{prepPack.role_title}</span>
            </div>
            <div className="flex items-center space-x-1.5 text-slate-400">
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400/80" />
              <span>Anchored to your verified Candidate Profile</span>
            </div>
          </div>
        )}
      </div>

      {loading && (
        <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-12 text-center space-y-3">
          <RefreshCw className="w-8 h-8 text-emerald-400 animate-spin mx-auto" />
          <div className="text-sm font-semibold text-slate-200">Synthesizing Role Interview Prep...</div>
          <div className="text-xs text-slate-500 max-w-md mx-auto">
            Extracting tech stack requirements, mapping candidate projects, and formulating STAR framework questions.
          </div>
        </div>
      )}

      {error && !loading && (
        <div className="p-4 bg-rose-950/40 border border-rose-800/60 rounded-xl text-rose-300 text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {!loading && prepPack && (
        <div className="space-y-6">
          {/* Sub Navigation Tabs */}
          <div className="flex flex-wrap items-center gap-2 border-b border-white/[0.06] pb-2">
            {[
              { id: 'technical', label: 'Technical & Architecture', icon: Code, count: prepPack.technical_questions.length },
              { id: 'dsa', label: 'DSA & Algorithms', icon: Binary, count: prepPack.dsa_questions.length },
              { id: 'projects', label: 'Project Deep Dives', icon: Layers, count: prepPack.project_questions.length },
              { id: 'behavioral', label: 'Behavioral (STAR)', icon: Users, count: prepPack.behavioral_questions.length },
              { id: 'hr', label: 'HR & Motivation', icon: Compass, count: prepPack.hr_questions.length },
              { id: 'company', label: 'Company & Culture', icon: Building, count: prepPack.company_topics.length },
            ].map(tab => {
              const Icon = tab.icon;
              const active = activeSubTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveSubTab(tab.id as any)}
                  className={`inline-flex min-h-[32px] items-center gap-1.5 rounded-md px-2.5 text-[12px] font-medium transition-colors ${
                    active
                      ? 'bg-white/[0.08] text-[var(--color-ink)]'
                      : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200 border border-white/[0.07]'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{tab.label}</span>
                  <span className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${active ? 'bg-white/[0.06] text-emerald-300' : 'bg-white/[0.04] text-slate-500'}`}>
                    {tab.count}
                  </span>
                </button>
              );
            })}
          </div>

          {/* 1. Technical Questions */}
          {activeSubTab === 'technical' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>Core architectural and stack mastery questions tailored to role requirements.</span>
                <span className="text-emerald-400 font-medium">Click "Practice in Simulator" to test your response.</span>
              </div>
              <div className="grid grid-cols-1 gap-4">
                {prepPack.technical_questions.map((q) => (
                  <div key={q.id} className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13] space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="rounded border border-emerald-400/20 bg-emerald-400/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
                            {q.topic}
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            q.difficulty === 'Hard' ? 'border border-rose-400/25 bg-rose-400/[0.08] text-rose-300' : 'border border-amber-400/25 bg-amber-400/[0.08] text-amber-300'
                          }`}>
                            {q.difficulty}
                          </span>
                        </div>
                        <h4 className="text-sm font-semibold text-gray-100 leading-snug pt-1">
                          {q.question}
                        </h4>
                      </div>

                      <button
                        onClick={() => onStartPractice?.(
                          'technical',
                          q.question,
                          `Expected concepts to cover: ${q.expected_concepts.join(', ')}`,
                          prepPack.company_name,
                          prepPack.role_title,
                          prepPack.opportunity_id
                        )}
                        className="inline-flex min-h-[28px] shrink-0 items-center gap-1.5 rounded-md border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Play className="w-3 h-3" />
                        <span>Practice in Simulator</span>
                      </button>
                    </div>

                    <div className="rounded-md border border-white/[0.05] bg-[var(--color-paper-2)] p-3">
                      <div className="mb-1.5 flex items-center gap-1 text-[10px] font-medium text-slate-500">
                        <Lightbulb className="w-3 h-3 text-amber-400" />
                        <span>Key Concepts to Articulate</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {q.expected_concepts.map((concept, i) => (
                          <span key={i} className="rounded border border-white/[0.07] bg-white/[0.03] px-1.5 py-0.5 text-[11px] text-slate-300">
                            {concept}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 2. DSA Questions */}
          {activeSubTab === 'dsa' && (
            <div className="space-y-4">
              <div className="text-xs text-slate-400">
                Algorithmic problem patterns directly applicable to backend latency, scheduling, and streaming systems.
              </div>
              <div className="grid grid-cols-1 gap-4">
                {prepPack.dsa_questions.map((dsa) => (
                  <div key={dsa.id} className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13] space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="rounded border border-white/[0.07] bg-white/[0.03] px-1.5 py-0.5 text-[10px] font-medium text-slate-300">
                            {dsa.category}
                          </span>
                          <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                            dsa.difficulty === 'Hard' ? 'border border-rose-400/25 bg-rose-400/[0.08] text-rose-300' : 'border border-amber-400/25 bg-amber-400/[0.08] text-amber-300'
                          }`}>
                            {dsa.difficulty}
                          </span>
                          <span className="text-xs font-semibold text-slate-200">
                            {dsa.title}
                          </span>
                        </div>
                        <h4 className="text-sm font-semibold text-gray-100 leading-snug pt-2">
                          {dsa.question}
                        </h4>
                      </div>

                      <button
                        onClick={() => onStartPractice?.(
                          'dsa',
                          dsa.question,
                          `Pattern: ${dsa.pattern}. Relevance: ${dsa.relevance}`,
                          prepPack.company_name,
                          prepPack.role_title,
                          prepPack.opportunity_id
                        )}
                        className="inline-flex min-h-[28px] shrink-0 items-center gap-1.5 rounded-md border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Play className="w-3 h-3" />
                        <span>Practice in Simulator</span>
                      </button>
                    </div>

                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                      <div className="rounded-md border border-white/[0.05] bg-[var(--color-paper-2)] p-2.5">
                        <span className="block text-[10px] font-medium text-slate-500 mb-1">Algorithmic Pattern:</span>
                        <span className="text-emerald-300 font-mono text-[11px]">{dsa.pattern}</span>
                      </div>
                      <div className="rounded-md border border-white/[0.05] bg-[var(--color-paper-2)] p-2.5">
                        <span className="block text-[10px] font-medium text-slate-500 mb-1">Role Relevance:</span>
                        <span className="text-slate-300">{dsa.relevance}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 3. Project-Based Questions */}
          {activeSubTab === 'projects' && (
            <div className="space-y-4">
              <div className="flex items-center space-x-2 text-xs text-emerald-400 bg-emerald-950/30 border border-emerald-800/40 p-3 rounded-lg">
                <ShieldCheck className="w-4 h-4 flex-shrink-0" />
                <span>
                  Strictly grounded in your Candidate Profile projects. Interviewers will interrogate architectural bottlenecks and validation benchmarks.
                </span>
              </div>
              <div className="grid grid-cols-1 gap-4">
                {prepPack.project_questions.map((proj) => (
                  <div key={proj.id} className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13] space-y-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center space-x-2">
                          <span className="px-2.5 py-0.5 rounded text-[10px] font-bold  bg-blue-950/80 text-blue-300 border border-blue-800/50">
                            Project: {proj.project_name}
                          </span>
                          <span className="text-xs text-slate-400 font-mono">
                            [{proj.tech_stack}]
                          </span>
                        </div>
                        <h4 className="text-sm font-semibold text-gray-100 leading-snug pt-2">
                          {proj.question}
                        </h4>
                      </div>

                      <button
                        onClick={() => onStartPractice?.(
                          'projects',
                          proj.question,
                          `Focus areas: ${proj.focus_areas.join(', ')}. Evidence: ${proj.candidate_evidence}`,
                          prepPack.company_name,
                          prepPack.role_title,
                          prepPack.opportunity_id
                        )}
                        className="inline-flex min-h-[28px] shrink-0 items-center gap-1.5 rounded-md border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Play className="w-3 h-3" />
                        <span>Practice in Simulator</span>
                      </button>
                    </div>

                    <div className="space-y-2">
                      <div className="text-[10px] font-medium text-slate-500">
                        Key Discussion Focus Areas:
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        {proj.focus_areas.map((area, i) => (
                          <div key={i} className="flex items-start gap-1.5 rounded border border-white/[0.05] bg-[var(--color-paper-2)] p-2 text-[11px] text-slate-300">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 flex-shrink-0 mt-0.5" />
                            <span>{area}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {proj.candidate_evidence && (
                      <div className="rounded-md border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5 text-[11px] italic text-slate-500">
                        <span className="text-slate-300 font-medium not-italic">Profile Evidence: </span>
                        "{proj.candidate_evidence}"
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 4. Behavioral Questions (STAR Method) */}
          {activeSubTab === 'behavioral' && (
            <div className="space-y-4">
              <div className="text-xs text-slate-400">
                Behavioral questions structured around the STAR method (Situation, Task, Action, Result).
              </div>
              <div className="grid grid-cols-1 gap-4">
                {prepPack.behavioral_questions.map((b) => (
                  <div key={b.id} className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13] space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="px-2 py-0.5 rounded text-[10px] font-bold  bg-amber-950/80 text-amber-300 border border-amber-800/50">
                          {b.competency}
                        </span>
                        <h4 className="text-sm font-semibold text-gray-100 leading-snug pt-2">
                          {b.question}
                        </h4>
                      </div>

                      <button
                        onClick={() => onStartPractice?.(
                          'behavioral',
                          b.question,
                          `STAR Framework: ${b.star_framework}`,
                          prepPack.company_name,
                          prepPack.role_title,
                          prepPack.opportunity_id
                        )}
                        className="inline-flex min-h-[28px] shrink-0 items-center gap-1.5 rounded-md border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Play className="w-3 h-3" />
                        <span>Practice in Simulator</span>
                      </button>
                    </div>

                    <div className="rounded-md border border-white/[0.05] bg-[var(--color-paper-2)] p-3 text-[12px] text-slate-300">
                      <div className="mb-1 flex items-center gap-1 text-[10px] font-medium text-slate-500">
                        <Users className="w-3 h-3 text-amber-400" />
                        <span>STAR Sequence Guide</span>
                      </div>
                      <p className="rounded border border-white/[0.06] bg-[var(--color-paper-2)] p-2 font-mono text-[11px] text-slate-300">
                        {b.star_framework}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 5. HR Questions */}
          {activeSubTab === 'hr' && (
            <div className="space-y-4">
              <div className="text-xs text-slate-400">
                Logistics, team collaboration, motivation, and career roadmap questions.
              </div>
              <div className="grid grid-cols-1 gap-4">
                {prepPack.hr_questions.map((hr) => (
                  <div key={hr.id} className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13] space-y-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <span className="rounded border border-teal-400/20 bg-teal-400/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-teal-300">
                          {hr.topic}
                        </span>
                        <h4 className="text-sm font-semibold text-gray-100 leading-snug pt-2">
                          {hr.question}
                        </h4>
                      </div>

                      <button
                        onClick={() => onStartPractice?.(
                          'hr',
                          hr.question,
                          `Recommended Angle: ${hr.recommended_angle}`,
                          prepPack.company_name,
                          prepPack.role_title,
                          prepPack.opportunity_id
                        )}
                        className="inline-flex min-h-[28px] shrink-0 items-center gap-1.5 rounded-md border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Play className="w-3 h-3" />
                        <span>Practice in Simulator</span>
                      </button>
                    </div>

                    <div className="rounded-md border border-white/[0.05] bg-[var(--color-paper-2)] p-3 text-[12px]">
                      <span className="block text-[10px] font-medium text-slate-500 mb-1">Recommended Response Strategy:</span>
                      <p className="text-slate-300">{hr.recommended_angle}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 6. Company & Role Research */}
          {activeSubTab === 'company' && (
            <div className="space-y-4">
              <div className="text-xs text-slate-400">
                Research targets, system design scope, and reverse interview questions to ask hiring managers.
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {prepPack.company_topics.map((item) => (
                  <div key={item.id} className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13] space-y-3">
                    <div className="flex items-center space-x-2">
                      <Building className="h-3.5 w-3.5 text-slate-500" />
                      <h4 className="text-sm font-semibold text-[var(--color-ink)]">{item.title}</h4>
                    </div>
                    <p className="text-xs text-slate-300 leading-relaxed">
                      {item.description}
                    </p>
                    <div className="rounded-md border border-white/[0.05] bg-[var(--color-paper-2)] p-2.5 text-[12px]">
                      <span className="text-emerald-400 font-semibold block text-[11px] mb-1">Proactive Action Item:</span>
                      <p className="text-slate-300">{item.action_item}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
