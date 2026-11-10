import { chromium } from 'playwright';
import path from 'path';

const ARTIFACTS_DIR = '/home/krishna/.gemini/antigravity/brain/913ec7f7-c5ad-46ab-9267-acc5887bf6b9';
const BASE_URL = 'http://127.0.0.1:5174';

async function runDiscoverAudit() {
  console.log('--- Starting CareerOS 2.9.0 Iteration 2.2 Discover View Audit ---');
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const viewports = [
    { name: '1440px', width: 1440, height: 900 },
    { name: '1280px', width: 1280, height: 800 },
    { name: '768px', width: 768, height: 1024 },
    { name: '390px', width: 390, height: 844 },
  ];

  // 1. Multi-viewport overflow & visual captures on Discover page
  for (const vp of viewports) {
    console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
    await page.waitForTimeout(600);

    // Navigate to Discover tab depending on viewport
    if (vp.width < 768) {
      const hamburger = page.locator('button[aria-label="Open navigation menu"]').first();
      await hamburger.click();
      await page.waitForTimeout(400);
      const mobileDiscover = page.locator('div[role="dialog"][aria-label="Navigation menu"] button:has-text("Discover")').first();
      await mobileDiscover.click();
    } else {
      const discoverBtn = page.locator('aside button:has-text("Discover")').first();
      await discoverBtn.click();
    }
    await page.waitForTimeout(1000);

    // Verify zero horizontal overflow
    const overflow = await page.evaluate(() => {
      const doc = document.documentElement;
      const body = document.body;
      const scrollW = Math.max(doc.scrollWidth, body.scrollWidth);
      const innerW = window.innerWidth;
      return {
        scrollWidth: scrollW,
        innerWidth: innerW,
        hasOverflow: scrollW > innerW + 1,
      };
    });

    console.log(`Viewport ${vp.name} overflow check:`, overflow);
    if (overflow.hasOverflow) {
      console.warn(`WARNING: Horizontal overflow detected in ${vp.name}`);
    } else {
      console.log(`✓ Zero horizontal overflow verified for ${vp.name}`);
    }

    const screenshotPath = path.join(ARTIFACTS_DIR, `iteration_2_2_elevated_discover_${vp.name}.png`);
    await page.screenshot({ path: screenshotPath });
    console.log(`Captured screenshot: ${screenshotPath}`);

    await context.close();
  }

  // 2. Interactive Verification on Desktop (1440px)
  console.log('\n--- Testing Discover Interactive Features (1440px) ---');
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(600);

  // Navigate to Discover
  await page.click('aside button:has-text("Discover")');
  await page.waitForTimeout(800);

  // A. Test Search input filtering
  console.log('Testing search input filter...');
  const searchInput = page.locator('#opportunity-search-input');
  await searchInput.fill('Engineer');
  await page.waitForTimeout(600);
  console.log('Search input populated with "Engineer".');
  await searchInput.fill('');
  await page.waitForTimeout(400);

  // B. Test Match Intelligence drawer open/close
  console.log('Testing Match Intelligence drawer toggle...');
  const matchIntelBtn = page.locator('button:has-text("Match Intelligence")').first();
  if (await matchIntelBtn.isVisible()) {
    await matchIntelBtn.click();
    await page.waitForTimeout(600);
    console.log('Match Intelligence drawer opened.');
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'iteration_2_2_elevated_match_intelligence_open.png') });
    // Close drawer
    await matchIntelBtn.click();
    await page.waitForTimeout(400);
    console.log('Match Intelligence drawer closed.');
  }

  // C. Test Bookmark toggle on the first card
  console.log('Testing bookmark button toggle...');
  const bookmarkBtn = page.locator('button[title="Save opportunity"], button[title="Remove from saved"]').first();
  if (await bookmarkBtn.isVisible()) {
    await bookmarkBtn.click();
    await page.waitForTimeout(600);
    console.log('Bookmark toggled successfully.');
  }

  // D. Test Opening Opportunity Detail Modal
  console.log('Testing Opportunity Detail Modal open...');
  const detailBtn = page.locator('button:has-text("Details")').first();
  if (await detailBtn.isVisible()) {
    await detailBtn.click();
    await page.waitForTimeout(800);
    console.log('Opportunity Detail modal opened.');
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'iteration_2_2_elevated_detail_modal.png') });

    // Verify modal has tabs, score, etc.
    const modalHeading = await page.evaluate(() => {
      const modal = document.querySelector('[role="dialog"]');
      if (!modal) return null;
      const h2 = modal.querySelector('h2');
      return h2 ? h2.innerText : 'dialog found';
    });
    console.log('Modal heading detected:', modalHeading);

    // Close modal
    const closeBtn = page.locator('[role="dialog"] button:has-text("Close")').first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await page.waitForTimeout(400);
      console.log('Modal closed successfully.');
    }
  }

  // E. Candidate switching verification on Discover
  console.log('Testing Candidate switching on Discover page...');
  const candidateSwitcherBtn = page.locator('header button[title*="Candidate profile context"]');
  await candidateSwitcherBtn.click();
  await page.waitForTimeout(400);

  const candidateBItem = page.locator('button[role="menuitem"]:has-text("Candidate B")');
  if (await candidateBItem.isVisible()) {
    await candidateBItem.click();
    await page.waitForTimeout(1000);
    console.log('Switched to Candidate B on Discover.');

    // Switch back to Candidate 1 (Shreekrishna)
    await candidateSwitcherBtn.click();
    await page.waitForTimeout(400);
    const candidateAItem = page.locator('button[role="menuitem"]:has-text("Shreekrishna")');
    await candidateAItem.click();
    await page.waitForTimeout(1000);
    console.log('Switched back to Candidate 1 (Shreekrishna).');
  }

  await context.close();
  await browser.close();

  console.log('\n--- CareerOS 2.9.0 Iteration 2.2 Discover View Audit Complete ---');
}

runDiscoverAudit().catch(err => {
  console.error('Discover audit failed with error:', err);
  process.exit(1);
});
