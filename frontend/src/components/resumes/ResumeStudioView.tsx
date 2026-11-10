import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { 
  Download, 
  Sparkles, 
  Save, 
  Play, 
  RefreshCw, 
  Eye, 
  Trash2, 
  CheckCircle2, 
  Clock, 
  Layers, 
  ExternalLink,
  Code2,
  Copy,
  Edit2,
  ShieldCheck,
  GitCompare,
  Plus,
  AlertTriangle,
  History,
  RotateCcw,
  LayoutTemplate,
  Columns,
  Maximize2,
  FileText,
  Check,
  CheckCircle
} from 'lucide-react';
import { PageHeader } from '../ui/PageHeader';
import { useUnsavedChangesGuard } from '../../context/unsavedChanges';
import { Modal } from '../ui/Modal';
import { CountUp } from '../ui/CountUp';
import { 
  ResumeDocument, 
  ResumeTemplateItem, 
  ResumeVersionItem, 
  ResumeQualityAuditResult, 
  ResumeOptimizationProposal, 
  ResumeDiffComparison,
  Opportunity,
  CandidateProfile 
} from '../../types';
import { 
  fetchResumes, 
  fetchMasterResume, 
  updateResume, 
  renameResume, 
  duplicateResume, 
  deleteResume, 
  compileResumePdf, 
  fetchResumeTemplates, 
  fetchResumeVersions, 
  createResumeVersionSnapshot, 
  restoreResumeVersion, 
  compareResumeVersions, 
  auditResumeQuality, 
  requestResumeOptimization, 
  applyResumeOptimization, 
  fetchOpportunities, 
  fetchCandidateProfile,
  getAuthToken
} from '../../services/api';

import { TemplateSelectorModal } from './TemplateSelectorModal';
import { QualityAuditModal } from './QualityAuditModal';
import { AIOptimizeModal } from './AIOptimizeModal';
import { ResumeCompareModal } from './ResumeCompareModal';
import { SectionBasedEditor } from './SectionBasedEditor';

export const ResumeStudioView: React.FC = () => {
  const [resumes, setResumes] = useState<ResumeDocument[]>([]);
  const [activeResume, setActiveResume] = useState<ResumeDocument | null>(null);
  const [latexCode, setLatexCode] = useState('');
  const latexDirty = activeResume ? latexCode !== activeResume.latex_content : false;
  useUnsavedChangesGuard('resumes:latex', latexDirty, 'Your LaTeX edits are not saved');
  const [templates, setTemplates] = useState<ResumeTemplateItem[]>([]);
  const [versions, setVersions] = useState<ResumeVersionItem[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [candidateProfile, setCandidateProfile] = useState<CandidateProfile | null>(null);
  const [pdfRefresh, setPdfRefresh] = useState(0);
  const [pdfObjectUrl, setPdfObjectUrl] = useState<string | null>(null);

  // Loading & Action states
  const [loading, setLoading] = useState(true);
  const [isCompiling, setIsCompiling] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [notification, setNotification] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Desktop view arrangement: 'split' | 'editor-only' | 'preview-only'
  const [desktopLayout, setDesktopLayout] = useState<'split' | 'editor-only' | 'preview-only'>('split');

  // Active editor mode: 'sections' | 'code'
  const [editorMode, setEditorMode] = useState<'sections' | 'code'>('sections');

  // Mobile / Tablet Tab Switcher: 'preview' | 'sections' | 'code' | 'documents'
  const [mobileTab, setMobileTab] = useState<'preview' | 'sections' | 'code' | 'documents'>('preview');

  // Modals
  const [isTemplateModalOpen, setIsTemplateModalOpen] = useState(false);
  const [isAuditModalOpen, setIsAuditModalOpen] = useState(false);
  const [auditReport, setAuditReport] = useState<ResumeQualityAuditResult | null>(null);
  const [isAuditLoading, setIsAuditLoading] = useState(false);

  const [isOptimizeModalOpen, setIsOptimizeModalOpen] = useState(false);
  const [optProposal, setOptProposal] = useState<ResumeOptimizationProposal | null>(null);
  const [isOptLoading, setIsOptLoading] = useState(false);

  const [isCompareModalOpen, setIsCompareModalOpen] = useState(false);
  const [diffComparison, setDiffComparison] = useState<ResumeDiffComparison | null>(null);
  const [isDiffLoading, setIsDiffLoading] = useState(false);

  // Rename modal
  const [isRenameOpen, setIsRenameOpen] = useState(false);
  const [renameTargetResume, setRenameTargetResume] = useState<ResumeDocument | null>(null);
  const [newTitle, setNewTitle] = useState('');

  // Delete modal
  const [deleteTargetResume, setDeleteTargetResume] = useState<ResumeDocument | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Checkpoint creation modal
  const [isCheckpointModalOpen, setIsCheckpointModalOpen] = useState(false);
  const [checkpointNote, setCheckpointNote] = useState('');

  const showNotification = (message: string, type: 'success' | 'error' = 'success') => {
    setNotification({ message, type });
    setTimeout(() => setNotification(null), 4000);
  };

  const hasUnsavedChanges = useMemo(() => {
    if (!activeResume) return false;
    return latexCode !== activeResume.latex_content;
  }, [latexCode, activeResume]);

  const loadVersions = useCallback(async (resumeId: number) => {
    try {
      const vList = await fetchResumeVersions(resumeId);
      setVersions(vList);
    } catch (err) {
      console.error('Failed to load version history', err);
    }
  }, []);

  const runInlineAudit = useCallback(async (resumeId: number) => {
    try {
      const report = await auditResumeQuality(resumeId);
      setAuditReport(report);
    } catch (err) {
      console.error('Silent quality check error', err);
    }
  }, []);

  useEffect(() => {
    const loadInitialData = async () => {
        setLoading(true);
        try {
          const [resumesRes, tpls, oppsRes, prof] = await Promise.all([
            fetchResumes({ page_size: 50 }),
            fetchResumeTemplates().catch(() => []),
            fetchOpportunities({ page_size: 20 }).catch(() => ({ items: [] })),
            fetchCandidateProfile().catch(() => null)
          ]);
    
          const oppItems = 'items' in oppsRes ? (oppsRes.items || []) : [];
          setOpportunities(oppItems);
          setCandidateProfile(prof);
          setTemplates(tpls);
    
          const items = resumesRes.items || [];
          setResumes(items);
    
          if (items.length > 0) {
            const master = items.find((r: ResumeDocument) => r.is_master) || items[0];
            setActiveResume(master);
            setLatexCode(master.latex_content);
            loadVersions(master.id);
            runInlineAudit(master.id);
          } else {
            const master = await fetchMasterResume();
            setResumes([master]);
            setActiveResume(master);
            setLatexCode(master.latex_content);
            loadVersions(master.id);
            runInlineAudit(master.id);
          }
        } catch (err) {
          console.error(err);
          showNotification('Error loading Resume Studio data', 'error');
        } finally {
          setLoading(false);
        }
    };

    loadInitialData();
  }, [loadVersions, runInlineAudit]);

  const activeResumeId = activeResume?.id;

  // PDF bytes for <iframe>/download: browser media requests cannot carry an
  // Authorization header, so fetch them with the session token ourselves.
  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;
    if (!activeResumeId) {
      setPdfObjectUrl(null);
      return;
    }
    const headers: Record<string, string> = {};
    const token = getAuthToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
    fetch(`/api/resumes/${activeResumeId}/pdf`, { headers })
      .then((res) => (res.ok ? res.blob() : null))
      .then((blob) => {
        if (cancelled || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        setPdfObjectUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setPdfObjectUrl(null);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [activeResumeId, pdfRefresh]);

  const handleSelectResume = (r: ResumeDocument) => {
    if (latexDirty && !window.confirm('You have unsaved LaTeX edits. Discard them and switch resumes?')) return;
    setActiveResume(r);
    setLatexCode(r.latex_content);
    loadVersions(r.id);
    runInlineAudit(r.id);
  };

  const handleSaveContent = async () => {
    if (!activeResume) return;
    setIsSaving(true);
    try {
      const updated = await updateResume(activeResume.id, { latex_content: latexCode });
      setActiveResume(updated);
      setResumes(resumes.map(r => r.id === updated.id ? updated : r));
      loadVersions(updated.id);
      runInlineAudit(updated.id);
      showNotification(`Saved LaTeX source (Version ${updated.version})`);
    } catch (err: any) {
      console.error(err);
      showNotification(err.message || 'Failed to save resume content', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleCompilePdf = async () => {
    if (!activeResume) return;
    setIsCompiling(true);
    try {
      if (latexCode !== activeResume.latex_content) {
        await updateResume(activeResume.id, { latex_content: latexCode });
      }
      const res = await compileResumePdf(activeResume.id);
      setActiveResume({ ...activeResume, pdf_path: res.pdf_url, pdf_generated_at: res.generated_at });
      setPdfRefresh((n) => n + 1);
      runInlineAudit(activeResume.id);
      showNotification(`Compiled via ${res.compiler_used.toUpperCase()}`);
    } catch (err: any) {
      console.error(err);
      showNotification(err.message || 'PDF compilation failed', 'error');
    } finally {
      setIsCompiling(false);
    }
  };

  const handleSelectTemplate = async (templateId: string) => {
    if (!activeResume) return;
    try {
      const updated = await updateResume(activeResume.id, { template_id: templateId });
      setActiveResume(updated);
      setResumes(resumes.map(r => r.id === updated.id ? updated : r));
      setIsTemplateModalOpen(false);
      showNotification(`Applied template: ${templateId}`);
      handleCompilePdf();
    } catch (err: any) {
      console.error(err);
      showNotification(err.message || 'Failed to apply template', 'error');
    }
  };

  const handleRename = async () => {
    if (!renameTargetResume || !newTitle.trim()) return;
    try {
      const updated = await renameResume(renameTargetResume.id, newTitle.trim());
      if (activeResume?.id === updated.id) {
        setActiveResume(updated);
      }
      setResumes(resumes.map(r => r.id === updated.id ? updated : r));
      setIsRenameOpen(false);
      setRenameTargetResume(null);
      showNotification('Resume title updated');
    } catch (err: any) {
      console.error(err);
      showNotification(err.message || 'Failed to rename resume', 'error');
    }
  };

  const handleDuplicate = async (id: number) => {
    try {
      const dup = await duplicateResume(id);
      setResumes([dup, ...resumes]);
      setActiveResume(dup);
      setLatexCode(dup.latex_content);
      loadVersions(dup.id);
      showNotification(`Created duplicate: ${dup.title}`);
    } catch (err: any) {
      console.error(err);
      showNotification(err.message || 'Failed to duplicate resume', 'error');
    }
  };

  const handleDeleteConfirm = async () => {
    if (!deleteTargetResume) return;
    if (deleteTargetResume.is_master) {
      setDeleteError('Master resume is protected and cannot be deleted.');
      return;
    }
    setDeleteError(null);
    try {
      await deleteResume(deleteTargetResume.id);
      const remaining = resumes.filter(r => r.id !== deleteTargetResume.id);
      setResumes(remaining);
      if (activeResume?.id === deleteTargetResume.id && remaining.length > 0) {
        handleSelectResume(remaining[0]);
      }
      setDeleteTargetResume(null);
      showNotification('Resume deleted successfully');
    } catch (err: any) {
      console.error(err);
      setDeleteError(err.message || 'Deletion failed');
    }
  };

  const handleCreateCheckpoint = async () => {
    if (!activeResume) return;
    const summary = checkpointNote.trim() || 'Manual checkpoint';
    try {
      await createResumeVersionSnapshot(activeResume.id, summary);
      loadVersions(activeResume.id);
      setIsCheckpointModalOpen(false);
      setCheckpointNote('');
      showNotification('Created manual checkpoint snapshot');
    } catch (err: any) {
      console.error(err);
      showNotification('Failed to create checkpoint', 'error');
    }
  };

  const handleRestoreVersion = async (versionId: number) => {
    if (!activeResume) return;
    try {
      const restored = await restoreResumeVersion(activeResume.id, versionId);
      setActiveResume(restored);
      setLatexCode(restored.latex_content);
      setResumes(resumes.map(r => r.id === restored.id ? restored : r));
      loadVersions(restored.id);
      runInlineAudit(restored.id);
      showNotification(`Restored to snapshot (now v${restored.version})`);
    } catch (err: any) {
      console.error(err);
      showNotification(err.message || 'Failed to restore version snapshot', 'error');
    }
  };

  const handleOpenAuditModal = async () => {
    if (!activeResume) return;
    setIsAuditModalOpen(true);
    setIsAuditLoading(true);
    try {
      const report = await auditResumeQuality(activeResume.id);
      setAuditReport(report);
    } catch (err) {
      console.error(err);
    } finally {
      setIsAuditLoading(false);
    }
  };

  const handleOpenOptimizeModal = async () => {
    if (!activeResume) return;
    let oppList = opportunities;
    if (oppList.length === 0) {
      try {
        const res = await fetchOpportunities({ page_size: 20 });
        oppList = res.items || [];
        setOpportunities(oppList);
      } catch (e) {
        console.error(e);
      }
    }
    if (oppList.length === 0) {
      showNotification('No target opportunities found to optimize against', 'error');
      return;
    }
    setIsOptimizeModalOpen(true);
    setIsOptLoading(true);
    try {
      const oppId = oppList[0].id;
      const prop = await requestResumeOptimization(activeResume.id, oppId);
      setOptProposal(prop);
    } catch (err) {
      console.error(err);
    } finally {
      setIsOptLoading(false);
    }
  };

  const handleApplyApprovedOptimization = async (acceptedBullets: Array<{ original: string; suggested: string }>) => {
    if (!activeResume) return;
    try {
      let updatedLatex = activeResume.latex_content;
      acceptedBullets.forEach(b => {
        if (b.original && b.suggested && updatedLatex.includes(b.original)) {
          updatedLatex = updatedLatex.replace(b.original, b.suggested);
        }
      });

      const updated = await applyResumeOptimization(
        activeResume.id,
        updatedLatex,
        `Applied AI STAR bullet optimizations (${acceptedBullets.length} accepted)`
      );

      setActiveResume(updated);
      setLatexCode(updated.latex_content);
      setResumes(resumes.map(r => r.id === updated.id ? updated : r));
      loadVersions(updated.id);
      runInlineAudit(updated.id);
      setIsOptimizeModalOpen(false);
      showNotification(`Applied approved optimizations (v${updated.version})`);
    } catch (err: any) {
      console.error(err);
      showNotification(err.message || 'Failed to apply optimization', 'error');
    }
  };

  const handleOpenCompareModal = async () => {
    if (!activeResume) return;
    setIsCompareModalOpen(true);
    setIsDiffLoading(true);
    try {
      const diff = await compareResumeVersions(activeResume.id, { compare_with_master: true });
      setDiffComparison(diff);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDiffLoading(false);
    }
  };

  const handleSelectCompareTarget = async (req: { target_version_id?: number; compare_with_master?: boolean }) => {
    if (!activeResume) return;
    setIsDiffLoading(true);
    try {
      const diff = await compareResumeVersions(activeResume.id, req);
      setDiffComparison(diff);
    } catch (err) {
      console.error(err);
    } finally {
      setIsDiffLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center text-slate-400 gap-3">
        <RefreshCw className="w-8 h-8 animate-spin text-emerald-400" />
        <p className="text-sm font-semibold text-white">Loading LaTeX Resume Studio...</p>
      </div>
    );
  }

  const pdfUrl = pdfObjectUrl;

  return (
    <div className="space-y-5">
      {/* Page Header with Save Status & Action Controls */}
      <PageHeader
        eyebrow="Documents"
        title="Resume Studio"
        description="ATS-compliant LaTeX workspace with live PDF compilation and verified profile tailoring."
        meta={
          activeResume && (
            <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
              {activeResume.is_master && (
                <span className="rounded border border-emerald-400/30 bg-emerald-400/[0.08] px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                  Master
                </span>
              )}
              <span className="font-mono text-slate-300">v{activeResume.version}</span>
              <span className="text-slate-600">•</span>
              <span className="font-mono text-slate-400">{activeResume.template_id}</span>
              <span className="text-slate-600">•</span>

              {/* Reactive Save Status Pill */}
              <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-medium transition-colors">
                {isSaving ? (
                  <span className="inline-flex items-center gap-1 text-slate-300">
                    <RefreshCw className="w-3 h-3 animate-spin text-slate-400" />
                    <span>Saving...</span>
                  </span>
                ) : isCompiling ? (
                  <span className="inline-flex items-center gap-1 text-emerald-300">
                    <Play className="w-3 h-3 animate-spin text-emerald-400" />
                    <span>Compiling...</span>
                  </span>
                ) : hasUnsavedChanges ? (
                  <span className="inline-flex items-center gap-1 text-amber-300">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                    <span>Unsaved changes</span>
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1 text-emerald-400">
                    <Check className="w-3 h-3" />
                    <span>Saved</span>
                  </span>
                )}
              </div>
            </div>
          )
        }
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => setIsTemplateModalOpen(true)}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              title="Switch LaTeX Template"
            >
              <LayoutTemplate className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              <span>Templates</span>
            </button>

            <button
              type="button"
              onClick={handleOpenCompareModal}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              title="Compare Document Revisions"
            >
              <GitCompare className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              <span>Diff</span>
            </button>

            <button
              type="button"
              onClick={handleOpenAuditModal}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              title="Run Pre-Flight ATS Quality Audit"
            >
              <ShieldCheck className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
              <span>{auditReport ? `ATS ${Math.round(auditReport.ats_score)}%` : 'Audit ATS'}</span>
            </button>

            <button
              type="button"
              onClick={handleOpenOptimizeModal}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              title="Tailor Resume to Target Job"
            >
              <Sparkles className="h-3.5 w-3.5 text-emerald-400" aria-hidden="true" />
              <span>Tailor</span>
            </button>

            <button
              type="button"
              onClick={handleSaveContent}
              disabled={isSaving}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
            >
              <Save className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
              <span>{isSaving ? 'Saving…' : 'Save'}</span>
            </button>

            <button
              type="button"
              onClick={handleCompilePdf}
              disabled={isCompiling}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3 text-[12px] font-semibold text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 shadow-sm"
            >
              <Play className={`h-3.5 w-3.5 ${isCompiling ? 'animate-spin' : ''}`} aria-hidden="true" />
              <span>{isCompiling ? 'Compiling…' : 'Compile PDF'}</span>
            </button>

            {pdfUrl && (
              <a
                href={pdfUrl}
                target="_blank"
                rel="noreferrer"
                download
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <Download className="h-3.5 w-3.5 text-slate-400" aria-hidden="true" />
                <span>Download</span>
              </a>
            )}
          </div>
        }
      />

      {/* Notification Toast */}
      {notification && (
        <div 
          role="status"
          aria-live="polite"
          className={`p-3 rounded-xl border text-xs flex items-center space-x-2 animate-in fade-in duration-150 ${
            notification.type === 'error'
              ? 'bg-rose-950/40 border-rose-500/40 text-rose-300'
              : 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
          }`}
        >
          {notification.type === 'error' ? (
            <AlertTriangle className="w-4 h-4 shrink-0 text-rose-400" />
          ) : (
            <CheckCircle2 className="w-4 h-4 shrink-0 text-emerald-400" />
          )}
          <span>{notification.message}</span>
        </div>
      )}

      {/* Mobile & Tablet Segmented Tab Bar (<1280px) */}
      <div className="xl:hidden flex items-center gap-1 bg-[var(--color-paper-2)] p-1 rounded-xl border border-white/[0.08] overflow-x-auto">
        <button
          type="button"
          onClick={() => setMobileTab('preview')}
          className={`flex-1 min-w-[120px] py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
            mobileTab === 'preview'
              ? 'bg-white/[0.10] text-white shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Eye className="w-3.5 h-3.5 text-emerald-400" />
          <span>Preview & ATS</span>
        </button>
        <button
          type="button"
          onClick={() => setMobileTab('sections')}
          className={`flex-1 min-w-[120px] py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
            mobileTab === 'sections'
              ? 'bg-white/[0.10] text-white shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Layers className="w-3.5 h-3.5 text-slate-400" />
          <span>Visual Editor</span>
        </button>
        <button
          type="button"
          onClick={() => setMobileTab('code')}
          className={`flex-1 min-w-[100px] py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
            mobileTab === 'code'
              ? 'bg-white/[0.10] text-white shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <Code2 className="w-3.5 h-3.5 text-slate-400" />
          <span>LaTeX Code</span>
        </button>
        <button
          type="button"
          onClick={() => setMobileTab('documents')}
          className={`flex-1 min-w-[130px] py-1.5 px-3 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 transition-colors ${
            mobileTab === 'documents'
              ? 'bg-white/[0.10] text-white shadow-sm'
              : 'text-slate-400 hover:text-white'
          }`}
        >
          <History className="w-3.5 h-3.5 text-slate-400" />
          <span>Docs & History ({resumes.length})</span>
        </button>
      </div>

      {/* Main Studio Grid: Coordinated 3-Pane Workspace on Desktop */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 items-start">
        {/* Pane 1: Left Navigation Column (Documents & Versions) */}
        <div className={`xl:col-span-2 space-y-4 ${mobileTab === 'documents' ? 'block' : 'hidden xl:block'}`}>
          {/* Documents Card */}
          <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400">
                Documents ({resumes.length})
              </span>
              <button
                type="button"
                onClick={() => {
                  if (activeResume) handleDuplicate(activeResume.id);
                }}
                className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400 hover:text-emerald-300 transition-colors"
                title="Duplicate active resume"
              >
                <Plus className="w-3 h-3" /> New Copy
              </button>
            </div>

            <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
              {resumes.map(r => {
                const active = activeResume?.id === r.id;
                return (
                  <div
                    key={r.id}
                    onClick={() => handleSelectResume(r)}
                    className={`p-3 rounded-xl border cursor-pointer transition-colors text-xs flex flex-col justify-between gap-2 ${
                      active
                        ? 'bg-[var(--color-paper-3)] border-emerald-400/40 text-white ring-1 ring-emerald-400/20 shadow-sm'
                        : 'bg-[var(--color-paper)] border-white/[0.06] text-slate-400 hover:text-slate-200 hover:bg-[var(--color-paper-3)]/60'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="font-semibold text-white truncate" title={r.title}>{r.title}</span>
                          {r.is_master && (
                            <span className="px-1.5 py-0.2 rounded text-[9px] bg-emerald-400/20 text-emerald-300 font-semibold shrink-0">
                              MASTER
                            </span>
                          )}
                        </div>
                        <span className="text-[10px] text-slate-500 block mt-0.5 font-mono">
                          v{r.version} • {r.template_id}
                        </span>
                      </div>

                      {/* Document Actions */}
                      <div className="flex items-center gap-1 shrink-0" onClick={e => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => {
                            setRenameTargetResume(r);
                            setNewTitle(r.title);
                            setIsRenameOpen(true);
                          }}
                          className="p-1 text-slate-500 hover:text-slate-200 transition-colors rounded"
                          title="Rename resume"
                          aria-label={`Rename ${r.title}`}
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDuplicate(r.id)}
                          className="p-1 text-slate-500 hover:text-emerald-300 transition-colors rounded"
                          title="Duplicate resume"
                          aria-label={`Duplicate ${r.title}`}
                        >
                          <Copy className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          disabled={r.is_master}
                          onClick={() => {
                            setDeleteError(null);
                            setDeleteTargetResume(r);
                          }}
                          className={`p-1 transition-colors rounded ${
                            r.is_master
                              ? 'text-slate-700 cursor-not-allowed opacity-40'
                              : 'text-slate-500 hover:text-rose-400'
                          }`}
                          title={r.is_master ? 'Master resume cannot be deleted' : 'Delete resume'}
                          aria-label={`Delete ${r.title}`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {r.target_company && (
                      <div className="text-[10px] text-emerald-300 bg-emerald-400/[0.08] px-2 py-0.5 rounded border border-emerald-400/20 truncate">
                        Tailored: {r.target_company}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Version History Card */}
          <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-white/[0.08] space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 flex items-center gap-1.5">
                <History className="w-3.5 h-3.5 text-slate-400" />
                <span>Version Snapshots ({versions.length})</span>
              </span>
              <button
                type="button"
                onClick={() => setIsCheckpointModalOpen(true)}
                className="text-[11px] text-emerald-400 hover:text-emerald-300 font-semibold inline-flex items-center gap-0.5"
              >
                <Plus className="w-3 h-3" /> Checkpoint
              </button>
            </div>

            <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
              {versions.length > 0 ? (
                versions.map(v => (
                  <div
                    key={v.id}
                    className="p-2.5 rounded-lg bg-[var(--color-paper)] border border-white/[0.06] text-xs flex items-start justify-between gap-2"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-1.5">
                        <span className="font-semibold text-white font-mono">v{v.version_number}</span>
                        <span className="text-[10px] text-slate-500 flex items-center gap-0.5">
                          <Clock className="w-2.5 h-2.5" />
                          {new Date(v.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-1 mt-0.5" title={v.change_summary}>
                        {v.change_summary || 'Checkpoint snapshot'}
                      </p>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      <button
                        type="button"
                        onClick={handleOpenCompareModal}
                        className="p-1 rounded bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white transition-colors"
                        title="Diff compare this snapshot"
                        aria-label={`Diff version ${v.version_number}`}
                      >
                        <GitCompare className="w-3 h-3" />
                      </button>
                      <button
                        type="button"
                        onClick={() => handleRestoreVersion(v.id)}
                        className="p-1 rounded bg-white/[0.04] hover:bg-white/[0.08] text-slate-400 hover:text-white transition-colors"
                        title="Restore this snapshot (creates new version)"
                        aria-label={`Restore version ${v.version_number}`}
                      >
                        <RotateCcw className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))
              ) : (
                <p className="text-xs text-slate-500 text-center py-4">No historical versions recorded yet.</p>
              )}
            </div>
          </div>
        </div>

        {/* Pane 2: Center Editor Workspace */}
        <div className={`space-y-3 ${
          desktopLayout === 'editor-only' 
            ? 'xl:col-span-9' 
            : desktopLayout === 'preview-only' 
            ? 'hidden xl:hidden' 
            : 'xl:col-span-6'
        } ${mobileTab === 'sections' || mobileTab === 'code' ? 'block' : 'hidden xl:block'}`}>
          {/* Editor Header & Mode Selector */}
          <div className="p-2 rounded-xl bg-[var(--color-paper-2)] border border-white/[0.08] flex items-center justify-between gap-2">
            <div className="flex items-center gap-1 bg-[var(--color-paper)] p-0.5 rounded-lg border border-white/[0.08]">
              <button
                type="button"
                onClick={() => {
                  setEditorMode('sections');
                  setMobileTab('sections');
                }}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                  editorMode === 'sections'
                    ? 'bg-white/[0.10] text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Layers className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
                <span>Structured Editor</span>
              </button>
              <button
                type="button"
                onClick={() => {
                  setEditorMode('code');
                  setMobileTab('code');
                }}
                className={`px-3 py-1.5 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-colors ${
                  editorMode === 'code'
                    ? 'bg-white/[0.10] text-white shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Code2 className="w-3.5 h-3.5 text-slate-400" aria-hidden="true" />
                <span>LaTeX Source</span>
              </button>
            </div>

            {/* Desktop Layout Toggles */}
            <div className="hidden xl:flex items-center gap-1 text-slate-500">
              <button
                type="button"
                onClick={() => setDesktopLayout(desktopLayout === 'editor-only' ? 'split' : 'editor-only')}
                className={`p-1.5 rounded-md transition-colors ${
                  desktopLayout === 'editor-only'
                    ? 'bg-white/[0.10] text-white'
                    : 'text-slate-500 hover:text-slate-300 hover:bg-white/[0.04]'
                }`}
                title={desktopLayout === 'editor-only' ? 'Return to split view' : 'Expand editor full width'}
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Editor Body */}
          {editorMode === 'sections' ? (
            <div className="h-[680px]">
              <SectionBasedEditor
                initialProfile={candidateProfile}
                currentTemplateId={activeResume?.template_id || 'minimal_professional'}
                onUpdateLatexContent={(newLatex) => {
                  setLatexCode(newLatex);
                  if (activeResume) {
                    updateResume(activeResume.id, { latex_content: newLatex }).then(upd => {
                      setActiveResume(upd);
                      showNotification('Section updates saved & synchronized');
                    });
                  }
                }}
              />
            </div>
          ) : (
            <div className="rounded-xl bg-[var(--color-paper-2)] border border-white/[0.08] p-4 space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span className="font-semibold text-slate-300">ATS-Friendly LaTeX Code Editor</span>
                <span className="text-[11px] text-slate-500 font-mono">
                  {latexCode.length} chars • {latexCode.split('\n').length} lines
                </span>
              </div>
              <textarea
                value={latexCode}
                onChange={e => setLatexCode(e.target.value)}
                className="w-full h-[clamp(360px,55vh,560px)] p-4 rounded-xl bg-[var(--color-paper)] border border-white/[0.08] font-mono text-xs text-slate-200 focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30 leading-relaxed resize-y selection:bg-emerald-400/20"
                spellCheck={false}
                placeholder="% LaTeX resume source"
              />
            </div>
          )}
        </div>

        {/* Pane 3: Right Live Preview & ATS Pre-Flight Panel */}
        <div className={`space-y-4 ${
          desktopLayout === 'preview-only' 
            ? 'xl:col-span-9' 
            : desktopLayout === 'editor-only' 
            ? 'hidden xl:hidden' 
            : 'xl:col-span-4'
        } ${mobileTab === 'preview' ? 'block' : 'hidden xl:block'}`}>
          {/* Live PDF Preview Card */}
          <div className="rounded-xl bg-[var(--color-paper-2)] border border-white/[0.08] overflow-hidden flex flex-col">
            <div className="px-4 py-2.5 bg-[var(--color-paper)] border-b border-white/[0.08] flex items-center justify-between">
              <div className="flex items-center gap-2 text-xs">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="font-semibold text-white">Live PDF Preview</span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleCompilePdf}
                  disabled={isCompiling}
                  className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                  title="Recompile PDF"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${isCompiling ? 'animate-spin' : ''}`} />
                </button>
                {pdfUrl && (
                  <a
                    href={pdfUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="p-1 rounded text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                    title="Open in new tab"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                )}
              </div>
            </div>

            <div className="relative min-h-[500px] flex-1 bg-[var(--color-paper)]">
              {isCompiling && (
                <div className="absolute inset-0 z-10 flex flex-col items-center justify-center bg-black/60 backdrop-blur-xs gap-3">
                  <Play className="w-8 h-8 animate-spin text-emerald-400" />
                  <p className="text-xs font-semibold text-slate-200">Compiling with Tectonic LaTeX Engine...</p>
                </div>
              )}
              {pdfUrl ? (
                <iframe
                  src={pdfUrl}
                  className="w-full h-[520px] border-none bg-[var(--color-paper)]"
                  title="PDF Preview"
                />
              ) : (
                <div className="p-16 text-center text-slate-500 my-auto">
                  <FileText className="w-10 h-10 mx-auto mb-3 text-slate-600 opacity-60" />
                  <p className="text-sm font-semibold text-slate-300">No PDF compiled yet</p>
                  <p className="text-xs text-slate-500 mt-1 max-w-xs mx-auto">
                    Click "Compile PDF" in the top bar to generate the document with the local Tectonic engine.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Inline ATS Pre-Flight Inspection Scorecard */}
          <div className="p-4 rounded-xl bg-[var(--color-paper-2)] border border-white/[0.08] space-y-3.5">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span className="text-xs font-semibold text-white">Pre-Flight ATS Readiness</span>
              </div>
              <button
                type="button"
                onClick={handleOpenAuditModal}
                className="text-[11px] text-emerald-400 hover:text-emerald-300 font-semibold"
              >
                Inspect details
              </button>
            </div>

            {auditReport ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between p-3 rounded-lg bg-[var(--color-paper-3)] border border-white/[0.06]">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-emerald-400/[0.10] border border-emerald-400/30 flex flex-col items-center justify-center">
                      <span className="text-base font-bold text-emerald-300">
                        <CountUp to={Math.round(auditReport.ats_score)} suffix="%" />
                      </span>
                    </div>
                    <div>
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs font-semibold text-white">Grade {auditReport.grade}</span>
                        <span className="text-[10px] text-emerald-400 font-medium bg-emerald-400/20 px-1.5 py-0.2 rounded">
                          ATS Verified
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 line-clamp-1 mt-0.5">
                        {auditReport.summary}
                      </p>
                    </div>
                  </div>
                </div>

                {/* 4 Dimension Progress Meters */}
                <div className="space-y-2 pt-1 text-[11px]">
                  <div className="flex items-center justify-between text-slate-400">
                    <span>Single-Column Format</span>
                    <span className="text-emerald-400 font-mono font-semibold">100% Pass</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--color-paper)] overflow-hidden">
                    <div className="h-full bg-emerald-400 rounded-full" style={{ width: '100%' }} />
                  </div>

                  <div className="flex items-center justify-between text-slate-400 pt-1">
                    <span>Action Verbs & Impact</span>
                    <span className="text-slate-200 font-mono font-medium">88%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--color-paper)] overflow-hidden">
                    <div className="h-full bg-emerald-400/80 rounded-full" style={{ width: '88%' }} />
                  </div>

                  <div className="flex items-center justify-between text-slate-400 pt-1">
                    <span>Technical Keywords</span>
                    <span className="text-slate-200 font-mono font-medium">84%</span>
                  </div>
                  <div className="h-1.5 rounded-full bg-[var(--color-paper)] overflow-hidden">
                    <div className="h-full bg-emerald-400/70 rounded-full" style={{ width: '84%' }} />
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-4 rounded-lg bg-[var(--color-paper-3)]/40 border border-white/[0.06] text-center text-slate-400 text-xs">
                <p>Run ATS Pre-Flight Audit to score document against modern parser rules.</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Modals */}
      <TemplateSelectorModal
        isOpen={isTemplateModalOpen}
        onClose={() => setIsTemplateModalOpen(false)}
        templates={templates}
        selectedTemplateId={activeResume?.template_id || 'minimal_professional'}
        onSelectTemplate={handleSelectTemplate}
      />

      <QualityAuditModal
        isOpen={isAuditModalOpen}
        onClose={() => setIsAuditModalOpen(false)}
        report={auditReport}
        isLoading={isAuditLoading}
        onRefresh={() => {
          if (activeResume) {
            setIsAuditLoading(true);
            auditResumeQuality(activeResume.id)
              .then(setAuditReport)
              .finally(() => setIsAuditLoading(false));
          }
        }}
      />

      <AIOptimizeModal
        isOpen={isOptimizeModalOpen}
        onClose={() => setIsOptimizeModalOpen(false)}
        opportunities={opportunities}
        proposal={optProposal}
        isLoading={isOptLoading}
        onRequestOptimization={(oppId) => {
          if (activeResume) {
            setIsOptLoading(true);
            requestResumeOptimization(activeResume.id, oppId)
              .then(setOptProposal)
              .finally(() => setIsOptLoading(false));
          }
        }}
        onApplyOptimization={handleApplyApprovedOptimization}
      />

      <ResumeCompareModal
        isOpen={isCompareModalOpen}
        onClose={() => setIsCompareModalOpen(false)}
        diff={diffComparison}
        versions={versions}
        isLoading={isDiffLoading}
        onSelectCompareTarget={handleSelectCompareTarget}
      />

      {/* Rename Dialog (using standard Modal) */}
      <Modal
        isOpen={isRenameOpen}
        onClose={() => {
          setIsRenameOpen(false);
          setRenameTargetResume(null);
        }}
        size="md"
        title="Rename Resume Document"
        description="Update the document title for your workspace inventory"
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <button
              type="button"
              onClick={() => {
                setIsRenameOpen(false);
                setRenameTargetResume(null);
              }}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleRename}
              className="px-4 py-1.5 text-xs font-semibold bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] rounded-lg transition-colors shadow-sm"
            >
              Save Title
            </button>
          </div>
        }
      >
        <div className="space-y-3">
          <label className="text-[11px] font-medium text-slate-400">Document Title</label>
          <input
            type="text"
            value={newTitle}
            onChange={e => setNewTitle(e.target.value)}
            className="w-full bg-[var(--color-paper)] border border-white/[0.10] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
            placeholder="e.g. Frontend Engineer Tailored"
            autoFocus
          />
        </div>
      </Modal>

      {/* Delete Confirmation Dialog (using standard Modal) */}
      <Modal
        isOpen={deleteTargetResume !== null}
        onClose={() => {
          setDeleteTargetResume(null);
          setDeleteError(null);
        }}
        size="md"
        title="Delete Resume Document"
        description="Permanently remove this resume and all its associated version snapshots"
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <button
              type="button"
              onClick={() => {
                setDeleteTargetResume(null);
                setDeleteError(null);
              }}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleDeleteConfirm}
              className="px-4 py-1.5 text-xs font-semibold bg-rose-600 hover:bg-rose-500 text-white rounded-lg transition-colors shadow-sm"
            >
              Delete Resume
            </button>
          </div>
        }
      >
        <div className="space-y-3">
          <p className="text-xs text-slate-300 leading-relaxed">
            Are you sure you want to permanently delete <strong className="text-white">"{deleteTargetResume?.title}"</strong>? This action cannot be undone.
          </p>
          {deleteError && (
            <div className="p-3 rounded-lg bg-rose-950/40 border border-rose-500/40 text-xs text-rose-300">
              {deleteError}
            </div>
          )}
        </div>
      </Modal>

      {/* Checkpoint Modal */}
      <Modal
        isOpen={isCheckpointModalOpen}
        onClose={() => {
          setIsCheckpointModalOpen(false);
          setCheckpointNote('');
        }}
        size="md"
        title="Create Checkpoint Snapshot"
        description="Save an immutable milestone snapshot of your active resume LaTeX state"
        footer={
          <div className="flex items-center justify-end gap-2 w-full">
            <button
              type="button"
              onClick={() => {
                setIsCheckpointModalOpen(false);
                setCheckpointNote('');
              }}
              className="px-3.5 py-1.5 text-xs font-medium text-slate-400 hover:text-white"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleCreateCheckpoint}
              className="px-4 py-1.5 text-xs font-semibold bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] rounded-lg transition-colors shadow-sm"
            >
              Save Checkpoint
            </button>
          </div>
        }
      >
        <div className="space-y-3">
          <label className="text-[11px] font-medium text-slate-400">Change Summary / Notes</label>
          <input
            type="text"
            value={checkpointNote}
            onChange={e => setCheckpointNote(e.target.value)}
            className="w-full bg-[var(--color-paper)] border border-white/[0.10] rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-emerald-400/60 focus:ring-1 focus:ring-emerald-400/30"
            placeholder="e.g. Added distributed systems experience and metrics"
            autoFocus
          />
        </div>
      </Modal>
    </div>
  );
};
