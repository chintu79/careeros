import React, { useState, useEffect, useCallback } from 'react';
import {
  Users,
  UserPlus,
  Search,
  Mail,
  Building,
  Briefcase,
  Calendar,
  MessageSquare,
  Plus,
  Trash2,
  Edit2,
  ExternalLink,
  ShieldCheck,
  CheckCircle2,
  Clock,
  Sparkles,
  Phone,
  FileText,
  AlertCircle
} from 'lucide-react';
import { RecruiterContact, RecruiterInteraction } from '../../types';
import {
  fetchRecruiters,
  createRecruiter,
  updateRecruiter,
  deleteRecruiter,
  logRecruiterInteraction
} from '../../services/api';

const Linkedin = ({ className = "w-3.5 h-3.5" }: { className?: string }) => (
  <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
    <rect width="4" height="12" x="2" y="9" />
    <circle cx="4" cy="4" r="2" />
  </svg>
);

export const RecruiterCRMView: React.FC = () => {
  const [recruiters, setRecruiters] = useState<RecruiterContact[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [searchTerm, setSearchTerm] = useState<string>('');
  const [companyFilter, setCompanyFilter] = useState<string>('all');
  const [selectedRecruiter, setSelectedRecruiter] = useState<RecruiterContact | null>(null);

  // Modals
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);
  const [isTouchpointModalOpen, setIsTouchpointModalOpen] = useState<boolean>(false);
  const [activeContactForTouchpoint, setActiveContactForTouchpoint] = useState<RecruiterContact | null>(null);

  // New Recruiter form
  const [newRecruiter, setNewRecruiter] = useState({
    name: '',
    email: '',
    linkedin_url: '',
    company: '',
    position: '',
    contact_source: 'LinkedIn Outreach',
    notes: ''
  });

  // Touchpoint form
  const [touchpointForm, setTouchpointForm] = useState({
    type: 'email',
    summary: '',
    date: new Date().toISOString().split('T')[0],
    follow_up_needed: true,
    next_step: ''
  });

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [formError, setFormError] = useState<string | null>(null);

  const loadRecruiters = useCallback(() => {
    setLoading(true);
    fetchRecruiters({ page_size: 100 })
      .then((data) => {
        const items = data.items || [];
        setRecruiters(items);
        setSelectedRecruiter((prev) => prev ?? (items.length > 0 ? items[0] : prev));
      })
      .catch((err) => {
        console.error('Failed to load recruiters:', err);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadRecruiters();
  }, [loadRecruiters]);

  const handleCreateRecruiter = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRecruiter.name.trim()) {
      setFormError('Recruiter name is required.');
      return;
    }

    setSubmitting(true);
    setFormError(null);
    try {
      const created = await createRecruiter(newRecruiter);
      setRecruiters([created, ...recruiters]);
      setSelectedRecruiter(created);
      setIsAddModalOpen(false);
      setNewRecruiter({
        name: '',
        email: '',
        linkedin_url: '',
        company: '',
        position: '',
        contact_source: 'LinkedIn Outreach',
        notes: ''
      });
    } catch (err: any) {
      setFormError(err.message || 'Failed to add recruiter');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteRecruiter = async (id: number) => {
    if (!window.confirm('Are you sure you want to remove this recruiter contact?')) return;
    try {
      await deleteRecruiter(id);
      const remaining = recruiters.filter((r) => r.id !== id);
      setRecruiters(remaining);
      if (selectedRecruiter?.id === id) {
        setSelectedRecruiter(remaining[0] || null);
      }
    } catch (err) {
      console.error('Failed to delete recruiter:', err);
    }
  };

  const handleLogTouchpoint = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!activeContactForTouchpoint || !touchpointForm.summary.trim()) return;

    setSubmitting(true);
    try {
      const updated = await logRecruiterInteraction(activeContactForTouchpoint.id, {
        interaction_type: touchpointForm.type,
        summary: touchpointForm.summary,
        date: touchpointForm.date,
        follow_up_needed: touchpointForm.follow_up_needed,
        next_step: touchpointForm.next_step || undefined
      });
      setRecruiters(recruiters.map((r) => (r.id === updated.id ? updated : r)));
      if (selectedRecruiter?.id === updated.id) {
        setSelectedRecruiter(updated);
      }
      setIsTouchpointModalOpen(false);
      setTouchpointForm({
        type: 'email',
        summary: '',
        date: new Date().toISOString().split('T')[0],
        follow_up_needed: true,
        next_step: ''
      });
    } catch (err: any) {
      alert(err.message || 'Failed to log touchpoint');
    } finally {
      setSubmitting(false);
    }
  };

  const companies = Array.from(new Set(recruiters.map((r) => r.company).filter(Boolean))) as string[];

  const filteredRecruiters = recruiters.filter((r) => {
    const matchesSearch =
      searchTerm === '' ||
      r.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (r.company && r.company.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (r.position && r.position.toLowerCase().includes(searchTerm.toLowerCase())) ||
      (r.email && r.email.toLowerCase().includes(searchTerm.toLowerCase()));

    const matchesCompany = companyFilter === 'all' || r.company === companyFilter;
    return matchesSearch && matchesCompany;
  });

  const getInteractionIcon = (type: string) => {
    switch (type) {
      case 'email':
        return <Mail className="w-3.5 h-3.5 text-blue-400" />;
      case 'linkedin_message':
        return <Linkedin className="w-3.5 h-3.5 text-sky-400" />;
      case 'phone_screen':
        return <Phone className="h-3.5 w-3.5 text-slate-500" />;
      case 'interview':
        return <Users className="w-3.5 h-3.5 text-sky-300" />;
      default:
        return <FileText className="w-3.5 h-3.5 text-slate-400" />;
    }
  };

  return (
    <div className="space-y-4">
      {/* Compliance / Privacy notice */}
      <div className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-3 text-[12px] text-slate-400">
        <div className="flex items-center space-x-2">
          <ShieldCheck className="h-4 w-4 shrink-0 text-slate-500" />
          <span>
            <strong className="text-slate-200">Ethical Sourcing & CRM Privacy:</strong> CareerOS manages recruiter relations using strictly user-provided or public professional details. No automated web-scraping or unauthorized outreach.
          </span>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="px-3 py-1.5 bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] font-medium rounded-lg text-xs flex items-center space-x-1.5 transition shrink-0"
        >
          <UserPlus className="w-3.5 h-3.5" />
          <span>Add Recruiter</span>
        </button>
      </div>

      {/* Control bar: Search + Company Filter */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 border border-white/[0.07] bg-[var(--color-paper)] p-3 rounded-xl">
        <div className="relative flex-1 sm:w-72">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search by name, company, email..."
            className="input-base min-h-[32px] py-1 pl-9"
          />
        </div>

        <div className="flex items-center space-x-2">
          <span className="text-xs text-slate-400">Company:</span>
          <select
            value={companyFilter}
            onChange={(e) => setCompanyFilter(e.target.value)}
            className="input-base min-h-[32px] w-auto py-1 text-[11px]"
          >
            <option value="all">All Companies ({recruiters.length})</option>
            {companies.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Grid: Directory + Detail Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Recruiter cards list */}
        <div className="lg:col-span-7 space-y-3">
          {loading ? (
            <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-12 text-center text-slate-400">
              <Clock className="w-6 h-6 text-slate-500 mx-auto animate-spin mb-2" />
              <p className="text-sm">Loading recruiter directory...</p>
            </div>
          ) : filteredRecruiters.length === 0 ? (
            <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-12 text-center text-slate-400 space-y-3">
              <Users className="w-10 h-10 text-slate-600 mx-auto" />
              <h4 className="text-sm font-semibold text-[var(--color-ink)]">No recruiter contacts recorded</h4>
              <p className="text-xs text-slate-500 max-w-sm mx-auto">
                Keep track of talent acquisition partners, campus recruiters, and hiring managers you connect with.
              </p>
              <button
                onClick={() => setIsAddModalOpen(true)}
                className="mt-2 px-3 py-1.5 bg-white/[0.04] hover:bg-white/[0.07] text-[var(--color-ink)] rounded-lg text-xs font-semibold inline-flex items-center space-x-1.5"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Your First Recruiter</span>
              </button>
            </div>
          ) : (
            filteredRecruiters.map((r) => {
              const isSelected = selectedRecruiter?.id === r.id;
              const interactionsCount = r.interaction_history?.length || 0;

              return (
                <div
                  key={r.id}
                  onClick={() => setSelectedRecruiter(r)}
                  className={`bg-[var(--color-paper-2)] border rounded-xl p-4 cursor-pointer transition space-y-3 ${
                    isSelected
                      ? 'border-emerald-400/30 bg-emerald-400/[0.03]'
                      : 'border-white/[0.07] bg-[var(--color-paper)] hover:border-white/[0.13]'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center space-x-2">
                        <h4 className="text-[13px] font-medium text-[var(--color-ink)]">
                          {r.name}
                        </h4>
                        {r.contact_source && (
                          <span className="px-2 py-0.5 rounded border border-white/[0.07] bg-white/[0.03] px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
                            {r.contact_source}
                          </span>
                        )}
                      </div>

                      <div className="flex items-center space-x-3 text-xs text-slate-400 mt-1">
                        {r.company && (
                          <span className="flex items-center space-x-1 text-slate-300 font-medium">
                            <Building className="w-3.5 h-3.5 text-slate-500" />
                            <span>{r.company}</span>
                          </span>
                        )}
                        {r.position && (
                          <>
                            <span className="text-slate-600">•</span>
                            <span>{r.position}</span>
                          </>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-1.5">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setActiveContactForTouchpoint(r);
                          setIsTouchpointModalOpen(true);
                        }}
                        className="inline-flex min-h-[27px] items-center gap-1 rounded border border-white/[0.09] bg-white/[0.03] px-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.06] hover:text-[var(--color-ink)]"
                      >
                        <MessageSquare className="w-3 h-3" />
                        <span>Log Touchpoint</span>
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDeleteRecruiter(r.id);
                        }}
                        className="p-1 text-slate-500 hover:text-rose-400 rounded transition"
                        title="Delete contact"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>

                  {/* Contact Links & Stats */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-white/[0.07]/80 text-xs">
                    <div className="flex items-center space-x-3 text-slate-400">
                      {r.email ? (
                        <a
                          href={`mailto:${r.email}`}
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center gap-1 text-slate-400 transition-colors hover:text-[var(--color-ink)]"
                        >
                          <Mail className="w-3.5 h-3.5 text-slate-500" />
                          <span className="text-[11px]">{r.email}</span>
                        </a>
                      ) : (
                        <span className="text-[11px] text-slate-600">No email</span>
                      )}

                      {r.linkedin_url && (
                        <a
                          href={r.linkedin_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="flex items-center space-x-1 text-sky-400 hover:text-sky-300 transition"
                        >
                          <Linkedin className="w-3.5 h-3.5" />
                          <span className="text-[11px]">LinkedIn</span>
                        </a>
                      )}
                    </div>

                    <div className="flex items-center space-x-3 text-[11px] text-slate-500">
                      <span>
                        Last contact:{' '}
                        <strong className="text-slate-400 font-mono">
                          {r.last_contact_date ? new Date(r.last_contact_date).toLocaleDateString() : 'Never'}
                        </strong>
                      </span>
                      <span>•</span>
                      <span>
                        <strong className="text-slate-300 font-mono">{interactionsCount}</strong> interactions
                      </span>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Selected Recruiter Detail Panel */}
        <div className="lg:col-span-5 border border-white/[0.07] bg-[var(--color-paper)] rounded-xl p-4 sticky top-4 space-y-4">
          {selectedRecruiter ? (
            <>
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-base font-bold text-[var(--color-ink)]">{selectedRecruiter.name}</h3>
                    <p className="text-xs text-slate-400">
                      {selectedRecruiter.position || 'Recruiter'} at{' '}
                      <span className="text-slate-200 font-semibold">{selectedRecruiter.company || 'Unknown Company'}</span>
                    </p>
                  </div>
                  <button
                    onClick={() => {
                      setActiveContactForTouchpoint(selectedRecruiter);
                      setIsTouchpointModalOpen(true);
                    }}
                    className="px-2.5 py-1 bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] font-medium rounded text-xs flex items-center space-x-1"
                  >
                    <Plus className="w-3 h-3" />
                    <span>Touchpoint</span>
                  </button>
                </div>

                <div className="mt-3 space-y-1.5 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5 text-[11px] text-slate-300">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Professional Email:</span>
                    {selectedRecruiter.email ? (
                      <a href={`mailto:${selectedRecruiter.email}`} className="text-emerald-300 hover:underline">
                        {selectedRecruiter.email}
                      </a>
                    ) : (
                      <span className="text-slate-600">Not recorded</span>
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">LinkedIn:</span>
                    {selectedRecruiter.linkedin_url ? (
                      <a
                        href={selectedRecruiter.linkedin_url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-sky-400 hover:underline flex items-center space-x-1"
                      >
                        <span>Profile</span>
                        <ExternalLink className="w-2.5 h-2.5" />
                      </a>
                    ) : (
                      <span className="text-slate-600">Not recorded</span>
                    )}
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-500">Acquisition Source:</span>
                    <span className="text-slate-400">{selectedRecruiter.contact_source || 'Unknown'}</span>
                  </div>
                </div>

                {selectedRecruiter.notes && (
                  <div className="mt-3 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5 text-[11px] text-slate-400">
                    <strong className="text-slate-300 block mb-1">Notes:</strong>
                    {selectedRecruiter.notes}
                  </div>
                )}
              </div>

              {/* Interaction History Feed */}
              <div className="space-y-3 pt-3 border-t border-white/[0.07]">
                <h4 className="text-xs font-bold  text-slate-400 flex items-center space-x-1.5">
                  <Clock className="h-3.5 w-3.5 text-slate-500" />
                  <span>Interaction History ({selectedRecruiter.interaction_history?.length || 0})</span>
                </h4>

                {(!selectedRecruiter.interaction_history || selectedRecruiter.interaction_history.length === 0) ? (
                  <p className="text-xs text-slate-500 italic py-3 text-center">
                    No interactions logged yet. Log your first email, phone screen, or note above.
                  </p>
                ) : (
                  <div className="space-y-2 max-h-72 overflow-y-auto pr-1">
                    {selectedRecruiter.interaction_history.map((interaction, i) => (
                      <div
                        key={interaction.id || i}
                        className="space-y-1.5 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5 text-[11px]"
                      >
                        <div className="flex items-center justify-between">
                          <span className="flex items-center space-x-1.5 font-semibold text-[var(--color-ink)] capitalize">
                            {getInteractionIcon(interaction.type)}
                            <span>{interaction.type.replace('_', ' ')}</span>
                          </span>
                          <span className="text-[10px] text-slate-500 font-mono">
                            {interaction.date ? new Date(interaction.date).toLocaleDateString() : ''}
                          </span>
                        </div>

                        <p className="text-slate-300 leading-relaxed text-[11px]">{interaction.summary}</p>

                        {(interaction.follow_up_needed || interaction.next_step) && (
                          <div className="pt-1 flex items-center justify-between text-[10px] text-amber-400/90 border-t border-white/[0.07]/60">
                            <span>Next: {interaction.next_step || 'Follow-up pending'}</span>
                            {interaction.follow_up_needed && (
                              <span className="px-1.5 py-0.2 rounded bg-amber-500/10 border border-amber-500/20 font-semibold">
                                Action Needed
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div className="text-center py-12 text-slate-500 text-xs">
              Select a recruiter on the left to inspect contact details and logged interaction history.
            </div>
          )}
        </div>
      </div>

      {/* Add Recruiter Modal */}
      {isAddModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
              <h3 className="text-sm font-bold text-[var(--color-ink)] flex items-center space-x-2">
                <UserPlus className="w-4 h-4 text-emerald-400" />
                <span>Add Recruiter Contact</span>
              </h3>
              <button
                onClick={() => setIsAddModalOpen(false)}
                className="text-xs text-slate-400 hover:text-[var(--color-ink)]"
              >
                Cancel
              </button>
            </div>

            {formError && (
              <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center space-x-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <form onSubmit={handleCreateRecruiter} className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  Full Name <span className="text-rose-400">*</span>
                </label>
                <input
                  type="text"
                  required
                  value={newRecruiter.name}
                  onChange={(e) => setNewRecruiter({ ...newRecruiter, name: e.target.value })}
                  placeholder="e.g. Sarah Jenkins"
                  className="input-base min-w-0"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Company</label>
                  <input
                    type="text"
                    value={newRecruiter.company}
                    onChange={(e) => setNewRecruiter({ ...newRecruiter, company: e.target.value })}
                    placeholder="e.g. Stripe"
                    className="input-base min-w-0"
                  />
                </div>
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Position / Role</label>
                  <input
                    type="text"
                    value={newRecruiter.position}
                    onChange={(e) => setNewRecruiter({ ...newRecruiter, position: e.target.value })}
                    placeholder="e.g. University Recruiter"
                    className="input-base min-w-0"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Professional Email</label>
                <input
                  type="email"
                  value={newRecruiter.email}
                  onChange={(e) => setNewRecruiter({ ...newRecruiter, email: e.target.value })}
                  placeholder="e.g. sarah.j@stripe.com"
                  className="input-base min-w-0"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">LinkedIn Profile URL</label>
                <input
                  type="url"
                  value={newRecruiter.linkedin_url}
                  onChange={(e) => setNewRecruiter({ ...newRecruiter, linkedin_url: e.target.value })}
                  placeholder="https://linkedin.com/in/sarah-jenkins"
                  className="input-base min-w-0"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Contact Source</label>
                <select
                  value={newRecruiter.contact_source}
                  onChange={(e) => setNewRecruiter({ ...newRecruiter, contact_source: e.target.value })}
                  className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
                >
                  <option value="LinkedIn Outreach">LinkedIn Outreach</option>
                  <option value="Career Fair">Campus Career Fair</option>
                  <option value="Referral">Peer / Referral</option>
                  <option value="Inbound Email">Inbound Recruiter Email</option>
                  <option value="Company Portal">Company Portal / Listing</option>
                  <option value="Networking Event">Networking Event / Meetup</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Notes / Context</label>
                <textarea
                  rows={2}
                  value={newRecruiter.notes}
                  onChange={(e) => setNewRecruiter({ ...newRecruiter, notes: e.target.value })}
                  placeholder="Met at virtual info session, focused on Summer 2026 internships..."
                  className="input-base min-w-0"
                />
              </div>

              <div className="pt-2 flex items-center justify-end space-x-2 border-t border-white/[0.07]">
                <button
                  type="button"
                  onClick={() => setIsAddModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-[var(--color-ink)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 text-slate-950 font-bold rounded-lg text-xs"
                >
                  {submitting ? 'Saving...' : 'Save Recruiter'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Log Touchpoint Modal */}
      {isTouchpointModalOpen && activeContactForTouchpoint && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm">
          <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
              <div>
                <h3 className="text-sm font-bold text-[var(--color-ink)] flex items-center space-x-2">
                  <MessageSquare className="w-4 h-4 text-emerald-400" />
                  <span>Log Touchpoint</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  With {activeContactForTouchpoint.name} ({activeContactForTouchpoint.company})
                </p>
              </div>
              <button
                onClick={() => setIsTouchpointModalOpen(false)}
                className="text-xs text-slate-400 hover:text-[var(--color-ink)]"
              >
                Cancel
              </button>
            </div>

            <form onSubmit={handleLogTouchpoint} className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Interaction Type</label>
                  <select
                    value={touchpointForm.type}
                    onChange={(e) => setTouchpointForm({ ...touchpointForm, type: e.target.value })}
                    className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-slate-300 focus:outline-none focus:border-emerald-500"
                  >
                    <option value="email">Email Sent/Received</option>
                    <option value="linkedin_message">LinkedIn Message</option>
                    <option value="phone_screen">Phone Screen</option>
                    <option value="interview">Interview Round</option>
                    <option value="note">Internal Note</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs font-semibold text-slate-300 block mb-1">Date</label>
                  <input
                    type="date"
                    required
                    value={touchpointForm.date}
                    onChange={(e) => setTouchpointForm({ ...touchpointForm, date: e.target.value })}
                    className="input-base min-w-0"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">
                  Summary / Discussion Points <span className="text-rose-400">*</span>
                </label>
                <textarea
                  rows={3}
                  required
                  value={touchpointForm.summary}
                  onChange={(e) => setTouchpointForm({ ...touchpointForm, summary: e.target.value })}
                  placeholder="Notes from the call (e.g. resume forwarded, review expected by Friday)"
                  className="input-base min-w-0"
                />
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1">Next Step / Follow-Up</label>
                <input
                  type="text"
                  value={touchpointForm.next_step}
                  onChange={(e) => setTouchpointForm({ ...touchpointForm, next_step: e.target.value })}
                  placeholder="Follow up if no reply by next Friday"
                  className="input-base min-w-0"
                />
              </div>

              <div className="flex items-center space-x-2 pt-1">
                <input
                  type="checkbox"
                  id="followUpNeeded"
                  checked={touchpointForm.follow_up_needed}
                  onChange={(e) => setTouchpointForm({ ...touchpointForm, follow_up_needed: e.target.checked })}
                  className="rounded border-white/[0.09] text-emerald-500 focus:ring-0 bg-slate-950"
                />
                <label htmlFor="followUpNeeded" className="text-xs text-slate-300">
                  Mark this conversation as requiring follow-up
                </label>
              </div>

              <div className="pt-2 flex items-center justify-end space-x-2 border-t border-white/[0.07]">
                <button
                  type="button"
                  onClick={() => setIsTouchpointModalOpen(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-[var(--color-ink)]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 text-slate-950 font-bold rounded-lg text-xs"
                >
                  {submitting ? 'Saving...' : 'Log Interaction'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
