import React, { useState } from 'react';
import { X, Link2, FileText, Mail, Sparkles, Loader2, CheckCircle2 } from 'lucide-react';
import { importFromUrl, importFromPaste, importFromEmailAlert } from '../../services/api';
import { Modal } from '../ui/Modal';

interface ManualImportModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ManualImportModal: React.FC<ManualImportModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [activeTab, setActiveTab] = useState<'url' | 'paste' | 'email'>('url');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Form states
  const [url, setUrl] = useState('');
  const [pasteTitle, setPasteTitle] = useState('');
  const [pasteCompany, setPasteCompany] = useState('');
  const [pasteLocation, setPasteLocation] = useState('Remote, India');
  const [pasteStipend, setPasteStipend] = useState('₹35,000 / month');
  const [pasteDesc, setPasteDesc] = useState('');
  const [pasteUrl, setPasteUrl] = useState('');

  const [emailText, setEmailText] = useState('');
  const [emailPlatform, setEmailPlatform] = useState('internshala');

  if (!isOpen) return null;

  const handleUrlSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await importFromUrl(url.trim());
      setSuccessMsg("Opportunity successfully extracted and ingested into discovery feed!");
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to import from URL");
    } finally {
      setLoading(false);
    }
  };

  const handlePasteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!pasteTitle.trim() || !pasteCompany.trim() || !pasteDesc.trim()) {
      setError("Please fill in Job Title, Company Name, and Job Description.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await importFromPaste({
        title: pasteTitle,
        company_name: pasteCompany,
        location: pasteLocation,
        description: pasteDesc,
        stipend_text: pasteStipend,
        original_url: pasteUrl
      });
      setSuccessMsg("Job description successfully analyzed and saved!");
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to process pasted job description");
    } finally {
      setLoading(false);
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      await importFromEmailAlert(emailText, emailPlatform);
      setSuccessMsg("Email alert parsed and added to opportunities!");
      setTimeout(() => {
        onSuccess();
        onClose();
      }, 1000);
    } catch (err: any) {
      setError(err.message || "Failed to parse email alert");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="2xl"
      title="Import Job Opportunity"
      description="Manually ingest opportunities from URLs, raw descriptions, or alert digests"
    >
      <div>
        {/* Tab Selection */}
        <div className="px-5 pt-3 border-b border-dark-700 flex space-x-4 bg-dark-900" role="tablist" aria-label="Import methods">
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'url'}
            onClick={() => { setActiveTab('url'); setError(null); }}
            className={`pb-3 text-xs font-semibold flex items-center space-x-1.5 border-b-2 transition focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 rounded-t ${
              activeTab === 'url' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-[var(--color-ink)]'
            }`}
          >
            <Link2 className="w-4 h-4" aria-hidden="true" />
            <span>Import via URL</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'paste'}
            onClick={() => { setActiveTab('paste'); setError(null); }}
            className={`pb-3 text-xs font-semibold flex items-center space-x-1.5 border-b-2 transition focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 rounded-t ${
              activeTab === 'paste' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-[var(--color-ink)]'
            }`}
          >
            <FileText className="w-4 h-4" aria-hidden="true" />
            <span>Paste Job Description</span>
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={activeTab === 'email'}
            onClick={() => { setActiveTab('email'); setError(null); }}
            className={`pb-3 text-xs font-semibold flex items-center space-x-1.5 border-b-2 transition focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-emerald-500 rounded-t ${
              activeTab === 'email' ? 'border-emerald-500 text-emerald-400' : 'border-transparent text-slate-400 hover:text-[var(--color-ink)]'
            }`}
          >
            <Mail className="w-4 h-4" aria-hidden="true" />
            <span>Import Email Alert</span>
          </button>
        </div>

        {/* Form Body */}
        <div className="p-6">
          {error && (
            <div className="mb-4 p-3 rounded-lg bg-rose-950/40 border border-rose-500/30 text-rose-300 text-xs">
              {error}
            </div>
          )}
          {successMsg && (
            <div className="mb-4 p-3 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs flex items-center space-x-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <span>{successMsg}</span>
            </div>
          )}

          {activeTab === 'url' && (
            <form onSubmit={handleUrlSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1.5">Public Career or Job Listing URL</label>
                <input
                  type="url"
                  placeholder="https://boards.greenhouse.io/... or https://internshala.com/..."
                  value={url}
                  onChange={e => setUrl(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs placeholder:text-slate-600 focus:outline-none focus:border-emerald-500"
                  required
                />
                <p className="text-[11px] text-slate-400 mt-1.5">
                  Supports company career pages (Greenhouse, Lever, Ashby), Internshala, LinkedIn, Naukri, and public job portals.
                </p>
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-semibold flex items-center space-x-2 transition"
                >
                  {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{loading ? "Extracting..." : "Analyze & Ingest Opportunity"}</span>
                </button>
              </div>
            </form>
          )}

          {activeTab === 'paste' && (
            <form onSubmit={handlePasteSubmit} className="space-y-3.5">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Job Title *</label>
                  <input
                    type="text"
                    placeholder="e.g. AI Engineer Intern"
                    value={pasteTitle}
                    onChange={e => setPasteTitle(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500"
                    required
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Company Name *</label>
                  <input
                    type="text"
                    placeholder="e.g. Swiggy"
                    value={pasteCompany}
                    onChange={e => setPasteCompany(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Location</label>
                  <input
                    type="text"
                    placeholder="e.g. Bengaluru, India or Remote"
                    value={pasteLocation}
                    onChange={e => setPasteLocation(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">Stipend</label>
                  <input
                    type="text"
                    placeholder="e.g. ₹35,000 / month"
                    value={pasteStipend}
                    onChange={e => setPasteStipend(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Full Job Description *</label>
                <textarea
                  rows={4}
                  placeholder="Paste complete responsibilities, technical requirements, and eligibility details..."
                  value={pasteDesc}
                  onChange={e => setPasteDesc(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500 font-sans"
                  required
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Application URL (Optional)</label>
                <input
                  type="url"
                  placeholder="Link to apply"
                  value={pasteUrl}
                  onChange={e => setPasteUrl(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-semibold flex items-center space-x-2 transition"
                >
                  {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{loading ? "Analyzing..." : "Process Job Listing"}</span>
                </button>
              </div>
            </form>
          )}

          {activeTab === 'email' && (
            <form onSubmit={handleEmailSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Platform Format</label>
                <select
                  value={emailPlatform}
                  onChange={e => setEmailPlatform(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500"
                >
                  <option value="internshala">Internshala Job Alert</option>
                  <option value="linkedin">LinkedIn Daily Job Digest</option>
                  <option value="naukri">Naukri Job Recommendation</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Pasted Alert Email Content</label>
                <textarea
                  rows={5}
                  placeholder="Paste the text from your job alert email..."
                  value={emailText}
                  onChange={e => setEmailText(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-dark-800 border border-dark-600 text-[var(--color-ink)] text-xs focus:outline-none focus:border-emerald-500 font-mono"
                  required
                />
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-xl bg-emerald-400 hover:bg-emerald-300 text-[var(--color-accent-ink)] text-xs font-semibold flex items-center space-x-2 transition"
                >
                  {loading && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                  <span>{loading ? "Parsing..." : "Ingest Alert"}</span>
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </Modal>
  );
};
