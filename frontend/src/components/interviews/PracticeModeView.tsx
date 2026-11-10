import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Play,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Star,
  Sparkles,
  ArrowRight,
  ArrowLeft,
  RefreshCw,
  Plus,
  Clock,
  ShieldAlert,
  Award,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  BookOpen,
  Mic,
  MicOff,
  Square,
  Radio,
  Volume2
} from 'lucide-react';
import { PracticeSessionItem, PracticeQuestionItem } from '../../types';
import {
  fetchPracticeSessions,
  createPracticeSession,
  fetchPracticeSessionDetail,
  evaluatePracticeQuestion,
  completePracticeSession,
  fetchOpportunities
} from '../../services/api';

interface PracticeModeViewProps {
  initialPrepTrigger?: {
    category: string;
    question: string;
    hint: string;
    company?: string;
    role?: string;
    oppId?: number;
  } | null;
  onClearInitialTrigger?: () => void;
}

export const PracticeModeView: React.FC<PracticeModeViewProps> = ({
  initialPrepTrigger,
  onClearInitialTrigger
}) => {
  const [sessions, setSessions] = useState<PracticeSessionItem[]>([]);
  const [currentSession, setCurrentSession] = useState<PracticeSessionItem | null>(null);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [userAnswer, setUserAnswer] = useState('');
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [loadingSessions, setLoadingSessions] = useState(true);
  const [showNewModal, setShowNewModal] = useState(false);
  const [showHint, setShowHint] = useState(false);

  // Audio Mode State & Speech Recognition
  const [responseMode, setResponseMode] = useState<'text' | 'audio'>('text');
  const [isRecording, setIsRecording] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [micPermission, setMicPermission] = useState<'prompt' | 'granted' | 'denied' | 'unsupported'>('prompt');
  const recognitionRef = React.useRef<any>(null);
  const timerRef = React.useRef<any>(null);

  useEffect(() => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setMicPermission('unsupported');
    }
    return () => {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (_) {}
      }
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  const startVoiceRecording = async () => {
    try {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (!SpeechRecognition) {
        setMicPermission('unsupported');
        return;
      }

      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        await navigator.mediaDevices.getUserMedia({ audio: true });
        setMicPermission('granted');
      }

      const recognition = new SpeechRecognition();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = 'en-US';

      recognition.onstart = () => {
        setIsRecording(true);
        setRecordingSeconds(0);
        timerRef.current = setInterval(() => {
          setRecordingSeconds(prev => prev + 1);
        }, 1000);
      };

      recognition.onresult = (event: any) => {
        let fullTranscript = '';
        for (let i = 0; i < event.results.length; i++) {
          fullTranscript += event.results[i][0].transcript + ' ';
        }
        setUserAnswer(fullTranscript.trim());
      };

      recognition.onerror = (event: any) => {
        console.error('Speech recognition error:', event.error);
        if (event.error === 'not-allowed') {
          setMicPermission('denied');
        }
        stopVoiceRecording();
      };

      recognition.onend = () => {
        setIsRecording(false);
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
      };

      recognitionRef.current = recognition;
      recognition.start();
    } catch (err) {
      console.error('Failed to access microphone:', err);
      setMicPermission('denied');
      setIsRecording(false);
    }
  };

  const stopVoiceRecording = () => {
    if (recognitionRef.current) {
      try { recognitionRef.current.stop(); } catch (_) {}
    }
    setIsRecording(false);
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }
  };

  // New Session Form State
  const [sessionTitle, setSessionTitle] = useState('Technical & Architecture Drill');
  const [sessionType, setSessionType] = useState('technical');
  const [selectedOppId, setSelectedOppId] = useState<number | undefined>(undefined);
  const [opportunities, setOpportunities] = useState<any[]>([]);

  // Load Sessions
  const currentSessionRef = useRef(currentSession);
  useEffect(() => {
    currentSessionRef.current = currentSession;
  }, [currentSession]);

  const loadSessionsList = useCallback(async () => {
    setLoadingSessions(true);
    try {
      const res = await fetchPracticeSessions({ page: 1, page_size: 20 });
      setSessions(res.items || []);
      if (!currentSessionRef.current && res.items && res.items.length > 0) {
        // Load the most recent session
        const detail = await fetchPracticeSessionDetail(res.items[0].id);
        setCurrentSession(detail);
        setCurrentQuestionIndex(detail.current_question_index || 0);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoadingSessions(false);
    }
  }, []);

  useEffect(() => {
    loadSessionsList();
    fetchOpportunities({ page: 1, pageSize: 20 }).then(r => setOpportunities(r.items || [])).catch(() => {});
  }, [loadSessionsList]);

  const handleStartFromPrep = useCallback(async (trigger: {
    category: string;
    question: string;
    hint: string;
    company?: string;
    role?: string;
    oppId?: number;
  }) => {
    try {
      const newSession = await createPracticeSession({
        session_title: `${trigger.company || 'Role'} ${trigger.category.toUpperCase()} Drill`,
        session_type: trigger.category,
        opportunity_id: trigger.oppId,
        company_name: trigger.company,
        role_title: trigger.role
      });
      setCurrentSession(newSession);
      setCurrentQuestionIndex(0);
      setUserAnswer('');
      setShowHint(false);
      setSessions(prev => [newSession, ...prev]);
    } catch (err) {
      console.error('Failed to create session from prep trigger', err);
    }
  }, []);

  // Handle incoming trigger from InterviewPrepTab
  useEffect(() => {
    if (initialPrepTrigger) {
      handleStartFromPrep(initialPrepTrigger);
      onClearInitialTrigger?.();
    }
  }, [initialPrepTrigger, handleStartFromPrep, onClearInitialTrigger]);

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const opp = opportunities.find(o => o.id === selectedOppId);
      const created = await createPracticeSession({
        session_title: sessionTitle.trim() || 'Mock Practice Session',
        session_type: sessionType,
        opportunity_id: selectedOppId,
        company_name: opp?.company_name,
        role_title: opp?.title
      });
      setSessions([created, ...sessions]);
      setCurrentSession(created);
      setCurrentQuestionIndex(0);
      setUserAnswer('');
      setShowNewModal(false);
    } catch (err) {
      console.error(err);
      alert('Failed to launch practice session.');
    }
  };

  const handleSelectSession = async (sId: number) => {
    try {
      const detail = await fetchPracticeSessionDetail(sId);
      setCurrentSession(detail);
      setCurrentQuestionIndex(detail.current_question_index || 0);
      const currentQ = detail.questions?.[detail.current_question_index || 0];
      setUserAnswer(currentQ?.user_answer || '');
      setShowHint(false);
    } catch (err) {
      console.error(err);
    }
  };

  const currentQuestion: PracticeQuestionItem | undefined = currentSession?.questions?.[currentQuestionIndex];

  // Update answer box when the displayed question object changes (navigation,
  // session load, or session replacement after evaluation). Identity-based: the
  // server returns the same text for the same object, so renders stay no-ops.
  useEffect(() => {
    if (currentQuestion) {
      setUserAnswer(currentQuestion.user_answer || '');
      setShowHint(false);
    }
  }, [currentQuestion]);

  const handleEvaluateCurrent = async () => {
    if (!currentSession || !currentQuestion || !userAnswer.trim()) return;
    setIsEvaluating(true);
    try {
      const res = await evaluatePracticeQuestion(currentSession.id, currentQuestion.id, userAnswer.trim());
      const updated = res.session || res;
      setCurrentSession(updated);
      setSessions(sessions.map(s => s.id === updated.id ? updated : s));
    } catch (err: any) {
      console.error(err);
      alert(err.message || 'Evaluation failed. Please try again.');
    } finally {
      setIsEvaluating(false);
    }
  };

  const handleCompleteSession = async () => {
    if (!currentSession) return;
    try {
      const finished = await completePracticeSession(currentSession.id);
      setCurrentSession(finished);
      setSessions(sessions.map(s => s.id === finished.id ? finished : s));
    } catch (err) {
      console.error(err);
      alert('Failed to finalize session.');
    }
  };

  const wordCount = userAnswer.trim() ? userAnswer.trim().split(/\s+/).length : 0;

  return (
    <div className="space-y-6">
      {/* Top Banner & Session Controls */}
      <div className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h3 className="text-lg font-bold text-[var(--color-ink)] flex items-center space-x-2">
              <Sparkles className="w-5 h-5 text-emerald-400" />
              <span>Interactive Mock Interview Simulator</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Practice role and technical questions with instant AI evaluation of depth, clarity, and architectural trade-offs.
            </p>
          </div>

          <div className="flex items-center space-x-3">
            <button
              onClick={() => setShowNewModal(true)}
              className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-semibold rounded-lg transition flex items-center space-x-1.5"
            >
              <Plus className="w-4 h-4" />
              <span>New Practice Session</span>
            </button>
          </div>
        </div>

        {/* Existing Sessions Pill Selector */}
        {sessions.length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-800/80 flex items-center space-x-2 overflow-x-auto pb-1 text-xs">
            <span className="text-slate-500 text-xs font-medium flex-shrink-0">Recent Sessions:</span>
            {sessions.map((s) => (
              <button
                key={s.id}
                onClick={() => handleSelectSession(s.id)}
                className={`px-3 py-1.5 rounded-lg flex-shrink-0 font-medium transition flex items-center space-x-1.5 ${
                  currentSession?.id === s.id
                    ? 'bg-emerald-950/80 text-emerald-300 border border-emerald-700/60 font-semibold'
                    : 'bg-slate-800 text-slate-400 hover:text-slate-200 border border-slate-700/50'
                }`}
              >
                <span>{s.session_title}</span>
                {s.overall_score && (
                  <span className="px-1.5 py-0.2 bg-emerald-900/60 text-emerald-400 rounded text-[10px] font-bold">
                    {s.overall_score} pts
                  </span>
                )}
                {s.status === 'completed' && (
                  <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Main Practice Workspace */}
      {currentSession ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column: Question & Answer Workspace (7 cols) */}
          <div className="lg:col-span-7 space-y-4">
            <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-6 space-y-5">
              {/* Question Header & Nav */}
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center space-x-2">
                  <span className="px-2.5 py-0.5 rounded text-[11px] font-bold  bg-slate-800 text-emerald-400 border border-slate-700">
                    {currentQuestion?.category || currentSession.session_type}
                  </span>
                  <span className="text-xs text-slate-400 font-medium">
                    Question {(currentQuestionIndex + 1)} of {currentSession.questions.length}
                  </span>
                </div>

                <div className="flex items-center space-x-1">
                  <button
                    onClick={() => setCurrentQuestionIndex(Math.max(0, currentQuestionIndex - 1))}
                    disabled={currentQuestionIndex === 0}
                    className="p-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-slate-800 text-slate-300 rounded transition"
                    title="Previous Question"
                  >
                    <ArrowLeft className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => setCurrentQuestionIndex(Math.min(currentSession.questions.length - 1, currentQuestionIndex + 1))}
                    disabled={currentQuestionIndex === currentSession.questions.length - 1}
                    className="p-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-40 disabled:hover:bg-slate-800 text-slate-300 rounded transition"
                    title="Next Question"
                  >
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Question Text */}
              <div className="space-y-3">
                <h4 className="text-base font-semibold text-[var(--color-ink)] leading-relaxed">
                  {currentQuestion?.question}
                </h4>

                {currentQuestion?.context_or_hint && (
                  <div>
                    <button
                      onClick={() => setShowHint(!showHint)}
                      className="text-xs text-amber-400/90 hover:text-amber-300 font-medium flex items-center space-x-1 transition"
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                      <span>{showHint ? 'Hide Hint / Context' : 'Show Hint / Context'}</span>
                      {showHint ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                    </button>
                    {showHint && (
                      <div className="mt-2 p-3 bg-amber-950/30 border border-amber-800/40 rounded-lg text-xs text-amber-200/90 leading-relaxed">
                        {currentQuestion.context_or_hint}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Response Mode Selector & Answer Input */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  {/* Mode Toggle */}
                  <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                    <button
                      type="button"
                      onClick={() => {
                        if (isRecording) stopVoiceRecording();
                        setResponseMode('text');
                      }}
                      className={`px-3 py-1 rounded text-xs font-semibold transition ${
                        responseMode === 'text'
                          ? 'bg-slate-800 text-[var(--color-ink)]'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Text Mode
                    </button>
                    <button
                      type="button"
                      onClick={() => setResponseMode('audio')}
                      className={`px-3 py-1 rounded text-xs font-semibold flex items-center gap-1.5 transition ${
                        responseMode === 'audio'
                          ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      <Mic className="w-3.5 h-3.5 text-emerald-400" aria-hidden="true" />
                      <span>Audio Mode</span>
                    </button>
                  </div>

                  {/* Word Count */}
                  <span className={`${wordCount < 20 ? 'text-amber-400' : 'text-emerald-400'} text-xs font-medium`}>
                    {wordCount} words {wordCount < 20 && '(recommend 30+ for depth)'}
                  </span>
                </div>

                {/* Audio Recording Controls when in Audio Mode */}
                {responseMode === 'audio' && (
                  <div className="p-3.5 rounded-xl bg-slate-950 border border-slate-800 space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        {isRecording ? (
                          <button
                            type="button"
                            onClick={stopVoiceRecording}
                            className="px-3.5 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-500 text-[var(--color-ink)] text-xs font-bold flex items-center gap-2 transition animate-pulse"
                          >
                            <Square className="w-3.5 h-3.5" aria-hidden="true" />
                            <span>Stop Recording</span>
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={startVoiceRecording}
                            className="px-3.5 py-1.5 rounded-lg bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-bold flex items-center gap-2 transition"
                          >
                            <Mic className="w-3.5 h-3.5" aria-hidden="true" />
                            <span>Start Speaking</span>
                          </button>
                        )}

                        {isRecording && (
                          <div className="flex items-center gap-2 text-xs font-mono text-rose-400 bg-rose-950/40 px-2.5 py-1 rounded-md border border-rose-500/30">
                            <span className="w-2 h-2 rounded-full bg-rose-500 animate-ping inline-block" />
                            <span>
                              {Math.floor(recordingSeconds / 60).toString().padStart(2, '0')}:
                              {(recordingSeconds % 60).toString().padStart(2, '0')}
                            </span>
                          </div>
                        )}
                      </div>

                      <div className="text-[11px] text-slate-400 flex items-center gap-1.5">
                        <Radio className="w-3.5 h-3.5 text-emerald-400 shrink-0" aria-hidden="true" />
                        <span>Real-time speech-to-text transcript</span>
                      </div>
                    </div>

                    {micPermission === 'unsupported' && (
                      <p className="text-[11px] text-amber-400 bg-amber-950/30 p-2 rounded border border-amber-800/40">
                        Web Speech API is not supported in this browser. Please use Text Mode or Google Chrome / Microsoft Edge.
                      </p>
                    )}
                    {micPermission === 'denied' && (
                      <p className="text-[11px] text-rose-400 bg-rose-950/30 p-2 rounded border border-rose-800/40">
                        Microphone access was denied. Please allow microphone permissions in your browser URL bar.
                      </p>
                    )}

                    <p className="text-[10px] text-slate-500 italic">
                      Privacy guarantee: audio is transcribed locally in your browser. No voice recordings are stored or transmitted without explicit consent.
                    </p>
                  </div>
                )}

                {/* Editable Transcript / Text Response Area */}
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    {responseMode === 'audio' ? 'Review & Edit Your Spoken Response Before Submitting:' : 'Your Response:'}
                  </label>
                  <textarea
                    rows={8}
                    value={userAnswer}
                    onChange={(e) => setUserAnswer(e.target.value)}
                    placeholder={
                      responseMode === 'audio'
                        ? "Click 'Start Speaking' above to dictate your answer. Your spoken words will transcribe here in real-time for you to review and edit..."
                        : "Structure your answer with definition, architectural mechanics, concrete trade-offs, and failure mode considerations..."
                    }
                    className="w-full bg-slate-950 border border-slate-700/80 rounded-xl p-4 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-emerald-500 font-sans leading-relaxed"
                  />
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-between pt-2">
                <button
                  onClick={handleEvaluateCurrent}
                  disabled={isEvaluating || !userAnswer.trim()}
                  className="px-5 py-2.5 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 text-[var(--color-accent-ink)] text-xs font-bold rounded-lg transition flex items-center space-x-2"
                >
                  <Sparkles className={`w-4 h-4 ${isEvaluating ? 'animate-spin' : ''}`} />
                  <span>{isEvaluating ? 'Evaluating with AI Engine...' : 'Submit & Evaluate Answer'}</span>
                </button>

                {currentSession.status !== 'completed' && (
                  <button
                    onClick={handleCompleteSession}
                    className="px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium rounded-lg border border-slate-700 transition flex items-center space-x-1.5"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Finalize Session</span>
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Right Column: AI Evaluation Panel (5 cols) */}
          <div className="lg:col-span-5 space-y-4">
            {currentQuestion?.ai_evaluation ? (
              <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-6 space-y-5">
                {/* Explicit AI Disclaimer Banner */}
                <div className="flex items-center gap-2 rounded-lg border border-white/[0.07] bg-white/[0.02] p-2.5 text-[11px] text-slate-400">
                  <ShieldAlert className="h-3.5 w-3.5 shrink-0 text-slate-500" />
                  <span>AI-Generated Mock Evaluation (Distinct from actual company interviewer feedback)</span>
                </div>

                {/* Score & Verdict */}
                <div className="flex items-center justify-between pb-3 border-b border-slate-800">
                  <div>
                    <span className="text-[11px]  font-semibold text-slate-400">Score Assessment</span>
                    <div className="text-[24px] font-semibold text-emerald-400 flex items-baseline space-x-1">
                      <span>{currentQuestion.ai_evaluation.score}</span>
                      <span className="text-xs text-slate-500 font-normal">/ 100</span>
                    </div>
                  </div>

                  <span className={`px-2.5 py-1 rounded text-xs font-bold ${
                    currentQuestion.ai_evaluation.score >= 80
                      ? 'border border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                      : 'border border-amber-400/25 bg-amber-400/[0.06] text-amber-300'
                  }`}>
                    {currentQuestion.ai_evaluation.verdict}
                  </span>
                </div>

                {/* Metric Bars */}
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
                    <span className="text-slate-400 font-medium block text-[11px] mb-1">Clarity Rating</span>
                    <div className="flex items-center space-x-1 text-emerald-400 font-bold">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <Star
                          key={i}
                          className={`w-3.5 h-3.5 ${
                            i < currentQuestion.ai_evaluation!.clarity_rating
                              ? 'fill-emerald-400 text-emerald-400'
                              : 'text-slate-700'
                          }`}
                        />
                      ))}
                      <span className="ml-1 text-slate-200 text-xs">
                        {currentQuestion.ai_evaluation.clarity_rating}/5
                      </span>
                    </div>
                  </div>

                  <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
                    <span className="text-slate-400 font-medium block text-[11px] mb-1">Technical Depth</span>
                    <div className="flex items-center gap-1 font-medium">
                      {Array.from({ length: 5 }).map((_, i) => (
                        <div
                          key={i}
                          className={`h-2 flex-1 rounded-sm ${
                            i < currentQuestion.ai_evaluation!.technical_depth
                              ? 'bg-emerald-400/80'
                              : 'bg-slate-800'
                          }`}
                        />
                      ))}
                      <span className="ml-1 text-slate-200 text-xs">
                        {currentQuestion.ai_evaluation.technical_depth}/5
                      </span>
                    </div>
                  </div>
                </div>

                {/* Strengths */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-emerald-400 flex items-center space-x-1.5 ">
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Identified Strengths</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-slate-300">
                    {(currentQuestion.ai_evaluation.strengths || []).map((str, i) => (
                      <li key={i} className="flex items-start space-x-2 bg-slate-950/40 p-2 rounded border border-slate-800/60">
                        <span className="text-emerald-400">•</span>
                        <span>{str}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Improvement Areas */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-amber-400 flex items-center space-x-1.5 ">
                    <AlertCircle className="w-3.5 h-3.5" />
                    <span>Areas for Improvement</span>
                  </div>
                  <ul className="space-y-1.5 text-xs text-slate-300">
                    {(currentQuestion.ai_evaluation.improvement_areas || []).map((imp, i) => (
                      <li key={i} className="flex items-start space-x-2 bg-slate-950/40 p-2 rounded border border-slate-800/60">
                        <span className="text-amber-400">•</span>
                        <span>{imp}</span>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Ideal Answer Points */}
                <div className="space-y-2">
                  <div className="text-xs font-semibold text-slate-300 flex items-center space-x-1.5 ">
                    <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Ideal Response Outline</span>
                  </div>
                  <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3 space-y-1 text-xs text-slate-300">
                    {(currentQuestion.ai_evaluation.ideal_answer_points || []).map((pt, i) => (
                      <p key={i} className="text-slate-300 leading-relaxed font-mono text-[11px]">
                        {pt}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-8 text-center space-y-3">
                <Sparkles className="w-10 h-10 text-slate-700 mx-auto" />
                <h4 className="text-sm font-semibold text-slate-300">Awaiting Your Answer</h4>
                <p className="text-xs text-slate-500 max-w-xs mx-auto">
                  Type your technical explanation on the left and submit to receive instant scores for clarity, depth, and recommended answer outlines.
                </p>
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-12 text-center space-y-4">
          <BookOpen className="w-10 h-10 text-emerald-400 mx-auto" />
          <h4 className="text-base font-bold text-[var(--color-ink)]">No Active Mock Practice Session</h4>
          <p className="text-xs text-slate-400 max-w-md mx-auto">
            Select an interview question from the Interview Prep tab, or create a new session above to practice questions and receive real-time AI evaluations.
          </p>
          <button
            onClick={() => setShowNewModal(true)}
            className="whitespace-nowrap px-4 py-2 bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-bold rounded-lg transition"
          >
            Start practice
          </button>
        </div>
      )}

      {/* New Practice Session Modal */}
      {showNewModal && (
        <div className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl max-w-md w-full p-6 space-y-5">
            <h3 className="text-base font-bold text-[var(--color-ink)] flex items-center space-x-2">
              <Plus className="w-4 h-4 text-emerald-400" />
              <span>Launch Mock Practice Session</span>
            </h3>

            <form onSubmit={handleCreateSession} className="space-y-4">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Session Title</label>
                <input
                  type="text"
                  value={sessionTitle}
                  onChange={(e) => setSessionTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-emerald-500"
                  placeholder="e.g. Stripe Backend Architecture Drill"
                  required
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Session Category</label>
                <select
                  value={sessionType}
                  onChange={(e) => setSessionType(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="technical">Technical & System Architecture</option>
                  <option value="dsa">DSA & Algorithmic Problem Solving</option>
                  <option value="projects">Candidate Profile Project Deep Dive</option>
                  <option value="behavioral">Behavioral (STAR Method)</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Target Opportunity (Optional)</label>
                <select
                  value={selectedOppId || ''}
                  onChange={(e) => setSelectedOppId(e.target.value ? Number(e.target.value) : undefined)}
                  className="w-full bg-slate-950 border border-slate-700 text-sm text-slate-200 rounded-lg px-3 py-2 outline-none focus:ring-2 focus:ring-emerald-500"
                >
                  <option value="">General Practice (No specific opportunity)</option>
                  {opportunities.map((opp) => (
                    <option key={opp.id} value={opp.id}>
                      {opp.company_name} - {opp.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="flex items-center justify-end space-x-3 pt-3 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-semibold rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-bold rounded-lg transition"
                >
                  Start Simulator
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
