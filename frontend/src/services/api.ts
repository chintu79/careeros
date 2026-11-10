import { 
  AIHealthStatusResponse, 
  TestProviderResponse, 
  DiscoverySearchResponse, 
  ProfileMatchResult, 
  OpportunityDetail, 
  SummaryMetrics, 
  CandidateProfile,
  ProfileCompletenessAssessment,
  SkillTaxonomyResponse
} from "../types";

export const API_BASE = (typeof window !== "undefined" && window.location.port === "5174")
  ? "/api"
  : (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8005/api");

const TOKEN_KEY = "careeros_auth_token";
const ACTIVE_USER_KEY = "careeros_active_user_id";

export function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAuthToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  } else {
    localStorage.removeItem(TOKEN_KEY);
  }
}

export function getActiveUserId(): number {
  if (typeof window === "undefined") return 1;
  const stored = localStorage.getItem(ACTIVE_USER_KEY);
  return stored ? parseInt(stored, 10) || 1 : 1;
}

export function setActiveUserId(userId: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(ACTIVE_USER_KEY, String(userId));
}

export async function obtainAuthToken(userId: number = 1): Promise<string> {
  const url = `${API_BASE}/auth/token`;
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId })
  });
  if (!res.ok) {
    throw new Error(`Failed to obtain auth token for user ${userId}`);
  }
  const data = await res.json();
  setAuthToken(data.access_token);
  setActiveUserId(userId);
  return data.access_token;
}

export async function ensureAuthenticated(userId?: number): Promise<string> {
  const currentToken = getAuthToken();
  const currentUserId = getActiveUserId();
  const targetId = userId ?? currentUserId;
  if (currentToken && targetId === currentUserId) {
    return currentToken;
  }
  return obtainAuthToken(targetId);
}

let currentRequestEpoch = 0;

export function getNextRequestEpoch(): number {
  return ++currentRequestEpoch;
}

export function getCurrentRequestEpoch(): number {
  return currentRequestEpoch;
}

export function clearAuth(): void {
  if (typeof window === "undefined") return;
  if (searchAbortController) {
    searchAbortController.abort();
    searchAbortController = null;
  }
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ACTIVE_USER_KEY);
}

export async function switchCandidate(userId: number): Promise<string> {
  if (searchAbortController) {
    searchAbortController.abort();
    searchAbortController = null;
  }
  getNextRequestEpoch();
  setAuthToken(null);
  setActiveUserId(userId);
  return obtainAuthToken(userId);
}

export class SessionExpiredError extends Error {
  restartRequired: boolean;
  code: string;
  constructor(message = "Pagination session has expired or is invalid. Please restart search from page 1.") {
    super(message);
    this.name = "SessionExpiredError";
    this.restartRequired = true;
    this.code = "PAGINATION_SESSION_EXPIRED";
  }
}

export async function apiRequest<T = any>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Accept": "application/json",
    ...(options.headers as Record<string, string> || {})
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  if (options.body && typeof options.body === "string" && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  const cleanEndpoint = endpoint.startsWith("/") ? endpoint : `/${endpoint}`;
  const fullUrl = endpoint.startsWith("http") ? endpoint : `${API_BASE}${cleanEndpoint}`;

  const res = await fetch(fullUrl, { ...options, headers });

  if (res.status === 410) {
    let detail = "Pagination session has expired or is invalid. Please restart search from page 1.";
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {}
    throw new SessionExpiredError(detail);
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {}
    throw new Error(detail);
  }

  return res.json();
}

let searchAbortController: AbortController | null = null;

// --- OPPORTUNITIES ---
export async function fetchOpportunities(
  params: Record<string, any> = {},
  options?: { signal?: AbortSignal; cancelPrevious?: boolean }
): Promise<DiscoverySearchResponse> {
  if (options?.cancelPrevious !== false && searchAbortController) {
    searchAbortController.abort();
  }
  const controller = new AbortController();
  if (options?.cancelPrevious !== false) {
    searchAbortController = controller;
  }

  const query = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== "") {
      query.append(key, String(val));
    }
  });

  try {
    const data = await apiRequest<DiscoverySearchResponse>(
      `/opportunities?${query.toString()}`,
      { signal: options?.signal || controller.signal }
    );
    return data;
  } finally {
    if (searchAbortController === controller) {
      searchAbortController = null;
    }
  }
}

export async function fetchSummaryMetrics() {
  return apiRequest<SummaryMetrics>("/opportunities/summary-metrics");
}

export async function fetchOpportunityDetail(id: number) {
  return apiRequest<OpportunityDetail>(`/opportunities/${id}`);
}

export async function evaluateOpportunityMatch(id: number, forceRefresh = false, useAi = false) {
  return apiRequest<ProfileMatchResult>(`/opportunities/${id}/evaluate-match`, {
    method: "POST",
    body: JSON.stringify({ force_refresh: forceRefresh, use_ai: useAi })
  });
}

export async function toggleSaveOpportunity(id: number) {
  return apiRequest<{ id: number; is_saved: boolean }>(`/opportunities/${id}/save`, { method: "POST" });
}

export async function dismissOpportunity(id: number) {
  return apiRequest<{ id: number; is_dismissed: boolean }>(`/opportunities/${id}/dismiss`, { method: "POST" });
}

export async function undismissOpportunity(id: number) {
  return apiRequest<{ id: number; is_dismissed: boolean }>(`/opportunities/${id}/undismiss`, { method: "POST" });
}

export async function fetchCuratedRecommendations(limitPerSection = 6) {
  return apiRequest(`/opportunities/recommendations?limit_per_section=${limitPerSection}`);
}

export async function submitOpportunityFeedback(id: number, feedbackType: string, reasonNote?: string) {
  return apiRequest(`/opportunities/${id}/feedback`, {
    method: "POST",
    body: JSON.stringify({ feedback_type: feedbackType, reason_note: reasonNote })
  });
}

// --- SEARCHES (SAVED & HISTORY) ---
export async function fetchSavedSearches() {
  const res = await fetch(`${API_BASE}/searches/saved`);
  if (!res.ok) throw new Error("Failed to fetch saved searches");
  return res.json();
}

export async function createSavedSearch(data: { name: string; search_mode?: string; query?: string; filters?: Record<string, any> }) {
  const res = await fetch(`${API_BASE}/searches/saved`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to save search");
  return res.json();
}

export async function deleteSavedSearch(id: number) {
  const res = await fetch(`${API_BASE}/searches/saved/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete saved search");
  return res.json();
}

export async function fetchSearchHistory(limit = 15) {
  const res = await fetch(`${API_BASE}/searches/history?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch search history");
  return res.json();
}

export async function clearSearchHistory() {
  const res = await fetch(`${API_BASE}/searches/history`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to clear search history");
  return res.json();
}

// --- IMPORT ---
export async function importFromUrl(url: string) {
  const res = await fetch(`${API_BASE}/import/url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to import URL");
  }
  return res.json();
}

export async function importFromPaste(data: {
  title: string;
  company_name: string;
  location?: string;
  description: string;
  stipend_text?: string;
  original_url?: string;
}) {
  const res = await fetch(`${API_BASE}/import/paste`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to import pasted text");
  }
  return res.json();
}export async function importFromEmailAlert(email_text: string, platform_hint = "internshala") {
  const res = await fetch(`${API_BASE}/import/email-alert`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email_text, platform_hint })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to import email alert");
  }
  return res.json();
}

// --- RESUME STUDIO ---
export async function fetchResumes(params: { page?: number; page_size?: number; is_master?: boolean } = {}) {
  const query = new URLSearchParams();
  if (params.page) query.append("page", String(params.page));
  if (params.page_size) query.append("page_size", String(params.page_size));
  if (params.is_master !== undefined) query.append("is_master", String(params.is_master));
  return apiRequest(`/resumes?${query.toString()}`);
}

export async function fetchMasterResume() {
  return apiRequest("/resumes/master");
}

export async function fetchResumeDetail(id: number) {
  return apiRequest(`/resumes/${id}`);
}

export async function createResume(data: { title: string; template_id?: string; latex_content?: string; is_master?: boolean }) {
  return apiRequest("/resumes", {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export async function updateResume(id: number, data: { title?: string; template_id?: string; latex_content?: string }) {
  return apiRequest(`/resumes/${id}`, {
    method: "PUT",
    body: JSON.stringify(data)
  });
}

export async function deleteResume(id: number) {
  return apiRequest(`/resumes/${id}`, { method: "DELETE" });
}

export async function compileResumePdf(id: number) {
  return apiRequest(`/resumes/${id}/compile`, { method: "POST" });
}

export async function fetchResumeTemplates() {
  return apiRequest("/resumes/templates");
}

export async function renameResume(id: number, title: string) {
  return apiRequest(`/resumes/${id}/rename`, {
    method: "POST",
    body: JSON.stringify({ title })
  });
}

export async function duplicateResume(id: number) {
  return apiRequest(`/resumes/${id}/duplicate`, { method: "POST" });
}

export async function fetchResumeVersions(id: number) {
  return apiRequest(`/resumes/${id}/versions`);
}

export async function createResumeVersionSnapshot(id: number, change_summary = "Manual snapshot checkpoint") {
  return apiRequest(`/resumes/${id}/versions`, {
    method: "POST",
    body: JSON.stringify({ change_summary })
  });
}

export async function restoreResumeVersion(id: number, version_id: number) {
  return apiRequest(`/resumes/${id}/versions/${version_id}/restore`, {
    method: "POST"
  });
}

export async function compareResumeVersions(id: number, req: { target_version_id?: number; compare_with_master?: boolean }) {
  return apiRequest(`/resumes/${id}/compare`, {
    method: "POST",
    body: JSON.stringify(req)
  });
}

export async function auditResumeQuality(id: number) {
  return apiRequest(`/resumes/${id}/quality-check`, {
    method: "POST"
  });
}

export async function requestResumeOptimization(id: number, opportunity_id: number) {
  return apiRequest(`/resumes/${id}/optimize`, {
    method: "POST",
    body: JSON.stringify({ opportunity_id })
  });
}

export async function applyResumeOptimization(id: number, latex_content: string, change_summary = "Applied user-approved AI optimizations") {
  return apiRequest(`/resumes/${id}/apply-optimization`, {
    method: "POST",
    body: JSON.stringify({ latex_content, change_summary })
  });
}

export async function tailorResume(opportunity_id: number, template_id = "minimal_professional") {
  return apiRequest("/resumes/tailor", {
    method: "POST",
    body: JSON.stringify({ opportunity_id, template_id })
  });
}

// --- APPLICATIONS & TRACKER ---
export async function fetchApplications(params: { page?: number; page_size?: number; status?: string; search?: string } = {}) {
  const query = new URLSearchParams();
  if (params.page) query.append("page", String(params.page));
  if (params.page_size) query.append("page_size", String(params.page_size));
  if (params.status) query.append("status", params.status);
  if (params.search) query.append("search", params.search);
  const res = await fetch(`${API_BASE}/applications?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch applications");
  return res.json();
}

export async function fetchApplicationDetail(id: number) {
  const res = await fetch(`${API_BASE}/applications/${id}`);
  if (!res.ok) throw new Error("Failed to fetch application detail");
  return res.json();
}

export async function handoffApplication(data: {
  opportunity_id: number;
  initial_status?: string;
  user_notes?: string;
  recruiter_name?: string;
  recruiter_email?: string;
  recruiter_linkedin?: string;
}) {
  const res = await fetch(`${API_BASE}/applications/handoff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to hand off application");
  }
  return res.json();
}

export async function prepareAssistedApplication(opportunity_id: number) {
  const res = await fetch(`${API_BASE}/applications/prepare/${opportunity_id}`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to prepare application");
  }
  return res.json();
}

export async function submitAssistedApplication(data: {
  opportunity_id: number;
  submission_mode?: string;
  resume_id?: number;
  notes?: string;
  submission_verified?: boolean;
}) {
  const res = await fetch(`${API_BASE}/applications/submit-assisted`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to record submission");
  }
  return res.json();
}

export async function updateApplication(id: number, data: any) {
  const res = await fetch(`${API_BASE}/applications/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to update application");
  return res.json();
}

export async function deleteApplication(id: number) {
  const res = await fetch(`${API_BASE}/applications/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete application");
  return res.json();
}

export async function fetchApplicationAnalytics() {
  const res = await fetch(`${API_BASE}/applications/analytics`);
  if (!res.ok) throw new Error("Failed to fetch application analytics");
  return res.json();
}

export async function fetchApplicationTimeline(limit = 50, filterCategory = "all", applicationId?: number) {
  const query = new URLSearchParams();
  query.append("limit", String(limit));
  if (filterCategory && filterCategory !== "all") query.append("filter_category", filterCategory);
  if (applicationId) query.append("application_id", String(applicationId));
  const res = await fetch(`${API_BASE}/applications/timeline?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch application timeline");
  const data = await res.json();
  return data?.events || data || [];
}

export async function fetchApplicationCalendar(startDate?: string, endDate?: string) {
  const query = new URLSearchParams();
  if (startDate) query.append("start_date", startDate);
  if (endDate) query.append("end_date", endDate);
  const res = await fetch(`${API_BASE}/applications/calendar?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch application calendar");
  const data = await res.json();
  return data?.events || data || [];
}

export async function fetchFollowUpAlerts(staleDays = 7) {
  const res = await fetch(`${API_BASE}/applications/follow-ups?stale_days=${staleDays}`);
  if (!res.ok) throw new Error("Failed to fetch follow-up alerts");
  return res.json();
}

export async function generateFollowUpEmail(id: number, tone = "inquisitive", customNote?: string) {
  const res = await fetch(`${API_BASE}/applications/${id}/generate-follow-up`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tone, custom_note: customNote })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to generate follow-up email draft");
  }
  return res.json();
}

export async function approveFollowUpEmail(id: number, advanceDays = 7, notes = "Follow-up email dispatched") {
  const res = await fetch(`${API_BASE}/applications/${id}/approve-follow-up`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ advance_days: advanceDays, notes })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve follow-up email");
  }
  return res.json();
}

export async function scheduleApplicationInterview(id: number, data: {
  round_name: string;
  date: string;
  format?: string;
  interviewer?: string;
  meeting_link?: string;
  notes?: string;
}) {
  const res = await fetch(`${API_BASE}/applications/${id}/schedule-interview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to schedule interview");
  }
  return res.json();
}

// --- RECRUITER CRM ---
export async function fetchRecruiters(params: { page?: number; page_size?: number; search?: string; company?: string } = {}) {
  const query = new URLSearchParams();
  if (params.page) query.append("page", String(params.page));
  if (params.page_size) query.append("page_size", String(params.page_size));
  if (params.search) query.append("search", params.search);
  if (params.company) query.append("company", params.company);
  const res = await fetch(`${API_BASE}/recruiters?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch recruiters");
  return res.json();
}

export async function createRecruiter(data: {
  name: string;
  email?: string;
  linkedin_url?: string;
  company?: string;
  position?: string;
  contact_source?: string;
  notes?: string;
}) {
  const res = await fetch(`${API_BASE}/recruiters`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to add recruiter");
  }
  return res.json();
}

export async function getRecruiterDetail(id: number) {
  const res = await fetch(`${API_BASE}/recruiters/${id}`);
  if (!res.ok) throw new Error("Failed to fetch recruiter detail");
  return res.json();
}

export async function updateRecruiter(id: number, data: any) {
  const res = await fetch(`${API_BASE}/recruiters/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to update recruiter");
  return res.json();
}

export async function deleteRecruiter(id: number) {
  const res = await fetch(`${API_BASE}/recruiters/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete recruiter");
  return res.json();
}

export async function logRecruiterInteraction(id: number, data: {
  interaction_type: string;
  summary: string;
  date?: string;
  follow_up_needed?: boolean;
  next_step?: string;
}) {
  const res = await fetch(`${API_BASE}/recruiters/${id}/interactions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to log interaction");
  }
  return res.json();
}

// --- INTERVIEW JOURNAL ---
export async function fetchInterviews(params: { page?: number; page_size?: number; company_name?: string; round_type?: string } = {}) {
  const query = new URLSearchParams();
  if (params.page) query.append("page", String(params.page));
  if (params.page_size) query.append("page_size", String(params.page_size));
  if (params.company_name) query.append("company_name", params.company_name);
  if (params.round_type) query.append("round_type", params.round_type);
  const res = await fetch(`${API_BASE}/interviews?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch interview entries");
  return res.json();
}

export async function createInterview(data: any) {
  const res = await fetch(`${API_BASE}/interviews`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to create interview record");
  return res.json();
}

export async function updateInterview(id: number, data: any) {
  const res = await fetch(`${API_BASE}/interviews/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to update interview");
  return res.json();
}

export async function deleteInterview(id: number) {
  const res = await fetch(`${API_BASE}/interviews/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete interview");
  return res.json();
}

export async function analyzeInterviewAI(id: number) {
  const res = await fetch(`${API_BASE}/interviews/${id}/ai-analysis`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to analyze interview");
  return res.json();
}

// --- INTERVIEW INTELLIGENCE & PRACTICE SIMULATOR ---
export async function fetchInterviewPrep(opportunity_id: number) {
  const res = await fetch(`${API_BASE}/interviews/prep?opportunity_id=${opportunity_id}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to generate interview preparation materials");
  }
  return res.json();
}

export async function fetchInterviewAnalytics() {
  const res = await fetch(`${API_BASE}/interviews/analytics`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch historical interview analytics");
  }
  return res.json();
}

export async function fetchPracticeSessions(params: { page?: number; page_size?: number } = {}) {
  const query = new URLSearchParams();
  if (params.page) query.append("page", String(params.page));
  if (params.page_size) query.append("page_size", String(params.page_size));
  const res = await fetch(`${API_BASE}/interviews/practice/sessions?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch mock practice sessions");
  return res.json();
}

export async function createPracticeSession(data: {
  session_title?: string;
  opportunity_id?: number;
  company_name?: string;
  role_title?: string;
  session_type?: string;
}) {
  const res = await fetch(`${API_BASE}/interviews/practice/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to create practice session");
  }
  return res.json();
}

export async function fetchPracticeSessionDetail(sessionId: number) {
  const res = await fetch(`${API_BASE}/interviews/practice/sessions/${sessionId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch practice session detail");
  }
  return res.json();
}

export async function evaluatePracticeQuestion(sessionId: number, questionId: string, userAnswer: string) {
  const res = await fetch(`${API_BASE}/interviews/practice/sessions/${sessionId}/evaluate-question`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question_id: questionId, user_answer: userAnswer })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to evaluate answer");
  }
  return res.json();
}

export async function completePracticeSession(sessionId: number) {
  const res = await fetch(`${API_BASE}/interviews/practice/sessions/${sessionId}/complete`, {
    method: "POST"
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to complete practice session");
  }
  return res.json();
}

// --- AI CHAT ASSISTANT ---
export async function fetchConversations() {
  const res = await fetch(`${API_BASE}/chat/conversations`);
  if (!res.ok) throw new Error("Failed to fetch chat conversations");
  return res.json();
}

export async function createConversation(title = "New Career Chat") {
  const res = await fetch(`${API_BASE}/chat/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title })
  });
  if (!res.ok) throw new Error("Failed to create conversation");
  return res.json();
}

export async function fetchConversationDetail(id: number) {
  const res = await fetch(`${API_BASE}/chat/conversations/${id}`);
  if (!res.ok) throw new Error("Failed to fetch conversation");
  return res.json();
}

export async function deleteConversation(id: number) {
  const res = await fetch(`${API_BASE}/chat/conversations/${id}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete conversation");
  return res.json();
}

export async function sendChatMessage(
  conversation_id: number, 
  content: string, 
  options?: { opportunity_id?: number; workflow?: string }
) {
  const payload: any = { content };
  if (options?.opportunity_id) payload.opportunity_id = options.opportunity_id;
  if (options?.workflow) payload.workflow = options.workflow;

  const res = await fetch(`${API_BASE}/chat/conversations/${conversation_id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Chat message failed");
  }
  return res.json();
}

export async function runJobMatchingWorkflow(opportunity_id: number) {
  const res = await fetch(`${API_BASE}/chat/workflows/job-matching`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ opportunity_id })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Job matching workflow failed");
  }
  return res.json();
}

export async function runResumeIntelligenceWorkflow(opportunity_id: number) {
  const res = await fetch(`${API_BASE}/chat/workflows/resume-intelligence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ opportunity_id })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Resume intelligence workflow failed");
  }
  return res.json();
}

export async function runInterviewPrepWorkflow(opportunity_id: number, interview_id?: number) {
  const res = await fetch(`${API_BASE}/chat/workflows/interview-prep`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ opportunity_id, interview_id })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Interview prep workflow failed");
  }
  return res.json();
}

export async function runCareerGrowthWorkflow() {
  const res = await fetch(`${API_BASE}/chat/workflows/career-growth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Career growth workflow failed");
  }
  return res.json();
}

export async function runApplicationIntelligenceWorkflow() {
  const res = await fetch(`${API_BASE}/chat/workflows/application-intelligence`, {
    method: "POST",
    headers: { "Content-Type": "application/json" }
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Application intelligence workflow failed");
  }
  return res.json();
}

// --- CANDIDATE PROFILE & INTEGRATIONS ---
export async function fetchCandidateProfile() {
  return apiRequest<CandidateProfile>("/candidate");
}

export async function updateCandidateProfile(data: any) {
  return apiRequest<CandidateProfile>("/candidate", {
    method: "PUT",
    body: JSON.stringify(data)
  });
}

export async function syncGitHubProfile(username: string) {
  const res = await fetch(`${API_BASE}/candidate/integrations/github`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to sync GitHub");
  }
  return res.json();
}

export async function syncPortfolio(url: string) {
  return apiRequest('/candidate/integrations/portfolio', {
    method: "POST",
    body: JSON.stringify({ url })
  });
}

export async function importLinkedInData(data: any) {
  return apiRequest('/candidate/integrations/linkedin', {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export async function parseResumeUpload(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const token = getAuthToken();
  const headers: Record<string, string> = {};
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}/candidate/integrations/parse-resume`, {
    method: "POST",
    headers,
    body: formData
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to parse resume file");
  }
  return res.json();
}

export async function approveIntegrations(data: { 
  approved_skills?: any[]; 
  approved_projects?: any[];
  candidate_updates?: Record<string, any>;
}) {
  return apiRequest('/candidate/integrations/approve', {
    method: "POST",
    body: JSON.stringify(data)
  });
}

// --- CANDIDATE ONBOARDING & PROFILE COMPLETENESS (Iteration 2.8) ---
export async function fetchProfileCompleteness(): Promise<ProfileCompletenessAssessment> {
  return apiRequest<ProfileCompletenessAssessment>("/candidate/completeness");
}

export async function updateOnboardingProgress(data: {
  step: number;
  status?: string;
  career_goals?: Record<string, any>;
  profile_data?: Record<string, any>;
}): Promise<{ status: string; onboarding_step: number; onboarding_status: string; candidate: CandidateProfile }> {
  return apiRequest<{ status: string; onboarding_step: number; onboarding_status: string; candidate: CandidateProfile }>(
    "/candidate/onboarding-progress",
    {
      method: "PUT",
      body: JSON.stringify(data)
    }
  );
}

export async function completeOnboarding(): Promise<{
  status: string;
  message: string;
  evidence_version: number;
  readiness: ProfileCompletenessAssessment;
}> {
  return apiRequest<{
    status: string;
    message: string;
    evidence_version: number;
    readiness: ProfileCompletenessAssessment;
  }>("/candidate/complete-onboarding", {
    method: "POST"
  });
}

export async function fetchSkillsTaxonomy(): Promise<SkillTaxonomyResponse> {
  const res = await fetch(`${API_BASE}/candidate/skills/taxonomy`);
  if (!res.ok) throw new Error("Failed to fetch skills taxonomy");
  return res.json();
}

export async function addCandidateSkill(skill: {
  name: string;
  category?: string;
  level?: string;
  evidence?: string;
}): Promise<CandidateProfile> {
  return apiRequest<CandidateProfile>("/candidate/skills", {
    method: "POST",
    body: JSON.stringify(skill)
  });
}

export async function deleteCandidateSkill(skillName: string): Promise<CandidateProfile> {
  return apiRequest<CandidateProfile>(`/candidate/skills/${encodeURIComponent(skillName)}`, {
    method: "DELETE"
  });
}

export async function addCandidateProject(project: {
  title: string;
  description: string;
  tech_stack?: string[];
  url?: string;
  stars?: number;
  index?: number;
}): Promise<CandidateProfile> {
  return apiRequest<CandidateProfile>("/candidate/projects", {
    method: "POST",
    body: JSON.stringify(project)
  });
}

export async function deleteCandidateProject(projectIndex: number): Promise<CandidateProfile> {
  return apiRequest<CandidateProfile>(`/candidate/projects/${projectIndex}`, {
    method: "DELETE"
  });
}


// --- ANALYTICS & SANKEY ---
export async function fetchAnalytics() {
  const res = await fetch(`${API_BASE}/analytics`);
  if (!res.ok) throw new Error("Failed to fetch analytics");
  return res.json();
}

export async function fetchSankeyData(source = "all", category = "all") {
  const query = new URLSearchParams();
  if (source) query.append("source_platform", source);
  if (category) query.append("category", category);
  const res = await fetch(`${API_BASE}/analytics/sankey?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch Sankey pipeline data");
  return res.json();
}

// --- SOURCES & LIVE SYNC ---
export async function fetchSources() {
  const res = await fetch(`${API_BASE}/sources`);
  if (!res.ok) throw new Error("Failed to fetch sources");
  return res.json();
}

export async function fetchLiveSyncProgress() {
  const res = await fetch(`${API_BASE}/sources/sync-progress`);
  if (!res.ok) throw new Error("Failed to fetch sync progress");
  return res.json();
}

export async function triggerParallelSync() {
  const res = await fetch(`${API_BASE}/sources/sync-all`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger sync");
  return res.json();
}

export async function updateSource(id: number, data: any) {
  const res = await fetch(`${API_BASE}/sources/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to update source");
  return res.json();
}

export async function syncAllSources() {
  const res = await fetch(`${API_BASE}/sources/sync-all`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger sources sync");
  return res.json();
}

export async function syncSource(id: number) {
  const res = await fetch(`${API_BASE}/sources/${id}/sync`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to sync source");
  return res.json();
}

export async function testSourceConnection(id: number) {
  const res = await fetch(`${API_BASE}/sources/${id}/test`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to test connection");
  return res.json();
}

export async function fetchSyncLogs() {
  const res = await fetch(`${API_BASE}/sources/logs`);
  if (!res.ok) throw new Error("Failed to fetch sync logs");
  return res.json();
}

export async function retryFailedSources() {
  const res = await fetch(`${API_BASE}/sources/retry-failed`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to retry failed sources");
  return res.json();
}

export async function fetchSchedulerStatus() {
  const res = await fetch(`${API_BASE}/sources/scheduler/status`);
  if (!res.ok) throw new Error("Failed to fetch scheduler status");
  return res.json();
}

export async function toggleSchedulerState(enabled: boolean) {
  const res = await fetch(`${API_BASE}/sources/scheduler/toggle?enabled=${enabled}`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to toggle scheduler state");
  return res.json();
}

export async function fetchSourceEfficacyAnalytics() {
  const res = await fetch(`${API_BASE}/analytics/source-efficacy`);
  if (!res.ok) throw new Error("Failed to fetch source efficacy metrics");
  return res.json();
}

// --- COMPANIES ---
export async function fetchCompanies(params: { page?: number; page_size?: number; search?: string; ats?: string } = {}) {
  const query = new URLSearchParams();
  if (params.page) query.append("page", String(params.page));
  if (params.page_size) query.append("page_size", String(params.page_size));
  if (params.search) query.append("search", params.search);
  if (params.ats) query.append("ats_provider", params.ats);
  const res = await fetch(`${API_BASE}/companies?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch companies");
  return res.json();
}

export async function detectAtsFromUrl(career_url: string) {
  const res = await fetch(`${API_BASE}/companies/detect-ats`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ career_url })
  });
  if (!res.ok) throw new Error("Failed to auto-detect ATS provider");
  return res.json();
}

export async function addCompany(data: any) {
  const res = await fetch(`${API_BASE}/companies`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to add company");
  return res.json();
}

export async function syncSingleCompany(id: number) {
  const res = await fetch(`${API_BASE}/companies/${id}/sync`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to sync company");
  return res.json();
}

// --- PREFERENCES & NOTIFICATIONS ---
export async function fetchPreferences() {
  const res = await fetch(`${API_BASE}/preferences`);
  if (!res.ok) throw new Error("Failed to fetch preferences");
  return res.json();
}

export async function updatePreferences(data: any) {
  const res = await fetch(`${API_BASE}/preferences`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to update preferences");
  return res.json();
}

export async function fetchNotifications() {
  const res = await fetch(`${API_BASE}/notifications`);
  if (!res.ok) throw new Error("Failed to fetch notifications");
  return res.json();
}

export async function markNotificationRead(id: number) {
  const res = await fetch(`${API_BASE}/notifications/${id}/read`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to mark read");
  return res.json();
}

export async function markAllNotificationsRead() {
  const res = await fetch(`${API_BASE}/notifications/mark-all-read`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to mark all read");
  return res.json();
}

// --- COMMAND CENTER ---
export async function fetchCommandCenterData(dateRange = "30d") {
  const res = await fetch(`${API_BASE}/command-center?date_range=${encodeURIComponent(dateRange)}`);
  if (!res.ok) throw new Error("Failed to fetch command center data");
  return res.json();
}

// --- GLOBAL AI COMMAND CENTER ---
export async function fetchAICommandTools() {
  const res = await fetch(`${API_BASE}/ai/command/tools`);
  if (!res.ok) throw new Error("Failed to fetch permitted tools");
  return res.json();
}

export async function fetchAICommandSuggestions() {
  const res = await fetch(`${API_BASE}/ai/command/suggestions`);
  if (!res.ok) throw new Error("Failed to fetch suggestions");
  return res.json();
}

export async function sendAICommandMessage(data: { content: string; conversation_id?: number; opportunity_id?: number }) {
  const res = await fetch(`${API_BASE}/ai/command/message`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) throw new Error("Failed to execute AI command");
  return res.json();
}

export async function fetchPendingAIActions() {
  const res = await fetch(`${API_BASE}/ai/command/actions/pending`);
  if (!res.ok) throw new Error("Failed to fetch pending actions");
  return res.json();
}

export async function executeAIAction(actionId: number) {
  const res = await fetch(`${API_BASE}/ai/command/actions/${actionId}/execute`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to execute action");
  }
  return res.json();
}

export async function rejectAIAction(actionId: number, reason?: string) {
  const res = await fetch(`${API_BASE}/ai/command/actions/${actionId}/reject`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ reason: reason || "Declined by user" })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to reject action");
  }
  return res.json();
}

export async function fetchAIActionAuditLog(limit = 50) {
  const res = await fetch(`${API_BASE}/ai/command/audit-log?limit=${limit}`);
  if (!res.ok) throw new Error("Failed to fetch audit log");
  return res.json();
}

// --- EMAIL & CALENDAR INTEGRATIONS ---
export async function fetchIntegrationsStatus() {
  const res = await fetch(`${API_BASE}/integrations/status`);
  if (!res.ok) throw new Error("Failed to fetch integrations status");
  return res.json();
}

export async function fetchGoogleAuthUrl(): Promise<{ auth_url: string; is_configured: boolean; message?: string }> {
  const res = await fetch(`${API_BASE}/integrations/google/auth-url`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to fetch Google OAuth URL");
  return res.json();
}

export async function fetchMicrosoftAuthUrl(): Promise<{ auth_url: string; is_configured: boolean; message?: string }> {
  const res = await fetch(`${API_BASE}/integrations/microsoft/auth-url`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to fetch Microsoft OAuth URL");
  return res.json();
}

export async function handleGoogleOAuthCallback(code: string, state?: string) {
  const res = await fetch(`${API_BASE}/integrations/google/callback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, state })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Google authentication callback failed");
  }
  return res.json();
}

export async function handleMicrosoftOAuthCallback(code: string, state?: string) {
  const res = await fetch(`${API_BASE}/integrations/microsoft/callback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ code, state })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Microsoft authentication callback failed");
  }
  return res.json();
}

export async function syncIntegrationConnection(id: number) {
  const res = await fetch(`${API_BASE}/integrations/${id}/sync`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to synchronize integration");
  }
  return res.json();
}

export async function disconnectIntegrationConnection(id: number) {
  const res = await fetch(`${API_BASE}/integrations/${id}/disconnect`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to disconnect integration");
  }
  return res.json();
}

export async function seedSandboxIntegrations() {
  const res = await fetch(`${API_BASE}/integrations/sandbox/seed`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to seed sandbox fixtures");
  }
  return res.json();
}

// --- EMAIL INTELLIGENCE ---
export async function fetchEmailIntelligenceMessages(params: {
  review_status?: string;
  category?: string;
  application_id?: number;
  page?: number;
  page_size?: number;
} = {}) {
  const query = new URLSearchParams();
  if (params.review_status) query.append("review_status", params.review_status);
  if (params.category) query.append("category", params.category);
  if (params.application_id) query.append("application_id", String(params.application_id));
  if (params.page) query.append("page", String(params.page));
  if (params.page_size) query.append("page_size", String(params.page_size));

  const res = await fetch(`${API_BASE}/email-intelligence/messages?${query.toString()}`);
  if (!res.ok) throw new Error("Failed to fetch email messages");
  return res.json();
}

export async function approveEmailUpdate(id: number) {
  const res = await fetch(`${API_BASE}/email-intelligence/messages/${id}/approve`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to approve email update");
  }
  return res.json();
}

export async function dismissEmailUpdate(id: number) {
  const res = await fetch(`${API_BASE}/email-intelligence/messages/${id}/dismiss`, { method: "POST" });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to dismiss email update");
  }
  return res.json();
}

export async function associateEmailToApplication(id: number, applicationId: number) {
  const res = await fetch(`${API_BASE}/email-intelligence/messages/${id}/associate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ application_id: applicationId })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to associate email to application");
  }
  return res.json();
}

export async function parseRawEmail(data: { subject: string; body_text: string; sender: string; recipient?: string; application_id?: number }) {
  const res = await fetch(`${API_BASE}/email-intelligence/parse-raw`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to parse raw email");
  }
  return res.json();
}

// --- AI INFRASTRUCTURE & DIAGNOSTICS ---
export async function fetchAIHealthStatus(): Promise<AIHealthStatusResponse> {
  const res = await fetch(`${API_BASE}/ai/status`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch AI health status");
  }
  return res.json();
}

export async function testAIProvider(provider: 'groq' | 'ollama'): Promise<TestProviderResponse> {
  const res = await fetch(`${API_BASE}/ai/test-provider`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ provider })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to test AI provider");
  }
  return res.json();
}


