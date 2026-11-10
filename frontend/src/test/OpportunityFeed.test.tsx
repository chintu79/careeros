import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OpportunityFeed } from '../components/discovery/OpportunityFeed';
import { OpportunityItem } from '../types';

// Mock api methods imported by OpportunityFeed
vi.mock('../../services/api', () => ({
  fetchSavedSearches: vi.fn().mockResolvedValue([]),
  createSavedSearch: vi.fn().mockResolvedValue({ id: 1, name: 'Saved' }),
  deleteSavedSearch: vi.fn().mockResolvedValue({ success: true }),
  fetchSearchHistory: vi.fn().mockResolvedValue([]),
  clearSearchHistory: vi.fn().mockResolvedValue({ success: true }),
  submitOpportunityFeedback: vi.fn().mockResolvedValue({ success: true }),
}));

const mockItems: OpportunityItem[] = [
  {
    id: 1,
    title: 'Frontend Developer',
    normalized_title: 'frontend developer',
    company_name: 'Vercel',
    location: 'Remote',
    normalized_location: 'remote',
    workplace_type: 'remote',
    employment_type: 'internship',
    source_platform: 'greenhouse',
    status: 'active',
    discovered_at: '2026-11-01T00:00:00Z',
    match_score: 92,
    is_saved: false,
    is_applied: false,
    eligibility_status: 'eligible',
  },
  {
    id: 2,
    title: 'Backend Engineer',
    normalized_title: 'backend engineer',
    company_name: 'Supabase',
    location: 'Singapore',
    normalized_location: 'singapore',
    workplace_type: 'remote',
    employment_type: 'internship',
    source_platform: 'lever',
    status: 'active',
    discovered_at: '2026-11-01T00:00:00Z',
    match_score: 85,
    is_saved: false,
    is_applied: false,
    eligibility_status: 'eligible',
  },
];

describe('OpportunityFeed Component', () => {
  const defaultProps = {
    items: mockItems,
    total: 25,
    page: 1,
    pageSize: 10,
    totalPages: 3,
    loading: false,
    activeTab: 'recommended',
    onTabChange: vi.fn(),
    onPageChange: vi.fn(),
    onPageSizeChange: vi.fn(),
    onViewDetail: vi.fn(),
    onToggleSave: vi.fn(),
    onDismiss: vi.fn(),
    onHandoffTracker: vi.fn(),
    onTailorResume: vi.fn(),
    onPrepareApply: vi.fn(),
    onOpenImport: vi.fn(),
    filters: { search: '', search_mode: 'hybrid' },
    onFilterChange: vi.fn(),
  };

  it('renders loading skeletons when loading is true', () => {
    render(<OpportunityFeed {...defaultProps} loading={true} items={[]} total={0} />);

    expect(screen.getByText('Searching…')).toBeInTheDocument();
  });

  it('renders empty state when there are no items and not loading', () => {
    render(<OpportunityFeed {...defaultProps} items={[]} total={0} />);

    expect(screen.getByText('No opportunities match this query')).toBeInTheDocument();
    expect(screen.getByText('Import job by URL')).toBeInTheDocument();
  });

  it('renders opportunity items and header count', () => {
    render(<OpportunityFeed {...defaultProps} />);

    expect(screen.getByText('Frontend Developer')).toBeInTheDocument();
    expect(screen.getByText('Backend Engineer')).toBeInTheDocument();
    expect(screen.getByText('Vercel')).toBeInTheDocument();
    expect(screen.getByText((_, element) => element?.textContent === '2 of 25 opportunities')).toBeInTheDocument();
  });

  it('renders Load More Opportunities button and handles click', () => {
    const handleLoadMore = vi.fn();
    render(
      <OpportunityFeed
        {...defaultProps}
        hasMore={true}
        nextCursor={12}
        snapshotId="snap-12345678"
        onLoadMore={handleLoadMore}
        loadingMore={false}
      />
    );

    const loadMoreBtn = screen.getByRole('button', { name: /load more opportunities/i });
    expect(loadMoreBtn).toBeInTheDocument();
    expect(screen.getByText(/23 remaining/i)).toBeInTheDocument();
    expect(screen.getByText(/Snapshot consistency active/i)).toBeInTheDocument();

    fireEvent.click(loadMoreBtn);
    expect(handleLoadMore).toHaveBeenCalledTimes(1);
  });

  it('disables Load More button during loadingMore to prevent concurrent duplicate clicks', () => {
    const handleLoadMore = vi.fn();
    render(
      <OpportunityFeed
        {...defaultProps}
        hasMore={true}
        nextCursor={12}
        snapshotId="snap-12345678"
        onLoadMore={handleLoadMore}
        loadingMore={true}
      />
    );

    const loadMoreBtn = screen.getByRole('button', { name: /loading more opportunities/i });
    expect(loadMoreBtn).toBeDisabled();

    fireEvent.click(loadMoreBtn);
    expect(handleLoadMore).not.toHaveBeenCalled();
  });

  it('renders exhausted pagination footer when hasMore is false and items loaded', () => {
    render(
      <OpportunityFeed
        {...defaultProps}
        items={mockItems}
        total={2}
        hasMore={false}
      />
    );

    expect(screen.getByText(/All 2 matching opportunities loaded · Snapshot consistent/i)).toBeInTheDocument();
  });

  it('renders session expired recovery banner when sessionExpiredNotice is true', () => {
    const handleDismissNotice = vi.fn();
    render(
      <OpportunityFeed
        {...defaultProps}
        sessionExpiredNotice={true}
        onDismissSessionExpiredNotice={handleDismissNotice}
      />
    );

    expect(screen.getByText(/Pagination session refreshed/i)).toBeInTheDocument();
    const dismissBtn = screen.getByRole('button', { name: /dismiss notice/i });
    fireEvent.click(dismissBtn);
    expect(handleDismissNotice).toHaveBeenCalledTimes(1);
  });
});
