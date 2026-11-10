export interface SourceLink {
  source: string;
  url: string;
  discovered_at?: string;
}

export interface ExtractedData {
  responsibilities?: string[];
  mandatory_technical_skills?: string[];
  preferred_skills?: string[];
  programming_languages?: string[];
  frameworks_libraries?: string[];
  tools_platforms?: string[];
  educational_requirements?: string;
  experience_requirements?: string;
  soft_skills?: string[];
  eligibility_restrictions?: string[];
  duration_details?: string;
  compensation_details?: string;
}

export interface SkillMatch {
  skill: string;
  evidence?: string;
  transferable_from?: string;
  reason?: string;
}

export interface MatchedProject {
  title: string;
  description: string;
  overlapping_tech: string[];
  relevance: string;
}

export interface ScoreBreakdown {
  required_technical_skills: number;
  projects_and_experience: number;
  education_and_eligibility: number;
  preferred_skills: number;
  location_and_availability: number;
  other_requirements: number;
}

export interface SkillGap {
  skill_name: string;
  priority: 'mandatory' | 'preferred' | 'optional' | string;
  current_evidence?: string | null;
  missing_evidence: string;
  suggested_learning_or_improvement: string;
}

export interface ExtractedRequirement {
  name: string;
  category: string;
  priority: 'mandatory' | 'preferred' | 'optional' | string;
  source_text?: string;
  evidence_reference?: string;
}

export interface RequirementMatchResult {
  requirement: ExtractedRequirement;
  status: 'strong_match' | 'partial_match' | 'weak_match' | 'no_evidence' | 'not_applicable' | string;
  matched_evidence: Array<{
    name: string;
    canonical_name?: string;
    evidence_text?: string;
    is_verified?: boolean;
    proficiency?: string | null;
  }>;
  evidence_strength: number;
  confidence: string;
  match_type: string;
  explanation: string;
  missing_evidence_description?: string | null;
}

export interface ProfileMatchResult {
  profile_match_score: number;
  category_scores: Record<string, number>;
  category_weights: Record<string, number>;
  requirement_matches: RequirementMatchResult[];
  skill_gaps: SkillGap[];
  eligibility_status: string;
  disqualifying_reasons: string[];
  scoring_explanation: string;
  candidate_content_hash?: string;
  opportunity_content_hash?: string;
  calculated_at?: string;
  is_stale: boolean;
  is_cached: boolean;
  engine_version: string;
  user_id?: number;
}

export interface RankingReasons {
  primary_factor: string;
  evaluation_state: 'not_evaluated' | 'stale' | 'evaluated_high' | 'evaluated_moderate' | 'evaluated_low' | string;
  match_score: number;
  is_evaluated: boolean;
  is_stale: boolean;
  eligibility_status: string;
  highlights: string[];
}

export interface DiscoverySearchResponse {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  page_items: number;
  snapshot_id?: string | null;
  next_cursor?: number | null;
  has_more?: boolean;
  items: OpportunityItem[];
}

export interface MatchAnalysis {
  match_score?: number;
  profile_match_score?: number;
  score_breakdown?: ScoreBreakdown;
  category_scores?: Record<string, number>;
  category_weights?: Record<string, number>;
  requirement_matches?: RequirementMatchResult[];
  skill_gaps?: SkillGap[];
  scoring_explanation?: string;
  is_stale?: boolean;
  is_cached?: boolean;
  engine_version?: string;
  skill_compatibility?: {
    strong: SkillMatch[];
    partial: SkillMatch[];
    missing: string[];
    unverified: string[];
  };
  experience_compatibility?: string;
  education_compatibility?: string;
  eligibility_status?: string;
  disqualifying_reasons?: string[];
  transferable_skills?: string[];
  relevant_projects?: MatchedProject[];
  recommendation_reasons?: string[];
}

export type Opportunity = OpportunityItem;

export interface OpportunityItem {
  id: number;
  title: string;
  normalized_title: string;
  internship_category?: string;
  company_name: string;
  location: string;
  normalized_location: string;
  workplace_type: string;
  internship_type?: string;
  work_mode?: string;
  employment_type: string;
  stipend_text?: string;
  min_stipend?: number;
  currency?: string;
  compensation_type?: string;
  duration_months?: number;
  posted_at?: string;
  deadline_at?: string;
  discovered_at?: string;
  last_fetched_at?: string;
  last_verified_at?: string;
  status: string;
  original_url: string;
  application_url?: string;
  source_platform: string;
  source_links?: SourceLink[];
  match_score: number;
  eligibility_status: string;
  quality_score?: number;
  quality_breakdown?: Record<string, any>;
  top_skills?: string[];
  is_saved: boolean;
  is_dismissed: boolean;
  is_applied: boolean;
  recommendation_impressions?: number;
  why_it_matches?: string[];
  matching_skills?: string[];
  missing_skills?: string[];
  eligibility_assessment?: {
    status: string;
    summary: string;
    disqualifying_reasons?: string[];
  };
  source_reliability?: {
    score: number;
    tier: string;
    badge: string;
    platform: string;
  };
  deadline_info?: {
    deadline_at?: string;
    deadline_formatted: string;
    days_left?: number;
    urgency: string;
  };
  based_on_project?: {
    project_title: string;
    matching_tech: string[];
    relevance_reason: string;
  };
  intelligence?: any;
  ranking_reasons?: RankingReasons;
  match_analysis?: MatchAnalysis;
  category_scores?: Record<string, number>;
  category_weights?: Record<string, number>;
  skill_gaps?: SkillGap[];
  requirement_matches?: RequirementMatchResult[];
  scoring_explanation?: string;
  match_freshness?: Record<string, any>;
  content_version?: number;
}

export interface SavedSearchItem {
  id: number;
  name: string;
  search_mode: string;
  query: string;
  filters: Record<string, any>;
  created_at: string;
  last_run_at?: string;
}

export interface SearchHistoryItem {
  id: number;
  query: string;
  search_mode: string;
  filters: Record<string, any>;
  results_count: number;
  created_at: string;
}

export interface CuratedRecommendationsResponse {
  best_matches: OpportunityItem[];
  recently_posted: OpportunityItem[];
  remote_opportunities: OpportunityItem[];
  aiml_internships: OpportunityItem[];
  fullstack_internships: OpportunityItem[];
  closing_soon: OpportunityItem[];
  based_on_projects: OpportunityItem[];
  meta: Record<string, any>;
}

export interface OpportunityDetail extends OpportunityItem {
  description: string;
  max_stipend?: number;
  stipend_period?: string;
  extracted_data?: ExtractedData;
  match_analysis?: MatchAnalysis;
  user_notes?: string;
}

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  page_items?: number;
  items: T[];
}

export interface SummaryMetrics {
  total_discovered: number;
  new_today: number;
  high_match: number;
  saved: number;
  expiring_soon: number;
}

export interface Company {
  id: number;
  name: string;
  website?: string;
  career_url?: string;
  industry?: string;
  hq_location?: string;
  ats_provider: string;
  ats_board_id?: string;
  company_size?: string;
  monitoring_status: string;
  last_sync_at?: string;
  opportunities_count: number;
  created_at: string;
  updated_at: string;
}

export interface JobSource {
  id: number;
  name: string;
  source_type: string;
  integration_method: string;
  connection_status: string;
  sync_frequency_hours: number;
  config_data: Record<string, any>;
  last_sync_at?: string;
  last_successful_sync_at?: string;
  last_attempted_sync_at?: string;
  last_sync_status?: string;
  last_error_message?: string;
  last_duration_seconds?: number;
  total_jobs_discovered: number;
  created_at: string;
}

export interface SyncLog {
  id: number;
  source_name: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  retrieved_count: number;
  new_count: number;
  duplicate_count: number;
  expired_count: number;
  relevant_count: number;
  error_count: number;
  error_details?: string;
  status: string;
}

export interface UserPreferences {
  id?: number;
  preferred_categories: string[];
  search_priorities: Array<{ priority: number; category: string }>;
  preferred_locations: string[];
  paid_only: boolean;
  allow_unpaid: boolean;
  min_stipend: number;
  preferred_duration_months: number;
  workplace_types: string[];
  max_experience_years: number;
  student_only: boolean;
  graduation_year: number;
  excluded_keywords: string[];
  excluded_companies: string[];
}

export interface CandidateProfile {
  id?: number;
  name: string;
  email: string;
  phone?: string;
  location?: string;
  bio?: string;
  degree: string;
  graduation_year: number;
  college: string;
  cgpa: number;
  github_url?: string;
  github_username?: string;
  github_data?: Record<string, any>;
  linkedin_url?: string;
  linkedin_data?: Record<string, any>;
  portfolio_url?: string;
  portfolio_data?: Record<string, any>;
  website_url?: string;
  skills: Array<{ name: string; level: string; category?: string; evidence?: string }>;
  projects: Array<{ title: string; description: string; tech_stack: string[]; url?: string; stars?: number }>;
  experience: Array<{ title: string; company: string; duration: string; description: string }>;
  certifications?: Array<{ name: string; issuer: string; year: string | number }>;
  achievements?: Array<{ title: string; organization: string; year: string | number }>;
  extracurriculars?: Array<{ role: string; organization: string; description: string }>;
  preferred_locations: string[];
  work_authorization: string;
  onboarding_status?: string;
  onboarding_step?: number;
  career_goals?: Record<string, any>;
  evidence_version?: number;
  updated_at?: string;
}

export interface ActionableRecommendation {
  priority: 'critical' | 'high' | 'medium' | 'low' | string;
  title: string;
  description: string;
  action_target: string;
}

export interface SkillSummaryItem {
  name: string;
  raw_name: string;
  category: string;
  level: string;
  status: 'verified' | 'unverified' | string;
  verification_source: string;
  evidence?: string;
}

export interface ProfileCompletenessAssessment {
  completeness_score: number;
  readiness_stage: 'getting_started' | 'core_evidence_ready' | 'high_confidence_readiness' | string;
  is_onboarded: boolean;
  onboarding_status: string;
  onboarding_step: number;
  category_scores: Record<string, { score: number; max: number }>;
  verified_evidence: string[];
  unverified_evidence: string[];
  missing_evidence: string[];
  actionable_recommendations: ActionableRecommendation[];
  skills_summary: {
    total: number;
    verified: number;
    unverified: number;
    items: SkillSummaryItem[];
  };
  has_master_resume: boolean;
  master_resume_version: number;
  projects_count: number;
  disclaimer: string;
}

export interface SkillTaxonomyResponse {
  categories: Record<string, string[]>;
  canonical_aliases: Record<string, string>;
}

export interface ResumeDocument {
  id: number;
  user_id: number;
  title: string;
  template_id: string;
  latex_content: string;
  target_opportunity_id?: number;
  target_company?: string;
  target_role?: string;
  is_master: boolean;
  version: number;
  tailored_insights?: Record<string, any>;
  pdf_path?: string;
  pdf_generated_at?: string;
  created_at: string;
  updated_at: string;
}

export interface ResumeTemplateItem {
  id: string;
  name: string;
  description: string;
  tags: string[];
  recommended_for: string;
}

export interface ResumeVersionItem {
  id: number;
  resume_id: number;
  version_number: number;
  title: string;
  template_id: string;
  latex_content: string;
  pdf_path?: string;
  change_summary?: string;
  created_at: string;
}

export interface QualityCheckItem {
  category: string;
  title: string;
  score: number;
  passed: boolean;
  details: string[];
}

export interface ResumeQualityAuditResult {
  ats_score: number;
  grade: string;
  timestamp: string;
  summary: string;
  checks: QualityCheckItem[];
}

export interface ResumeBulletRefinement {
  original: string;
  suggested: string;
  rationale: string;
}

export interface ResumeOptimizationProposal {
  opportunity_id: number;
  target_title: string;
  target_company: string;
  verified_matching_skills: string[];
  missing_job_keywords: string[];
  highlight_projects: Array<{
    title: string;
    overlapping_skills: string[];
    recommended_focus: string;
  }>;
  suggested_section_order: string[];
  section_order_rationale: string;
  bullet_refinements: ResumeBulletRefinement[];
  content_trim_suggestions: Array<{
    section: string;
    suggestion: string;
  }>;
  strict_zero_fabrication_confirmed: boolean;
}

export interface ResumeDiffLine {
  type: 'added' | 'removed' | 'unchanged';
  base_line_no: number | null;
  target_line_no: number | null;
  content: string;
}

export interface ResumeSectionChange {
  section: string;
  status: 'added' | 'removed' | 'reordered' | 'modified_content';
  rationale: string;
}

export interface ResumeDiffComparison {
  base_label: string;
  target_label: string;
  added_lines: number;
  removed_lines: number;
  diff_lines: ResumeDiffLine[];
  section_changes: ResumeSectionChange[];
  summary: string;
}


export interface InterviewJournalRecord {
  id: number;
  application_id?: number;
  company_name: string;
  role?: string;
  round_name: string;
  round_type: string;
  interview_format?: string;
  interview_date?: string;
  scheduled_at?: string;
  completed_at?: string;
  questions_asked: Array<{ 
    question: string; 
    topic?: string; 
    user_answer?: string; 
    feedback?: string;
    confidence?: number;
  }>;
  topics_covered?: string[];
  confidence_level?: number;
  interview_result?: string;
  interviewer_feedback?: string;
  personal_notes?: string;
  ai_feedback?: {
    strengths?: string[];
    weaknesses?: string[];
    action_items?: string[];
    summary?: string;
  };
  difficulty_rating: number;
  performance_rating: number;
  notes?: string;
  created_at: string;
}

export interface TechnicalQuestionItem {
  id: string;
  topic: string;
  question: string;
  expected_concepts: string[];
  difficulty: string;
}

export interface DsaQuestionItem {
  id: string;
  title: string;
  category: string;
  question: string;
  relevance: string;
  pattern: string;
  difficulty: string;
}

export interface ProjectQuestionItem {
  id: string;
  project_name: string;
  tech_stack: string;
  question: string;
  focus_areas: string[];
  candidate_evidence: string;
}

export interface BehavioralQuestionItem {
  id: string;
  competency: string;
  question: string;
  star_framework: string;
}

export interface HrQuestionItem {
  id: string;
  topic: string;
  question: string;
  recommended_angle: string;
}

export interface CompanyTopicItem {
  id: string;
  title: string;
  description: string;
  action_item: string;
}

export interface InterviewPrepPack {
  opportunity_id: number;
  company_name: string;
  role_title: string;
  technical_questions: TechnicalQuestionItem[];
  dsa_questions: DsaQuestionItem[];
  project_questions: ProjectQuestionItem[];
  behavioral_questions: BehavioralQuestionItem[];
  hr_questions: HrQuestionItem[];
  company_topics: CompanyTopicItem[];
  generated_at: string;
}

export interface PracticeQuestionEvaluation {
  score: number;
  clarity_rating: number;
  technical_depth: number;
  strengths: string[];
  improvement_areas: string[];
  ideal_answer_points: string[];
  verdict: string;
  evaluation_type: 'ai_generated_evaluation';
  evaluated_at: string;
}

export interface PracticeQuestionItem {
  id: string;
  category: string;
  question: string;
  context_or_hint?: string;
  user_answer?: string | null;
  ai_evaluation?: PracticeQuestionEvaluation | null;
}

export interface PracticeSessionItem {
  id: number;
  session_title: string;
  opportunity_id?: number | null;
  company_name?: string | null;
  role_title?: string | null;
  session_type: string;
  status: 'active' | 'completed' | 'abandoned';
  current_question_index: number;
  questions: PracticeQuestionItem[];
  overall_score?: number | null;
  final_feedback?: {
    summary?: string;
    strengths?: string[];
    improvements?: string[];
  } | null;
  created_at: string;
  updated_at: string;
}

export interface HistoricalInterviewAnalytics {
  total_interviews: number;
  avg_difficulty: number;
  avg_performance: number;
  avg_confidence: number;
  funnel_metrics: {
    pending: number;
    passed: number;
    rejected: number;
    offer: number;
    withdrawn: number;
    conversion_rate_pct: number;
  };
  repeatedly_difficult_topics: Array<{
    topic: string;
    frequency: number;
    severity: string;
  }>;
  strong_technical_areas: Array<{
    topic: string;
    consistency_score: number;
  }>;
  communication_improvement_areas: string[];
  knowledge_gaps: string[];
  qa_quality_score: number;
  preparation_priorities: string[];
  zero_records_note?: string;
}

export interface InterviewScheduleItem {
  id?: string;
  round_name: string;
  date: string;
  format?: 'virtual_video' | 'in_person' | 'phone_screen' | 'take_home' | string;
  interviewer?: string;
  meeting_link?: string;
  notes?: string;
  created_at?: string;
}

export interface ApplicationRecord {
  id: number;
  opportunity_id: number;
  company_name: string;
  job_title: string;
  original_url: string;
  status: string;
  applied_date?: string;
  match_score: number;
  resume_id?: number;
  resume_version_number?: number;
  submission_mode?: string;
  submission_verified?: boolean;
  follow_up_date?: string;
  salary_or_stipend?: string;
  cover_letter_text?: string;
  cover_letter_points?: string[];
  tailored_resume_summary?: string;
  recruiter_id?: number;
  recruiter_name?: string;
  recruiter_position?: string;
  recruiter_email?: string;
  recruiter_linkedin?: string;
  interview_schedule?: InterviewScheduleItem[];
  user_notes?: string;
  created_at: string;
  updated_at: string;
}

export interface RecruiterInteraction {
  id: string;
  type: 'email' | 'linkedin_message' | 'phone_screen' | 'interview' | 'note' | string;
  summary: string;
  date: string;
  follow_up_needed?: boolean;
  next_step?: string;
  logged_at?: string;
}

export interface RecruiterContact {
  id: number;
  name: string;
  email?: string;
  linkedin_url?: string;
  company?: string;
  position?: string;
  contact_source?: string;
  notes?: string;
  last_contact_date?: string;
  interaction_history?: RecruiterInteraction[];
  created_at?: string;
  updated_at?: string;
}

export interface ApplicationTimelineEvent {
  id: string;
  type?: 'stage_transition' | 'interview_scheduled' | 'touchpoint' | string;
  source_type?: string;
  event_category?: string;
  timestamp: string;
  title: string;
  company_name: string;
  job_title: string;
  application_id?: number;
  details?: string;
  description?: string;
  notes?: string;
  sender?: string;
  confidence_score?: number;
  review_status?: string;
  suggested_stage?: string;
  meeting_link?: string;
  meeting_platform?: string;
  badge_color?: string;
}

export interface ApplicationCalendarEvent {
  id: string;
  application_id?: number;
  title: string;
  company: string;
  date: string;
  time?: string;
  event_type: 'applied' | 'follow_up_due' | 'interview' | 'deadline' | string;
  status?: string;
  meeting_platform?: string;
  meeting_link?: string;
  time_zone?: string;
  details?: any;
}

export interface FollowUpAlertItem {
  application_id: number;
  opportunity_id?: number;
  company_name: string;
  job_title: string;
  applied_date?: string;
  days_elapsed?: number;
  status?: string;
  follow_up_date?: string;
  recruiter_name?: string;
  recruiter_email?: string;
  recommendation?: string;
  round_name?: string;
  date?: string;
  format?: string;
  interviewer?: string;
  meeting_link?: string;
  days_until?: number;
  deadline?: string;
  days_remaining?: number;
  original_url?: string;
}

export interface FollowUpIntelligenceData {
  stale_days_threshold: number;
  summary: {
    unanswered_count: number;
    follow_up_due_count: number;
    upcoming_interviews_count: number;
    approaching_deadlines_count: number;
  };
  unanswered_applications: FollowUpAlertItem[];
  follow_ups_due: FollowUpAlertItem[];
  upcoming_interviews: FollowUpAlertItem[];
  approaching_deadlines: FollowUpAlertItem[];
  generated_at: string;
}

export interface FollowUpDraftResponse {
  application_id: number;
  company_name: string;
  job_title: string;
  recipient_name: string;
  recipient_email: string;
  subject: string;
  body: string;
  tone: string;
  requires_user_approval: boolean;
  generated_at: string;
}

export interface SourcePerformanceItem {
  source: string;
  total_applied: number;
  responses: number;
  interviews: number;
  offers: number;
  response_rate_pct: number;
  interview_rate_pct: number;
}

export interface ResumePerformanceItem {
  resume_title: string;
  total_applied: number;
  responses: number;
  interviews: number;
  offers: number;
  response_rate_pct: number;
  interview_rate_pct: number;
}

export interface ApplicationAnalyticsData {
  pipeline_counts: {
    total_tracked: number;
    ready_to_apply: number;
    submitted_total: number;
    applied_pending: number;
    screening: number;
    interviewing: number;
    offered: number;
    rejected: number;
    withdrawn: number;
  };
  rates: {
    application_response_rate: number;
    interview_conversion_rate: number;
    offer_conversion_rate: number;
    average_response_time_days: number;
  };
  formula_definitions: {
    response_rate: string;
    interview_rate: string;
    offer_rate: string;
    response_time: string;
  };
  source_performance: SourcePerformanceItem[];
  resume_performance: ResumePerformanceItem[];
  computed_at: string;
}

export interface TruthLayers {
  verified_database: string[];
  extracted_external: string[];
  strategic_recommendations: string[];
  unknown_missing: string[];
}

export type IntelligenceWorkflowType = 
  | 'chat'
  | 'job_matching'
  | 'resume_intelligence'
  | 'interview_prep'
  | 'career_growth'
  | 'application_intelligence';

export interface IntelligenceReport {
  workflow: string;
  title: string;
  summary: string;
  metrics: Record<string, any>;
  details: Record<string, any>;
  truth_layers: TruthLayers;
}

export interface ChatMessage {
  id: number;
  conversation_id: number;
  sender: 'user' | 'assistant' | 'system';
  content: string;
  tool_calls?: Array<{ tool: string; result: any }>;
  truth_layers?: TruthLayers;
  created_at: string;
}

export interface ChatConversation {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface SankeyNode {
  id: number;
  name: string;
  stage_key: string;
  applications: Array<{ application_id: number; company_name: string; job_title: string; match_score: number }>;
  count: number;
}

export interface SankeyLink {
  source: number;
  target: number;
  source_name: string;
  target_name: string;
  value: number;
}

export interface SankeyData {
  empty: boolean;
  nodes: SankeyNode[];
  links: SankeyLink[];
  total_transitions: number;
  message?: string;
}

export interface NotificationItem {
  id: number;
  title: string;
  message: string;
  notification_type: string;
  opportunity_id?: number;
  is_read: boolean;
  created_at: string;
}

export interface AssistedApplicationDossier {
  opportunity_id: number;
  job_title: string;
  company_name: string;
  original_url: string;
  application_url: string;
  applicant_info: Record<string, any>;
  has_tailored_resume: boolean;
  selected_resume?: {
    id: number;
    title: string;
    pdf_url: string;
  };
  draft_cover_letter: string;
  standard_questions: Array<{ question: string; answer: string }>;
  submission_modes: Array<{ mode: string; label: string; description: string }>;
}

export interface PrioritizedActionItem {
  id: string;
  priority: 'urgent' | 'high' | 'medium';
  category: 'interview' | 'follow_up' | 'deadline' | 'resume' | 'apply';
  title: string;
  reason: string;
  action_label: string;
  action_type: 'navigate_tab' | 'tailor_resume' | 'prepare_apply';
  target_id?: number;
  target_tab?: string;
}

export interface UpcomingDeadlineItem {
  id: number;
  company_name: string;
  title: string;
  match_score: number;
  location: string;
  deadline_at: string;
  days_left: number;
  hours_left: number;
  urgency: 'urgent' | 'high' | 'medium';
  application_status?: string;
}

export interface ActivityTimelineEvent {
  type: string;
  timestamp: string;
  title: string;
  description: string;
  target_tab: string;
  target_id?: number;
  badge?: string;
}

export interface CommandCenterData {
  date_range: string;
  pipeline_summary: {
    total_applications: number;
    stages_count: Record<string, number>;
    response_rate: number;
    interview_rate: number;
    offer_rate: number;
    overdue_follow_ups_count: number;
  };
  prioritized_actions: PrioritizedActionItem[];
  upcoming_deadlines: UpcomingDeadlineItem[];
  follow_ups_due: Array<{
    application_id: number;
    opportunity_id: number;
    company_name: string;
    job_title: string;
    status: string;
    applied_date?: string;
    follow_up_date?: string;
    days_waiting: number;
  }>;
  recently_discovered_relevant: OpportunityItem[];
  readiness_diagnostics: {
    interview: {
      total_logged: number;
      average_performance: number;
      average_difficulty: number;
      strengths: string[];
      weaknesses: string[];
    };
    resume: {
      total_resumes: number;
      tailored_count: number;
      compiled_pdf_rate: number;
      missing_resume_apps_count: number;
    };
    skills: {
      verified_skills_count: number;
      market_demanded_mastered: Array<{ skill: string; frequency: number }>;
      missing_high_roi_gaps: Array<{ skill: string; frequency: number }>;
    };
  };
  strategic_focus: {
    focus_area: string;
    reason: string;
    milestone_project: string;
    weekly_pace: string;
  };
  activity_timeline: ActivityTimelineEvent[];
}

export interface IntegrationConnectionItem {
  id: number;
  provider: 'google' | 'microsoft' | string;
  account_email: string;
  account_name?: string;
  scopes: string[];
  connection_status: 'connected' | 'expired' | 'revoked' | 'disconnected' | 'error' | 'not_configured' | string;
  token_expires_at?: string;
  last_sync_at?: string;
  last_sync_error?: string;
  created_at?: string;
}

export interface ProviderStatusItem {
  provider: string;
  name: string;
  is_configured: boolean;
  connection?: IntegrationConnectionItem | null;
  status: string;
  minimum_scopes: string[];
}

export interface IntegrationsStatusResponse {
  providers: {
    google: ProviderStatusItem;
    microsoft: ProviderStatusItem;
  };
  total_connected: number;
}

export interface EmailMessageRecord {
  id: number;
  connection_id?: number;
  application_id?: number;
  application_company?: string;
  application_title?: string;
  application_status?: string;
  provider_message_id: string;
  thread_id?: string;
  sender: string;
  sender_email: string;
  sender_name?: string;
  recipient?: string;
  subject: string;
  snippet?: string;
  body_plain?: string;
  received_at: string;
  detected_category: string;
  confidence_score: number;
  is_low_confidence: boolean;
  extracted_data: {
    company_name?: string;
    role_title?: string;
    meeting_platform?: string;
    meeting_link?: string;
    deadline_text?: string;
    action_required?: string;
    is_low_confidence?: boolean;
  };
  suggested_stage?: string;
  review_status: 'pending_review' | 'approved' | 'dismissed' | string;
  user_action_at?: string;
  created_at?: string;
}

export interface EmailMessagesResponse {
  items: EmailMessageRecord[];
  total: number;
  page: number;
  page_size: number;
  pending_review_count: number;
}

export interface AIProviderTelemetry {
  total_requests: number;
  successful_requests: number;
  failed_requests: number;
  success_rate_pct: number;
  avg_latency_ms: number;
  last_latency_ms: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  last_call_at: string | null;
  last_error: string | null;
  last_error_at: string | null;
}

export interface AIProviderInfo {
  name: string;
  role: string;
  configured: boolean;
  model: string;
  base_url?: string;
  status_message: string;
  telemetry: AIProviderTelemetry;
}

export interface AIHealthStatusResponse {
  status: 'operational' | 'degraded';
  providers: {
    groq: AIProviderInfo;
    ollama: AIProviderInfo;
  };
  routing_policy: Record<string, string>;
  privacy_guarantee: string;
  timestamp: string;
}

export interface TestProviderResponse {
  provider: string;
  status: 'online' | 'offline' | 'unconfigured' | string;
  latency_ms: number;
  message: string;
}
