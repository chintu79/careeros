import { chromium } from 'playwright';
import path from 'path';

const ARTIFACTS_DIR = process.env.CAREEROS_E2E_ARTIFACTS || path.join(process.cwd(), 'artifacts');
const BASE_URL = 'http://127.0.0.1:5174';

async function runShellAudit() {
  console.log('--- Starting CareerOS 2.9.0 Shell & Design Foundation Audit ---');
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
  });

  const viewports = [
    { name: '1440px_desktop_wide', width: 1440, height: 900 },
    { name: '1280px_desktop_std', width: 1280, height: 800 },
    { name: '768px_tablet', width: 768, height: 1024 },
    { name: '390px_mobile', width: 390, height: 844 },
  ];

  // 1. Verify responsive layouts and capture screenshots at required widths
  for (const vp of viewports) {
    console.log(`\nTesting viewport: ${vp.name} (${vp.width}x${vp.height})`);
    const context = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    await page.goto(BASE_URL, { waitUntil: 'networkidle' });
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
        hasOverflow: scrollW > innerW + 1, // allow 1px rounding tolerance
      };
    });

    console.log(`Viewport ${vp.name} overflow check:`, overflow);
    if (overflow.hasOverflow) {
      console.warn(`WARNING: Horizontal overflow detected in ${vp.name}: scrollWidth=${overflow.scrollWidth}, innerWidth=${overflow.innerWidth}`);
    } else {
      console.log(`✓ Zero horizontal overflow verified for ${vp.name}`);
    }

    const screenshotPath = path.join(ARTIFACTS_DIR, `shell_${vp.name}.png`);
    await page.screenshot({ path: screenshotPath });
    console.log(`Captured screenshot: ${screenshotPath}`);

    await context.close();
  }

  // 2. Deep Interactive Tests on Desktop (1440px)
  console.log('\n--- Testing Desktop Shell Interactions (1440px) ---');
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });
  const page = await context.newPage();
  await page.goto(BASE_URL, { waitUntil: 'networkidle' });
  await page.waitForTimeout(800);

  // A. Overview Route
  console.log('Testing Route: Overview');
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_route_overview.png') });

  // B. Test Sidebar Collapse
  console.log('Testing Sidebar Collapse...');
  const collapseBtn = page.locator('aside button[aria-label="Collapse sidebar"]');
  if (await collapseBtn.isVisible()) {
    await collapseBtn.click();
    await page.waitForTimeout(400);
    const isCollapsed = await page.evaluate(() => {
      const aside = document.querySelector('aside');
      return aside ? aside.classList.contains('w-[64px]') : false;
    });
    console.log('Sidebar is collapsed (w-64px):', isCollapsed);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_sidebar_collapsed_1440px.png') });

    // Expand sidebar again
    const expandBtn = page.locator('aside button[aria-label="Expand sidebar"]');
    if (await expandBtn.isVisible()) {
      await expandBtn.click();
      await page.waitForTimeout(400);
    }
  }

  // C. Test Navigation to Discover
  console.log('Navigating to Discover tab...');
  await page.click('aside button:has-text("Discover")');
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_route_discover.png') });

  // D. Test Candidate Profile Context Dropdown
  console.log('Testing Candidate Switcher Dropdown...');
  const switcherBtn = page.locator('header button[title*="Candidate profile context"]');
  await switcherBtn.click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_candidate_switcher_dropdown.png') });

  // Close candidate switcher by clicking backdrop
  await page.click('header');
  await page.waitForTimeout(300);

  // E. Test Notifications Popover
  console.log('Testing Notifications Popover...');
  const notifBtn = page.locator('header button[aria-label*="notifications"]');
  await notifBtn.click();
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_notifications_panel.png') });

  // Close notifications
  await page.click('header');
  await page.waitForTimeout(300);

  // F. Test Command Palette
  console.log('Testing Command Palette...');
  await page.keyboard.press('Control+k');
  await page.waitForTimeout(500);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_command_palette.png') });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);

  await context.close();

  // 3. Test Mobile Drawer Navigation (390px)
  console.log('\n--- Testing Mobile Drawer on 390px Viewport ---');
  const mobileContext = await browser.newContext({
    viewport: { width: 390, height: 844 },
  });
  const mobilePage = await mobileContext.newPage();
  await mobilePage.goto(BASE_URL, { waitUntil: 'networkidle' });
  await mobilePage.waitForTimeout(800);

  // Open mobile drawer
  const menuBtn = mobilePage.locator('button[aria-label="Open navigation menu"]');
  await menuBtn.click();
  await mobilePage.waitForTimeout(400);
  await mobilePage.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_mobile_drawer_open.png') });

  // Verify mobile navigation item click
  console.log('Clicking Resume Studio in mobile drawer...');
  await mobilePage.click('div[role="dialog"] button:has-text("Resume Studio")');
  await mobilePage.waitForTimeout(800);
  await mobilePage.screenshot({ path: path.join(ARTIFACTS_DIR, 'shell_mobile_route_resumes.png') });

  // Verify no overflow on mobile
  const mobileOverflow = await mobilePage.evaluate(() => {
    return document.documentElement.scrollWidth <= window.innerWidth + 1;
  });
  console.log('Mobile route resumes overflow check passed:', mobileOverflow);

  await mobileContext.close();
  await browser.close();

  console.log('\n--- CareerOS 2.9.0 Shell & Design Foundation Audit Complete ---');
}

runShellAudit().catch(err => {
  console.error('Audit failed with error:', err);
  process.exit(1);
});
