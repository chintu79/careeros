import React, { useState, useEffect, useRef } from 'react';
import { 
  Bot, 
  Send, 
  Sparkles, 
  Plus, 
  Trash2, 
  Database, 
  User, 
  Clock, 
  Target,
  FileText,
  Mic,
  TrendingUp,
  BarChart3,
  CheckCircle2,
  AlertTriangle,
  HelpCircle,
  ExternalLink,
  ChevronRight,
  Layers,
  ArrowRight
} from 'lucide-react';
import { 
  ChatConversation, 
  ChatMessage, 
  IntelligenceWorkflowType, 
  IntelligenceReport,
  TruthLayers,
  OpportunityItem
} from '../../types';
import { 
  fetchConversations, 
  createConversation, 
  fetchConversationDetail, 
  sendChatMessage, 
  deleteConversation,
  fetchOpportunities,
  runJobMatchingWorkflow,
  runResumeIntelligenceWorkflow,
  runInterviewPrepWorkflow,
  runCareerGrowthWorkflow,
  runApplicationIntelligenceWorkflow
} from '../../services/api';
import { PageHeader } from '../ui/PageHeader';
import { MarkdownRenderer } from '../ui/MarkdownRenderer';

export const AIChatAssistantView: React.FC = () => {
  const [conversations, setConversations] = useState<ChatConversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<number | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputText, setInputText] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  
  // Workflow state
  const [activeWorkflow, setActiveWorkflow] = useState<IntelligenceWorkflowType>('chat');
  const [topOpportunities, setTopOpportunities] = useState<OpportunityItem[]>([]);
  const [selectedOpportunityId, setSelectedOpportunityId] = useState<number>(37);
  const [activeReport, setActiveReport] = useState<IntelligenceReport | null>(null);
  const [loadingWorkflow, setLoadingWorkflow] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const loadConversations = async () => {
    try {
      const convs = await fetchConversations();
      setConversations(convs);
      if (convs.length > 0 && !activeConvId) {
        selectConversation(convs[0].id);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadTopOpportunities = async () => {
    try {
      const res = await fetchOpportunities({ page: 1, page_size: 20, sort_by: 'match_score' });
      const items = res.items || [];
      setTopOpportunities(items);
      if (items.length > 0) {
        setSelectedOpportunityId(items[0].id);
      }
    } catch (err) {
      if ((err as Error)?.name !== 'AbortError') console.error('Failed to load opportunities:', err);
    }
  };

  const selectConversation = async (id: number) => {
    setActiveConvId(id);
    try {
      const detail = await fetchConversationDetail(id);
      setMessages(detail.messages || []);
    } catch (err) {
      console.error(err);
    }
  };

  useEffect(() => {
    loadConversations();
    loadTopOpportunities();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, activeReport]);

  const handleNewConversation = async () => {
    try {
      const newConv = await createConversation("New Career Conversation");
      setConversations([newConv, ...conversations]);
      setActiveConvId(newConv.id);
      setMessages([]);
      setActiveReport(null);
    } catch (err) {
      console.error(err);
    }
  };

  const handleDeleteConversation = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteConversation(id);
      const remaining = conversations.filter(c => c.id !== id);
      setConversations(remaining);
      if (activeConvId === id && remaining.length > 0) {
        selectConversation(remaining[0].id);
      } else if (remaining.length === 0) {
        handleNewConversation();
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleSendMessage = async (textToSend?: string) => {
    const text = textToSend || inputText;
    if (!text.trim() || !activeConvId || sending) return;

    const userTempMessage: ChatMessage = {
      id: Date.now(),
      conversation_id: activeConvId,
      sender: 'user',
      content: text,
      created_at: new Date().toISOString()
    };
    setMessages(prev => [...prev, userTempMessage]);
    setInputText('');
    setSending(true);

    try {
      const response = await sendChatMessage(activeConvId, text, {
        opportunity_id: selectedOpportunityId,
        workflow: activeWorkflow !== 'chat' ? activeWorkflow : undefined
      });
      setMessages(prev => [...prev, response]);
      fetchConversations().then(res => setConversations(res));
    } catch (err) {
      console.error(err);
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 1,
          conversation_id: activeConvId,
          sender: 'assistant',
          content: "Encountered an issue executing AI workflow. Ensure the backend and Ollama are reachable.",
          created_at: new Date().toISOString()
        }
      ]);
    } finally {
      setSending(false);
    }
  };

  const handleRunWorkflow = async (wf: IntelligenceWorkflowType) => {
    setActiveWorkflow(wf);
    if (wf === 'chat') {
      setActiveReport(null);
      return;
    }

    setLoadingWorkflow(true);
    setActiveReport(null);

    try {
      let report: IntelligenceReport;
      if (wf === 'job_matching') {
        report = await runJobMatchingWorkflow(selectedOpportunityId);
      } else if (wf === 'resume_intelligence') {
        report = await runResumeIntelligenceWorkflow(selectedOpportunityId);
      } else if (wf === 'interview_prep') {
        report = await runInterviewPrepWorkflow(selectedOpportunityId);
      } else if (wf === 'career_growth') {
        report = await runCareerGrowthWorkflow();
      } else if (wf === 'application_intelligence') {
        report = await runApplicationIntelligenceWorkflow();
      } else {
        return;
      }
      setActiveReport(report);
    } catch (err: any) {
      console.error('Workflow execution error:', err);
      alert(err.message || 'Failed to execute workflow');
    } finally {
      setLoadingWorkflow(false);
    }
  };

  const renderTruthLayerCard = (layers?: TruthLayers) => {
    if (!layers) return null;

    const hasDb = layers.verified_database && layers.verified_database.length > 0;
    const hasExt = layers.extracted_external && layers.extracted_external.length > 0;
    const hasAi = layers.strategic_recommendations && layers.strategic_recommendations.length > 0;
    const hasUnknown = layers.unknown_missing && layers.unknown_missing.length > 0;

    if (!hasDb && !hasExt && !hasAi && !hasUnknown) return null;

    return (
      <div className="mt-4 pt-3 border-t border-dark-750 grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
        {/* Layer 1: Verified DB */}
        {hasDb && (
          <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/30 text-emerald-200">
            <div className="flex items-center space-x-1.5 font-bold text-emerald-400 mb-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400/80" aria-hidden="true" />
              <span>Verified Database Record</span>
            </div>
            <ul className="space-y-1 text-[11px] opacity-90">
              {layers.verified_database.map((item, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 flex-shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Layer 2: Extracted External */}
        {hasExt && (
          <div className="p-3 rounded-xl bg-blue-950/20 border border-blue-500/30 text-blue-200">
            <div className="flex items-center space-x-1.5 font-bold text-blue-400 mb-2">
              <span className="w-2 h-2 rounded-full bg-blue-400" />
              <span>Extracted External Information</span>
            </div>
            <ul className="space-y-1 text-[11px] opacity-90">
              {layers.extracted_external.map((item, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <ChevronRight className="w-3.5 h-3.5 text-blue-400 flex-shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Layer 3: Strategic AI Recommendations */}
        {hasAi && (
          <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-200">
            <div className="flex items-center space-x-1.5 font-bold text-amber-400 mb-2">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              <span>AI Strategic Recommendation</span>
            </div>
            <ul className="space-y-1 text-[11px] opacity-90">
              {layers.strategic_recommendations.map((item, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400 flex-shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* Layer 4: Unknown / Missing */}
        {hasUnknown && (
          <div className="p-3 rounded-xl bg-rose-950/20 border border-rose-500/30 text-rose-200">
            <div className="flex items-center space-x-1.5 font-bold text-rose-400 mb-2">
              <span className="w-2 h-2 rounded-full bg-rose-400" />
              <span>Unknown / Missing Information</span>
            </div>
            <ul className="space-y-1 text-[11px] opacity-90">
              {layers.unknown_missing.map((item, idx) => (
                <li key={idx} className="flex items-start space-x-1.5">
                  <AlertTriangle className="w-3.5 h-3.5 text-rose-400 flex-shrink-0 mt-0.5" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };

  const quickPrompts = [
    "Find internships matching my profile",
    "Identify missing skills for target role",
    "Tailor resume for top matched opportunity",
    "Generate technical interview questions"
  ];

  if (loading) {
    return <div className="p-12 text-center text-slate-400">Loading CareerOS AI Assistant...</div>;
  }

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Intelligence"
        title="AI Assistant"
        description="Grounded answers over your verified profile, live opportunities and application history."
      />

      <div className="flex min-h-[480px] flex-1 flex-col space-y-3">
      {/* Top Workflow Switcher Bar */}
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-1.5">
        <div className="flex flex-1 items-center gap-0.5 overflow-x-auto no-scrollbar">
          <button
            onClick={() => handleRunWorkflow('chat')}
            className={`inline-flex min-h-[32px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-2.5 text-[12px] font-medium transition-colors ${
              activeWorkflow === 'chat'
                ? 'bg-white/[0.08] text-[var(--color-ink)]'
                : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
            }`}
          >
            <Bot className="w-3.5 h-3.5" />
            <span>Interactive Chat</span>
          </button>

          <button
            onClick={() => handleRunWorkflow('job_matching')}
            className={`inline-flex min-h-[32px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-2.5 text-[12px] font-medium transition-colors ${
              activeWorkflow === 'job_matching'
                ? 'bg-white/[0.08] text-[var(--color-ink)]'
                : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
            }`}
          >
            <Target className="whitespace-nowrap w-3.5 h-3.5" />
            <span>Job matching</span>
          </button>

          <button
            onClick={() => handleRunWorkflow('resume_intelligence')}
            className={`inline-flex min-h-[32px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-2.5 text-[12px] font-medium transition-colors ${
              activeWorkflow === 'resume_intelligence'
                ? 'bg-white/[0.08] text-[var(--color-ink)]'
                : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
            }`}
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Resume Intelligence</span>
          </button>

          <button
            onClick={() => handleRunWorkflow('interview_prep')}
            className={`inline-flex min-h-[32px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-2.5 text-[12px] font-medium transition-colors ${
              activeWorkflow === 'interview_prep'
                ? 'bg-white/[0.08] text-[var(--color-ink)]'
                : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
            }`}
          >
            <Mic className="w-3.5 h-3.5" />
            <span>Interview Prep</span>
          </button>

          <button
            onClick={() => handleRunWorkflow('career_growth')}
            className={`inline-flex min-h-[32px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-2.5 text-[12px] font-medium transition-colors ${
              activeWorkflow === 'career_growth'
                ? 'bg-white/[0.08] text-[var(--color-ink)]'
                : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
            }`}
          >
            <TrendingUp className="w-3.5 h-3.5" />
            <span>Career Growth</span>
          </button>

          <button
            onClick={() => handleRunWorkflow('application_intelligence')}
            className={`inline-flex min-h-[32px] shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[6px] px-2.5 text-[12px] font-medium transition-colors ${
              activeWorkflow === 'application_intelligence'
                ? 'bg-white/[0.08] text-[var(--color-ink)]'
                : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Application Intelligence</span>
          </button>
        </div>

        {/* Opportunity Picker for Role-Specific Workflows */}
        {['job_matching', 'resume_intelligence', 'interview_prep'].includes(activeWorkflow) && (
          <div className="flex w-full items-center gap-2 sm:w-auto sm:pl-2">
            <span className="text-[11px] text-slate-400 whitespace-nowrap">Target Role:</span>
            <select
              value={selectedOpportunityId}
              onChange={(e) => {
                const newId = Number(e.target.value);
                setSelectedOpportunityId(newId);
              }}
              aria-label="Target Role for Specialized Analysis"
              className="input-base min-h-[32px] max-w-xs py-1 text-[11px]"
            >
              {topOpportunities.map(o => (
                <option key={o.id} value={o.id}>
                  #{o.id} {o.company_name} - {o.title} ({Math.round(o.match_score || 0)}%)
                </option>
              ))}
            </select>
            <button
              onClick={() => handleRunWorkflow(activeWorkflow)}
              disabled={loadingWorkflow}
              className="inline-flex min-h-[32px] shrink-0 items-center gap-1.5 rounded-md bg-emerald-400 px-2.5 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50"
            >
              <Sparkles className="w-3 h-3" />
              <span>{loadingWorkflow ? 'Analyzing...' : 'Run Analysis'}</span>
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col md:flex-row gap-4 overflow-hidden">
        {/* Conversations Sidebar (always available) */}
        <div className="flex w-full flex-shrink-0 flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-[var(--color-paper)] md:w-64">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-3 py-2.5">
            <span className="text-[10px] font-medium text-slate-400">Conversations</span>
            <button
              type="button"
              onClick={handleNewConversation}
              className="inline-flex min-h-[26px] items-center gap-1 rounded-md border border-white/[0.09] px-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              title="Start new conversation"
            >
              <Plus className="w-3.5 h-3.5" aria-hidden="true" />
              <span>New Chat</span>
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {conversations.map(c => {
              const active = activeConvId === c.id;
              return (
                <div
                  key={c.id}
                  className={`group flex items-center justify-between rounded-md p-0.5 transition-colors ${
                    active
                      ? 'bg-white/[0.06] text-[var(--color-ink)]'
                      : 'text-slate-400 hover:bg-white/[0.03] hover:text-slate-200'
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => selectConversation(c.id)}
                    aria-current={active ? 'true' : undefined}
                    className="flex flex-1 items-center gap-2 truncate rounded px-2 py-1.5 text-left text-[12px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                  >
                    <Bot className={`w-3.5 h-3.5 flex-shrink-0 ${active ? 'text-emerald-400' : 'text-slate-500'}`} aria-hidden="true" />
                    <span className="truncate">{c.title}</span>
                  </button>

                  <button
                    type="button"
                    onClick={(e) => handleDeleteConversation(c.id, e)}
                    aria-label={`Delete conversation: ${c.title}`}
                    className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 text-slate-400 hover:text-rose-400 rounded transition focus-visible:ring-1 focus-visible:ring-rose-500 min-h-[24px] min-w-[24px] flex items-center justify-center"
                    title="Delete chat"
                  >
                    <Trash2 className="w-3.5 h-3.5" aria-hidden="true" />
                  </button>
                </div>
              );
            })}
          </div>

          <div className="flex flex-col space-y-1 border-t border-white/[0.06] px-3 py-2.5 text-[11px] text-slate-500">
            <div className="flex items-center space-x-2">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400/80" aria-hidden="true" />
              <span className="text-[11px] font-medium text-slate-300">PostgreSQL pgvector Grounded</span>
            </div>
            <span className="text-[10px] text-slate-400">Local Ollama AI (qwen2.5:3b + bge-m3)</span>
          </div>
        </div>

        {/* Intelligence Workspace / Chat Feed */}
        <div className="flex flex-1 flex-col overflow-hidden rounded-xl border border-white/[0.07] bg-[var(--color-paper)]">
          {/* Active Workflow Dedicated Dossier View */}
          {activeWorkflow !== 'chat' && activeReport ? (
            <div
              tabIndex={0}
              role="region"
              aria-label="Workflow Dossier Report"
              className="flex-1 space-y-5 overflow-y-auto p-4 focus:outline-none focus-visible:ring-1 focus-visible:ring-emerald-400/60 sm:p-5"
            >
              {/* Dossier Header */}
              <div className="flex items-center justify-between border-b border-white/[0.06] pb-3">
                <div>
                  <span className="text-[10px] font-medium text-emerald-300">
                    Specialized Intelligence Workflow
                  </span>
                  <h2 className="mt-0.5 text-[15px] font-semibold text-[var(--color-ink)]">{activeReport.title}</h2>
                </div>
                <button
                  onClick={() => setActiveWorkflow('chat')}
                  className="inline-flex min-h-[28px] items-center gap-1.5 rounded-md border border-white/[0.09] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
                >
                  <span>Discuss in Chat</span>
                  <ArrowRight className="w-3.5 h-3.5 text-emerald-400" />
                </button>
              </div>

              {/* Quick Metrics Bar */}
              {activeReport.metrics && (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {Object.entries(activeReport.metrics).map(([key, val]) => (
                    <div key={key} className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
                      <span className="block text-[10px] font-medium text-slate-500">
                        {key.replace(/_/g, ' ')}
                      </span>
                      <span className="mt-1 block text-[15px] font-semibold text-[var(--color-ink)]">
                        {typeof val === 'boolean' ? (val ? 'Yes' : 'No') : String(val)}
                      </span>
                    </div>
                  ))}
                </div>
              )}

              {/* Executive Summary */}
              <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-4">
                <MarkdownRenderer content={activeReport.summary} />
              </div>

              {/* 4 Truth Layers Visual Card */}
              {renderTruthLayerCard(activeReport.truth_layers)}
            </div>
          ) : activeWorkflow !== 'chat' && loadingWorkflow ? (
            <div className="flex h-full flex-col items-center justify-center space-y-3 p-8">
              <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
              <p className="text-[12px] font-medium text-slate-300">Running Context-Aware Intelligence Workflow...</p>
              <p className="text-[11px] text-slate-400">Querying verified database records and extracting job posting requirements.</p>
            </div>
          ) : (
            /* Interactive Chat Feed */
            <div
              tabIndex={0}
              role="log"
              aria-live="polite"
              aria-label="Conversation Messages Feed"
              className="flex-1 space-y-4 overflow-y-auto p-4 focus:outline-none focus-visible:ring-1 focus-visible:ring-emerald-400/60 sm:p-5"
            >
              {messages.length === 0 ? (
                <div className="flex h-full flex-col items-center justify-center space-y-4 p-6 text-center">
                  <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300">
                    <Sparkles className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="block text-[15px] font-semibold text-[var(--color-ink)]">
                      Ask anything about your search
                    </span>
                    <p className="mx-auto mt-1.5 max-w-md text-[12px] leading-relaxed text-slate-500">
                      Directly connected to your verified candidate profile, 205 live internship records, and application funnel.
                      Every answer separates verified database facts from external job descriptions and AI advice.
                    </p>
                  </div>

                  {/* Quick Prompt Chips */}
                  <div className="grid w-full max-w-lg grid-cols-1 gap-2 pt-2 sm:grid-cols-2">
                    {quickPrompts.map((qp, i) => (
                      <button
                        key={i}
                        onClick={() => handleSendMessage(qp)}
                        className="rounded-lg border border-white/[0.07] bg-[var(--color-paper-2)] p-2.5 text-left text-[12px] text-slate-400 transition-colors hover:border-white/[0.13] hover:text-slate-200"
                      >
                        {qp}
                      </button>
                    ))}
                  </div>
                </div>
              ) : (
                messages.map(m => {
                  const isUser = m.sender === 'user';
                  return (
                    <div
                      key={m.id}
                      className={`flex items-start space-x-3 ${isUser ? 'flex-row-reverse space-x-reverse' : ''}`}
                    >
                      <div className={`flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md border ${
                        isUser 
                          ? 'border-white/[0.10] bg-white/[0.06] text-slate-300' 
                          : 'border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-300'
                      }`}>
                        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
                      </div>

                      <div className={`max-w-[85%] rounded-lg p-3.5 text-[12px] leading-relaxed ${
                        isUser
                          ? 'border border-emerald-400/20 bg-emerald-400/[0.08] text-slate-100'
                          : 'border border-white/[0.07] bg-[var(--color-paper-2)] text-slate-300'
                      }`}>
                        {/* Tool Execution Badges */}
                        {!isUser && m.tool_calls && m.tool_calls.length > 0 && (
                          <div className="mb-2.5 flex flex-wrap gap-1.5 border-b border-white/[0.06] pb-2">
                            {m.tool_calls.map((t, idx) => (
                              <span
                                key={idx}
                                className="inline-flex items-center gap-1 rounded border border-white/[0.06] bg-white/[0.03] px-1.5 py-0.5 font-mono text-[10px] text-emerald-300/90"
                              >
                                <Database className="w-3 h-3 text-emerald-500" />
                                <span>Queried DB: {t.tool}</span>
                              </span>
                            ))}
                          </div>
                        )}

                        {isUser ? (
                          <div className="whitespace-pre-wrap font-sans">
                            {m.content}
                          </div>
                        ) : (
                          <MarkdownRenderer content={m.content} />
                        )}

                        {/* Structured Truth Layers if attached */}
                        {!isUser && renderTruthLayerCard(m.truth_layers)}

                        <span className={`block mt-2 text-[10px] text-right font-mono ${isUser ? 'text-slate-500' : 'text-slate-600'}`}>
                          {new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                    </div>
                  );
                })
              )}
              <div ref={messagesEndRef} />
            </div>
          )}

          {/* Chat Input Bar */}
          <div className="border-t border-white/[0.06] bg-[var(--color-paper-2)] p-2.5">
            <form
              onSubmit={e => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="flex items-center space-x-2"
            >
              <input
                id="chat-composer-input"
                type="text"
                aria-label="Ask CareerOS AI"
                placeholder="Ask CareerOS AI (e.g. 'Match me against role #37', 'Analyze my application bottlenecks')..."
                value={inputText}
                onChange={e => setInputText(e.target.value)}
                className="input-base min-h-[36px] flex-1"
              />
                <button
                  type="submit"
                  aria-label="Send message to CareerOS AI"
                  aria-busy={sending}
                  disabled={sending || !inputText.trim()}
                  className="inline-flex min-h-[36px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3.5 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                >
                  <Send className="w-3.5 h-3.5" aria-hidden="true" />
                  <span>{sending ? 'Thinking...' : 'Send'}</span>
                </button>
            </form>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
};
