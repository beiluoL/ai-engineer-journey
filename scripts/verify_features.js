const path = require('path');
let chromium;
try { ({ chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')); }
catch (e) { ({ chromium } = require('/Users/beiluo/.workbuddy/binaries/node/workspace/node_modules/playwright')); }

const ROOT = '/Users/beiluo/Documents/alProject/ai-engineer-journey';
const HTML = 'file://' + path.join(ROOT, 'publishing/html');
const SHOT = path.join(ROOT, 'publishing/site-assets');
let pass = 0, fail = 0;
function check(name, ok, extra) {
  (ok ? pass++ : fail++);
  console.log((ok ? '  ✓ ' : '  ✗ ') + name + (extra ? '   [' + extra + ']' : ''));
}

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await ctx.newPage();
  const errs = [];
  page.on('pageerror', e => errs.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errs.push('console: ' + m.text()); });

  /* ---------------- 索引页：全文搜索 ---------------- */
  console.log('\n【索引页 · 全文搜索】');
  await page.goto(HTML + '/index.html', { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  check('索引已预热加载', await page.evaluate(() => !!(window.__SEARCH__ && window.__SEARCH__.secs.length)));
  check('索引小节数 > 4000', await page.evaluate(() => window.__SEARCH__.secs.length) > 4000,
    String(await page.evaluate(() => window.__SEARCH__.secs.length)));

  await page.locator('#q').fill('注意力');
  await page.waitForTimeout(400);
  check('结果面板可见', await page.locator('#searchPanel').isVisible());
  const n = await page.locator('#searchPanel .sp-item').count();
  check('有结果条目', n > 0, n + ' 条');
  check('片段有高亮', await page.locator('#searchPanel mark').count() > 0);
  const firstDoc = await page.locator('#searchPanel .sp-doc').first().innerText();
  check('显示真实章节号（非 undefined）', !/undefined/.test(firstDoc), firstDoc);
  const firstHref = await page.locator('#searchPanel .sp-item').first().getAttribute('href');
  check('结果链接指向渲染页', /^docs\/.+\.html(#.+)?$/.test(decodeURIComponent(firstHref)), decodeURIComponent(firstHref));

  await page.screenshot({ path: path.join(SHOT, 'site-search-panel.png'), clip: { x: 0, y: 0, width: 1280, height: 900 } });

  // 多词 AND 命中数应显著减少
  const many = await page.evaluate(() => document.querySelectorAll('#searchPanel .sp-item').length);
  await page.locator('#q').fill('注意力 缩放');
  await page.waitForTimeout(350);
  const headTxt = await page.locator('#searchPanel .sp-head').innerText();
  const andTotal = parseInt((headTxt.match(/命中\s*(\d+)/) || [0, 0])[1], 10);
  check('多词为 AND（命中数下降）', andTotal > 0 && andTotal < 200, '单词 ' + many + ' 条 → 多词 ' + andTotal + ' 小节');

  // 无结果
  await page.locator('#q').fill('zzz这个词不存在xyz');
  await page.waitForTimeout(300);
  check('无结果给出提示', /没有找到/.test(await page.locator('#searchPanel .sp-head').innerText()));

  // 键盘：Enter 打开第一条
  await page.locator('#q').fill('缩放点积注意力');
  await page.waitForTimeout(350);
  const [pop] = await Promise.all([ctx.waitForEvent('page'), page.locator('#q').press('Enter')]);
  await pop.waitForLoadState('load');
  await page.waitForTimeout(600);
  const landed = await pop.evaluate(() => {
    const id = decodeURIComponent(location.hash.slice(1));
    const el = id && document.getElementById(id);
    return { url: decodeURIComponent(location.pathname.split('/publishing/html/')[1]),
             hash: id, exists: !!el, top: el ? Math.round(el.getBoundingClientRect().top) : null };
  });
  check('Enter 打开新标签并落在小节', landed.exists, landed.url + '#' + landed.hash);
  // 落在视口内即可。落在文档末尾的小节本就无法滚到顶部（页面已到底），
  // 所以不能断言 top≈0——那会把「正确」判成失败。
  check('锚点落在视口内（图片撑高后已重新落位）',
    landed.top !== null && landed.top >= -20 && landed.top < 900, 'top=' + landed.top);
  await pop.close();

  // 深链 #q=
  await page.goto(HTML + '/index.html#q=' + encodeURIComponent('流式输出'), { waitUntil: 'load' });
  await page.waitForTimeout(900);
  check('深链 #q= 预填并出结果',
    (await page.locator('#q').inputValue()) === '流式输出' &&
    await page.locator('#searchPanel .sp-item').count() > 0);

  /* ---------------- 章节页：返回入口 + 搜索入口 + 主题 ---------------- */
  console.log('\n【章节页 · 入口与主题】');
  await page.goto(HTML + '/docs/llm-fundamentals/02-attention.html', { waitUntil: 'load' });
  await page.waitForTimeout(400);
  check('顶栏有返回文档总览', await page.locator('.bb-back').count() === 1,
    await page.locator('.bb-back').getAttribute('href'));
  const sBtn = page.locator('.bb-search');
  check('顶栏有全站搜索入口', await sBtn.count() === 1, await sBtn.getAttribute('href'));
  check('顶栏有主题按钮', await page.locator('#themeBtn').count() === 1);
  check('搜索入口回链到总览带 #q=', /index\.html#q=$/.test(await sBtn.getAttribute('href')));

  // 回归：小节深链在图片撑高后要重新落位。修复前这里会偏出视口约 1000px
  // （浏览器按「图片还没加载时」的布局滚，等图片撑开，目标就跑到下面去了）。
  await page.goto(HTML + '/docs/llm-fundamentals/02-attention.html#'
    + encodeURIComponent('26-多头注意力mha并行地看多种关系'), { waitUntil: 'load' });
  await page.waitForTimeout(1500);
  const fp = await page.evaluate(() => {
    const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    return el ? Math.round(el.getBoundingClientRect().top) : null;
  });
  check('深链小节：图片撑高后仍停在视口顶部', fp !== null && fp >= -20 && fp < 160, 'top=' + fp);
  check('回链带章节锚点', /#ch-2$/.test(await page.locator('.bb-back').getAttribute('href')),
    await page.locator('.bb-back').getAttribute('href'));

  /* ---------------- 主题：三页一致 ---------------- */
  console.log('\n【主题系统】');
  await page.evaluate(() => { try { localStorage.removeItem('aij-theme'); } catch (e) {} });
  // 强制深色
  await page.evaluate(() => { try { localStorage.setItem('aij-theme', 'dark'); } catch (e) {} });
  await page.reload({ waitUntil: 'load' });
  await page.waitForTimeout(300);
  check('章节页读同一 key → 深色', await page.evaluate(() => document.documentElement.dataset.theme) === 'dark');
  await page.screenshot({ path: path.join(SHOT, 'site-chapter-dark.png') });

  // 索引页应跟随同一 key
  await page.goto(HTML + '/index.html', { waitUntil: 'load' });
  await page.waitForTimeout(900);
  check('索引页读同一 key → 深色', await page.evaluate(() => document.documentElement.dataset.theme) === 'dark');
  await page.screenshot({ path: path.join(SHOT, 'site-index-dark.png') });

  // 点按钮循环：dark → auto
  await page.locator('#themeBtn').click();
  await page.waitForTimeout(200);
  check('按钮循环切到 auto 并写入', await page.evaluate(() => localStorage.getItem('aij-theme')) === 'auto',
    await page.evaluate(() => localStorage.getItem('aij-theme')));
  await page.locator('#themeBtn').click();
  await page.waitForTimeout(200);
  check('再点切到 light', await page.evaluate(() => localStorage.getItem('aij-theme')) === 'light' &&
    await page.evaluate(() => document.documentElement.dataset.theme) === 'light');
  await page.screenshot({ path: path.join(SHOT, 'site-index-light.png') });

  /* ---------------- 代码浏览器 ---------------- */
  console.log('\n【代码浏览器 · 入口与主题】');
  const ide = await ctx.newPage();
  ide.on('pageerror', e => errs.push('ide pageerror: ' + e.message));
  await ide.goto(HTML + '/ide.html', { waitUntil: 'load' });
  await ide.waitForTimeout(700);
  check('IDE 首页有返回文档总览', await ide.locator('.hlink').count() === 1,
    await ide.locator('.hlink').getAttribute('href'));
  check('IDE 首页有主题按钮', await ide.locator('.theme-btn').count() >= 1);
  check('IDE 读同一 key → 浅色', await ide.evaluate(() => document.documentElement.dataset.theme) === 'light');
  await ide.screenshot({ path: path.join(SHOT, 'site-ide-light.png') });
  // 进项目后顶栏也应有主题按钮
  await ide.locator('.card').first().click();
  await ide.waitForTimeout(400);
  check('IDE 顶栏也有主题按钮', await ide.locator('.bar .theme-btn').count() === 1);
  await ide.screenshot({ path: path.join(SHOT, 'site-ide-light-code.png') });
  // 切深色看外观
  await ide.locator('.bar .theme-btn').click();
  await ide.waitForTimeout(250);
  check('IDE 切深色生效', await ide.evaluate(() => localStorage.getItem('aij-theme')) === 'dark' &&
    await ide.evaluate(() => document.documentElement.dataset.theme) === 'dark');
  await ide.screenshot({ path: path.join(SHOT, 'site-ide-dark.png') });
  await ide.close();

  /* ---------------- 移动端 ---------------- */
  console.log('\n【移动端】');
  const m = await ctx.newPage();
  await m.setViewportSize({ width: 390, height: 780 });
  await m.goto(HTML + '/index.html', { waitUntil: 'load' });
  await m.waitForTimeout(1200);
  await m.locator('#q').fill('rag');
  await m.waitForTimeout(400);
  const mPanel = await m.locator('#searchPanel').boundingBox();
  check('移动端搜索面板不溢出视口', mPanel && mPanel.x >= 0 && mPanel.x + mPanel.width <= 392,
    mPanel ? Math.round(mPanel.width) + 'px' : 'n/a');
  await m.screenshot({ path: path.join(SHOT, 'site-search-mobile.png') });
  await m.close();

  console.log('\n控制台错误:', errs.length ? errs : '（无）');
  console.log(`\n结果：${pass} 通过 / ${fail} 失败`);
  await browser.close();
  process.exit(fail ? 1 : 0);
})().catch(e => { console.error('FATAL', e); process.exit(1); });
