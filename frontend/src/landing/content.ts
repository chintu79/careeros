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

export const INSTALL_COMMANDS = `git clone https://github.com/chintu79/careeros.git
cd careeros
cp .env.example .env
# set the three secrets from .env.example
docker compose up -d --build`;

export const HERO_WORDS = ['Your', 'career', 'deserves', 'a', 'command', 'center.'];

// Every interactive demonstration below uses one shared fictional thread:
// an illustrative backend intern opportunity at Linear, saved in Chapter 03,
// tracked through the board in Chapter 04 and prepared for in Chapter 06.
// Nothing here is a real person, account or application.
export const SAMPLE_DATA_LABEL = 'Illustrative sample data';

export const AUTHOR = {
  name: 'Shreekrishna Chinta',
  github: 'https://github.com/chintu79',
  email: 'shrikrishnachinta79@gmail.com',
  location: 'Pune, India',
};

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

export const STACK = [
  { label: 'Frontend', value: 'React 18, TypeScript, Vite, Tailwind CSS' },
  { label: 'Backend', value: 'FastAPI, SQLAlchemy, Python' },
  { label: 'Database', value: 'PostgreSQL 17 with pgvector' },
  { label: 'Deployment', value: 'Docker Compose, nginx, persistent volumes' },
  { label: 'AI', value: 'Groq or Ollama, both optional' },
  { label: 'Testing and CI', value: 'pytest, Vitest, GitHub Actions, secret scanning' },
];

export const CHAPTERS = [
  { id: 'problem', index: '01', label: 'Scattered' },
  { id: 'workspace', index: '02', label: 'Connected' },
  { id: 'discover', index: '03', label: 'Discover' },
  { id: 'track', index: '04', label: 'Track' },
  { id: 'resume', index: '05', label: 'Resume' },
  { id: 'interviews', index: '06', label: 'Interviews' },
  { id: 'insights', index: '07', label: 'Insights' },
  { id: 'open-source', index: '08', label: 'Open source' },
] as const;

/* ---------- Chapter sample data (all illustrative) ---------- */

export interface Opportunity {
  id: string;
  company: string;
  role: string;
  meta: string;
  location: string;
  score: number;
  source: string;
  match: string[];
}

export const OPPORTUNITIES: Opportunity[] = [
  {
    id: 'linear',
    company: 'Linear',
    role: 'Backend Engineering Intern',
    meta: 'Remote · Summer 2027',
    location: 'Remote',
    score: 92,
    source: 'Greenhouse',
    match: ['TypeScript', 'PostgreSQL', 'Systems'],
  },
  {
    id: 'stripe',
    company: 'Stripe',
    role: 'Platform Engineering Intern',
    meta: 'Bengaluru · 6 months',
    location: 'Bengaluru',
    score: 87,
    source: 'Lever',
    match: ['Infrastructure', 'Go', 'Kubernetes'],
  },
  {
    id: 'notion',
    company: 'Notion',
    role: 'Product Engineer, New Grad',
    meta: 'Hybrid · Full time',
    location: 'Hybrid',
    score: 81,
    source: 'Ashby',
    match: ['React', 'Product', 'SQL'],
  },
  {
    id: 'vercel',
    company: 'Vercel',
    role: 'Developer Experience Intern',
    meta: 'Remote · Winter 2027',
    location: 'Remote',
    score: 79,
    source: 'SmartRecruiters',
    match: ['Docs', 'Node.js', 'DX'],
  },
];

export type PipelineStage = 'Saved' | 'Applied' | 'Assessment' | 'Interview' | 'Offer';

export const PIPELINE_STAGES: PipelineStage[] = [
  'Saved',
  'Applied',
  'Assessment',
  'Interview',
  'Offer',
];

export interface PipelineCard {
  id: string;
  company: string;
  role: string;
  stage: PipelineStage;
  updated: string;
  note: string;
}

export const INITIAL_PIPELINE: PipelineCard[] = [
  { id: 'linear', company: 'Linear', role: 'Backend Engineering Intern', stage: 'Assessment', updated: 'Today', note: 'Take-home: rate-limiter' },
  { id: 'stripe', company: 'Stripe', role: 'Platform Engineering Intern', stage: 'Interview', updated: 'Thu 14:00', note: 'System design round' },
  { id: 'notion', company: 'Notion', role: 'Product Engineer', stage: 'Applied', updated: '4d ago', note: 'Recruiter screen pending' },
  { id: 'vercel', company: 'Vercel', role: 'Developer Experience', stage: 'Saved', updated: '6d ago', note: 'Portfolio deck drafted' },
];

export const RESUME_BULLETS = [
  {
    id: 'tracing',
    text: 'Instrumented p99-latency tracing for the ingest path during a student co-op; found a 400 ms lock wait.',
    focus: true,
  },
  {
    id: 'batch',
    text: 'Replaced per-row writes with a batched queue; build time dropped from 9 minutes to 90 seconds.',
    focus: true,
  },
  {
    id: 'mentor',
    text: 'Mentored two first-year contributors through their first merged pull requests.',
    focus: false,
  },
];

export const RESUME_SKILLS = ['TypeScript', 'PostgreSQL', 'FastAPI', 'Redis', 'Docker'];

export const PREP_CHECKLIST = [
  { id: 'system', label: 'Re-derive the token-bucket math out loud', minutes: 20 },
  { id: 'story', label: 'Two stories: the 400 ms lock wait, and the ignored incident in chat', minutes: 25 },
  { id: 'questions', label: 'Ask about the on-call rotation and migration from Kafka to NATS', minutes: 10 },
];

export const ACTIVITY = [
  { date: 'Jun 3', label: 'Ranking snapshot: Linear, Backend Intern, score 92' },
  { date: 'Jun 6', label: 'Tailored resume variant against the posting, audit 3 fixes' },
  { date: 'Jun 9', label: 'Take-home submitted; 3 self-review questions logged' },
  { date: 'Jun 12', label: 'Assessment passed; system design scheduled' },
];

export const FUNNEL = [
  { label: 'Applied', value: 24, width: '100%' },
  { label: 'Screen', value: 11, width: '72%' },
  { label: 'Interview', value: 6, width: '48%' },
  { label: 'Offer', value: 2, width: '24%' },
];

export const SOURCES = [
  { label: 'Greenhouse', value: 14, width: '100%' },
  { label: 'Lever', value: 9, width: '64%' },
  { label: 'Ashby', value: 4, width: '29%' },
];
