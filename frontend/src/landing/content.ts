export const REPOSITORY = 'https://github.com/chintu79/careeros';

// LICENSE, SECURITY.md, CONTRIBUTING.md and docs/ land on main with PR #2.
// Until that merges, link to the release branch so every link resolves.
const RELEASE = `${REPOSITORY}/blob/release-3.1.0`;

export const LINKS = {
  repository: REPOSITORY,
  license: `${RELEASE}/LICENSE`,
  security: `${RELEASE}/SECURITY.md`,
  contributing: `${RELEASE}/CONTRIBUTING.md`,
  docs: `${RELEASE}/docs/self-hosting.md`,
  ci: `${REPOSITORY}/blob/main/.github/workflows/ci.yml`,
  readme: `${REPOSITORY}/blob/main/README.md`,
  issues: `${REPOSITORY}/issues`,
};

export type FeatureVisual =
  | 'discovery'
  | 'tracking'
  | 'resume'
  | 'interviews'
  | 'insights'
  | 'ai';

export interface Feature {
  id: string;
  title: string;
  body: string;
  visual: FeatureVisual;
  span: 'wide' | 'half' | 'third' | 'full';
}

export const FEATURES: Feature[] = [
  {
    id: 'discovery',
    title: 'Opportunity discovery',
    body: 'Greenhouse, Lever, Ashby, SmartRecruiters and more, normalized into one feed and ranked against your profile.',
    visual: 'discovery',
    span: 'wide',
  },
  {
    id: 'tracking',
    title: 'Application tracking',
    body: 'Board, table, timeline and calendar over one record set. Every stage and follow-up stays in place.',
    visual: 'tracking',
    span: 'half',
  },
  {
    id: 'resume',
    title: 'Resume Studio',
    body: 'A LaTeX master resume, tailored variants, PDF rebuild and an ATS-style quality audit.',
    visual: 'resume',
    span: 'third',
  },
  {
    id: 'interviews',
    title: 'Interview workflows',
    body: 'Role-specific practice questions with local AI evaluation and a running prep journal.',
    visual: 'interviews',
    span: 'third',
  },
  {
    id: 'insights',
    title: 'Career insights',
    body: 'Pipeline conversion, source efficacy and a Sankey view of where applications actually go.',
    visual: 'insights',
    span: 'third',
  },
  {
    id: 'ai',
    title: 'Optional AI assistance',
    body: 'Groq or local Ollama. Matching, tracking and resume generation work with neither configured.',
    visual: 'ai',
    span: 'full',
  },
];

export interface WalkthroughStage {
  id: string;
  index: string;
  label: string;
  title: string;
  body: string;
  bullets: string[];
}

export const STAGES: WalkthroughStage[] = [
  {
    id: 'discover',
    index: '01',
    label: 'Discover',
    title: 'One feed, ranked by fit.',
    body: 'Postings from ATS boards, public APIs and manual imports are normalized, deduplicated and scored against your profile.',
    bullets: [
      'Hybrid keyword and pgvector match scoring',
      'Saved searches, ranking snapshots and source health',
      'Eligibility, location and workplace filters',
    ],
  },
  {
    id: 'organize',
    index: '02',
    label: 'Organize',
    title: 'Every application, one record.',
    body: 'Move a role from saved to applied to interview without re-entering it, then work from the view that fits the task.',
    bullets: [
      'Kanban, table, timeline and calendar views',
      'Follow-up drafts and interview scheduling',
      'A prep journal attached to the role',
    ],
  },
  {
    id: 'progress',
    index: '03',
    label: 'Progress',
    title: 'See what is converting.',
    body: 'Response and interview rates by source, stage and role family, drawn from the applications you already track.',
    bullets: [
      'Pipeline conversion and career readiness',
      'Source efficacy across every connector',
      'A Sankey view of the whole search',
    ],
  },
];

export const CREDIBILITY = [
  {
    title: 'Apache-2.0',
    body: 'The full source, not an open-core shell.',
    href: LINKS.license,
  },
  {
    title: 'Self-hosted',
    body: 'Frontend, API and PostgreSQL in one Compose stack.',
    href: LINKS.docs,
  },
  {
    title: 'Tested in the open',
    body: 'Backend and frontend suites run on every pull request.',
    href: LINKS.ci,
  },
  {
    title: 'A security policy',
    body: 'A written disclosure process and supported versions.',
    href: LINKS.security,
  },
];

export const STACK = [
  { label: 'Frontend', value: 'React 18, TypeScript, Vite, Tailwind CSS' },
  { label: 'Backend', value: 'FastAPI, SQLAlchemy, Python' },
  { label: 'Database', value: 'PostgreSQL 17 with pgvector' },
  { label: 'Deployment', value: 'Docker Compose, nginx, persistent volumes' },
  { label: 'AI', value: 'Groq or Ollama, both optional' },
  { label: 'Testing and CI', value: 'pytest, Vitest, GitHub Actions, secret scanning' },
];

export const FAQ = [
  {
    question: 'Is CareerOS free and open source?',
    answer:
      'Yes. CareerOS is licensed under Apache-2.0. The repository contains the backend, frontend, deployment files and tests. There is no paid tier and no open-core gate.',
  },
  {
    question: 'Can I self-host it?',
    answer:
      'Yes. The v3.1.0 stack runs with Docker Compose: PostgreSQL with pgvector, the FastAPI backend and the React frontend behind nginx. It is single-tenant, so do not expose it as a public multi-user service without additional hardening.',
  },
  {
    question: 'Is my data stored locally?',
    answer:
      'The database, resume artifacts and application records live in Docker volumes on your machine. If you enable Groq, the content you send to AI features leaves the machine. Ollama keeps inference local. Neither provider is required.',
  },
  {
    question: 'Does it require an AI API key?',
    answer:
      'No. Matching, tracking, resume generation and the rest of the deterministic path work without an AI provider. Groq and Ollama are optional enhancements, and features fall back with explicit unavailable states.',
  },
  {
    question: 'What integrations are supported?',
    answer:
      'Discovery covers Greenhouse, Lever, Ashby, SmartRecruiters, Remotive, Remote OK, RSS feeds and manual URL, paste or email-alert import. Adzuna was retired in v3.1.0. Optional adapters cover GitHub and Google Calendar.',
  },
  {
    question: 'Can I contribute?',
    answer:
      'Yes. Read CONTRIBUTING.md, run the test suites and open a pull request against main. Pull requests run the same CI workflow used for releases and require an approving review.',
  },
];

export const INSTALL_COMMANDS = `git clone https://github.com/chintu79/careeros.git
cd careeros
cp .env.example .env
# set the three secrets from .env.example
docker compose up -d --build`;

export const HERO_WORDS = ['Your', 'career', 'deserves', 'a', 'command', 'center.'];
