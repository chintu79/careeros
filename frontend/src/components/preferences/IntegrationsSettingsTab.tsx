import React, { useState, useEffect } from 'react';
import {
  Mail,
  Calendar,
  ShieldCheck,
  RotateCw,
  Trash2,
  Sparkles,
  Info,
  Plus
} from 'lucide-react';
import { IntegrationsStatusResponse, ProviderStatusItem } from '../../types';
import {
  fetchIntegrationsStatus,
  fetchGoogleAuthUrl,
  fetchMicrosoftAuthUrl,
  syncIntegrationConnection,
  disconnectIntegrationConnection,
  seedSandboxIntegrations
} from '../../services/api';
import { PageHeader } from '../ui/PageHeader';
import { AIDiagnosticsCard } from './AIDiagnosticsCard';

export const IntegrationsSettingsTab: React.FC<{ embedded?: boolean }> = ({ embedded = false }) => {
  const [data, setData] = useState<IntegrationsStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [banner, setBanner] = useState<{ type: 'success' | 'error' | 'info'; message: string } | null>(null);

  const loadStatus = async () => {
    setLoading(true);
    try {
      const res = await fetchIntegrationsStatus();
      setData(res);
    } catch (err: any) {
      console.error(err);
      setBanner({ type: 'error', message: err.message || 'Failed to fetch integrations status' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStatus();
  }, []);

  const handleConnect = async (provider: 'google' | 'microsoft') => {
    setActionLoading(`connect_${provider}`);
    setBanner(null);
    try {
      const authData = provider === 'google' ? await fetchGoogleAuthUrl() : await fetchMicrosoftAuthUrl();
      if (!authData.is_configured) {
        setBanner({
          type: 'info',
          message: authData.message || `${provider.toUpperCase()} credentials not configured in backend environment. You can use Sandbox Mode to test full functionality!`
        });
      } else if (authData.auth_url) {
        window.location.href = authData.auth_url;
      }
    } catch (err: any) {
      setBanner({ type: 'error', message: err.message || `Failed to initiate ${provider} connection` });
    } finally {
      setActionLoading(null);
    }
  };

  const handleSync = async (connectionId: number, providerName: string) => {
    setActionLoading(`sync_${connectionId}`);
    setBanner(null);
    try {
      const res = await syncIntegrationConnection(connectionId);
      setBanner({
        type: 'success',
        message: `Synced ${providerName}: ${res.emails_synced} emails and ${res.calendar_events_synced} calendar events processed.`
      });
      loadStatus();
    } catch (err: any) {
      setBanner({ type: 'error', message: err.message || 'Sync failed' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleDisconnect = async (connectionId: number, providerName: string) => {
    if (!window.confirm(`Are you sure you want to disconnect ${providerName}? Access tokens will be revoked.`)) return;
    setActionLoading(`disconnect_${connectionId}`);
    setBanner(null);
    try {
      await disconnectIntegrationConnection(connectionId);
      setBanner({ type: 'success', message: `${providerName} disconnected successfully.` });
      loadStatus();
    } catch (err: any) {
      setBanner({ type: 'error', message: err.message || 'Disconnect failed' });
    } finally {
      setActionLoading(null);
    }
  };

  const handleSeedSandbox = async () => {
    setActionLoading('seed_sandbox');
    setBanner(null);
    try {
      const res = await seedSandboxIntegrations();
      setBanner({
        type: 'success',
        message: `${res.message} (4 career communication emails and 2 calendar events populated).`
      });
      loadStatus();
    } catch (err: any) {
      setBanner({ type: 'error', message: err.message || 'Failed to seed sandbox data' });
    } finally {
      setActionLoading(null);
    }
  };

  const renderProviderCard = (providerKey: 'google' | 'microsoft', info?: ProviderStatusItem) => {
    if (!info) return null;
    const isConnected = info.status === 'connected';
    const isGoogle = providerKey === 'google';

    return (
      <div className="p-4 sm:p-5 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] flex flex-col justify-between">
        <div>
          {/* Card Header */}
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-center gap-2.5">
              {isGoogle ? <Mail className="h-3.5 w-3.5 text-slate-400" /> : <Calendar className="h-3.5 w-3.5 text-slate-400" />}
              <div>
                <h3 className="text-[13px] font-semibold text-[var(--color-ink)] flex items-center gap-2">
                  <span>{info.name}</span>
                </h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  {isGoogle ? 'Gmail & Google Calendar' : 'Outlook Mail & Calendar'}
                </p>
              </div>
            </div>

            {/* Connection Status Badge */}
            <span
              className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] font-medium ${
                isConnected
                  ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
                  : info.is_configured
                  ? 'border-white/[0.10] bg-white/[0.03] text-slate-400'
                  : 'border-amber-400/25 bg-amber-400/[0.06] text-amber-300'
              }`}
            >
              {isConnected ? 'Connected' : info.is_configured ? 'Ready to Connect' : 'Setup Required'}
            </span>
          </div>

          {/* Account Details if Connected */}
          {isConnected && info.connection && (
            <div className="mt-4 p-3 rounded-lg border border-white/[0.06] bg-[var(--color-paper-2)] space-y-1.5 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Account:</span>
                <span className="text-[var(--color-ink)] font-medium">{info.connection.account_email}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Last Synchronized:</span>
                <span className="text-slate-300 text-[11px]">
                  {info.connection.last_sync_at
                    ? new Date(info.connection.last_sync_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                    : 'Never'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-slate-500 text-[11px]">Token Storage:</span>
                <span className="text-emerald-300 font-mono text-[10px] flex items-center gap-1">
                  <ShieldCheck className="h-3 w-3" />
                  <span>Fernet Encrypted (AES-128-CBC)</span>
                </span>
              </div>
            </div>
          )}

          {/* Minimum Scopes Disclosed */}
          <div className="mt-4 space-y-1.5">
            <span className="text-[10px] font-medium text-slate-500">
              Requested Permissions (Minimum Scopes):
            </span>
            <div className="flex flex-wrap gap-1.5">
              {info.minimum_scopes.map((scope, idx) => {
                const shortName = scope.split('/').pop() || scope;
                return (
                  <span
                    key={idx}
                    className="rounded border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 text-[10px] text-slate-300 font-mono"
                  >
                    {shortName}
                  </span>
                );
              })}
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="mt-5 pt-3 border-t border-white/[0.07] flex items-center justify-between">
          {isConnected && info.connection ? (
            <>
              <button
                type="button"
                onClick={() => handleDisconnect(info.connection!.id, info.name)}
                disabled={actionLoading === `disconnect_${info.connection.id}`}
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-rose-400/25 bg-rose-400/[0.06] px-2.5 text-[12px] font-medium text-rose-300 transition-colors hover:bg-rose-400/[0.10] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <Trash2 className="h-3.5 w-3.5" />
                <span>Disconnect</span>
              </button>

              <button
                type="button"
                onClick={() => handleSync(info.connection!.id, info.name)}
                disabled={actionLoading === `sync_${info.connection.id}`}
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-3 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              >
                <RotateCw className={`h-3.5 w-3.5 ${actionLoading === `sync_${info.connection.id}` ? 'animate-spin' : ''}`} />
                <span>Sync Now</span>
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => handleConnect(providerKey)}
              disabled={actionLoading === `connect_${providerKey}`}
              className="inline-flex min-h-[32px] w-full items-center justify-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-3 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
            >
              <Plus className="h-3.5 w-3.5" />
              <span>Connect {info.name}</span>
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
        {!embedded && (
        <PageHeader
          eyebrow="Settings"
          title="Connected accounts"
          description="Connect your communication and schedule to automatically detect recruiter updates, interview invites, and coding test deadlines."
          actions={
            /* Sandbox Seed Button for Instant Evaluation */
            <button
              type="button"
              onClick={handleSeedSandbox}
              disabled={actionLoading === 'seed_sandbox'}
              className="inline-flex min-h-[32px] items-center gap-1.5 rounded-lg border border-white/[0.10] bg-white/[0.03] px-2.5 text-[12px] font-medium text-slate-300 transition-colors hover:border-white/[0.16] hover:bg-white/[0.06] disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400/60"
              title="Seed realistic career emails and calendar events without needing Google or Microsoft credentials"
            >
              <Sparkles className="h-3.5 w-3.5 text-slate-400" />
              <span>{actionLoading === 'seed_sandbox' ? 'Seeding...' : 'Seed Sandbox Fixtures'}</span>
            </button>
          }
        />
      )}

      {/* Notification Banner */}
      {banner && (
        <div
          className={`p-3 rounded-xl text-xs flex items-center gap-2 border ${
            banner.type === 'success'
              ? 'border-emerald-400/25 bg-emerald-400/[0.06] text-emerald-300'
              : banner.type === 'error'
              ? 'border-rose-400/25 bg-rose-400/[0.06] text-rose-300'
              : 'border-sky-400/25 bg-sky-400/[0.06] text-sky-300'
          }`}
        >
          <Info className="h-3.5 w-3.5 shrink-0" />
          <span>{banner.message}</span>
        </div>
      )}

      {/* Security & Privacy Guarantee */}
      <div className="p-4 rounded-xl border border-white/[0.07] bg-[var(--color-paper)] text-xs text-slate-300 space-y-1">
        <div className="flex items-center gap-2 text-emerald-300 font-semibold">
          <ShieldCheck className="h-3.5 w-3.5" />
          <span>Zero-Password, Encrypted Integration Guarantee</span>
        </div>
        <p className="text-[11px] text-slate-500 leading-relaxed">
          CareerOS connects exclusively via official OAuth 2.0 authorization code flows with read-only scopes.
          Tokens are encrypted with Fernet AES-128-CBC at rest. No passwords are ever stored. No personal emails are processed.
          Consequential application tracker status changes require explicit user approval.
        </p>
      </div>

      {/* Provider Cards */}
      {loading ? (
        <div className="p-8 text-center text-xs text-slate-500 flex items-center justify-center gap-2">
          <RotateCw className="h-3.5 w-3.5 animate-spin text-slate-400" />
          <span>Loading integration statuses...</span>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {renderProviderCard('google', data?.providers.google)}
          {renderProviderCard('microsoft', data?.providers.microsoft)}
        </div>
      )}

      {/* AI Provider Infrastructure & Health Diagnostics */}
      <div className="pt-4 border-t border-white/[0.07]">
        <AIDiagnosticsCard />
      </div>
    </div>
  );
};
