import React, { useState, useEffect, useCallback } from 'react';
import {
  BookOpen,
  Plus,
  Sparkles,
  Calendar,
  Star,
  Trash2,
  CheckCircle2,
  HelpCircle,
  MessageSquare,
  ArrowRight,
  TrendingUp,
  AlertTriangle,
  X,
  Building,
  Briefcase,
  Target,
  Video,
  Award,
  ShieldCheck,
  ShieldAlert,
  Play,
  BarChart3,
  Tag
} from 'lucide-react';
import { InterviewJournalRecord } from '../../types';
import {
  fetchInterviews,
  createInterview,
  updateInterview,
  deleteInterview,
  analyzeInterviewAI
} from '../../services/api';

import { PageHeader, Tabs } from '../ui/PageHeader';
import { InterviewPrepTab } from './InterviewPrepTab';
import { PracticeModeView } from './PracticeModeView';
import { HistoricalAnalyticsTab } from './HistoricalAnalyticsTab';
import { OverviewTab } from './OverviewTab';

export const InterviewJournalView: React.FC = () => {
  // Navigation Tabs: 'prep' | 'practice' | 'journal' | 'analytics'
  const [activeMainTab, setActiveMainTab] = useState<'overview' | 'prep' | 'practice' | 'journal' | 'analytics'>('overview');

  // Trigger state passed into PracticeModeView when initiated from PrepTab
  const [practiceTrigger, setPracticeTrigger] = useState<{
    category: string;
    question: string;
    hint: string;
    company?: string;
    role?: string;
    oppId?: number;
  } | null>(null);

  // Journal State
  const [interviews, setInterviews] = useState<InterviewJournalRecord[]>([]);
  const [selectedEntry, setSelectedEntry] = useState<InterviewJournalRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [showAddModal, setShowAddModal] = useState(false);
  const [isDiagnosing, setIsDiagnosing] = useState(false);

  // Form State for Recording Interview
  const [formCompany, setFormCompany] = useState('');
  const [formRole, setFormRole] = useState('Software Engineering Intern');
  const [formRound, setFormRound] = useState('Technical Round 1');
  const [formType, setFormType] = useState('technical');
  const [formFormat, setFormFormat] = useState('virtual_video');
  const [formDate, setFormDate] = useState(new Date().toISOString().split('T')[0]);
  const [formTopics, setFormTopics] = useState('PostgreSQL, Python, System Design');
  const [formConfidence, setFormConfidence] = useState(4);
  const [formPerformance, setFormPerformance] = useState(4);
  const [formDifficulty, setFormDifficulty] = useState(3);
  const [formResult, setFormResult] = useState('pending');
  const [formInterviewerFeedback, setFormInterviewerFeedback] = useState('');
  const [formNotes, setFormNotes] = useState('');

  // Q&A Temp State
  const [newQuestion, setNewQuestion] = useState('');
  const [newAnswer, setNewAnswer] = useState('');
  const [newTopic, setNewTopic] = useState('');

  const loadJournalData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchInterviews({ page_size: 50 });
      setInterviews(res.items || []);
      setSelectedEntry((prev) => prev ?? (res.items && res.items.length > 0 ? res.items[0] : prev));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJournalData();
  }, [loadJournalData]);

  const handleStartPracticeFromPrep = useCallback((
    category: string,
    question: string,
    hint: string,
    company?: string,
    role?: string,
    oppId?: number
  ) => {
    setPracticeTrigger({ category, question, hint, company, role, oppId });
    setActiveMainTab('practice');
  }, []);

  const clearPracticeTrigger = useCallback(() => setPracticeTrigger(null), []);

  const handleCreateInterview = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formCompany.trim()) return;
    try {
      const topicsList = formTopics
        .split(',')
        .map(t => t.trim())
        .filter(Boolean);

      const created = await createInterview({
        company_name: formCompany.trim(),
        role: formRole.trim(),
        round_name: formRound.trim(),
        round_type: formType,
        interview_format: formFormat,
        interview_date: formDate,
        topics_covered: topicsList,
        confidence_level: formConfidence,
        performance_rating: formPerformance,
        difficulty_rating: formDifficulty,
        interview_result: formResult,
        interviewer_feedback: formInterviewerFeedback.trim() || undefined,
        personal_notes: formNotes.trim() || undefined,
        notes: formNotes.trim() || undefined,
        scheduled_at: formDate ? new Date(formDate).toISOString() : new Date().toISOString()
      });

      setInterviews([created, ...interviews]);
      setSelectedEntry(created);
      setShowAddModal(false);
      // Reset form
      setFormCompany('');
      setFormInterviewerFeedback('');
      setFormNotes('');
    } catch (err) {
      console.error(err);
      alert('Failed to save interview record.');
    }
  };

  const handleAddQuestion = async () => {
    if (!selectedEntry || !newQuestion.trim()) return;
    const updatedQuestions = [
      ...(selectedEntry.questions_asked || []),
      {
        question: newQuestion.trim(),
        user_answer: newAnswer.trim(),
        topic: newTopic.trim() || undefined
      }
    ];
    try {
      const updated = await updateInterview(selectedEntry.id, { questions_asked: updatedQuestions });
      setSelectedEntry(updated);
      setInterviews(interviews.map(i => i.id === updated.id ? updated : i));
      setNewQuestion('');
      setNewAnswer('');
      setNewTopic('');
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunAiAnalysis = async () => {
    if (!selectedEntry) return;
    setIsDiagnosing(true);
    try {
      const feedback = await analyzeInterviewAI(selectedEntry.id);
      const updated = { ...selectedEntry, ai_feedback: feedback };
      setSelectedEntry(updated);
      setInterviews(interviews.map(i => i.id === updated.id ? updated : i));
    } catch (err) {
      console.error(err);
      alert('AI analysis failed. Please verify Ollama is accessible.');
    } finally {
      setIsDiagnosing(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this interview journal entry?')) return;
    try {
      await deleteInterview(id);
      const remaining = interviews.filter(i => i.id !== id);
      setInterviews(remaining);
      if (selectedEntry?.id === id) {
        setSelectedEntry(remaining.length > 0 ? remaining[0] : null);
      }
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Practice"
        title="Interviews"
        description="Role-tailored preparation, mock practice, debriefs and honest analytics from your recorded rounds."
      />

      <Tabs
        ariaLabel="Interview modules"
        variant="segmented"
        active={activeMainTab}
        onChange={(id) => setActiveMainTab(id as typeof activeMainTab)}
        items={[
          { id: 'overview', label: 'Overview', icon: <Target className="h-3.5 w-3.5" /> },
          { id: 'prep', label: 'Preparation resources', icon: <Sparkles className="h-3.5 w-3.5" /> },
          { id: 'practice', label: 'Question practice', icon: <Play className="h-3.5 w-3.5" /> },
          { id: 'journal', label: 'Interview journal', icon: <BookOpen className="h-3.5 w-3.5" /> },
          { id: 'analytics', label: 'Analytics', icon: <BarChart3 className="h-3.5 w-3.5" /> },
        ]}
      />

      {/* 1. Overview Module */}
      {activeMainTab === 'overview' && (
        <OverviewTab
          onNavigateToPractice={() => setActiveMainTab('practice')}
          onNavigateToJournal={() => setActiveMainTab('journal')}
          onNavigateToPreparation={() => setActiveMainTab('prep')}
        />
      )}

      {/* 2. Preparation Module */}
      {activeMainTab === 'prep' && (
        <InterviewPrepTab onStartPractice={handleStartPracticeFromPrep} />
      )}

      {/* 3. Practice Simulator Module */}
      {activeMainTab === 'practice' && (
        <PracticeModeView
          initialPrepTrigger={practiceTrigger}
          onClearInitialTrigger={clearPracticeTrigger}
        />
      )}

      {/* 4. Interview Journal Module */}
      {activeMainTab === 'journal' && (
        <div className="space-y-6">
          {/* Header Action */}
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div className="text-[12px] text-slate-400">
              Record interview questions, interviewer feedback, topics covered, and self-ratings.
            </div>

            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-md bg-emerald-400 px-3 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300"
            >
              <Plus className="w-4 h-4" />
              <span>Record Interview Round</span>
            </button>
          </div>

          {interviews.length === 0 ? (
            <div className="rounded-xl border border-dashed border-white/[0.09] bg-white/[0.01] p-10 text-center space-y-3">
              <BookOpen className="mx-auto h-8 w-8 text-slate-600" />
              <h4 className="text-[13px] font-medium text-[var(--color-ink)]">No interview rounds recorded yet</h4>
              <p className="mx-auto max-w-sm text-[12px] leading-relaxed text-slate-500">
                Log your technical, behavioral, or system design interviews to track performance and discover recurring topic trends.
              </p>
              <button
                onClick={() => setShowAddModal(true)}
                className="mt-2 inline-flex min-h-[32px] items-center gap-1.5 rounded-md bg-emerald-400 px-3 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300"
              >
                <Plus className="w-4 h-4" />
                <span>Record First Interview</span>
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Entries Sidebar (4 cols) */}
              <div className="lg:col-span-4 space-y-3">
                {interviews.map((item) => {
                  const active = selectedEntry?.id === item.id;
                  const res = (item.interview_result || 'pending').toLowerCase();
                  return (
                    <div
                      key={item.id}
                      onClick={() => setSelectedEntry(item)}
                      className={`cursor-pointer rounded-xl border p-3.5 space-y-2 transition-colors ${
                        active
                          ? 'border-emerald-400/40 bg-emerald-400/[0.03]'
                          : 'border-white/[0.07] bg-[var(--color-paper)] hover:border-white/[0.13]'
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className="text-[13px] font-medium text-[var(--color-ink)]">{item.company_name}</span>
                            <span className="text-slate-600">•</span>
                            <span className="text-[11px] text-slate-400">{item.role || 'Intern'}</span>
                          </div>
                          <span className="mt-0.5 block text-[11px] text-slate-500">{item.round_name}</span>
                        </div>

                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold  ${
                          res === 'offer' ? 'border border-emerald-400/25 bg-emerald-400/[0.08] text-emerald-300' :
                          res === 'passed' ? 'border border-emerald-400/20 bg-emerald-400/[0.05] text-emerald-300/90' :
                          res === 'rejected' ? 'border border-rose-400/25 bg-rose-400/[0.08] text-rose-300' :
                          'border border-white/[0.08] bg-white/[0.03] text-slate-400'
                        }`}>
                          {item.interview_result || 'Pending'}
                        </span>
                      </div>

                      {/* Format and Date */}
                      <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-500">
                        <span className="capitalize">{item.round_type}</span>
                        <span>•</span>
                        <span className="capitalize">{item.interview_format?.replace('_', ' ') || 'Virtual'}</span>
                        {item.interview_date && (
                          <>
                            <span>•</span>
                            <span>{item.interview_date}</span>
                          </>
                        )}
                      </div>

                      {/* Ratings and count */}
                      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-500">
                        <div className="flex items-center space-x-1 text-amber-400 font-semibold">
                          <Star className="w-3 h-3 fill-current" />
                          <span>{item.performance_rating}/5</span>
                        </div>
                        <span>{item.questions_asked?.length || 0} questions logged</span>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Deep Dive Panel (8 cols) */}
              {selectedEntry && (
                <div className="space-y-5 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5 lg:col-span-8">
                  {/* Header Bar */}
                  <div className="flex items-start justify-between border-b border-slate-800 pb-4">
                    <div>
                      <div className="flex items-center space-x-2 text-xs">
                        <span className="font-bold text-emerald-400 ">{selectedEntry.company_name}</span>
                        <span className="text-slate-600">•</span>
                        <span className="text-slate-300">{selectedEntry.role || 'Intern'}</span>
                        <span className="text-slate-600">•</span>
                        <span className="capitalize text-slate-400">{selectedEntry.interview_format?.replace('_', ' ') || 'Virtual Video'}</span>
                      </div>
                      <h3 className="text-lg font-bold text-[var(--color-ink)] mt-1">{selectedEntry.round_name}</h3>
                      {selectedEntry.interview_date && (
                        <span className="text-xs text-slate-500 flex items-center space-x-1 mt-0.5">
                          <Calendar className="w-3.5 h-3.5" />
                          <span>Interview Date: {selectedEntry.interview_date}</span>
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-2">
                      <button
                        onClick={handleRunAiAnalysis}
                        disabled={isDiagnosing}
                        className="inline-flex min-h-[28px] items-center gap-1.5 rounded-md border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <Sparkles className={`w-3.5 h-3.5 ${isDiagnosing ? 'animate-spin' : ''}`} />
                        <span>{isDiagnosing ? 'Diagnosing...' : 'AI Performance Diagnosis'}</span>
                      </button>

                      <button
                        onClick={() => handleDelete(selectedEntry.id)}
                        className="rounded p-1.5 text-slate-500 transition-colors hover:bg-white/[0.05] hover:text-rose-400"
                        title="Delete entry"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>

                  {/* Badges & Metrics Bar */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                    <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5">
                      <span className="field-label block">Round result</span>
                      <span className="text-[13px] font-medium capitalize text-[var(--color-ink)]">{selectedEntry.interview_result || 'Pending'}</span>
                    </div>
                    <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5">
                      <span className="field-label block">Confidence level</span>
                      <span className="font-mono text-[13px] font-medium text-slate-200 tnum">{selectedEntry.confidence_level || 3} / 5</span>
                    </div>
                    <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5">
                      <span className="field-label block">Self performance</span>
                      <span className="font-mono text-[13px] font-medium text-slate-200 tnum">{selectedEntry.performance_rating} / 5</span>
                    </div>
                    <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5">
                      <span className="field-label block">Difficulty level</span>
                      <span className="font-mono text-[13px] font-medium text-slate-200 tnum">{selectedEntry.difficulty_rating} / 5</span>
                    </div>
                  </div>

                  {/* Topics Covered */}
                  {selectedEntry.topics_covered && selectedEntry.topics_covered.length > 0 && (
                    <div className="space-y-1.5">
                      <span className="block text-[10px] font-medium text-slate-500">
                        Topics Covered in Round:
                      </span>
                      <div className="flex flex-wrap gap-1.5">
                        {selectedEntry.topics_covered.map((t, i) => (
                          <span key={i} className="flex items-center gap-1 rounded border border-white/[0.07] bg-white/[0.03] px-1.5 py-0.5 text-[11px] text-slate-300">
                            <Tag className="h-2.5 w-2.5 text-slate-500" />
                            <span>{t}</span>
                          </span>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Clear separation: Actual Interviewer Feedback vs Personal Notes */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {/* Actual Interviewer Feedback (Employer) */}
                    <div className="space-y-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5">
                      <div className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
                        <Building className="h-3.5 w-3.5 text-slate-500" />
                        <span>Actual Interviewer Feedback</span>
                      </div>
                      <p className="text-[12px] italic leading-relaxed text-slate-400">
                        {selectedEntry.interviewer_feedback || (
                          <span className="text-slate-500 not-italic">No feedback received from the employer interviewer yet.</span>
                        )}
                      </p>
                    </div>

                    {/* Personal Reflection Notes */}
                    <div className="space-y-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5">
                      <div className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
                        <Briefcase className="h-3.5 w-3.5 text-slate-500" />
                        <span>Personal Notes & Self-Debrief</span>
                      </div>
                      <p className="text-[12px] leading-relaxed text-slate-400">
                        {selectedEntry.personal_notes || selectedEntry.notes || (
                          <span className="text-slate-500">No personal reflection notes recorded for this round.</span>
                        )}
                      </p>
                    </div>
                  </div>

                  {/* AI Diagnostic Report if available */}
                  {selectedEntry.ai_feedback && (
                    <div className="space-y-3 rounded-lg border border-white/[0.07] bg-[var(--color-paper-2)] p-4">
                      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                        <div className="flex items-center gap-2 text-[10px] font-medium text-slate-300">
                          <Sparkles className="h-3.5 w-3.5 text-emerald-400/80" aria-hidden="true" />
                          <span>AI Interview Performance Diagnosis</span>
                        </div>
                        <span className="text-[10px] text-slate-500">AI-Generated Assessment</span>
                      </div>

                      {selectedEntry.ai_feedback.summary && (
                        <p className="text-[12px] leading-relaxed text-slate-400">
                          {selectedEntry.ai_feedback.summary}
                        </p>
                      )}

                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 pt-1">
                        <div className="rounded-md border border-white/[0.06] bg-white/[0.02] p-3">
                          <span className="mb-1.5 block text-[10px] font-medium text-slate-400">Demonstrated Strengths</span>
                          <ul className="space-y-1 list-disc list-inside text-xs text-slate-300">
                            {selectedEntry.ai_feedback.strengths?.map((s, idx) => (
                              <li key={idx}>{s}</li>
                            ))}
                          </ul>
                        </div>

                        <div className="rounded-md border border-white/[0.06] bg-white/[0.02] p-3">
                          <span className="mb-1.5 block text-[10px] font-medium text-amber-300/90">Action Items & Next Focus</span>
                          <ul className="space-y-1 list-disc list-inside text-xs text-slate-300">
                            {selectedEntry.ai_feedback.action_items?.map((a, idx) => (
                              <li key={idx}>{a}</li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Questions & Answers Section */}
                  <div className="space-y-4">
                    <span className="block text-[10px] font-medium text-slate-400">
                      Questions Asked & Your Responses
                    </span>

                    <div className="space-y-2.5">
                      {selectedEntry.questions_asked && selectedEntry.questions_asked.map((q, idx) => (
                        <div key={idx} className="space-y-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5">
                          <div className="flex items-center justify-between text-[12px] font-medium text-[var(--color-ink)]">
                            <div className="flex items-center space-x-2">
                              <span className="flex h-5 w-5 items-center justify-center rounded bg-white/[0.05] font-mono text-[10px] text-slate-400">
                                Q{idx + 1}
                              </span>
                              <span>{q.question}</span>
                            </div>
                            {q.topic && (
                              <span className="rounded border border-white/[0.07] bg-white/[0.03] px-1.5 py-0.5 text-[10px] text-slate-400">
                                {q.topic}
                              </span>
                            )}
                          </div>
                          {q.user_answer && (
                            <p className="pl-7 text-[12px] leading-relaxed text-slate-500">
                              <span className="font-medium text-slate-300">Your response: </span>
                              {q.user_answer}
                            </p>
                          )}
                        </div>
                      ))}

                      {(!selectedEntry.questions_asked || selectedEntry.questions_asked.length === 0) && (
                        <p className="text-xs text-slate-500">No questions recorded yet for this round.</p>
                      )}
                    </div>

                    {/* Add Question Subform */}
                    <div className="space-y-3 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5">
                      <span className="block text-[10px] font-medium text-slate-400">Log New Question to this Round</span>
                      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                        <input
                          type="text"
                          placeholder="Question asked by interviewer..."
                          value={newQuestion}
                          onChange={e => setNewQuestion(e.target.value)}
                          className="sm:col-span-2 p-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-[var(--color-ink)] placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                        />
                        <input
                          type="text"
                          placeholder="Topic (e.g. Postgres, Async)..."
                          value={newTopic}
                          onChange={e => setNewTopic(e.target.value)}
                          className="p-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-[var(--color-ink)] placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                        />
                      </div>
                      <textarea
                        rows={2}
                        placeholder="Brief summary of your response or approach..."
                        value={newAnswer}
                        onChange={e => setNewAnswer(e.target.value)}
                        className="w-full p-2 rounded-lg bg-slate-900 border border-slate-700 text-xs text-[var(--color-ink)] placeholder:text-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500"
                      />
                      <button
                        onClick={handleAddQuestion}
                        disabled={!newQuestion.trim()}
                        className="px-3.5 py-1.5 rounded-lg bg-emerald-400 hover:bg-emerald-300 disabled:opacity-40 text-[var(--color-accent-ink)] text-xs font-semibold transition"
                      >
                        Add Question to Log
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* 5. AI Analytics Module */}
      {activeMainTab === 'analytics' && (
        <HistoricalAnalyticsTab
          onGoToJournal={() => {
            setActiveMainTab('journal');
            setShowAddModal(true);
          }}
          onGoToPractice={() => setActiveMainTab('practice')}
        />
      )}

      {/* Record Interview Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-xl p-6 space-y-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="text-base font-bold text-[var(--color-ink)] flex items-center space-x-2">
                <Plus className="w-4 h-4 text-emerald-400" />
                <span>Record Interview Round</span>
              </h3>
              <button onClick={() => setShowAddModal(false)} className="text-slate-400 hover:text-[var(--color-ink)]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleCreateInterview} className="space-y-3.5 text-xs">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Company Name</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Stripe, Google, Databricks..."
                    value={formCompany}
                    onChange={e => setFormCompany(e.target.value)}
                    className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Role Title</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Backend Engineering Intern"
                    value={formRole}
                    onChange={e => setFormRole(e.target.value)}
                    className="w-full p-2.5 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none focus:ring-2 focus:ring-emerald-500"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Round Name</label>
                  <input
                    type="text"
                    value={formRound}
                    onChange={e => setFormRound(e.target.value)}
                    className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Round Type</label>
                  <select
                    value={formType}
                    onChange={e => setFormType(e.target.value)}
                    className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none"
                  >
                    <option value="technical">Technical</option>
                    <option value="system_design">System Design</option>
                    <option value="behavioral">Behavioral</option>
                    <option value="screening">Screening</option>
                    <option value="take_home">Take Home</option>
                    <option value="hr">HR</option>
                  </select>
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Format</label>
                  <select
                    value={formFormat}
                    onChange={e => setFormFormat(e.target.value)}
                    className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none"
                  >
                    <option value="virtual_video">Virtual Video</option>
                    <option value="in_person">In Person</option>
                    <option value="phone_screen">Phone Screen</option>
                    <option value="take_home">Take Home</option>
                    <option value="online_assessment">Online Assessment</option>
                  </select>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Interview Date</label>
                  <input
                    type="date"
                    value={formDate}
                    onChange={e => setFormDate(e.target.value)}
                    className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">Round Result</label>
                  <select
                    value={formResult}
                    onChange={e => setFormResult(e.target.value)}
                    className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none"
                  >
                    <option value="pending">Pending Decision</option>
                    <option value="passed">Passed Round</option>
                    <option value="offer">Offer Extended</option>
                    <option value="rejected">Rejected</option>
                    <option value="withdrawn">Withdrawn</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Topics Covered (comma separated)</label>
                <input
                  type="text"
                  placeholder="e.g. Distributed Caching, Python Async, B-Tree Indexing"
                  value={formTopics}
                  onChange={e => setFormTopics(e.target.value)}
                  className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Confidence ({formConfidence}/5)
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={formConfidence}
                    onChange={e => setFormConfidence(Number(e.target.value))}
                    className="w-full accent-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Performance ({formPerformance}/5)
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={formPerformance}
                    onChange={e => setFormPerformance(Number(e.target.value))}
                    className="w-full accent-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-slate-300 font-semibold mb-1">
                    Difficulty ({formDifficulty}/5)
                  </label>
                  <input
                    type="range"
                    min="1"
                    max="5"
                    value={formDifficulty}
                    onChange={e => setFormDifficulty(Number(e.target.value))}
                    className="w-full accent-amber-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">
                  Actual Interviewer Feedback (From Company)
                </label>
                <textarea
                  placeholder="What did the interviewer directly say about your solution, communication, or code structure?"
                  value={formInterviewerFeedback}
                  onChange={e => setFormInterviewerFeedback(e.target.value)}
                  className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] h-16 resize-none focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-slate-300 font-semibold mb-1">Personal Reflection & Notes</label>
                <textarea
                  placeholder="Your personal impressions, what you felt comfortable with, questions you hesitated on..."
                  value={formNotes}
                  onChange={e => setFormNotes(e.target.value)}
                  className="w-full p-2 rounded-lg bg-slate-950 border border-slate-700 text-[var(--color-ink)] h-16 resize-none focus:outline-none"
                />
              </div>

              <div className="flex justify-end space-x-2 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 rounded-lg bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] font-semibold"
                >
                  Save Interview Record
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
