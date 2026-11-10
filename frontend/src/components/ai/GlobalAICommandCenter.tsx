import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  X,
  Send,
  RotateCw,
  ShieldCheck,
  ShieldAlert,
  CheckCircle2,
  XCircle,
  Clock,
  History,
  CornerDownLeft,
  ChevronRight,
  Layers,
  ArrowRight,
  Database,
  ExternalLink,
  Plus
} from 'lucide-react';
import {
  sendAICommandMessage,
  fetchAICommandSuggestions,
  executeAIAction,
  rejectAIAction,
  fetchAIActionAuditLog,
  fetchConversations,
  createConversation
} from '../../services/api';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import { TOKENS } from '../ui/DesignTokens';
import { saveActiveElement, restoreActiveElement, trapFocus } from '../../utils/focusTrap';
import { useAnnounce } from '../a11y/LiveAnnouncer';

interface ActionProposal {
  action_id: number;
  tool_name: string;
  description: string;
  data_payload: Record<string, any>;
  requires_approval: boolean;
  status: 'pending_approval' | 'executed' | 'rejected' | 'failed';
  result_summary?: string;
  executed_at?: string;
}

interface MessageItem {
  id: string | number;
  sender: 'user' | 'assistant';
  content: string;
  tool_executed?: string;
  is_consequential?: boolean;
  action_proposal?: ActionProposal | null;
  suggested_actions?: string[];
  created_at?: string;
}

interface GlobalAICommandCenterProps {
  isOpen: boolean;
  onClose: () => void;
  onNavigateTab?: (tab: string) => void;
}

export const GlobalAICommandCenter: React.FC<GlobalAICommandCenterProps> = ({
  isOpen,
  onClose,
  onNavigateTab
}) => {
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [inputPrompt, setInputPrompt] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [currentTool, setCurrentTool] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [activeView, setActiveView] = useState<'chat' | 'audit'>('chat');
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [actionLoadingId, setActionLoadingId] = useState<number | null>(null);

  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const { announce } = useAnnounce();

  // Load suggestions, initial conversation, and manage focus
  useEffect(() => {
    if (isOpen) {
      saveActiveElement();
      fetchAICommandSuggestions()
        .then(res => setSuggestions(res.suggestions || []))
        .catch(err => console.error(err));

      fetchConversations()
        .then((convs: any[]) => {
          if (convs && convs.length > 0) {
            setConversationId(convs[0].id);
          }
        })
        .catch((err: any) => console.error(err));

      setTimeout(() => inputRef.current?.focus(), 100);
    } else {
      restoreActiveElement();
    }
  }, [isOpen]);

  // Load audit log if active
  useEffect(() => {
    if (isOpen && activeView === 'audit') {
      fetchAIActionAuditLog()
        .then(res => setAuditLogs(res.logs || []))
        .catch(err => console.error(err));
    }
  }, [isOpen, activeView]);

  // Auto-scroll on new message
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  // Handle escape dismissal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (isOpen && e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleSendMessage = async (textToSend?: string) => {
    const prompt = (textToSend || inputPrompt).trim();
    if (!prompt || isLoading) return;

    setInputPrompt('');
    const userMsgId = Date.now();
    const newMsgList: MessageItem[] = [
      ...messages,
      {
        id: userMsgId,
        sender: 'user',
        content: prompt,
        created_at: new Date().toISOString()
      }
    ];
    setMessages(newMsgList);
    setIsLoading(true);
    setCurrentTool('Analyzing intent...');

    try {
      const res = await sendAICommandMessage({
        content: prompt,
        conversation_id: conversationId || undefined
      });

      setMessages(prev => [
        ...prev,
        {
          id: res.id || Date.now() + 1,
          sender: 'assistant',
          content: res.content,
          tool_executed: res.tool_executed,
          is_consequential: res.is_consequential,
          action_proposal: res.action_proposal,
          suggested_actions: res.suggested_actions,
          created_at: res.created_at
        }
      ]);
      if (res.conversation_id && !conversationId) {
        setConversationId(res.conversation_id);
      }
    } catch (err: any) {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now() + 2,
          sender: 'assistant',
          content: `⚠️ Failed to execute command: ${err.message || 'Server error'}. Please try again.`
        }
      ]);
    } finally {
      setIsLoading(false);
      setCurrentTool(null);
    }
  };

  // IME-safe enter-to-submit
  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      // Block premature submission during IME composition
      if (e.nativeEvent.isComposing || (e.nativeEvent as any).keyCode === 229) {
        return;
      }
      handleSendMessage();
    }
  };

  // Handle Action Approval
  const handleApproveAction = async (msgId: string | number, actionId: number) => {
    setActionLoadingId(actionId);
    try {
      const res = await executeAIAction(actionId);
      announce('Consequential action executed successfully.', 'polite');
      // Update message state with execution result
      setMessages(prev =>
        prev.map(m => {
          if (m.action_proposal && m.action_proposal.action_id === actionId) {
            return {
              ...m,
              action_proposal: {
                ...m.action_proposal,
                status: 'executed',
                result_summary: res.result_summary,
                executed_at: res.executed_at
              }
            };
          }
          return m;
        })
      );
    } catch (err: any) {
      announce(`Execution failed: ${err.message}`, 'assertive');
      alert(`Execution failed: ${err.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  // Handle Action Rejection
  const handleRejectAction = async (msgId: string | number, actionId: number) => {
    setActionLoadingId(actionId);
    try {
      await rejectAIAction(actionId, 'Declined by user via Command Center');
      announce('Consequential action declined.', 'polite');
      setMessages(prev =>
        prev.map(m => {
          if (m.action_proposal && m.action_proposal.action_id === actionId) {
            return {
              ...m,
              action_proposal: {
                ...m.action_proposal,
                status: 'rejected'
              }
            };
          }
          return m;
        })
      );
    } catch (err: any) {
      announce(`Rejection failed: ${err.message}`, 'assertive');
      alert(`Rejection failed: ${err.message}`);
    } finally {
      setActionLoadingId(null);
    }
  };

  const handleStartNewChat = async () => {
    try {
      const conv = await createConversation("AI Command Session");
      setConversationId(conv.id);
      setMessages([]);
    } catch (err: any) {
      console.error(err);
    }
  };

  if (!isOpen) return null;

  return (
    <div
      ref={dialogRef}
      role="dialog"
      aria-modal="true"
      aria-label="Global AI Command Center"
      className="fixed inset-0 z-50 flex justify-end bg-slate-950/70 backdrop-blur-sm animate-fade-in"
      style={{ overscrollBehavior: 'contain' }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') {
          e.stopPropagation();
          onClose();
          return;
        }
        if (dialogRef.current) {
          trapFocus(dialogRef.current, e);
        }
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-2xl h-full bg-slate-900 border-l border-slate-800 flex flex-col animate-slide-down">
        {/* Top Header */}
        <div className="h-16 px-5 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-950/80">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400" aria-hidden="true">
              <Sparkles className="w-4 h-4 animate-pulse" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-sm font-bold text-[var(--color-ink)] tracking-tight">Global AI Command Center</h2>
                <Badge variant="emerald" size="sm" dot>
                  Ollama Local
                </Badge>
              </div>
              <p className="text-[11px] text-slate-400 font-mono">
                Ambient Intelligence & Authorized Actions (⌘J)
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={() => setActiveView(activeView === 'chat' ? 'audit' : 'chat')}
              aria-pressed={activeView === 'audit'}
              aria-label="Toggle consequential action audit log"
              className={`px-2.5 py-1.5 rounded-lg border text-xs font-medium transition flex items-center space-x-1.5 focus-visible:ring-1 focus-visible:ring-emerald-500 ${
                activeView === 'audit'
                  ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                  : 'bg-slate-800/80 border-slate-700/80 text-slate-300 hover:text-[var(--color-ink)]'
              }`}
            >
              <History className="w-3.5 h-3.5" aria-hidden="true" />
              <span>Audit Log</span>
            </button>

            <button
              type="button"
              onClick={handleStartNewChat}
              aria-label="Start new AI command session"
              className="p-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-400 hover:text-[var(--color-ink)] hover:border-slate-600 transition focus-visible:ring-1 focus-visible:ring-emerald-500"
            >
              <Plus className="w-4 h-4" aria-hidden="true" />
            </button>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close Global AI Command Center (Esc)"
              className="p-1.5 rounded-lg text-slate-400 hover:text-[var(--color-ink)] hover:bg-slate-800 border border-transparent hover:border-slate-700 transition focus-visible:ring-1 focus-visible:ring-emerald-500"
            >
              <X className="w-4 h-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* View Switcher: Chat or Audit Log */}
        {activeView === 'audit' ? (
          /* Audit Log View */
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-800">
              <div>
                <h3 className="text-xs font-bold text-[var(--color-ink)] ">Consequential Action Audit Log</h3>
                <p className="text-[11px] text-slate-400 mt-0.5">Immutable record of all AI proposals, authorizations, and database mutations</p>
              </div>
              <Badge variant="neutral" size="sm">
                {auditLogs.length} events
              </Badge>
            </div>

            <div className="space-y-3">
              {auditLogs.map((log) => {
                const isApproved = log.status === 'executed';
                const isRejected = log.status === 'rejected';

                return (
                  <div key={log.id} className="p-3.5 rounded-xl bg-slate-950/70 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        {isApproved ? (
                          <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                        ) : isRejected ? (
                          <XCircle className="w-4 h-4 text-rose-400 shrink-0" />
                        ) : (
                          <Clock className="w-4 h-4 text-amber-400 shrink-0" />
                        )}
                        <span className="text-xs font-semibold text-[var(--color-ink)]">{log.action_type}</span>
                      </div>
                      <Badge
                        variant={isApproved ? 'emerald' : isRejected ? 'rose' : 'amber'}
                        size="sm"
                      >
                        {log.status.toUpperCase()}
                      </Badge>
                    </div>

                    <p className="text-xs text-slate-300">{log.description}</p>

                    {log.result_summary && (
                      <div className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px] text-emerald-300 font-mono">
                        {log.result_summary}
                      </div>
                    )}

                    <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono pt-1 border-t border-slate-850">
                      <span>Action #{log.id} · Tool: {log.tool_name}</span>
                      <span>{log.executed_at ? new Date(log.executed_at).toLocaleTimeString() : new Date(log.created_at).toLocaleTimeString()}</span>
                    </div>
                  </div>
                );
              })}

              {auditLogs.length === 0 && (
                <div className="py-16 text-center text-xs text-slate-400">
                  No consequential actions recorded yet.
                </div>
              )}
            </div>
          </div>
        ) : (
          /* Chat & Command View */
          <>
            {/* Context Suggestions Quick Chips */}
            {suggestions.length > 0 && messages.length === 0 && (
              <div className="p-4 bg-slate-950/50 border-b border-slate-800/80">
                <span className="text-[10px] font-bold  text-slate-400 block mb-2">
                  Context-Aware Commands
                </span>
                <div className="flex flex-wrap gap-2">
                  {suggestions.map((s, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSendMessage(s.prompt)}
                      className="px-2.5 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-750 border border-slate-700/80 hover:border-emerald-500/40 text-xs text-slate-200 hover:text-[var(--color-ink)] transition flex items-center space-x-1.5 text-left"
                    >
                      <Sparkles className="w-3 h-3 text-emerald-400 shrink-0" />
                      <span>{s.title}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Scrollable Conversation Stream */}
            <div
              ref={scrollRef}
              role="log"
              aria-live="polite"
              aria-label="AI Command Conversation History"
              className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-5"
            >
              {messages.length === 0 && (
                <div className="py-14 text-center max-w-md mx-auto space-y-3">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto">
                    <Database className="w-6 h-6" />
                  </div>
                  <h3 className="text-sm font-bold text-[var(--color-ink)]">Unified Career Intelligence</h3>
                  <p className="text-xs text-slate-400 leading-relaxed">
                    Query your 205 live database opportunities, audit follow-ups, compare internships, generate tailored resumes, and prepare for interviews without navigating between tabs.
                  </p>
                  <div className="p-3 rounded-xl bg-slate-950 border border-slate-800 text-[11px] text-slate-400 text-left space-y-1">
                    <span className="font-semibold text-slate-300 block">Try asking:</span>
                    <div>• "Find AI internships matching my profile"</div>
                    <div>• "Compare these three opportunities"</div>
                    <div>• "Which applications need follow-up?"</div>
                    <div>• "Update application for Gateway Software to Interviewing"</div>
                  </div>
                </div>
              )}

              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex flex-col ${msg.sender === 'user' ? 'items-end' : 'items-start'}`}
                >
                  {/* Sender & Tool Badge */}
                  <div className="flex items-center space-x-2 mb-1 px-1">
                    <span className="text-[10px] font-mono text-slate-400">
                      {msg.sender === 'user' ? 'You' : 'CareerOS AI'}
                    </span>
                    {msg.tool_executed && (
                      <span className="px-1.5 py-0.2 rounded text-[9px] font-mono bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 flex items-center space-x-1">
                        <CheckCircle2 className="w-2.5 h-2.5" />
                        <span>{msg.tool_executed}</span>
                      </span>
                    )}
                  </div>

                  {/* Message Bubble */}
                  <div
                    className={`max-w-[92%] rounded-xl p-4 text-xs leading-relaxed ${
                      msg.sender === 'user'
                        ? 'bg-emerald-500 text-slate-950 font-medium rounded-br-none'
                        : 'bg-slate-950 border border-slate-800 text-slate-200 rounded-bl-none w-full'
                    }`}
                  >
                    <div className="whitespace-pre-wrap font-sans space-y-2">
                      {msg.content}
                    </div>

                    {/* Consequential Action Card */}
                    {msg.action_proposal && (
                      <div className="mt-4 p-3.5 rounded-xl bg-amber-950/20 border border-amber-500/30 space-y-3">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-2 text-amber-400">
                            <ShieldAlert className="w-4 h-4 shrink-0" />
                            <span className="font-bold text-xs">Consequential Operation Proposed</span>
                          </div>
                          <Badge
                            variant={
                              msg.action_proposal.status === 'executed'
                                ? 'emerald'
                                : msg.action_proposal.status === 'rejected'
                                ? 'rose'
                                : 'amber'
                            }
                            size="sm"
                          >
                            {msg.action_proposal.status.replace('_', ' ').toUpperCase()}
                          </Badge>
                        </div>

                        <p className="text-xs text-[var(--color-ink)] font-medium">
                          {msg.action_proposal.description}
                        </p>

                        {/* Data Payload Inspection */}
                        <div className="p-2.5 rounded-lg bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300">
                          <span className="text-slate-500 text-[10px] block mb-1">DATA PAYLOAD:</span>
                          <pre className="whitespace-pre-wrap overflow-x-auto text-[10px]">
                            {JSON.stringify(msg.action_proposal.data_payload, null, 2)}
                          </pre>
                        </div>

                        {/* Action Decision Controls */}
                        {msg.action_proposal.status === 'pending_approval' && (
                          <div className="flex items-center space-x-2 pt-1">
                            <Button
                              variant="primary"
                              size="sm"
                              isLoading={actionLoadingId === msg.action_proposal.action_id}
                              onClick={() => handleApproveAction(msg.id, msg.action_proposal!.action_id)}
                              aria-label={`Approve and execute ${msg.action_proposal.tool_name}`}
                              leftIcon={<CheckCircle2 className="w-3.5 h-3.5" />}
                            >
                              Approve & Execute
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={actionLoadingId === msg.action_proposal.action_id}
                              onClick={() => handleRejectAction(msg.id, msg.action_proposal!.action_id)}
                              aria-label={`Reject proposal for ${msg.action_proposal.tool_name}`}
                              leftIcon={<XCircle className="w-3.5 h-3.5 text-rose-400" />}
                            >
                              Reject
                            </Button>
                          </div>
                        )}

                        {msg.action_proposal.status === 'executed' && (
                          <div className="flex items-center space-x-1.5 text-emerald-400 text-xs font-semibold">
                            <CheckCircle2 className="w-4 h-4" />
                            <span>{msg.action_proposal.result_summary || 'Action verified and applied.'}</span>
                          </div>
                        )}

                        {msg.action_proposal.status === 'rejected' && (
                          <div className="flex items-center space-x-1.5 text-rose-400 text-xs font-semibold">
                            <XCircle className="w-4 h-4" />
                            <span>Action was declined by user. No database changes were applied.</span>
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Suggested Follow-up Action Chips */}
                  {msg.suggested_actions && msg.suggested_actions.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2 ml-1">
                      {msg.suggested_actions.map((act, idx) => (
                        <button
                          key={idx}
                          onClick={() => handleSendMessage(act)}
                          className="px-2 py-1 rounded bg-slate-800/80 hover:bg-slate-750 border border-slate-700 text-[11px] text-slate-300 hover:text-[var(--color-ink)] transition flex items-center space-x-1"
                        >
                          <span>{act}</span>
                          <ArrowRight className="w-2.5 h-2.5 text-slate-500" />
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {/* Live Loading Indicator */}
              {isLoading && (
                <div className="flex flex-col items-start space-y-1">
                  <div className="flex items-center space-x-2 px-1">
                    <span className="text-[10px] font-mono text-emerald-400 animate-pulse">
                      {currentTool || 'Synthesizing career advice...'}
                    </span>
                  </div>
                  <div className="p-3.5 rounded-xl rounded-bl-none bg-slate-950 border border-slate-800 text-xs text-slate-400 flex items-center space-x-2">
                    <RotateCw className="w-3.5 h-3.5 text-emerald-400 animate-spin" />
                    <span>Executing structured query against PostgreSQL database...</span>
                  </div>
                </div>
              )}
            </div>

            {/* Input Bar with IME-safe handling */}
            <div className="p-3.5 bg-slate-950 border-t border-slate-800 shrink-0 space-y-2">
              <div className="relative flex items-center">
                <textarea
                  ref={inputRef}
                  id="ai-command-prompt"
                  aria-label="Ask CareerOS AI command center or run an action"
                  value={inputPrompt}
                  onChange={(e) => setInputPrompt(e.target.value)}
                  onKeyDown={handleInputKeyDown}
                  placeholder="Ask anything or run actions (e.g. 'Which applications need follow-up?')..."
                  rows={2}
                  className="w-full bg-slate-900 border border-slate-750 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 rounded-xl pl-3.5 pr-12 py-2.5 text-xs text-[var(--color-ink)] placeholder-slate-400 focus:outline-none resize-none-inner"
                />
                <button
                  type="button"
                  onClick={() => handleSendMessage()}
                  disabled={!inputPrompt.trim() || isLoading}
                  aria-label="Send AI command"
                  aria-busy={isLoading}
                  className={`absolute right-2.5 p-2 rounded-lg transition focus-visible:ring-1 focus-visible:ring-emerald-500 ${
                    inputPrompt.trim() && !isLoading
                      ? 'bg-emerald-500 text-slate-950 hover:bg-emerald-400 font-bold'
                      : 'bg-slate-800 text-slate-500 cursor-not-allowed'
                  }`}
                  title="Send (Enter)"
                >
                  <Send className="w-3.5 h-3.5" aria-hidden="true" />
                </button>
              </div>

              <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono px-1">
                <span>↵ to send · Shift+↵ for newline</span>
                <span>ESC to close</span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};
