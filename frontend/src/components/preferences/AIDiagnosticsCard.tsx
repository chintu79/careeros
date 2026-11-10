import React, { useState, useEffect } from 'react';
import {
  Cpu,
  Cloud,
  HardDrive,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  RotateCw,
  Activity,
  Layers,
  Server
} from 'lucide-react';
import { AIHealthStatusResponse, TestProviderResponse } from '../../types';
import { fetchAIHealthStatus, testAIProvider } from '../../services/api';

export const AIDiagnosticsCard: React.FC = () => {
  const [data, setData] = useState<AIHealthStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [testingGroq, setTestingGroq] = useState<boolean>(false);
  const [testingOllama, setTestingOllama] = useState<boolean>(false);
  const [groqTestResult, setGroqTestResult] = useState<TestProviderResponse | null>(null);
  const [ollamaTestResult, setOllamaTestResult] = useState<TestProviderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const loadHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchAIHealthStatus();
      setData(res);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Failed to load AI health status');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHealth();
  }, []);

  const handleTestGroq = async () => {
    setTestingGroq(true);
    setGroqTestResult(null);
    try {
      const res = await testAIProvider('groq');
      setGroqTestResult(res);
      // Refresh telemetry
      const health = await fetchAIHealthStatus();
      setData(health);
    } catch (err: any) {
      setGroqTestResult({
        provider: 'groq',
        status: 'error',
        latency_ms: 0,
        message: err.message || 'Groq connectivity test failed'
      });
    } finally {
      setTestingGroq(false);
    }
  };

  const handleTestOllama = async () => {
    setTestingOllama(true);
    setOllamaTestResult(null);
    try {
      const res = await testAIProvider('ollama');
      setOllamaTestResult(res);
      // Refresh telemetry
      const health = await fetchAIHealthStatus();
      setData(health);
    } catch (err: any) {
      setOllamaTestResult({
        provider: 'ollama',
        status: 'error',
        latency_ms: 0,
        message: err.message || 'Ollama connectivity test failed'
      });
    } finally {
      setTestingOllama(false);
    }
  };

  const groq = data?.providers.groq;
  const ollama = data?.providers.ollama;

  return (
    <div className="p-4 sm:p-5 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Cpu className="h-3.5 w-3.5 text-slate-400" />
            <h2 className="text-[13px] font-semibold text-[var(--color-ink)]">Centralized AI Provider Infrastructure</h2>
            {data && (
              <span
                className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-medium ${
                  data.status === 'operational'
                    ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                    : 'border-amber-400/25 bg-amber-400/[0.06] text-amber-300'
                }`}
              >
                {data.status}
              </span>
            )}
          </div>
          <p className="text-[12px] leading-relaxed text-slate-500">
            Dual-tier task routing architecture: Groq cloud reasoning for complex artifacts, local Ollama for everyday private chat.
          </p>
        </div>

        <button
          type="button"
          onClick={loadHealth}
          disabled={loading}
          className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
        >
          <RotateCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Status</span>
        </button>
      </div>

      {error && (
        <div className="p-3 rounded-xl border border-rose-400/25 bg-rose-400/[0.06] text-rose-300 text-xs flex items-center gap-2">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Strict Privacy Guarantee Banner */}
      <div className="p-4 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] flex items-start gap-3">
        <ShieldCheck className="h-3.5 w-3.5 text-emerald-300 shrink-0 mt-0.5" />
        <div className="space-y-1 text-xs">
          <h3 className="text-[13px] font-semibold text-[var(--color-ink)] flex items-center gap-1.5">
            <span>Strict Privacy & Boundary Isolation Guarantee</span>
          </h3>
          <p className="text-slate-500 text-[11px] leading-relaxed">
            {data?.privacy_guarantee ||
              'Zero cross-provider leakage. Local chat is strictly isolated from cloud APIs.'}
            {' '}Everyday AI assistant messages and journal reflections run entirely on your local machine via Ollama and are NEVER sent to cloud providers.
            Complex generative tasks (resumes, interview evaluations) use Groq exclusively.
          </p>
        </div>
      </div>

      {/* Provider Status Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Groq Provider Card */}
        <div className="p-4 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <Cloud className="h-3.5 w-3.5 text-slate-400" />
                <div>
                  <h3 className="text-[13px] font-semibold text-[var(--color-ink)] flex items-center gap-1.5">
                    <span>Groq Cloud API</span>
                  </h3>
                  <span className="text-[10px] text-slate-500">Complex Reasoning & Structured Output</span>
                </div>
              </div>
              <span
                className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-medium ${
                  groq?.configured
                    ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                    : 'border-amber-400/25 bg-amber-400/[0.06] text-amber-300'
                }`}
              >
                {groq?.configured ? 'Active' : 'Unconfigured'}
              </span>
            </div>

            <div className="p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Configured Model:</span>
                <span className="font-mono text-slate-300 text-[11px] font-semibold">
                  {groq?.model || 'llama-3.3-70b-versatile'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Latency Target:</span>
                <span className="text-slate-300 text-[11px]">Sub-second LPUs (&lt;800ms)</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Output Format:</span>
                <span className="text-slate-300 text-[11px]">Pydantic-validated JSON Schema</span>
              </div>
            </div>

            {/* Provider Status Message */}
            <p className="text-[11px] text-slate-500 leading-relaxed">
              {groq?.status_message || (groq?.configured ? 'Connected and operational.' : 'GROQ_API_KEY is not set in backend/.env.')}
            </p>

            {/* Telemetry Stats */}
            {groq?.telemetry && (
              <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/[0.07] text-center">
                <div className="p-2 rounded-lg border border-white/[0.06] bg-white/[0.02]">
                  <span className="block text-[10px] text-slate-500">Total Calls</span>
                  <span className="text-xs font-bold text-[var(--color-ink)] font-mono">{groq.telemetry.total_requests}</span>
                </div>
                <div className="p-2 rounded-lg border border-white/[0.06] bg-white/[0.02]">
                  <span className="block text-[10px] text-slate-500">Avg Latency</span>
                  <span className="text-xs font-bold text-emerald-400 font-mono">
                    {groq.telemetry.avg_latency_ms ? `${groq.telemetry.avg_latency_ms}ms` : '--'}
                  </span>
                </div>
                <div className="p-2 rounded-lg border border-white/[0.06] bg-white/[0.02]">
                  <span className="block text-[10px] text-slate-500">Tokens</span>
                  <span className="text-xs font-bold text-slate-300 font-mono">{groq.telemetry.total_tokens}</span>
                </div>
              </div>
            )}

            {/* Test result display */}
            {groqTestResult && (
              <div
                className={`p-2.5 rounded-lg text-xs flex items-center justify-between border ${
                  groqTestResult.status === 'online'
                    ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                    : 'border-amber-400/25 bg-amber-400/[0.06] text-amber-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  {groqTestResult.status === 'online' ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  )}
                  <span className="text-[11px]">{groqTestResult.message}</span>
                </div>
                {groqTestResult.latency_ms > 0 && (
                  <span className="font-mono text-[10px] text-emerald-400 font-bold shrink-0 ml-2">
                    {groqTestResult.latency_ms}ms
                  </span>
                )}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleTestGroq}
            disabled={testingGroq}
            className="w-full inline-flex min-h-[32px] items-center justify-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
          >
            <Activity className={`h-3.5 w-3.5 ${testingGroq ? 'animate-spin' : ''}`} />
            <span>{testingGroq ? 'Testing Groq API...' : 'Test Groq Connectivity'}</span>
          </button>
        </div>

        {/* Local Ollama Provider Card */}
        <div className="p-4 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <HardDrive className="h-3.5 w-3.5 text-slate-400" />
                <div>
                  <h3 className="text-[13px] font-semibold text-[var(--color-ink)] flex items-center gap-1.5">
                    <span>Local Ollama Daemon</span>
                  </h3>
                  <span className="text-[10px] text-slate-500">Everyday Chat & Private Interactions</span>
                </div>
              </div>
              <span
                className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-medium ${
                  ollama?.configured
                    ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                    : 'border-rose-400/25 bg-rose-400/[0.06] text-rose-300'
                }`}
              >
                {ollama?.configured ? 'Online' : 'Offline'}
              </span>
            </div>

            <div className="p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] space-y-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Chat Model:</span>
                <span className="font-mono text-slate-300 text-[11px] font-semibold">
                  {ollama?.model || 'llama3.2:latest'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Daemon URL:</span>
                <span className="font-mono text-slate-300 text-[11px]">
                  {ollama?.base_url || 'http://localhost:11434'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Capability:</span>
                <span className="text-slate-300 text-[11px]">Streaming Token Generator, Offline-First</span>
              </div>
            </div>

            {/* Provider Status Message */}
            <p className="text-[11px] text-slate-500 leading-relaxed">
              {ollama?.status_message || (ollama?.configured ? 'Local Ollama service running.' : 'Ollama is unreachable on localhost.')}
            </p>

            {/* Telemetry Stats */}
            {ollama?.telemetry && (
              <div className="grid grid-cols-3 gap-2 pt-1 border-t border-white/[0.07] text-center">
                <div className="p-2 rounded-lg border border-white/[0.06] bg-white/[0.02]">
                  <span className="block text-[10px] text-slate-500">Total Calls</span>
                  <span className="text-xs font-bold text-[var(--color-ink)] font-mono">{ollama.telemetry.total_requests}</span>
                </div>
                <div className="p-2 rounded-lg border border-white/[0.06] bg-white/[0.02]">
                  <span className="block text-[10px] text-slate-500">Avg Latency</span>
                  <span className="text-xs font-bold text-emerald-400 font-mono">
                    {ollama.telemetry.avg_latency_ms ? `${ollama.telemetry.avg_latency_ms}ms` : '--'}
                  </span>
                </div>
                <div className="p-2 rounded-lg border border-white/[0.06] bg-white/[0.02]">
                  <span className="block text-[10px] text-slate-500">Tokens</span>
                  <span className="text-xs font-bold text-slate-300 font-mono">{ollama.telemetry.total_tokens}</span>
                </div>
              </div>
            )}

            {/* Test result display */}
            {ollamaTestResult && (
              <div
                className={`p-2.5 rounded-lg text-xs flex items-center justify-between border ${
                  ollamaTestResult.status === 'online'
                    ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                    : 'border-rose-400/25 bg-rose-400/[0.06] text-rose-300'
                }`}
              >
                <div className="flex items-center gap-2">
                  {ollamaTestResult.status === 'online' ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertTriangle className="h-3.5 w-3.5" />
                  )}
                  <span className="text-[11px]">{ollamaTestResult.message}</span>
                </div>
                {ollamaTestResult.latency_ms > 0 && (
                  <span className="font-mono text-[10px] text-emerald-400 font-bold shrink-0 ml-2">
                    {ollamaTestResult.latency_ms}ms
                  </span>
                )}
              </div>
            )}
          </div>

          <button
            type="button"
            onClick={handleTestOllama}
            disabled={testingOllama}
            className="w-full inline-flex min-h-[32px] items-center justify-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
          >
            <Activity className={`h-3.5 w-3.5 ${testingOllama ? 'animate-spin' : ''}`} />
            <span>{testingOllama ? 'Testing Ollama Service...' : 'Test Ollama Connectivity'}</span>
          </button>
        </div>
      </div>

      {/* Task Routing & Deterministic Policy Matrix */}
      <div className="p-4 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-[13px] font-semibold text-[var(--color-ink)] flex items-center gap-2">
            <Layers className="h-3.5 w-3.5 text-slate-400" />
            <span>Task Routing Policy</span>
          </h3>
          <span className="text-[10px] text-slate-500 font-medium">Automatic Policy Routing</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
          {/* Groq Tasks */}
          <div className="p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] space-y-2">
            <div className="flex items-center gap-1.5 text-slate-300 font-semibold text-[11px]">
              <Cloud className="h-3.5 w-3.5 text-slate-400" />
              <span>Groq Cloud Tasks</span>
            </div>
            <ul className="text-[11px] text-slate-400 space-y-1 list-disc list-inside">
              <li>Resume generation & structuring</li>
              <li>Resume tailoring against JDs</li>
              <li>Job description deep analysis</li>
              <li>Candidate-job compatibility</li>
              <li>Project technical descriptions</li>
              <li>Interview feedback evaluation</li>
              <li>Complex career recommendations</li>
            </ul>
          </div>

          {/* Ollama Tasks */}
          <div className="p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] space-y-2">
            <div className="flex items-center gap-1.5 text-slate-300 font-semibold text-[11px]">
              <HardDrive className="h-3.5 w-3.5 text-slate-400" />
              <span>Local Ollama Tasks</span>
            </div>
            <ul className="text-[11px] text-slate-400 space-y-1 list-disc list-inside">
              <li>AI Assistant chat (Streaming)</li>
              <li>General career advisory Q&A</li>
              <li>Email category classification</li>
              <li>Quick content summarization</li>
              <li>Basic entity extraction</li>
              <li>Journal thought exploration</li>
            </ul>
          </div>

          {/* Deterministic Tasks */}
          <div className="p-3 rounded-lg border border-white/[0.06] bg-white/[0.02] space-y-2">
            <div className="flex items-center gap-1.5 text-slate-300 font-semibold text-[11px]">
              <Server className="h-3.5 w-3.5 text-slate-400" />
              <span>Deterministic Core (0% LLM)</span>
            </div>
            <ul className="text-[11px] text-slate-400 space-y-1 list-disc list-inside">
              <li>Application tracker status transitions</li>
              <li>Job search, filter & pagination</li>
              <li>Date calculations & deadlines</li>
              <li>Duplicate detection & hashing</li>
              <li>Sankey & pipeline metrics</li>
              <li>100% functional when offline</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
