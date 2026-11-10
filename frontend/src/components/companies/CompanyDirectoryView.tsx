import React, { useState, useEffect } from 'react';
import { Plus, RotateCw, ExternalLink, Search, CheckCircle2 } from 'lucide-react';
import { Company } from '../../types';
import { fetchCompanies, addCompany, syncSingleCompany, detectAtsFromUrl } from '../../services/api';
import { PageHeader } from '../ui/PageHeader';
import { EmptyState } from '../ui/EmptyState';
import { CountUp } from '../ui/CountUp';

export const CompanyDirectoryView: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState('');
  const [syncingId, setSyncingId] = useState<number | null>(null);

  // Add Company Modal State
  const [showAddModal, setShowAddModal] = useState(false);
  const [newName, setNewName] = useState('');
  const [newWebsite, setNewWebsite] = useState('');
  const [newCareerUrl, setNewCareerUrl] = useState('');
  const [newIndustry, setNewIndustry] = useState('Technology & AI');
  const [newHq, setNewHq] = useState('Bengaluru, India');
  const [newAts, setNewAts] = useState('greenhouse');
  const [newBoardId, setNewBoardId] = useState('');
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [atsDetectedMsg, setAtsDetectedMsg] = useState<string | null>(null);

  const loadCompanies = () => {
    setLoading(true);
    fetchCompanies({ search, page: 1, page_size: 50 })
      .then(data => setCompanies(data.items || []))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadCompanies();
  }, [search]);

  const handleCareerUrlChange = async (url: string) => {
    setNewCareerUrl(url);
    if (!url.trim()) {
      setAtsDetectedMsg(null);
      return;
    }
    try {
      const res = await detectAtsFromUrl(url);
      if (res.detected) {
        setNewAts(res.ats_provider);
        if (res.ats_board_id) {
          setNewBoardId(res.ats_board_id);
          if (!newName.trim()) {
            setNewName(res.ats_board_id.charAt(0).toUpperCase() + res.ats_board_id.slice(1));
          }
        }
        setAtsDetectedMsg(`Auto-detected ${res.ats_provider.toUpperCase()} (${res.ats_board_id})`);
      } else {
        setAtsDetectedMsg(null);
      }
    } catch {
      // Ignore detection errors during typing
    }
  };

  const handleSyncCompany = async (id: number) => {
    setSyncingId(id);
    try {
      await syncSingleCompany(id);
      loadCompanies();
    } catch (err) {
      console.error(err);
    } finally {
      setSyncingId(null);
    }
  };

  const handleAddSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    setModalLoading(true);
    setModalError(null);
    try {
      await addCompany({
        name: newName,
        website: newWebsite,
        career_url: newCareerUrl,
        industry: newIndustry,
        hq_location: newHq,
        ats_provider: newAts,
        ats_board_id: newBoardId || newName.toLowerCase().replace(/\s+/g, '')
      });
      setShowAddModal(false);
      setNewName('');
      setNewWebsite('');
      setNewCareerUrl('');
      setNewBoardId('');
      loadCompanies();
    } catch (err: any) {
      setModalError(err.message || "Failed to add company");
    } finally {
      setModalLoading(false);
    }
  };

  return (
    <div className="space-y-6">
        {!embedded && (
        <PageHeader
          eyebrow="Monitoring"
          title="Company directory"
          description="CareerOS monitors official ATS career pages (Greenhouse, Lever, Ashby, SmartRecruiters) and alerts you as soon as new internships are published."
          actions={
            <button
              onClick={() => setShowAddModal(true)}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Monitor New Company</span>
            </button>
          }
        />
      )}

      {/* Search Input */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
        <input
          type="text"
          placeholder="Search monitored companies or industries..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="input-base pl-9"
        />
      </div>

      {/* Directory Grid */}
      {loading && companies.length === 0 && (
        <div className="flex items-center gap-2.5 py-10 text-slate-500">
          <div className="h-4 w-4 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
          <span className="text-[12px]">Loading company directory…</span>
        </div>
      )}

      {!loading && companies.length === 0 && (
        <EmptyState
          title="No companies monitored yet"
          description="Add a company career page and CareerOS will watch it for new internships."
          action={
            <button
              type="button"
              onClick={() => setShowAddModal(true)}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300"
            >
              <Plus className="h-3.5 w-3.5" aria-hidden="true" />
              <span>Monitor a company</span>
            </button>
          }
        />
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {companies.map(comp => (
          <div
            key={comp.id}
            className="p-4 sm:p-5 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] flex flex-col justify-between"
          >
            <div>
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] font-semibold text-slate-400 flex items-center justify-center text-[13px]">
                    {comp.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <h3 className="text-[13px] font-semibold text-[var(--color-ink)] flex items-center gap-1.5">
                      <span>{comp.name}</span>
                      {comp.monitoring_status === 'active' && (
                        <span className="h-2 w-2 rounded-full bg-emerald-400" title="Actively Monitored" />
                      )}
                    </h3>
                    <span className="text-[11px] text-slate-500">{comp.industry || 'Technology'}</span>
                  </div>
                </div>

                <span className="rounded border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] font-medium text-slate-400">
                  {comp.ats_provider}
                </span>
              </div>

              <div className="mt-4 space-y-1.5 text-xs text-slate-300">
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Board Identifier:</span>
                  <span className="font-mono text-slate-300">{comp.ats_board_id || 'default'}</span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Opportunities Discovered:</span>
                  <span className="font-mono text-slate-200 tnum">
                    <CountUp to={comp.opportunities_count} duration={0.8} />
                  </span>
                </div>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-500">Last Synchronization:</span>
                  <span className="text-slate-400">
                    {comp.last_sync_at ? new Date(comp.last_sync_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Pending'}
                  </span>
                </div>
              </div>
            </div>

            {/* Actions Footer */}
            <div className="mt-4 pt-3 border-t border-white/[0.07] flex items-center justify-between">
              {comp.career_url ? (
                <a
                  href={comp.career_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[12px] text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                >
                  <span>Career Page</span>
                  <ExternalLink className="h-3 w-3" />
                </a>
              ) : <span />}

              <button
                onClick={() => handleSyncCompany(comp.id)}
                disabled={syncingId === comp.id}
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <RotateCw className={`h-3 w-3 ${syncingId === comp.id ? 'animate-spin text-emerald-400' : ''}`} />
                <span>{syncingId === comp.id ? 'Syncing...' : 'Poll Board'}</span>
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Add Company Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-6">
            <h3 className="text-[15px] font-semibold text-[var(--color-ink)] mb-1">Add Company to Career Monitor</h3>
            <p className="text-[12px] text-slate-500 mb-4">Automatically discover newly published internships from their official career page.</p>

            {modalError && (
              <div className="mb-3 p-2.5 rounded-lg border border-rose-400/25 bg-rose-400/[0.06] text-rose-300 text-xs">
                {modalError}
              </div>
            )}

            <form onSubmit={handleAddSubmit} className="space-y-3 text-xs">
              <div>
                <label className="field-label mb-1 block">Career Page URL (Paste to Auto-Detect)</label>
                <input
                  type="url"
                  placeholder="e.g. https://boards.greenhouse.io/stripe or https://jobs.lever.co/palantir"
                  value={newCareerUrl}
                  onChange={e => handleCareerUrlChange(e.target.value)}
                  className="input-base font-mono text-[11px]"
                />
                {atsDetectedMsg && (
                  <p className="mt-1 text-[11px] text-emerald-300 font-medium flex items-center gap-1">
                    <CheckCircle2 className="h-3.5 w-3.5" />
                    <span>{atsDetectedMsg}</span>
                  </p>
                )}
              </div>

              <div>
                <label className="field-label mb-1 block">Company Name *</label>
                <input
                  type="text"
                  placeholder="e.g. Stripe or Palantir"
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  className="input-base"
                  required
                />
              </div>

              <div>
                <label className="field-label mb-1 block">ATS Provider *</label>
                <select
                  value={newAts}
                  onChange={e => setNewAts(e.target.value)}
                  className="input-base capitalize"
                >
                  <option value="greenhouse">Greenhouse (boards-api.greenhouse.io)</option>
                  <option value="lever">Lever (api.lever.co)</option>
                  <option value="ashby">Ashby (api.ashbyhq.com)</option>
                  <option value="smartrecruiters">SmartRecruiters</option>
                  <option value="custom">Custom Portal</option>
                </select>
              </div>

              <div>
                <label className="field-label mb-1 block">ATS Board Identifier / Slug</label>
                <input
                  type="text"
                  placeholder="e.g. cloudflare (from boards.greenhouse.io/cloudflare)"
                  value={newBoardId}
                  onChange={e => setNewBoardId(e.target.value)}
                  className="input-base font-mono text-[11px]"
                />
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={modalLoading}
                  className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                >
                  {modalLoading ? 'Adding...' : 'Add Company'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
