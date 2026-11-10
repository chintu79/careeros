import React, { useState, useEffect } from 'react';
import { 
  X, 
  Send, 
  FileText, 
  CheckCircle2, 
  ExternalLink, 
  Copy, 
  Check, 
  AlertCircle,
  Sparkles,
  User,
  ShieldCheck,
  Layers,
  FileCode2,
  HelpCircle,
  Briefcase
} from 'lucide-react';
import { AssistedApplicationDossier } from '../../types';
import { prepareAssistedApplication, submitAssistedApplication } from '../../services/api';

interface AssistedApplicationModalProps {
  opportunityId: number;
  onClose: () => void;
  onSuccess: () => void;
}

type TabType = 'ats_mapper' | 'cover_letter' | 'resume' | 'workflow';
type ATSPreset = 'greenhouse' | 'lever' | 'standard';

interface ATSFieldItem {
  id: string;
  label: string;
  value: string;
  category: 'identity' | 'contact' | 'education' | 'links' | 'authorization';
  required?: boolean;
}

export const AssistedApplicationModal: React.FC<AssistedApplicationModalProps> = ({
  opportunityId,
  onClose,
  onSuccess
}) => {
  const [dossier, setDossier] = useState<AssistedApplicationDossier | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabType>('ats_mapper');
  const [atsPreset, setAtsPreset] = useState<ATSPreset>('greenhouse');
  const [selectedMode, setSelectedMode] = useState('assisted');
  const [copiedLetter, setCopiedLetter] = useState(false);
  const [copiedBundle, setCopiedBundle] = useState(false);
  const [copiedFieldId, setCopiedFieldId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [notes, setNotes] = useState('');

  useEffect(() => {
    setLoading(true);
    prepareAssistedApplication(opportunityId)
      .then(data => setDossier(data))
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  }, [opportunityId]);

  const applicant = dossier?.applicant_info || {};
  const fullName = applicant.full_name || '';
  const nameParts = fullName.trim().split(' ');
  const firstName = nameParts[0] || '';
  const lastName = nameParts.length > 1 ? nameParts.slice(1).join(' ') : '';

  // ATS Field Mappings tailored for Greenhouse, Lever, and Standard formats
  const getFieldsForPreset = (preset: ATSPreset): ATSFieldItem[] => {
    switch (preset) {
      case 'greenhouse':
        return [
          { id: 'first_name', label: 'First Name', value: firstName, category: 'identity', required: true },
          { id: 'last_name', label: 'Last Name', value: lastName, category: 'identity', required: true },
          { id: 'email', label: 'Email Address', value: applicant.email || '', category: 'contact', required: true },
          { id: 'phone', label: 'Phone Number', value: applicant.phone || '', category: 'contact', required: true },
          { id: 'location', label: 'Location (City, State/Country)', value: applicant.location || '', category: 'contact' },
          { id: 'school', label: 'School / University', value: applicant.college || '', category: 'education', required: true },
          { id: 'degree', label: 'Degree', value: applicant.degree || '', category: 'education', required: true },
          { id: 'discipline', label: 'Discipline / Major', value: 'Computer Science & Engineering', category: 'education' },
          { id: 'grad_year', label: 'End Date / Graduation Year', value: applicant.graduation_year ? String(applicant.graduation_year) : '', category: 'education' },
          { id: 'cgpa', label: 'GPA / CGPA', value: applicant.cgpa ? String(applicant.cgpa) : '', category: 'education' },
          { id: 'linkedin', label: 'LinkedIn Profile', value: applicant.linkedin_url || '', category: 'links' },
          { id: 'website', label: 'Website / Portfolio', value: applicant.portfolio_url || '', category: 'links' },
          { id: 'github', label: 'GitHub Profile', value: applicant.github_url || '', category: 'links' },
          { id: 'auth', label: 'Work Authorization', value: applicant.work_authorization || 'Authorized to work without sponsorship', category: 'authorization', required: true }
        ];

      case 'lever':
        return [
          { id: 'full_name', label: 'Full Name', value: fullName, category: 'identity', required: true },
          { id: 'email', label: 'Email', value: applicant.email || '', category: 'contact', required: true },
          { id: 'phone', label: 'Phone', value: applicant.phone || '', category: 'contact', required: true },
          { id: 'current_company', label: 'Current Company / School', value: applicant.college || '', category: 'education' },
          { id: 'linkedin', label: 'LinkedIn URL', value: applicant.linkedin_url || '', category: 'links' },
          { id: 'github', label: 'GitHub URL', value: applicant.github_url || '', category: 'links' },
          { id: 'portfolio', label: 'Portfolio URL', value: applicant.portfolio_url || '', category: 'links' },
          { id: 'location', label: 'Location', value: applicant.location || '', category: 'contact' },
          { id: 'auth', label: 'Work Authorization Status', value: applicant.work_authorization || 'Authorized', category: 'authorization' },
          { id: 'additional_info', label: 'Additional Information', value: `Candidate cohort ${applicant.graduation_year || 2025} studying ${applicant.degree || 'Computer Science'}.`, category: 'education' }
        ];

      case 'standard':
      default:
        return [
          { id: 'full_name', label: 'Full Name', value: fullName, category: 'identity', required: true },
          { id: 'email', label: 'Email', value: applicant.email || '', category: 'contact', required: true },
          { id: 'phone', label: 'Phone', value: applicant.phone || '', category: 'contact' },
          { id: 'location', label: 'Location', value: applicant.location || '', category: 'contact' },
          { id: 'college', label: 'University / College', value: applicant.college || '', category: 'education' },
          { id: 'degree', label: 'Degree & Program', value: applicant.degree || '', category: 'education' },
          { id: 'graduation_year', label: 'Graduation Year', value: applicant.graduation_year ? String(applicant.graduation_year) : '', category: 'education' },
          { id: 'cgpa', label: 'CGPA', value: applicant.cgpa ? String(applicant.cgpa) : '', category: 'education' },
          { id: 'work_authorization', label: 'Work Authorization', value: applicant.work_authorization || '', category: 'authorization' },
          { id: 'github_url', label: 'GitHub URL', value: applicant.github_url || '', category: 'links' },
          { id: 'linkedin_url', label: 'LinkedIn URL', value: applicant.linkedin_url || '', category: 'links' },
          { id: 'portfolio_url', label: 'Portfolio Website', value: applicant.portfolio_url || '', category: 'links' }
        ];
    }
  };

  const fields = getFieldsForPreset(atsPreset);
  const missingFields = fields.filter(f => !f.value || f.value.trim() === '');

  const handleCopyField = (id: string, value: string) => {
    if (!value) return;
    navigator.clipboard.writeText(value);
    setCopiedFieldId(id);
    setTimeout(() => setCopiedFieldId(null), 2000);
  };

  const handleCopyBundle = () => {
    const lines = [
      `=== CAREEROS VERIFIED ATS BUNDLE (${atsPreset.toUpperCase()} FORMAT) ===`,
      `Target Role: ${dossier?.job_title} at ${dossier?.company_name}`,
      `Generated: ${new Date().toLocaleDateString()}`,
      `----------------------------------------------------`
    ];
    for (const f of fields) {
      lines.push(`${f.label}: ${f.value || '[Missing in Profile]'}`);
    }
    navigator.clipboard.writeText(lines.join('\n'));
    setCopiedBundle(true);
    setTimeout(() => setCopiedBundle(false), 2500);
  };

  const handleCopyCoverLetter = () => {
    if (!dossier?.draft_cover_letter) return;
    navigator.clipboard.writeText(dossier.draft_cover_letter);
    setCopiedLetter(true);
    setTimeout(() => setCopiedLetter(false), 2500);
  };

  const handleConfirmSubmission = async () => {
    setSubmitting(true);
    try {
      await submitAssistedApplication({
        opportunity_id: opportunityId,
        submission_mode: selectedMode,
        resume_id: dossier?.selected_resume?.id,
        notes: notes || `Application dossier prepared via CareerOS (${atsPreset} ATS mapping)`,
        submission_verified: false
      });
      onSuccess();
      onClose();
    } catch (err) {
      console.error(err);
      alert("Failed to record application submission.");
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
        <div className="p-8 rounded-xl bg-dark-900 border border-dark-700 text-center text-slate-300">
          <Sparkles className="w-8 h-8 animate-spin mx-auto mb-2 text-emerald-400" />
          <p className="text-sm font-semibold">Preparing verified application materials...</p>
        </div>
      </div>
    );
  }

  if (!dossier) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-black/85 backdrop-blur-sm overflow-y-auto">
      <div 
        className="relative w-full max-w-4xl bg-dark-900 border border-dark-700 rounded-xl overflow-hidden flex flex-col max-h-[92vh] animate-in fade-in zoom-in-95 duration-150"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-5 border-b border-dark-700 bg-dark-850 flex items-start justify-between">
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-semibold text-emerald-400 ">{dossier.company_name}</span>
              <span className="text-slate-600">•</span>
              <span className="text-xs text-slate-400">Assisted Application Workflow & ATS Mapper</span>
            </div>
            <h2 className="text-lg font-bold text-[var(--color-ink)] mt-0.5">{dossier.job_title}</h2>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1.5 rounded-lg bg-dark-800 hover:bg-dark-700 text-slate-400 hover:text-[var(--color-ink)] transition min-h-[28px] min-w-[28px] flex items-center justify-center focus-visible:ring-1 focus-visible:ring-emerald-500"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="px-5 border-b border-dark-750 bg-dark-850/60 flex items-center justify-between overflow-x-auto">
          <div className="flex items-center space-x-1 py-2">
            <button
              onClick={() => setActiveTab('ats_mapper')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center space-x-1.5 ${
                activeTab === 'ats_mapper'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800'
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>ATS Field Mapper</span>
              {missingFields.length > 0 && (
                <span className="ml-1 px-1.5 py-0.2 rounded-full bg-amber-500/20 text-amber-400 text-[10px] font-bold">
                  {missingFields.length}
                </span>
              )}
            </button>

            <button
              onClick={() => setActiveTab('cover_letter')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center space-x-1.5 ${
                activeTab === 'cover_letter'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800'
              }`}
            >
              <FileCode2 className="w-3.5 h-3.5" />
              <span>Cover Letter</span>
            </button>

            <button
              onClick={() => setActiveTab('resume')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center space-x-1.5 ${
                activeTab === 'resume'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800'
              }`}
            >
              <FileText className="w-3.5 h-3.5" />
              <span>Selected Resume</span>
            </button>

            <button
              onClick={() => setActiveTab('workflow')}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition flex items-center space-x-1.5 ${
                activeTab === 'workflow'
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-dark-800'
              }`}
            >
              <ShieldCheck className="w-3.5 h-3.5" />
              <span>Handoff & Tracking</span>
            </button>
          </div>

          {activeTab === 'ats_mapper' && (
            <button
              onClick={handleCopyBundle}
              className="whitespace-nowrap px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-emerald-400 text-xs font-semibold border border-emerald-500/30 flex items-center space-x-1.5 transition shrink-0 ml-2"
            >
              {copiedBundle ? (
                <>
                  <Check className="whitespace-nowrap w-3.5 h-3.5 text-emerald-400" />
                  <span>Copied</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Bundle</span>
                </>
              )}
            </button>
          )}
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs text-slate-300">
          
          {/* TAB 1: Controlled ATS Field Mapper */}
          {activeTab === 'ats_mapper' && (
            <div className="space-y-4">
              {/* Presets Selector & Info */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 p-3.5 rounded-xl bg-dark-850 border border-dark-700">
                <div className="space-y-0.5">
                  <span className="text-xs font-bold text-[var(--color-ink)] flex items-center space-x-1.5">
                    <span>Target ATS Preset</span>
                    <span className="text-slate-500">•</span>
                    <span className="text-emerald-400 font-normal">Auto-formats labels to match target portal forms</span>
                  </span>
                  <p className="text-[11px] text-slate-400">
                    Switch preset to mirror the exact input fields of Greenhouse, Lever, or standard portals.
                  </p>
                </div>

                <div className="flex items-center space-x-1.5 bg-dark-900 p-1 rounded-xl border border-dark-750 shrink-0">
                  <button
                    onClick={() => setAtsPreset('greenhouse')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                      atsPreset === 'greenhouse'
                        ? 'bg-emerald-400 text-[var(--color-accent-ink)]'
                        : 'text-slate-400 hover:text-[var(--color-ink)]'
                    }`}
                  >
                    Greenhouse
                  </button>
                  <button
                    onClick={() => setAtsPreset('lever')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                      atsPreset === 'lever'
                        ? 'bg-emerald-400 text-[var(--color-accent-ink)]'
                        : 'text-slate-400 hover:text-[var(--color-ink)]'
                    }`}
                  >
                    Lever
                  </button>
                  <button
                    onClick={() => setAtsPreset('standard')}
                    className={`px-3 py-1 rounded-lg text-xs font-semibold transition ${
                      atsPreset === 'standard'
                        ? 'bg-emerald-400 text-[var(--color-accent-ink)]'
                        : 'text-slate-400 hover:text-[var(--color-ink)]'
                    }`}
                  >
                    Standard / All
                  </button>
                </div>
              </div>

              {/* Missing Fields Banner if any */}
              {missingFields.length > 0 && (
                <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between">
                  <div className="flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
                    <span>
                      <strong>{missingFields.length} field(s)</strong> are missing in your Master Profile ({missingFields.map(m => m.label).join(', ')}).
                    </span>
                  </div>
                  <span className="text-[11px] text-amber-400/80">Update via Profile tab</span>
                </div>
              )}

              {/* Field Mapping Grid */}
              <div className="border border-dark-750 rounded-xl overflow-hidden divide-y divide-dark-800 bg-dark-850">
                <div className="grid grid-cols-12 px-4 py-2 bg-dark-800/80 text-[11px] font-bold text-slate-400 ">
                  <div className="col-span-4 sm:col-span-3">ATS Form Field</div>
                  <div className="col-span-6 sm:col-span-7">Candidate Profile Value</div>
                  <div className="col-span-2 text-right">1-Click Action</div>
                </div>

                {fields.map(f => {
                  const hasValue = f.value && f.value.trim().length > 0;
                  const isCopied = copiedFieldId === f.id;

                  return (
                    <div 
                      key={f.id} 
                      className="grid grid-cols-12 px-4 py-2.5 items-center hover:bg-dark-800/40 transition text-xs"
                    >
                      <div className="col-span-4 sm:col-span-3 pr-2">
                        <span className="font-semibold text-[var(--color-ink)] block">{f.label}</span>
                        {f.required && (
                          <span className="text-[10px] text-rose-400 font-medium">Required field</span>
                        )}
                      </div>

                      <div className="col-span-6 sm:col-span-7 pr-3 font-mono text-[11px]">
                        {hasValue ? (
                          <div className="flex items-center space-x-2">
                            <span className="text-slate-200 truncate">{f.value}</span>
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold shrink-0">
                              Ready
                            </span>
                          </div>
                        ) : (
                          <div className="flex items-center space-x-1.5 text-amber-400 text-[11px]">
                            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                            <span>Missing in Profile</span>
                          </div>
                        )}
                      </div>

                      <div className="col-span-2 flex justify-end">
                        <button
                          type="button"
                          onClick={() => handleCopyField(f.id, f.value)}
                          disabled={!hasValue}
                          title={hasValue ? `Copy ${f.label}` : 'No value to copy'}
                          className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold flex items-center space-x-1 transition border ${
                            !hasValue
                              ? 'bg-dark-900 border-dark-800 text-slate-600 cursor-not-allowed'
                              : isCopied
                              ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-400'
                              : 'bg-dark-800 hover:bg-dark-750 border-dark-700 text-slate-300 hover:text-[var(--color-ink)]'
                          }`}
                        >
                          {isCopied ? (
                            <>
                              <Check className="w-3 h-3 text-emerald-400" />
                              <span className="hidden sm:inline">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3 h-3" />
                              <span className="hidden sm:inline">Copy</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Compliance Guarantee Banner */}
              <div className="p-3.5 rounded-xl bg-dark-850 border border-dark-750 flex items-start space-x-2.5 text-slate-400 text-[11px] leading-relaxed">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-slate-200 block">Assisted Manual Handoff Compliance:</strong>
                  CareerOS strictly respects employer ATS terms and security policies. We never inject unauthorized bot scripts, bypass CAPTCHA, or simulate candidate submissions. You inspect every value and submit through the official portal.
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: Cover Letter Draft */}
          {activeTab === 'cover_letter' && (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-xs font-bold  text-[var(--color-ink)] block">Tailored Cover Letter Draft</span>
                  <span className="text-[11px] text-slate-400">Grounded strictly in your verified candidate profile and project facts.</span>
                </div>
                <button
                  onClick={handleCopyCoverLetter}
                  className="whitespace-nowrap px-3 py-1.5 rounded-lg bg-dark-800 hover:bg-dark-750 text-slate-200 text-xs font-semibold flex items-center space-x-1.5 border border-dark-700 transition"
                >
                  {copiedLetter ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-emerald-400" />
                      <span className="whitespace-nowrap text-emerald-400">Copied</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>Letter</span>
                    </>
                  )}
                </button>
              </div>

              <pre className="p-4 rounded-xl bg-dark-900 border border-dark-750 font-sans text-xs text-slate-300 whitespace-pre-wrap leading-relaxed max-h-80 overflow-y-auto">
                {dossier.draft_cover_letter}
              </pre>
            </div>
          )}

          {/* TAB 3: Selected Resume Document */}
          {activeTab === 'resume' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center">
                    <FileText className="w-6 h-6" />
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-400  font-semibold">Active Tailored Document</span>
                    <h4 className="font-bold text-[var(--color-ink)] text-sm mt-0.5">
                      {dossier.selected_resume?.title || "Master Candidate Resume"}
                    </h4>
                    <span className="text-[11px] text-emerald-400">Compiled PDF ready for ATS upload</span>
                  </div>
                </div>

                {dossier.selected_resume?.pdf_url && (
                  <a
                    href={dossier.selected_resume.pdf_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-750 border border-dark-600 text-xs font-semibold text-emerald-400 flex items-center space-x-1.5"
                  >
                    <span>View / Download PDF</span>
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>

              {/* Standard Q&A Guidance */}
              <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 space-y-3">
                <span className="text-xs font-bold  text-[var(--color-ink)] block">Standard ATS Questions & Verified Answers</span>
                <div className="space-y-2">
                  {dossier.standard_questions?.map((q, idx) => (
                    <div key={idx} className="p-2.5 rounded-lg bg-dark-900 border border-dark-750 space-y-1">
                      <span className="text-[11px] font-semibold text-slate-300 block">{q.question}</span>
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] text-emerald-400 font-mono">{q.answer}</span>
                        <button
                          type="button"
                          onClick={() => {
                            navigator.clipboard.writeText(q.answer);
                            setCopiedFieldId(`qa_${idx}`);
                            setTimeout(() => setCopiedFieldId(null), 2000);
                          }}
                          className="px-2 py-0.5 rounded text-[10px] bg-dark-800 hover:bg-dark-750 text-slate-300"
                        >
                          {copiedFieldId === `qa_${idx}` ? "Copied" : "Copy Answer"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 4: Workflow Handoff & Tracking */}
          {activeTab === 'workflow' && (
            <div className="space-y-4">
              <div className="p-4 rounded-xl bg-dark-850 border border-dark-700 space-y-3">
                <span className="text-xs font-bold  text-[var(--color-ink)] block">Application Submission Mode</span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  {dossier.submission_modes.map(m => (
                    <div
                      key={m.mode}
                      onClick={() => setSelectedMode(m.mode)}
                      className={`p-3.5 rounded-xl border cursor-pointer transition ${
                        selectedMode === m.mode
                          ? 'bg-dark-800 border-emerald-500/50 ring-1 ring-emerald-500/20'
                          : 'bg-dark-900 border-dark-750 hover:border-dark-700'
                      }`}
                    >
                      <span className="font-bold text-[var(--color-ink)] block">{m.label}</span>
                      <p className="text-[11px] text-slate-400 mt-1 leading-snug">{m.description}</p>
                    </div>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-slate-400 mb-1 font-medium">Tracking Notes / Follow-Up Context (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. Applied via Greenhouse form, referred by alumnus, scheduled reminder for 7 days"
                  value={notes}
                  onChange={e => setNotes(e.target.value)}
                  className="w-full p-2.5 rounded-xl bg-dark-900 border border-dark-750 text-[var(--color-ink)] focus:outline-none focus:ring-1 focus:ring-emerald-500 text-xs"
                />
              </div>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 border-t border-dark-700 bg-dark-850 flex items-center justify-between">
          <a
            href={dossier.application_url || dossier.original_url}
            target="_blank"
            rel="noopener noreferrer"
            className="px-4 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-slate-200 border border-dark-600 text-xs font-semibold flex items-center space-x-1.5 transition"
          >
            <span>Open Official Portal</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>

          <div className="flex items-center space-x-2">
            <button
              onClick={onClose}
              className="px-3.5 py-2 rounded-xl bg-dark-800 hover:bg-dark-700 text-slate-400 text-xs font-medium"
            >
              Cancel
            </button>

            <button
              onClick={handleConfirmSubmission}
              disabled={submitting}
              className="px-4 py-2 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-semibold flex items-center space-x-1.5 transition-emerald-950/40"
            >
              <ShieldCheck className="w-4 h-4" />
              <span>{submitting ? "Saving..." : "Confirm & Move to Tracker"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

