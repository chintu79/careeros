import React, { useState, useEffect, useRef } from 'react';
import {
  Sparkles,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ArrowLeft,
  Save,
  Plus,
  Trash2,
  UploadCloud,
  FileText,
  Briefcase,
  GraduationCap,
  Code2,
  FolderGit2,
  ShieldCheck,
  ExternalLink,
  Info,
  Check,
  ChevronRight,
  RefreshCw,
  LogOut
} from 'lucide-react';
import {
  CandidateProfile,
  ProfileCompletenessAssessment,
  SkillTaxonomyResponse,
  SkillSummaryItem
} from '../../types';
import {
  fetchCandidateProfile,
  fetchProfileCompleteness,
  updateOnboardingProgress,
  completeOnboarding,
  fetchSkillsTaxonomy,
  addCandidateSkill,
  deleteCandidateSkill,
  addCandidateProject,
  deleteCandidateProject,
  parseResumeUpload,
  approveIntegrations,
  API_BASE
} from '../../services/api';

interface CandidateOnboardingViewProps {
  onComplete: () => void;
  onExit: () => void;
}

const STEPS = [
  { id: 1, name: 'Career Goals', icon: Briefcase, desc: 'Target roles & preferences' },
  { id: 2, name: 'Education', icon: GraduationCap, desc: 'Degree & eligibility' },
  { id: 3, name: 'Technical Skills', icon: Code2, desc: 'Core competencies' },
  { id: 4, name: 'Projects', icon: FolderGit2, desc: 'Portfolio & code evidence' },
  { id: 5, name: 'Resume', icon: FileText, desc: 'Upload & master document' },
  { id: 6, name: 'Readiness & Launch', icon: Sparkles, desc: 'Review & activate' }
];

export const CandidateOnboardingView: React.FC<CandidateOnboardingViewProps> = ({
  onComplete,
  onExit
}) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [completeness, setCompleteness] = useState<ProfileCompletenessAssessment | null>(null);
  const [taxonomy, setTaxonomy] = useState<SkillTaxonomyResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Step 1: Goals State
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [location, setLocation] = useState('');
  const [bio, setBio] = useState('');
  const [targetRoleInput, setTargetRoleInput] = useState('');
  const [targetRoles, setTargetRoles] = useState<string[]>([]);
  const [preferredLocations, setPreferredLocations] = useState<string[]>([]);
  const [locationInput, setLocationInput] = useState('');
  const [workplacePreference, setWorkplacePreference] = useState('any');
  const [workAuthorization, setWorkAuthorization] = useState('');

  // Step 2: Education State
  const [degree, setDegree] = useState('');
  const [college, setCollege] = useState('');
  const [gradYear, setGradYear] = useState<number | ''>('');
  const [cgpa, setCgpa] = useState<number | ''>('');
  const [hasExperience, setHasExperience] = useState(false);
  const [expTitle, setExpTitle] = useState('');
  const [expCompany, setExpCompany] = useState('');
  const [expDuration, setExpDuration] = useState('');
  const [expDescription, setExpDescription] = useState('');

  // Step 3: Skills State
  const [newSkillName, setNewSkillName] = useState('');
  const [newSkillCategory, setNewSkillCategory] = useState('Languages');
  const [newSkillLevel, setNewSkillLevel] = useState('intermediate');
  const [newSkillEvidence, setNewSkillEvidence] = useState('');

  // Step 4: Projects State
  const [showAddProject, setShowAddProject] = useState(false);
  const [projTitle, setProjTitle] = useState('');
  const [projDesc, setProjDesc] = useState('');
  const [projTechInput, setProjTechInput] = useState('');
  const [projTechs, setProjTechs] = useState<string[]>([]);
  const [projUrl, setProjUrl] = useState('');

  // Step 5: Resume State
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isParsingResume, setIsParsingResume] = useState(false);
  const [parsedDraft, setParsedDraft] = useState<any | null>(null);
  const [selectedParsedSkills, setSelectedParsedSkills] = useState<string[]>([]);
  const [selectedParsedProjects, setSelectedParsedProjects] = useState<number[]>([]);
  const [applyParsedDetails, setApplyParsedDetails] = useState(true);

  // Load candidate and completeness data
  useEffect(() => {
    loadInitialData();
  }, []);

  const loadInitialData = async () => {
    setLoading(true);
    try {
      const [cand, comp, tax] = await Promise.all([
        fetchCandidateProfile(),
        fetchProfileCompleteness(),
        fetchSkillsTaxonomy().catch(() => null)
      ]);

      setProfile(cand);
      setCompleteness(comp);
      setTaxonomy(tax);

      // Hydrate Step 1
      setName(cand.name || '');
      setEmail(cand.email || '');
      setPhone(cand.phone || '');
      setLocation(cand.location || '');
      setBio(cand.bio || '');
      const goals = cand.career_goals || {};
      setTargetRoles(goals.target_roles || ['Software Engineer', 'Full Stack Developer']);
      setPreferredLocations(cand.preferred_locations || ['Remote', 'San Francisco, CA']);
      setWorkplacePreference(goals.workplace_preference || 'any');
      setWorkAuthorization(cand.work_authorization || 'US Citizen');

      // Hydrate Step 2
      setDegree(cand.degree || '');
      setCollege(cand.college || '');
      setGradYear(cand.graduation_year || 2026);
      setCgpa(cand.cgpa || '');
      if (cand.experience && cand.experience.length > 0) {
        setHasExperience(true);
        const exp = cand.experience[0];
        setExpTitle(exp.title || '');
        setExpCompany(exp.company || '');
        setExpDuration(exp.duration || '');
        setExpDescription(exp.description || '');
      }

      // Resume step if previously in progress
      if (cand.onboarding_step && cand.onboarding_step >= 1 && cand.onboarding_step <= 6) {
        setCurrentStep(cand.onboarding_step);
      }
    } catch (err: any) {
      console.error('Failed to load initial onboarding data:', err);
      setErrorMessage(err.message || 'Failed to load profile data.');
    } finally {
      setLoading(false);
    }
  };

  const reloadCompleteness = async () => {
    try {
      const comp = await fetchProfileCompleteness();
      setCompleteness(comp);
    } catch (err) {
      console.error('Failed to reload completeness:', err);
    }
  };

  const handleSaveCurrentStep = async (nextStep?: number, markCompleted: boolean = false) => {
    setSaving(true);
    setSaveMessage(null);
    setErrorMessage(null);

    try {
      const stepToSave = nextStep || currentStep;
      let profileUpdates: Record<string, any> = {};

      if (currentStep === 1) {
        if (!name.trim()) throw new Error('Please enter your full name.');
        if (!email.trim()) throw new Error('Please enter your email address.');

        profileUpdates = {
          name,
          email,
          phone,
          location,
          bio,
          preferred_locations: preferredLocations,
          work_authorization: workAuthorization
        };
      } else if (currentStep === 2) {
        if (!degree.trim()) throw new Error('Please enter your degree or field of study.');
        if (!college.trim()) throw new Error('Please enter your college or university.');
        if (!gradYear) throw new Error('Please enter your graduation year.');

        profileUpdates = {
          degree,
          college,
          graduation_year: Number(gradYear),
          cgpa: cgpa ? Number(cgpa) : undefined,
          experience: hasExperience && expTitle.trim() ? [{
            title: expTitle.trim(),
            company: expCompany.trim() || 'Internship',
            duration: expDuration.trim() || '3 months',
            description: expDescription.trim() || 'Software engineering internship'
          }] : (profile?.experience || [])
        };
      }

      const res = await updateOnboardingProgress({
        step: stepToSave,
        status: markCompleted ? 'completed' : 'in_progress',
        career_goals: {
          target_roles: targetRoles,
          target_locations: preferredLocations,
          workplace_preference: workplacePreference,
          work_authorization: workAuthorization
        },
        profile_data: profileUpdates
      });

      setProfile(res.candidate);
      await reloadCompleteness();

      setSaveMessage('Progress saved.');
      setTimeout(() => setSaveMessage(null), 3000);

      if (nextStep) {
        setCurrentStep(nextStep);
      }
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to save progress.');
    } finally {
      setSaving(false);
    }
  };

  const handleAddSkill = async () => {
    if (!newSkillName.trim()) return;
    try {
      const updated = await addCandidateSkill({
        name: newSkillName.trim(),
        category: newSkillCategory,
        level: newSkillLevel,
        evidence: newSkillEvidence.trim()
      });
      setProfile(updated);
      setNewSkillName('');
      setNewSkillEvidence('');
      await reloadCompleteness();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to add skill.');
    }
  };

  const handleDeleteSkill = async (skillName: string) => {
    try {
      const updated = await deleteCandidateSkill(skillName);
      setProfile(updated);
      await reloadCompleteness();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete skill.');
    }
  };

  const handleCreateProject = async () => {
    if (!projTitle.trim()) {
      setErrorMessage('Project title is required.');
      return;
    }
    try {
      const updated = await addCandidateProject({
        title: projTitle.trim(),
        description: projDesc.trim() || 'Software project',
        tech_stack: projTechs.length > 0 ? projTechs : ['TypeScript', 'React'],
        url: projUrl.trim()
      });
      setProfile(updated);
      setShowAddProject(false);
      setProjTitle('');
      setProjDesc('');
      setProjTechs([]);
      setProjUrl('');
      await reloadCompleteness();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to add project.');
    }
  };

  const handleDeleteProject = async (index: number) => {
    try {
      const updated = await deleteCandidateProject(index);
      setProfile(updated);
      await reloadCompleteness();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to delete project.');
    }
  };

  const handleResumeUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsParsingResume(true);
    setErrorMessage(null);
    try {
      const parsed = await parseResumeUpload(file);
      setParsedDraft(parsed);
      setSelectedParsedSkills(parsed.detected_skills?.map((s: any) => s.name) || []);
      setSelectedParsedProjects(parsed.detected_projects?.map((_: any, idx: number) => idx) || []);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to parse resume.');
    } finally {
      setIsParsingResume(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleApproveResumeData = async () => {
    if (!parsedDraft) return;
    try {
      const approvedSkills = parsedDraft.detected_skills?.filter((s: any) =>
        selectedParsedSkills.includes(s.name)
      ) || [];

      const approvedProjects = parsedDraft.detected_projects?.filter((_: any, idx: number) =>
        selectedParsedProjects.includes(idx)
      ) || [];

      const candidateUpdates = applyParsedDetails ? parsedDraft.candidate_draft : undefined;

      const updated = await approveIntegrations({
        approved_skills: approvedSkills,
        approved_projects: approvedProjects,
        candidate_updates: candidateUpdates
      });

      setProfile(updated);
      setParsedDraft(null);
      await reloadCompleteness();
      setSaveMessage('Resume data merged successfully.');
      setTimeout(() => setSaveMessage(null), 3000);
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to merge resume data.');
    }
  };

  const handleCompleteAndActivate = async () => {
    setSaving(true);
    setErrorMessage(null);
    try {
      await completeOnboarding();
      onComplete();
    } catch (err: any) {
      setErrorMessage(err.message || 'Failed to complete onboarding.');
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3 text-[var(--color-muted)]">
        <RefreshCw className="w-6 h-6 animate-spin text-emerald-400" />
        <p className="text-sm">Preparing your onboarding workspace…</p>
      </div>
    );
  }

  const progressPercent = Math.round((currentStep / STEPS.length) * 100);

  return (
    <div className="w-full max-w-5xl mx-auto space-y-8 pb-16">
      {/* Top Header & Navigation Breadcrumb */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-[var(--color-rule)] pb-5">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium mb-2">
            <Sparkles className="w-3.5 h-3.5" />
            <span>Profile Activation & Onboarding</span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-[var(--color-ink)]">
            Set Up Your CareerOS Profile
          </h1>
          <p className="text-sm text-[var(--color-muted)] mt-1">
            Ground your skills in verifiable project evidence and activate high-confidence opportunity matching.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => handleSaveCurrentStep(currentStep)}
            disabled={saving}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--color-rule)] bg-[var(--color-paper-2)] text-[var(--color-ink-2)] hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-3)] text-xs font-medium transition-colors"
            title="Save current progress"
          >
            <Save className="w-3.5 h-3.5" />
            <span>{saving ? 'Saving…' : 'Save Progress'}</span>
          </button>
          <button
            onClick={onExit}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--color-rule)] bg-[var(--color-paper-2)] text-[var(--color-ink-2)] hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-3)] text-xs font-medium transition-colors"
            title="Save & return to dashboard"
          >
            <span>Save & Exit</span>
          </button>
        </div>
      </div>

      {/* Progress Bar & Steps Tabs */}
      <div className="space-y-4">
        <div className="flex items-center justify-between text-xs text-[var(--color-muted)] font-medium">
          <span>Step {currentStep} of {STEPS.length}: {STEPS[currentStep - 1].name}</span>
          <span>{progressPercent}% Complete</span>
        </div>
        <div className="w-full h-1.5 bg-[var(--color-paper-3)] rounded-full overflow-hidden">
          <div
            className="h-full bg-[var(--color-accent)] transition-colors duration-300 rounded-full"
            style={{ width: `${progressPercent}%` }}
          />
        </div>

        {/* Step Indicator Badges */}
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2 pt-2">
          {STEPS.map((step) => {
            const Icon = step.icon;
            const isCompleted = step.id < currentStep || (step.id === 6 && completeness?.is_onboarded);
            const isCurrent = step.id === currentStep;

            return (
              <button
                key={step.id}
                onClick={() => handleSaveCurrentStep(step.id)}
                className={`flex flex-col items-start p-2.5 rounded-xl border text-left transition-colors ${
                  isCurrent
                    ? 'border-emerald-500/60 bg-emerald-500/10 text-[var(--color-ink)] shadow-sm'
                    : isCompleted
                    ? 'border-[var(--color-rule)] bg-[var(--color-paper-2)] text-[var(--color-ink-2)] hover:border-[var(--color-rule)]'
                    : 'border-slate-900 bg-[var(--color-paper-2)] text-[var(--color-muted)] hover:border-[var(--color-rule)]'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <div
                    className={`p-1 rounded-md ${
                      isCurrent
                        ? 'bg-emerald-500 text-slate-950 font-bold'
                        : isCompleted
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : 'bg-[var(--color-paper-3)] text-[var(--color-muted)]'
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                  </div>
                  <span className="text-xs font-semibold">
                    {step.id}. {step.name}
                  </span>
                </div>
                <span className="text-[10px] text-[var(--color-muted)] line-clamp-1">
                  {step.desc}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Notifications / Alerts */}
      {saveMessage && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          <span>{saveMessage}</span>
        </div>
      )}
      {errorMessage && (
        <div className="flex items-center gap-2 p-3 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs animate-in fade-in">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      {/* MAIN STEP CONTENT */}
      <div className="bg-[var(--color-paper-2)] border border-[var(--color-rule)] rounded-xl p-6 sm:p-8 backdrop-blur-sm">
        {/* STEP 1: CAREER GOALS */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-[var(--color-ink)]">Target Roles & Career Goals</h2>
              <p className="text-xs text-[var(--color-muted)] mt-0.5">
                Tell CareerOS what positions you are targeting so the discovery engine can calibrate search keywords and location matching.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  Full Name <span className="text-emerald-400">*</span>
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Alex River"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  Email Address <span className="text-emerald-400">*</span>
                </label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="e.g. alex@example.com"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  Phone Number <span className="text-[var(--color-muted)] font-normal">(Optional)</span>
                </label>
                <input
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="e.g. +1 (555) 019-2834"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  Current Location <span className="text-[var(--color-muted)] font-normal">(City, Country)</span>
                </label>
                <input
                  type="text"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  placeholder="e.g. San Francisco, CA"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            <div className="space-y-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  Target Roles <span className="text-emerald-400">*</span> <span className="text-[var(--color-muted)] font-normal">(Press Enter to add role)</span>
                </label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {targetRoles.map((role, idx) => (
                    <span
                      key={idx}
                      className="inline-flex items-center gap-1 px-2.5 py-1 rounded-md bg-[var(--color-paper-3)] border border-[var(--color-rule)] text-slate-200 text-xs"
                    >
                      <span>{role}</span>
                      <button
                        type="button"
                        onClick={() => setTargetRoles(targetRoles.filter((_, i) => i !== idx))}
                        className="text-[var(--color-muted)] hover:text-rose-400"
                      >
                        ×
                      </button>
                    </span>
                  ))}
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={targetRoleInput}
                    onChange={(e) => setTargetRoleInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (targetRoleInput.trim() && !targetRoles.includes(targetRoleInput.trim())) {
                          setTargetRoles([...targetRoles, targetRoleInput.trim()]);
                          setTargetRoleInput('');
                        }
                      }
                    }}
                    placeholder="e.g. Frontend Engineer, Backend Developer, AI Engineer"
                    className="flex-1 px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      if (targetRoleInput.trim() && !targetRoles.includes(targetRoleInput.trim())) {
                        setTargetRoles([...targetRoles, targetRoleInput.trim()]);
                        setTargetRoleInput('');
                      }
                    }}
                    className="px-3 py-2 rounded-lg bg-[var(--color-paper-3)] hover:bg-[var(--color-hover)] text-slate-200 text-xs font-medium"
                  >
                    Add
                  </button>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                    Workplace Preference
                  </label>
                  <select
                    value={workplacePreference}
                    onChange={(e) => setWorkplacePreference(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                  >
                    <option value="any">Any (Remote, Hybrid, or On-site)</option>
                    <option value="remote">Remote Only</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="onsite">On-site</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                    Work Authorization
                  </label>
                  <select
                    value={workAuthorization}
                    onChange={(e) => setWorkAuthorization(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                  >
                    <option value="US Citizen">US Citizen</option>
                    <option value="Permanent Resident">Permanent Resident (Green Card)</option>
                    <option value="F-1 OPT/CPT">F-1 Visa (OPT / CPT Eligible)</option>
                    <option value="Requires Sponsorship">Requires Visa Sponsorship</option>
                    <option value="Authorized to work">Authorized to work</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="p-3.5 rounded-xl bg-[var(--color-paper-2)]/80 border border-[var(--color-rule)] flex items-start gap-2.5 text-xs text-[var(--color-muted)]">
              <Info className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>
                <strong>Why this matters:</strong> Target roles directly guide the hybrid search vector space, ensuring newly discovered opportunities surface roles aligned with your preferred specialization.
              </span>
            </div>
          </div>
        )}

        {/* STEP 2: EDUCATION & EXPERIENCE */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-[var(--color-ink)]">Education & Background</h2>
              <p className="text-xs text-[var(--color-muted)] mt-0.5">
                Education criteria verify graduation deadlines and degree restrictions for university programs (10% of match score).
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  Degree / Field of Study <span className="text-emerald-400">*</span>
                </label>
                <input
                  type="text"
                  value={degree}
                  onChange={(e) => setDegree(e.target.value)}
                  placeholder="e.g. B.S. in Computer Science"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  College / University <span className="text-emerald-400">*</span>
                </label>
                <input
                  type="text"
                  value={college}
                  onChange={(e) => setCollege(e.target.value)}
                  placeholder="e.g. Stanford University"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  Expected Graduation Year <span className="text-emerald-400">*</span>
                </label>
                <input
                  type="number"
                  value={gradYear}
                  onChange={(e) => setGradYear(e.target.value ? Number(e.target.value) : '')}
                  placeholder="e.g. 2026"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">
                  CGPA / GPA <span className="text-[var(--color-muted)] font-normal">(Optional)</span>
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={cgpa}
                  onChange={(e) => setCgpa(e.target.value ? Number(e.target.value) : '')}
                  placeholder="e.g. 3.85"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                />
              </div>
            </div>

            {/* Optional Past Experience */}
            <div className="pt-3 border-t border-[var(--color-rule)]">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-[var(--color-ink)]">Prior Internship or Work Experience</h3>
                  <p className="text-xs text-[var(--color-muted)]">
                    Completely optional. You will never be penalized for having no prior corporate experience.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setHasExperience(!hasExperience)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                    hasExperience
                      ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                      : 'bg-[var(--color-paper-2)] border-[var(--color-rule)] text-[var(--color-muted)] hover:text-[var(--color-ink)]'
                  }`}
                >
                  {hasExperience ? '✓ Experience Added' : '+ Add Experience'}
                </button>
              </div>

              {hasExperience && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 p-4 rounded-xl bg-[var(--color-paper-2)] border border-[var(--color-rule)] animate-in fade-in">
                  <div>
                    <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">Role Title</label>
                    <input
                      type="text"
                      value={expTitle}
                      onChange={(e) => setExpTitle(e.target.value)}
                      placeholder="e.g. Software Engineering Intern"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">Company / Org</label>
                    <input
                      type="text"
                      value={expCompany}
                      onChange={(e) => setExpCompany(e.target.value)}
                      placeholder="e.g. Stripe Labs"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1.5">Key Contributions</label>
                    <textarea
                      rows={2}
                      value={expDescription}
                      onChange={(e) => setExpDescription(e.target.value)}
                      placeholder="Built microservices, integrated payment endpoints, and improved latency."
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* STEP 3: TECHNICAL SKILLS */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-[var(--color-ink)]">Technical Skills Management</h2>
              <p className="text-xs text-[var(--color-muted)] mt-0.5">
                Mandatory skills represent 40% of the match weight. Add your core languages and frameworks to enable automated qualification evaluation.
              </p>
            </div>

            {/* Add Skill Form */}
            <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-[var(--color-rule)] space-y-3">
              <h3 className="text-xs font-semibold text-[var(--color-ink-2)] ">Add Technical Skill</h3>
              <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                <div className="sm:col-span-2">
                  <input
                    type="text"
                    value={newSkillName}
                    onChange={(e) => setNewSkillName(e.target.value)}
                    placeholder="Skill name (e.g. Python, React, PostgreSQL)"
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <select
                    value={newSkillCategory}
                    onChange={(e) => setNewSkillCategory(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                  >
                    <option value="Languages">Languages</option>
                    <option value="Frameworks">Frameworks</option>
                    <option value="Databases">Databases</option>
                    <option value="Cloud & DevOps">Cloud & DevOps</option>
                    <option value="Architecture & APIs">Architecture & APIs</option>
                    <option value="AI & Machine Learning">AI & Machine Learning</option>
                  </select>
                </div>
                <div>
                  <button
                    type="button"
                    onClick={handleAddSkill}
                    disabled={!newSkillName.trim()}
                    className="w-full h-full px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-[var(--color-ink)] text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    <span>Add Skill</span>
                  </button>
                </div>
              </div>

              {/* Taxonomy Suggestions */}
              {taxonomy && (
                <div className="pt-2">
                  <span className="text-[11px] text-[var(--color-muted)] block mb-1.5">Common Canonical Skills:</span>
                  <div className="flex flex-wrap gap-1.5">
                    {['Python', 'TypeScript', 'React', 'FastAPI', 'PostgreSQL', 'Docker', 'AWS'].map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => setNewSkillName(s)}
                        className="px-2 py-0.5 rounded bg-[var(--color-paper-2)] hover:bg-[var(--color-paper-3)] border border-[var(--color-rule)] text-[11px] text-[var(--color-ink-2)] transition-colors"
                      >
                        + {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Added Skills List */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-[var(--color-ink-2)] ">
                  Added Skills ({profile?.skills?.length || 0})
                </span>
                <span className="text-xs text-[var(--color-muted)]">
                  {completeness?.skills_summary.verified || 0} verified by project code
                </span>
              </div>

              {(!profile?.skills || profile.skills.length === 0) ? (
                <div className="text-center py-8 border border-dashed border-[var(--color-rule)] rounded-xl text-[var(--color-muted)] text-xs">
                  No skills added yet. Add at least 3 core technical skills above.
                </div>
              ) : (
                <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                  {profile.skills.map((s, idx) => {
                    const verifiedItem = completeness?.skills_summary.items.find(
                      (item) => item.name.toLowerCase() === s.name.toLowerCase()
                    );
                    const isVerified = verifiedItem?.status === 'verified';

                    return (
                      <div
                        key={idx}
                        className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] hover:border-[var(--color-rule)] transition-colors"
                      >
                        <div className="min-w-0 pr-2">
                          <div className="flex items-center gap-1.5">
                            <span className="text-xs font-medium text-[var(--color-ink)] truncate">{s.name}</span>
                            {isVerified ? (
                              <span
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 text-[9px] font-semibold border border-emerald-500/20"
                                title="Verified by project code or external repos"
                              >
                                <Check className="w-2.5 h-2.5" /> Verified
                              </span>
                            ) : (
                              <span
                                className="inline-flex items-center gap-0.5 px-1.5 py-0.2 rounded bg-amber-500/10 text-amber-400 text-[9px] font-semibold border border-amber-500/20"
                                title="Self-reported claim: Add a project using this skill to verify evidence"
                              >
                                Self-reported
                              </span>
                            )}
                          </div>
                          <span className="text-[10px] text-[var(--color-muted)] block truncate">
                            {s.category || 'General'}
                          </span>
                        </div>
                        <button
                          type="button"
                          onClick={() => handleDeleteSkill(s.name)}
                          className="p-1 rounded text-[var(--color-muted)] hover:text-rose-400 transition-colors"
                          title="Remove skill"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="p-3.5 rounded-xl bg-[var(--color-paper-2)]/80 border border-[var(--color-rule)] flex items-start gap-2.5 text-xs text-[var(--color-muted)]">
              <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>
                <strong>Verification Policy:</strong> Self-reported skills are evaluated as preliminary signals. Linking skills to working projects in Step 4 verifies them as concrete evidence for high-confidence matching.
              </span>
            </div>
          </div>
        )}

        {/* STEP 4: PROJECTS */}
        {currentStep === 4 && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-semibold text-[var(--color-ink)]">Project Portfolio Evidence</h2>
                <p className="text-xs text-[var(--color-muted)] mt-0.5">
                  Projects account for 15% of your match score and independently ground your technical skills in demonstrable code.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowAddProject(!showAddProject)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-[var(--color-ink)] text-xs font-medium transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Project</span>
              </button>
            </div>

            {/* Add Project Form Drawer */}
            {showAddProject && (
              <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-[var(--color-rule)] space-y-3 animate-in fade-in">
                <h3 className="text-xs font-semibold text-[var(--color-ink)] ">New Project Entry</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1">Project Title *</label>
                    <input
                      type="text"
                      value={projTitle}
                      onChange={(e) => setProjTitle(e.target.value)}
                      placeholder="e.g. Distributed Task Queue"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1">GitHub / Live URL</label>
                    <input
                      type="url"
                      value={projUrl}
                      onChange={(e) => setProjUrl(e.target.value)}
                      placeholder="https://github.com/username/project"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1">Technologies Used (Comma-separated)</label>
                    <input
                      type="text"
                      value={projTechInput}
                      onChange={(e) => {
                        setProjTechInput(e.target.value);
                        setProjTechs(e.target.value.split(',').map((t) => t.trim()).filter(Boolean));
                      }}
                      placeholder="e.g. Go, Redis, Docker, PostgreSQL"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                  <div className="md:col-span-2">
                    <label className="block text-xs font-medium text-[var(--color-ink-2)] mb-1">Description & Architecture Highlights</label>
                    <textarea
                      rows={2}
                      value={projDesc}
                      onChange={(e) => setProjDesc(e.target.value)}
                      placeholder="High-throughput worker pool handling concurrent tasks with Redis pub/sub..."
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-slate-100 text-sm focus:outline-none focus:border-emerald-500"
                    />
                  </div>
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setShowAddProject(false)}
                    className="px-3 py-1.5 rounded-lg bg-[var(--color-paper-2)] text-[var(--color-muted)] hover:text-[var(--color-ink)] text-xs font-medium"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    onClick={handleCreateProject}
                    disabled={!projTitle.trim()}
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-[var(--color-ink)] text-xs font-semibold"
                  >
                    Save Project
                  </button>
                </div>
              </div>
            )}

            {/* Preserved Project Cards */}
            <div className="space-y-3">
              {(!profile?.projects || profile.projects.length === 0) ? (
                <div className="text-center py-8 border border-dashed border-[var(--color-rule)] rounded-xl text-[var(--color-muted)] text-xs">
                  No projects added yet. Click &quot;Add Project&quot; to showcase your code evidence.
                </div>
              ) : (
                profile.projects.map((proj, idx) => (
                  <div
                    key={idx}
                    className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-[var(--color-rule)] hover:border-[var(--color-rule)] transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2">
                          <h4 className="text-sm font-semibold text-[var(--color-ink)]">{proj.title}</h4>
                          {proj.url && (
                            <a
                              href={proj.url}
                              target="_blank"
                              rel="noreferrer"
                              className="text-[var(--color-muted)] hover:text-emerald-400 inline-flex items-center gap-0.5 text-xs"
                            >
                              <ExternalLink className="w-3 h-3" />
                            </a>
                          )}
                        </div>
                        <p className="text-xs text-[var(--color-muted)] mt-1 line-clamp-2">{proj.description}</p>
                        <div className="flex flex-wrap gap-1.5 mt-2.5">
                          {(proj.tech_stack || []).map((t, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 rounded bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-[10px] font-medium text-emerald-300"
                            >
                              {t}
                            </span>
                          ))}
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={() => handleDeleteProject(idx)}
                        className="p-1 rounded text-[var(--color-muted)] hover:text-rose-400 transition-colors shrink-0"
                        title="Delete project"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* STEP 5: RESUME INTEGRATION */}
        {currentStep === 5 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-[var(--color-ink)]">Resume Document & ATS Master</h2>
              <p className="text-xs text-[var(--color-muted)] mt-0.5">
                Upload your resume (PDF, TXT, MD) to extract structured details and establish a Master Resume document for 1-click tailored ATS exports.
              </p>
            </div>

            {/* Master Resume Status */}
            <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-[var(--color-rule)] flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2.5 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <FileText className="w-5 h-5" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-[var(--color-ink)]">
                    {completeness?.has_master_resume ? 'Master Resume Active' : 'Master Resume Pending'}
                  </h4>
                  <p className="text-xs text-[var(--color-muted)]">
                    {completeness?.has_master_resume
                      ? `Version ${completeness.master_resume_version} active and available for ATS tailoring.`
                      : 'Upload a resume file to parse and initialize your master ATS document.'}
                  </p>
                </div>
              </div>
              <label className="cursor-pointer inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[var(--color-paper-3)] hover:bg-[var(--color-hover)] text-slate-200 text-xs font-medium transition-colors">
                <UploadCloud className="w-3.5 h-3.5" />
                <span>{isParsingResume ? 'Parsing…' : 'Upload Resume'}</span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.txt,.md"
                  onChange={handleResumeUpload}
                  className="hidden"
                />
              </label>
            </div>

            {/* Parsed Resume Review Modal / Preview */}
            {parsedDraft && (
              <div className="p-5 rounded-xl bg-[var(--color-paper-2)] border border-emerald-500/30 space-y-4 animate-in fade-in">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Sparkles className="w-4 h-4 text-emerald-400" />
                    <h4 className="text-sm font-semibold text-[var(--color-ink)]">Review Extracted Information</h4>
                  </div>
                  <span className="text-[11px] text-[var(--color-muted)]">
                    Select which items to merge into your candidate profile
                  </span>
                </div>

                {/* Candidate details preview */}
                <div className="p-3 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="apply-details"
                      checked={applyParsedDetails}
                      onChange={(e) => setApplyParsedDetails(e.target.checked)}
                      className="rounded bg-[var(--color-paper-2)] border-[var(--color-rule)] text-emerald-500 focus:ring-0"
                    />
                    <label htmlFor="apply-details" className="text-xs font-medium text-slate-200 cursor-pointer">
                      Apply Extracted Profile Info ({parsedDraft.candidate_draft.name || 'Identified'}, {parsedDraft.candidate_draft.college || 'College'})
                    </label>
                  </div>
                </div>

                {/* Skills Checkboxes */}
                <div>
                  <span className="text-xs font-semibold text-[var(--color-ink-2)] block mb-2">
                    Detected Skills ({parsedDraft.detected_skills?.length || 0})
                  </span>
                  <div className="flex flex-wrap gap-2">
                    {(parsedDraft.detected_skills || []).map((s: any, idx: number) => {
                      const isChecked = selectedParsedSkills.includes(s.name);
                      return (
                        <button
                          key={idx}
                          type="button"
                          onClick={() => {
                            if (isChecked) {
                              setSelectedParsedSkills(selectedParsedSkills.filter((name) => name !== s.name));
                            } else {
                              setSelectedParsedSkills([...selectedParsedSkills, s.name]);
                            }
                          }}
                          className={`px-2.5 py-1 rounded-md text-xs border transition-colors ${
                            isChecked
                              ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-300'
                              : 'bg-[var(--color-paper-2)] border-[var(--color-rule)] text-[var(--color-muted)]'
                          }`}
                        >
                          {isChecked ? '✓ ' : '+ '} {s.name}
                        </button>
                      );
                    })}
                  </div>
                </div>

                <div className="flex justify-end gap-2 pt-2 border-t border-[var(--color-rule)]">
                  <button
                    type="button"
                    onClick={() => setParsedDraft(null)}
                    className="px-3 py-1.5 rounded-lg bg-[var(--color-paper-2)] text-[var(--color-muted)] hover:text-[var(--color-ink)] text-xs font-medium"
                  >
                    Discard Preview
                  </button>
                  <button
                    type="button"
                    onClick={handleApproveResumeData}
                    className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-[var(--color-ink)] text-xs font-semibold"
                  >
                    Approve and merge
                  </button>
                </div>
              </div>
            )}

            <div className="p-3.5 rounded-xl bg-[var(--color-paper-2)]/80 border border-[var(--color-rule)] flex items-start gap-2.5 text-xs text-[var(--color-muted)]">
              <Info className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
              <span>
                <strong>Protection Guarantee:</strong> Uploading a resume never silently overwrites your manually entered information. You retain complete selective approval over extracted skills and project details.
              </span>
            </div>
          </div>
        )}

        {/* STEP 6: READINESS & LAUNCH */}
        {currentStep === 6 && (
          <div className="space-y-6">
            <div>
              <h2 className="text-lg font-semibold text-[var(--color-ink)]">Profile Readiness & Verification Review</h2>
              <p className="text-xs text-[var(--color-muted)] mt-0.5">
                Review your evidence density score, confirmed evidence items, and recommended improvements before activating personalized discovery.
              </p>
            </div>

            {/* Score Ring Banner */}
            <div className="rounded-xl border border-[var(--color-rule)] bg-[var(--color-paper-2)] p-4 flex flex-col sm:flex-row items-center justify-between gap-4">
              <div className="flex items-center gap-5">
                <div className="relative w-20 h-20 flex items-center justify-center rounded-full bg-[var(--color-paper-2)] border-4 border-emerald-500 shadow-lg shadow-emerald-500/10">
                  <span className="text-2xl font-bold text-[var(--color-ink)]">
                    {completeness?.completeness_score || 0}%
                  </span>
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-base font-bold text-[var(--color-ink)]">
                      {completeness?.readiness_stage === 'high_confidence_readiness'
                        ? 'High-Confidence Match Ready'
                        : completeness?.readiness_stage === 'core_evidence_ready'
                        ? 'Core Evidence Established'
                        : 'Getting Started'}
                    </h3>
                    <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-semibold ">
                      {completeness?.readiness_stage}
                    </span>
                  </div>
                  <p className="text-xs text-[var(--color-muted)] max-w-md">
                    {completeness?.disclaimer}
                  </p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleCompleteAndActivate}
                disabled={saving}
                className="w-full sm:w-auto min-h-[40px] inline-flex items-center justify-center gap-2 rounded-md border border-[var(--color-accent)] bg-[var(--color-accent)] px-4 text-[14px] font-semibold text-[var(--color-accent-ink)] transition-colors hover:bg-[var(--color-accent-hover)] focus-visible:outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--color-focus)]"
              >
                <Sparkles className="w-4 h-4" />
                <span>{saving ? 'Activating…' : 'Activate Profile & Discover Matches'}</span>
              </button>
            </div>

            {/* Verified Evidence vs Unverified vs Missing */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Confirmed Evidence */}
              <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-[var(--color-rule)] space-y-2.5">
                <h4 className="text-xs font-semibold text-emerald-400  flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Confirmed Evidence ({completeness?.verified_evidence.length || 0})</span>
                </h4>
                <ul className="space-y-1.5">
                  {(completeness?.verified_evidence || []).map((ev, i) => (
                    <li key={i} className="text-xs text-[var(--color-ink-2)] flex items-start gap-2">
                      <span className="text-emerald-400 font-bold">✓</span>
                      <span>{ev}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Actionable Recommendations */}
              <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-[var(--color-rule)] space-y-2.5">
                <h4 className="text-xs font-semibold text-[var(--color-ink-2)]  flex items-center gap-1.5">
                  <Sparkles className="w-3.5 h-3.5 text-amber-400" />
                  <span>Recommended Next Actions</span>
                </h4>
                {(!completeness?.actionable_recommendations || completeness.actionable_recommendations.length === 0) ? (
                  <p className="text-xs text-[var(--color-muted)]">Your profile evidence base is complete!</p>
                ) : (
                  <ul className="space-y-2">
                    {completeness.actionable_recommendations.slice(0, 3).map((rec, i) => (
                      <li key={i} className="p-2.5 rounded-lg bg-[var(--color-paper-2)] border border-[var(--color-rule)] text-xs">
                        <span className="font-semibold text-[var(--color-ink)] block mb-0.5">{rec.title}</span>
                        <span className="text-[var(--color-muted)] text-[11px] block">{rec.description}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* FOOTER NAVIGATION CONTROLS */}
      <div className="flex items-center justify-between pt-2">
        <button
          type="button"
          onClick={() => handleSaveCurrentStep(currentStep - 1)}
          disabled={currentStep === 1 || saving}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-xl border border-[var(--color-rule)] bg-[var(--color-paper-2)] text-[var(--color-ink-2)] hover:text-[var(--color-ink)] disabled:opacity-40 text-xs font-medium transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Previous Step</span>
        </button>

        <div className="flex items-center gap-3">
          {currentStep < 6 ? (
            <button
              type="button"
              onClick={() => handleSaveCurrentStep(currentStep + 1)}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-5 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-[var(--color-ink)] text-xs font-semibold transition-colors"
            >
              <span>{saving ? 'Saving…' : 'Save & Continue'}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          ) : (
            <button
              type="button"
              onClick={handleCompleteAndActivate}
              disabled={saving}
              className="inline-flex items-center gap-1.5 px-6 py-2 rounded-xl bg-emerald-500 hover:bg-emerald-400 text-slate-950 text-xs font-bold transition-colors"
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>{saving ? 'Activating…' : 'Complete & Discover Matches'}</span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
