import React, { useState, useEffect, useMemo } from 'react';
import { User, Sliders, Save, Plus, X, Check, ShieldAlert, DollarSign, MapPin, Briefcase, Layers, Building2, Mail, Cpu, AlertTriangle, ExternalLink } from 'lucide-react';
import { CandidateProfile, UserPreferences } from '../../types';
import { fetchPreferences, updatePreferences, fetchCandidateProfile } from '../../services/api';
import { SourcesView } from '../sources/SourcesView';
import { CompanyDirectoryView } from '../companies/CompanyDirectoryView';
import { IntegrationsSettingsTab } from './IntegrationsSettingsTab';
import { AIDiagnosticsCard } from './AIDiagnosticsCard';
import { PageHeader } from '../ui/PageHeader';
import { useUnsavedChangesGuard } from '../../context/unsavedChanges';

type SectionId = 'account' | 'criteria' | 'sources' | 'companies' | 'accounts' | 'diagnostics';

interface PreferencesViewProps {
  initialSubTab?: 'criteria' | 'sources' | 'companies' | 'integrations' | 'ai';
  onNavigateTab?: (tab: string) => void;
}

export const PreferencesView: React.FC<PreferencesViewProps> = ({ initialSubTab, onNavigateTab }) => {
  const [active, setActive] = useState<SectionId>(
    initialSubTab === 'sources' ? 'sources'
    : initialSubTab === 'companies' ? 'companies'
    : initialSubTab === 'integrations' ? 'accounts'
    : initialSubTab === 'ai' ? 'diagnostics'
    : 'criteria'
  );
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [baseline, setBaseline] = useState<UserPreferences | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [newCustomCategory, setNewCustomCategory] = useState('');
  const [newExcludedKeyword, setNewExcludedKeyword] = useState('');
  const [newExcludedCompany, setNewExcludedCompany] = useState('');

  const dirty = useMemo(
    () => Boolean(prefs && baseline) && JSON.stringify(prefs) !== JSON.stringify(baseline),
    [prefs, baseline]
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setLoadError(null);
    fetchPreferences()
      .then(data => {
        if (cancelled) return;
        setPrefs(data);
        setBaseline(data);
      })
      .catch(err => {
        if (cancelled) return;
        console.error(err);
        setLoadError(err instanceof Error ? err.message : 'Failed to load preferences');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // Shared navigation guard: blocks SPA navigation away from Settings while edits are unsaved
  useUnsavedChangesGuard('settings:preferences', dirty, 'Your preference edits are not saved');

  const changeSection = (id: SectionId) => {
    if (active === 'criteria' && dirty && id !== 'criteria') {
      const discard = window.confirm('You have unsaved preference changes. Discard them?');
      if (!discard) return;
    }
    setActive(id);
  };

  const handleSave = async () => {
    if (!prefs) return;
    setSaving(true);
    setSavedSuccess(false);
    setSaveError(null);
    try {
      const updated = await updatePreferences(prefs);
      setPrefs(updated);
      setBaseline(updated);
      setSavedSuccess(true);
      window.setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err) {
      console.error(err);
      setSaveError(err instanceof Error ? err.message : 'Failed to save preferences');
    } finally {
      setSaving(false);
    }
  };

  const addCategory = () => {
    if (!newCustomCategory.trim() || !prefs) return;
    if (!prefs.preferred_categories.includes(newCustomCategory.trim())) {
      setPrefs({
        ...prefs,
        preferred_categories: [...prefs.preferred_categories, newCustomCategory.trim()]
      });
    }
    setNewCustomCategory('');
  };

  const removeCategory = (cat: string) => {
    if (!prefs) return;
    setPrefs({
      ...prefs,
      preferred_categories: prefs.preferred_categories.filter(c => c !== cat)
    });
  };

  const toggleLocation = (loc: string) => {
    if (!prefs) return;
    const exists = prefs.preferred_locations.includes(loc);
    setPrefs({
      ...prefs,
      preferred_locations: exists
        ? prefs.preferred_locations.filter(l => l !== loc)
        : [...prefs.preferred_locations, loc]
    });
  };

  const toggleWorkplace = (wp: string) => {
    if (!prefs) return;
    const exists = prefs.workplace_types.includes(wp);
    setPrefs({
      ...prefs,
      workplace_types: exists
        ? prefs.workplace_types.filter(w => w !== wp)
        : [...prefs.workplace_types, wp]
    });
  };

  const addExcludedKeyword = () => {
    if (!newExcludedKeyword.trim() || !prefs) return;
    setPrefs({
      ...prefs,
      excluded_keywords: [...prefs.excluded_keywords, newExcludedKeyword.trim().toLowerCase()]
    });
    setNewExcludedKeyword('');
  };

  const removeExcludedKeyword = (kw: string) => {
    if (!prefs) return;
    setPrefs({
      ...prefs,
      excluded_keywords: prefs.excluded_keywords.filter(k => k !== kw)
    });
  };

  const addExcludedCompany = () => {
    if (!newExcludedCompany.trim() || !prefs) return;
    setPrefs({
      ...prefs,
      excluded_companies: [...prefs.excluded_companies, newExcludedCompany.trim()]
    });
    setNewExcludedCompany('');
  };

  const removeExcludedCompany = (comp: string) => {
    if (!prefs) return;
    setPrefs({
      ...prefs,
      excluded_companies: prefs.excluded_companies.filter(c => c !== comp)
    });
  };

  const setStipend = (raw: string) => {
    if (!prefs) return;
    const v = Number(raw);
    setPrefs({ ...prefs, min_stipend: Number.isFinite(v) && v >= 0 ? v : 0 });
  };

  const setGraduationYear = (raw: string) => {
    if (!prefs) return;
    const v = Number(raw);
    if (Number.isFinite(v) && v >= 1900 && v <= 2100) {
      setPrefs({ ...prefs, graduation_year: Math.round(v) });
    }
  };

  const standardLocations = [
    "Remote, India", "Pune", "Bengaluru", "Mumbai", "Hyderabad", "Chennai", "Delhi NCR", "Remote, worldwide"
  ];

  const sections: Array<{ id: SectionId; label: string; icon: React.ReactNode }> = [
    { id: 'account', label: 'Account', icon: <User className="h-4 w-4" aria-hidden="true" /> },
    { id: 'criteria', label: 'Discovery criteria', icon: <Sliders className="h-4 w-4" aria-hidden="true" /> },
    { id: 'sources', label: 'Sources', icon: <Layers className="h-4 w-4" aria-hidden="true" /> },
    { id: 'companies', label: 'Companies', icon: <Building2 className="h-4 w-4" aria-hidden="true" /> },
    { id: 'accounts', label: 'Connected accounts', icon: <Mail className="h-4 w-4" aria-hidden="true" /> },
    { id: 'diagnostics', label: 'AI diagnostics', icon: <Cpu className="h-4 w-4" aria-hidden="true" /> },
  ];

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow="Settings"
        title="Settings"
        description="Account, discovery criteria and connected workspace. Every control here persists to the backend."
        actions={
          active === 'criteria' && (
            <button
              type="button"
              onClick={handleSave}
              disabled={saving || !dirty}
              className="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3.5 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
            >
              {savedSuccess ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Save className="h-3.5 w-3.5" aria-hidden="true" />}
              <span>{saving ? 'Saving…' : savedSuccess ? 'Saved' : 'Save preferences'}</span>
            </button>
          )
        }
      />

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[232px_minmax(0,1fr)]">
        {/* Section navigation — vertical rail on desktop, horizontal strip on small screens */}
        <nav
          aria-label="Settings sections"
          className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden lg:mx-0 lg:max-w-[232px] lg:flex-col lg:self-start lg:overflow-visible lg:px-0 lg:pb-0"
        >
          {sections.map((section) => {
            const selected = active === section.id;
            return (
              <button
                key={section.id}
                type="button"
                aria-current={selected ? 'page' : undefined}
                onClick={() => changeSection(section.id)}
                className={`inline-flex min-h-[36px] shrink-0 items-center gap-2 whitespace-nowrap rounded-lg border px-3 text-[12.5px] font-medium transition-colors focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-[var(--color-focus)] ${
                  selected
                    ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                    : 'border-transparent text-[var(--color-ink-2)] hover:border-white/[0.08] hover:bg-white/[0.03] hover:text-[var(--color-ink)]'
                }`}
              >
                {section.icon}
                <span>{section.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Content pane */}
        <div className="min-w-0 space-y-5">
          {active === 'account' && <AccountSection onNavigateTab={onNavigateTab} />}
          {active === 'sources' && <SourcesView embedded />}
          {active === 'companies' && <CompanyDirectoryView embedded />}
          {active === 'accounts' && <AccountsSection onNavigateTab={onNavigateTab} />}
          {active === 'diagnostics' && <AIDiagnosticsCard />}

          {active === 'criteria' && (
            <div className="space-y-5">
              {(loadError || saveError || dirty) && (
                <div className="space-y-2">
                  {loadError && (
                    <p role="alert" className="flex items-start gap-2 rounded-lg border border-rose-400/25 bg-rose-400/[0.06] px-3 py-2 text-[12px] text-rose-300">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      <span>Could not load preferences: {loadError}</span>
                    </p>
                  )}
                  {saveError && (
                    <p role="alert" className="flex items-start gap-2 rounded-lg border border-rose-400/25 bg-rose-400/[0.06] px-3 py-2 text-[12px] text-rose-300">
                      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                      <span>Save failed. Your edits are kept on this device but not stored: {saveError}</span>
                    </p>
                  )}
                  {dirty && (
                    <p role="status" className="inline-flex items-center gap-2 rounded-lg border border-amber-400/20 bg-amber-400/[0.05] px-3 py-1.5 text-[11px] font-medium text-amber-200/90">
                      <span className="h-1.5 w-1.5 rounded-full bg-amber-300" aria-hidden="true" />
                      Unsaved changes. Press Save preferences to persist
                    </p>
                  )}
                </div>
              )}

              {loading || !prefs ? (
                <div className="flex flex-col items-center gap-3 py-24 text-slate-400" role="status" aria-label="Loading preferences">
                  <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
                  <p className="text-[12px]">Loading preferences…</p>
                </div>
              ) : (
                <>
                  {/* Section 1: Preferred Categories */}
                  <div className="space-y-4 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5">
                    <h3 className="flex items-center gap-2 text-[13px] font-semibold text-[var(--color-ink)]">
                      <Briefcase className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      <span>Target Job Roles &amp; Categories</span>
                    </h3>
                    <p className="text-[12px] leading-relaxed text-slate-500">
                      CareerOS prioritizes opportunities matching these role keywords across all monitored boards and APIs.
                    </p>

                    <div className="flex flex-wrap gap-2">
                      {prefs.preferred_categories.map((cat, i) => (
                        <span
                          key={i}
                          className="inline-flex items-center gap-1.5 rounded border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[11px] text-slate-300"
                        >
                          <span>{cat}</span>
                          <button onClick={() => removeCategory(cat)} aria-label={`Remove ${cat}`} className="text-slate-500 transition-colors hover:text-rose-400">
                            <X className="w-3.5 h-3.5" aria-hidden="true" />
                          </button>
                        </span>
                      ))}
                    </div>

                    <div className="flex max-w-md items-center gap-2 pt-1">
                      <input
                        type="text"
                        placeholder="Add custom role (e.g. MLOps Intern)..."
                        value={newCustomCategory}
                        onChange={e => setNewCustomCategory(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addCategory())}
                        className="input-base min-w-0 flex-1"
                      />
                      <button
                        type="button"
                        onClick={addCategory}
                        className="inline-flex min-h-[34px] shrink-0 items-center gap-1.5 rounded-lg border border-white/[0.10] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                      >
                        <Plus className="w-4 h-4" aria-hidden="true" />
                        <span>Add</span>
                      </button>
                    </div>
                  </div>

                  {/* Section 2: Preferred Locations & Workplace Mode */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5">
                      <h3 className="flex items-center gap-2 text-[13px] font-semibold text-[var(--color-ink)]">
                        <MapPin className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                        <span>Preferred Locations</span>
                      </h3>
                      <p className="text-[12px] leading-relaxed text-slate-500">Select regions where you are eligible and available to work.</p>

                      <div className="grid grid-cols-2 gap-1.5 pt-1">
                        {standardLocations.map(loc => {
                          const selected = prefs.preferred_locations.includes(loc);
                          return (
                            <button
                              type="button"
                              key={loc}
                              aria-pressed={selected}
                              onClick={() => toggleLocation(loc)}
                              className={`flex items-center justify-between rounded-md border px-2.5 py-2 text-left text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 ${
                                selected
                                  ? 'border-emerald-400/30 bg-emerald-400/[0.06] text-emerald-300'
                                  : 'border-white/[0.07] bg-white/[0.02] text-slate-400 hover:border-white/[0.13] hover:text-slate-200'
                              }`}
                            >
                              <span>{loc}</span>
                              {selected && <Check className="w-3.5 h-3.5" aria-hidden="true" />}
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div className="space-y-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5">
                      <h3 className="flex items-center gap-2 text-[13px] font-semibold text-[var(--color-ink)]">
                        <Briefcase className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                        <span>Workplace Arrangement</span>
                      </h3>
                      <p className="text-[12px] leading-relaxed text-slate-500">Filter acceptable work models for student scheduling.</p>

                      <div className="space-y-1.5 pt-1">
                        {['remote', 'hybrid', 'onsite'].map(wp => {
                          const current = prefs.workplace_types.includes(wp);
                          return (
                            <button
                              type="button"
                              key={wp}
                              aria-pressed={current}
                              onClick={() => toggleWorkplace(wp)}
                              className={`flex w-full cursor-pointer items-center justify-between rounded-md border px-2.5 py-2.5 text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 ${
                                current
                                  ? 'border-emerald-400/30 bg-emerald-400/[0.06] text-emerald-300'
                                  : 'border-white/[0.07] bg-white/[0.02] text-slate-400 hover:border-white/[0.13] hover:text-slate-200'
                              }`}
                            >
                              <span className="capitalize">{wp} Work Opportunities</span>
                              {current && <Check className="w-4 h-4" aria-hidden="true" />}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Section 3: Internship Financial & Academic Criteria */}
                  <div className="space-y-5 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5">
                    <h3 className="flex items-center gap-2 text-[13px] font-semibold text-[var(--color-ink)]">
                      <DollarSign className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      <span>Compensation &amp; Student Eligibility</span>
                    </h3>

                    <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3">
                      <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
                        <span className="field-label block" id="paidOnlyLabel">Paid Internships Only</span>
                        <div className="mt-2 flex items-center gap-2.5">
                          <input
                            type="checkbox"
                            id="paidOnly"
                            checked={prefs.paid_only}
                            onChange={e => setPrefs({ ...prefs, paid_only: e.target.checked })}
                            className="h-3.5 w-3.5 rounded accent-emerald-400"
                          />
                          <label htmlFor="paidOnly" className="cursor-pointer text-[12px] font-medium text-slate-300">
                            Strictly paid positions
                          </label>
                        </div>
                        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">Unpaid internships will be automatically disqualified.</p>
                      </div>

                      <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
                        <span className="field-label block" id="minStipendLabel">Minimum Monthly Stipend</span>
                        <div className="mt-2 flex items-center space-x-2">
                          <span className="font-mono text-[12px] text-slate-400">₹</span>
                          <input
                            type="number"
                            min={0}
                            step="5000"
                            aria-labelledby="minStipendLabel"
                            value={prefs.min_stipend}
                            onChange={e => setStipend(e.target.value)}
                            className="input-base min-w-0 font-mono tnum"
                          />
                        </div>
                        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">Opportunities below this will be flagged.</p>
                      </div>

                      <div className="rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
                        <span className="field-label block" id="gradYearLabel">Graduation Year Eligibility</span>
                        <div className="mt-2">
                          <input
                            type="number"
                            min={1900}
                            max={2100}
                            aria-labelledby="gradYearLabel"
                            value={prefs.graduation_year}
                            onChange={e => setGraduationYear(e.target.value)}
                            className="input-base min-w-0 font-mono tnum"
                          />
                        </div>
                        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">Jobs demanding 2024 graduates will be flagged.</p>
                      </div>
                    </div>
                  </div>

                  {/* Section 4: Exclusion Rules */}
                  <div className="space-y-4 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5">
                    <h3 className="flex items-center gap-2 text-[13px] font-semibold text-[var(--color-ink)]">
                      <ShieldAlert className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                      <span>Exclusion Rules</span>
                    </h3>
                    <p className="text-[12px] leading-relaxed text-slate-500">Exclude listings containing specific unwanted keywords or companies.</p>

                    <div className="grid grid-cols-1 gap-4 pt-1 md:grid-cols-2">
                      {/* Excluded Keywords */}
                      <div>
                        <label className="field-label mb-1.5 block" htmlFor="excludedKeywords">Excluded Keywords</label>
                        <div className="flex flex-wrap gap-1.5 mb-2">
                          {prefs.excluded_keywords.map((kw, i) => (
                            <span key={i} className="inline-flex items-center gap-1 rounded border border-rose-400/20 bg-rose-400/[0.06] px-1.5 py-0.5 text-[11px] text-rose-300">
                              <span>{kw}</span>
                              <button onClick={() => removeExcludedKeyword(kw)} aria-label={`Remove keyword ${kw}`} className="text-rose-300/70 transition-colors hover:text-rose-200">
                                <X className="w-3 h-3" aria-hidden="true" />
                              </button>
                            </span>
                          ))}
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            id="excludedKeywords"
                            type="text"
                            placeholder="e.g. telecaller, unpaid..."
                            value={newExcludedKeyword}
                            onChange={e => setNewExcludedKeyword(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addExcludedKeyword())}
                            className="input-base min-w-0 flex-1"
                          />
                          <button type="button" onClick={addExcludedKeyword} className="inline-flex min-h-[34px] shrink-0 items-center rounded-lg border border-white/[0.10] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60">
                            Exclude
                          </button>
                        </div>
                      </div>

                      {/* Excluded Companies */}
                      <div>
                        <label className="field-label mb-1.5 block" htmlFor="excludedCompanies">Excluded Companies</label>
                        <div className="flex flex-wrap gap-1.5 mb-2">
                          {prefs.excluded_companies.map((comp, i) => (
                            <span key={i} className="inline-flex items-center gap-1 rounded border border-rose-400/20 bg-rose-400/[0.06] px-1.5 py-0.5 text-[11px] text-rose-300">
                              <span>{comp}</span>
                              <button onClick={() => removeExcludedCompany(comp)} aria-label={`Remove company ${comp}`} className="text-rose-300/70 transition-colors hover:text-rose-200">
                                <X className="w-3 h-3" aria-hidden="true" />
                              </button>
                            </span>
                          ))}
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            id="excludedCompanies"
                            type="text"
                            placeholder="e.g. BannedCorp..."
                            value={newExcludedCompany}
                            onChange={e => setNewExcludedCompany(e.target.value)}
                            onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), addExcludedCompany())}
                            className="input-base min-w-0 flex-1"
                          />
                          <button type="button" onClick={addExcludedCompany} className="inline-flex min-h-[34px] shrink-0 items-center rounded-lg border border-white/[0.10] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60">
                            Exclude
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

/* ---------- Account section: identity backed by /api/candidate ---------- */

const AccountSection: React.FC<{ onNavigateTab?: (tab: string) => void }> = ({ onNavigateTab }) => {
  const [candidate, setCandidate] = useState<CandidateProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchCandidateProfile()
      .then(data => { if (!cancelled) { setCandidate(data); setError(null); } })
      .catch(err => {
        if (cancelled) return;
        console.error(err);
        setError(err instanceof Error ? err.message : 'Failed to load account identity');
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div className="flex flex-col items-center gap-3 py-16 text-slate-400" role="status" aria-label="Loading account">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
        <p className="text-[12px]">Loading account…</p>
      </div>
    );
  }

  if (error || !candidate) {
    return (
      <p role="alert" className="rounded-xl border border-rose-400/25 bg-rose-400/[0.06] px-4 py-3 text-[12px] text-rose-300">
        Account identity could not be loaded{error ? `: ${error}` : '.'}
      </p>
    );
  }

  const updated = candidate.updated_at ? new Date(candidate.updated_at) : null;
  const initials = (candidate.name || '?').trim().split(/\s+/).slice(0, 2).map(p => p[0]?.toUpperCase() ?? '').join('');

  return (
    <div className="space-y-4">
      <section aria-label="Account overview" className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
          <div aria-hidden="true" className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-emerald-400/25 bg-emerald-400/[0.06] text-[15px] font-semibold text-emerald-300">
            {initials}
          </div>
          <div className="min-w-0">
            <h2 className="text-[15px] font-semibold text-[var(--color-ink)]">{candidate.name}</h2>
            <p className="mt-0.5 truncate text-[12px] text-[var(--color-ink-2)]">{candidate.email}</p>
            {candidate.location && <p className="mt-0.5 text-[11px] text-[var(--color-ink-tertiary)]">{candidate.location}</p>}
          </div>
          <div className="flex shrink-0 flex-col items-start gap-1 sm:ml-auto sm:items-end">
            <span className="rounded border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 font-mono text-[10px] text-slate-400">evidence v{candidate.evidence_version ?? 'n/a'}</span>
            {updated && <span className="text-[10px] text-[var(--color-ink-tertiary)]">Profile updated {updated.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}</span>}
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-1 gap-2 border-t border-white/[0.06] pt-4 sm:grid-cols-2">
          <div className="flex items-center justify-between gap-3">
            <dt className="text-[11px] text-slate-500">Education</dt>
            <dd className="truncate text-[11px] font-medium text-slate-200">{[candidate.degree, candidate.college].filter(Boolean).join(' · ') || '—'}</dd>
          </div>
          <div className="flex items-center justify-between gap-3">
            <dt className="text-[11px] text-slate-500">Work authorization</dt>
            <dd className="text-[11px] font-medium text-slate-200">{candidate.work_authorization || '—'}</dd>
          </div>
        </dl>
      </section>

      {/* Identity lives in Candidate Profile — link, never duplicate */}
      <section aria-label="Where edits happen" className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => onNavigateTab?.('profile')}
          className="group flex flex-col items-start gap-1 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 text-left transition-colors hover:border-[var(--color-rule)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
        >
          <span className="flex w-full items-center justify-between">
            <span className="text-[12px] font-medium text-[var(--color-ink)]">Identity &amp; evidence</span>
            <ExternalLink className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)] transition-colors group-hover:text-[var(--color-accent)]" aria-hidden="true" />
          </span>
          <span className="text-[11px] leading-relaxed text-[var(--color-ink-tertiary)]">Name, education, skills, projects and GitHub sync are edited in Candidate Profile.</span>
        </button>

        <button
          type="button"
          onClick={() => onNavigateTab?.('resumes')}
          className="group flex flex-col items-start gap-1 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 text-left transition-colors hover:border-[var(--color-rule)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
        >
          <span className="flex w-full items-center justify-between">
            <span className="text-[12px] font-medium text-[var(--color-ink)]">Resume versions</span>
            <ExternalLink className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)] transition-colors group-hover:text-[var(--color-accent)]" aria-hidden="true" />
          </span>
          <span className="text-[11px] leading-relaxed text-[var(--color-ink-tertiary)]">Master Resume and tailored versions are managed in Resume Studio.</span>
        </button>
      </section>

      <p className="text-[11px] leading-relaxed text-[var(--color-ink-tertiary)]">
        Account email and candidate identity are managed together in this workspace. Sign-in is handled by your local session; no passwords, sessions or access tokens are shown here.
      </p>
    </div>
  );
};

/* ---------- Connected accounts section: Google/Microsoft + profile-managed integrations ---------- */

const AccountsSection: React.FC<{ onNavigateTab?: (tab: string) => void }> = ({ onNavigateTab }) => (
  <div className="space-y-4">
    <IntegrationsSettingsTab embedded />

    {/* GitHub, Portfolio & LinkedIn sync lives in Candidate Profile */}
    <section aria-label="Other connected services" className="flex flex-col gap-2 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:p-5">
      <div className="min-w-0">
        <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">GitHub, Portfolio &amp; LinkedIn</h3>
        <p className="mt-0.5 text-[11px] leading-relaxed text-[var(--color-ink-tertiary)]">
          Code and profile sync for matching are managed from the Candidate Profile integration hub.
        </p>
      </div>
      <button
        type="button"
        onClick={() => onNavigateTab?.('profile')}
        className="inline-flex min-h-[32px] shrink-0 items-center gap-1.5 self-start rounded-lg border border-white/[0.10] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 sm:self-auto"
      >
        <span>Open Candidate Profile</span>
        <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
      </button>
    </section>
  </div>
);
