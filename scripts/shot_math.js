// 产出公式渲染的真实截图（Chromium 实拍，非合成图）
// playwright 模块位置：优先用环境变量 / 常规解析，兜底到本机 WorkBuddy 的 node 工作区
let chromium;
try {
  ({ chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright'));
} catch (e) {
  ({ chromium } = require(process.env.PLAYWRIGHT_MODULE ||
    '/Users/beiluo/.workbuddy/binaries/node/workspace/node_modules/playwright'));
}
const BASE = 'file:///Users/beiluo/Documents/alProject/ai-engineer-journey/publishing/html/docs/llm-fundamentals/';
const OUT = '/Users/beiluo/Documents/alProject/ai-engineer-journey/llm-fundamentals/assets/';

(async () => {
  const browser = await chromium.launch();

  const page = await browser.newPage({ viewport: { width: 1000, height: 900 }, deviceScaleFactor: 2 });
  await page.goto(BASE + '01-basics-language-model.html', { waitUntil: 'load' });
  await page.waitForTimeout(400);

  // 1) 用户点名的行间公式
  const blk = page.locator('div.math-block', { hasText: 'logits' }).first();
  await blk.scrollIntoViewIfNeeded();
  await blk.screenshot({ path: OUT + 'math-render-block.png' });

  // 2) 行内公式 + 中文混排：必须真的含 math.math-inline，否则抓到的是纯文字段落
  await page.goto(BASE + '09-math-foundations.html', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const para = page.locator('p', { has: page.locator('math.math-inline'), hasText: '约定说明' }).first();
  await para.scrollIntoViewIfNeeded();
  await para.screenshot({ path: OUT + 'math-render-inline.png' });
  console.log('行内混排段落:', (await para.innerText()).replace(/\s+/g, ' ').slice(0, 80));

  // 3) 表格里的公式（09 章：含 \| 的 KL 行，改动前会被切成两格）
  await page.goto(BASE + '09-math-foundations.html', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  const tbl = page.locator('table', { hasText: '不对称' }).first();
  await tbl.scrollIntoViewIfNeeded();
  await tbl.screenshot({ path: OUT + 'math-render-table.png' });

  await page.close();

  // 4) 移动端 390px：最长的一条行间公式
  const mp = await browser.newPage({ viewport: { width: 390, height: 780 }, deviceScaleFactor: 3 });
  await mp.goto(BASE + '08-alignment-rlhf.html', { waitUntil: 'load' });
  await mp.waitForTimeout(500);
  const mblk = mp.locator('div.math-block').first();
  await mblk.scrollIntoViewIfNeeded();
  await mblk.screenshot({ path: OUT + 'math-render-mobile.png' });
  await mp.close();

  await browser.close();
  console.log('截图完成 → llm-fundamentals/assets/');
})().catch(e => { console.error('FAILED:', e.message); process.exit(1); });
