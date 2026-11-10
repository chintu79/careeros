import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ResumeStudioView } from '../components/resumes/ResumeStudioView';
import * as api from '../services/api';
import { 
  ResumeDocument, 
  ResumeTemplateItem, 
  ResumeVersionItem, 
  ResumeQualityAuditResult,
  CandidateProfile,
  Opportunity
} from '../types';

vi.mock('../services/api', () => ({
  getAuthToken: vi.fn(() => 'ci-test-token'),
  fetchResumes: vi.fn(),
  fetchMasterResume: vi.fn(),
  createResume: vi.fn(),
  updateResume: vi.fn(),
  renameResume: vi.fn(),
  duplicateResume: vi.fn(),
  deleteResume: vi.fn(),
  compileResumePdf: vi.fn(),
  fetchResumeTemplates: vi.fn(),
  fetchResumeVersions: vi.fn(),
  createResumeVersionSnapshot: vi.fn(),
  restoreResumeVersion: vi.fn(),
  compareResumeVersions: vi.fn(),
  auditResumeQuality: vi.fn(),
  requestResumeOptimization: vi.fn(),
  applyResumeOptimization: vi.fn(),
  fetchOpportunities: vi.fn(),
  fetchCandidateProfile: vi.fn(),
}));

const mockMasterResume: ResumeDocument = {
  id: 1,
  user_id: 1,
  title: 'Master Candidate Resume',
  template_id: 'minimal_professional',
  latex_content: '\\documentclass{article}\n\\begin{document}\nMaster Resume Content\n\\end{document}',
  is_master: true,
  target_role: 'Full Stack Engineer',
  target_company: undefined,
  version: 75,
  pdf_path: '/api/resumes/1/pdf',
  pdf_generated_at: '2026-11-09T10:00:00Z',
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-09T10:00:00Z',
};

const mockCopyResume: ResumeDocument = {
  id: 2,
  user_id: 1,
  title: 'Tailored Stripe Resume',
  template_id: 'software_engineering',
  latex_content: '\\documentclass{article}\n\\begin{document}\nStripe Tailored Content\n\\end{document}',
  is_master: false,
  target_role: 'Backend Engineer',
  target_company: 'Stripe',
  version: 3,
  pdf_path: '/api/resumes/2/pdf',
  pdf_generated_at: '2026-11-09T11:00:00Z',
  created_at: '2026-11-05T00:00:00Z',
  updated_at: '2026-11-09T11:00:00Z',
};

const mockTemplates: ResumeTemplateItem[] = [
  {
    id: 'minimal_professional',
    name: 'Minimal Professional',
    description: 'Ultra-clean single column layout optimized for parsing.',
    tags: ['ATS-Safe', 'Clean', 'Single-Column'],
    recommended_for: 'General SWE, Data Science'
  },
  {
    id: 'software_engineering',
    name: 'Software Engineering Classic',
    description: 'Technical-first layout emphasizing open-source projects.',
    tags: ['Technical', 'GitHub', 'Metrics'],
    recommended_for: 'Full Stack, Backend, Systems'
  }
];

const mockVersions: ResumeVersionItem[] = [
  {
    id: 101,
    resume_id: 1,
    version_number: 75,
    change_summary: 'Applied STAR bullet metrics refinement',
    created_at: '2026-11-09T10:00:00Z',
  },
  {
    id: 100,
    resume_id: 1,
    version_number: 74,
    change_summary: 'Added Docker containerization experience',
    created_at: '2026-11-08T18:00:00Z',
  }
];

const mockAuditReport: ResumeQualityAuditResult = {
  ats_score: 88,
  grade: 'A',
  summary: 'Excellent ATS parsing fidelity with 100% single-column compliance.',
  checks: [
    { title: 'Single-Column Layout', passed: true, score: 100, details: ['No multicolumn or text boxes detected'] },
    { title: 'Action Verbs', passed: true, score: 90, details: ['Strong technical action verbs utilized'] },
  ]
};

const mockProfile: CandidateProfile = {
  id: 1,
  user_id: 1,
  name: 'Krishna Patel',
  email: 'krishna@example.com',
  phone: '+91 9876543210',
  location: 'Pune, India',
  college: 'PICT Pune',
  degree: 'B.Tech AI & Data Science',
  graduation_year: 2028,
  cgpa: 8.16,
  github_url: 'https://github.com/krishna',
  linkedin_url: 'https://linkedin.com/in/krishna',
  skills: [
    { name: 'Python', category: 'Languages' },
    { name: 'React', category: 'Frameworks' },
  ],
  experience: [
    { title: 'Software Engineering Intern', company: 'TechCorp', duration: 'Jun - Aug 2025', description: 'Built APIs' }
  ],
  projects: [
    { title: 'CareerOS AI', tech_stack: ['Python', 'FastAPI'], description: 'Autonomous agent platform', url: 'https://github.com/krishna/careeros' }
  ],
  created_at: '2026-11-01T00:00:00Z',
  updated_at: '2026-11-09T00:00:00Z',
};

const mockOpportunities: Opportunity[] = [
  {
    id: 201,
    title: 'Distributed Systems Intern',
    company_name: 'Stripe',
    location: 'Remote',
    source: 'lever',
    url: 'https://jobs.stripe.com/201',
    is_active: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-09T00:00:00Z',
  }
];

describe('ResumeStudioView Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (api.fetchResumes as any).mockResolvedValue({ items: [mockMasterResume, mockCopyResume], total: 2 });
    (api.fetchMasterResume as any).mockResolvedValue(mockMasterResume);
    (api.fetchResumeTemplates as any).mockResolvedValue(mockTemplates);
    (api.fetchResumeVersions as any).mockResolvedValue(mockVersions);
    (api.auditResumeQuality as any).mockResolvedValue(mockAuditReport);
    (api.fetchOpportunities as any).mockResolvedValue({ items: mockOpportunities, total: 1 });
    (api.fetchCandidateProfile as any).mockResolvedValue(mockProfile);
    (api.updateResume as any).mockResolvedValue({ ...mockMasterResume, version: 76 });
    (api.compileResumePdf as any).mockResolvedValue({
      pdf_url: '/api/resumes/1/pdf',
      generated_at: '2026-11-09T12:00:00Z',
      compiler_used: 'tectonic'
    });
    (api.createResumeVersionSnapshot as any).mockResolvedValue({ id: 102, version_number: 76 });
    (api.restoreResumeVersion as any).mockResolvedValue({ ...mockMasterResume, version: 77 });
    (api.duplicateResume as any).mockResolvedValue({
      ...mockMasterResume,
      id: 3,
      title: 'Copy of Master Candidate Resume',
      is_master: false,
      version: 1
    });
  });

  it('renders page header, active resume metadata, and action buttons', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Resume Studio')).toBeInTheDocument();
    });

    expect(screen.getAllByText('Master').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText(/v75/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('minimal_professional')).toBeInTheDocument();
    expect(screen.getByText('Templates')).toBeInTheDocument();
    expect(screen.getByText('Diff')).toBeInTheDocument();
    expect(screen.getByTitle('Run Pre-Flight ATS Quality Audit')).toBeInTheDocument();
    expect(screen.getByText('Tailor')).toBeInTheDocument();
    expect(screen.getByText('Compile PDF')).toBeInTheDocument();
  });

  it('renders resume documents list and version history snapshots', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Master Candidate Resume')).toBeInTheDocument();
      expect(screen.getByText('Tailored Stripe Resume')).toBeInTheDocument();
    });

    expect(screen.getByText('Applied STAR bullet metrics refinement')).toBeInTheDocument();
    expect(screen.getByText('Added Docker containerization experience')).toBeInTheDocument();
  });

  it('switches between Structured Editor and LaTeX Source modes', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Structured Editor')).toBeInTheDocument();
    });

    const latexCodeBtn = screen.getByText('LaTeX Source');
    fireEvent.click(latexCodeBtn);

    expect(screen.getByText('ATS-Friendly LaTeX Code Editor')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('% LaTeX resume source')).toBeInTheDocument();
  });

  it('saves LaTeX source content and updates state', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Save')).toBeInTheDocument();
    });

    const saveBtn = screen.getByText('Save');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.updateResume).toHaveBeenCalledWith(1, expect.any(Object));
      expect(screen.getByText(/Saved LaTeX source/i)).toBeInTheDocument();
    });
  });

  it('compiles PDF document when clicking Compile PDF', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Compile PDF')).toBeInTheDocument();
    });

    const compileBtn = screen.getByText('Compile PDF');
    fireEvent.click(compileBtn);

    await waitFor(() => {
      expect(api.compileResumePdf).toHaveBeenCalledWith(1);
      expect(screen.getByText(/Compiled via TECTONIC/i)).toBeInTheDocument();
    });
  });

  it('opens and closes Templates modal', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Templates')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Templates'));

    await waitFor(() => {
      expect(screen.getByText('ATS-Optimized LaTeX Templates')).toBeInTheDocument();
      expect(screen.getByText('Software Engineering Classic')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Apply Template'));
  });

  it('opens and closes Pre-Flight ATS Quality Audit modal', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByTitle('Run Pre-Flight ATS Quality Audit')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTitle('Run Pre-Flight ATS Quality Audit'));

    await waitFor(() => {
      expect(screen.getByText('Pre-Flight ATS Quality Audit')).toBeInTheDocument();
      expect(screen.getByText('ATS Health Assessment')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Close Audit'));
  });

  it('opens Diff Compare modal when clicking Diff button', async () => {
    (api.compareResumeVersions as any).mockResolvedValue({
      base_label: 'Current LaTeX',
      target_label: 'Master Resume',
      added_lines: 4,
      removed_lines: 1,
      section_changes: [],
      diff_lines: [{ type: 'same', content: 'Sample code' }]
    });

    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Diff')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Diff'));

    await waitFor(() => {
      expect(screen.getByText('Resume Comparison & Change Audit')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Close Diff'));
  });

  it('protects master resume from deletion', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Master Candidate Resume')).toBeInTheDocument();
    });

    const deleteMasterBtn = screen.getByLabelText('Delete Master Candidate Resume');
    expect(deleteMasterBtn).toBeDisabled();
  });

  it('creates manual checkpoint snapshot', async () => {
    render(<ResumeStudioView />);

    await waitFor(() => {
      expect(screen.getByText('Checkpoint')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Checkpoint'));

    await waitFor(() => {
      expect(screen.getByText('Create Checkpoint Snapshot')).toBeInTheDocument();
    });

    const input = screen.getByPlaceholderText(/Added distributed systems/i);
    fireEvent.change(input, { target: { value: 'Pre-interview polishing' } });

    fireEvent.click(screen.getByText('Save Checkpoint'));

    await waitFor(() => {
      expect(api.createResumeVersionSnapshot).toHaveBeenCalledWith(1, 'Pre-interview polishing');
    });
  });
});
