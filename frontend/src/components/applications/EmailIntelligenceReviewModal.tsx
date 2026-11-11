import React, { useState, useEffect, useCallback } from 'react';
import {
  Mail,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Video,
  ExternalLink,
  ChevronDown,
  ChevronUp,
  Search,
  Sparkles,
  X,
  Calendar,
  Building,
  Check
} from 'lucide-react';
import { EmailMessageRecord, ApplicationRecord } from '../../types';
import {
  fetchEmailIntelligenceMessages,
  approveEmailUpdate,
  dismissEmailUpdate,
  associateEmailToApplication,
  parseRawEmail
} from '../../services/api';

interface EmailIntelligenceReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  applications: ApplicationRecord[];
  onApplicationUpdated?: () => void;
  onNavigateToInterviewPrep?: (company?: string, role?: string) => void;
}

export const EmailIntelligenceReviewModal: React.FC<EmailIntelligenceReviewModalProps> = ({
  isOpen,
  onClose,
  applications,
  onApplicationUpdated,
  onNavigateToInterviewPrep
}) => {
  const [activeTab, setActiveTab] = useState<'pending' | 'all' | 'approved' | 'dismissed' | 'raw_test'>('pending');
  const [messages, setMessages] = useState<EmailMessageRecord[]>([]);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [actionInProgressId, setActionInProgressId] = useState<number | null>(null);

  // Manual raw email parse state
  const [rawSubject, setRawSubject] = useState<string>('');
  const [rawBody, setRawBody] = useState<string>('');
  const [rawSender, setRawSender] = useState<string>('recruiting@company.com');
  const [rawParsing, setRawParsing] = useState<boolean>(false);
  const [rawResult, setRawResult] = useState<any | null>(null);
  const [rawError, setRawError] = useState<string | null>(null);

  const loadMessages = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const reviewStatus =
        activeTab === 'pending'
          ? 'pending_review'
          : activeTab === 'approved'
          ? 'approved'
          : activeTab === 'dismissed'
          ? 'dismissed'
          : undefined;

      const res = await fetchEmailIntelligenceMessages({
        review_status: reviewStatus,
        page_size: 50
      });

      setMessages(res.items || []);
      setPendingCount(res.pending_review_count || 0);
    } catch (err: any) {
      console.error('Failed to load email messages:', err);
      setError('Unable to load emails. Verify the backend service is running.');
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    if (isOpen && activeTab !== 'raw_test') {
      loadMessages();
    }
  }, [isOpen, activeTab, loadMessages]);

  if (!isOpen) return null;

  const handleApprove = async (msgId: number) => {
    setActionInProgressId(msgId);
    try {
      await approveEmailUpdate(msgId);
      // Refresh list and notify parent
      await loadMessages();
      if (onApplicationUpdated) onApplicationUpdated();
    } catch (err: any) {
      alert(`Approval error: ${err.message || 'Failed to update application'}`);
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleDismiss = async (msgId: number) => {
    setActionInProgressId(msgId);
    try {
      await dismissEmailUpdate(msgId);
      await loadMessages();
      if (onApplicationUpdated) onApplicationUpdated();
    } catch (err: any) {
      alert(`Dismiss error: ${err.message || 'Failed to dismiss email'}`);
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleAssociate = async (msgId: number, targetAppId: number) => {
    setActionInProgressId(msgId);
    try {
      await associateEmailToApplication(msgId, targetAppId);
      await loadMessages();
    } catch (err: any) {
      alert(`Associate error: ${err.message || 'Failed to link application'}`);
    } finally {
      setActionInProgressId(null);
    }
  };

  const handleParseRaw = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!rawSubject.trim() || !rawBody.trim()) {
      setRawError('Please enter both subject and body text.');
      return;
    }
    setRawParsing(true);
    setRawError(null);
    setRawResult(null);
    try {
      const res = await parseRawEmail({
        subject: rawSubject.trim(),
        body_text: rawBody.trim(),
        sender: rawSender.trim()
      });
      setRawResult(res);
      // Reload pending counts in background
      fetchEmailIntelligenceMessages({ page_size: 1 })
        .then((r) => setPendingCount(r.pending_review_count || 0))
        .catch(() => {});
    } catch (err: any) {
      setRawError(err.message || 'Failed to parse raw email.');
    } finally {
      setRawParsing(false);
    }
  };

  const getCategoryBadge = (cat: string) => {
    const formatted = cat.replace(/_/g, ' ');
    switch (cat) {
      case 'interview_invitation':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold border border-sky-400/25 bg-sky-400/[0.06] text-sky-300 flex items-center space-x-1">
            <Video className="w-3 h-3 text-sky-300" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
      case 'offer_letter':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30 flex items-center space-x-1">
            <Sparkles className="w-3 h-3 text-amber-400" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
      case 'assessment_test':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 flex items-center space-x-1">
            <Clock className="w-3 h-3 text-cyan-400" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
      case 'application_confirmation':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3 text-emerald-400" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
      case 'rejection':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-500/15 text-rose-300 border border-rose-500/30 flex items-center space-x-1">
            <XCircle className="w-3 h-3 text-rose-400" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
      case 'shortlisting_screening':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-teal-500/15 text-teal-300 border border-teal-500/30 flex items-center space-x-1">
            <Check className="w-3 h-3 text-teal-400" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
      case 'recruiter_outreach':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-blue-500/15 text-blue-300 border border-blue-500/30 flex items-center space-x-1">
            <Mail className="w-3 h-3 text-blue-400" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-slate-700/40 text-slate-300 border border-slate-600/30 flex items-center space-x-1">
            <Mail className="w-3 h-3 text-slate-400" />
            <span className="capitalize">{formatted}</span>
          </span>
        );
    }
  };

  const filteredMessages = messages.filter((msg) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      msg.subject.toLowerCase().includes(query) ||
      msg.sender.toLowerCase().includes(query) ||
      msg.application_company?.toLowerCase().includes(query) ||
      msg.extracted_data?.company_name?.toLowerCase().includes(query) ||
      msg.extracted_data?.role_title?.toLowerCase().includes(query)
    );
  });

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="email-intelligence-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-5 bg-slate-950/80 backdrop-blur-sm animate-in fade-in duration-200"
    >
      <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-white/[0.07] flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center space-x-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-[var(--color-rule-2)] bg-[var(--color-paper-3)] text-[var(--color-accent)]">
              <Mail className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 id="email-intelligence-modal-title" className="text-base font-bold text-[var(--color-ink)]">
                  Email & Calendar Intelligence
                </h2>
                {pendingCount > 0 && (
                  <span className="px-2 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30">
                    {pendingCount} Pending Review
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                AI classifies incoming emails, extracts interviews, deadlines, and suggests tracker updates.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close Email Intelligence Modal"
            className="p-2 text-slate-400 hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-3)] rounded-lg transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Filter Navigation Tabs */}
        <div className="px-4 py-2.5 border-b border-white/[0.07] bg-[var(--color-paper-2)] flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="flex items-center space-x-1.5 overflow-x-auto">
            <button
              type="button"
              onClick={() => setActiveTab('pending')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition flex items-center space-x-1.5 ${
                activeTab === 'pending'
                  ? 'bg-amber-500/15 text-amber-300 border border-amber-500/30'
                  : 'text-slate-400 hover:text-[var(--color-ink)]'
              }`}
            >
              <span>Pending Review</span>
              {pendingCount > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-amber-500 text-slate-950 font-bold font-mono">
                  {pendingCount}
                </span>
              )}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('all')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                activeTab === 'all'
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-[var(--color-ink)]'
              }`}
            >
              All Detected Emails
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('approved')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                activeTab === 'approved'
                  ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-[var(--color-ink)]'
              }`}
            >
              Approved Updates
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('dismissed')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition ${
                activeTab === 'dismissed'
                  ? 'bg-slate-700/50 text-slate-300 border border-slate-600'
                  : 'text-slate-400 hover:text-[var(--color-ink)]'
              }`}
            >
              Dismissed
            </button>

            <button
              type="button"
              onClick={() => setActiveTab('raw_test')}
              className={`px-3 py-1.5 rounded-lg font-semibold transition flex items-center space-x-1 ${
                activeTab === 'raw_test'
                  ? 'bg-blue-500/15 text-blue-300 border border-blue-500/30'
                  : 'text-slate-400 hover:text-[var(--color-ink)]'
              }`}
            >
              <Sparkles className="w-3 h-3 text-blue-400" />
              <span>Paste & Test Email</span>
            </button>
          </div>

          {activeTab !== 'raw_test' && (
            <div className="relative w-full sm:w-56">
              <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search subject, company..."
                className="w-full bg-slate-950 border border-white/[0.07] rounded-lg pl-8 pr-3 py-1 text-xs text-[var(--color-ink)] placeholder-slate-500 focus:outline-none focus:border-emerald-500"
              />
            </div>
          )}
        </div>

        {/* Modal Body */}
        <div className="p-4 sm:p-5 overflow-y-auto flex-1 space-y-4">
          {activeTab === 'raw_test' ? (
            /* Paste & Test View */
            <div className="space-y-4">
              <div className="bg-slate-950/60 border border-white/[0.07] rounded-xl p-4 space-y-3">
                <div className="flex items-center space-x-2 text-xs text-slate-300 font-semibold">
                  <Sparkles className="w-4 h-4 text-emerald-400" />
                  <span>Manual Email Parser & Sandbox Tester</span>
                </div>
                <p className="text-xs text-slate-400">
                  Paste the text or HTML of any email to test 10-category AI classification, structured entity extraction (dates, meeting links, action items), and tracker stage recommendation without sending live API requests.
                </p>

                <form onSubmit={handleParseRaw} className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">
                        Sender Email
                      </label>
                      <input
                        type="text"
                        value={rawSender}
                        onChange={(e) => setRawSender(e.target.value)}
                        placeholder="e.g. recruiting@stripe.com"
                        className="w-full bg-[var(--color-paper-2)] border border-white/[0.09] rounded-lg px-3 py-1.5 text-xs text-[var(--color-ink)] placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[11px] font-medium text-slate-400 mb-1">
                        Subject Line *
                      </label>
                      <input
                        type="text"
                        required
                        value={rawSubject}
                        onChange={(e) => setRawSubject(e.target.value)}
                        placeholder="e.g. Invitation to Technical Screen: Stripe Backend Intern"
                        className="w-full bg-[var(--color-paper-2)] border border-white/[0.09] rounded-lg px-3 py-1.5 text-xs text-[var(--color-ink)] placeholder-slate-500 focus:outline-none focus:border-emerald-500"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-[11px] font-medium text-slate-400 mb-1">
                      Email Body (Plain Text or HTML) *
                    </label>
                    <textarea
                      required
                      rows={5}
                      value={rawBody}
                      onChange={(e) => setRawBody(e.target.value)}
                      placeholder="Hi Alex, We were impressed with your application and would like to schedule a 45-minute technical interview. Please join using Google Meet: https://meet.google.com/xyz-abcd-efg on Oct 25 at 3 PM..."
                      className="w-full bg-[var(--color-paper-2)] border border-white/[0.09] rounded-lg p-3 text-xs text-[var(--color-ink)] placeholder-slate-500 focus:outline-none focus:border-emerald-500 font-mono"
                    />
                  </div>

                  {rawError && (
                    <div className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 p-2.5 rounded-lg flex items-center space-x-2">
                      <AlertTriangle className="w-4 h-4 shrink-0" />
                      <span>{rawError}</span>
                    </div>
                  )}

                  <div className="flex items-center justify-between pt-1">
                    <button
                      type="button"
                      onClick={() => {
                        setRawSubject('Invitation to Technical Screen: Stripe Backend Intern');
                        setRawSender('recruiting@stripe.com');
                        setRawBody(
                          'Hi Alex,\n\nWe would love to invite you to a 45-minute technical screen for the Backend Engineering Internship position at Stripe.\n\nPlease join via Google Meet: https://meet.google.com/abc-defg-hij on Friday at 2:00 PM EST.\n\nBest,\nStripe Recruiting Team'
                        );
                      }}
                      className="text-xs text-slate-400 hover:text-emerald-400 transition"
                    >
                      Fill Example Invitation
                    </button>

                    <button
                      type="submit"
                      disabled={rawParsing}
                      className="whitespace-nowrap px-4 py-2 bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] rounded-lg text-xs font-semibold flex items-center space-x-1.5 transition disabled:opacity-50"
                    >
                      {rawParsing ? (
                        <>
                          <Clock className="whitespace-nowrap w-3.5 h-3.5 animate-spin" />
                          <span>Parsing…</span>
                        </>
                      ) : (
                        <>
                          <Sparkles className="w-3.5 h-3.5" />
                          <span>Analyze</span>
                        </>
                      )}
                    </button>
                  </div>
                </form>
              </div>

              {/* Raw parse output */}
              {rawResult && (
                <div className="bg-slate-950 border border-emerald-500/30 rounded-xl p-4 space-y-3 animate-in fade-in">
                  <div className="flex items-center justify-between border-b border-white/[0.07] pb-2">
                    <div className="flex items-center space-x-2">
                      <span className="text-xs font-semibold text-[var(--color-ink)]">Parsed Classification:</span>
                      {getCategoryBadge(rawResult.detected_category)}
                    </div>
                    <span className="text-[11px] font-mono text-emerald-400">
                      {(rawResult.confidence_score * 100).toFixed(0)}% Confidence
                    </span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                    <div>
                      <span className="text-slate-400 block text-[10px] ">Detected Company</span>
                      <span className="font-semibold text-[var(--color-ink)]">
                        {rawResult.extracted_data?.company_name || 'None detected'}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 block text-[10px] ">Detected Role</span>
                      <span className="font-semibold text-[var(--color-ink)]">
                        {rawResult.extracted_data?.role_title || 'None detected'}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 block text-[10px] ">Suggested Pipeline Stage</span>
                      <span className="font-semibold text-amber-400 capitalize">
                        {rawResult.suggested_stage ? rawResult.suggested_stage.replace('_', ' ') : 'None'}
                      </span>
                    </div>

                    <div>
                      <span className="text-slate-400 block text-[10px] ">Meeting Link</span>
                      {rawResult.extracted_data?.meeting_link ? (
                        <a
                          href={rawResult.extracted_data.meeting_link}
                          target="_blank"
                          rel="noreferrer"
                          className="text-emerald-400 hover:underline flex items-center space-x-1"
                        >
                          <Video className="w-3 h-3 text-emerald-400" />
                          <span className="truncate max-w-[200px]">
                            {rawResult.extracted_data.meeting_platform || 'Link'}: {rawResult.extracted_data.meeting_link}
                          </span>
                        </a>
                      ) : (
                        <span className="text-slate-500">None detected</span>
                      )}
                    </div>
                  </div>

                  {rawResult.application_id && (
                    <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300">
                      Matched to Application #{rawResult.application_id} (Status: {rawResult.review_status}). Saved to email inbox.
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : loading ? (
            <div className="p-12 text-center text-slate-400 space-y-2">
              <Clock className="w-6 h-6 animate-spin mx-auto text-slate-500" />
              <p className="text-xs">Loading career emails...</p>
            </div>
          ) : error ? (
            <div className="p-6 text-center text-rose-400 bg-rose-500/10 border border-rose-500/20 rounded-xl space-y-2">
              <AlertTriangle className="w-6 h-6 mx-auto" />
              <p className="text-xs font-semibold">{error}</p>
              <button
                type="button"
                onClick={loadMessages}
                className="px-3 py-1 bg-white/[0.04] hover:bg-white/[0.07] text-[var(--color-ink)] rounded text-xs"
              >
                Retry
              </button>
            </div>
          ) : filteredMessages.length === 0 ? (
            <div className="p-12 text-center text-slate-500 bg-slate-950/40 border border-white/[0.07] rounded-xl space-y-2">
              <Mail className="w-8 h-8 mx-auto text-slate-600" />
              <h3 className="text-sm font-semibold text-slate-300">
                {activeTab === 'pending'
                  ? 'No pending email updates'
                  : 'No emails found matching your filter'}
              </h3>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                {activeTab === 'pending'
                  ? 'Great job! All detected career communications have been reviewed. Connect an account in Settings or use "Paste & Test Email" to test.'
                  : 'Try adjusting your search query or connect a provider in Connected Accounts.'}
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {filteredMessages.map((msg) => {
                const isExpanded = expandedId === msg.id;
                const isActioning = actionInProgressId === msg.id;
                const formattedDate = msg.received_at
                  ? new Date(msg.received_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit'
                    })
                  : '';

                const meetingLink = msg.extracted_data?.meeting_link;
                const meetingPlatform = msg.extracted_data?.meeting_platform || 'Video Call';
                const hasSuggestedStage = Boolean(msg.suggested_stage);
                const currentStage = msg.application_status || 'unknown';

                return (
                  <div
                    key={msg.id}
                    className={`border rounded-xl transition ${
                      msg.review_status === 'pending_review'
                        ? 'bg-slate-950 border-amber-500/30'
                        : 'bg-slate-950/50 border-white/[0.07]'
                    }`}
                  >
                    {/* Header Row */}
                    <div className="p-3.5 sm:p-4 space-y-2">
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                        <div className="flex items-center space-x-2 flex-wrap gap-y-1">
                          {getCategoryBadge(msg.detected_category)}

                          {msg.is_low_confidence ? (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center space-x-1" title="Confidence is below 85%">
                              <AlertTriangle className="w-2.5 h-2.5" />
                              <span>Low Confidence ({Math.round(msg.confidence_score * 100)}%)</span>
                            </span>
                          ) : (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-mono text-slate-400 border border-white/[0.07] bg-[var(--color-paper)]">
                              {Math.round(msg.confidence_score * 100)}% Match
                            </span>
                          )}

                          {msg.review_status === 'approved' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1">
                              <CheckCircle2 className="w-2.5 h-2.5" />
                              <span>Approved</span>
                            </span>
                          )}
                          {msg.review_status === 'dismissed' && (
                            <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-[var(--color-paper-3)] text-slate-400 border border-white/[0.09]">
                              Dismissed
                            </span>
                          )}
                        </div>

                        <span className="text-[11px] text-slate-500 font-mono">
                          {formattedDate}
                        </span>
                      </div>

                      {/* Subject & Sender */}
                      <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-1">
                        <h3 className="text-sm font-semibold text-[var(--color-ink)] group flex items-center space-x-2">
                          <span>{msg.subject}</span>
                        </h3>
                        <span className="text-xs text-slate-400 font-mono truncate max-w-xs">
                          {msg.sender_name ? `${msg.sender_name} <${msg.sender_email}>` : msg.sender}
                        </span>
                      </div>

                      {/* Application association */}
                      <div className="flex flex-wrap items-center gap-2 pt-1 text-xs">
                        {msg.application_id ? (
                          <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border border-white/[0.07] bg-[var(--color-paper)] text-slate-300">
                            <Building className="w-3 h-3 text-slate-400" />
                            <span className="font-semibold text-[var(--color-ink)]">
                              {msg.application_company || msg.extracted_data?.company_name}
                            </span>
                            <span className="text-slate-500">•</span>
                            <span className="text-slate-400">
                              {msg.application_title || msg.extracted_data?.role_title || 'Application'}
                            </span>
                            <span className="text-slate-500">|</span>
                            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-[var(--color-paper-3)] text-slate-300 ">
                              {currentStage}
                            </span>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-2 text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2.5 py-1 rounded-lg text-xs">
                            <AlertTriangle className="w-3 h-3" />
                            <span>Unlinked Application. Associate:</span>
                            <select
                              aria-label="Associate email with an existing application"
                              onChange={(e) => {
                                const appId = Number(e.target.value);
                                if (appId) handleAssociate(msg.id, appId);
                              }}
                              className="bg-[var(--color-paper-2)] border border-white/[0.09] rounded px-2 py-0.5 text-xs text-[var(--color-ink)] focus:outline-none"
                              defaultValue=""
                            >
                              <option value="" disabled>Select application...</option>
                              {applications.map((app) => (
                                <option key={app.id} value={app.id}>
                                  {app.company_name} - {app.job_title}
                                </option>
                              ))}
                            </select>
                          </div>
                        )}

                        {meetingLink && (
                          <a
                            href={meetingLink}
                            target="_blank"
                            rel="noreferrer"
                            className="px-2.5 py-1 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 text-emerald-300 border border-emerald-500/30 flex items-center space-x-1 text-xs font-semibold transition"
                          >
                            <Video className="w-3.5 h-3.5 text-emerald-400" />
                            <span>Join {meetingPlatform}</span>
                            <ExternalLink className="w-3 h-3 text-emerald-400" />
                          </a>
                        )}

                        {msg.extracted_data?.deadline_text && (
                          <span className="px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-300 border border-rose-500/20 flex items-center space-x-1 text-xs">
                            <Calendar className="w-3 h-3 text-rose-400" />
                            <span>Deadline: {msg.extracted_data.deadline_text}</span>
                          </span>
                        )}
                      </div>

                      {/* Snippet */}
                      {msg.snippet && (
                        <p className="text-xs text-slate-300 bg-[var(--color-paper-2)] p-2.5 rounded-lg border border-white/[0.07]/80 leading-relaxed font-sans">
                          {msg.snippet}
                        </p>
                      )}

                      {/* Expandable full body */}
                      {isExpanded && msg.body_plain && (
                        <div className="p-3 border border-white/[0.07] bg-[var(--color-paper)] rounded-lg text-xs font-mono text-slate-300 whitespace-pre-wrap max-h-60 overflow-y-auto leading-relaxed">
                          {msg.body_plain}
                        </div>
                      )}

                      {/* Consequential Stage Approval Banner (if pending review and has suggestion) */}
                      {msg.review_status === 'pending_review' && hasSuggestedStage && (
                        <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 mt-2">
                          <div className="space-y-0.5">
                            <div className="flex items-center space-x-2 text-xs font-bold text-amber-300">
                              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                              <span>
                                Recommended Stage Update: <span className="capitalize">{currentStage.replace('_', ' ')}</span> ➔ <span className="text-emerald-400 capitalize">{msg.suggested_stage?.replace('_', ' ')}</span>
                              </span>
                            </div>
                            <p className="text-[11px] text-slate-400">
                              No tracker stage changes are made without your explicit permission.
                            </p>
                          </div>

                          <div className="flex items-center space-x-2 shrink-0">
                            <button
                              type="button"
                              onClick={() => handleDismiss(msg.id)}
                              disabled={isActioning}
                              className="px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.07] text-slate-300 text-xs font-semibold transition disabled:opacity-50"
                            >
                              Dismiss
                            </button>
                            <button
                              type="button"
                              onClick={() => handleApprove(msg.id)}
                              disabled={isActioning}
                              className="px-3.5 py-1.5 rounded-lg bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-semibold flex items-center space-x-1.5 transition disabled:opacity-50"
                            >
                              <Check className="w-3.5 h-3.5" />
                              <span>{isActioning ? 'Updating...' : 'Approve Update'}</span>
                            </button>
                          </div>
                        </div>
                      )}

                      {/* Action footer */}
                      <div className="flex items-center justify-between pt-2 border-t border-white/[0.07]/60 text-xs">
                        <button
                          type="button"
                          onClick={() => setExpandedId(isExpanded ? null : msg.id)}
                          className="whitespace-nowrap text-slate-400 hover:text-slate-200 flex items-center space-x-1 transition text-[11px]"
                        >
                          {isExpanded ? (
                            <>
                              <ChevronUp className="whitespace-nowrap w-3 h-3" />
                              <span>Hide email</span>
                            </>
                          ) : (
                            <>
                              <ChevronDown className="w-3 h-3" />
                              <span>Show email</span>
                            </>
                          )}
                        </button>

                        <div className="flex items-center space-x-2">
                          {(msg.detected_category === 'interview_invitation' || meetingLink) && onNavigateToInterviewPrep && (
                            <button
                              type="button"
                              onClick={() => {
                                onNavigateToInterviewPrep(
                                  msg.application_company || msg.extracted_data?.company_name,
                                  msg.application_title || msg.extracted_data?.role_title
                                );
                                onClose();
                              }}
                              className="px-2.5 py-1 rounded bg-purple-500/15 hover:bg-purple-500/25 text-sky-300 border border-purple-500/30 flex items-center space-x-1 text-xs font-semibold transition"
                            >
                              <Sparkles className="w-3 h-3 text-sky-300" />
                              <span>Prepare for Interview</span>
                            </button>
                          )}

                          {msg.review_status === 'pending_review' && !hasSuggestedStage && (
                            <button
                              type="button"
                              onClick={() => handleDismiss(msg.id)}
                              disabled={isActioning}
                              className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200 bg-white/[0.04] hover:bg-white/[0.07] rounded transition"
                            >
                              Dismiss
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3.5 border-t border-white/[0.07] bg-slate-950/60 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center space-x-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
            <span>All sensitive credentials encrypted with Fernet AES-128-CBC at rest.</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-1.5 bg-white/[0.04] hover:bg-white/[0.07] text-slate-200 rounded-lg text-xs font-medium transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
