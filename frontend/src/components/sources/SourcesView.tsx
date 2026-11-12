import React, { useState, useEffect } from 'react';
import { 
  RotateCw, 
  Sliders, 
  Play, 
  Pause, 
  FileText, 
  RefreshCcw,
  Info
} from 'lucide-react';
import { JobSource, SyncLog } from '../../types';
import { 
  fetchSources, 
  syncSource, 
  syncAllSources, 
  retryFailedSources, 
  testSourceConnection, 
  updateSource, 
  fetchSyncLogs,
  fetchSchedulerStatus,
  toggleSchedulerState 
} from '../../services/api';
import { PageHeader } from '../ui/PageHeader';
import { CountUp } from '../ui/CountUp';

export const SourcesView: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const [sources, setSources] = useState<JobSource[]>([]);
  const [logs, setLogs] = useState<SyncLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [syncingId, setSyncingId] = useState<number | null>(null);
  const [syncingAll, setSyncingAll] = useState(false);
  const [retryingFailed, setRetryingFailed] = useState(false);
  const [schedulerEnabled, setSchedulerEnabled] = useState(true);
  const [testResult, setTestResult] = useState<{ id: number; message: string; success: boolean } | null>(null);
  const [bannerMsg, setBannerMsg] = useState<{ text: string; type: 'success' | 'info' | 'error' } | null>(null);
  const [showLogs, setShowLogs] = useState(false);

  // Configure modal state
  const [configSource, setConfigSource] = useState<JobSource | null>(null);
  const [feedUrl, setFeedUrl] = useState('');
  const [freqHours, setFreqHours] = useState(6);

  const loadData = () => {
    setLoading(true);
    Promise.all([fetchSources(), fetchSyncLogs(), fetchSchedulerStatus()])
      .then(([srcs, lgs, sched]) => {
        setSources(srcs);
        setLogs(lgs);
        if (sched && typeof sched.is_enabled === 'boolean') {
          setSchedulerEnabled(sched.is_enabled);
        }
      })
      .catch(err => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSync = async (id: number) => {
    setSyncingId(id);
    try {
      await syncSource(id);
      loadData();
      setBannerMsg({ text: "Source synchronized successfully.", type: "success" });
      setTimeout(() => setBannerMsg(null), 4000);
    } catch (err: any) {
      console.error(err);
      setBannerMsg({ text: err.message || "Sync failed", type: "error" });
      setTimeout(() => setBannerMsg(null), 4000);
    } finally {
      setSyncingId(null);
    }
  };

  const handleSyncAll = async () => {
    setSyncingAll(true);
    try {
      await syncAllSources();
      setBannerMsg({ text: "Parallel background synchronization launched across all active sources.", type: "info" });
      setTimeout(() => {
        loadData();
        setSyncingAll(false);
      }, 3000);
    } catch (err: any) {
      setBannerMsg({ text: err.message || "Failed to trigger parallel sync", type: "error" });
      setSyncingAll(false);
    }
  };

  const handleRetryFailed = async () => {
    setRetryingFailed(true);
    try {
      const res = await retryFailedSources();
      setBannerMsg({ text: res.message || `Retrying ${res.retried} failed sources.`, type: "info" });
      loadData();
      setTimeout(() => setBannerMsg(null), 4000);
    } catch (err: any) {
      setBannerMsg({ text: err.message || "Retry failed", type: "error" });
    } finally {
      setRetryingFailed(false);
    }
  };

  const handleToggleScheduler = async () => {
    const nextState = !schedulerEnabled;
    try {
      await toggleSchedulerState(nextState);
      setSchedulerEnabled(nextState);
      setBannerMsg({ 
        text: `Background synchronization scheduler is now ${nextState ? 'ACTIVE (every 6h)' : 'PAUSED'}.`, 
        type: nextState ? "success" : "info" 
      });
      setTimeout(() => setBannerMsg(null), 4000);
    } catch (err) {
      console.error(err);
    }
  };

  const handleTest = async (id: number) => {
    try {
      const res = await testSourceConnection(id);
      setTestResult({ id, message: res.message, success: res.connected });
      setTimeout(() => setTestResult(null), 5000);
    } catch (err: any) {
      setTestResult({ id, message: err.message || "Test failed", success: false });
    }
  };

  const openConfig = (src: JobSource) => {
    setConfigSource(src);
    setFeedUrl(src.config_data?.feed_url || '');
    setFreqHours(src.sync_frequency_hours || 6);
  };

  const handleSaveConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!configSource) return;
    try {
      const config: any = {};
      if (feedUrl) config.feed_url = feedUrl;

      await updateSource(configSource.id, {
        sync_frequency_hours: freqHours,
        config_data: config,
        connection_status: 'operational'
      });
      setConfigSource(null);
      loadData();
    } catch (err) {
      console.error(err);
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'operational':
      case 'connected':
      case 'working':
        return <span className="inline-flex items-center rounded border border-emerald-400/25 bg-emerald-400/[0.06] px-2 py-0.5 text-[10px] font-medium text-emerald-300">Operational</span>;
      case 'partially_operational':
      case 'partially_working':
        return <span className="inline-flex items-center rounded border border-amber-400/25 bg-amber-400/[0.06] px-2 py-0.5 text-[10px] font-medium text-amber-300">Partial</span>;
      case 'rate_limited':
        return <span className="inline-flex items-center rounded border border-amber-400/25 bg-amber-400/[0.06] px-2 py-0.5 text-[10px] font-medium text-amber-300">Rate Limited</span>;
      case 'failed':
        return <span className="inline-flex items-center rounded border border-rose-400/25 bg-rose-400/[0.06] px-2 py-0.5 text-[10px] font-medium text-rose-300">Failed</span>;
      case 'not_configured':
      case 'needs_configuration':
        return <span className="inline-flex items-center rounded border border-white/[0.10] bg-white/[0.03] px-2 py-0.5 text-[10px] font-medium text-slate-400">Needs Setup</span>;
      case 'unsupported':
      case 'manual_import_only':
      case 'blocked':
        return <span className="inline-flex items-center rounded border border-sky-400/25 bg-sky-400/[0.06] px-2 py-0.5 text-[10px] font-medium text-sky-300">Manual Import</span>;
      default:
        return <span className="inline-flex items-center rounded border border-white/[0.10] bg-white/[0.03] px-2 py-0.5 text-[10px] font-medium text-slate-400">{status}</span>;
    }
  };

  return (
    <div className="space-y-6">
        {!embedded && (
        <PageHeader
          eyebrow="Sourcing"
          title="Job sources"
          description="Aggregating legitimate public ATS boards, APIs, and student portals. India portals with bot management are supported via verified manual import workflows."
          actions={
            <>
              {/* Scheduler Status Toggle */}
              <button
                onClick={handleToggleScheduler}
                className={`inline-flex min-h-[32px] items-center gap-1.5 rounded-lg px-2.5 text-[12px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60 ${
                  schedulerEnabled 
                    ? 'border border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300 hover:bg-emerald-400/[0.10]'
                    : 'border border-white/[0.10] bg-white/[0.03] text-slate-300 hover:border-white/[0.16] hover:bg-white/[0.06]'
                }`}
                title="Toggle background synchronization scheduler"
              >
                {schedulerEnabled ? <Play className="h-3.5 w-3.5" /> : <Pause className="h-3.5 w-3.5" />}
                <span>Scheduler: {schedulerEnabled ? 'Active (6h)' : 'Paused'}</span>
              </button>

              {/* Retry Failed */}
              <button
                onClick={handleRetryFailed}
                disabled={retryingFailed}
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <RefreshCcw className={`h-3.5 w-3.5 ${retryingFailed ? 'animate-spin' : ''}`} />
                <span>Retry Failed</span>
              </button>

              {/* Sync All */}
              <button
                onClick={handleSyncAll}
                disabled={syncingAll}
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <RotateCw className={`h-3.5 w-3.5 ${syncingAll ? 'animate-spin' : ''}`} />
                <span>{syncingAll ? 'Syncing...' : 'Sync All Sources'}</span>
              </button>

              {/* View Logs Toggle */}
              <button
                onClick={() => setShowLogs(!showLogs)}
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <FileText className="h-3.5 w-3.5 text-slate-400" />
                <span>{showLogs ? 'Hide Logs' : 'Sync Logs'}</span>
              </button>
            </>
          }
        />
      )}

      {/* Global Notification Banner */}
      {bannerMsg && (
        <div className={`p-3 rounded-xl text-xs flex items-center gap-2 border ${
          bannerMsg.type === 'success' 
            ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
            : bannerMsg.type === 'error'
            ? 'border-rose-400/25 bg-rose-400/[0.06] text-rose-300'
            : 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300'
        }`}>
          <Info className="h-3.5 w-3.5 shrink-0" />
          <span>{bannerMsg.text}</span>
        </div>
      )}

      {/* Sync Execution History Drawer */}
      {showLogs && (
        <div className="p-4 sm:p-5 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">Synchronization Execution History</h3>
            <span className="text-[11px] text-slate-500">{logs.length} recent operations</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300">
              <thead className="border-b border-white/[0.07] text-[10px] font-medium text-slate-500">
                <tr>
                  <th className="py-2 font-medium">Source</th>
                  <th className="py-2 font-medium">Started</th>
                  <th className="py-2 font-medium">Duration</th>
                  <th className="py-2 font-medium">Retrieved</th>
                  <th className="py-2 font-medium">New</th>
                  <th className="py-2 font-medium">Duplicates Merged</th>
                  <th className="py-2 font-medium">Relevant (≥70%)</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/[0.05]">
                {logs.map(log => (
                  <tr key={log.id} className="hover:bg-white/[0.02]">
                    <td className="py-2.5 font-semibold text-[var(--color-ink)]">{log.source_name}</td>
                    <td className="py-2.5 text-slate-400">
                      {new Date(log.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </td>
                    <td className="py-2.5 font-mono text-slate-400">
                      {log.duration_seconds ? `${log.duration_seconds}s` : '—'}
                    </td>
                    <td className="py-2.5 font-mono">{log.retrieved_count}</td>
                    <td className="py-2.5 font-mono text-emerald-400 font-bold">{log.new_count}</td>
                    <td className="py-2.5 font-mono text-slate-300">{log.duplicate_count}</td>
                    <td className="py-2.5 font-mono text-slate-300">{log.relevant_count}</td>
                    <td className="py-2.5">
                      <span className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-medium ${
                        log.status === 'success'
                          ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                          : 'border-rose-400/25 bg-rose-400/[0.06] text-rose-300'
                      }`}>
                        {log.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Integration Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {sources.map(src => {
          const isUnsupported = src.connection_status === 'unsupported' || src.connection_status === 'manual_import_only';
          return (
            <div
              key={src.id}
              className="p-4 sm:p-5 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] flex flex-col justify-between"
            >
              <div>
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-[13px] font-semibold text-[var(--color-ink)]">{src.name}</h3>
                    <span className="text-[11px] text-slate-500 capitalize">{src.source_type} • {src.integration_method}</span>
                  </div>
                  {getStatusBadge(src.connection_status)}
                </div>

                {/* Status details */}
                <div className="mt-4 space-y-1.5 text-xs text-slate-300">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">Sync Frequency:</span>
                    <span className="text-slate-300">Every {src.sync_frequency_hours} hours</span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">Total Opportunities:</span>
                    <span className="font-bold text-emerald-400">
                      <CountUp to={src.total_jobs_discovered} duration={0.8} />
                    </span>
                  </div>
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-slate-500">Last Synced:</span>
                    <span className="text-slate-300">
                      {src.last_sync_at ? new Date(src.last_sync_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'Never'}
                      {src.last_duration_seconds ? ` (${src.last_duration_seconds}s)` : ''}
                    </span>
                  </div>
                </div>

                {/* Technical Diagnostic Note for Unsupported Platforms */}
                {isUnsupported && src.last_error_message && (
                  <div className="mt-3 p-2 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] text-[11px] text-slate-400 leading-snug">
                    <span className="text-slate-300 font-medium">Compliance Note:</span> {src.last_error_message}
                  </div>
                )}

                {/* In-card test message banner if active */}
                {testResult && testResult.id === src.id && (
                  <div className={`mt-3 p-2 rounded-lg text-xs leading-snug border ${
                    testResult.success 
                      ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                      : 'border-rose-400/25 bg-rose-400/[0.06] text-rose-300'
                  }`}>
                    {testResult.message}
                  </div>
                )}
              </div>

              {/* Actions Bar */}
              <div className="mt-4 pt-3 border-t border-white/[0.07] flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => openConfig(src)}
                    className="inline-flex h-[30px] w-[30px] items-center justify-center rounded-lg border border-white/[0.10] bg-white/[0.03] text-slate-400 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                    title="Configure source parameters"
                  >
                    <Sliders className="h-3.5 w-3.5" />
                  </button>

                  <button
                    onClick={() => handleTest(src.id)}
                    className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                  >
                    Test
                  </button>
                </div>

                {!isUnsupported ? (
                  <button
                    onClick={() => handleSync(src.id)}
                    disabled={syncingId === src.id}
                    className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[11px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                  >
                    <RotateCw className={`h-3.5 w-3.5 ${syncingId === src.id ? 'animate-spin' : ''}`} />
                    <span>{syncingId === src.id ? 'Syncing...' : 'Sync Now'}</span>
                  </button>
                ) : (
                  <span className="text-[11px] text-slate-500 italic">URL & Alert paste only</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Configure Source Modal */}
      {configSource && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-xl border border-white/[0.07] bg-[var(--color-paper)] p-6">
            <h3 className="text-[15px] font-semibold text-[var(--color-ink)] mb-1">Configure {configSource.name}</h3>
            <p className="text-[12px] text-slate-500 mb-4">Set credentials and synchronization intervals securely.</p>

            <form onSubmit={handleSaveConfig} className="space-y-3.5 text-xs">
              {configSource.name.toLowerCase().includes('rss') && (
                <div>
                  <label className="field-label mb-1 block">Custom RSS / Atom Feed URL</label>
                  <input
                    type="url"
                    placeholder="https://feed.company.com/jobs.xml"
                    value={feedUrl}
                    onChange={e => setFeedUrl(e.target.value)}
                    className="input-base"
                  />
                </div>
              )}

              <div>
                <label className="field-label mb-1 block">Sync Frequency (Hours)</label>
                <select
                  value={freqHours}
                  onChange={e => setFreqHours(Number(e.target.value))}
                  className="input-base"
                >
                  <option value={3}>Every 3 Hours</option>
                  <option value={6}>Every 6 Hours (Recommended)</option>
                  <option value={12}>Every 12 Hours</option>
                  <option value={24}>Every 24 Hours</option>
                </select>
              </div>

              <div className="pt-3 flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setConfigSource(null)}
                  className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg bg-emerald-400 px-3 text-[12px] font-medium text-[var(--color-accent-ink)] transition-colors hover:bg-emerald-300 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
                >
                  Save Configuration
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
