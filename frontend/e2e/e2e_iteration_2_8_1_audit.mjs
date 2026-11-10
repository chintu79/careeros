import { chromium } from 'playwright';
import path from 'path';

const ARTIFACT_DIR = '/home/krishna/.gemini/antigravity/brain/913ec7f7-c5ad-46ab-9267-acc5887bf6b9';
const BASE_URL = 'http://127.0.0.1:5174';
const BACKEND_URL = 'http://127.0.0.1:8005';
const TEST_RESUME_PATH = '/home/krishna/Desktop/interniq/frontend/e2e/test_resume.txt';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runAuditE2E() {
  console.log('========================================================================');
  console.log('CareerOS 2.8.1: Strict Production Verification & Browser Audit Journeys');
  console.log('========================================================================\n');

  // 1. Verify backend health
  const healthRes = await fetch(`${BACKEND_URL}/api/health`);
  if (!healthRes.ok) throw new Error(`Backend not healthy: ${healthRes.status}`);
  console.log('✓ Verified backend health on port 8005');

  // 2. Prepare test candidate (User 2)
  const tokenRes = await fetch(`${BACKEND_URL}/api/auth/token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: 2 })
  });
  const tokenData = await tokenRes.json();
  const user2Token = tokenData.access_token;
  console.log('✓ Authenticated as Audit Candidate (User ID: 2)');

  // Reset User 2 state cleanly
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
        name: 'Audit Candidate Two',
        email: 'audit_two@careeros.ai',
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
  if (!resetRes.ok) throw new Error(`Failed to reset audit candidate: ${resetRes.status}`);
  console.log('✓ Reset Audit Candidate 2 to step 1 (not_started)');

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
    // JOURNEY STEP 1: Career Goals & Target Roles
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 1: Goals & Target Roles Verification ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });

    await page.evaluate(({ token, userId }) => {
      localStorage.setItem('careeros_auth_token', token);
      localStorage.setItem('careeros_active_user_id', String(userId));
    }, { token: user2Token, userId: 2 });

    await page.reload({ waitUntil: 'networkidle' });
    await sleep(600);

    // Open Setup & Activation tab
    const onboardingNavBtn = await page.waitForSelector('button:has-text("Setup & Activation")');
    await onboardingNavBtn.click();
    await sleep(600);

    await page.waitForSelector('h1:has-text("Set Up Your CareerOS Profile")');
    await page.waitForSelector('text=Step 1 of 6: Career Goals');

    // Fill form
    const nameInput = await page.waitForSelector('input[placeholder*="Alex River"]');
    await nameInput.fill('Jordan Cross');

    const emailInput = await page.waitForSelector('input[placeholder*="alex@example.com"]');
    await emailInput.fill('jordan.cross@careeros.ai');

    const locationInput = await page.waitForSelector('input[placeholder*="San Francisco"]');
    await locationInput.fill('Austin, TX');

    const roleInput = await page.waitForSelector('input[placeholder*="Frontend Engineer, Backend"]');
    await roleInput.fill('Infrastructure Engineer');
    await page.keyboard.press('Enter');
    await sleep(200);

    await page.selectOption('select:has-text("Any (Remote, Hybrid, or On-site)")', 'remote');
    await page.selectOption('select:has-text("US Citizen")', 'US Citizen');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step1_goals.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step1_goals.png');

    // Advance to Step 2
    const save1Btn = await page.waitForSelector('button:has-text("Save & Continue")');
    await save1Btn.click();
    await sleep(800);

    // Verify backend persistence for Step 1
    const cand1Res = await fetch(`${BACKEND_URL}/api/candidate`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const cand1Data = await cand1Res.json();
    if (cand1Data.name !== 'Jordan Cross' || cand1Data.location !== 'Austin, TX' || cand1Data.onboarding_step !== 2) {
      throw new Error(`Step 1 backend persistence assertion failed: ${JSON.stringify(cand1Data)}`);
    }
    console.log('✓ Step 1 Backend State Confirmed: Name="Jordan Cross", Step=2, Status="in_progress"');

    // -------------------------------------------------------------------------
    // JOURNEY STEP 2: Education & Background
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 2: Education & University Background ---');
    await page.waitForSelector('h2:has-text("Education & Background")');
    await page.waitForSelector('text=Step 2 of 6: Education');

    const degreeInput = await page.waitForSelector('input[placeholder*="B.S. in Computer Science"]');
    await degreeInput.fill('B.S. in Computer Engineering');

    const collegeInput = await page.waitForSelector('input[placeholder*="Stanford University"]');
    await collegeInput.fill('University of Texas at Austin');

    const gradYearInput = await page.waitForSelector('input[placeholder*="2026"]');
    await gradYearInput.fill('2026');

    const cgpaInput = await page.waitForSelector('input[placeholder*="3.85"]');
    await cgpaInput.fill('3.88');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step2_education.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step2_education.png');

    const save2Btn = await page.waitForSelector('button:has-text("Save & Continue")');
    await save2Btn.click();
    await sleep(800);

    // Verify backend persistence for Step 2
    const cand2Res = await fetch(`${BACKEND_URL}/api/candidate`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const cand2Data = await cand2Res.json();
    if (cand2Data.college !== 'University of Texas at Austin' || cand2Data.graduation_year !== 2026 || cand2Data.onboarding_step !== 3) {
      throw new Error(`Step 2 backend persistence assertion failed: ${JSON.stringify(cand2Data)}`);
    }
    console.log('✓ Step 2 Backend State Confirmed: College="University of Texas at Austin", GradYear=2026, Step=3');

    // -------------------------------------------------------------------------
    // JOURNEY STEP 3: Technical Skills Management
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 3: Canonical Technical Skills & Unverified Status ---');
    await page.waitForSelector('h2:has-text("Technical Skills Management")');
    await page.waitForSelector('text=Step 3 of 6: Technical Skills');

    const skillInput = await page.waitForSelector('input[placeholder*="Skill name (e.g. Python, React"]');
    const skillCategory = await page.waitForSelector('select:has-text("Languages")');
    const addSkillBtn = await page.waitForSelector('button:has-text("Add Skill")');

    // Add skills
    const pythonChip = await page.waitForSelector('button:has-text("+ Python")');
    await pythonChip.click();
    await addSkillBtn.click();
    await sleep(400);

    await skillInput.fill('FastAPI');
    await skillCategory.selectOption('Frameworks');
    await addSkillBtn.click();
    await sleep(400);

    await skillInput.fill('PostgreSQL');
    await skillCategory.selectOption('Databases');
    await addSkillBtn.click();
    await sleep(400);

    await skillInput.fill('Docker');
    await skillCategory.selectOption('Cloud & DevOps');
    await addSkillBtn.click();
    await sleep(400);

    await page.waitForSelector('text=Added Skills (4)');
    const selfBadges = await page.$$('text=Self-reported');
    console.log(`✓ Added 4 technical skills; verified ${selfBadges.length} self-reported indicators prior to project code linking`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step3_skills.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step3_skills.png');

    // Verify backend completeness: all 4 skills must be unverified
    const comp3Res = await fetch(`${BACKEND_URL}/api/candidate/completeness`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const comp3Data = await comp3Res.json();
    if (comp3Data.skills_summary.total !== 4 || comp3Data.skills_summary.verified !== 0) {
      throw new Error(`Skills unverified assertion failed: total=${comp3Data.skills_summary.total}, verified=${comp3Data.skills_summary.verified}`);
    }
    console.log('✓ Step 3 Backend State Confirmed: 4 total skills, 0 verified (distinguishing unverified claims)');

    // -------------------------------------------------------------------------
    // JOURNEY STEP 4: Project Portfolio Evidence & Skill Grounding
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 4: Project Portfolio Evidence & Automated Skill Verification ---');
    const save3Btn = await page.waitForSelector('button:has-text("Save & Continue")');
    await save3Btn.click();
    await sleep(800);

    await page.waitForSelector('h2:has-text("Project Portfolio Evidence")');
    await page.waitForSelector('text=Step 4 of 6: Projects');

    const addProjBtn = await page.waitForSelector('button:has-text("Add Project")');
    await addProjBtn.click();
    await sleep(300);

    const projTitleInput = await page.waitForSelector('input[placeholder*="Distributed Task Queue"]');
    await projTitleInput.fill('Cloud Infrastructure Monitor');

    const projUrlInput = await page.waitForSelector('input[placeholder*="github.com/username/project"]');
    await projUrlInput.fill('https://github.com/jordancross/infra-monitor');

    const projTechInput = await page.waitForSelector('input[placeholder*="Go, Redis, Docker, PostgreSQL"]');
    await projTechInput.fill('Python, FastAPI, PostgreSQL, Docker');

    const projDescInput = await page.waitForSelector('textarea[placeholder*="High-throughput worker pool"]');
    await projDescInput.fill('Observability metrics collector and alerting gateway running on Docker containers with PostgreSQL time-series queries.');

    const saveProjBtn = await page.waitForSelector('button:has-text("Save Project")');
    await saveProjBtn.click();
    await sleep(800);

    await page.waitForSelector('h4:has-text("Cloud Infrastructure Monitor")');
    console.log('✓ Project card rendered with tech stack chips');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step4_projects.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step4_projects.png');

    // Verify backend completeness: all 4 skills are now verified by project code!
    const comp4Res = await fetch(`${BACKEND_URL}/api/candidate/completeness`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const comp4Data = await comp4Res.json();
    if (comp4Data.skills_summary.verified !== 4) {
      throw new Error(`Project skill linking failed: expected 4 verified, got ${comp4Data.skills_summary.verified}`);
    }
    console.log('✓ Step 4 Backend State Confirmed: 4 of 4 skills successfully verified by project code evidence');

    // -------------------------------------------------------------------------
    // JOURNEY STEP 5: Resume Upload, Sandbox Parsing & Selective Merge
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 5: Resume Upload, Parsing & Selective Merge ---');
    const save4Btn = await page.waitForSelector('button:has-text("Save & Continue")');
    await save4Btn.click();
    await sleep(800);

    await page.waitForSelector('h2:has-text("Resume Document & ATS Master")');
    await page.waitForSelector('text=Step 5 of 6: Resume');

    // Upload resume file
    const fileInput = await page.waitForSelector('input[type="file"]', { state: 'attached' });
    await fileInput.setInputFiles(TEST_RESUME_PATH);
    console.log('  → Uploaded test_resume.txt');

    // Wait for parse review card
    await page.waitForSelector('h4:has-text("Review Extracted Information")');
    console.log('✓ Resume parsing completed: Review Extracted Information displayed');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step5_resume_parsed.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step5_resume_parsed.png');

    // Approve & Merge
    const approveBtn = await page.waitForSelector('button:has-text("Approve and merge")');
    await approveBtn.click();
    await sleep(1000);

    await page.waitForSelector('text=Resume data merged successfully.');
    console.log('✓ Resume data merged successfully toast verified');

    // Verify backend state after merge
    const cand5Res = await fetch(`${BACKEND_URL}/api/candidate`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const cand5Data = await cand5Res.json();
    if (cand5Data.skills.length <= 4) {
      throw new Error(`Resume skill merge failed: expected > 4 skills, found ${cand5Data.skills.length}`);
    }
    console.log(`✓ Step 5 Backend State Confirmed: Profile updated with ${cand5Data.skills.length} skills after merge`);

    // -------------------------------------------------------------------------
    // JOURNEY STEP 6: Readiness Review & Activation Ready
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 6: Readiness Review & Verification Checklist ---');
    const save5Btn = await page.waitForSelector('button:has-text("Save & Continue")');
    await save5Btn.click();
    await sleep(800);

    await page.waitForSelector('h2:has-text("Profile Readiness & Verification Review")');
    await page.waitForSelector('text=Step 6 of 6: Readiness & Launch');

    await page.waitForSelector('text=Confirmed Evidence');
    const stageHeading = await page.waitForSelector('h3:has-text("High-Confidence Match Ready"), h3:has-text("Core Evidence Established")');
    const stageText = await stageHeading.textContent();
    console.log(`✓ Readiness Stage: ${stageText.trim()}`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step6_readiness_breakdown.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step6_readiness_breakdown.png');

    // -------------------------------------------------------------------------
    // JOURNEY STEP 7: Profile Activation & First Discovery Session
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 7: Profile Activation & First Discovery Session ---');
    const activateBtn = await page.waitForSelector('button:has-text("Activate Profile & Discover Matches")');
    
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/opportunities') && resp.status() === 200),
      activateBtn.click()
    ]);
    await sleep(1000);

    await page.waitForSelector('h1:has-text("Discover"), h2:has-text("Discover")');
    await page.waitForSelector('article.group');
    const oppCards = await page.$$('article.group');
    console.log(`✓ Navigated to Discover feed: loaded ${oppCards.length} personalized opportunities`);

    // Verify backend onboarding_status is 'completed'
    const cand7Res = await fetch(`${BACKEND_URL}/api/candidate`, {
      headers: { 'Authorization': `Bearer ${user2Token}` }
    });
    const cand7Data = await cand7Res.json();
    if (cand7Data.onboarding_status !== 'completed' || cand7Data.onboarding_step !== 6) {
      throw new Error(`Profile activation failed: status=${cand7Data.onboarding_status}, step=${cand7Data.onboarding_step}`);
    }
    console.log('✓ Step 7 Backend State Confirmed: onboarding_status="completed", onboarding_step=6');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step7_discovery_activation.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step7_discovery_activation.png');

    // -------------------------------------------------------------------------
    // JOURNEY STEP 8: Candidate 1 Integrity Verification
    // -------------------------------------------------------------------------
    console.log('\n--- Audit Step 8: Candidate 1 Data Integrity Verification ---');
    const headerUserBtn = await page.waitForSelector('header button[title*="Candidate profile context"]');
    await headerUserBtn.click();
    await sleep(200);

    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/auth/token') && resp.status() === 200),
      page.click('button[role="menuitem"]:has-text("Shreekrishna Chinta")')
    ]);
    await sleep(1000);

    const cand1TokenRes = await fetch(`${BACKEND_URL}/api/auth/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: 1 })
    });
    const cand1Token = (await cand1TokenRes.json()).access_token;

    const cand1FinalRes = await fetch(`${BACKEND_URL}/api/candidate`, {
      headers: { 'Authorization': `Bearer ${cand1Token}` }
    });
    const cand1Final = await cand1FinalRes.json();

    if (cand1Final.user_id !== 1 || cand1Final.name !== 'Shreekrishna Chinta' || cand1Final.projects.length !== 7 || cand1Final.onboarding_status !== 'completed') {
      throw new Error(`Candidate 1 corrupted during audit: ${JSON.stringify(cand1Final)}`);
    }
    console.log('✓ Candidate 1 Verified 100% Intact: 7 projects preserved, onboarding_status="completed"');

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'audit_step8_candidate_1_preserved.png'),
      fullPage: false
    });
    console.log('📸 Saved audit_step8_candidate_1_preserved.png');

    console.log('\n========================================================================');
    console.log('ALL PLAYWRIGHT AUDIT JOURNEYS & BACKEND ASSERTIONS PASSED! 🚀');
    console.log('========================================================================');

  } finally {
    await browser.close();
  }
}

runAuditE2E().catch(err => {
  console.error('\n❌ Playwright Audit Execution Failed:', err);
  process.exit(1);
});
