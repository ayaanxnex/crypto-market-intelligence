/* BlackCoin — EDA & Pipeline Report add-on
 * Drop this file in /public and add <script src="eda.js"></script> before </body> in index.html.
 * It hooks into render() and apiRequest() from index.html and builds a report section
 * above the footer. No backend changes required.
 */
(function () {
  'use strict';

  /* ============ EDIT THESE FOR YOUR ASSIGNMENT WRITE-UP ============ */
  const CONFIG = {
    dataset: 'CoinGecko public API (/coins/markets), top 50 cryptocurrencies by market cap, USD.',
    whyDataset:
      'Crypto markets are public, high-frequency and volatile, so they give a live, realistic dataset ' +
      'with mixed asset types (large caps, meme coins, stablecoins, tokenized funds) that makes EDA interesting.',
    storage: 'YOUR DATABASE / FILE HERE (e.g. Supabase PostgreSQL, SQLite, CSV)',
    whyStorage:
      'EDIT ME: explain why you chose this storage (e.g. free hosted tier, works with Vercel serverless, ' +
      'supports timestamped snapshots).',
    stack: 'Python serverless functions on Vercel · pandas (transform) · Pydantic (validation) · Chart.js dashboard',
    edaQuestions: [
      'How is 24h price change distributed across the top 50 assets, and is the market broad or narrow?',
      'Which assets are statistical outliers in volatility, return and trading activity?',
      'How do market cap, volume, volatility and returns relate to each other (correlation)?',
      'How do stablecoins differ from non-stablecoins, and how much do they distort market totals?',
      'How concentrated is the market in BTC / ETH / the top 5 assets?'
    ],
    alertThreshold: 10
  };
  /* ================================================================= */

  const STABLE_SYMBOLS = new Set(['USDT', 'USDC', 'USDS', 'DAI', 'USDE', 'USD1', 'USDG', 'PYUSD',
    'RLUSD', 'USDY', 'USYC', 'BUIDL', 'FDUSD', 'TUSD', 'USDD', 'GUSD']);

  const EXPECTED_FIELDS = ['price_change_percentage_1h_in_currency',
    'price_change_percentage_7d_in_currency', 'sparkline_in_7d'];

  const DICT = {
    timestamp: 'Snapshot load time (UTC)',
    coin_id: 'CoinGecko API identifier',
    symbol: 'Ticker symbol',
    name: 'Asset name',
    image: 'Logo URL',
    current_price: 'Current price (USD)',
    market_cap: 'Market capitalization (USD)',
    market_cap_rank: 'Rank by market cap',
    fully_diluted_valuation: 'Valuation at max supply (USD)',
    total_volume: '24h traded volume (USD)',
    high_24h: 'Highest price, last 24h',
    low_24h: 'Lowest price, last 24h',
    price_change_24h: 'Absolute price change, 24h',
    price_change_percentage_24h: 'Price change, 24h (%)',
    market_cap_change_24h: 'Absolute market cap change, 24h',
    market_cap_change_percentage_24h: 'Market cap change, 24h (%)',
    circulating_supply: 'Coins currently in circulation',
    total_supply: 'Total coins created',
    max_supply: 'Maximum possible supply',
    ath: 'All-time high price',
    ath_change_percentage: 'Distance from all-time high (%)',
    ath_date: 'Date of all-time high',
    atl: 'All-time low price',
    atl_change_percentage: 'Distance from all-time low (%)',
    atl_date: 'Date of all-time low',
    roi: 'Return on investment object (if any)',
    last_updated: 'Last update time at source',
    volatility_spread: 'Derived: high_24h − low_24h',
    volatility_pct: 'Derived: spread ÷ low_24h × 100',
    liquidity_ratio: 'Derived: total_volume ÷ market_cap',
    is_volatility_alert: 'Derived: volatility_pct above alert threshold',
    price_change_percentage_1h_in_currency: 'Price change, 1h (%)',
    price_change_percentage_7d_in_currency: 'Price change, 7d (%)',
    sparkline_in_7d: '7-day hourly price series'
  };

  let lastRefresh = null;
  let histChart = null;

  /* ---------- helpers ---------- */
  const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g,
    c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const num = v => (v === null || v === undefined || v === '' || typeof v === 'boolean') ? NaN : Number(v);
  const finite = arr => arr.filter(Number.isFinite);
  const sym = c => String(c.symbol || '').toUpperCase();
  const money = n => {
    if (!Number.isFinite(n)) return '—';
    if (n >= 1e12) return '$' + (n / 1e12).toFixed(2) + 'T';
    if (n >= 1e9) return '$' + (n / 1e9).toFixed(2) + 'B';
    if (n >= 1e6) return '$' + (n / 1e6).toFixed(1) + 'M';
    return '$' + n.toLocaleString('en-US', { maximumFractionDigits: 2 });
  };
  const pct = (n, d = 2) => Number.isFinite(n) ? (n >= 0 ? '+' : '') + n.toFixed(d) + '%' : '—';
  const f = (n, d = 2) => Number.isFinite(n) ? n.toLocaleString('en-US', { maximumFractionDigits: d }) : '—';

  function quantile(sorted, p) {
    if (!sorted.length) return NaN;
    const i = (sorted.length - 1) * p, lo = Math.floor(i), hi = Math.ceil(i);
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (i - lo);
  }
  function describe(values) {
    const v = finite(values).sort((a, b) => a - b);
    const n = v.length;
    if (!n) return { n: 0 };
    const mean = v.reduce((s, x) => s + x, 0) / n;
    const std = n > 1 ? Math.sqrt(v.reduce((s, x) => s + (x - mean) ** 2, 0) / (n - 1)) : NaN;
    return { n, mean, std, min: v[0], q1: quantile(v, .25), median: quantile(v, .5), q3: quantile(v, .75), max: v[n - 1] };
  }
  function pearson(xs, ys) {
    const px = [], py = [];
    for (let i = 0; i < xs.length; i++) if (Number.isFinite(xs[i]) && Number.isFinite(ys[i])) { px.push(xs[i]); py.push(ys[i]); }
    const n = px.length;
    if (n < 3) return NaN;
    const mx = px.reduce((a, b) => a + b, 0) / n, my = py.reduce((a, b) => a + b, 0) / n;
    let sxy = 0, sxx = 0, syy = 0;
    for (let i = 0; i < n; i++) { sxy += (px[i] - mx) * (py[i] - my); sxx += (px[i] - mx) ** 2; syy += (py[i] - my) ** 2; }
    return sxx && syy ? sxy / Math.sqrt(sxx * syy) : NaN;
  }
  function isStable(c) {
    if (STABLE_SYMBOLS.has(sym(c))) return true;
    const p = num(c.current_price), v = num(c.volatility_pct);
    return Number.isFinite(p) && p > 0.97 && p < 1.2 && Number.isFinite(v) && v < 1;
  }

  /* ---------- CSS ---------- */
  function injectCSS() {
    if (document.getElementById('edaStyle')) return;
    const s = document.createElement('style');
    s.id = 'edaStyle';
    s.textContent = `
      #edaRoot{margin:30px 0 10px}
      .eda-head{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;flex-wrap:wrap;margin-bottom:16px}
      .eda-head h2{margin:4px 0 0;font-size:26px;letter-spacing:-.8px}
      .eda-head p{margin:6px 0 0;color:var(--bc-muted);font-size:13px}
      .eda-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-bottom:16px}
      .eda-wide{grid-column:1/-1}
      @media(max-width:900px){.eda-grid{grid-template-columns:1fr}}
      #edaRoot .panel h2{font-size:15px;margin:0 0 4px}
      .eda-sub{font-size:12px;color:var(--bc-muted);margin:0 0 12px;line-height:1.55}
      .eda-scroll{overflow:auto}
      #edaRoot table{min-width:0;width:100%}
      #edaRoot th,#edaRoot td{padding:9px 10px;text-align:right;font-size:12px}
      #edaRoot th:first-child,#edaRoot td:first-child{text-align:left}
      #edaRoot td{font-family:'DM Mono',monospace}
      #edaRoot td.eda-txt{font-family:'Space Grotesk',sans-serif;text-align:left;white-space:normal}
      .eda-stages{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
      @media(max-width:700px){.eda-stages{grid-template-columns:repeat(2,minmax(0,1fr))}}
      .eda-stage{border:1px solid var(--bc-border);border-radius:10px;padding:12px;background:var(--bc-surface)}
      .eda-stage .n{font:10px 'DM Mono',monospace;color:var(--bc-lime);letter-spacing:.6px}
      .eda-stage strong{display:block;font-size:15px;margin:5px 0 3px}
      .eda-stage span{font-size:11px;color:var(--bc-muted);line-height:1.5;display:block}
      .eda-ok{color:var(--bc-lime)} .eda-bad{color:var(--bc-red)}
      .eda-bar{height:8px;background:var(--bc-border);border-radius:5px;overflow:hidden;min-width:70px}
      .eda-bar i{display:block;height:100%;background:var(--bc-lime)}
      .eda-bar.red i{background:var(--bc-red)}
      .eda-row{display:grid;grid-template-columns:150px 1fr 70px;gap:10px;align-items:center;margin:9px 0;font-size:12px}
      .eda-row span:last-child{font-family:'DM Mono',monospace;text-align:right}
      .eda-tag{display:inline-block;padding:2px 6px;border-radius:5px;font:10px 'DM Mono',monospace;border:1px solid var(--bc-border);color:var(--bc-muted)}
      .eda-tag.red{color:var(--bc-red);border-color:var(--bc-red)}
      .eda-ul{margin:0;padding-left:18px;font-size:13px;line-height:1.7}
      .eda-kv{display:grid;grid-template-columns:130px 1fr;gap:6px 12px;font-size:13px;line-height:1.55}
      .eda-kv b{color:var(--bc-muted);font:11px 'DM Mono',monospace;text-transform:uppercase;padding-top:2px}
      .eda-chart{height:260px;position:relative}
      .eda-heat td{text-align:center!important;min-width:64px}
      .eda-note{font-size:11px;color:var(--bc-muted);margin-top:10px;line-height:1.5}
    `;
    document.head.appendChild(s);
  }

  /* ---------- sections ---------- */
  function secMethod() {
    return `<div class="panel eda-wide"><h2>00 / Methodology</h2>
      <p class="eda-sub">What this pipeline does, and why.</p>
      <div class="eda-kv">
        <b>Dataset</b><div>${esc(CONFIG.dataset)}</div>
        <b>Why</b><div>${esc(CONFIG.whyDataset)}</div>
        <b>Loaded to</b><div>${esc(CONFIG.storage)}</div>
        <b>Why</b><div>${esc(CONFIG.whyStorage)}</div>
        <b>Stack</b><div>${esc(CONFIG.stack)}</div>
        <b>EDA aims</b><div><ul class="eda-ul">${CONFIG.edaQuestions.map(q => `<li>${esc(q)}</li>`).join('')}</ul></div>
      </div></div>`;
  }

  function secStages(data, coins) {
    const r = lastRefresh;
    const fetched = r && r.fetched != null ? r.fetched : coins.length;
    const valid = r && r.valid != null ? r.valid : coins.length;
    const rejected = r && r.rejected != null ? r.rejected : '—';
    const derived = ['volatility_spread', 'volatility_pct', 'liquidity_ratio', 'is_volatility_alert']
      .filter(k => coins.some(c => c[k] !== null && c[k] !== undefined)).length;
    const src = r ? 'from last refresh this session' : 'from latest snapshot — click Refresh pipeline for live counts';
    const ts = data && data.timestamp ? new Date(data.timestamp) : null;
    return `<div class="panel eda-wide"><h2>01 / ETL stages</h2>
      <p class="eda-sub">Counts ${esc(src)}.</p>
      <div class="eda-stages">
        <div class="eda-stage"><div class="n">01 EXTRACT</div><strong>${esc(fetched)} records</strong><span>Fetched from CoinGecko /coins/markets</span></div>
        <div class="eda-stage"><div class="n">02 VALIDATE</div><strong><span class="eda-ok" style="display:inline;font-size:15px">${esc(valid)} valid</span> · <span class="${Number(rejected) > 0 ? 'eda-bad' : ''}" style="display:inline;font-size:15px">${esc(rejected)} rejected</span></strong><span>Pydantic schema checks</span></div>
        <div class="eda-stage"><div class="n">03 TRANSFORM</div><strong>${derived} derived fields</strong><span>volatility_spread, volatility_pct, liquidity_ratio, alert flag (pandas)</span></div>
        <div class="eda-stage"><div class="n">04 LOAD</div><strong>${coins.length} rows</strong><span>${ts && !isNaN(ts) ? 'Snapshot ' + esc(ts.toLocaleString()) : 'Snapshot time unavailable'}</span></div>
      </div></div>`;
  }

  function secValidation(coins) {
    const r = lastRefresh;
    if (!r) {
      return `<div class="panel"><h2>02 / Validation report</h2>
        <p class="eda-sub">Click <b>Refresh pipeline</b> to capture the Pydantic validation results from the backend.</p>
        <p class="eda-note">Schema-level checks available from the current snapshot: ${coins.filter(c => !(num(c.current_price) > 0)).length} assets without a positive price · ${coins.filter(c => !(num(c.market_cap) > 0)).length} without market cap.</p></div>`;
    }
    const raw = r.rejections || r.rejected_details || r.rejected_records || r.errors || r.validation_errors;
    let reasons = '';
    if (Array.isArray(raw) && raw.length) {
      const counts = {};
      raw.forEach(it => {
        const k = typeof it === 'string' ? it : (it.reason || it.error || it.message || it.msg || JSON.stringify(it));
        counts[k] = (counts[k] || 0) + 1;
      });
      reasons = `<div class="eda-scroll"><table><thead><tr><th>Rejection reason</th><th>Count</th></tr></thead><tbody>` +
        Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 12)
          .map(([k, v]) => `<tr><td class="eda-txt">${esc(k)}</td><td>${v}</td></tr>`).join('') + '</tbody></table></div>';
    } else if (Number(r.rejected) === 0) {
      reasons = '<p class="eda-note">No records were rejected in this run: every fetched asset passed the Pydantic schema.</p>';
    } else {
      reasons = '<p class="eda-note">The refresh response did not include per-record rejection reasons.</p>';
    }
    const rate = r.fetched ? (r.valid / r.fetched * 100) : NaN;
    return `<div class="panel"><h2>02 / Validation report</h2>
      <p class="eda-sub">Result of the last pipeline run in this session.</p>
      <div class="eda-row"><span>Valid</span><div class="eda-bar"><i style="width:${Number.isFinite(rate) ? rate : 0}%"></i></div><span>${f(rate, 1)}%</span></div>
      <div class="eda-row"><span>Fetched / valid / rejected</span><span></span><span>${esc(r.fetched ?? '—')} / ${esc(r.valid ?? '—')} / ${esc(r.rejected ?? '—')}</span></div>
      <div class="eda-row"><span>Volatility alerts</span><span></span><span>${(r.alerts || []).length}</span></div>
      ${reasons}</div>`;
  }

  function secSummary(coins) {
    const defs = [
      ['volatility_pct', 'Volatility (%)'], ['price_change_percentage_24h', '24h change (%)'],
      ['liquidity_ratio', 'Volume / cap'], ['total_volume', 'Volume (USD)'], ['market_cap', 'Market cap (USD)']
    ];
    const big = k => k === 'total_volume' || k === 'market_cap';
    const fmt = (k, v) => big(k) ? money(v) : f(v, k === 'liquidity_ratio' ? 4 : 2);
    const rows = defs.map(([k, label]) => {
      const d = describe(coins.map(c => num(c[k])));
      return `<tr><td>${label}</td><td>${d.n || 0}</td><td>${fmt(k, d.mean)}</td><td>${fmt(k, d.std)}</td><td>${fmt(k, d.min)}</td><td>${fmt(k, d.median)}</td><td>${fmt(k, d.max)}</td></tr>`;
    }).join('');
    return `<div class="panel"><h2>03 / Summary statistics</h2>
      <p class="eda-sub">Equivalent of pandas <code>describe()</code> on the current snapshot.</p>
      <div class="eda-scroll"><table><thead><tr><th>Variable</th><th>n</th><th>Mean</th><th>Std</th><th>Min</th><th>Median</th><th>Max</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="eda-note">Mean far above median means a right-skewed variable (a few giant assets), which is why medians are more reliable than means for market cap and volume.</p></div>`;
  }

  function secHist() {
    return `<div class="panel"><h2>04 / Distribution of 24h change</h2>
      <p class="eda-sub" id="edaHistSub"></p>
      <div class="eda-chart"><canvas id="edaHist"></canvas></div></div>`;
  }

  function drawHist(coins) {
    const vals = finite(coins.map(c => num(c.price_change_percentage_24h)));
    const canvas = document.getElementById('edaHist');
    if (!canvas || typeof Chart === 'undefined' || !vals.length) return;
    const lo = Math.floor(Math.min(...vals)), hi = Math.ceil(Math.max(...vals));
    const bins = [];
    for (let x = lo; x < hi || bins.length === 0; x += 1) bins.push({ from: x, n: 0 });
    vals.forEach(v => { const i = Math.min(Math.floor(v) - lo, bins.length - 1); bins[i].n++; });
    const d = describe(vals);
    document.getElementById('edaHistSub').textContent =
      `1-point bins · mean ${pct(d.mean)} · median ${pct(d.median)} · std ${f(d.std)} pts · ${vals.filter(v => v > 0).length} up / ${vals.filter(v => v < 0).length} down`;
    if (histChart) histChart.destroy();
    histChart = new Chart(canvas, {
      type: 'bar',
      data: {
        labels: bins.map(b => `${b.from}% to ${b.from + 1}%`),
        datasets: [{ data: bins.map(b => b.n), backgroundColor: bins.map(b => b.from >= 0 ? 'rgba(183,228,69,.82)' : 'rgba(240,106,114,.82)') }]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: i => `${i.raw} assets` } } },
        scales: { y: { ticks: { precision: 0 }, title: { display: true, text: 'Assets' } }, x: { ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: 8 } } }
      }
    });
  }

  function secCorr(coins) {
    const lg = v => (Number.isFinite(v) && v > 0) ? Math.log10(v) : NaN;
    const vars = [
      ['Market cap (log)', coins.map(c => lg(num(c.market_cap)))],
      ['Volume (log)', coins.map(c => lg(num(c.total_volume)))],
      ['Volatility', coins.map(c => num(c.volatility_pct))],
      ['24h change', coins.map(c => num(c.price_change_percentage_24h))],
      ['Volume/cap', coins.map(c => num(c.liquidity_ratio))]
    ];
    const color = v => !Number.isFinite(v) ? 'transparent'
      : v >= 0 ? `rgba(183,228,69,${Math.min(Math.abs(v), 1) * .75})` : `rgba(240,106,114,${Math.min(Math.abs(v), 1) * .75})`;
    let strongest = { v: 0, a: '', b: '' };
    const body = vars.map(([la, xa], i) => '<tr><td>' + la + '</td>' + vars.map(([lb, xb], j) => {
      const r = i === j ? 1 : pearson(xa, xb);
      if (j > i && Number.isFinite(r) && Math.abs(r) > Math.abs(strongest.v)) strongest = { v: r, a: la, b: lb };
      return `<td style="background:${color(r)}">${Number.isFinite(r) ? r.toFixed(2) : '—'}</td>`;
    }).join('') + '</tr>').join('');
    return `<div class="panel eda-wide"><h2>05 / Correlation matrix</h2>
      <p class="eda-sub">Pearson correlation across assets. Market cap and volume are log-transformed because they span several orders of magnitude.</p>
      <div class="eda-scroll"><table class="eda-heat"><thead><tr><th></th>${vars.map(v => `<th>${v[0]}</th>`).join('')}</tr></thead><tbody>${body}</tbody></table></div>
      <p class="eda-note">${strongest.a ? `Strongest off-diagonal pair: <b>${esc(strongest.a)}</b> vs <b>${esc(strongest.b)}</b> (r = ${strongest.v.toFixed(2)}). ` : ''}Correlation on one snapshot of 50 assets describes this moment only and does not imply causation.</p></div>`;
  }

  function secOutliers(coins) {
    const metrics = [
      ['Volatility', c => num(c.volatility_pct), v => v, v => f(v) + '%'],
      ['24h change', c => num(c.price_change_percentage_24h), v => v, v => pct(v)],
      ['Volume/cap', c => num(c.liquidity_ratio), v => v > 0 ? Math.log10(v) : NaN, v => f(v * 100) + '%']
    ];
    const hits = [];
    metrics.forEach(([label, get, tf, show]) => {
      const pts = coins.map(c => ({ c, raw: get(c), t: tf(get(c)) })).filter(p => Number.isFinite(p.t));
      const sorted = pts.map(p => p.t).sort((a, b) => a - b);
      const q1 = quantile(sorted, .25), q3 = quantile(sorted, .75), iqr = q3 - q1;
      const lo = q1 - 1.5 * iqr, hi = q3 + 1.5 * iqr;
      pts.forEach(p => {
        if (p.t < lo || p.t > hi) hits.push({ sym: sym(p.c), name: p.c.name, label, val: show(p.raw), dir: p.t > hi ? 'high' : 'low', dist: Math.abs(p.t - (p.t > hi ? hi : lo)) / (iqr || 1) });
      });
    });
    hits.sort((a, b) => b.dist - a.dist);
    const rows = hits.slice(0, 14).map(h => `<tr><td>${esc(h.sym)}</td><td class="eda-txt">${esc(h.label)}</td><td>${esc(h.val)}</td><td><span class="eda-tag ${h.dir === 'high' ? 'red' : ''}">${h.dir}</span></td></tr>`).join('')
      || '<tr><td colspan="4" class="eda-txt">No outliers detected.</td></tr>';
    return `<div class="panel"><h2>06 / Outlier detection</h2>
      <p class="eda-sub">Tukey IQR rule: values beyond 1.5 × IQR from the quartiles (Volume/cap tested on a log scale). ${hits.length} flags in total; strongest shown.</p>
      <div class="eda-scroll"><table><thead><tr><th>Asset</th><th>Metric</th><th>Value</th><th>Side</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="eda-note">This is a statistical complement to the fixed ${CONFIG.alertThreshold}% SHOCK alert rule.</p></div>`;
  }

  function secSegments(coins) {
    const groups = { 'Stablecoins / pegged': coins.filter(isStable), 'Other assets': coins.filter(c => !isStable(c)) };
    const totCap = coins.reduce((s, c) => s + (num(c.market_cap) || 0), 0);
    const totVol = coins.reduce((s, c) => s + (num(c.total_volume) || 0), 0);
    const rows = Object.entries(groups).map(([name, g]) => {
      const cap = g.reduce((s, c) => s + (num(c.market_cap) || 0), 0);
      const vol = g.reduce((s, c) => s + (num(c.total_volume) || 0), 0);
      const v = describe(g.map(c => num(c.volatility_pct))).median;
      const ch = describe(g.map(c => Math.abs(num(c.price_change_percentage_24h)))).median;
      return `<tr><td>${name}</td><td>${g.length}</td><td>${money(cap)}</td><td>${f(totCap ? cap / totCap * 100 : NaN, 1)}%</td><td>${money(vol)}</td><td>${f(totVol ? vol / totVol * 100 : NaN, 1)}%</td><td>${f(v)}%</td><td>${f(ch)}%</td></tr>`;
    }).join('');
    const stableNames = groups['Stablecoins / pegged'].map(sym).join(', ');
    return `<div class="panel"><h2>07 / Stablecoins vs the rest</h2>
      <p class="eda-sub">Pegged assets barely move but carry large volume, so they inflate totals.</p>
      <div class="eda-scroll"><table><thead><tr><th>Segment</th><th>n</th><th>Cap</th><th>Cap %</th><th>Volume</th><th>Vol %</th><th>Med vol.</th><th>Med |24h|</th></tr></thead><tbody>${rows}</tbody></table></div>
      <p class="eda-note">Classified as stable: ${esc(stableNames) || 'none'} (known symbols, or price near $1 with under 1% intraday range).</p></div>`;
  }

  function secConcentration(coins) {
    const byCap = [...coins].sort((a, b) => (num(b.market_cap) || 0) - (num(a.market_cap) || 0));
    const tot = byCap.reduce((s, c) => s + (num(c.market_cap) || 0), 0);
    const share = list => tot ? list.reduce((s, c) => s + (num(c.market_cap) || 0), 0) / tot * 100 : NaN;
    const nonStable = byCap.filter(c => !isStable(c));
    const totNS = nonStable.reduce((s, c) => s + (num(c.market_cap) || 0), 0);
    const btc = byCap.filter(c => sym(c) === 'BTC'), eth = byCap.filter(c => sym(c) === 'ETH');
    const items = [
      ['BTC share', share(btc)], ['ETH share', share(eth)], ['Top 5', share(byCap.slice(0, 5))],
      ['Top 10', share(byCap.slice(0, 10))], ['Stablecoins', share(byCap.filter(isStable))],
      ['BTC ex-stable', totNS && btc.length ? (num(btc[0].market_cap) / totNS * 100) : NaN]
    ];
    const bar = ([l, v]) => `<div class="eda-row"><span>${l}</span><div class="eda-bar"><i style="width:${Number.isFinite(v) ? Math.min(v, 100) : 0}%"></i></div><span>${f(v, 1)}%</span></div>`;
    return `<div class="panel"><h2>08 / Market concentration</h2>
      <p class="eda-sub">Share of total market cap within the ${coins.length} tracked assets.</p>
      ${items.map(bar).join('')}
      <p class="eda-note">Shares are relative to this top-50 set, not the whole crypto market.</p></div>`;
  }

  function allKeys(coins) {
    const keys = [];
    coins.forEach(c => Object.keys(c).forEach(k => { if (!keys.includes(k)) keys.push(k); }));
    EXPECTED_FIELDS.forEach(k => { if (!keys.includes(k)) keys.push(k); });
    return keys;
  }

  function secQuality(coins) {
    const keys = allKeys(coins);
    const rows = keys.map(k => {
      const present = coins.filter(c => c[k] !== null && c[k] !== undefined && c[k] !== '').length;
      const comp = coins.length ? present / coins.length * 100 : 0;
      const sample = coins.map(c => c[k]).find(v => v !== null && v !== undefined);
      const type = sample === undefined ? '—' : Array.isArray(sample) ? 'list' : typeof sample === 'object' ? 'object' : typeof sample === 'number' ? 'number' : typeof sample === 'boolean' ? 'bool' : 'text';
      const bad = comp < 100;
      return { k, comp, type, row: `<tr><td>${esc(k)}</td><td>${type}</td><td class="eda-txt">${esc(DICT[k] || '—')}</td><td><div class="eda-bar ${bad ? 'red' : ''}"><i style="width:${comp}%"></i></div></td><td class="${bad ? 'eda-bad' : 'eda-ok'}">${f(comp, 0)}%</td></tr>` };
    });
    rows.sort((a, b) => a.comp - b.comp);
    const cells = coins.length * keys.length;
    const filled = rows.reduce((s, r) => s + r.comp / 100 * coins.length, 0);
    const empty = rows.filter(r => r.comp === 0).length;
    return `<div class="panel eda-wide"><h2>09 / Data dictionary &amp; quality</h2>
      <p class="eda-sub">Overall completeness ${f(cells ? filled / cells * 100 : NaN, 1)}% · ${empty} of ${keys.length} columns are completely empty. Least complete columns first.</p>
      <div class="eda-scroll" style="max-height:420px"><table><thead><tr><th>Column</th><th>Type</th><th>Meaning</th><th>Completeness</th><th></th></tr></thead><tbody>${rows.map(r => r.row).join('')}</tbody></table></div>
      <p class="eda-note">Columns at 0% usually mean a field is fetched from the API but not kept by the extract/transform step. Fixing those in the pipeline improves every chart above.</p></div>`;
  }

  function secRuns() {
    return `<div class="panel eda-wide"><h2>10 / Pipeline run history</h2>
      <p class="eda-sub" id="edaRunsSub">Loading run history…</p>
      <div class="eda-chart" id="edaRunsChartBox" style="height:220px;display:none"><canvas id="edaRunsChart"></canvas></div>
      <div class="eda-scroll" id="edaRunsTable"></div></div>`;
  }

  let runsChart = null;
  async function loadRuns() {
    const sub = document.getElementById('edaRunsSub');
    if (!sub) return;
    try {
      const res = await fetch('/api/runs', { cache: 'no-store' });
      const data = await res.json();
      const runs = Array.isArray(data.runs) ? data.runs : [];
      if (!runs.length) { sub.textContent = 'No runs recorded yet. Click Refresh pipeline to log the first one.'; return; }
      sub.textContent = `${runs.length} most recent runs, stored in the pipeline_runs table (audit log of every ETL execution).`;
      const rows = [...runs].reverse().map(r => `<tr><td>${esc(new Date(r.run_at).toLocaleString())}</td><td>${esc(r.fetched)}</td><td>${esc(r.valid)}</td><td class="${Number(r.rejected) > 0 ? 'eda-bad' : ''}">${esc(r.rejected)}</td><td>${esc(r.saved)}</td><td>${esc(r.alerts)}</td><td>${f(num(r.duration_ms) / 1000, 1)}s</td><td>${money(num(r.total_market_cap))}</td></tr>`).join('');
      document.getElementById('edaRunsTable').innerHTML = `<table><thead><tr><th>Run time</th><th>Fetched</th><th>Valid</th><th>Rejected</th><th>Saved</th><th>Alerts</th><th>Duration</th><th>Total cap</th></tr></thead><tbody>${rows}</tbody></table>`;
      if (runs.length >= 2 && typeof Chart !== 'undefined') {
        document.getElementById('edaRunsChartBox').style.display = 'block';
        if (runsChart) runsChart.destroy();
        runsChart = new Chart(document.getElementById('edaRunsChart'), {
          type: 'line',
          data: {
            labels: runs.map(r => new Date(r.run_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })),
            datasets: [{ label: 'Total market cap (USD)', data: runs.map(r => num(r.total_market_cap)), borderColor: '#B7E445', backgroundColor: 'rgba(183,228,69,.15)', fill: true, tension: .2, pointRadius: 3 }]
          },
          options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false }, tooltip: { callbacks: { label: i => money(i.raw) } } }, scales: { y: { ticks: { callback: v => money(v) } }, x: { ticks: { maxTicksLimit: 6, maxRotation: 0 } } } }
        });
      } else {
        sub.textContent += ' Run the pipeline at least twice to see the market-cap trend.';
      }
    } catch (e) {
      sub.textContent = 'Run history unavailable: ' + e.message;
    }
  }

  /* ---------- export ---------- */
  function exportCSV(coins) {
    const keys = allKeys(coins).filter(k => k !== 'sparkline_in_7d');
    const cell = v => {
      if (v === null || v === undefined) return '';
      const s = typeof v === 'object' ? JSON.stringify(v) : String(v);
      return /[",\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
    };
    const csv = [keys.join(',')].concat(coins.map(c => keys.map(k => cell(c[k])).join(','))).join('\n');
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url; a.download = 'blackcoin_snapshot_' + new Date().toISOString().slice(0, 10) + '.csv';
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 500);
  }

  /* ---------- build ---------- */
  function build(data) {
    const coins = Array.isArray(data && data.coins) ? data.coins : [];
    injectCSS();
    let root = document.getElementById('edaRoot');
    if (!root) {
      root = document.createElement('section');
      root.id = 'edaRoot';
      const footer = document.querySelector('.footer');
      if (footer && footer.parentNode) footer.parentNode.insertBefore(root, footer);
      else document.body.appendChild(root);
    }
    if (!coins.length) { root.innerHTML = ''; return; }

    root.innerHTML = `
      <div class="eda-head">
        <div><div class="eyebrow">ANALYSIS / 002</div><h2>Pipeline &amp; EDA report</h2>
        <p>Methodology, validation, data quality and exploratory analysis of the latest snapshot.</p></div>
        <button class="btn secondary" id="edaCsv" type="button">⬇ Export CSV</button>
      </div>
      <div class="eda-grid">
        ${secMethod()}
        ${secStages(data, coins)}
        ${secValidation(coins)}
        ${secSummary(coins)}
        ${secHist()}
        ${secSegments(coins)}
        ${secCorr(coins)}
        ${secOutliers(coins)}
        ${secConcentration(coins)}
        ${secQuality(coins)}
        ${secRuns()}
      </div>`;
    root.querySelectorAll('.eda-grid > .panel').forEach(p => p.classList.add('eda-panel'));
    document.getElementById('edaCsv').addEventListener('click', () => exportCSV(coins));
    drawHist(coins);
    loadRuns();
  }

  /* ---------- hooks into index.html ---------- */
  function install() {
    const origRender = window.render;
    const origApi = window.apiRequest;
    if (typeof origRender !== 'function') { console.warn('eda.js: render() not found'); return; }
    window.render = function (data) {
      const out = origRender.apply(this, arguments);
      try { build(data); } catch (e) { console.error('eda.js build error', e); }
      return out;
    };
    if (typeof origApi === 'function') {
      window.apiRequest = async function (url) {
        const res = await origApi.apply(this, arguments);
        if (String(url).indexOf('/api/refresh') !== -1) lastRefresh = res;
        return res;
      };
    }
  }
  install();
})();
