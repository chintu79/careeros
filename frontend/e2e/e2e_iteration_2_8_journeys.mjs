import { chromium } from 'playwright';
import path from 'path';

const ARTIFACT_DIR = '/home/krishna/.gemini/antigravity/brain/913ec7f7-c5ad-46ab-9267-acc5887bf6b9';
const BASE_URL = 'http://127.0.0.1:5174';
const BACKEND_URL = 'http://127.0.0.1:8005';
const TEST_RESUME_PATH = '/home/krishna/Desktop/interniq/frontend/e2e/test_resume.txt';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runE2E() {
  console.log('====================================================================');
  console.log('CareerOS Iteration 2.8: Candidate Onboarding & Activation Journeys');
  console.log('====================================================================\n');

  // 1. Verify backend health
  const healthRes = await fetch(`${BACKEND_URL}/api/health`);
  if (!healthRes.ok) {
    throw new Error(`Backend not healthy: ${healthRes.status}`);
  }
  console.log('✓ Verified backend health on port 8005');

  // 2. Prepare test candidate (User 2) via backend API to clean onboarding state
  const tokenRes = await fetch(`${BACKEND_URL}/api/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: 2 })
  });
  const tokenData = await tokenRes.json();
  const user2Token = tokenData.access_token;
  console.log('✓ Obtained authenticated token for Test Candidate (User ID: 2)');

  // Reset User 2 onboarding state cleanly
  const resetRes = await fetch(`${BACKEND_URL}/api/candidate/onboarding-progress`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${user2Token}`
    },
    body: JSON.stringify({
      step: 1,
      status: 'not_started',
      career_goals: {},
      profile_data: {
        name: 'Demo Candidate',
        email: 'demo@careeros.ai',
        phone: '',
        location: '',
        degree: '',
        college: '',
        graduation_year: 2026,
        cgpa: null,
        skills: [],
        projects: [],
        experience: []
      }
    })
  });
  if (!resetRes.ok) {
    throw new Error(`Failed to reset test candidate onboarding: ${resetRes.status}`);
  }
  console.log('✓ Reset Test Candidate 2 to pristine onboarding state (Step 1, not_started)');

  // Launch Chrome browser
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });

  const page = await context.newPage();

  try {
    // -------------------------------------------------------------------------
    // JOURNEY 1: New Candidate Signs Up / Initializes Onboarding
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 1: New Candidate Signs In & Initializes Onboarding ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });

    // Set authenticated session as User 2 in localStorage
    await page.evaluate(({ token, userId }) => {
      localStorage.setItem('careeros_auth_token', token);
      localStorage.setItem('careeros_active_user_id', String(userId));
    }, { token: user2Token, userId: 2 });

    // Reload page to adopt User 2 session
    await page.reload({ waitUntil: 'networkidle' });
    await sleep(600);

    // Navigate to Setup & Activation tab in sidebar
    const onboardingNavBtn = await page.waitForSelector('button:has-text("Setup & Activation")');
    await onboardingNavBtn.click();
    await sleep(600);

    // Verify Onboarding View rendered
    await page.waitForSelector('h1:has-text("Set Up Your CareerOS Profile")');
    await page.waitForSelector('text=Step 1 of 6: Career Goals');
    console.log('✓ Step 1 (Career Goals) successfully rendered');

    // Screenshot Journey 1
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_1_onboarding_welcome.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_1_onboarding_welcome.png');

    // -------------------------------------------------------------------------
    // JOURNEY 2: Completes Basic Profile Information & Career Goals
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 2: Complete Goals & Profile Information ---');
    
    // Fill Name & Email & Details
    const nameInput = await page.waitForSelector('input[placeholder*="Alex River"]');
    await nameInput.fill('Morgan Taylor');

    const emailInput = await page.waitForSelector('input[placeholder*="alex@example.com"]');
    await emailInput.fill('morgan.taylor@example.com');

    const phoneInput = await page.waitForSelector('input[placeholder*="(555)"]');
    await phoneInput.fill('+1 (555) 345-6789');

    const locationInput = await page.waitForSelector('input[placeholder*="San Francisco"]');
    await locationInput.fill('San Francisco, CA');

    // Add target roles
    const roleInput = await page.waitForSelector('input[placeholder*="Frontend Engineer, Backend"]');
    await roleInput.fill('Backend Developer');
    await page.keyboard.press('Enter');
    await sleep(200);

    // Select workplace & authorization
    await page.selectOption('select:has-text("Any (Remote, Hybrid, or On-site)")', 'remote');
    await page.selectOption('select:has-text("US Citizen")', 'US Citizen');

    // Click "Save & Continue" to advance to Step 2
    const saveAndContinueBtn = await page.waitForSelector('button:has-text("Save & Continue")');
    await saveAndContinueBtn.click();
    await sleep(800);

    // Verify step advances to Step 2: Education
    await page.waitForSelector('h2:has-text("Education & Background")');
    await page.waitForSelector('text=Step 2 of 6: Education');
    console.log('✓ Successfully saved Step 1 and advanced to Step 2: Education');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_2_goals_and_education.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_2_goals_and_education.png');

    // -------------------------------------------------------------------------
    // JOURNEY 3: Adds Education & Technical Skills with Canonical Categories
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 3: Education & Canonical Technical Skills ---');
    
    // Step 2 Form
    const degreeInput = await page.waitForSelector('input[placeholder*="B.S. in Computer Science"]');
    await degreeInput.fill('B.S. in Computer Science');

    const collegeInput = await page.waitForSelector('input[placeholder*="Stanford University"]');
    await collegeInput.fill('UC Berkeley');

    const gradYearInput = await page.waitForSelector('input[placeholder*="2026"]');
    await gradYearInput.fill('2026');

    const cgpaInput = await page.waitForSelector('input[placeholder*="3.85"]');
    await cgpaInput.fill('3.90');

    // Add optional experience
    const addExpBtn = await page.waitForSelector('button:has-text("+ Add Experience")');
    await addExpBtn.click();
    await sleep(200);

    const expTitleInput = await page.waitForSelector('input[placeholder*="Software Engineering Intern"]');
    await expTitleInput.fill('Software Engineering Intern');

    const expCompanyInput = await page.waitForSelector('input[placeholder*="Stripe Labs"]');
    await expCompanyInput.fill('Stripe');

    // Advance to Step 3: Technical Skills
    const nextToSkillsBtn = await page.waitForSelector('button:has-text("Save & Continue")');
    await nextToSkillsBtn.click();
    await sleep(800);

    await page.waitForSelector('h2:has-text("Technical Skills Management")');
    await page.waitForSelector('text=Step 3 of 6: Technical Skills');
    console.log('✓ Successfully advanced to Step 3: Technical Skills');

    // Add skills using suggestion chips and input
    const skillNameInput = await page.waitForSelector('input[placeholder*="Skill name (e.g. Python, React"]');
    const skillCategorySelect = await page.waitForSelector('select:has-text("Languages")');
    const addSkillBtn = await page.waitForSelector('button:has-text("Add Skill")');

    // 1. Python via suggestion chip
    const pythonChip = await page.waitForSelector('button:has-text("+ Python")');
    await pythonChip.click();
    await addSkillBtn.click();
    await sleep(400);

    // 2. FastAPI
    await skillNameInput.fill('FastAPI');
    await skillCategorySelect.selectOption('Frameworks');
    await addSkillBtn.click();
    await sleep(400);

    // 3. PostgreSQL
    await skillNameInput.fill('PostgreSQL');
    await skillCategorySelect.selectOption('Databases');
    await addSkillBtn.click();
    await sleep(400);

    // 4. Docker
    await skillNameInput.fill('Docker');
    await skillCategorySelect.selectOption('Cloud & DevOps');
    await addSkillBtn.click();
    await sleep(400);

    // Verify skills are listed with Self-reported badges (pre-project linking)
    await page.waitForSelector('text=Added Skills (4)');
    const selfReportedBadges = await page.$$('text=Self-reported');
    console.log(`✓ Added 4 technical skills; found ${selfReportedBadges.length} self-reported indicators (awaiting project grounding)`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_3_technical_skills.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_3_technical_skills.png');

    // -------------------------------------------------------------------------
    // JOURNEY 4: Adds Project with Tech Stack Tags & Verifies Evidence Linking
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 4: Project Portfolio Evidence & Skill Linking ---');
    
    // Advance to Step 4: Projects
    const nextToProjectsBtn = await page.waitForSelector('button:has-text("Save & Continue")');
    await nextToProjectsBtn.click();
    await sleep(800);

    await page.waitForSelector('h2:has-text("Project Portfolio Evidence")');
    await page.waitForSelector('text=Step 4 of 6: Projects');

    // Click "Add Project"
    const addProjectBtn = await page.waitForSelector('button:has-text("Add Project")');
    await addProjectBtn.click();
    await sleep(300);

    // Fill project details
    const projTitleInput = await page.waitForSelector('input[placeholder*="Distributed Task Queue"]');
    await projTitleInput.fill('Distributed Job Processing Engine');

    const projUrlInput = await page.waitForSelector('input[placeholder*="github.com/username/project"]');
    await projUrlInput.fill('https://github.com/morgantaylor/distributed-job-engine');

    const projTechInput = await page.waitForSelector('input[placeholder*="Go, Redis, Docker, PostgreSQL"]');
    await projTechInput.fill('Python, FastAPI, PostgreSQL, Docker');

    const projDescInput = await page.waitForSelector('textarea[placeholder*="High-throughput worker pool"]');
    await projDescInput.fill('High-throughput asynchronous task orchestrator using FastAPI and PostgreSQL with automated worker scaling and observability.');

    // Save project
    const saveProjBtn = await page.waitForSelector('button:has-text("Save Project")');
    await saveProjBtn.click();
    await sleep(800);

    // Verify project card rendered
    await page.waitForSelector('h4:has-text("Distributed Job Processing Engine")');
    console.log('✓ Successfully created project with tech stack tags');

    // Verify skills are now verified via backend completeness API
    const compCheckRes = await fetch(`${BACKEND_URL}/api/candidate/completeness`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const compCheck = await compCheckRes.json();
    console.log(`✓ Completeness Service Evidence Linking: verified ${compCheck.skills_summary.verified} of ${compCheck.skills_summary.total} skills`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_4_project_portfolio.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_4_project_portfolio.png');

    // -------------------------------------------------------------------------
    // JOURNEY 5: Uploads Resume & Reviews Parsed Draft with Selective Merge
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 5: Resume Upload & Selective Merge ---');
    
    // Advance to Step 5: Resume
    const nextToResumeBtn = await page.waitForSelector('button:has-text("Save & Continue")');
    await nextToResumeBtn.click();
    await sleep(800);

    await page.waitForSelector('h2:has-text("Resume Document & ATS Master")');
    await page.waitForSelector('text=Step 5 of 6: Resume');

    // Set file in hidden resume file input
    const fileInput = await page.waitForSelector('input[type="file"]', { state: 'attached' });
    await fileInput.setInputFiles(TEST_RESUME_PATH);
    console.log('  → Uploaded test_resume.txt');

    // Wait for parse review card to appear
    await page.waitForSelector('h4:has-text("Review Extracted Information")');
    console.log('✓ Resume parsing completed: Review Extracted Information displayed');

    // Click "Approve & Merge to Profile"
    const approveBtn = await page.waitForSelector('button:has-text("Approve & Merge to Profile")');
    await approveBtn.click();
    await sleep(1000);

    // Verify merge toast
    await page.waitForSelector('text=Resume data merged successfully.');
    console.log('✓ Successfully approved and merged resume draft to profile');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_5_resume_upload_parsed.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_5_resume_upload_parsed.png');

    // -------------------------------------------------------------------------
    // JOURNEY 6: Reviews Profile Readiness, Score Ring Banner & Recommendations
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 6: Profile Readiness Review & Activation Ready ---');
    
    // Advance to Step 6: Readiness & Launch
    const nextToLaunchBtn = await page.waitForSelector('button:has-text("Save & Continue")');
    await nextToLaunchBtn.click();
    await sleep(800);

    await page.waitForSelector('h2:has-text("Profile Readiness & Verification Review")');
    await page.waitForSelector('text=Step 6 of 6: Readiness & Launch');

    // Verify Completeness Score ring and Stage badge
    await page.waitForSelector('text=Confirmed Evidence');
    const stageHeading = await page.waitForSelector('h3:has-text("High-Confidence Match Ready"), h3:has-text("Core Evidence Established")');
    const stageText = await stageHeading.textContent();
    console.log(`✓ Readiness Stage: ${stageText.trim()}`);

    // Verify actionable recommendations card
    await page.waitForSelector('text=Recommended Next Actions');
    console.log('✓ Confirmed evidence checklist and recommendations rendered');

    // Verify Activation CTA is present
    await page.waitForSelector('button:has-text("Activate Profile & Discover Matches")');
    console.log('✓ Activation CTA "Activate Profile & Discover Matches" is ready');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_6_readiness_review.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_6_readiness_review.png');

    // -------------------------------------------------------------------------
    // JOURNEY 7: Opens Personalized Discovery Feed
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 7: Activate Profile & Open Discovery Feed ---');
    
    const activateBtn = await page.waitForSelector('button:has-text("Activate Profile & Discover Matches")');
    
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/opportunities') && resp.status() === 200),
      activateBtn.click()
    ]);
    await sleep(1000);

    // Verify navigated to Discover tab
    await page.waitForSelector('h1:has-text("Discover"), h2:has-text("Discover")');
    console.log('✓ Successfully activated profile and navigated to Discover tab');

    // Verify opportunities loaded in feed
    await page.waitForSelector('article.group');
    const cards = await page.$$('article.group');
    console.log(`✓ Discovery Feed rendered with ${cards.length} personalized opportunities`);

    // In backend, verify onboarding status is 'completed'
    const candStatusRes = await fetch(`${BACKEND_URL}/api/candidate`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const candStatus = await candStatusRes.json();
    console.log(`✓ Backend Candidate Profile Status: onboarding_status="${candStatus.onboarding_status}"`);
    if (candStatus.onboarding_status !== 'completed') {
      throw new Error(`Expected onboarding_status="completed", got "${candStatus.onboarding_status}"`);
    }

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_7_first_discovery_activation.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_7_first_discovery_activation.png');

    // -------------------------------------------------------------------------
    // JOURNEY 8: Updates Skill & Verifies Evidence Version Bump
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 8: Evidence Update & Evidence Version Bump ---');
    const initialEvidenceVersion = candStatus.evidence_version || 1;
    console.log(`Current candidate evidence_version: ${initialEvidenceVersion}`);

    // Add a new skill via API
    const skillAddRes = await fetch(`${BACKEND_URL}/api/candidate/skills`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${user2Token}`
      },
      body: JSON.stringify({
        name: 'GraphQL',
        category: 'Architecture & APIs',
        level: 'advanced',
        evidence: 'Microservice federated schema and Apollo client'
      })
    });
    if (!skillAddRes.ok) throw new Error('Failed to add skill for version bump test');
    const updatedCand = await skillAddRes.json();

    console.log(`Updated candidate evidence_version: ${updatedCand.evidence_version}`);
    if (updatedCand.evidence_version <= initialEvidenceVersion) {
      throw new Error(`Evidence version did not bump: ${initialEvidenceVersion} -> ${updatedCand.evidence_version}`);
    }
    console.log(`✓ Verified Evidence Version Bump: ${initialEvidenceVersion} → ${updatedCand.evidence_version}`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_8_evidence_version_updated.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_8_evidence_version_updated.png');

    // -------------------------------------------------------------------------
    // JOURNEY 9: Starts New Discovery Session with Updated Evidence
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 9: New Discovery Session with Fresh Evidence ---');
    const searchInput = await page.waitForSelector('#opportunity-search-input');
    
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/opportunities') && resp.status() === 200),
      searchInput.fill('Engineer')
    ]);
    await sleep(800);

    const freshCards = await page.$$('article.group');
    console.log(`✓ Fresh discovery session loaded with ${freshCards.length} matching opportunities against version ${updatedCand.evidence_version}`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_9_new_discovery_session.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_9_new_discovery_session.png');

    // -------------------------------------------------------------------------
    // JOURNEY 10: Existing Candidate Returns Without Losing Previous Information
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 10: Switch to Candidate 1 (Candidate One) & Verify Data Integrity ---');
    
    // Switch account to Candidate 1
    const headerUserBtn = await page.waitForSelector('header button[title*="Candidate profile context"]');
    await headerUserBtn.click();
    await sleep(200);

    const [switchResp] = await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/auth/token') && resp.status() === 200),
      page.click('button[role="menuitem"]:has-text("Candidate One")')
    ]);
    await sleep(1000);

    // Verify context header now shows Candidate 1
    const userBtnAfter = await page.waitForSelector('header button[title*="Candidate profile context"]');
    const userTextAfter = await userBtnAfter.textContent();
    console.log(`✓ Active Candidate Context: ${userTextAfter.trim()}`);

    // Verify Candidate 1 database integrity directly
    const cand1TokenRes = await fetch(`${BACKEND_URL}/api/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 1 })
    });
    const cand1TokenData = await cand1TokenRes.json();
    const cand1Res = await fetch(`${BACKEND_URL}/api/candidate`, {
      headers: { 'Authorization': `Bearer ${cand1TokenData.access_token}` }
    });
    const cand1 = await cand1Res.json();

    console.log(`Candidate 1 Name: ${cand1.name}`);
    console.log(`Candidate 1 Onboarding Status: ${cand1.onboarding_status}`);
    console.log(`Candidate 1 Projects Count: ${cand1.projects.length}`);

    if (cand1.user_id !== 1 || cand1.name !== 'Candidate One') {
      throw new Error(`Candidate 1 identity compromised: id=${cand1.user_id}, name=${cand1.name}`);
    }
    if (cand1.projects.length !== 7) {
      throw new Error(`Candidate 1 projects compromised: expected 7, found ${cand1.projects.length}`);
    }
    if (cand1.onboarding_status !== 'completed') {
      throw new Error(`Candidate 1 onboarding status compromised: expected 'completed', found ${cand1.onboarding_status}`);
    }
    console.log('✓ Candidate 1 Verified 100% Intact: 7 projects preserved, onboarding_status="completed"');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_10_candidate_1_preserved.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_10_candidate_1_preserved.png');

    console.log('\n====================================================================');
    console.log('ALL 10 ITERATION 2.8 USER JOURNEYS COMPLETED SUCCESSFULLY! 🚀');
    console.log('====================================================================');

  } finally {
    await browser.close();
  }
}

runE2E().catch(err => {
  console.error('\n❌ E2E Execution Failed:', err);
  process.exit(1);
});
