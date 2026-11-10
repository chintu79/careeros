import React, { useState, useEffect } from 'react';
import { 
  Search, 
  ArrowUpDown, 
  Sparkles, 
  Clock, 
  Bookmark, 
  CheckCircle2, 
  XCircle, 
  X,
  SlidersHorizontal,
  RefreshCw,
  Plus,
  Brain,
  Cpu,
  Building2,
  MapPin,
  Trash2
} from 'lucide-react';
import { OpportunityItem, SavedSearchItem, SearchHistoryItem } from '../../types';
import { OpportunityCard } from './OpportunityCard';
import { DismissFeedbackModal } from './DismissFeedbackModal';
import { SavedSearchesModal } from './SavedSearchesModal';
import {
  CardSkeleton,
  EmptyState,
  Pagination,
  Badge,
  Button
} from '../ui';
import { 
  submitOpportunityFeedback,
  fetchSavedSearches,
  createSavedSearch,
  deleteSavedSearch,
  fetchSearchHistory,
  clearSearchHistory
} from '../../services/api';

interface OpportunityFeedProps {
  items: OpportunityItem[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  loading: boolean;
  activeTab: string;
  onTabChange: (tab: string) => void;
  onPageChange: (newPage: number) => void;
  onPageSizeChange: (newPageSize: number) => void;
  onViewDetail: (id: number) => void;
  onToggleSave: (id: number) => void;
  onDismiss: (id: number) => void;
  onHandoffTracker: (id: number) => void;
  onTailorResume: (id: number) => void;
  onPrepareApply: (id: number) => void;
  onOpenImport: () => void;
  filters: any;
  onFilterChange: (filters: any) => void;
  snapshotId?: string | null;
  nextCursor?: number | null;
  hasMore?: boolean;
  onLoadMore?: () => void;
  loadingMore?: boolean;
  sessionExpiredNotice?: boolean;
  onDismissSessionExpiredNotice?: () => void;
  onCalculateMatch?: (id: number) => Promise<void> | void;
}

const SEARCH_MODES = [
  { id: 'hybrid', label: 'Hybrid AI', icon: Sparkles, desc: 'pgvector semantic cosine similarity blended with keyword matching' },
  { id: 'semantic', label: 'Semantic (pgvector)', icon: Brain, desc: 'Pure 1024-d neural embedding distance via BGE-M3' },
  { id: 'keyword', label: 'Keyword', icon: Search, desc: 'Broad title, description, and company name match' },
  { id: 'skill', label: 'Skill-Based', icon: Cpu, desc: 'Matches against required & extracted technical skills' },
  { id: 'company', label: 'Company', icon: Building2, desc: 'Filters directly by organization / employer name' },
  { id: 'location', label: 'Location', icon: MapPin, desc: 'Filters by city or remote/hybrid work arrangement' }
];

export const OpportunityFeed: React.FC<OpportunityFeedProps> = ({
  items,
  total,
  page,
  pageSize,
  totalPages,
  loading,
  activeTab,
  onTabChange,
  onPageChange,
  onPageSizeChange,
  onViewDetail,
  onToggleSave,
  onDismiss,
  onHandoffTracker,
  onTailorResume,
  onPrepareApply,
  onOpenImport,
  filters,
  onFilterChange,
  snapshotId,
  nextCursor,
  hasMore,
  onLoadMore,
  loadingMore,
  sessionExpiredNotice,
  onDismissSessionExpiredNotice,
  onCalculateMatch
}) => {
  const [showFilters, setShowFilters] = useState(false);
  
  // Saved Searches & History state
  const [savedSearches, setSavedSearches] = useState<SavedSearchItem[]>([]);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryItem[]>([]);
  const [showSavedDropdown, setShowSavedDropdown] = useState(false);
  const [showSaveModal, setShowSaveModal] = useState(false);

  // Dismiss feedback state
  const [dismissingItem, setDismissingItem] = useState<OpportunityItem | null>(null);

  const loadSavedAndHistory = () => {
    fetchSavedSearches().then(res => setSavedSearches(res)).catch(() => {});
    fetchSearchHistory(8).then(res => setSearchHistory(res)).catch(() => {});
  };

  useEffect(() => {
    loadSavedAndHistory();
  }, []);

  const handleFeedbackSubmit = async (id: number, feedbackType: string, note?: string) => {
    try {
      await submitOpportunityFeedback(id, feedbackType, note);
      onDismiss(id);
    } catch (e) {
      console.error("Feedback submit error:", e);
      onDismiss(id);
    }
  };

  const handleSaveSearch = async (name: string) => {
    try {
      await createSavedSearch({
        name,
        search_mode: filters.search_mode || 'hybrid',
        query: filters.search || '',
        filters: { ...filters }
      });
      loadSavedAndHistory();
    } catch (e) {
      console.error(e);
    }
  };

  const handleDeleteSavedSearch = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteSavedSearch(id);
      loadSavedAndHistory();
    } catch (err) {
      console.error(err);
    }
  };

  const handleRunSavedSearch = (saved: SavedSearchItem) => {
    setShowSavedDropdown(false);
    onFilterChange({
      ...filters,
      ...saved.filters,
      search: saved.query,
      search_mode: saved.search_mode
    });
  };

  const handleClearHistory = async () => {
    try {
      await clearSearchHistory();
      setSearchHistory([]);
    } catch (err) {
      console.error(err);
    }
  };

  const tabs = [
    { id: 'recommended', label: 'Recommended', icon: Sparkles },
    { id: 'latest', label: 'Latest Feed', icon: Clock },
    { id: 'saved', label: 'Saved', icon: Bookmark },
    { id: 'expiring', label: 'Expiring Soon', icon: Clock },
    { id: 'applied', label: 'Applied', icon: CheckCircle2 },
    { id: 'dismissed', label: 'Dismissed', icon: XCircle }
  ];

  const currentSearchMode = filters.search_mode || 'hybrid';

  return (
    <div className="space-y-6">
      {/* Search & Filter Master Surface */}
      <section className="rounded-[var(--radius-card)] border border-white/[0.07] bg-[var(--color-surface)] shadow-card">
        {/* Navigation Tabs Bar & Action Controls */}
        <div className="flex flex-col gap-3 px-4 pt-3 sm:flex-row sm:items-center sm:justify-between sm:px-5">
          <div className="flex flex-1 items-center gap-5 overflow-x-auto no-scrollbar border-b border-white/[0.06]">
            {tabs.map(tab => {
              const Icon = tab.icon;
              const active = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => onTabChange(tab.id)}
                  aria-current={active ? 'page' : undefined}
                  className={`relative -mb-px inline-flex shrink-0 items-center gap-1.5 border-b-2 px-1 pb-3 pt-1 text-[13px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] ${
                    active
                      ? 'border-[var(--color-primary)] text-[var(--color-ink)]'
                      : 'border-transparent text-[var(--color-ink-secondary)] hover:text-[var(--color-ink)]'
                  }`}
                >
                  <Icon className={`h-3.5 w-3.5 ${active ? 'text-[var(--color-primary)]' : 'text-[var(--color-ink-tertiary)]'}`} strokeWidth={1.75} aria-hidden="true" />
                  <span>{tab.label}</span>
                </button>
              );
            })}
          </div>

          <div className="flex shrink-0 flex-wrap items-center gap-2 pb-2 sm:pb-0">
            {/* Saved Searches Popover Trigger */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowSavedDropdown(!showSavedDropdown)}
                aria-expanded={showSavedDropdown}
                className="inline-flex min-h-[32px] items-center gap-1.5 rounded-[var(--radius-sm)] border border-white/[0.08] bg-white/[0.02] px-2.5 text-[12px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.05] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
              >
                <Bookmark className="h-3.5 w-3.5 text-[var(--color-ink-tertiary)]" strokeWidth={1.75} aria-hidden="true" />
                <span>Saved</span>
                <span className="font-mono text-[10px] text-[var(--color-ink-tertiary)] tnum">
                  {savedSearches.length}
                </span>
              </button>

              {showSavedDropdown && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setShowSavedDropdown(false)} aria-hidden="true" />
                  <div
                    className="absolute right-0 z-40 mt-1.5 w-72 rounded-[var(--radius-card)] border border-white/[0.10] bg-[var(--color-surface-raised)] p-2 text-[12px] text-[var(--color-ink)] shadow-overlay animate-fadeIn"
                    onClick={e => e.stopPropagation()}
                  >
                    <div className="flex items-center justify-between border-b border-white/[0.07] px-2 py-1.5">
                      <span className="font-semibold text-[var(--color-ink)]">Saved searches</span>
                      <button
                        type="button"
                        onClick={() => { setShowSavedDropdown(false); setShowSaveModal(true); }}
                        className="text-[11px] font-medium text-[var(--color-primary)] hover:underline transition-colors"
                      >
                        Save current
                      </button>
                    </div>

                    <div className="max-h-60 space-y-0.5 overflow-y-auto py-1">
                      {savedSearches.length === 0 ? (
                        <p className="p-3 text-center text-[12px] text-[var(--color-ink-tertiary)]">No saved searches yet.</p>
                      ) : (
                        savedSearches.map(saved => (
                          <div
                            key={saved.id}
                            className="group flex items-center justify-between rounded-[var(--radius-xs)] px-2.5 py-1.5 transition-colors hover:bg-white/[0.04]"
                          >
                            <button
                              type="button"
                              onClick={() => handleRunSavedSearch(saved)}
                              className="min-w-0 flex-1 text-left"
                            >
                              <span className="block truncate font-medium text-[var(--color-ink)]">{saved.name}</span>
                              <span className="text-[10px] capitalize font-mono text-[var(--color-ink-tertiary)]">
                                {saved.search_mode} · {saved.query || 'All roles'}
                              </span>
                            </button>
                            <button
                              type="button"
                              onClick={e => handleDeleteSavedSearch(saved.id, e)}
                              className="p-1 text-[var(--color-ink-tertiary)] opacity-0 transition-opacity hover:text-rose-400 group-hover:opacity-100"
                              title="Delete saved search"
                              aria-label={`Delete saved search ${saved.name}`}
                            >
                              <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            </button>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>

            {/* Import Job Button */}
            <Button
              size="sm"
              variant="secondary"
              onClick={onOpenImport}
              leftIcon={<Plus className="h-3.5 w-3.5" />}
            >
              Import
            </Button>

            {/* Advanced Filters Button */}
            <Button
              size="sm"
              variant={showFilters ? 'primary' : 'secondary'}
              onClick={() => setShowFilters(!showFilters)}
              aria-expanded={showFilters}
              leftIcon={<SlidersHorizontal className="h-3.5 w-3.5" />}
            >
              Filters
            </Button>
          </div>
        </div>

        {/* Search Mode Segmented Bar */}
        <div className="flex items-center gap-2 overflow-x-auto border-t border-white/[0.06] px-4 py-2.5 no-scrollbar sm:px-5">
          <span className="shrink-0 text-[11px] font-medium text-[var(--color-ink-tertiary)]">Match mode</span>
          <div className="flex items-center gap-1 rounded-[var(--radius-sm)] bg-black/30 p-1 border border-white/[0.05]">
            {SEARCH_MODES.map(mode => {
              const Icon = mode.icon;
              const active = currentSearchMode === mode.id;
              return (
                <button
                  key={mode.id}
                  type="button"
                  onClick={() => onFilterChange({ ...filters, search_mode: mode.id })}
                  aria-pressed={active}
                  title={mode.desc}
                  className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[var(--radius-xs)] px-2.5 py-1 text-[11px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)] ${
                    active
                      ? 'bg-white/[0.08] text-[var(--color-ink)] shadow-sm'
                      : 'text-[var(--color-ink-secondary)] hover:bg-white/[0.03] hover:text-[var(--color-ink)]'
                  }`}
                >
                  <Icon className={`h-3 w-3 ${active ? 'text-[var(--color-primary)]' : 'text-[var(--color-ink-tertiary)]'}`} strokeWidth={1.75} aria-hidden="true" />
                  <span>{mode.label.replace(' (pgvector)', '')}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Query Input + Sort Selector Bar */}
        <div className="grid grid-cols-1 gap-2 border-t border-white/[0.06] px-4 py-3 sm:grid-cols-12 sm:px-5">
          <div className="relative sm:col-span-8">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-ink-tertiary)]" aria-hidden="true" />
            <input
              id="opportunity-search-input"
              type="text"
              aria-label="Search opportunities"
              placeholder={
                currentSearchMode === 'semantic'
                  ? 'Describe the work — e.g. “distributed backend services in Python or Go”'
                  : currentSearchMode === 'skill'
                  ? 'Enter skills — e.g. Python, FastAPI, Docker, PyTorch, React'
                  : currentSearchMode === 'company'
                  ? 'Enter an employer — e.g. Google, Zerodha, Swiggy, Razorpay'
                  : currentSearchMode === 'location'
                  ? 'Enter a location or “Remote” — e.g. Pune, Bengaluru, Remote India'
                  : 'Search by title, technology, company, or concept'
              }
              value={filters.search || ''}
              onChange={e => onFilterChange({ ...filters, search: e.target.value })}
              className="w-full rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-quiet)] px-3 pl-9 pr-24 text-[13px] text-[var(--color-ink)] placeholder-[var(--color-ink-tertiary)] min-h-[38px] transition-colors focus:border-[var(--color-border-hover)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
            />
            {filters.search && (
              <button
                type="button"
                onClick={() => setShowSaveModal(true)}
                aria-label="Save current search criteria"
                className="absolute right-2 top-1/2 -translate-y-1/2 rounded-[var(--radius-xs)] border border-white/[0.08] bg-white/[0.04] px-2 py-1 text-[10px] font-medium text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.08] hover:text-[var(--color-ink)]"
                title="Save this search"
              >
                Save search
              </button>
            )}
          </div>

          <div className="flex items-center gap-2 sm:col-span-4">
            <select
              id="opportunity-sort-select"
              aria-label="Sort opportunities by"
              value={filters.sort_by || 'match_score'}
              onChange={e => onFilterChange({ ...filters, sort_by: e.target.value })}
              className="flex-1 rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-quiet)] px-3 text-[13px] text-[var(--color-ink)] min-h-[38px] transition-colors focus:border-[var(--color-border-hover)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
            >
              <option value="match_score">Best match</option>
              <option value="posted_at">Newest first</option>
              <option value="deadline_at">Closing soonest</option>
              <option value="discovered_at">Recently discovered</option>
              <option value="min_stipend">Highest stipend</option>
            </select>

            <button
              type="button"
              onClick={() => onFilterChange({ ...filters, sort_order: filters.sort_order === 'asc' ? 'desc' : 'asc' })}
              aria-label={`Sort direction: currently ${filters.sort_order === 'asc' ? 'ascending' : 'descending'}. Click to toggle.`}
              className="inline-flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-quiet)] text-[var(--color-ink-secondary)] transition-colors hover:border-white/[0.16] hover:text-[var(--color-ink)] focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
              title="Toggle sort direction"
            >
              <ArrowUpDown className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        {/* Recent Search Chips */}
        {searchHistory.length > 0 && (
          <div className="flex items-center justify-between gap-2 border-t border-white/[0.06] px-4 py-2 text-[11px] sm:px-5">
            <div className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
              <span className="shrink-0 text-[var(--color-ink-tertiary)]">Recent</span>
              {searchHistory.map(h => (
                <button
                  key={h.id}
                  type="button"
                  onClick={() => onFilterChange({ ...filters, search: h.query, search_mode: h.search_mode })}
                  className="shrink-0 whitespace-nowrap rounded-[var(--radius-xs)] bg-white/[0.02] border border-white/[0.04] px-2 py-0.5 text-[var(--color-ink-secondary)] transition-colors hover:bg-white/[0.06] hover:text-[var(--color-primary)]"
                >
                  {h.query} <span className="font-mono text-[var(--color-ink-tertiary)]">{h.results_count}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={handleClearHistory}
              className="shrink-0 whitespace-nowrap rounded px-1.5 py-0.5 text-[var(--color-ink-tertiary)] transition-colors hover:text-[var(--color-ink)] focus-visible:ring-1 focus-visible:ring-[var(--color-primary)]"
            >
              Clear
            </button>
          </div>
        )}

        {/* Advanced Filters Drawer */}
        {showFilters && (
          <div className="grid grid-cols-1 gap-3.5 border-t border-white/[0.06] bg-black/20 px-4 py-4 sm:grid-cols-2 lg:grid-cols-4 sm:px-5 animate-fadeIn">
            <div className="space-y-1.5">
              <label htmlFor="filter-workplace" className="block text-[11px] font-semibold text-[var(--color-ink-tertiary)]">
                Workplace
              </label>
              <select
                id="filter-workplace"
                value={filters.workplace_type || ''}
                onChange={e => onFilterChange({ ...filters, workplace_type: e.target.value })}
                className="w-full rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-quiet)] px-3 text-[12px] text-[var(--color-ink)] min-h-[36px]"
              >
                <option value="">Any workplace</option>
                <option value="remote">Remote</option>
                <option value="hybrid">Hybrid</option>
                <option value="onsite">Onsite</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="filter-location" className="block text-[11px] font-semibold text-[var(--color-ink-tertiary)]">
                Location
              </label>
              <select
                id="filter-location"
                value={filters.location || ''}
                onChange={e => onFilterChange({ ...filters, location: e.target.value })}
                className="w-full rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-quiet)] px-3 text-[12px] text-[var(--color-ink)] min-h-[36px]"
              >
                <option value="">Any location</option>
                <option value="Remote, India">Remote, India</option>
                <option value="Bengaluru">Bengaluru</option>
                <option value="Pune">Pune</option>
                <option value="Mumbai">Mumbai</option>
                <option value="Hyderabad">Hyderabad</option>
                <option value="Gurugram">Gurugram / NCR</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="filter-compensation" className="block text-[11px] font-semibold text-[var(--color-ink-tertiary)]">
                Compensation
              </label>
              <select
                id="filter-compensation"
                value={filters.compensation_type || ''}
                onChange={e => onFilterChange({ ...filters, compensation_type: e.target.value })}
                className="w-full rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-quiet)] px-3 text-[12px] text-[var(--color-ink)] min-h-[36px]"
              >
                <option value="">Any compensation</option>
                <option value="paid">Paid only</option>
                <option value="unpaid">Unpaid</option>
                <option value="undisclosed">Undisclosed</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="filter-score" className="block text-[11px] font-semibold text-[var(--color-ink-tertiary)]">
                Minimum Match
              </label>
              <select
                id="filter-score"
                value={filters.min_score || ''}
                onChange={e => onFilterChange({ ...filters, min_score: e.target.value ? Number(e.target.value) : undefined })}
                className="w-full rounded-[var(--radius-control)] border border-white/[0.09] bg-[var(--color-paper-quiet)] px-3 text-[12px] text-[var(--color-ink)] min-h-[36px]"
              >
                <option value="">Any score</option>
                <option value="80">80% and above</option>
                <option value="70">70% and above</option>
                <option value="60">60% and above</option>
              </select>
            </div>
          </div>
        )}
      </section>

      {/* Session Expired Recovery Notice */}
      {sessionExpiredNotice && (
        <div className="flex items-center justify-between gap-3 rounded-[var(--radius-card)] border border-amber-500/30 bg-amber-500/[0.08] p-3.5 text-xs text-amber-200 animate-fadeIn">
          <div className="flex items-center gap-2.5">
            <RefreshCw className="h-4 w-4 text-amber-400 shrink-0" aria-hidden="true" />
            <span>
              <strong>Pagination session refreshed:</strong> We updated your discovery feed with the newest opportunities while preserving your active filters and search query.
            </span>
          </div>
          {onDismissSessionExpiredNotice && (
            <button
              type="button"
              onClick={onDismissSessionExpiredNotice}
              className="rounded p-1 text-amber-300/80 hover:bg-amber-500/20 hover:text-amber-100 transition-colors"
              aria-label="Dismiss notice"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          )}
        </div>
      )}

      {/* Result Count Status Bar */}
      <div className="flex items-center justify-between px-1 text-[12px] text-[var(--color-ink-secondary)]">
        <div className="flex items-center gap-2">
          <span className="tnum">
            <strong className="font-mono font-semibold text-[var(--color-ink)]">{items.length}</strong> of{' '}
            <strong className="font-mono font-semibold text-[var(--color-ink)]">{total}</strong> opportunities
          </span>
          <span className="h-3 w-px bg-white/[0.08]" aria-hidden="true" />
          <span className="capitalize text-[var(--color-ink-tertiary)] font-mono text-[11px]">{currentSearchMode} match</span>
        </div>

        {loading && (
          <span className="flex items-center gap-1.5 text-[var(--color-primary)] font-medium">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
            <span>Searching…</span>
          </span>
        )}
      </div>

      {/* Opportunity Cards Stream / Skeleton State */}
      {loading ? (
        <div className="grid grid-cols-1 gap-3.5">
          <CardSkeleton />
          <CardSkeleton />
          <CardSkeleton />
        </div>
      ) : items.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="h-5 w-5 text-[var(--color-primary)]" />}
          title="No opportunities match this query"
          description="Try a different match mode, widen your filters, or import a role you found elsewhere."
          action={
            <Button
              variant="secondary"
              onClick={onOpenImport}
              leftIcon={<Plus className="h-4 w-4" />}
            >
              Import job by URL
            </Button>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-3.5">
          {items.map(item => (
            <OpportunityCard
              key={item.id}
              item={item}
              onViewDetail={onViewDetail}
              onToggleSave={onToggleSave}
              onDismiss={onDismiss}
              onDismissClick={item => setDismissingItem(item)}
              onHandoffTracker={onHandoffTracker}
              onTailorResume={onTailorResume}
              onPrepareApply={onPrepareApply}
              onCalculateMatch={onCalculateMatch}
            />
          ))}
        </div>
      )}

      {/* Snapshot Consistency & Load More Cursor Bar */}
      {hasMore && onLoadMore && (
        <div className="flex flex-col items-center justify-center gap-2 py-4">
          <Button
            size="lg"
            variant="secondary"
            onClick={onLoadMore}
            disabled={loadingMore}
            isLoading={loadingMore}
            className="px-6 rounded-[var(--radius-card)]"
          >
            {loadingMore ? (
              <span>Loading more opportunities…</span>
            ) : (
              <span className="flex items-center gap-1.5">
                <span>Load More Opportunities</span>
                {total > items.length && (
                  <span className="font-mono text-[11px] text-[var(--color-ink-tertiary)]">
                    ({total - items.length} remaining)
                  </span>
                )}
              </span>
            )}
          </Button>
          {snapshotId && (
            <span className="font-mono text-[10px] text-[var(--color-ink-tertiary)]">
              Snapshot consistency active · ID: {snapshotId.slice(0, 8)}…
            </span>
          )}
        </div>
      )}

      {!hasMore && items.length > 0 && total > 0 && (
        <div className="py-3 text-center font-mono text-[11px] text-[var(--color-ink-tertiary)]">
          All {total} matching opportunities loaded · Snapshot consistent
        </div>
      )}

      {/* Pagination Footer */}
      {total > 0 && (
        <div className="rounded-[var(--radius-card)] border border-white/[0.07] bg-[var(--color-surface)] overflow-hidden shadow-card">
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            totalItems={total}
            pageSize={pageSize}
            onPageChange={onPageChange}
            onPageSizeChange={onPageSizeChange}
          />
        </div>
      )}

      {/* Feedback & Save Search Modals */}
      <DismissFeedbackModal
        item={dismissingItem}
        isOpen={!!dismissingItem}
        onClose={() => setDismissingItem(null)}
        onSubmitFeedback={handleFeedbackSubmit}
      />

      <SavedSearchesModal
        isOpen={showSaveModal}
        onClose={() => setShowSaveModal(false)}
        onSave={handleSaveSearch}
        query={filters.search || ''}
        searchMode={currentSearchMode}
        filters={filters}
      />
    </div>
  );
};
