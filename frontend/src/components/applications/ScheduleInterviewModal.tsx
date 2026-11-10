import React, { useState } from 'react';
import {
  Video,
  Calendar,
  Clock,
  User,
  Link as LinkIcon,
  FileText,
  X,
  AlertCircle,
  Building
} from 'lucide-react';
import { ApplicationRecord } from '../../types';
import { scheduleApplicationInterview } from '../../services/api';

interface ScheduleInterviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  application: ApplicationRecord | null;
  onSuccess: () => void;
}

export const ScheduleInterviewModal: React.FC<ScheduleInterviewModalProps> = ({
  isOpen,
  onClose,
  application,
  onSuccess
}) => {
  const [formData, setFormData] = useState({
    round_name: 'Technical Round 1',
    date: new Date(Date.now() + 24 * 3600 * 1000).toISOString().slice(0, 16), // tomorrow default
    format: 'Virtual Video (Google Meet / Zoom)',
    interviewer: '',
    meeting_link: '',
    notes: ''
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen || !application) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.round_name.trim() || !formData.date) {
      setError('Round name and interview date are required.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await scheduleApplicationInterview(application.id, {
        round_name: formData.round_name,
        date: new Date(formData.date).toISOString(),
        format: formData.format,
        interviewer: formData.interviewer || undefined,
        meeting_link: formData.meeting_link || undefined,
        notes: formData.notes || undefined
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.message || 'Failed to schedule interview round');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div className="border border-white/[0.07] bg-[var(--color-paper)] rounded-xl max-w-md w-full p-6 space-y-4">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/[0.07] pb-3">
          <div>
            <h3 className="text-sm font-bold text-[var(--color-ink)] flex items-center space-x-2">
              <Video className="w-4 h-4 text-sky-300" />
              <span>Schedule Interview Round</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              {application.company_name} , {application.job_title}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close dialog"
            className="p-1 rounded-lg text-slate-400 hover:text-[var(--color-ink)] hover:bg-[var(--color-paper-3)] transition min-h-[28px] min-w-[28px] flex items-center justify-center focus-visible:ring-1 focus-visible:ring-emerald-500"
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>

        {error && (
          <div className="p-2.5 rounded-lg bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Interview Round <span className="text-rose-400">*</span>
            </label>
            <select
              value={formData.round_name}
              onChange={(e) => setFormData({ ...formData, round_name: e.target.value })}
              className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
            >
              <option value="Recruiter Phone Screen">Recruiter Phone Screen</option>
              <option value="Technical Round 1 (Coding / DSA)">Technical Round 1 (Coding / DSA)</option>
              <option value="Technical Round 2 (System Architecture)">Technical Round 2 (System Architecture)</option>
              <option value="Hiring Manager Discussion">Hiring Manager Discussion</option>
              <option value="Behavioral & Values Alignment">Behavioral & Values Alignment</option>
              <option value="Take-Home Challenge Review">Take-Home Challenge Review</option>
              <option value="Final Executive Round">Final Executive Round</option>
            </select>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">
              Date & Time <span className="text-rose-400">*</span>
            </label>
            <input
              type="datetime-local"
              required
              value={formData.date}
              onChange={(e) => setFormData({ ...formData, date: e.target.value })}
              className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-purple-500"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Format</label>
              <select
                value={formData.format}
                onChange={(e) => setFormData({ ...formData, format: e.target.value })}
                className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
              >
                <option value="Virtual Video (Google Meet / Zoom)">Virtual Video</option>
                <option value="Phone Call">Phone Call</option>
                <option value="In-Person Office">In-Person Office</option>
                <option value="Online Code Assessment">Code Assessment</option>
              </select>
            </div>

            <div>
              <label className="text-xs font-semibold text-slate-300 block mb-1">Interviewer Name</label>
              <input
                type="text"
                value={formData.interviewer}
                onChange={(e) => setFormData({ ...formData, interviewer: e.target.value })}
                placeholder="e.g. Alex Chen"
                className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-purple-500"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Meeting / Video Link</label>
            <input
              type="url"
              value={formData.meeting_link}
              onChange={(e) => setFormData({ ...formData, meeting_link: e.target.value })}
              placeholder="https://meet.google.com/abc-defg-hij"
              className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-purple-500"
            />
          </div>

          <div>
            <label className="text-xs font-semibold text-slate-300 block mb-1">Preparation Notes / Focus Areas</label>
            <textarea
              rows={2}
              value={formData.notes}
              onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
              placeholder="Focus on distributed caching, Redis, and project architecture..."
              className="w-full bg-slate-950 border border-white/[0.09] rounded-lg px-3 py-2 text-xs text-[var(--color-ink)] focus:outline-none focus:border-purple-500"
            />
          </div>

          <div className="pt-2 flex items-center justify-end space-x-2 border-t border-white/[0.07]">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 text-xs text-slate-400 hover:text-[var(--color-ink)]"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={loading}
              className="px-4 py-2 bg-emerald-400 hover:bg-emerald-300 disabled:opacity-50 text-[var(--color-accent-ink)] font-bold rounded-lg text-xs transition"
            >
              {loading ? 'Saving Round...' : 'Add to Schedule'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
