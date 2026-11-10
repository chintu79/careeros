import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OpportunityDetailModal } from '../components/detail/OpportunityDetailModal';
import * as api from '../services/api';
import { OpportunityDetail } from '../types';

vi.mock('../services/api', () => ({
  fetchOpportunityDetail: vi.fn(),
  evaluateOpportunityMatch: vi.fn(),
}));

const mockDetail: OpportunityDetail = {
  id: 42,
  title: 'Distributed Systems Intern',
  company_name: 'Cloudflare',
  location: 'Austin, TX',
  normalized_location: 'Austin, TX',
  workplace_type: 'hybrid',
  employment_type: 'internship',
  source_platform: 'greenhouse',
  description: 'Join our edge computing team working on global workers architecture.',
  stipend_text: '$60/hr',
  duration_months: 3,
  match_score: 87,
  eligibility_status: 'eligible',
  is_saved: false,
  is_applied: false,
  scoring_explanation: 'Strong alignment with Rust, distributed systems, and networking profile.',
  category_scores: {
    mandatory_skills: 90,
    experience: 85,
    projects: 85,
    preferred_skills: 80,
    education_certifications: 95,
  },
  category_weights: {
    mandatory_skills: 0.40,
    experience: 0.20,
    projects: 0.15,
    preferred_skills: 0.15,
    education_certifications: 0.10,
  },
  match_analysis: {
    disqualifying_reasons: [],
    skill_compatibility: {
      strong: [{ skill: 'Rust', evidence: 'Project: Edge KV Store' }],
      partial: [{ skill: 'Go', transferable_from: 'C++', reason: 'Concurrency primitives' }],
      missing: ['Kubernetes'],
      unverified: [],
    },
  },
};

describe('OpportunityDetailModal Component', () => {
  const defaultHandlers = {
    onClose: vi.fn(),
    onToggleSave: vi.fn(),
    onHandoffTracker: vi.fn(),
  };

  it('renders nothing when opportunityId is null', () => {
    const { container } = render(
      <OpportunityDetailModal opportunityId={null} {...defaultHandlers} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('fetches detail and renders opportunity header and metadata', async () => {
    vi.mocked(api.fetchOpportunityDetail).mockResolvedValue(mockDetail);

    render(<OpportunityDetailModal opportunityId={42} {...defaultHandlers} />);

    expect(screen.getByText('Loading opportunity analysis...')).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText('Distributed Systems Intern')).toBeInTheDocument();
      expect(screen.getByText('Cloudflare')).toBeInTheDocument();
      expect(screen.getByText('Austin, TX')).toBeInTheDocument();
      expect(screen.getByText('$60/hr')).toBeInTheDocument();
    });
  });

  it('renders 5-category evaluation progress bars and exact precision copy', async () => {
    vi.mocked(api.fetchOpportunityDetail).mockResolvedValue(mockDetail);

    render(<OpportunityDetailModal opportunityId={42} {...defaultHandlers} />);

    await waitFor(() => {
      expect(screen.getByText('Distributed Systems Intern')).toBeInTheDocument();
      expect(screen.getByText(/5-category weighted evaluation and eligibility validation/i)).toBeInTheDocument();
    });
    const scoreElement = screen.getByText((content, element) => {
      return element?.tagName.toLowerCase() === 'span' && content.includes('87%');
    });
    expect(scoreElement).toBeInTheDocument();
    expect(screen.getByText('Evaluation Breakdown by Category')).toBeInTheDocument();
    expect(screen.getByText('Mandatory Skills')).toBeInTheDocument();
    expect(screen.getByText('40% weight')).toBeInTheDocument();
    expect(screen.getByText('Experience')).toBeInTheDocument();
    expect(screen.getByText('20% weight')).toBeInTheDocument();
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getAllByText('15% weight')).toHaveLength(2);
    expect(screen.getByText('Preferred Skills')).toBeInTheDocument();
    expect(screen.getByText('Education Certifications')).toBeInTheDocument();
    expect(screen.getByText('10% weight')).toBeInTheDocument();
  });

  it('handles Recalculate Match action button and updates detail', async () => {
    vi.mocked(api.fetchOpportunityDetail).mockResolvedValue(mockDetail);
    vi.mocked(api.evaluateOpportunityMatch).mockResolvedValue({
      opportunity_id: 42,
      candidate_id: 1,
      profile_match_score: 93,
      eligibility_status: 'eligible',
      category_scores: { ...mockDetail.category_scores, mandatory_skills: 98 },
      category_weights: mockDetail.category_weights!,
      calculated_at: '2026-11-08T12:00:00Z',
    } as any);

    render(<OpportunityDetailModal opportunityId={42} {...defaultHandlers} />);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /recalculate match/i })).toBeInTheDocument();
    });

    const recalcBtn = screen.getByRole('button', { name: /recalculate match/i });
    fireEvent.click(recalcBtn);

    expect(api.evaluateOpportunityMatch).toHaveBeenCalledWith(42, true);
  });

  it('switches to Full Job Description and Application Handoff tabs', async () => {
    vi.mocked(api.fetchOpportunityDetail).mockResolvedValue(mockDetail);

    render(<OpportunityDetailModal opportunityId={42} {...defaultHandlers} />);

    await waitFor(() => {
      expect(screen.getByText('Distributed Systems Intern')).toBeInTheDocument();
    });

    // Switch to Description
    const descTab = screen.getByRole('tab', { name: /full job description/i });
    fireEvent.click(descTab);
    expect(screen.getByText(/Join our edge computing team working on global workers architecture/i)).toBeInTheDocument();

    // Switch to Handoff
    const handoffTab = screen.getByRole('tab', { name: /application handoff & strategy/i });
    fireEvent.click(handoffTab);
    expect(screen.getByText('Application Handoff & Dossier Strategy')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add to application tracker/i })).toBeInTheDocument();
  });
});
