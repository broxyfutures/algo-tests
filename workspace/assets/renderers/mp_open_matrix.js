// Рендерер mp_open_matrix: место и тип открытия → тип дня, описательная статистика.
// Ожидает window.DATA = {test, meta, zones, open_types, day_types, variants, rows} из results.json
// (mp-es-pipeline/scripts/11_test_open_matrix.py). rows: [date, f0 zone, f0 open, f0 day, f0 dir, f1 …, a0 …, a1 …].
// Режим «своя строка» пересчитывает точку и тип открытия, Double-Distribution и композиты прямо здесь,
// из цен блоков window.MPCHART (assets/data/mp_chart_data.js), теми же правилами, что пайплайн.
// На странице: #hdr-meta, #om-controls, #om-calc, #om-note. Страница: калькулятор (точка и тип
// открытия) → большое кольцо типов дня и легенда с разницей против всех дней выборки.
// «Показать на графике» кладёт дни в localStorage (mp-chart-pick) и открывает страницу инструмента с #pick.
(function(){
  const D = window.DATA, M = D.meta;
  const KEY = 'mp-open-matrix-' + D.test + '-v2';
  // nv: 1 учитывать Normal Variation, 0 исключить из выборки
  const S = {m:'f', c:'0', from:'', to:'', ticks:8, cz:'*', co:'*', nv:1};
  try{ Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); }catch(e){}
  if (!['f', 'a', 'x'].includes(S.m)) S.m = 'f';
  const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} };
  const f1 = v => Number.isFinite(v) ? v.toFixed(1) : '';
  const sg = v => (v > 0 ? '+' : '') + f1(v);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;'}[c]));

  const ZN = Object.fromEntries(D.zones);
  const OT = D.open_types, OTN = Object.fromEntries(OT);
  const DT = D.day_types;
  const FIRST = D.rows[0][0], LAST = D.rows[D.rows.length - 1][0];

  // цвета типов дня: синие, голубые, фиолетовые и розовые, порядок как в DT (nm, nt, nv, tr, dd, nc, ne).
  // Цвет закреплён за типом и не меняется, когда Normal Variation исключён.
  const st = document.createElement('style');
  st.textContent = `.om-viz{--d1:#3c65c6;--d2:#239fae;--d3:#6846c9;--d4:#cf4b73;--d5:#ae79ba;--d6:#5389e8;--d7:#a85e98}
:root[data-theme="light"] .om-viz{--d1:#4771d4;--d2:#1999a9;--d3:#5c36b9;--d4:#bd3b64;--d5:#9561a1;--d6:#3e72cf;--d7:#a85e98}
#om-controls .ctl,#om-calc .ctl{flex-wrap:wrap;max-width:100%}
#om-controls .seg,#om-calc .seg{flex-wrap:wrap;max-width:100%}
.om-num{font:inherit;font-size:11px;width:58px;padding:5px 6px;background:var(--surface-2);color:var(--t1);border:1px solid var(--border-2);border-radius:2px;font-family:var(--mono)}
.om-date{font:inherit;font-size:11px;padding:4px 6px;background:var(--surface-2);color:var(--t1);border:1px solid var(--border-2);border-radius:2px;font-family:var(--mono)}
.om-inl{display:inline-flex;align-items:center;gap:7px;font-size:11px;color:var(--t3);flex-wrap:wrap}
.om-busy{font-size:11px;color:var(--t3);margin:0 0 10px}
.om-calc .om-cin{margin-bottom:6px}
.om-res{display:flex;gap:28px 40px;align-items:center;flex-wrap:wrap;border-top:1px solid var(--border);padding-top:18px}
.om-donut{flex:0 1 560px;max-width:100%}
.om-donut svg{display:block;width:100%;height:auto;overflow:visible}
.om-donut .om-lead{stroke:var(--t4);fill:none;stroke-width:1}
.om-donut .om-lab{font-family:var(--mono);font-size:12px;fill:var(--t2)}
.om-donut .om-lab tspan{fill:var(--t1);font-weight:600}
.om-side{flex:1 1 340px;min-width:0;font-family:var(--mono)}
.om-head{font-size:11px;letter-spacing:.06em;color:var(--t3);margin-bottom:12px;line-height:1.6}
.om-head b{color:var(--t1);font-weight:600}
table.om-leg{border-collapse:collapse;width:100%;font-size:12.5px}
.om-leg th{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3);font-weight:500;text-align:right;padding:0 0 8px 12px;border-bottom:1px solid var(--border)}
.om-leg th:first-child{text-align:left;padding-left:0}
.om-leg td{padding:8px 0 8px 12px;border-bottom:1px solid var(--border);text-align:right;color:var(--t1);font-variant-numeric:tabular-nums}
.om-leg td:first-child{text-align:left;padding-left:0;color:var(--t2);white-space:nowrap}
.om-leg td:first-child i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:9px;vertical-align:-1px}
.om-leg td.n{color:var(--t3)}
.om-leg td.up{color:var(--up)}.om-leg td.dn{color:var(--dn)}
.om-leg tr.zero td{color:var(--t4)}
.om-go{display:inline-block;margin-top:14px;font-size:11px;color:var(--up)}
.om-go:hover{color:var(--t1)}`;
  document.head.appendChild(st);
  const slot = i => `var(--d${i})`;
  const SHORT = {'Double-Distribution Trend':'DD-Trend', 'Normal Variation':'Normal Var.',
                 'Neutral-Center':'Neutral-C', 'Neutral-Extreme':'Neutral-E'};

  // ================================================================ пересчёт со своей строкой
  // Порт mp/profile.py, mp/daytype.py (только Double-Distribution / Trend / Normal Variation:
  // остальное от строки не зависит), mp/composite.py + scripts/06, mp/opentype.py.
  const TICK = 0.25;
  const P = {VA: 0.68, TAIL: 2, DD: 0.25, OVL: 0.50, POS: [0.25, 0.75], PEAK: 0.80, TROUGH: 0.60, GAP: 3,
             SYM: 1 / 3, TF_N: 2, TF_BLOCKS: 10, CLOSE: 0.25};
  // поля дня в данных графика
  const F = {bl:1, o:7, h:8, l:9, c:10, dt:11, dd:12, ref0:17, flags:22, c1030:23, sh:24};

  function counts(lows, highs, row){
    const li = lows.map(v => Math.floor(v / row + 1e-9)), hj = highs.map(v => Math.floor(v / row + 1e-9));
    let base = Infinity, top = -Infinity;
    for (let k = 0; k < li.length; k++){ if (li[k] < base) base = li[k]; if (hj[k] > top) top = hj[k]; }
    const c = new Array(top - base + 1).fill(0);
    for (let k = 0; k < li.length; k++) for (let r = li[k]; r <= hj[k]; r++) c[r - base]++;
    return {base, c};
  }
  function pocIndex(c){
    let mx = -1; for (const v of c) if (v > mx) mx = v;
    const mid = (c.length - 1) / 2;
    let best = 0, bd = Infinity;
    c.forEach((v, i) => { if (v === mx){ const d = Math.abs(i - mid); if (d < bd){ bd = d; best = i; } } });
    return best;
  }
  function valueArea(c, poc){
    const n = c.length; let sum = 0; for (const v of c) sum += v;
    const target = P.VA * sum;
    const part = (a, b) => { let s = 0; for (let i = Math.max(a, 0); i < Math.min(b, n); i++) s += c[i]; return s; };
    let lo = poc, hi = poc, acc = c[poc];
    while (acc < target - 1e-9 && (lo > 0 || hi < n - 1)){
      const up = hi < n - 1 ? part(hi + 1, hi + 3) : -1;
      const dn = lo > 0 ? part(lo - 2, lo) : -1;
      if (up >= dn){ acc += Math.max(up, 0); hi = Math.min(hi + 2, n - 1); }
      if (dn >= up){ acc += Math.max(dn, 0); lo = Math.max(lo - 2, 0); }
    }
    return [lo, hi];
  }
  // VAH / VAL как в tpo_stats: край строки, но не дальше проторгованного high / low
  function vaOf(lows, highs, row){
    const p = counts(lows, highs, row), ip = pocIndex(p.c), [vlo, vhi] = valueArea(p.c, ip);
    let mx = -Infinity, mn = Infinity;
    for (let k = 0; k < lows.length; k++){ if (highs[k] > mx) mx = highs[k]; if (lows[k] < mn) mn = lows[k]; }
    return {vah: Math.min((p.base + vhi + 1) * row, mx), val: Math.max((p.base + vlo) * row, mn), c: p.c, hi: mx, lo: mn};
  }
  function edgeRun(c, fromTop){
    let k = 0, n = c.length;
    for (let j = 0; j < n; j++){ if (c[fromTop ? n - 1 - j : j] !== 1) break; k++; }
    return k;
  }
  function ddSplit(c){
    const n = c.length, top = edgeRun(c, true), bot = edgeRun(c, false);
    const single = c.map((v, i) => v === 1 && i < n - top && i >= bot);
    let total = 0; const cum = c.map(v => (total += v));
    let i = 0;
    while (i < n){
      if (single[i]){
        let j = i; while (j < n && single[j]) j++;
        if (j - i >= P.TAIL){
          const below = i > 0 ? cum[i - 1] : 0, above = total - cum[j - 1];
          if (below >= P.DD * total && above >= P.DD * total) return true;
        }
        i = j;
      } else i++;
    }
    return false;
  }
  function tfViol(lows, highs, up){
    const last = Math.min(P.TF_BLOCKS, lows.length); let v = 0;
    for (let i = 1; i < last; i++){
      const a = Math.max(0, i - P.TF_N);
      if (up){ let m = Infinity; for (let k = a; k < i; k++) m = Math.min(m, lows[k]); if (lows[i] < m) v++; }
      else { let m = -Infinity; for (let k = a; k < i; k++) m = Math.max(m, highs[k]); if (highs[i] > m) v++; }
    }
    return v;
  }
  // форма склеенного профиля (mp/composite.py: shape). Сглаживание как np.convolve(c, ones(3)/3, 'same')
  function shapeOk(c){
    const n = c.length, ip = pocIndex(c), [lo, hi] = valueArea(c, ip);
    const pos = (ip + 0.5) / n, w = 1 / 3;
    const sm = c.map((_, j) => { let s = 0; for (let k = j - 1; k <= j + 1; k++) if (k >= 0 && k < n) s += c[k] * w; return s; });
    let pk = 0; for (let j = 1; j < n; j++) if (sm[j] > sm[pk]) pk = j;
    let bimodal = false;
    for (let j = 1; j < n - 1 && !bimodal; j++){
      if (sm[j] >= sm[j - 1] && sm[j] >= sm[j + 1] && Math.abs(j - pk) >= P.GAP && sm[j] >= P.PEAK * sm[pk]){
        const a = Math.min(j, pk), b = Math.max(j, pk);
        let mn = Infinity; for (let k = a; k <= b; k++) mn = Math.min(mn, sm[k]);
        if (mn <= P.TROUGH * sm[j]) bimodal = true;
      }
    }
    const up = hi - ip, dn = ip - lo;
    const sym = (Math.min(up, dn) + 1) / (Math.max(up, dn) + 1);
    return P.POS[0] <= pos && pos <= P.POS[1] && !bimodal && sym >= P.SYM;
  }
  function overlap(nval, nvah, cval, cvah){
    const ov = Math.max(0, Math.min(nvah, cvah) - Math.max(nval, cval)), w = nvah - nval;
    return w > 0 ? ov / w : (cval <= nval && nval <= cvah ? 1 : 0);
  }
  function zoneOf(o, r){
    if (o > r.high) return 'ar';
    if (o > r.vah) return 'av';
    if (o < r.low) return 'br';
    if (o < r.val) return 'bv';
    return 'iv';
  }
  // mp/opentype.py: classify по ценам блоков A, B (IB), закрытию B и блокам C + D (следующий час)
  function openType(L, H, o, c1030, r){
    const t = TICK;
    if (L.length < 2) return '';
    if (r.val <= o && o <= r.vah) return 'oai';
    const up = o > r.vah;
    const ibH = Math.max(H[0], H[1]), ibL = Math.min(L[0], L[1]);
    const nH = H.slice(2, 4), nL = L.slice(2, 4);
    const brk = up ? (nH.length > 0 && Math.max(...nH) >= ibH + t) : (nL.length > 0 && Math.min(...nL) <= ibL - t);
    const cand = () => brk ? 'otd' : 'oao';
    const vaTouch = up ? ibL <= r.vah + t : ibH >= r.val - t;
    if (vaTouch){
      const backOut = up ? c1030 > r.vah : c1030 < r.val;
      return backOut ? cand() : 'orr';
    }
    const outside = up ? o > r.high : o < r.low;
    if (!outside){
      const bTestsA = up ? L[1] <= L[0] + t : H[1] >= H[0] - t;
      return bTestsA ? cand() : 'od';
    }
    const bTouch = up ? L[1] <= r.high + t : H[1] >= r.low - t;
    if (bTouch) return cand();
    const aHeld = up ? L[1] >= L[0] - t : H[1] <= H[0] + t;
    return aHeld ? 'od' : 'oao';
  }

  // вся история с высотой строки ticks × 0.25: [{z0, t0, z1, t1, dt}] по индексу дня графика
  const engineCache = new Map();
  function engine(ticks){
    if (engineCache.has(ticks)) return engineCache.get(ticks);
    const G = window.MPCHART, days = G.modes.f.days, row = ticks * TICK, out = [];
    const blocks = days.map(d => { const L = [], H = [];
      for (let k = 0; k < d[F.bl].length; k += 2){ L.push(d[F.l] + d[F.bl][k] * TICK); H.push(d[F.l] + d[F.bl][k + 1] * TICK); }
      return [L, H]; });
    const lv = blocks.map(([L, H]) => vaOf(L, H, row));
    let cL = null, cH = null, state = null;
    days.forEach((d, i) => {
      const [L, H] = blocks[i], fl = d[F.flags], sh = d[F.sh] || 0;
      // тип дня: от строки зависит только Double-Distribution, а через него Trend и Normal Variation
      let dt = d[F.dt];
      if (dt === 'nv' || dt === 'tr' || dt === 'dd'){
        const up = d[F.dd] === 'u', rng = d[F.h] - d[F.l];
        const cp = rng > 0 ? (d[F.c] - d[F.l]) / rng : 0.5;
        const closeOk = up ? cp >= 1 - P.CLOSE : cp <= P.CLOSE;
        dt = ddSplit(lv[i].c) ? 'dd' : (tfViol(L, H, up) === 0 && closeOk ? 'tr' : 'nv');
      }
      // опора «вчерашний день»: профиль вчера с этой строкой, в день ролла со сдвигом
      const r0 = d[F.ref0];
      const refDay = r0 ? {vah: lv[i - 1].vah + sh, val: lv[i - 1].val + sh, high: r0[3], low: r0[4]} : null;
      // композит: ролл сдвигает открытый композит на спред
      if ((fl & 1) && cL){ cL = cL.map(v => v + sh); cH = cH.map(v => v + sh);
        state = {...state, vah: state.vah + sh, val: state.val + sh, high: state.high + sh, low: state.low + sh}; }
      const refComp = !state || !r0 ? null : state.days >= 2 ? state : refDay;
      let start = true;
      if (cL && r0){
        const cs = vaOf(cL, cH, row);
        if (overlap(lv[i].val, lv[i].vah, cs.val, cs.vah) > P.OVL){
          const tl = cL.concat(L), th = cH.concat(H);
          if (shapeOk(counts(tl, th, row).c)){ start = false; cL = tl; cH = th; state = {days: state.days + 1}; }
        }
      }
      if (start){ cL = L.slice(); cH = H.slice(); state = {days: 1}; }
      const cs = vaOf(cL, cH, row);
      Object.assign(state, {vah: cs.vah, val: cs.val, high: cs.hi, low: cs.lo});

      const o = d[F.o], c1030 = d[F.c1030];
      out.push({dt,
        z0: refDay ? zoneOf(o, refDay) : '', t0: refDay ? openType(L, H, o, c1030, refDay) : '',
        z1: refComp ? zoneOf(o, refComp) : '', t1: refComp ? openType(L, H, o, c1030, refComp) : ''});
    });
    engineCache.set(ticks, out);
    return out;
  }
  window.OMEngine = engine;   // для проверки: при 8 тиках обязан совпасть с фиксированным режимом пайплайна


  // ================================================================ большое кольцо
  function donut(parts, total){
    const R = 128, r = 80, cx = 280, cy = 175;
    const Pt = (rad, ang) => [cx + rad * Math.cos(ang), cy + rad * Math.sin(ang)];
    const xy = (rad, ang) => Pt(rad, ang).map(v => v.toFixed(2)).join(' ');
    let a0 = -Math.PI / 2, arcs = '', labs = [];
    parts.forEach(p => {
      if (!p.value) return;
      const f = p.value / total, a1 = a0 + f * 2 * Math.PI, big = f > 0.5 ? 1 : 0, mid = (a0 + a1) / 2;
      const d = f >= 0.9999
        ? `M${xy(R, a0)} A${R} ${R} 0 1 1 ${xy(R, a0 + Math.PI)} A${R} ${R} 0 1 1 ${xy(R, a0)} M${xy(r, a0)} A${r} ${r} 0 1 0 ${xy(r, a0 + Math.PI)} A${r} ${r} 0 1 0 ${xy(r, a0)}Z`
        : `M${xy(R, a0)} A${R} ${R} 0 ${big} 1 ${xy(R, a1)} L${xy(r, a1)} A${r} ${r} 0 ${big} 0 ${xy(r, a0)}Z`;
      arcs += `<path d="${d}" fill="${p.color}" stroke="var(--surface)" stroke-width="2" fill-rule="evenodd"><title>${p.label}: ${f1(f * 100)}% (${p.value})</title></path>`;
      if (f >= 0.02) labs.push({f, mid, label: SHORT[p.label] || p.label});
      a0 = a1;
    });
    // подписи разводим по вертикали внутри своей половины, чтобы не наезжали друг на друга
    let leads = '';
    ['r', 'l'].forEach(side => {
      const Lb = labs.filter(l => (Math.cos(l.mid) >= 0 ? 'r' : 'l') === side)
        .map(l => ({...l, y: Pt(R + 22, l.mid)[1]})).sort((a, b) => a.y - b.y);
      for (let i = 1; i < Lb.length; i++) if (Lb[i].y - Lb[i - 1].y < 17) Lb[i].y = Lb[i - 1].y + 17;
      for (let i = Lb.length - 2; i >= 0; i--) if (Lb[i + 1].y - Lb[i].y < 17) Lb[i].y = Lb[i + 1].y - 17;
      Lb.forEach(l => {
        const x1 = cx + (side === 'r' ? 1 : -1) * (R + 26), x2 = x1 + (side === 'r' ? 14 : -14);
        const [px0, py0] = Pt(R + 3, l.mid);
        leads += `<polyline class="om-lead" points="${px0.toFixed(1)},${py0.toFixed(1)} ${x1.toFixed(1)},${l.y.toFixed(1)} ${x2.toFixed(1)},${l.y.toFixed(1)}"/>` +
          `<text class="om-lab" x="${(x2 + (side === 'r' ? 5 : -5)).toFixed(1)}" y="${(l.y + 4).toFixed(1)}" text-anchor="${side === 'r' ? 'start' : 'end'}">${l.label} <tspan>${f1(l.f * 100)}%</tspan></text>`;
      });
    });
    return `<svg viewBox="0 0 560 350" role="img" aria-label="распределение типов дня">${arcs}${leads}` +
      `<text x="${cx}" y="${cy + 2}" text-anchor="middle" fill="var(--t1)" font-size="30" font-weight="600" font-family="var(--mono)">${total}</text>` +
      `<text x="${cx}" y="${cy + 24}" text-anchor="middle" fill="var(--t3)" font-size="12" font-family="var(--mono)">дней</text></svg>`;
  }

  const hm = document.getElementById('hdr-meta');
  if (hm) hm.innerHTML = `<div><span class="dot"></span><b>${M.days}</b> дней · ${M.from} → ${M.to}</div><div>${M.note}</div><div>Результаты собраны ${M.built}</div>`;

  // ================================================================ управление
  function seg(opts, cur, cb){
    const el = document.createElement('div'); el.className = 'seg';
    opts.forEach(([v, label]) => { const b = document.createElement('button'); b.textContent = label; b.setAttribute('aria-pressed', v === cur); b.addEventListener('click', () => cb(v)); el.appendChild(b); });
    return el;
  }
  function ctl(label, ...nodes){ const w = document.createElement('div'); w.className = 'ctl'; const l = document.createElement('span'); l.className = 'ctl-label'; l.textContent = label; w.append(l, ...nodes); return w; }
  const upd = (k, v) => { S[k] = v; save(); render(); };
  const updMany = o => { Object.assign(S, o); save(); render(); };
  let IDX = null;
  const idxOf = () => IDX || (IDX = Object.fromEntries(window.MPCHART.dates.map((d, i) => [d, i])));

  function tickInput(){
    const w = document.createElement('span'); w.className = 'om-inl';
    const inp = document.createElement('input');
    inp.type = 'number'; inp.min = 1; inp.max = 400; inp.step = 1; inp.className = 'om-num'; inp.value = S.ticks;
    inp.title = 'высота строки в тиках: 4 тика = 1 пункт';
    const apply = () => { const v = Math.max(1, Math.min(400, Math.round(+inp.value || 0))); if (v !== S.ticks || S.m !== 'x') updMany({ticks: v, m: 'x'}); };
    inp.addEventListener('change', apply);
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') apply(); });
    const note = document.createElement('span'); note.textContent = `тиков = ${(S.ticks * TICK).toFixed(2)} пт`;
    w.append(inp, note);
    return w;
  }
  function dateRange(){
    const w = document.createElement('span'); w.className = 'om-inl';
    const mk = (k, ph) => { const e = document.createElement('input'); e.type = 'date'; e.className = 'om-date';
      e.min = FIRST; e.max = LAST; e.value = S[k] || ph;
      e.addEventListener('change', () => upd(k, e.value && e.value !== ph ? e.value : '')); return e; };
    const a = mk('from', FIRST), b = mk('to', LAST), dash = document.createElement('span'); dash.textContent = '→';
    w.append(a, dash, b);
    return w;
  }
  const PRESETS = [['all', '2010–2026', '', ''], ['a', '2010–2018', '', '2018-12-31'], ['b', '2019–2026', '2019-01-01', '']];
  const presetNow = () => (PRESETS.find(p => p[2] === S.from && p[3] === S.to) || [''])[0];
  const periodLabel = () => { const p = PRESETS.find(p => p[2] === S.from && p[3] === S.to);
    return p ? p[1] : `${S.from || FIRST} → ${S.to || LAST}`; };

  // ================================================================ строки выборки
  function rowsNow(){
    const inRange = d => (!S.from || d >= S.from) && (!S.to || d <= S.to);
    if (S.m === 'x'){
      const G = window.MPCHART;
      if (!G) return null;
      const E = engine(S.ticks), days = G.modes.f.days, out = [];
      G.dates.forEach((d, i) => {
        if (days[i][F.flags] & 16 || !inRange(d)) return;
        const e = E[i];
        out.push({date: d, i, z5: S.c === '0' ? e.z0 : e.z1, o: S.c === '0' ? e.t0 : e.t1, t: e.dt});
      });
      return out;
    }
    const off = 1 + 4 * D.variants.indexOf(S.m + S.c);
    return D.rows.filter(r => inRange(r[0])).map(r => ({date: r[0], z5: r[off], o: r[off + 1], t: r[off + 2]}));
  }

  // «показать на графике»: дни уходят на страницу инструмента через localStorage
  function pick(dates, label){
    if (!window.MPCHART) return;
    const idx = dates.map(d => idxOf()[d]).filter(i => i !== undefined);
    try{ localStorage.setItem('mp-chart-pick', JSON.stringify({idx, label, m: S.m === 'x' ? 'f' : S.m, c: S.c,
      ticks: S.m === 'x' ? S.ticks : 0})); }catch(e){}
  }

  // ================================================================ страница
  function render(){
    const host = document.getElementById('om-controls'); host.innerHTML = '';
    host.append(
      ctl('Блок', seg([['f', 'Фикс. 2 пт'], ['a', 'Адаптивный'], ['x', 'Своя строка']], S.m, v => upd('m', v)), ...(S.m === 'x' ? [tickInput()] : [])),
      ctl('Опора', seg([['0', 'Вчерашний день'], ['1', 'Композит']], S.c, v => upd('c', v))),
      ctl('Период', seg(PRESETS.map(p => [p[0], p[1]]), presetNow(), v => { const p = PRESETS.find(x => x[0] === v); updMany({from: p[2], to: p[3]}); }), dateRange()),
      ctl('Normal Variation', seg([[1, 'Учитывать'], [0, 'Исключить']], S.nv, v => upd('nv', v))),
    );
    const calc = document.getElementById('om-calc');
    let R = rowsNow();
    if (!R){ calc.innerHTML = '<p class="om-busy">Загружаю цены блоков для пересчёта…</p>'; return; }
    if (!S.nv) R = R.filter(r => r.t !== 'nv');
    const types = DT.map((t, i) => ({code: t[0], name: t[1], color: slot(i + 1)})).filter(t => S.nv || t.code !== 'nv');

    // выбор: точка открытия и тип открытия, «все» = без условия
    const opens = S.cz === 'iv' ? ['oai'] : S.cz === '*' ? OT.map(o => o[0]) : OT.map(o => o[0]).filter(o => o !== 'oai');
    if (S.co !== '*' && !opens.includes(S.co)) S.co = '*';
    const sel = R.filter(r => (S.cz === '*' || r.z5 === S.cz) && (S.co === '*' || r.o === S.co));
    const count = rows => { const c = {}; rows.forEach(r => { c[r.t] = (c[r.t] || 0) + 1; }); return c; };
    const cs = count(sel), cb = count(R);
    const isAll = S.cz === '*' && S.co === '*';
    const title = isAll ? 'все дни' : [S.cz === '*' ? '' : ZN[S.cz], S.co === '*' ? '' : OTN[S.co]].filter(Boolean).join(' · ');

    calc.innerHTML = '<div class="om-calc om-viz"><div class="om-cin controls"></div><div class="om-res"></div></div>';
    calc.querySelector('.om-cin').append(
      ctl('Точка открытия', seg([['*', 'все']].concat(D.zones.map(([z, n]) => [z, n])), S.cz, v => upd('cz', v))),
      ctl('Тип открытия', seg([['*', 'все']].concat(opens.map(o => [o, OTN[o]])), S.co, v => upd('co', v))));
    const res = calc.querySelector('.om-res');
    if (!sel.length){ res.innerHTML = '<p class="om-busy">В выборке нет таких дней.</p>'; }
    else {
      const rows = types.map(t => {
        const n = cs[t.code] || 0, p = n / sel.length * 100, b = (cb[t.code] || 0) / R.length * 100, d = p - b;
        return `<tr class="${n ? '' : 'zero'}"><td><i style="background:${t.color}"></i>${t.name}</td><td>${f1(p)}%</td><td class="n">${n}</td>` +
          (isAll ? '' : `<td class="${d > 0.05 ? 'up' : d < -0.05 ? 'dn' : ''}">${sg(d)}</td>`) + '</tr>';
      }).join('');
      res.innerHTML = `<div class="om-donut">${donut(types.map(t => ({label: t.name, value: cs[t.code] || 0, color: t.color})), sel.length)}</div>` +
        `<div class="om-side"><div class="om-head"><b>${esc(title)}</b><br>${sel.length} дней` +
        (isAll ? '' : ` · ${f1(sel.length / R.length * 100)}% выборки`) + ` · ${periodLabel()}${S.nv ? '' : ' · без Normal Variation'}</div>` +
        `<table class="om-leg"><thead><tr><th>Тип дня</th><th>Доля</th><th>Дней</th>${isAll ? '' : '<th title="разница с долей среди всех дней выборки">к всем дням</th>'}</tr></thead><tbody>${rows}</tbody></table>` +
        `<a class="om-go" href="../index.html#pick">показать эти дни на графике →</a></div>`;
      res.querySelector('.om-go').addEventListener('click', () => pick(sel.map(r => r.date), title + (S.nv ? '' : ' · без NV')));
    }

    const blkN = S.m === 'f' ? 'фикс. 2 пт' : S.m === 'a' ? 'адаптивный блок' : `своя строка ${S.ticks} тиков`;
    document.getElementById('om-note').textContent = `${blkN} · опора: ${S.c === '0' ? 'вчерашний день' : 'композит'} · ${periodLabel()} · ${R.length} дней в выборке` +
      (S.m === 'x' ? ' · своя строка пересчитывает VA, открытия, DD и композиты, при 8 тиках совпадает с фикс. 2 пт' : '');
  }

  render();
  // данные графика приезжают отдельным файлом: когда доехали — пересчитываем
  if (!window.MPCHART) window.addEventListener('mpchart-data', () => render(), {once: true});
})();
