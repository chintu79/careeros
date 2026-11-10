import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  Sparkles,
  AlertTriangle,
  Clock,
  Video,
  Calendar,
  Mail,
  Copy,
  Check,
  ShieldCheck,
  Send,
  Building,
  User,
  ChevronRight,
  ExternalLink,
  RefreshCw,
  X
} from 'lucide-react';
import {
  FollowUpIntelligenceData,
  FollowUpAlertItem,
  FollowUpDraftResponse,
  ApplicationRecord
} from '../../types';
import {
  fetchFollowUpAlerts,
  generateFollowUpEmail,
  approveFollowUpEmail
} from '../../services/api';

interface FollowUpIntelligenceModalProps {
  isOpen: boolean;
  onClose: () => void;
  preselectedApp?: ApplicationRecord | null;
  onActionComplete?: () => void;
}

export const FollowUpIntelligenceModal: React.FC<FollowUpIntelligenceModalProps> = ({
  isOpen,
  onClose,
  preselectedApp,
  onActionComplete
}) => {
  const [data, setData] = useState<FollowUpIntelligenceData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [staleThreshold, setStaleThreshold] = useState<number>(7);
  const [activeTab, setActiveTab] = useState<'unanswered' | 'follow_ups' | 'interviews' | 'deadlines'>('unanswered');

  // Generator State
  const [selectedAppId, setSelectedAppId] = useState<number | null>(preselectedApp?.id || null);
  const [draft, setDraft] = useState<FollowUpDraftResponse | null>(null);
  const [tone, setTone] = useState<string>('inquisitive');
  const [customNote, setCustomNote] = useState<string>('');
  const [generatingDraft, setGeneratingDraft] = useState<boolean>(false);
  const [approving, setApproving] = useState<boolean>(false);
  const [copied, setCopied] = useState<boolean>(false);
  const [approvalSuccess, setApprovalSuccess] = useState<string | null>(null);

  // Latest-value refs: the modal-open effect must not re-run when the user
  // edits the tone picker or the custom note while drafts are being generated.
  const toneRef = useRef(tone);
  const customNoteRef = useRef(customNote);
  useEffect(() => {
    toneRef.current = tone;
    customNoteRef.current = customNote;
  });

  const loadAlerts = useCallback((threshold: number) => {
    setLoading(true);
    fetchFollowUpAlerts(threshold)
      .then((res) => {
        setData(res);
      })
      .catch((err) => {
        console.error('Failed to load follow-up alerts:', err);
      })
      .finally(() => setLoading(false));
  }, []);

  const handleGenerateDraft = useCallback(async (appId: number, selectedTone?: string) => {
    setGeneratingDraft(true);
    setApprovalSuccess(null);
    try {
      const t = selectedTone ?? toneRef.current;
      const res = await generateFollowUpEmail(appId, t, customNoteRef.current || undefined);
      setDraft(res);
    } catch (err: any) {
      alert(err.message || 'Failed to generate email draft');
    } finally {
      setGeneratingDraft(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadAlerts(staleThreshold);
      if (preselectedApp?.id) {
        setSelectedAppId(preselectedApp.id);
        handleGenerateDraft(preselectedApp.id);
      }
    }
  }, [isOpen, staleThreshold, preselectedApp, loadAlerts, handleGenerateDraft]);

  const handleApproveAndSend = async () => {
    if (!selectedAppId || !draft) return;
    setApproving(true);
    try {
      await approveFollowUpEmail(selectedAppId, 7, `Sent ${tone} follow-up email to ${draft.recipient_name || 'recruiter'}`);
      setApprovalSuccess('Follow-up approved and recorded! Next check-in scheduled for 7 days.');
      loadAlerts(staleThreshold);
      if (onActionComplete) onActionComplete();
    } catch (err: any) {
      alert(err.message || 'Failed to approve follow-up');
    } finally {
      setApproving(false);
    }
  };

  const handleCopy = () => {
    if (!draft) return;
    const fullText = `Subject: ${draft.subject}\n\n${draft.body}`;
    navigator.clipboard.writeText(fullText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-slate-950/85 backdrop-blur-sm overflow-y-auto">
      <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-white/[0.07] flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
              <Sparkles className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base sm:text-lg font-bold text-[var(--color-ink)] flex items-center space-x-2">
                <span>Follow-Up Intelligence & Communications Assistant</span>
              </h2>
              <p className="text-xs text-slate-400">
                Actionable triggers for unanswered applications, scheduled interviews, and approved email follow-ups.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1.5 rounded-lg text-slate-400 hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-3)] transition min-h-[28px] min-w-[28px] flex items-center justify-center focus-visible:ring-1 focus-visible:ring-emerald-500"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Guardrail Banner */}
        <div className="bg-emerald-950/40 border-b border-emerald-500/20 px-4 py-2.5 flex items-center justify-between text-xs text-emerald-300">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>
              <strong>Strict Guardrail:</strong> CareerOS will never automatically email a recruiter. Every draft requires explicit user review and approval.
            </span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-slate-400 text-[11px]">Unanswered threshold:</span>
            <select
              value={staleThreshold}
              onChange={(e) => setStaleThreshold(Number(e.target.value))}
              className="bg-[var(--color-paper-2)] border border-white/[0.09] rounded px-2 py-0.5 text-xs text-slate-200"
            >
              <option value={7}>7 Days</option>
              <option value={10}>10 Days</option>
              <option value={14}>14 Days</option>
              <option value={21}>21 Days</option>
            </select>
          </div>
        </div>

        {/* Content body: 2 columns */}
        <div className="grid grid-cols-1 lg:grid-cols-12 flex-1 overflow-hidden divide-y lg:divide-y-0 lg:divide-x divide-white/[0.07]">
          {/* Left Column: Alerts List */}
          <div className="lg:col-span-5 flex flex-col h-full max-h-[500px] lg:max-h-none overflow-hidden">
            {/* Tabs */}
            <div className="grid grid-cols-4 border-b border-white/[0.07] text-[11px] font-medium bg-slate-950/40">
              <button
                onClick={() => setActiveTab('unanswered')}
                className={`py-2.5 px-2 text-center transition border-b-2 flex flex-col items-center justify-center space-y-1 ${
                  activeTab === 'unanswered'
                    ? 'border-amber-400 text-amber-300 bg-amber-500/5'
                    : 'border-transparent text-slate-400 hover:text-[var(--color-ink)]'
                }`}
              >
                <span>Unanswered</span>
                <span className="px-1.5 py-0.2 rounded-full bg-[var(--color-paper-3)] text-[10px] font-mono">
                  {data?.summary.unanswered_count || 0}
                </span>
              </button>
              <button
                onClick={() => setActiveTab('follow_ups')}
                className={`py-2.5 px-2 text-center transition border-b-2 flex flex-col items-center justify-center space-y-1 ${
                  activeTab === 'follow_ups'
                    ? 'border-emerald-400 text-emerald-300 bg-emerald-500/5'
                    : 'border-transparent text-slate-400 hover:text-[var(--color-ink)]'
                }`}
              >
                <span>Follow-ups</span>
                <span className="px-1.5 py-0.2 rounded-full bg-[var(--color-paper-3)] text-[10px] font-mono">
                  {data?.summary.follow_up_due_count || 0}
                </span>
              </button>
              <button
                onClick={() => setActiveTab('interviews')}
                className={`py-2.5 px-2 text-center transition border-b-2 flex flex-col items-center justify-center space-y-1 ${
                  activeTab === 'interviews'
                    ? 'border-purple-400 text-sky-300 bg-purple-500/5'
                    : 'border-transparent text-slate-400 hover:text-[var(--color-ink)]'
                }`}
              >
                <span>Interviews</span>
                <span className="px-1.5 py-0.2 rounded-full bg-[var(--color-paper-3)] text-[10px] font-mono">
                  {data?.summary.upcoming_interviews_count || 0}
                </span>
              </button>
              <button
                onClick={() => setActiveTab('deadlines')}
                className={`py-2.5 px-2 text-center transition border-b-2 flex flex-col items-center justify-center space-y-1 ${
                  activeTab === 'deadlines'
                    ? 'border-rose-400 text-rose-300 bg-rose-500/5'
                    : 'border-transparent text-slate-400 hover:text-[var(--color-ink)]'
                }`}
              >
                <span>Deadlines</span>
                <span className="px-1.5 py-0.2 rounded-full bg-[var(--color-paper-3)] text-[10px] font-mono">
                  {data?.summary.approaching_deadlines_count || 0}
                </span>
              </button>
            </div>

            {/* List */}
            <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
              {loading ? (
                <div className="py-12 text-center text-slate-500 text-xs">
                  <RefreshCw className="w-5 h-5 mx-auto animate-spin mb-2" />
                  Analyzing pipeline alerts...
                </div>
              ) : (
                <>
                  {activeTab === 'unanswered' && (
                    <>
                      {(!data?.unanswered_applications || data.unanswered_applications.length === 0) ? (
                        <p className="text-xs text-slate-500 italic text-center py-8">
                          No applications pending beyond {staleThreshold} days.
                        </p>
                      ) : (
                        data.unanswered_applications.map((item) => (
                          <div
                            key={item.application_id}
                            onClick={() => {
                              setSelectedAppId(item.application_id);
                              handleGenerateDraft(item.application_id, tone);
                            }}
                            className={`p-3 rounded-xl border text-xs cursor-pointer transition space-y-1.5 ${
                              selectedAppId === item.application_id
                                ? 'bg-amber-500/10 border-amber-500/40 ring-1 ring-amber-500/30'
                                : 'bg-slate-950/60 border-white/[0.07] hover:border-white/[0.13]'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-[var(--color-ink)]">{item.company_name}</span>
                              <span className="text-[10px] text-amber-400 font-medium px-1.5 py-0.5 rounded bg-amber-500/10 border border-amber-500/20">
                                {item.days_elapsed} days waiting
                              </span>
                            </div>
                            <p className="text-slate-400">{item.job_title}</p>
                            <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                              <span>Applied: {item.applied_date ? new Date(item.applied_date).toLocaleDateString() : 'N/A'}</span>
                              <span className="text-emerald-400 font-medium flex items-center space-x-1">
                                <span>Draft Follow-up</span>
                                <ChevronRight className="w-3 h-3" />
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </>
                  )}

                  {activeTab === 'follow_ups' && (
                    <>
                      {(!data?.follow_ups_due || data.follow_ups_due.length === 0) ? (
                        <p className="text-xs text-slate-500 italic text-center py-8">
                          No scheduled follow-ups currently due.
                        </p>
                      ) : (
                        data.follow_ups_due.map((item) => (
                          <div
                            key={item.application_id}
                            onClick={() => {
                              setSelectedAppId(item.application_id);
                              handleGenerateDraft(item.application_id, tone);
                            }}
                            className={`p-3 rounded-xl border text-xs cursor-pointer transition space-y-1.5 ${
                              selectedAppId === item.application_id
                                ? 'bg-emerald-500/10 border-emerald-500/40 ring-1 ring-emerald-500/30'
                                : 'bg-slate-950/60 border-white/[0.07] hover:border-white/[0.13]'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-[var(--color-ink)]">{item.company_name}</span>
                              <span className="text-[10px] text-emerald-400 font-medium px-1.5 py-0.5 rounded bg-emerald-500/10 border border-emerald-500/20">
                                Follow-up Due
                              </span>
                            </div>
                            <p className="text-slate-400">{item.job_title}</p>
                            <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                              <span>Due: {item.follow_up_date ? new Date(item.follow_up_date).toLocaleDateString() : 'Now'}</span>
                              <span className="text-emerald-400 font-medium flex items-center space-x-1">
                                <span>Draft Email</span>
                                <ChevronRight className="w-3 h-3" />
                              </span>
                            </div>
                          </div>
                        ))
                      )}
                    </>
                  )}

                  {activeTab === 'interviews' && (
                    <>
                      {(!data?.upcoming_interviews || data.upcoming_interviews.length === 0) ? (
                        <p className="text-xs text-slate-500 italic text-center py-8">
                          No interviews scheduled in the next 7 days.
                        </p>
                      ) : (
                        data.upcoming_interviews.map((item, idx) => (
                          <div
                            key={idx}
                            onClick={() => {
                              setSelectedAppId(item.application_id);
                              handleGenerateDraft(item.application_id, 'thank_you');
                            }}
                            className="p-3 rounded-xl border border-white/[0.07] bg-slate-950/60 text-xs space-y-1.5 cursor-pointer hover:border-purple-500/50"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-[var(--color-ink)]">{item.company_name}</span>
                              <span className="text-[10px] text-sky-300 font-medium px-1.5 py-0.5 rounded bg-purple-500/10 border border-purple-500/20">
                                In {item.days_until} days
                              </span>
                            </div>
                            <p className="text-slate-400 font-medium">{item.round_name || 'Interview Round'}</p>
                            <div className="text-[11px] text-slate-500 space-y-0.5">
                              <div>Date: {item.date ? new Date(item.date).toLocaleString() : 'TBD'}</div>
                              {item.interviewer && <div>With: {item.interviewer}</div>}
                            </div>
                          </div>
                        ))
                      )}
                    </>
                  )}

                  {activeTab === 'deadlines' && (
                    <>
                      {(!data?.approaching_deadlines || data.approaching_deadlines.length === 0) ? (
                        <p className="text-xs text-slate-500 italic text-center py-8">
                          No opportunity deadlines expiring within 7 days.
                        </p>
                      ) : (
                        data.approaching_deadlines.map((item) => (
                          <div
                            key={item.application_id}
                            className="p-3 rounded-xl border border-white/[0.07] bg-slate-950/60 text-xs space-y-1.5"
                          >
                            <div className="flex items-center justify-between">
                              <span className="font-bold text-[var(--color-ink)]">{item.company_name}</span>
                              <span className="text-[10px] text-rose-400 font-medium px-1.5 py-0.5 rounded bg-rose-500/10 border border-rose-500/20">
                                {item.days_remaining} days left
                              </span>
                            </div>
                            <p className="text-slate-400">{item.job_title}</p>
                            <div className="flex items-center justify-between pt-1 text-[11px] text-slate-500">
                              <span>Deadline: {item.deadline ? new Date(item.deadline).toLocaleDateString() : 'N/A'}</span>
                              {item.original_url && (
                                <a
                                  href={item.original_url}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-emerald-400 hover:underline flex items-center space-x-1"
                                >
                                  <span>Apply Now</span>
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </>
                  )}
                </>
              )}
            </div>
          </div>

          {/* Right Column: AI Email Generator & Approval */}
          <div className="lg:col-span-7 p-4 sm:p-5 flex flex-col justify-between overflow-y-auto space-y-4">
            {selectedAppId ? (
              <>
                <div className="space-y-4">
                  {/* Tone selector & Controls */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-950/60 p-3 rounded-xl border border-white/[0.07]">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs text-slate-400">Tone:</span>
                      <select
                        value={tone}
                        onChange={(e) => {
                          setTone(e.target.value);
                          if (selectedAppId) handleGenerateDraft(selectedAppId, e.target.value);
                        }}
                        className="bg-[var(--color-paper-2)] border border-white/[0.09] rounded-lg px-2.5 py-1 text-xs text-[var(--color-ink)] focus:outline-none focus:border-emerald-500"
                      >
                        <option value="inquisitive">Inquisitive & Professional</option>
                        <option value="enthusiastic">Enthusiastic & High-Energy</option>
                        <option value="direct">Direct & Concise</option>
                        <option value="thank_you">Post-Interview Thank You</option>
                        <option value="portfolio_update">Project / Portfolio Update</option>
                      </select>
                    </div>

                    <button
                      onClick={() => handleGenerateDraft(selectedAppId, tone)}
                      disabled={generatingDraft}
                      className="px-3 py-1 bg-white/[0.04] hover:bg-white/[0.07] disabled:opacity-50 text-slate-200 rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${generatingDraft ? 'animate-spin' : ''}`} />
                      <span>Regenerate Draft</span>
                    </button>
                  </div>

                  {approvalSuccess && (
                    <div className="p-3 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-emerald-400 text-xs flex items-center space-x-2">
                      <Check className="w-4 h-4 shrink-0" />
                      <span>{approvalSuccess}</span>
                    </div>
                  )}

                  {/* Draft Preview */}
                  {generatingDraft ? (
                    <div className="py-16 text-center text-slate-500 text-xs">
                      <Sparkles className="w-6 h-6 mx-auto animate-pulse text-emerald-400 mb-2" />
                      Crafting personalized outreach email draft...
                    </div>
                  ) : draft ? (
                    <div className="space-y-3">
                      <div>
                        <label className="text-[11px] font-semibold  text-slate-400 block mb-1">
                          Subject Line
                        </label>
                        <input
                          type="text"
                          value={draft.subject}
                          onChange={(e) => setDraft({ ...draft, subject: e.target.value })}
                          className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-[var(--color-ink)] font-medium focus:outline-none focus:border-emerald-500"
                        />
                      </div>

                      <div>
                        <label className="text-[11px] font-semibold  text-slate-400 block mb-1">
                          Draft Body (Editable)
                        </label>
                        <textarea
                          rows={8}
                          value={draft.body}
                          onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                          className="w-full bg-slate-950 border border-white/[0.09] rounded-lg p-3 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none focus:border-emerald-500"
                        />
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slate-500">
                        <span>Recipient: {draft.recipient_name} ({draft.recipient_email || 'Public/General inbox'})</span>
                        <span className="italic">Tone: {draft.tone}</span>
                      </div>
                    </div>
                  ) : (
                    <div className="py-12 text-center text-slate-500 text-xs">
                      Select an application on the left to review or generate an email draft.
                    </div>
                  )}
                </div>

                {/* Footer Action Buttons */}
                {draft && (
                  <div className="pt-4 border-t border-white/[0.07] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">
                    <button
                      onClick={handleCopy}
                      className="px-3 py-2 bg-white/[0.04] hover:bg-white/[0.07] text-slate-200 rounded-lg text-xs font-semibold flex items-center justify-center space-x-1.5 transition"
                    >
                      {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                      <span>{copied ? 'Copied to Clipboard!' : 'Copy to Clipboard'}</span>
                    </button>

                    <button
                      onClick={handleApproveAndSend}
                      disabled={approving}
                      className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 text-slate-950 font-bold rounded-lg text-xs flex items-center justify-center space-x-1.5 transition"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>{approving ? 'Recording Approval...' : 'Approve & Mark Dispatched'}</span>
                    </button>
                  </div>
                )}
              </>
            ) : (
              <div className="py-24 text-center text-slate-500 space-y-3">
                <Sparkles className="w-8 h-8 text-slate-600 mx-auto" />
                <h4 className="text-sm font-semibold text-slate-300">No Application Selected</h4>
                <p className="text-xs text-slate-500 max-w-sm mx-auto">
                  Select an alert from the left panel to review follow-up triggers and prepare an AI email draft.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
