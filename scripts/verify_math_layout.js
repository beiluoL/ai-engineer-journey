// 真实 Chromium 量页面：桌面 + 移动端视口的公式排版行为，并产出真实截图
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
const DOCS = [
  '01-basics-language-model.html',
  '02-attention.html',
  '06-scaling-and-emergence.html',
  '07-decoding-and-inference.html',
  '08-alignment-rlhf.html',
  '09-math-foundations.html',
];

(async () => {
  const browser = await chromium.launch();
  const problems = [];

  // ---------- 桌面端：逐页量「公式是否溢出行容器 / 页面是否横向溢出」 ----------
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, deviceScaleFactor: 2 });
  page.on('pageerror', e => problems.push('pageerror: ' + e.message));
  let totalMath = 0, zeroSize = 0, docOverflow = [], inlineOver = 0;
  for (const doc of DOCS) {
    await page.goto(BASE + doc, { waitUntil: 'load' });
    await page.waitForTimeout(300);
    const r = await page.evaluate(() => {
      const ms = [].slice.call(document.querySelectorAll('math'));
      const zero = ms.filter(m => { const b = m.getBoundingClientRect(); return b.width < 1 || b.height < 1; }).length;
      // 行内公式：不能把段落撑出横向滚动
      const inlineOver = [].slice.call(document.querySelectorAll('math.math-inline')).filter(m => m.scrollWidth > m.clientWidth + 1).length;
      const blocksOver = [].slice.call(document.querySelectorAll('.math-block')).filter(b => b.scrollWidth > b.clientWidth + 1).length;
      return {
        count: ms.length, zero,
        docScrollW: document.documentElement.scrollWidth,
        docClientW: document.documentElement.clientWidth,
        inlineOver, blocksOver,
      };
    });
    totalMath += r.count; zeroSize += r.zero; inlineOver += r.inlineOver;
    if (r.docScrollW > r.docClientW + 1) docOverflow.push(doc + ' (' + r.docScrollW + '>' + r.docClientW + ')');
    console.log(`${doc.padEnd(32)} math=${String(r.count).padStart(3)} 未渲染=${r.zero} 行内挤压=${r.inlineOver} 行间仍需横滚=${r.blocksOver}`);
  }
  console.log(`\n[桌面 1280px] 公式 ${totalMath} 个，未渲染 ${zeroSize}，行内挤压 ${inlineOver}，页面横向溢出 ${docOverflow.length} 页 ${docOverflow.join(' ')}`);

  // ---------- 移动端 390px & 768px ----------
  for (const w of [390, 768]) {
    const mp = await browser.newPage({ viewport: { width: w, height: 780 }, deviceScaleFactor: 2 });
    await mp.goto(BASE + '08-alignment-rlhf.html', { waitUntil: 'load' });
    await mp.waitForTimeout(300);
    const r = await mp.evaluate(() => {
      const blocks = [].slice.call(document.querySelectorAll('.math-block'));
      return {
        total: blocks.length,
        stillScroll: blocks.filter(b => b.scrollWidth > b.clientWidth + 1).length,
        minFont: Math.min.apply(null, blocks.map(b => parseFloat(getComputedStyle(b.querySelector('math')).fontSize))),
        docScrollW: document.documentElement.scrollWidth,
        docClientW: document.documentElement.clientWidth,
      };
    });
    console.log(`[移动 ${w}px] 行间公式 ${r.total} 个，仍需横滚 ${r.stillScroll} 个，最小字号 ${r.minFont}px，页面横向溢出 ${r.docScrollW > r.docClientW + 1}`);
    await mp.close();
  }

  // ---------- 行内公式与中文混排：行高是否被撑歪（「不错位」的量化口径） ----------
  for (const doc of ['02-attention.html', '09-math-foundations.html']) {
    await page.goto(BASE + doc, { waitUntil: 'load' });
    await page.waitForTimeout(300);
    const r = await page.evaluate(() => {
      const out = [];
      document.querySelectorAll('p, li').forEach(el => {
        if (!el.querySelector('math.math-inline')) return;
        const lh = parseFloat(getComputedStyle(el).lineHeight) || 0;
        if (!lh) return;
        // 用 Range 量每一行的实际高度
        const rng = document.createRange();
        rng.selectNodeContents(el);
        const rects = [].slice.call(rng.getClientRects()).filter(b => b.height > 1);
        if (rects.length < 2) return;
        const maxH = Math.max.apply(null, rects.map(b => b.height));
        out.push({ lines: rects.length, lh: +lh.toFixed(1), maxLineH: +maxH.toFixed(1), ratio: +(maxH / lh).toFixed(2) });
      });
      return out;
    });
    const worst = r.reduce((a, b) => (b.ratio > a.ratio ? b : a), { ratio: 0 });
    console.log(`[混排 ${doc}] 含行内公式的段落 ${r.length} 个；最高行高比 ${worst.ratio}（行高 ${worst.lh}px / 实际 ${worst.maxLineH}px）`);
  }

  await page.close();
  if (problems.length) { console.log('页面错误:', problems); process.exit(1); }
  console.log('\n没有 JS 报错');
  await browser.close();
})().catch(e => { console.error('FAILED:', e.message); process.exit(1); });
