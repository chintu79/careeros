import React, { useState, useEffect, useRef, useMemo } from 'react';
import { 
  User, 
  Globe, 
  Sparkles, 
  Save, 
  CheckCircle2, 
  ExternalLink, 
  RefreshCw, 
  Plus, 
  Trash2,
  ShieldCheck,
  Cpu,
  FileText,
  UploadCloud,
  Check,
  CheckSquare,
  Square
} from 'lucide-react';

function readinessLabel(stage?: string | null): string {
  switch (stage) {
    case 'high_confidence_readiness': return 'High confidence';
    case 'core_evidence_ready': return 'Core ready';
    case 'getting_started': return 'Getting started';
    default: return stage ?? 'Not rated';
  }
}

const CATEGORY_LABELS: Record<string, string> = {
  basic_info: 'Basic info',
  education: 'Education',
  technical_skills: 'Skills',
  projects: 'Projects',
  resume: 'Resume',
  career_goals: 'Career goals',
};

function categoryLabel(key: string): string {
  return CATEGORY_LABELS[key] ?? key.replace(/_/g, ' ');
}

const Github = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
    <path d="M9 18c-4.51 2-5-2-7-2" />
  </svg>
);

const Linkedin = ({ className = "w-5 h-5" }: { className?: string }) => (
  <svg aria-hidden="true" className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M16 8a6 6 0 0 1 6 6v7h-4v-7a2 2 0 0 0-2-2 2 2 0 0 0-2 2v7h-4v-7a6 6 0 0 1 6-6z" />
    <rect width="4" height="12" x="2" y="9" />
    <circle cx="4" cy="4" r="2" />
  </svg>
);
import { CandidateProfile } from '../../types';
import type { ProfileCompletenessAssessment } from '../../types';
import { Modal } from '../ui/Modal';
import { PageHeader } from '../ui/PageHeader';
import {
  fetchCandidateProfile,
  updateCandidateProfile,
  syncGitHubProfile,
  syncPortfolio,
  importLinkedInData,
  approveIntegrations,
  parseResumeUpload,
  fetchProfileCompleteness,
  addCandidateSkill,
  deleteCandidateSkill
} from '../../services/api';

export const CandidateProfileView: React.FC = () => {
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [completeness, setCompleteness] = useState<ProfileCompletenessAssessment | null>(null);
  const [completenessLoading, setCompletenessLoading] = useState(true);
  const [completenessError, setCompletenessError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillLevel, setNewSkillLevel] = useState<'intermediate' | 'advanced' | 'expert'>('intermediate');
  const [skillAddError, setSkillAddError] = useState<string | null>(null);
  const [addSkillPending, setAddSkillPending] = useState(false);
  const [removingSkill, setRemovingSkill] = useState<string | null>(null);
  const [skillRemoveError, setSkillRemoveError] = useState<string | null>(null);
  const skillProvenance = useMemo(() => {
    const map = new Map<string, { status: string; source: string }>();
    completeness?.skills_summary?.items?.forEach((item) => {
      const key = (item.raw_name ?? item.name ?? '').trim().toLowerCase();
      if (!key) return;
      map.set(key, { status: String(item.status ?? '').trim(), source: String(item.verification_source ?? '').trim() });
    });
    return map;
  }, [completeness]);

  // Integrations state
  const [githubUser, setGithubUser] = useState('');
  const [portfolioUrl, setPortfolioUrl] = useState('');
  const [isSyncingGithub, setIsSyncingGithub] = useState(false);
  const [isSyncingPortfolio, setIsSyncingPortfolio] = useState(false);
  const [discoveredGithubData, setDiscoveredGithubData] = useState<any>(null);
  const [discoveredPortfolioData, setDiscoveredPortfolioData] = useState<any>(null);

  // Resume Parsing state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isParsingResume, setIsParsingResume] = useState(false);
  const [parsedResumeData, setParsedResumeData] = useState<any | null>(null);
  const [showResumeModal, setShowResumeModal] = useState(false);
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [selectedProjects, setSelectedProjects] = useState<number[]>([]);
  const [applyCandidateDetails, setApplyCandidateDetails] = useState(true);

  // LinkedIn manual import modal
  const [showLinkedInModal, setShowLinkedInModal] = useState(false);
  const [linkedInUrl, setLinkedInUrl] = useState('');
  const [linkedInHeadline, setLinkedInHeadline] = useState('');
  const [linkedInSkills, setLinkedInSkills] = useState('');

  const handleResumeFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsParsingResume(true);
    try {
      const data = await parseResumeUpload(file);
      setParsedResumeData(data);
      setSelectedSkills(data.detected_skills?.map((s: any) => s.name) || []);
      setSelectedProjects(data.detected_projects?.map((_: any, idx: number) => idx) || []);
      setShowResumeModal(true);
    } catch (err: any) {
      alert(`Resume parsing failed: ${err.message}`);
    } finally {
      setIsParsingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleApproveResumeData = async () => {
    if (!parsedResumeData) return;
    try {
      const approvedSkills = parsedResumeData.detected_skills?.filter((s: any) => 
        selectedSkills.includes(s.name)
      ) || [];

      const approvedProjects = parsedResumeData.detected_projects?.filter((_: any, idx: number) => 
        selectedProjects.includes(idx)
      ) || [];

      const candidateUpdates = applyCandidateDetails ? parsedResumeData.candidate_draft : undefined;

      const updated = await approveIntegrations({
        approved_skills: approvedSkills,
        approved_projects: approvedProjects,
        candidate_updates: candidateUpdates
      });
      setProfile(updated);
      setShowResumeModal(false);
      setParsedResumeData(null);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      alert(`Failed to merge resume data: ${err.message}`);
    }
  };

  const toggleSkill = (skillName: string) => {
    setSelectedSkills(prev => 
      prev.includes(skillName) ? prev.filter(s => s !== skillName) : [...prev, skillName]
    );
  };

  const toggleProject = (idx: number) => {
    setSelectedProjects(prev => 
      prev.includes(idx) ? prev.filter(i => i !== idx) : [...prev, idx]
    );
  };


  const loadCompleteness = async () => {
    setCompletenessLoading(true);
    try {
      const data = await fetchProfileCompleteness();
      setCompleteness(data);
      setCompletenessError(null);
    } catch (err) {
      setCompleteness(null);
      setCompletenessError(err instanceof Error ? err.message : 'Failed to fetch candidate readiness');
    } finally {
      setCompletenessLoading(false);
    }
  };

  const loadProfile = async () => {
    setLoading(true);
    try {
      const [data, readiness] = await Promise.all([
        fetchCandidateProfile(),
        fetchProfileCompleteness().catch(() => null)
      ]);
      setProfile(data);
      setCompleteness(readiness);
      setCompletenessLoading(false);
      setCompletenessError(null);
      if (data.github_username) setGithubUser(data.github_username);
      if (data.portfolio_url) setPortfolioUrl(data.portfolio_url);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const handleAddSkill = async () => {
    if (!profile || addSkillPending) return;
    const raw = newSkillName.trim();
    if (!raw) {
      setSkillAddError('Enter a skill name.');
      return;
    }
    const normKey = raw.toLowerCase();
    if ((profile.skills ?? []).some(s => (s.name || '').trim().toLowerCase() === normKey)) {
      setSkillAddError(`"${raw}" is already in your profile.`);
      return;
    }
    setAddSkillPending(true);
    setSkillAddError(null);
    try {
      const updated = await addCandidateSkill({ name: raw, category: 'General', level: newSkillLevel });
      setProfile(updated);
      setNewSkillName('');
      setNewSkillLevel('intermediate');
      loadCompleteness();
    } catch (err) {
      console.error(err);
      setSkillAddError(err instanceof Error ? err.message : 'Failed to add skill');
    } finally {
      setAddSkillPending(false);
    }
  };

  const handleRemoveSkill = async (name: string, verified: boolean, source?: string) => {
    if (!profile || removingSkill) return;
    const target = (name || '').trim();
    if (!target) return;
    const provenanceNote = verified && source ? ` Verified by ${source}.` : verified ? ' Marked as verified.' : '';
    const confirmed = window.confirm(`Remove "${target}" from your profile?${provenanceNote} Removing it removes it from matching until you re-add it.`);
    if (!confirmed) return;
    setRemovingSkill(target);
    setSkillRemoveError(null);
    try {
      const updated = await deleteCandidateSkill(target);
      setProfile(updated);
      loadCompleteness();
    } catch (err) {
      console.error(err);
      setSkillRemoveError(err instanceof Error ? err.message : `Failed to remove "${target}"`);
    } finally {
      setRemovingSkill(null);
    }
  };

  const handleSaveProfile = async () => {
    if (!profile) return;
    setSaving(true);
    try {
      const updated = await updateCandidateProfile(profile);
      setProfile(updated);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err) {
      console.error(err);
    } finally {
      setSaving(false);
    }
  };

  const handleSyncGithub = async () => {
    if (!githubUser.trim()) return;
    setIsSyncingGithub(true);
    try {
      const data = await syncGitHubProfile(githubUser.trim());
      setDiscoveredGithubData(data);
    } catch (err: any) {
      alert(`GitHub sync error: ${err.message}`);
    } finally {
      setIsSyncingGithub(false);
    }
  };

  const handleSyncPortfolio = async () => {
    if (!portfolioUrl.trim()) return;
    setIsSyncingPortfolio(true);
    try {
      const data = await syncPortfolio(portfolioUrl.trim());
      setDiscoveredPortfolioData(data);
    } catch (err: any) {
      alert(`Portfolio scan error: ${err.message}`);
    } finally {
      setIsSyncingPortfolio(false);
    }
  };

  const handleApproveGithubData = async () => {
    if (!discoveredGithubData) return;
    try {
      const approvedSkills = discoveredGithubData.languages_detected?.map((lang: string) => ({
        name: lang,
        level: "intermediate",
        category: "language",
        evidence: `GitHub verified repository: ${discoveredGithubData.username}`
      })) || [];

      const approvedProjects = discoveredGithubData.projects_discovered?.map((p: any) => ({
        title: p.title,
        description: p.description,
        tech_stack: p.tech_stack,
        url: p.url,
        stars: p.stars
      })) || [];

      const updated = await approveIntegrations({
        approved_skills: approvedSkills,
        approved_projects: approvedProjects
      });
      setProfile(updated);
      setDiscoveredGithubData(null);
      alert("GitHub projects and languages successfully merged into Master Profile!");
    } catch (err) {
      console.error(err);
    }
  };

  const handleApprovePortfolioData = async () => {
    if (!discoveredPortfolioData) return;
    try {
      const approvedProjects = discoveredPortfolioData.projects_discovered?.map((p: any) => ({
        title: p.title,
        description: p.description,
        tech_stack: p.tech_stack,
        url: p.url
      })) || [];

      const updated = await approveIntegrations({
        approved_projects: approvedProjects
      });
      setProfile(updated);
      setDiscoveredPortfolioData(null);
      alert("Portfolio projects merged into Master Profile!");
    } catch (err) {
      console.error(err);
    }
  };

  const handleImportLinkedIn = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const skillList = linkedInSkills.split(',').map(s => s.trim()).filter(Boolean);
      const updated = await importLinkedInData({
        profile_url: linkedInUrl,
        headline: linkedInHeadline,
        skills: skillList
      });
      setProfile(updated);
      setShowLinkedInModal(false);
      alert("LinkedIn profile details imported!");
    } catch (err) {
      console.error(err);
    }
  };

  if (loading || !profile) {
    return (
      <div className="flex flex-col items-center gap-3 py-24 text-slate-400">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-emerald-400 border-t-transparent" />
        <p className="text-[12px]">Loading your profile…</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Personal"
        title="Profile"
        description="The single source of truth for resume tailoring, recommendations and application submissions."
        actions={
          <button
            type="button"
            onClick={handleSaveProfile}
            disabled={saving}
            className="inline-flex min-h-[34px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3.5 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
          >
            <Save className="h-3.5 w-3.5" aria-hidden="true" />
            <span>{saving ? 'Saving…' : 'Save changes'}</span>
          </button>
        }
      />

      {saveSuccess && (
        <div role="status" aria-live="polite" className="flex items-center gap-2 rounded-lg border border-emerald-400/25 bg-emerald-400/[0.05] px-3 py-2 text-[12px] text-emerald-300">
          <CheckCircle2 className="w-4 h-4" aria-hidden="true" />
          <span>Profile changes saved successfully!</span>
        </div>
      )}

      {/* Readiness & Evidence — grounded in /api/candidate/completeness */}
      <section aria-label="Profile readiness and evidence" className="rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 sm:p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 className="section-title">Readiness &amp; evidence</h2>
            <p className="mt-1 max-w-2xl text-[12px] leading-relaxed text-[var(--color-ink-2)]">
              {completeness?.disclaimer ?? 'Evidence ratings are computed from real project, GitHub and resume data — they are never inferred.'}
            </p>
          </div>
          {completeness && (
            <div className="shrink-0 rounded-lg border border-emerald-400/25 bg-emerald-400/[0.04] px-3 py-2 text-center" aria-label={`Readiness score ${completeness.completeness_score} percent`}>
              <span className="block font-mono tnum text-[28px] font-semibold leading-none text-[var(--color-accent)]">{completeness.completeness_score}</span>
              <span className="mt-1 block text-[10px] font-medium text-emerald-300">{readinessLabel(completeness.readiness_stage)}</span>
            </div>
          )}
        </div>

        {completenessError && !completeness && (
          <p role="alert" className="mt-3 flex items-center gap-2 text-[11px] text-amber-200/90">
            <span aria-hidden="true">!</span>
            <span>Readiness data could not be loaded: {completenessError}</span>
          </p>
        )}

        {completeness && (
          <>
            <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6" aria-label="Evidence category scores">
              {Object.entries(completeness.category_scores).map(([key, value]) => (
                <div key={key} className="rounded-md border border-white/[0.06] bg-[var(--color-paper-2)] p-2.5">
                  <p className="field-label">{categoryLabel(key)}</p>
                  <p className="mt-1 font-mono text-[13px] text-[var(--color-ink)] tnum">{value.score}<span className="text-slate-500">/{value.max}</span></p>
                  <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-[var(--color-paper-3)]" role="progressbar" aria-valuenow={value.score} aria-valuemin={0} aria-valuemax={value.max} aria-label={`${categoryLabel(key)} ${value.score} of ${value.max}`}>
                    <div className="h-full bg-emerald-400" style={{ width: `${value.max ? Math.min(100, Math.round((value.score / value.max) * 100)) : 0}%` }} />
                  </div>
                </div>
              ))}
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {/* Verified evidence — GitHub / project / resume backed */}
              <div className="rounded-lg border border-emerald-400/10 bg-emerald-400/[0.03] p-3.5">
                <h3 className="flex items-center gap-1.5 text-[11px] font-medium text-emerald-300">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Verified evidence ({completeness.verified_evidence.length})
                </h3>
                {completeness.verified_evidence.length > 0 ? (
                  <ul className="mt-2 list-disc list-inside space-y-1 text-[11px] leading-snug text-slate-300">
                    {completeness.verified_evidence.slice(0, 5).map((line, i) => <li key={i}>{line}</li>)}
                  </ul>
                ) : (
                  <p className="mt-2 text-[11px] leading-snug text-slate-500">No verified evidence on file yet. Link GitHub and add a project to build real evidence.</p>
                )}
              </div>

              {/* Unverified / self-reported warnings */}
              <div className="rounded-lg border border-amber-400/10 bg-amber-400/[0.03] p-3.5">
                <h3 className="flex items-center gap-1.5 text-[11px] font-medium text-amber-300">
                  <ShieldCheck className="h-3.5 w-3.5" aria-hidden="true" /> Unverified / self-reported ({completeness.unverified_evidence.length})
                </h3>
                {completeness.unverified_evidence.length > 0 ? (
                  <ul className="mt-2 list-disc list-inside space-y-1 text-[11px] leading-snug text-slate-300">
                    {completeness.unverified_evidence.slice(0, 5).map((line, i) => <li key={i}>{line}</li>)}
                  </ul>
                ) : (
                  <p className="mt-2 text-[11px] leading-snug text-slate-500">No self-reported skills pending verification.</p>
                )}
                {completeness.actionable_recommendations.length > 0 && (
                  <ul className="mt-3 space-y-1 border-t border-amber-400/10 pt-3">
                    {completeness.actionable_recommendations.slice(0, 3).map((rec, i) => (
                      <li key={i} className="text-[11px] leading-snug text-amber-100/90">
                        <strong className="text-amber-200">Recommend:</strong> {rec.title}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </>
        )}
      </section>

      {/* External Integration Hub */}
      <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
        {/* GitHub Card */}
        <div className="flex flex-col justify-between space-y-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13]"
        >
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Github className="h-4 w-4 text-slate-400" />
                <span className="text-[12px] font-medium text-[var(--color-ink)]">GitHub Sync</span>
              </div>
              {profile.github_data?.connected && (
                <span className="rounded border border-emerald-400/25 bg-emerald-400/[0.06] px-1.5 py-0.5 text-[10px] font-medium text-emerald-300">
                  Connected
                </span>
              )}
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">
              Retrieves public repositories, tech stacks, and topics without scraping private repositories.
            </p>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                aria-label="GitHub username to sync"
                placeholder="GitHub username..."
                value={githubUser}
                onChange={e => setGithubUser(e.target.value)}
                className="input-base min-h-[32px] min-w-0 flex-1 py-1 text-[11px]"
              />
              <button
                type="button"
                onClick={handleSyncGithub}
                disabled={isSyncingGithub}
                aria-label="Sync GitHub profile"
                className="inline-flex min-h-[32px] shrink-0 items-center rounded-md border border-white/[0.10] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                {isSyncingGithub ? 'Scanning...' : 'Sync'}
              </button>
            </div>

            {discoveredGithubData && (
              <div className="mt-2 space-y-2 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.03] p-3">
                <span className="block text-[10px] font-medium text-emerald-300">Discovered Work</span>
                <p className="text-[11px] leading-relaxed text-slate-400">
                  Found {discoveredGithubData.projects_discovered?.length} public projects in {discoveredGithubData.languages_detected?.join(', ')}.
                </p>
                <button
                  type="button"
                  onClick={handleApproveGithubData}
                  className="whitespace-nowrap w-full rounded-md bg-emerald-400 py-1.5 text-[11px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300"
                >
                  Approve and merge
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Portfolio Card */}
        <div className="flex flex-col justify-between space-y-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13]"
        >
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Globe className="h-4 w-4 text-slate-400" />
                <span className="text-[12px] font-medium text-[var(--color-ink)]">Portfolio Site</span>
              </div>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">
              Safely scans public developer website with SSRF protection against private network queries.
            </p>
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                aria-label="Portfolio website URL to scan"
                placeholder="https://yourportfolio.dev"
                value={portfolioUrl}
                onChange={e => setPortfolioUrl(e.target.value)}
                className="input-base min-h-[32px] min-w-0 flex-1 py-1 text-[11px]"
              />
              <button
                type="button"
                onClick={handleSyncPortfolio}
                disabled={isSyncingPortfolio}
                aria-label="Scan portfolio website"
                className="inline-flex min-h-[32px] shrink-0 items-center rounded-md border border-white/[0.10] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                {isSyncingPortfolio ? 'Scanning...' : 'Scan'}
              </button>
            </div>

            {discoveredPortfolioData && (
              <div className="mt-2 space-y-2 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.03] p-3">
                <span className="block text-[10px] font-medium text-emerald-300">Portfolio Parsed</span>
                <p className="text-[11px] leading-relaxed text-slate-400">
                  Extracted {discoveredPortfolioData.projects_discovered?.length} projects from {discoveredPortfolioData.page_title}.
                </p>
                <button
                  onClick={handleApprovePortfolioData}
                  className="whitespace-nowrap w-full rounded-md bg-emerald-400 py-1.5 text-[11px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300"
                >
                  Approve and merge
                </button>
              </div>
            )}
          </div>
        </div>

        {/* LinkedIn Card */}
        <div className="flex flex-col justify-between space-y-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13]"
        >
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <Linkedin className="h-4 w-4 text-slate-400" />
                <span className="text-[12px] font-medium text-[var(--color-ink)]">LinkedIn Import</span>
              </div>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">
              Import skills and experience from your LinkedIn profile. Respects privacy and access controls.
            </p>
          </div>
          <div className="space-y-2">
            <button
              onClick={() => setShowLinkedInModal(true)}
              className="w-full rounded-md border border-white/[0.10] py-2 text-[12px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
            >
              Import LinkedIn Details
            </button>
            <div className="flex items-center space-x-1.5 text-[10px] text-slate-400">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
              <span>Never bypasses OAuth or scrapes</span>
            </div>
          </div>
        </div>

        {/* PDF Resume Parser Card */}
        <div className="flex flex-col justify-between space-y-3 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4 transition-colors hover:border-white/[0.13]"
        >
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-2">
                <FileText className="h-4 w-4 text-slate-400" />
                <span className="text-[12px] font-medium text-[var(--color-ink)]">Resume Parser</span>
              </div>
              <span className="rounded border border-white/[0.08] bg-white/[0.03] px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
                PDF / text
              </span>
            </div>
            <p className="mt-1.5 text-[11px] leading-relaxed text-slate-500">
              Extract candidate identity, education, technical skills, and project portfolio from PDF or text resume.
            </p>
          </div>
          <div className="space-y-2">
            <input
              type="file"
              ref={fileInputRef}
              accept=".pdf,.txt,.md"
              onChange={handleResumeFileSelect}
              className="hidden"
              aria-label="Upload resume file"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isParsingResume}
              className="flex w-full items-center justify-center gap-1.5 whitespace-nowrap rounded-md border border-white/[0.10] py-2 text-[12px] font-medium text-slate-300 transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)]"
            >
              {isParsingResume ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  <span>Parsing…</span>
                </>
              ) : (
                <>
                  <UploadCloud className="whitespace-nowrap w-3.5 h-3.5" />
                  <span>Parse resume</span>
                </>
              )}
            </button>
            <div className="flex items-center space-x-1.5 text-[10px] text-slate-400">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
              <span>Preview & approve before merging</span>
            </div>
          </div>
        </div>
      </div>

      {/* Profile Form Grid */}
      <div className="grid grid-cols-1 gap-2.5 lg:grid-cols-2">
        {/* Core Identity */}
        <div className="space-y-4 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
          <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">Candidate Identity & Education</h3>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="candidate-full-name" className="field-label mb-1 block">Full Name</label>
              <input
                id="candidate-full-name"
                type="text"
                value={profile.name ?? ''}
                onChange={e => setProfile({ ...profile, name: e.target.value })}
                className="input-base min-w-0"
              />
            </div>
            <div>
              <label htmlFor="candidate-email" className="field-label mb-1 block">Email</label>
              <input
                id="candidate-email"
                type="email"
                value={profile.email ?? ''}
                onChange={e => setProfile({ ...profile, email: e.target.value })}
                className="input-base min-w-0"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="candidate-phone" className="field-label mb-1 block">Phone</label>
              <input
                id="candidate-phone"
                type="text"
                value={profile.phone || ''}
                onChange={e => setProfile({ ...profile, phone: e.target.value })}
                className="input-base min-w-0"
              />
            </div>
            <div>
              <label htmlFor="candidate-location" className="field-label mb-1 block">Location</label>
              <input
                id="candidate-location"
                type="text"
                value={profile.location || ''}
                onChange={e => setProfile({ ...profile, location: e.target.value })}
                className="input-base min-w-0"
              />
            </div>
          </div>

          <div>
            <label htmlFor="candidate-bio" className="field-label mb-1 block">Professional Bio</label>
            <textarea
              id="candidate-bio"
              value={profile.bio || ''}
              onChange={e => setProfile({ ...profile, bio: e.target.value })}
              className="input-base min-w-0 h-20 resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="candidate-degree" className="field-label mb-1 block">Degree</label>
              <input
                id="candidate-degree"
                type="text"
                value={profile.degree ?? ''}
                onChange={e => setProfile({ ...profile, degree: e.target.value })}
                className="input-base min-w-0"
              />
            </div>
            <div>
              <label htmlFor="candidate-grad-year" className="field-label mb-1 block">Graduation Year</label>
              <input
                id="candidate-grad-year"
                type="number"
                value={profile.graduation_year ?? ''}
                onChange={e => setProfile({ ...profile, graduation_year: Number(e.target.value) })}
                className="input-base min-w-0"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="candidate-college" className="field-label mb-1 block">College</label>
              <input
                id="candidate-college"
                type="text"
                value={profile.college ?? ''}
                onChange={e => setProfile({ ...profile, college: e.target.value })}
                className="input-base min-w-0"
              />
            </div>
            <div>
              <label htmlFor="candidate-cgpa" className="field-label mb-1 block">CGPA</label>
              <input
                id="candidate-cgpa"
                type="number"
                step="0.01"
                value={profile.cgpa ?? ''}
                onChange={e => setProfile({ ...profile, cgpa: Number(e.target.value) })}
                className="input-base min-w-0"
              />
            </div>
          </div>
        </div>

        {/* Skills & Verified Projects */}
        <div className="space-y-4 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-4">
          <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">Verified Skills & Hands-On Projects</h3>

          {/* Skills List */}
          <div>
            <span className="mb-2 block text-[10px] font-medium text-slate-500">
              Skills ({completeness?.skills_summary ? `${completeness.skills_summary.verified ?? 0} verified / ${completeness.skills_summary.total ?? (profile.skills?.length ?? 0)} total` : (profile.skills?.length ?? 0)})
            </span>
            <div
              tabIndex={0}
              role="region"
              aria-label="Skills list"
              className="flex max-h-36 flex-wrap gap-1.5 overflow-y-auto rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
            >
              {profile.skills?.map((s, idx) => {
                const key = (s.name || '').trim().toLowerCase();
                const prov = skillProvenance.get(key);
                const verified = prov?.status?.toLowerCase() === 'verified';
                return (
                  <span
                    key={idx}
                    className={`flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] ${
                      verified
                        ? 'border-emerald-400/25 bg-emerald-400/[0.05] text-slate-200'
                        : 'border-white/[0.07] bg-white/[0.03] text-slate-300'
                    }`}
                    title={prov?.source ? `Source: ${prov.source}` : undefined}
                  >
                    {verified && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shrink-0" aria-hidden="true" />}
                    <span>{s.name}</span>
                    <span className="text-[10px] text-slate-400">({s.level})</span>
                    <button
                      type="button"
                      aria-label={`Remove ${s.name}`}
                      disabled={removingSkill === (s.name || '').trim()}
                      onClick={() => handleRemoveSkill(s.name, verified, prov?.source)}
                      className="ml-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded text-slate-500 transition-colors hover:bg-rose-400/10 hover:text-rose-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400/60 disabled:opacity-50"
                    >
                      <Trash2 className="h-3 w-3" aria-hidden="true" />
                    </button>
                  </span>
                );
              })}
            </div>
            {skillRemoveError && (
              <p role="alert" className="mt-2 text-[11px] text-amber-200/90">{skillRemoveError}</p>
            )}

            {/* Add a skill — dedupe-checked locally, same persistence as global save */}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <label htmlFor="new-skill-name" className="sr-only">Add a skill</label>
              <input
                id="new-skill-name"
                type="text"
                value={newSkillName}
                onChange={e => { setNewSkillName(e.target.value); if (skillAddError) setSkillAddError(null); }}
                onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), handleAddSkill())}
                placeholder="Add a skill, e.g. React"
                className="input-base min-w-0 flex-1"
                aria-describedby="skill-add-error"
              />
              <label htmlFor="new-skill-level" className="sr-only">Skill level</label>
              <select
                id="new-skill-level"
                value={newSkillLevel}
                onChange={e => setNewSkillLevel(e.target.value as 'intermediate' | 'advanced' | 'expert')}
                className="input-base w-auto shrink-0"
              >
                <option value="intermediate">Intermediate</option>
                <option value="advanced">Advanced</option>
                <option value="expert">Expert</option>
              </select>
              <button
                type="button"
                onClick={handleAddSkill}
                disabled={addSkillPending || !newSkillName.trim()}
                className="inline-flex min-h-[36px] shrink-0 items-center gap-1.5 rounded-lg border border-emerald-400/30 bg-emerald-400/[0.06] px-2.5 text-[12px] font-medium text-emerald-300 transition-colors hover:bg-emerald-400/[0.10] disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <Plus className="h-4 w-4" aria-hidden="true" />
                <span>{addSkillPending ? 'Adding…' : 'Add skill'}</span>
              </button>
            </div>
            {skillAddError && (
              <p id="skill-add-error" role="alert" className="mt-1.5 text-[11px] text-amber-200/90">{skillAddError}</p>
            )}
            <p className="mt-1 text-[10px] text-slate-500">Skill names are matched case-insensitively, so duplicates are skipped. Add skill persists immediately. Verified chips link back to the project or repository that produced them.</p>
          </div>

          {/* Projects List */}
          <div>
            <span className="mb-2 block text-[10px] font-medium text-slate-500">Projects Portfolio ({profile.projects?.length || 0})</span>
            <div
              tabIndex={0}
              role="region"
              aria-label="Projects Portfolio list"
              className="max-h-52 space-y-2 overflow-y-auto focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
            >
              {profile.projects?.map((p, idx) => (
                <div key={idx} className="space-y-1 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-[12px] font-medium text-[var(--color-ink)]">{p.title}</span>
                    {p.stars !== undefined && p.stars > 0 && (
                      <span className="font-mono text-[10px] text-amber-300">★ {p.stars}</span>
                    )}
                  </div>
                  <p className="text-[11px] leading-relaxed text-slate-500">{p.description}</p>
                  <div className="flex flex-wrap gap-1 pt-1">
                    {p.tech_stack?.map((t, ti) => (
                      <span key={ti} className="rounded bg-white/[0.04] px-1.5 py-0.5 font-mono text-[10px] text-slate-400">
                        {t}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* LinkedIn Import Modal */}
      <Modal
        isOpen={showLinkedInModal}
        onClose={() => setShowLinkedInModal(false)}
        title="Import LinkedIn Profile Details"
        size="md"
      >
        <form onSubmit={handleImportLinkedIn} className="space-y-4 text-xs">
          <div>
            <label htmlFor="linkedin-import-url" className="field-label mb-1 block">LinkedIn Profile URL</label>
            <input
              id="linkedin-import-url"
              type="url"
              placeholder="https://linkedin.com/in/username"
              value={linkedInUrl}
              onChange={e => setLinkedInUrl(e.target.value)}
              className="input-base"
            />
          </div>
          <div>
            <label htmlFor="linkedin-import-headline" className="field-label mb-1 block">Headline</label>
            <input
              id="linkedin-import-headline"
              type="text"
              placeholder="e.g. Computer Science Student | Backend Developer"
              value={linkedInHeadline}
              onChange={e => setLinkedInHeadline(e.target.value)}
              className="input-base"
            />
          </div>
          <div>
            <label htmlFor="linkedin-import-skills" className="field-label mb-1 block">Skills (Comma-separated)</label>
            <textarea
              id="linkedin-import-skills"
              placeholder="Python, C++, Docker, React, PostgreSQL..."
              value={linkedInSkills}
              onChange={e => setLinkedInSkills(e.target.value)}
              className="input-base h-20 resize-none"
            />
          </div>

          <div className="flex justify-end gap-2 border-t border-white/[0.06] pt-3">
            <button
              type="button"
              onClick={() => setShowLinkedInModal(false)}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-primary"
            >
              Import Data
            </button>
          </div>
        </form>
      </Modal>

      {/* Resume Review & Approval Modal */}
      <Modal
        isOpen={showResumeModal}
        onClose={() => setShowResumeModal(false)}
        title="Review & Approve Extracted Resume Data"
        size="lg"
      >
        {parsedResumeData && (
          <div className="space-y-4 text-xs">
            <div className="space-y-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
                  <User className="w-4 h-4 text-slate-400" />
                  <span>Extracted Identity & Education</span>
                </span>
                <label className="flex cursor-pointer items-center gap-2 text-[12px] text-slate-300">
                  <input
                    type="checkbox"
                    checked={applyCandidateDetails}
                    onChange={e => setApplyCandidateDetails(e.target.checked)}
                    className="rounded border-white/[0.12] bg-[var(--color-paper-2)] text-emerald-400 focus:ring-emerald-400/60"
                  />
                  <span>Update Profile Identity & Contact</span>
                </label>
              </div>

              <div className="grid grid-cols-2 gap-2 font-mono text-[11px] text-slate-300 sm:grid-cols-3">
                <div className="rounded border border-white/[0.05] bg-[var(--color-paper)] p-2">
                  <span className="block text-[10px] text-slate-500">Name</span>
                  <span className="text-[12px] font-medium text-[var(--color-ink)]">{parsedResumeData.candidate_draft?.name || "Not Detected"}</span>
                </div>
                <div className="rounded border border-white/[0.05] bg-[var(--color-paper)] p-2">
                  <span className="block text-[10px] text-slate-500">Email</span>
                  <span className="block truncate font-medium text-[var(--color-ink)]">{parsedResumeData.candidate_draft?.email || "Not Detected"}</span>
                </div>
                <div className="rounded border border-white/[0.05] bg-[var(--color-paper)] p-2">
                  <span className="block text-[10px] text-slate-500">Phone</span>
                  <span className="text-[12px] font-medium text-[var(--color-ink)]">{parsedResumeData.candidate_draft?.phone || "Not Detected"}</span>
                </div>
                <div className="rounded border border-white/[0.05] bg-[var(--color-paper)] p-2">
                  <span className="block text-[10px] text-slate-500">College</span>
                  <span className="block truncate font-medium text-[var(--color-ink)]">{parsedResumeData.candidate_draft?.college || "Not Detected"}</span>
                </div>
                <div className="rounded border border-white/[0.05] bg-[var(--color-paper)] p-2">
                  <span className="block text-[10px] text-slate-500">Degree & Year</span>
                  <span className="text-[12px] font-medium text-[var(--color-ink)]">{parsedResumeData.candidate_draft?.degree || "B.Tech"} ({parsedResumeData.candidate_draft?.graduation_year || "2025"})</span>
                </div>
                <div className="rounded border border-white/[0.05] bg-[var(--color-paper)] p-2">
                  <span className="block text-[10px] text-slate-500">CGPA</span>
                  <span className="text-[12px] font-medium text-[var(--color-ink)]">{parsedResumeData.candidate_draft?.cgpa || "N/A"}</span>
                </div>
              </div>
            </div>

            {/* Extracted Skills */}
            <div className="space-y-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
                  <Cpu className="w-4 h-4 text-emerald-400" />
                  <span>Detected Skills ({selectedSkills.length} of {parsedResumeData.detected_skills?.length || 0} Selected)</span>
                </span>
                <div className="flex items-center space-x-2 text-[11px]">
                  <button
                    type="button"
                    onClick={() => setSelectedSkills(parsedResumeData.detected_skills?.map((s: any) => s.name) || [])}
                    className="text-emerald-400 hover:underline"
                  >
                    Select All
                  </button>
                  <span className="text-slate-600">•</span>
                  <button
                    type="button"
                    onClick={() => setSelectedSkills([])}
                    className="text-slate-400 hover:underline"
                  >
                    Clear All
                  </button>
                </div>
              </div>

              <div className="flex max-h-36 flex-wrap gap-1.5 overflow-y-auto rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-2">
                {parsedResumeData.detected_skills?.map((s: any, idx: number) => {
                  const isChecked = selectedSkills.includes(s.name);
                  return (
                    <button
                      key={idx}
                      type="button"
                      onClick={() => toggleSkill(s.name)}
                      className={`px-2.5 py-1 rounded-lg text-xs font-medium transition flex items-center space-x-1.5 border ${
                        isChecked
                          ? 'border-emerald-400/30 bg-emerald-400/[0.08] text-emerald-300'
                          : 'border-white/[0.06] bg-white/[0.02] text-slate-500 line-through'
                      }`}
                    >
                      <span>{s.name}</span>
                      <span className="text-[10px] text-slate-400">({s.category})</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Extracted Projects */}
            {parsedResumeData.detected_projects?.length > 0 && (
              <div className="space-y-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] p-3.5">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-1.5 text-[10px] font-medium text-slate-400">
                    <Sparkles className="w-4 h-4 text-slate-400" />
                    <span>Detected Projects ({selectedProjects.length} of {parsedResumeData.detected_projects.length} Selected)</span>
                  </span>
                </div>

                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {parsedResumeData.detected_projects.map((p: any, idx: number) => {
                    const isChecked = selectedProjects.includes(idx);
                    return (
                      <div
                        key={idx}
                        onClick={() => toggleProject(idx)}
                        className={`p-2.5 rounded-lg border cursor-pointer transition ${
                          isChecked
                            ? 'bg-dark-850 border-emerald-500/30'
                            : 'bg-dark-850/50 border-dark-800 opacity-60'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-[var(--color-ink)] text-xs">{p.title}</span>
                          <span className={`text-[10px] font-bold ${isChecked ? 'text-emerald-400' : 'text-slate-600'}`}>
                            {isChecked ? 'SELECTED' : 'EXCLUDED'}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-2">{p.description}</p>
                        <div className="flex flex-wrap gap-1 mt-1.5">
                          {p.tech_stack?.map((t: string, ti: number) => (
                            <span key={ti} className="px-1.5 py-0.2 rounded text-[9px] bg-dark-800 text-slate-400">
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Footer Buttons */}
            <div className="flex items-center justify-between pt-3 border-t border-dark-750">
              <span className="text-[11px] text-slate-400">
                You retain full authority: only approved items will be added to your profile.
              </span>
              <div className="flex items-center space-x-2">
                <button
                  type="button"
                  onClick={() => setShowResumeModal(false)}
                  className="px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-750 text-slate-300 font-medium"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleApproveResumeData}
                  className="whitespace-nowrap px-4 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold transition"
                >
                  Approve and merge
                </button>
              </div>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

