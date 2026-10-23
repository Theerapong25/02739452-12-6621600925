// Capture real Airflow and dashboard pages for the exam summary.
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

(async () => {
  const root = __dirname;
  const env = Object.fromEntries(fs.readFileSync(path.join(root, '.env'), 'utf8').split(/\r?\n/)
    .filter(line => line.includes('=')).map(line => { const pos = line.indexOf('='); return [line.slice(0,pos), line.slice(pos+1)]; }));
  const target = path.join(root, 'report_assets');
  fs.mkdirSync(target, { recursive: true });
  const browser = await chromium.launch({ executablePath: 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 950 }, deviceScaleFactor: 1 });
  await page.goto('http://localhost:' + (env.WEB_PORT || '8502'), { waitUntil: 'networkidle' });
  await page.screenshot({ path: path.join(target, 'dashboard.png'), fullPage: true });
  await page.goto('http://localhost:' + (env.AIRFLOW_PORT || '8090') + '/login/', { waitUntil: 'domcontentloaded' });
  await page.locator('input[name="username"]').fill(env.AIRFLOW_ADMIN_USER);
  await page.locator('input[name="password"]').fill(env.AIRFLOW_ADMIN_PASSWORD);
  await page.locator('button[type="submit"], input[type="submit"]').first().click();
  await page.waitForLoadState('networkidle');
  const base = 'http://localhost:' + (env.AIRFLOW_PORT || '8090') + '/dags/notebook_price_comparison/';
  for (const name of ['grid','graph']) {
    await page.goto(base + name, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(target, 'airflow-' + name + '.png'), fullPage: true });
    console.log(name, page.url(), await page.title());
  }
  await browser.close();
})().catch(error => { console.error(error); process.exitCode = 1; });
