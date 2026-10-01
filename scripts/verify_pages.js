// 用真实 Chromium 验证「章节页 / 索引页 / 代码浏览器」三处的交互是否真的可用。
// 只信真截图：结构断言全绿但页面是错的，这个仓库已经踩过好几次。
//
//   NODE_PATH=... node scripts/verify_pages.js
const path = require('path');
let chromium;
try {
  ({ chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright'));
} catch (e) {
  ({ chromium } = require(process.env.PLAYWRIGHT_MODULE ||
    '/Users/beiluo/.workbuddy/binaries/node/workspace/node_modules/playwright'));
}
const ROOT = '/Users/beiluo/Documents/alProject/ai-engineer-journey';
const HTML = 'file://' + path.join(ROOT, 'publishing/html');
// 截图落在 publishing/site-assets/：README 里引用的是真实运行截图，不是占位图
const SHOT = path.join(ROOT, 'publishing/site-assets');
const fs = require('fs');

const fails = [];
function check(name, cond, extra) {
  console.log((cond ? '  OK   ' : '  FAIL ') + name + (extra ? '  ' + extra : ''));
  if (!cond) fails.push(name);
}

(async () => {
  fs.mkdirSync(SHOT, { recursive: true });
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 860 }, deviceScaleFactor: 2 });
  const errors = [];
  ctx.on('weberror', e => errors.push('weberror: ' + e.error().message));
  const page = await ctx.newPage();
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });

  /* ---------------- 1. 章节页 ---------------- */
  console.log('\n[1] 章节页 docs/llm-fundamentals/01-basics-language-model.html');
  await page.goto(HTML + '/docs/llm-fundamentals/01-basics-language-model.html', { waitUntil: 'load' });
  await page.waitForTimeout(500);

  const back = await page.locator('.bb-back').first();
  check('顶栏存在「返回文档总览」', await back.count() === 1);
  const backHref = await back.getAttribute('href');
  check('回链带章节锚点', /index\.html#ch-\d+$/.test(backHref), backHref);
  check('回链目标文件真实存在',
    fs.existsSync(path.join(ROOT, 'publishing/html/index.html')));

  await page.locator('.book-bar').screenshot({ path: path.join(SHOT, 'site-chapter-topbar.png') });

  // 代码块复制按钮真的被注入
  const cps = await page.locator('.code-wrap .cp').count();
  check('代码块复制按钮已注入', cps > 0, cps + ' 个');
  // 宽表包裹
  const tw = await page.locator('.doc-view .table-wrap table').count();
  const tables = await page.locator('.doc-view table').count();
  check('表格都被 .table-wrap 包住', tw === tables, tw + '/' + tables);
  // 灯箱
  const imgs = await page.locator('.doc-view img').count();
  check('页面有图（用于验证灯箱）', imgs > 0, imgs + ' 张');
  if (imgs > 0) {
    await page.locator('.doc-view img').first().click();
    await page.waitForTimeout(250);
    check('点图后灯箱打开', await page.locator('#lightbox.on').count() === 1);
    await page.locator('.lightbox').screenshot({ path: path.join(SHOT, 'site-chapter-lightbox.png') });
    await page.keyboard.press('Escape');
    await page.waitForTimeout(200);
    check('Esc 关闭灯箱', await page.locator('#lightbox.on').count() === 0);
  }

  // 源码视图
  check('源码切换段存在', await page.locator('#bbSeg button[data-view="src"]').count() === 1);
  await page.locator('#bbSeg button[data-view="src"]').click();
  await page.waitForTimeout(350);
  const srcLines = await page.locator('#srcCode .src-line').count();
  check('源码视图渲染出行号', srcLines > 20, srcLines + ' 行');
  check('源码视图隐藏正文', await page.locator('#docView').isHidden());
  check('源码模式收起侧栏', await page.locator('body.src-mode').count() === 1);
  check('hash 切到 #src', await page.evaluate(() => location.hash) === '#src');
  const firstLine = (await page.locator('#srcCode .tx').first().innerText()).trim();
  check('源码首行是 markdown 标题', firstLine.startsWith('#'), JSON.stringify(firstLine.slice(0, 40)));
  // 高亮确实生效（H1 有 md-h 类）
  check('markdown 高亮生效', await page.locator('#srcCode .md-h').count() > 0);
  await page.locator('.src-head').scrollIntoViewIfNeeded();
  await page.screenshot({ path: path.join(SHOT, 'site-chapter-source.png') });

  await page.locator('#bbSeg button[data-view="doc"]').click();
  await page.waitForTimeout(250);
  check('切回阅读视图', await page.locator('#docView').isVisible());

  // 关键路径：索引里那个「原始 Markdown」按钮 = docs/x.html#src，必须直接在源码视图打开
  await page.goto(HTML + '/docs/llm-fundamentals/01-basics-language-model.html#src',
    { waitUntil: 'load' });
  await page.waitForTimeout(500);
  check('深链 #src 直接进源码视图',
    await page.locator('#srcView').isVisible() &&
    await page.locator('#docView').isHidden() &&
    await page.locator('#srcCode .src-line').count() > 20);

  /* ---------------- 2. 索引页 ---------------- */
  console.log('\n[2] 索引页 index.html');
  await page.goto(HTML + '/index.html', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  check('章节卡 = 209', await page.locator('section.chapter').count() === 209);

  const mdLinks = await page.locator('a.btn:has-text("原始 Markdown")').count();
  check('209 条「原始 Markdown」入口', mdLinks === 209, String(mdLinks));
  const broken = await page.evaluate(() => {
    const bad = [];
    document.querySelectorAll('a.btn').forEach(a => {
      const u = a.getAttribute('href') || '';
      if (/^https?:/.test(u) || u.startsWith('#')) return;
      if (/\.md$/.test(u.split('#')[0])) bad.push(u);   // 又指回裸 .md 就是没修好
    });
    return bad;
  });
  check('没有链接再指向裸 .md 文件', broken.length === 0, broken.slice(0, 3).join(', '));

  // 深链：index.html#ch-120 应滚到第 120 章
  await page.goto(HTML + '/index.html#ch-120', { waitUntil: 'load' });
  await page.waitForTimeout(900);
  const y = await page.evaluate(() => {
    const el = document.getElementById('ch-120');
    return el ? Math.round(el.getBoundingClientRect().top) : -999;
  });
  check('深链 #ch-120 滚到该章附近', y > -50 && y < 400, 'top=' + y);

  // 复制路径
  await page.goto(HTML + '/index.html', { waitUntil: 'load' });
  await page.waitForTimeout(300);
  await page.locator('.btn.copy').first().click();
  await page.waitForTimeout(300);
  check('复制路径有反馈提示', await page.locator('.toast.on').count() === 1);
  await page.screenshot({ path: path.join(SHOT, 'site-index.png') });

  /* ---------------- 3. 代码浏览器 ---------------- */
  console.log('\n[3] 代码浏览器 ide.html');
  await page.goto(HTML + '/ide.html', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  check('首页有「文档总览」入口', await page.locator('a[href="index.html"]').count() >= 1);
  check('项目卡已渲染', await page.locator('.card').count() > 0, await page.locator('.card').count() + ' 个项目');

  await page.locator('.card').first().click();
  await page.waitForTimeout(400);
  check('进入 IDE 视图', await page.locator('#ide.on').count() === 1);
  check('hash 路由写入项目', /^#\/[^/]+/.test(await page.evaluate(() => location.hash)),
    await page.evaluate(() => location.hash));

  check('复制按钮存在', await page.locator('#copyFile').count() === 1);
  await page.locator('#copyFile').click();
  await page.waitForTimeout(250);
  check('未开文件时给出提示', await page.locator('.toast.on').count() === 1);

  // 打开第一个「可见」文件（深层目录默认折叠，DOM 里靠前的行可能不可见）
  const files = await page.locator('.tree .row.f:visible').count();
  check('文件树有可见文件行', files > 0, files + ' 个可见文件');
  await page.locator('.tree .row.f:visible').first().click();
  await page.waitForTimeout(400);
  const stat = await page.locator('#st-path').innerText();
  check('状态栏显示文件路径', stat.includes('·') && !stat.includes('未打开'), stat);
  check('hash 路由写入文件', (await page.evaluate(() => location.hash)).split('/').length >= 3);

  await page.locator('#copyFile').click();
  await page.waitForTimeout(300);
  const toastTxt = await page.locator('.toast').innerText();
  check('复制反馈含行数/体积', /已复制/.test(toastTxt), toastTxt);
  await page.screenshot({ path: path.join(SHOT, 'site-ide-copy.png') });

  // 浏览器后退：文件 → 项目 → 首页（hash 是唯一状态源，所以后退天然可用）
  await page.goBack();
  await page.waitForTimeout(350);
  check('后退一次回到项目（仍在 IDE）', await page.locator('#ide.on').count() === 1);
  await page.goBack();
  await page.waitForTimeout(350);
  check('再后退回到项目列表', await page.locator('#home').isVisible());

  // 深链直达文件
  await page.goto(HTML + '/ide.html#/01-python-ai-cli/README.md', { waitUntil: 'load' });
  await page.waitForTimeout(600);
  check('深链直达项目+文件',
    await page.locator('#ide.on').count() === 1 &&
    (await page.locator('#st-path').innerText()).includes('README.md'),
    await page.locator('#st-path').innerText());

  // 深链直达的界面也留一张：证明 #/项目/文件 这种地址确实能直接落到某个文件
  await page.screenshot({ path: path.join(SHOT, 'site-ide-deeplink.png') });

  await browser.close();
  console.log('\n控制台错误: ' + (errors.length ? JSON.stringify(errors.slice(0, 8), null, 1) : '无'));
  if (errors.length) fails.push('存在 JS 错误');
  console.log(fails.length ? '\nFAIL: ' + fails.length + ' 项\n  - ' + fails.join('\n  - ')
    : '\n全部通过');
  process.exit(fails.length ? 1 : 0);
})().catch(e => { console.error('RUNNER FAILED:', e); process.exit(2); });
