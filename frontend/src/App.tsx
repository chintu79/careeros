import React, { useState, useEffect, useRef } from 'react';
import { Sidebar, AppHeader, MobileDrawer, CommandPalette, KeyboardShortcutsModal } from './components/navigation';
import { SummaryBanner } from './components/discovery/SummaryBanner';
import { OpportunityFeed } from './components/discovery/OpportunityFeed';
import { OpportunityDetailModal } from './components/detail/OpportunityDetailModal';
import { ManualImportModal } from './components/import/ManualImportModal';
import { CompanyDirectoryView } from './components/companies/CompanyDirectoryView';
import { SourcesView } from './components/sources/SourcesView';
import { PreferencesView } from './components/preferences/PreferencesView';
import { ApplicationTrackerView } from './components/applications/ApplicationTrackerView';
import { AnalyticsView } from './components/analytics/AnalyticsView';
import { OverviewView } from './components/overview/OverviewView';
import { ResumeStudioView } from './components/resumes/ResumeStudioView';
import { InterviewJournalView } from './components/interviews/InterviewJournalView';
import { AIChatAssistantView } from './components/chat/AIChatAssistantView';
import { CandidateProfileView } from './components/candidate/CandidateProfileView';
import { CandidateOnboardingView } from './components/onboarding/CandidateOnboardingView';
import { AssistedApplicationModal } from './components/applications/AssistedApplicationModal';
import { GlobalAICommandCenter } from './components/ai/GlobalAICommandCenter';
import { LiveAnnouncerProvider, SkipLink } from './components/a11y';
import { PageHeader } from './components/ui/PageHeader';
import { ToastProvider } from './components/ui/Toast';
import { UnsavedChangesProvider, useNavigationGuard } from './context/unsavedChanges';

import { OpportunityItem, SummaryMetrics, NotificationItem } from './types';
import { 
  fetchOpportunities, 
  fetchSummaryMetrics, 
  toggleSaveOpportunity, 
  dismissOpportunity,
  handoffApplication,
  syncAllSources,
  fetchNotifications,
  markNotificationRead,
  markAllNotificationsRead,
  tailorResume,
  evaluateOpportunityMatch,
  switchCandidate,
  clearAuth,
  getNextRequestEpoch,
  getCurrentRequestEpoch,
  getActiveUserId,
  ensureAuthenticated,
  SessionExpiredError
} from './services/api';

const AppInner: React.FC = () => {
  const requestEpochRef = useRef<number>(0);
  const [navTab, setNavTab] = useState('overview'); // Default to overview
  const guardedNav = useNavigationGuard();
  const go = (tab: string) => guardedNav(() => setNavTab(tab));
  const [oppTab, setOppTab] = useState('recommended'); // recommended, latest, saved, expiring, applied, dismissed
  
  const [activeUserId, setActiveUserId] = useState<number>(() => getActiveUserId());
  const [opportunities, setOpportunities] = useState<OpportunityItem[]>([]);
  const [totalOpps, setTotalOpps] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [totalPages, setTotalPages] = useState(1);
  const [snapshotId, setSnapshotId] = useState<string | null>(null);
  const [nextCursor, setNextCursor] = useState<number | null>(null);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [sessionExpiredNotice, setSessionExpiredNotice] = useState(false);
  const [metrics, setMetrics] = useState<SummaryMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);

  // UI Navigation states
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('careeros_sidebar_collapsed');
      return saved === 'true';
    }
    return false;
  });
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isShortcutsOpen, setIsShortcutsOpen] = useState(false);
  const [isMobileNavOpen, setIsMobileNavOpen] = useState(false);
  const [isAICommandOpen, setIsAICommandOpen] = useState(false);

  // Modals
  const [selectedOppId, setSelectedOppId] = useState<number | null>(null);
  const [showImportModal, setShowImportModal] = useState(false);
  const [assistedOppId, setAssistedOppId] = useState<number | null>(null);

  // Notifications
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);

  // Filter state
  const [filters, setFilters] = useState<any>({
    search: '',
    search_mode: 'hybrid',
    category: '',
    company: '',
    location: '',
    workplace_type: '',
    min_stipend: '',
    source_platform: '',
    eligibility_status: '',
    min_score: 0,
    sort_by: 'match_score',
    sort_order: 'desc'
  });

  const handleToggleCollapse = () => {
    setIsSidebarCollapsed(prev => {
      const next = !prev;
      if (typeof window !== 'undefined') {
        localStorage.setItem('careeros_sidebar_collapsed', String(next));
      }
      return next;
    });
  };

  // Keyboard shortcut listener
  useEffect(() => {
    let lastKey = '';
    let lastKeyTime = 0;

    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const isEditing = 
        target?.tagName === 'INPUT' || 
        target?.tagName === 'TEXTAREA' || 
        target?.tagName === 'SELECT' || 
        target?.isContentEditable;

      // Cmd+K or Ctrl+K for command palette
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setIsCommandPaletteOpen(prev => !prev);
        return;
      }

      // Cmd+J or Ctrl+J for global AI command center
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') {
        e.preventDefault();
        setIsAICommandOpen(prev => !prev);
        return;
      }

      // If user is editing text in an input field, do not trigger single-key shortcuts
      if (isEditing) return;

      // '?' for cheatsheet
      if (e.key === '?') {
        e.preventDefault();
        setIsShortcutsOpen(prev => !prev);
        return;
      }

      // '[' to toggle sidebar collapse
      if (e.key === '[') {
        e.preventDefault();
        handleToggleCollapse();
        return;
      }

      // 'g' key sequence handler (e.g. g o, g d, g a, g r, g i, g c)
      const now = Date.now();
      if (e.key.toLowerCase() === 'g') {
        lastKey = 'g';
        lastKeyTime = now;
        return;
      }

      if (lastKey === 'g' && now - lastKeyTime < 1000) {
        lastKey = '';
        switch (e.key.toLowerCase()) {
          case 'o':
            e.preventDefault();
            go('overview');
            break;
          case 'd':
            e.preventDefault();
            go('discover');
            break;
          case 'a':
          case 't':
            e.preventDefault();
            go('tracker');
            break;
          case 'r':
            e.preventDefault();
            go('resumes');
            break;
          case 'i':
            e.preventDefault();
            go('interviews');
            break;
          case 'n':
            e.preventDefault();
            go('analytics');
            break;
          case 'c':
            e.preventDefault();
            go('chat');
            break;
          case 'p':
            e.preventDefault();
            go('profile');
            break;
          case 's':
            e.preventDefault();
            go('preferences');
            break;
          default:
            break;
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  useEffect(() => {
    ensureAuthenticated(activeUserId).catch(err => {
      console.warn("Auth initialization:", err);
    });
  }, [activeUserId]);

  const loadData = async (
    resetSessionOrPage: boolean | number = true,
    maybePageOrSize?: number,
    maybePageSize?: number
  ) => {
    let resetSession = true;
    let currentPage = page;
    let currentPageSize = pageSize;

    if (typeof resetSessionOrPage === 'boolean') {
      resetSession = resetSessionOrPage;
      if (typeof maybePageOrSize === 'number') {
        currentPage = maybePageOrSize;
      }
      if (typeof maybePageSize === 'number') {
        currentPageSize = maybePageSize;
      }
    } else if (typeof resetSessionOrPage === 'number') {
      resetSession = false;
      currentPage = resetSessionOrPage;
      if (typeof maybePageOrSize === 'number') {
        currentPageSize = maybePageOrSize;
      }
    }

    const reqEpoch = getNextRequestEpoch();
    requestEpochRef.current = reqEpoch;

    setLoading(true);
    if (resetSession) {
      setSnapshotId(null);
      setNextCursor(null);
    }
    try {
      const res = await fetchOpportunities({
        tab: oppTab,
        page: currentPage,
        page_size: currentPageSize,
        snapshot_id: resetSession ? undefined : (snapshotId || undefined),
        ...filters
      });
      if (requestEpochRef.current !== reqEpoch) return;
      setOpportunities(res.items || []);
      setTotalOpps(res.total || 0);
      setTotalPages(res.total_pages || 1);
      setSnapshotId(res.snapshot_id || null);
      setNextCursor(res.next_cursor || null);
      setHasMore(Boolean(res.has_more));
    } catch (err: any) {
      if (requestEpochRef.current !== reqEpoch) return;
      if (err instanceof SessionExpiredError || err?.restartRequired || err?.code === 'PAGINATION_SESSION_EXPIRED') {
        setSessionExpiredNotice(true);
        setSnapshotId(null);
        setNextCursor(null);
        try {
          const freshRes = await fetchOpportunities({
            tab: oppTab,
            page: 1,
            page_size: currentPageSize,
            ...filters
          });
          if (requestEpochRef.current !== reqEpoch) return;
          setOpportunities(freshRes.items || []);
          setTotalOpps(freshRes.total || 0);
          setTotalPages(freshRes.total_pages || 1);
          setSnapshotId(freshRes.snapshot_id || null);
          setNextCursor(freshRes.next_cursor || null);
          setHasMore(Boolean(freshRes.has_more));
        } catch (freshErr) {
          console.error("Session refresh failed:", freshErr);
        }
      } else {
        console.error("Discovery fetch failed:", err);
      }
    } finally {
      if (requestEpochRef.current === reqEpoch) {
        setLoading(false);
      }
    }

    fetchSummaryMetrics()
      .then(m => {
        if (requestEpochRef.current === reqEpoch) {
          setMetrics(m);
        }
      })
      .catch(err => console.error(err));
  };

  const handleLoadMore = async () => {
    if (loadingMore || !hasMore || nextCursor === null) return;
    setLoadingMore(true);
    const reqEpoch = requestEpochRef.current;
    try {
      const res = await fetchOpportunities({
        tab: oppTab,
        cursor: nextCursor,
        snapshot_id: snapshotId || undefined,
        limit: pageSize,
        ...filters
      });

      if (requestEpochRef.current !== reqEpoch) return;

      setOpportunities(prev => {
        const existingIds = new Set(prev.map(o => o.id));
        const newItems = (res.items || []).filter(o => !existingIds.has(o.id));
        return [...prev, ...newItems];
      });

      setSnapshotId(res.snapshot_id || snapshotId);
      setNextCursor(res.next_cursor || null);
      setHasMore(Boolean(res.has_more));
    } catch (err: any) {
      if (requestEpochRef.current !== reqEpoch) return;
      if (err instanceof SessionExpiredError || err?.restartRequired) {
        setSessionExpiredNotice(true);
        setSnapshotId(null);
        setNextCursor(null);
        loadData(true);
      } else {
        console.error("Load more opportunities failed:", err);
      }
    } finally {
      if (requestEpochRef.current === reqEpoch) {
        setLoadingMore(false);
      }
    }
  };

  const handleCalculateMatch = async (id: number) => {
    try {
      const res = await evaluateOpportunityMatch(id, true);
      setOpportunities(prev => prev.map(opp => {
        if (opp.id === id) {
          const evalScore = res.profile_match_score;
          return {
            ...opp,
            match_score: evalScore,
            eligibility_status: res.eligibility_status,
            category_scores: res.category_scores,
            category_weights: res.category_weights,
            skill_gaps: res.skill_gaps,
            requirement_matches: res.requirement_matches,
            scoring_explanation: res.scoring_explanation,
            ranking_reasons: {
              primary_factor: "evaluated_candidate_match",
              evaluation_state: evalScore >= 70 ? "evaluated_high" : evalScore >= 50 ? "evaluated_moderate" : "evaluated_low",
              match_score: evalScore,
              is_evaluated: true,
              is_stale: false,
              eligibility_status: res.eligibility_status,
              highlights: opp.why_it_matches || []
            },
            match_freshness: {
              calculated_at: res.calculated_at,
              is_stale: false,
              is_cached: false
            }
          };
        }
        return opp;
      }));
    } catch (err) {
      console.error("Match calculation failed:", err);
    }
  };

  const handleSwitchCandidate = async (newUserId: number) => {
    try {
      const nextEpoch = getNextRequestEpoch();
      requestEpochRef.current = nextEpoch;
      setOpportunities([]);
      setTotalOpps(0);
      setSnapshotId(null);
      setNextCursor(null);
      setHasMore(false);
      setSessionExpiredNotice(false);
      setNotifications([]);
      setUnreadCount(0);
      setPage(1);

      await switchCandidate(newUserId);
      setActiveUserId(newUserId);
      loadData(true, 1, pageSize);
      loadNotifs();
    } catch (err) {
      console.error("Failed to switch candidate context:", err);
    }
  };

  const handleLogout = () => {
    clearAuth();
    const nextEpoch = getNextRequestEpoch();
    requestEpochRef.current = nextEpoch;
    setActiveUserId(1);
    setOpportunities([]);
    setTotalOpps(0);
    setSnapshotId(null);
    setNextCursor(null);
    setHasMore(false);
    setNotifications([]);
    setUnreadCount(0);
    go('overview');
  };

  const loadNotifs = () => {
    fetchNotifications()
      .then(res => {
        setNotifications(res.items || []);
        setUnreadCount(res.unread_count || 0);
      })
      .catch(err => console.error(err));
  };

  useEffect(() => {
    if (navTab === 'discover') {
      loadData(true, page, pageSize);
    }
  }, [navTab, oppTab, filters, page, pageSize, activeUserId]);

  useEffect(() => {
    loadNotifs();
    const interval = setInterval(loadNotifs, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleSyncAll = async () => {
    setIsSyncing(true);
    try {
      await syncAllSources();
      loadData(page, pageSize);
      loadNotifs();
    } catch (err) {
      console.error(err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleToggleSave = async (id: number) => {
    try {
      const res = await toggleSaveOpportunity(id);
      setOpportunities(opportunities.map(o => o.id === id ? { ...o, is_saved: res.is_saved } : o));
      fetchSummaryMetrics().then(m => setMetrics(m));
    } catch (err) {
      console.error(err);
    }
  };

  const handleDismiss = async (id: number) => {
    try {
      await dismissOpportunity(id);
      setOpportunities(opportunities.filter(o => o.id !== id));
      fetchSummaryMetrics().then(m => setMetrics(m));
    } catch (err) {
      console.error(err);
    }
  };

  const handleHandoffTracker = async (id: number) => {
    try {
      await handoffApplication({ opportunity_id: id });
      setOpportunities(opportunities.map(o => o.id === id ? { ...o, is_applied: true } : o));
      loadNotifs();
    } catch (err) {
      console.error(err);
    }
  };

  const handleTailorResume = async (oppId: number) => {
    try {
      await tailorResume(oppId);
      go('resumes');
    } catch (err) {
      console.error(err);
      go('resumes');
    }
  };

  const handlePrepareApply = (oppId: number) => {
    setAssistedOppId(oppId);
  };

  const handleMarkNotifRead = async (id: number) => {
    await markNotificationRead(id);
    loadNotifs();
  };

  const handleMarkAllNotifsRead = async () => {
    await markAllNotificationsRead();
    loadNotifs();
  };

  const getPageHeading = (tab: string) => {
    switch (tab) {
      case 'overview': return 'Overview';
      case 'discover': return 'Discover';
      case 'tracker': return 'Applications';
      case 'resumes': return 'Resume Studio';
      case 'interviews': return 'Interviews';
      case 'analytics': return 'Career Insights';
      case 'chat': return 'AI Assistant';
      case 'profile': return 'My Profile';
      case 'onboarding': return 'Candidate Onboarding & Activation';
      case 'preferences': return 'Settings';
      case 'sources': return 'Job Sources';
      case 'companies': return 'Company Directory';
      default: return 'CareerOS';
    }
  };

  return (
    <LiveAnnouncerProvider>
      <ToastProvider>
        <div className="relative flex h-screen w-screen overflow-hidden bg-[var(--color-paper)] font-sans text-[var(--color-ink)] antialiased selection:bg-[var(--color-selection)] selection:text-[var(--color-accent-ink)]">
          {/* Skip to Main Content Link for Keyboard Users */}
          <SkipLink targetId="main-content" />

          {/* Linear-style Collapsible Desktop Sidebar */}
          <Sidebar
            currentTab={navTab}
            onTabChange={(tab) => go(tab)}
            isCollapsed={isSidebarCollapsed}
            onToggleCollapse={handleToggleCollapse}
            onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
            onOpenShortcuts={() => setIsShortcutsOpen(true)}
            onOpenAICommand={() => setIsAICommandOpen(true)}
            onSyncAll={handleSyncAll}
            isSyncing={isSyncing}
            unreadCount={unreadCount}
          />

          {/* Main Content Viewport */}
          <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden bg-[var(--color-paper)]">
            {/* Top App Header with Breadcrumb & Quick Actions */}
            <AppHeader
              currentTab={navTab}
              onOpenMobileSidebar={() => setIsMobileNavOpen(true)}
              onOpenCommandPalette={() => setIsCommandPaletteOpen(true)}
            onOpenShortcuts={() => setIsShortcutsOpen(true)}
            onOpenImportModal={() => setShowImportModal(true)}
            onOpenAICommand={() => setIsAICommandOpen(true)}
            onSyncAll={handleSyncAll}
            isSyncing={isSyncing}
            notifications={notifications}
            unreadCount={unreadCount}
            onMarkNotificationRead={handleMarkNotifRead}
            onMarkAllRead={handleMarkAllNotifsRead}
            activeUserId={activeUserId}
            onSwitchCandidate={handleSwitchCandidate}
            onLogout={handleLogout}
          />

          {/* Scrollable Main Application Space with Landmark & Focusability */}
          <main
            id="main-content"
            tabIndex={-1}
            role="main"
            className="flex-1 overflow-y-auto px-4 sm:px-6 lg:px-8 py-6 lg:py-8 focus:outline-none"
          >
            {/* Screen Reader Level-One Heading for WCAG 2.4.2 & Heading Hierarchy */}
            <h1 className="sr-only font-semibold">
              CareerOS , {getPageHeading(navTab)}
            </h1>

            <div className="w-full max-w-[1440px] mx-auto space-y-6">
            {navTab === 'overview' && (
              <OverviewView
                onNavigateTab={(tab) => go(tab)}
                onTailorResume={handleTailorResume}
                onPrepareApply={handlePrepareApply}
                onSyncAll={handleSyncAll}
                isSyncing={isSyncing}
              />
            )}

            {navTab === 'discover' && (
              <div className="space-y-5">
                <PageHeader
                  eyebrow="Workspace"
                  title="Discover"
                  description="Every opportunity the engine found, normalized and scored against your verified profile."
                />
                <SummaryBanner metrics={metrics} onSelectTab={(t) => setOppTab(t)} />
                <OpportunityFeed
                  items={opportunities}
                  total={totalOpps}
                  page={page}
                  pageSize={pageSize}
                  totalPages={totalPages}
                  loading={loading}
                  activeTab={oppTab}
                  onTabChange={(t) => { setOppTab(t); setPage(1); }}
                  onPageChange={(p) => setPage(p)}
                  onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
                  onViewDetail={(id) => setSelectedOppId(id)}
                  onToggleSave={handleToggleSave}
                  onDismiss={handleDismiss}
                  onHandoffTracker={handleHandoffTracker}
                  onTailorResume={handleTailorResume}
                  onPrepareApply={handlePrepareApply}
                  onOpenImport={() => setShowImportModal(true)}
                  filters={filters}
                  onFilterChange={(f) => { setFilters(f); setPage(1); }}
                  snapshotId={snapshotId}
                  nextCursor={nextCursor}
                  hasMore={hasMore}
                  onLoadMore={handleLoadMore}
                  loadingMore={loadingMore}
                  sessionExpiredNotice={sessionExpiredNotice}
                  onDismissSessionExpiredNotice={() => setSessionExpiredNotice(false)}
                  onCalculateMatch={handleCalculateMatch}
                />
              </div>
            )}

            {navTab === 'tracker' && (
              <ApplicationTrackerView
                onNavigateToInterviews={() => go('interviews')}
              />
            )}
            {navTab === 'resumes' && <ResumeStudioView />}
            {navTab === 'interviews' && <InterviewJournalView />}
            {navTab === 'analytics' && <AnalyticsView />}
            {navTab === 'chat' && <AIChatAssistantView />}
            {navTab === 'profile' && <CandidateProfileView />}
            {navTab === 'onboarding' && (
              <CandidateOnboardingView
                onComplete={() => {
                  go('discover');
                  loadData(1, pageSize);
                }}
                onExit={() => go('overview')}
              />
            )}
            {navTab === 'sources' && <SourcesView />}
            {navTab === 'companies' && <CompanyDirectoryView />}
            {navTab === 'preferences' && <PreferencesView onNavigateTab={go} />}
          </div>
        </main>
      </div>

      {/* Responsive Mobile Drawer Navigation */}
      <MobileDrawer
        isOpen={isMobileNavOpen}
        onClose={() => setIsMobileNavOpen(false)}
        currentTab={navTab}
        onTabChange={(tab) => go(tab)}
        onOpenImport={() => setShowImportModal(true)}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
        onSyncAll={handleSyncAll}
        isSyncing={isSyncing}
      />

      {/* Global Command Palette (Cmd+K / Ctrl+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        onNavigate={(tab) => go(tab)}
        onSyncAll={handleSyncAll}
        onOpenImport={() => setShowImportModal(true)}
        onOpenShortcuts={() => setIsShortcutsOpen(true)}
      />

      {/* Keyboard Shortcuts Cheatsheet Modal (?) */}
      <KeyboardShortcutsModal
        isOpen={isShortcutsOpen}
        onClose={() => setIsShortcutsOpen(false)}
      />

      {/* Global AI Command Center Drawer (Cmd+J / Ctrl+J) */}
      <GlobalAICommandCenter
        isOpen={isAICommandOpen}
        onClose={() => setIsAICommandOpen(false)}
        onNavigateTab={(tab) => go(tab)}
      />

      {/* Opportunity Detail Modal */}
      {selectedOppId && (
        <OpportunityDetailModal
          opportunityId={selectedOppId}
          onClose={() => setSelectedOppId(null)}
          onToggleSave={handleToggleSave}
          onHandoffTracker={handleHandoffTracker}
        />
      )}

      {/* Assisted Application Workflow Modal */}
      {assistedOppId && (
        <AssistedApplicationModal
          opportunityId={assistedOppId}
          onClose={() => setAssistedOppId(null)}
          onSuccess={() => {
            setAssistedOppId(null);
            loadData(page, pageSize);
            loadNotifs();
          }}
        />
      )}

      {/* Manual Import Modal */}
      <ManualImportModal
        isOpen={showImportModal}
        onClose={() => setShowImportModal(false)}
        onSuccess={() => {
          loadData(page, pageSize);
          loadNotifs();
        }}
      />
        </div>
      </ToastProvider>
    </LiveAnnouncerProvider>
  );
};

export const App: React.FC = () => (
  <UnsavedChangesProvider>
    <AppInner />
  </UnsavedChangesProvider>
);

export default App;
