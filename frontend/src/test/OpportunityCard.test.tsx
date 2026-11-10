import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import { OpportunityCard } from '../components/discovery/OpportunityCard';
import { OpportunityItem } from '../types';

const mockEvaluatedOpp: OpportunityItem = {
  id: 101,
  title: 'Full Stack Engineer Intern',
  normalized_title: 'full stack engineer intern',
  company_name: 'Stripe',
  location: 'San Francisco, CA',
  normalized_location: 'San Francisco, CA',
  workplace_type: 'hybrid',
  employment_type: 'internship',
  source_platform: 'linkedin',
  status: 'active',
  discovered_at: '2026-11-01T00:00:00Z',
  match_score: 88,
  is_saved: false,
  is_applied: false,
  eligibility_status: 'eligible',
  stipend_text: '$50/hr',
  posted_at: '2026-11-01T10:00:00Z',
  deadline_at: '2026-12-01T23:59:59Z',
  source_reliability: { score: 95, tier: 'high', badge: 'Verified', platform: 'linkedin' },
  why_it_matches: ['Strong proficiency in TypeScript and React', 'Proven backend architecture experience'],
  matching_skills: ['TypeScript', 'React', 'Node.js', 'PostgreSQL'],
  missing_skills: ['GraphQL'],
  category_scores: {
    mandatory_skills: 90,
    experience: 85,
    projects: 88,
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
  ranking_reasons: {
    primary_factor: 'evaluated_candidate_match',
    is_evaluated: true,
    is_stale: false,
    evaluation_state: 'evaluated_high',
    match_score: 88,
    eligibility_status: 'eligible',
    highlights: [],
  },
  skill_gaps: [
    {
      skill_name: 'GraphQL',
      priority: 'medium',
      suggested_learning_or_improvement: 'Review Apollo GraphQL Client & Schema stitching',
      missing_evidence: '',
    },
  ],
  scoring_explanation: 'High match across all core engineering domains.',
};

const mockUnevaluatedOpp: OpportunityItem = {
  id: 102,
  title: 'Junior Data Scientist',
  normalized_title: 'junior data scientist',
  company_name: 'Databricks',
  location: 'Remote',
  normalized_location: 'Remote',
  workplace_type: 'remote',
  employment_type: 'internship',
  source_platform: 'greenhouse',
  status: 'active',
  discovered_at: '2026-11-01T00:00:00Z',
  match_score: 0,
  is_saved: false,
  is_applied: false,
  eligibility_status: 'eligible',
  ranking_reasons: {
    primary_factor: 'unevaluated',
    is_evaluated: false,
    is_stale: false,
    evaluation_state: 'unevaluated',
    match_score: 0,
    eligibility_status: 'eligible',
    highlights: [],
  },
};

const mockDisqualifiedOpp: OpportunityItem = {
  id: 103,
  title: 'Hardware Systems Intern',
  normalized_title: 'hardware systems intern',
  company_name: 'Apple',
  location: 'Cupertino, CA',
  normalized_location: 'Cupertino, CA',
  workplace_type: 'onsite',
  employment_type: 'internship',
  source_platform: 'lever',
  status: 'active',
  discovered_at: '2026-11-01T00:00:00Z',
  match_score: 42,
  is_saved: false,
  is_applied: false,
  eligibility_status: 'disqualified',
  ranking_reasons: {
    primary_factor: 'disqualified',
    is_evaluated: true,
    is_stale: false,
    evaluation_state: 'evaluated_low',
    match_score: 42,
    eligibility_status: 'disqualified',
    highlights: [],
  },
};

describe('OpportunityCard Component', () => {
  const defaultHandlers = {
    onViewDetail: vi.fn(),
    onToggleSave: vi.fn(),
    onDismiss: vi.fn(),
    onHandoffTracker: vi.fn(),
    onTailorResume: vi.fn(),
    onPrepareApply: vi.fn(),
    onCalculateMatch: vi.fn(),
  };

  it('renders evaluated opportunity with company, title, and match label', () => {
    render(<OpportunityCard item={mockEvaluatedOpp} {...defaultHandlers} />);

    expect(screen.getByText('Stripe')).toBeInTheDocument();
    expect(screen.getByText('Full Stack Engineer Intern')).toBeInTheDocument();
    expect(screen.getByText('match')).toBeInTheDocument();
    expect(screen.getByText('San Francisco, CA')).toBeInTheDocument();
    expect(screen.getByText('$50/hr')).toBeInTheDocument();
  });

  it('renders unevaluated opportunity with Unevaluated badge and Calculate action', () => {
    render(<OpportunityCard item={mockUnevaluatedOpp} {...defaultHandlers} />);

    expect(screen.getByText('Databricks')).toBeInTheDocument();
    expect(screen.getByText('Junior Data Scientist')).toBeInTheDocument();
    expect(screen.getByText('Unevaluated')).toBeInTheDocument();
    expect(screen.getByText('Calculate')).toBeInTheDocument();
  });

  it('triggers onCalculateMatch when Calculate button is clicked on unevaluated card', async () => {
    const handleCalculate = vi.fn().mockResolvedValue(undefined);
    render(<OpportunityCard item={mockUnevaluatedOpp} {...defaultHandlers} onCalculateMatch={handleCalculate} />);

    const calculateBtn = screen.getByRole('button', { name: /calculate/i });
    fireEvent.click(calculateBtn);

    expect(handleCalculate).toHaveBeenCalledWith(102);
  });

  it('renders disqualified opportunity with Not eligible indicator', () => {
    render(<OpportunityCard item={mockDisqualifiedOpp} {...defaultHandlers} />);

    expect(screen.getByText('Not eligible')).toBeInTheDocument();
    expect(screen.getByText('Apple')).toBeInTheDocument();
  });

  it('handles missing optional stipend and deadline neutrally', () => {
    const sparseOpp: OpportunityItem = {
      id: 104,
      title: 'Backend Intern',
      normalized_title: 'backend intern',
      company_name: 'Acme Corp',
      location: 'Remote',
      normalized_location: 'remote',
      workplace_type: 'remote',
      employment_type: 'internship',
      source_platform: 'direct',
      status: 'active',
      discovered_at: '2026-11-01T00:00:00Z',
      match_score: 0,
      is_saved: false,
      is_applied: false,
      eligibility_status: 'eligible',
    };

    render(<OpportunityCard item={sparseOpp} {...defaultHandlers} />);
    expect(screen.getByText('Rolling deadline')).toBeInTheDocument();
    expect(screen.queryByText('$')).not.toBeInTheDocument();
  });

  it('expands Match Intelligence drawer and displays 5-category evaluation and skill gaps', () => {
    render(<OpportunityCard item={mockEvaluatedOpp} {...defaultHandlers} />);

    const expandBtn = screen.getByRole('button', { name: /match intelligence/i });
    fireEvent.click(expandBtn);

    // Verify 5-Category Evaluation section
    expect(screen.getByText('5-Category Evaluation')).toBeInTheDocument();
    expect(screen.getByText('Mandatory Skills')).toBeInTheDocument();
    expect(screen.getByText('Experience')).toBeInTheDocument();
    expect(screen.getByText('Projects')).toBeInTheDocument();
    expect(screen.getByText('Preferred Skills')).toBeInTheDocument();
    expect(screen.getByText('Education Certifications')).toBeInTheDocument();

    // Verify Skill Gaps
    expect(screen.getByText(/Skill Gaps & Suggestions/i)).toBeInTheDocument();
    expect(screen.getAllByText('GraphQL').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Review Apollo GraphQL Client/i)).toBeInTheDocument();
  });

  it('invokes onViewDetail when title or Details button is clicked', () => {
    render(<OpportunityCard item={mockEvaluatedOpp} {...defaultHandlers} />);

    const titleBtn = screen.getByRole('button', { name: 'Full Stack Engineer Intern' });
    fireEvent.click(titleBtn);
    expect(defaultHandlers.onViewDetail).toHaveBeenCalledWith(101);

    const detailsBtn = screen.getByRole('button', { name: /view full details/i });
    fireEvent.click(detailsBtn);
    expect(defaultHandlers.onViewDetail).toHaveBeenCalledWith(101);
  });
});
