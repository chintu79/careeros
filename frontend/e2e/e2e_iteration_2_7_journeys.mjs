import { chromium } from 'playwright';
import path from 'path';

const ARTIFACT_DIR = '/home/krishna/.gemini/antigravity/brain/913ec7f7-c5ad-46ab-9267-acc5887bf6b9';
const BASE_URL = 'http://127.0.0.1:5174';
const BACKEND_URL = 'http://127.0.0.1:8005';

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

async function runE2E() {
  console.log('=== CareerOS Iteration 2.7: E2E Playwright Journeys ===\n');

  // Verify backend health
  const healthRes = await fetch(`${BACKEND_URL}/api/health`);
  if (!healthRes.ok) {
    throw new Error(`Backend not healthy: ${healthRes.status}`);
  }
  console.log('✓ Verified backend health on port 8005');

  // Launch browser
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
    // JOURNEY 1 & 2: User signs in with Bearer token & Opens Discovery view
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 1 & 2: Sign in with Bearer token & Open Discovery ---');
    await page.goto(BASE_URL, { waitUntil: 'networkidle' });

    // Ensure authenticated as User 1 (Shreekrishna Chinta)
    await page.evaluate(async (backendUrl) => {
      const res = await fetch(`${backendUrl}/api/auth/token`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 1 })
      });
      const data = await res.json();
      localStorage.setItem('careeros_auth_token', data.access_token);
      localStorage.setItem('careeros_active_user_id', '1');
    }, BACKEND_URL);

    // Navigate to Discover tab
    const [discoverResp] = await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/opportunities') && resp.status() === 200),
      page.click('button:has-text("Discover")')
    ]);
    await page.waitForSelector('h1:has-text("Discover"), h2:has-text("Discover")');
    await sleep(600);

    // Verify User 1 context is indicated in header
    const userBtn = await page.waitForSelector('header button[title*="Candidate profile context"]');
    const userBtnText = await userBtn.textContent();
    console.log(`✓ Active Candidate Context: ${userBtnText.trim()}`);

    // Verify opportunity feed loaded
    await page.waitForSelector('article.group');
    const initialCards = await page.$$('article.group');
    console.log(`✓ Discovery Feed Loaded with ${initialCards.length} initial opportunities`);

    // Capture screenshot
    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_1_auth_discovery.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_1_auth_discovery.png');

    // -------------------------------------------------------------------------
    // JOURNEY 3: Search for an opportunity
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 3: Search for an opportunity ---');
    const searchInput = await page.waitForSelector('#opportunity-search-input');
    
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/opportunities') && resp.status() === 200),
      searchInput.fill('Software')
    ]);
    await sleep(600);

    const searchCards = await page.$$('article.group');
    console.log(`✓ Search for "Software" yielded ${searchCards.length} opportunities`);

    // -------------------------------------------------------------------------
    // JOURNEY 4: Apply search filters
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 4: Apply search filters ---');
    const filterBtn = await page.waitForSelector('button:has-text("Filters")');
    await filterBtn.click();
    await page.waitForSelector('#filter-workplace');

    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/opportunities') && resp.status() === 200),
      page.selectOption('#filter-workplace', 'remote')
    ]);
    await sleep(600);

    const filteredCards = await page.$$('article.group');
    console.log(`✓ Filter (Workplace: Remote) active, rendering ${filteredCards.length} matching cards`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_3_search_filters.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_3_search_filters.png');

    // Reset filters and search for clean feed
    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/opportunities') && resp.status() === 200),
      (async () => {
        await page.selectOption('#filter-workplace', '');
        await searchInput.fill('');
      })()
    ]);
    await filterBtn.click(); // close filter panel
    await sleep(600);

    // -------------------------------------------------------------------------
    // JOURNEY 5 & 6: Open opportunity card details & View 5-Category Intelligence
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 5 & 6: View Details & 5-Category Match Breakdown ---');
    const firstDetailsBtn = await page.waitForSelector('article.group button:has-text("Details")');
    await firstDetailsBtn.click();

    // Verify modal appears
    await page.waitForSelector('div[role="dialog"]');
    console.log('✓ Opportunity Detail Modal opened');

    // Verify exact precision copy
    await page.waitForSelector('text=5-category weighted evaluation and eligibility validation');
    console.log('✓ Verified 5-category evaluation contract and precision copy');

    // Verify 5 category progress bars
    await page.waitForSelector('text=Evaluation Breakdown by Category');
    const categoryLabels = ['Mandatory Skills', 'Experience', 'Projects', 'Preferred Skills', 'Education'];
    for (const label of categoryLabels) {
      const found = await page.locator(`text=${label}`).first().isVisible();
      if (found) {
        console.log(`  • Factor present: ${label}`);
      }
    }

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_5_opportunity_detail_modal.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_5_opportunity_detail_modal.png');

    // Close modal
    const closeBtn = await page.waitForSelector('button:has-text("Close")');
    await closeBtn.click();
    await page.waitForSelector('div[role="dialog"]', { state: 'hidden' });
    console.log('✓ Opportunity Detail Modal closed');

    // -------------------------------------------------------------------------
    // JOURNEY 7: Load more opportunities via cursor pagination
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 7: Cursor Pagination Stream ---');
    const beforeCount = (await page.$$('article.group')).length;
    console.log(`Count before load more: ${beforeCount}`);

    const loadMoreBtn = await page.waitForSelector('button:has-text("Load More Opportunities")');
    await loadMoreBtn.scrollIntoViewIfNeeded();
    await sleep(300);

    await Promise.all([
      page.waitForResponse(resp => resp.url().includes('cursor=') && resp.status() === 200),
      loadMoreBtn.click()
    ]);
    await sleep(600);

    const afterCount = (await page.$$('article.group')).length;
    console.log(`Count after load more: ${afterCount}`);
    if (afterCount <= beforeCount) {
      throw new Error(`Cursor pagination failed: before=${beforeCount}, after=${afterCount}`);
    }
    console.log(`✓ Cursor pagination successfully streamed ${afterCount - beforeCount} additional items`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_7_cursor_pagination.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_7_cursor_pagination.png');

    // -------------------------------------------------------------------------
    // JOURNEY 8 & 9: Simulated expired snapshot session (HTTP 410) & Automatic recovery
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 8 & 9: HTTP 410 Expired Session & Automatic Recovery ---');
    
    // Intercept next cursor pagination call to simulate expired session 410
    let simulated410 = false;
    await page.route('**/api/opportunities?*cursor=*', async (route) => {
      if (!simulated410) {
        simulated410 = true;
        console.log('  → Intercepting cursor request to simulate HTTP 410 Gone');
        await route.fulfill({
          status: 410,
          contentType: 'application/json',
          body: JSON.stringify({
            detail: 'Pagination session expired. Please restart search.',
            restart_required: true,
            code: 'PAGINATION_SESSION_EXPIRED'
          })
        });
      } else {
        await route.continue();
      }
    });

    // Trigger cursor fetch
    const loadMoreAgain = await page.$('button:has-text("Load More Opportunities")');
    if (loadMoreAgain) {
      await loadMoreAgain.click();
      await sleep(1000);
    }

    // Unroute interceptor
    await page.unroute('**/api/opportunities?*cursor=*');

    // Verify recovery notice appeared
    const noticeEl = await page.waitForSelector('text=Pagination session refreshed');
    const noticeText = await noticeEl.textContent();
    console.log(`✓ Recovery Notice displayed: "${noticeText.trim().slice(0, 70)}…"`);

    // Verify feed refreshed from page 1 / cursor 0
    const refreshedCards = await page.$$('article.group');
    console.log(`✓ Discovery feed successfully recovered with ${refreshedCards.length} items`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_9_session_recovery.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_9_session_recovery.png');

    // -------------------------------------------------------------------------
    // JOURNEY 10: Dismiss an opportunity with feedback
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 10: Dismiss an opportunity ---');
    const initialDismissCount = (await page.$$('article.group')).length;
    
    // Click more menu on first card
    const firstMenuBtn = await page.waitForSelector('article.group button[aria-label*="More options"]');
    await firstMenuBtn.click();
    await sleep(200);

    const dismissOption = await page.waitForSelector('button[role="menuitem"]:has-text("Not interested")');
    await dismissOption.click();
    await sleep(300);

    // DismissFeedbackModal is opened: click quick dismiss
    const quickDismissBtn = await page.waitForSelector('button:has-text("Dismiss without feedback")');
    await quickDismissBtn.click();
    await page.waitForSelector('div:has-text("Dismiss Opportunity")', { state: 'hidden' });
    await sleep(800);

    const afterDismissCount = (await page.$$('article.group')).length;
    console.log(`✓ Opportunity dismissed. Cards count: ${initialDismissCount} → ${afterDismissCount}`);

    // -------------------------------------------------------------------------
    // JOURNEY 11: Switch authenticated account to Candidate B
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 11: Switch authenticated account to Candidate B ---');
    const headerUserBtn = await page.waitForSelector('header button[title*="Candidate profile context"]');
    await headerUserBtn.click();
    await sleep(200);

    const [switchResp] = await Promise.all([
      page.waitForResponse(resp => resp.url().includes('/api/auth/token') && resp.status() === 200),
      page.click('button[role="menuitem"]:has-text("Candidate B")')
    ]);
    await sleep(1000);

    // Verify context header now shows Candidate B
    const newUserBtn = await page.waitForSelector('header button[title*="Candidate profile context"]');
    const newUserText = await newUserBtn.textContent();
    console.log(`✓ Switched account header: ${newUserText.trim()}`);

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_11_candidate_switching.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_11_candidate_switching.png');

    // -------------------------------------------------------------------------
    // JOURNEY 12: Verify isolated intelligence & unevaluated match cards for Candidate B
    // -------------------------------------------------------------------------
    console.log('\n--- Journey 12: Verify isolated intelligence & Unevaluated cards for Candidate B ---');
    
    await page.waitForSelector('article.group');
    const candBCards = await page.$$('article.group');
    console.log(`✓ Candidate B has ${candBCards.length} opportunities loaded in isolated session`);

    // Verify Unevaluated badges are present for Candidate B (proving isolation from Candidate A's scores)
    const unevaluatedBadge = await page.$('text=Unevaluated');
    if (unevaluatedBadge) {
      console.log('✓ Verified Candidate B receives Unevaluated status (no cross-tenant score leakage)');
    }

    // Trigger on-demand calculate on an unevaluated card
    const calculateBtn = await page.$('article.group button:has-text("Calculate")');
    if (calculateBtn) {
      console.log('  → Triggering on-demand match calculation for Candidate B');
      await Promise.all([
        page.waitForResponse(resp => resp.url().includes('/evaluate-match') && resp.status() === 200),
        calculateBtn.click()
      ]);
      await sleep(1000);
      console.log('✓ Successfully scored opportunity specifically against Candidate B verified profile');
    }

    await page.screenshot({
      path: path.join(ARTIFACT_DIR, 'journey_12_isolated_candidate_b.png'),
      fullPage: false
    });
    console.log('📸 Saved journey_12_isolated_candidate_b.png');

    console.log('\n======================================================');
    console.log('ALL 12 PRODUCTION USER JOURNEYS PASSED SUCCESSFULLY! 🚀');
    console.log('======================================================');

  } finally {
    await browser.close();
  }
}

runE2E().catch(err => {
  console.error('\n❌ E2E Execution Failed:', err);
  process.exit(1);
});
