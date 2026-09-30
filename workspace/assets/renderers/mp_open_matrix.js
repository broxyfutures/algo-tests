// Рендерер mp_open_matrix: точка открытия × тип открытия → тип дня, описательная статистика.
// Ожидает window.DATA = {test, meta, zones, open_types, day_types, variants, rows} из results.json
// (mp-es-pipeline/scripts/11_test_open_matrix.py). rows: [date, f0 zone, f0 open, f0 day, f0 dir, f1 …, a0 …, a1 …].
// Режим «своя строка» пересчитывает точку и тип открытия, Double-Distribution и композиты прямо здесь,
// из цен блоков window.MPCHART (assets/data/mp_chart_data.js), теми же правилами, что пайплайн.
// На странице: #hdr-meta, #om-controls, #om-calc, #om-heat, #om-heat-info, #om-types, #om-note.
// «Показать на графике» кладёт дни в localStorage (mp-chart-pick) и открывает страницу инструмента с #pick.
(function(){
  const D = window.DATA, M = D.meta;
  const KEY = 'mp-open-matrix-' + D.test;
  const S = {m:'f', c:'0', z:'5', from:'', to:'', v:'pct', sel:'_all', hs:'row', cell:'', hrow:'',
             ticks:8, cz:'av', co:'od'};
  try{ Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); }catch(e){}
  // старое поле «период» (2010–2018 / 2019–2026) переносим в даты
  if (S.p === 'a'){ S.from = ''; S.to = '2018-12-31'; } else if (S.p === 'b'){ S.from = '2019-01-01'; S.to = ''; }
  delete S.p;
  if (!['f', 'a', 'x'].includes(S.m)) S.m = 'f';
  const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} };
  const f1 = v => Number.isFinite(v) ? v.toFixed(1) : '';
  const sg = v => (v > 0 ? '+' : '') + f1(v);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;'}[c]));

  const Z5 = D.zones;
  const Z3 = [['or', 'снаружи диапазона'], ['ov', 'снаружи VA, в диапазоне'], ['iv', 'внутри VA']];
  const TO3 = {ar:'or', br:'or', av:'ov', bv:'ov', iv:'iv'};
  const OT = D.open_types, OTN = Object.fromEntries(OT);
  const DT = D.day_types, DTN = Object.fromEntries(DT.map(t => [t[0], t[1]]));
  const FIRST = D.rows[0][0], LAST = D.rows[D.rows.length - 1][0];

  // цвета типов дня: синие, голубые, фиолетовые и розовые, порядок как в DT
  // (nm, nt, nv, tr, dd, nc, ne). Соседние цвета разведены по светлоте и оттенку; подписи
  // у кольца, легенда и полоса калькулятора дублируют цвет текстом.
  const st = document.createElement('style');
  st.textContent = `.om-viz{--d1:#3c65c6;--d2:#239fae;--d3:#6846c9;--d4:#cf4b73;--d5:#ae79ba;--d6:#5389e8;--d7:#a85e98}
:root[data-theme="light"] .om-viz{--d1:#4771d4;--d2:#1999a9;--d3:#5c36b9;--d4:#bd3b64;--d5:#9561a1;--d6:#3e72cf;--d7:#a85e98}
.om-wrap{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
.om-wrap .twrap{flex:1 1 600px;min-width:0}
.om-pie{flex:0 1 340px;max-width:100%;font-family:var(--sans);font-size:12px;color:var(--t2)}
.om-pie svg{overflow:visible;max-width:100%;height:auto}
.om-pie .om-lead{stroke:var(--t4);fill:none;stroke-width:1}
.om-pie .om-lab{font-family:var(--sans);font-size:9.5px;fill:var(--t2)}
.om-pie .om-lab tspan{fill:var(--t1)}
.om-stat{margin-top:14px;border-top:1px solid var(--border);padding-top:10px}
.om-stat table{border-collapse:collapse;width:100%;font-size:11.5px}
.om-stat td{padding:2px 0;vertical-align:top}
.om-stat td:first-child{color:var(--t3);padding-right:10px}
.om-stat td:last-child{text-align:right;color:var(--t1);font-family:var(--mono)}
.om-pie .om-pt{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--t3);margin:2px 0 8px;line-height:1.5}
.om-pie ul{list-style:none;margin:10px 0 0;padding:0}
.om-pie li{display:flex;align-items:center;gap:8px;padding:2px 0}
.om-pie li i{width:10px;height:10px;border-radius:2px;flex:0 0 10px}
.om-pie li b{margin-left:auto;font-weight:500;color:var(--t1)}
.res tr.om-row{cursor:pointer}
.res tr.om-sel td{background:var(--surface-2)}
.res tr.om-zone td{border-top:1px solid var(--border-2)}
.res tr.om-sub td.state{padding-left:26px;font-weight:500;letter-spacing:.02em}
.om-heat{width:100%;overflow-x:auto}
table.om-hm{border-collapse:separate;border-spacing:3px;font-size:12.5px;width:100%;table-layout:fixed;min-width:760px}
.om-hm col.om-c0{width:240px}
.om-hm col.om-cn{width:56px}
.om-hm td.om-n{color:var(--t3);font-family:var(--mono);font-size:11.5px;background:none}
.om-hm tr.om-hz th.om-rowh{color:var(--t1);font-weight:600;padding-top:10px}
.om-hm tr.om-hs th.om-rowh{padding-left:18px}
.om-hm tr.om-ha th.om-rowh{color:var(--t1);font-weight:600}
.om-hm th.om-colh{cursor:pointer}
.om-hm th.om-colh:hover,.om-hm th.om-colsel{color:var(--t1)}
.om-hm th.om-colsel{box-shadow:inset 0 -2px 0 var(--t1)}
.om-hm th{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3);font-weight:500;padding:6px 4px;text-align:center;vertical-align:bottom;line-height:1.4}
.om-hm th.om-rowh{text-align:left;white-space:nowrap;text-transform:none;font-size:12px;letter-spacing:.02em;color:var(--t2);padding-right:12px;overflow:hidden;text-overflow:ellipsis}
.om-hm tbody th.om-rowh{cursor:pointer}
.om-hm tbody th.om-rowh:hover,.om-hm tbody th.om-rowsel{color:var(--t1)}
.om-hm tbody th.om-rowsel{box-shadow:inset 2px 0 0 var(--t1)}
.om-hm th .om-n{display:block;color:var(--t4);letter-spacing:.06em}
.om-hm td{padding:9px 4px;text-align:center;border-radius:3px;font-variant-numeric:tabular-nums}
.om-hm td.om-base{background:var(--surface-2)!important;color:var(--t2)!important}
.om-hm .om-colsel{outline:1px solid var(--border-hi);outline-offset:-1px}
.om-hm tbody td[data-k]{cursor:pointer}
.om-hm tbody td[data-k]:hover{outline:1px solid var(--t2);outline-offset:-1px}
.om-hm td.om-cellsel{outline:2px solid var(--t1)!important;outline-offset:-2px!important}
.om-scale{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:11px;color:var(--t3);font-family:var(--sans);flex-wrap:wrap}
.om-scale .om-bar{height:10px;width:220px;border-radius:2px}
.om-info{margin-top:14px;border:1px solid var(--border);border-radius:4px;padding:12px 14px;background:var(--bg);font-family:var(--sans);font-size:12px;color:var(--t2)}
.om-info[hidden]{display:none}
.om-info .om-it{display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:8px;flex-wrap:wrap}
.om-info .om-it b{color:var(--t1);font-weight:500;font-size:12.5px}
.om-info .om-x{font:inherit;font-size:11px;color:var(--t3);background:none;border:none;border-bottom:1px solid var(--border-2);padding:0 0 1px;cursor:pointer}
.om-info .om-x:hover,.om-info .om-go:hover{color:var(--t1)}
.om-info .om-go{font-size:11px;color:var(--up)}
.om-info .om-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:4px 28px}
.om-info .om-grid div{display:flex;justify-content:space-between;gap:10px;padding:2px 0;border-bottom:1px solid var(--border)}
.om-info .om-grid span{color:var(--t3)}
.om-info .om-grid em{font-style:normal;color:var(--t1);font-family:var(--mono)}
.om-info .om-dates{margin-top:8px;font-family:var(--mono);font-size:11px;color:var(--t3);line-height:1.6}
.om-calc{font-family:var(--sans)}
.om-calc .om-cin{display:flex;flex-wrap:wrap;gap:12px 18px;align-items:flex-end;margin-bottom:14px}
#om-calc .ctl{flex-wrap:wrap;max-width:100%}
#om-calc .seg{max-width:100%;flex-wrap:wrap}
.om-calc .om-cres{font-size:12px;color:var(--t3);margin-bottom:8px}
.om-calc .om-cres b{color:var(--t1);font-weight:500}
.om-sbar{display:flex;height:34px;gap:2px;border-radius:4px;overflow:hidden}
.om-sbar div{display:flex;align-items:center;justify-content:center;min-width:0;font-family:var(--mono);font-size:11.5px;color:#fff;white-space:nowrap;overflow:hidden}
.om-sbar div:first-child{border-radius:4px 0 0 4px}.om-sbar div:last-child{border-radius:0 4px 4px 0}
.om-sbase{display:flex;height:6px;gap:2px;margin-top:5px;opacity:.55}
.om-sbase div:first-child{border-radius:3px 0 0 3px}.om-sbase div:last-child{border-radius:0 3px 3px 0}
.om-leg{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:10px;font-size:12px;color:var(--t2)}
.om-leg span{display:inline-flex;align-items:center;gap:6px;white-space:nowrap}
.om-leg i{width:10px;height:10px;border-radius:2px;flex:0 0 10px}
.om-leg b{color:var(--t1);font-weight:500;font-family:var(--mono)}
.om-leg small{color:var(--t3);font-family:var(--mono);font-size:11px}
.om-leg small.up{color:var(--up)}.om-leg small.dn{color:var(--dn)}
.om-num{font:inherit;font-size:11px;width:58px;padding:5px 6px;background:var(--surface-2);color:var(--t1);border:1px solid var(--border-2);border-radius:2px;font-family:var(--mono)}
.om-date{font:inherit;font-size:11px;padding:4px 6px;background:var(--surface-2);color:var(--t1);border:1px solid var(--border-2);border-radius:2px;font-family:var(--mono)}
.om-inl{display:inline-flex;align-items:center;gap:7px;font-size:11px;color:var(--t3);flex-wrap:wrap}
#om-controls .ctl{flex-wrap:wrap;max-width:100%}
#om-controls .seg{max-width:100%}
.om-busy{font-size:11px;color:var(--t3);margin:0 0 10px}`;
  document.head.appendChild(st);
  const slot = i => `var(--d${i})`;
  // короткие имена для подписей у секторов: длинные не помещаются рядом с кольцом
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

  // ================================================================ кольцо
  function pie(title, parts, extra){
    const tot = parts.reduce((a, p) => a + p.value, 0);
    const R = 66, r = 40, cx = 165, cy = 108;
    const Pt = (rad, ang) => [cx + rad * Math.cos(ang), cy + rad * Math.sin(ang)];
    const xy = (rad, ang) => Pt(rad, ang).map(v => v.toFixed(2)).join(' ');
    let a0 = -Math.PI / 2, arcs = '', labs = [];
    parts.forEach(p => {
      if (!p.value) return;
      const f = p.value / tot, a1 = a0 + f * 2 * Math.PI, big = f > 0.5 ? 1 : 0, mid = (a0 + a1) / 2;
      const d = f >= 0.9999
        ? `M${xy(R, a0)} A${R} ${R} 0 1 1 ${xy(R, a0 + Math.PI)} A${R} ${R} 0 1 1 ${xy(R, a0)} M${xy(r, a0)} A${r} ${r} 0 1 0 ${xy(r, a0 + Math.PI)} A${r} ${r} 0 1 0 ${xy(r, a0)}Z`
        : `M${xy(R, a0)} A${R} ${R} 0 ${big} 1 ${xy(R, a1)} L${xy(r, a1)} A${r} ${r} 0 ${big} 0 ${xy(r, a0)}Z`;
      arcs += `<path d="${d}" fill="${p.color}" stroke="var(--surface)" stroke-width="2" fill-rule="evenodd"><title>${p.label}: ${f1(f * 100)}% (${p.value})</title></path>`;
      if (f >= 0.025) labs.push({f, mid, label: SHORT[p.label] || p.label});
      a0 = a1;
    });
    // подписи разводим по вертикали внутри своей половины, чтобы не наезжали друг на друга
    let leads = '';
    ['r', 'l'].forEach(side => {
      const Lb = labs.filter(l => (Math.cos(l.mid) >= 0 ? 'r' : 'l') === side)
        .map(l => ({...l, y: Pt(R + 16, l.mid)[1]}))
        .sort((a, b) => a.y - b.y);
      for (let i = 1; i < Lb.length; i++) if (Lb[i].y - Lb[i - 1].y < 13) Lb[i].y = Lb[i - 1].y + 13;
      for (let i = Lb.length - 2; i >= 0; i--) if (Lb[i + 1].y - Lb[i].y < 13) Lb[i].y = Lb[i + 1].y - 13;
      Lb.forEach(l => {
        const x1 = cx + (side === 'r' ? 1 : -1) * (R + 18), x2 = x1 + (side === 'r' ? 12 : -12);
        const [px0, py0] = Pt(R + 2, l.mid);
        leads += `<polyline class="om-lead" points="${px0.toFixed(1)},${py0.toFixed(1)} ${x1.toFixed(1)},${l.y.toFixed(1)} ${x2.toFixed(1)},${l.y.toFixed(1)}"/>` +
          `<text class="om-lab" x="${(x2 + (side === 'r' ? 4 : -4)).toFixed(1)}" y="${(l.y + 3.5).toFixed(1)}" text-anchor="${side === 'r' ? 'start' : 'end'}">${l.label} <tspan>${f1(l.f * 100)}%</tspan></text>`;
      });
    });
    const legend = parts.map(p => `<li><i style="background:${p.color}"></i>${p.label}<b>${tot ? f1(p.value / tot * 100) : ''}%</b></li>`).join('');
    return `<div class="om-pie om-viz"><div class="om-pt">${title}</div>` +
      `<svg viewBox="0 0 330 216" width="330" height="216" role="img" aria-label="${title}">${arcs}${leads}` +
      `<text x="${cx}" y="${cy - 3}" text-anchor="middle" fill="var(--t1)" font-size="19" font-weight="500">${tot}</text>` +
      `<text x="${cx}" y="${cy + 15}" text-anchor="middle" fill="var(--t3)" font-size="10.5">дней</text></svg><ul>${legend}</ul>${extra || ''}</div>`;
  }

  // ================================================================ сводка по дням (данные графика)
  const med = a => { if (!a.length) return NaN; const b = a.slice().sort((x, y) => x - y), i = b.length >> 1;
    return b.length % 2 ? b[i] : (b[i - 1] + b[i]) / 2; };
  let IDX = null;
  const idxOf = () => IDX || (IDX = Object.fromEntries(window.MPCHART.dates.map((d, i) => [d, i])));
  function summary(dates){
    const G = window.MPCHART;
    if (!G || !dates.length) return null;
    const days = dates.map(d => idxOf()[d]).filter(i => i !== undefined).map(i => G.modes[S.m === 'a' ? 'a' : 'f'].days[i]);
    if (!days.length) return null;
    const rng = days.map(d => d[8] - d[9]), ib = days.map(d => d[5] - d[6]);
    const share = days.map(d => (d[5] - d[6]) / (d[8] - d[9]) * 100);
    const cl = days.map(d => (d[10] - d[9]) / (d[8] - d[9]) * 100);
    const up = days.filter(d => d[8] > d[5]).length, dn = days.filter(d => d[9] < d[6]).length;
    const roll = days.filter(d => d[22] & 1).length, gap = days.filter(d => d[22] & 8).length;
    return [
      ['Медианный диапазон', f1(med(rng)) + ' пт'],
      ['Медианный IB', f1(med(ib)) + ' пт · ' + f1(med(share)) + '% диапазона'],
      ['Вышли за IB вверх', f1(up / days.length * 100) + '%'],
      ['Вышли за IB вниз', f1(dn / days.length * 100) + '%'],
      ['Закрытие в диапазоне', f1(med(cl)) + '% (медиана)'],
      ['Дней ролла · после дыр', roll + ' · ' + gap],
    ];
  }
  const stats = dates => { const s = summary(dates);
    return s ? '<div class="om-stat"><table>' + s.map(([k, v]) => `<tr><td>${k}</td><td>${v}</td></tr>`).join('') + '</table></div>' : ''; };

  // ================================================================ цвета тепловой карты
  // последовательная шкала в несколько оттенков: мало → голубой и синий, много → фиолетовый и
  // розовый. Светлота меняется монотонно: на тёмном фоне чем больше, тем ярче, на светлом — темнее.
  const RAMP = {
    dark:  ['#0e1b33', '#16407a', '#2f64c4', '#5a6fe0', '#8a5fd6', '#c05bbf', '#ef77b0'],
    light: ['#e8f1fc', '#b9d6f5', '#7fb0ec', '#6b83e0', '#7a58cc', '#a8409f', '#c42a73'],
  };
  const hex = h => h.replace('#', '').match(/../g).map(x => parseInt(x, 16));
  const isDark = () => document.documentElement.getAttribute('data-theme') !== 'light';
  function rampAt(t){
    const R = RAMP[isDark() ? 'dark' : 'light'].map(hex), x = Math.max(0, Math.min(1, t)) * (R.length - 1);
    const i = Math.min(Math.floor(x), R.length - 2), f = x - i;
    return R[i].map((v, k) => Math.round(v + (R[i + 1][k] - v) * f));
  }
  const relLum = v => v.reduce((s, x, i) => { const u = x / 255, l = u <= 0.03928 ? u / 12.92 : Math.pow((u + 0.055) / 1.055, 2.4);
    return s + [0.2126, 0.7152, 0.0722][i] * l; }, 0);
  const contrast = (a, b) => { const l1 = relLum(a), l2 = relLum(b); return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };
  const paint = t => { const c = rampAt(t);
    const ink = contrast(c, [11, 11, 11]) >= contrast(c, [255, 255, 255]) ? '#0b0b0b' : '#ffffff';
    return `background:rgb(${c.join(',')});color:${ink}`; };
  const rampCss = () => 'linear-gradient(90deg,' + RAMP[isDark() ? 'dark' : 'light'].join(',') + ')';

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
  function render(){
    const host = document.getElementById('om-controls'); host.innerHTML = '';
    const blk = seg([['f', 'Фикс. 2 пт'], ['a', 'Адаптивный'], ['x', 'Своя строка']], S.m, v => upd('m', v));
    host.append(
      ctl('Блок', blk, ...(S.m === 'x' ? [tickInput()] : [])),
      ctl('Композит', seg([['0', 'Выкл · опора вчера'], ['1', 'Вкл · опора композит']], S.c, v => upd('c', v))),
      ctl('Зоны', seg([['5', '5 зон'], ['3', '3 группы']], S.z, v => upd('z', v))),
      ctl('Период', seg(PRESETS.map(p => [p[0], p[1]]), presetNow(), v => { const p = PRESETS.find(x => x[0] === v); updMany({from: p[2], to: p[3]}); }), dateRange()),
      ctl('Показать', seg([['pct', '% дней'], ['n', 'дни']], S.v, v => upd('v', v))),
      ctl('Шкала карты', seg([['row', 'по типу дня'], ['all', 'общая']], S.hs, v => upd('hs', v))),
    );
    const R = rowsNow();
    if (!R){
      ['om-calc', 'om-heat', 'om-types'].forEach(id => { document.getElementById(id).innerHTML = '<p class="om-busy">Загружаю цены блоков для пересчёта…</p>'; });
      return;
    }
    if (!R.length){
      ['om-calc', 'om-heat', 'om-types'].forEach(id => { document.getElementById(id).innerHTML = '<p class="om-busy">В выбранном периоде нет дней.</p>'; });
      document.getElementById('om-heat-info').hidden = true;
      return;
    }
    const zk = r => S.z === '3' ? TO3[r.z5] : r.z5;
    const ZL = S.z === '3' ? Z3 : Z5;
    const zoneName = z => (ZL.find(x => x[0] === z) || ['', ''])[1];

    // группы строк: зона целиком + зона × тип открытия
    const G = {};
    const add = (k, r) => { const g = G[k] = G[k] || {n: 0, t: {}, dates: [], byT: {}}; g.n++; g.t[r.t] = (g.t[r.t] || 0) + 1; g.dates.push(r.date);
      (g.byT[r.t] = g.byT[r.t] || []).push(r.date); };
    R.forEach(r => { add('_all', r); add(zk(r) + '|*', r); add(zk(r) + '|' + r.o, r); add('*|' + r.o, r); });
    const allN = G._all.n;
    const base = t => (G._all.t[t] || 0) / allN * 100;
    const order = [];
    order.push({k: '_all', label: 'все дни', sub: 'базовая частота', cls: 'mid'});
    ZL.forEach(([z, name]) => {
      if (!G[z + '|*']) return;
      order.push({k: z + '|*', label: name, sub: 'вся зона', cls: 'om-zone', zone: z});
      OT.forEach(([o]) => { if (G[z + '|' + o]) order.push({k: z + '|' + o, label: OTN[o], cls: 'om-sub', zone: z}); });
    });
    if (!order.find(o => o.k === S.sel)) S.sel = '_all';

    // ---------------------------------------------------------------- калькулятор
    renderCalc(G, ZL, zoneName, base);

    // ---------------------------------------------------------------- таблица и кольцо
    const cell = (c, n, b) => {
      if (!n) return '<td class="muted">—</td>';
      const p = c / n * 100;
      if (S.v === 'n') return `<td><div class="cell"><span class="pct">${c}</span></div></td>`;
      const dd = b === null ? '' : `<span class="d ${p - b > 0 ? 'up' : p - b < 0 ? 'dn' : ''}">${sg(p - b)}</span>`;
      return `<td><div class="cell"><span class="pct">${f1(p)}</span>${dd}</div></td>`;
    };
    const selc = k => `om-row${S.sel === k ? ' om-sel' : ''}`;
    let h = `<div class="twrap"><table class="res"><thead><tr><th>Точка открытия · тип открытия</th><th>n</th><th>% зоны</th>${DT.map(t => `<th>${t[1]}</th>`).join('')}</tr></thead><tbody>`;
    order.forEach(o => {
      const g = G[o.k], zoneN = o.zone ? G[o.zone + '|*'].n : allN;
      const share = o.k === '_all' ? '' : o.cls === 'om-zone' ? f1(g.n / allN * 100) + '<span class="lbl2">от всех</span>' : f1(g.n / zoneN * 100);
      h += `<tr class="${o.cls} ${selc(o.k)}" data-k="${o.k}"><td class="state">${o.label}${o.sub ? `<span class="lbl2">${o.sub}</span>` : ''}</td><td class="n">${g.n}</td><td class="n">${share}</td>` +
        DT.map(t => cell(g.t[t[0]] || 0, g.n, o.k === '_all' ? null : base(t[0]))).join('') + '</tr>';
    });
    const sg1 = G[S.sel], selRow = order.find(o => o.k === S.sel);
    const selName = selRow.zone ? zoneName(selRow.zone) + (selRow.cls === 'om-sub' ? ' · ' + selRow.label : '') : 'все дни';
    const pie1 = pie(selName, DT.map((t, i) => ({label: t[1], value: sg1.t[t[0]] || 0, color: slot(i + 1)})),
      stats(sg1.dates) + '<p style="margin:12px 0 0"><a class="om-go-row" href="../index.html#pick">показать эти дни на графике →</a></p>');
    document.getElementById('om-types').innerHTML = `<div class="om-wrap">${h}</tbody></table></div>${pie1}</div>`;
    const goRow = document.querySelector('#om-types .om-go-row');
    if (goRow) goRow.addEventListener('click', () => pick(sg1.dates, selName));
    document.querySelectorAll('#om-types tr[data-k]').forEach(tr =>
      tr.addEventListener('click', () => upd('sel', tr.dataset.k)));

    // ---------------------------------------------------------------- тепловая карта
    // все три переменные сразу: строка = точка открытия (вся зона) и точка × тип открытия,
    // колонка = тип дня, ячейка = доля дней строки с этим типом дня (строка = 100%)
    const HR = order.filter(o => !(o.cls === 'om-sub' && ZL.length && G[o.zone + '|*'].n === G[o.k].n));   // «внутри VA» не дублируем
    if (S.cell && !S.cell.includes('#')) S.cell = '';
    const val = (g, t) => g.n ? (g.t[t] || 0) / g.n * 100 : 0;
    const colMax = {}, colMin = {};
    DT.forEach(t => {
      const v = HR.filter(o => o.k !== '_all').map(o => val(G[o.k], t[0]));
      colMax[t[0]] = Math.max(...v, 0.1); colMin[t[0]] = Math.min(...v, colMax[t[0]]);
    });
    const mxAll = Math.max(...DT.map(t => colMax[t[0]]), 1);
    // «по типу дня»: в каждой колонке своя шкала от минимума к максимуму; «общая»: 0 → максимум карты
    const norm = (p, t) => S.hs === 'row'
      ? (colMax[t] - colMin[t] < 1e-9 ? 0.5 : (p - colMin[t]) / (colMax[t] - colMin[t]))
      : p / mxAll;
    const rowName = o => o.k === '_all' ? 'все дни' : o.cls === 'om-zone' ? zoneName(o.zone) : zoneName(o.zone) + ' · ' + o.label;
    let hmh = `<table class="om-hm"><colgroup><col class="om-c0"><col class="om-cn">${DT.map(() => '<col>').join('')}</colgroup>` +
      `<thead><tr><th class="om-rowh">Точка · тип открытия</th><th>n</th>` +
      DT.map(t => `<th class="om-colh${S.hrow === t[0] && !S.cell ? ' om-colsel' : ''}" data-t="${t[0]}" title="сводка по типу «${t[1]}»">${SHORT[t[1]] || t[1]}</th>`).join('') +
      '</tr></thead><tbody>';
    HR.forEach(o => {
      const g = G[o.k], lab = o.k === '_all' ? 'все дни' : o.cls === 'om-zone' ? zoneName(o.zone) : o.label;
      hmh += `<tr class="${o.cls === 'om-zone' ? 'om-hz' : o.cls === 'om-sub' ? 'om-hs' : 'om-ha'}"><th class="om-rowh${S.sel === o.k ? ' om-rowsel' : ''}" data-k="${o.k}" title="${esc(rowName(o))}">${esc(lab)}</th><td class="om-n">${g.n}</td>` +
        DT.map(t => {
          const p = val(g, t[0]), k = o.k + '#' + t[0];
          if (o.k === '_all') return `<td class="om-base">${f1(p)}%</td>`;
          return `<td data-k="${k}" class="${S.cell === k ? 'om-cellsel' : ''}" style="${paint(norm(p, t[0]))}" ` +
            `title="${esc(rowName(o))} → ${t[1]}: ${f1(p)}% (${g.t[t[0]] || 0} из ${g.n}). Клик: сводка">${f1(p)}%</td>`;
        }).join('') + '</tr>';
    });
    hmh += `</tbody></table>`;
    hmh += `<div class="om-scale"><span class="om-bar" style="background:${rampCss()}"></span>` +
      `<span>${S.hs === 'row' ? 'голубой: реже всего для этого типа дня, розовый: чаще всего' : `общая шкала 0% → ${f1(mxAll)}%: голубой реже, розовый чаще`}</span></div>`;
    document.getElementById('om-heat').innerHTML = `<div class="om-heat">${hmh}</div>`;
    const sub = document.getElementById('om-heat-sub');
    if (sub) sub.textContent = 'строка = 100% · клик по ячейке или типу дня: сводка';
    document.querySelectorAll('#om-heat td[data-k]').forEach(td =>
      td.addEventListener('click', () => updMany({cell: S.cell === td.dataset.k ? '' : td.dataset.k, hrow: ''})));
    document.querySelectorAll('#om-heat th.om-colh').forEach(th =>
      th.addEventListener('click', () => updMany({hrow: S.hrow === th.dataset.t && !S.cell ? '' : th.dataset.t, cell: ''})));
    document.querySelectorAll('#om-heat tbody th[data-k]').forEach(th =>
      th.addEventListener('click', () => updMany({sel: th.dataset.k})));

    // ---------------------------------------------------------------- сводка по ячейке / типу дня
    const info = document.getElementById('om-heat-info');
    let infoDates = null, infoTitle = '', infoRows = [];
    if (S.cell){
      const [rk, t] = S.cell.split('#'), g = G[rk], o = order.find(x => x.k === rk);
      infoDates = (g && g.byT[t]) || [];
      infoTitle = (o ? rowName(o) : '') + ' → ' + DTN[t];
      const n = g ? g.n : 0, tAll = G._all.t[t] || 0, p = n ? infoDates.length / n * 100 : 0;
      infoRows = [
        ['Дней в ячейке', `${infoDates.length} из ${n}`],
        ['Вероятность при этом открытии', f1(p) + '%'],
        [`Частота «${DTN[t]}» во всей выборке`, f1(base(t)) + '%'],
        ['Разница с ней', sg(p - base(t)) + ' п.п.'],
        [`Из всех дней «${DTN[t]}» здесь`, tAll ? f1(infoDates.length / tAll * 100) + '%' : '—'],
      ];
    } else if (S.hrow){
      const t = S.hrow;
      infoDates = G._all.byT[t] || [];
      infoTitle = 'все дни → ' + DTN[t];
      // где этот тип дня чаще и реже всего: только строки точка × тип открытия от 20 дней
      const cand = HR.filter(o => o.k !== '_all' && (o.cls === 'om-sub' || o.zone === 'iv') && G[o.k].n >= 20)
        .map(o => ({o, p: val(G[o.k], t)})).sort((a, b) => b.p - a.p);
      const fmt = x => `${rowName(x.o)} · ${f1(x.p)}% (n ${G[x.o.k].n})`;
      infoRows = [
        ['Дней этого типа', `${infoDates.length} из ${allN}`],
        ['Частота', f1(infoDates.length / allN * 100) + '%'],
        ['Чаще всего при', cand.length ? fmt(cand[0]) : '—'],
        ['Реже всего при', cand.length ? fmt(cand[cand.length - 1]) : '—'],
      ];
    }
    if (infoDates){
      const s = summary(infoDates) || [];
      const last = infoDates.slice(-8).reverse();
      info.innerHTML = `<div class="om-it"><b>${esc(infoTitle)}</b><span><a class="om-go" href="../index.html#pick">показать на графике →</a>` +
        ` &nbsp; <button class="om-x" type="button">закрыть</button></span></div>` +
        `<div class="om-grid">${infoRows.concat(infoDates.length ? s : []).map(([k, v]) => `<div><span>${k}</span><em>${v}</em></div>`).join('')}</div>` +
        (last.length ? `<div class="om-dates">последние дни: ${last.join(' · ')}${infoDates.length > 8 ? ' …' : ''}</div>` : '');
      info.hidden = false;
      info.querySelector('.om-x').addEventListener('click', () => updMany({cell: '', hrow: ''}));
      info.querySelector('.om-go').addEventListener('click', () => pick(infoDates, infoTitle));
    } else info.hidden = true;

    const blkN = S.m === 'f' ? 'фиксированный блок 2 пт' : S.m === 'a' ? 'адаптивный блок' : `своя строка ${S.ticks} тиков (${(S.ticks * TICK).toFixed(2)} пт)`;
    const ref = S.c === '0' ? 'опора: вчерашний день' : 'опора: композит от 2 дней, иначе вчерашний день';
    document.getElementById('om-note').textContent = `${blkN} · ${ref} · ${periodLabel()} · ${allN} дней. ` +
      `Под процентом: разница с базовой частотой, п.п.` +
      (S.m === 'x' ? ' Своя строка пересчитывает VA, точку и тип открытия, Double-Distribution и композиты; при 8 тиках совпадает с фикс. 2 пт.' : '');
  }

  // ================================================================ калькулятор
  function renderCalc(G, ZL, zoneName, base){
    const host = document.getElementById('om-calc');
    if (!ZL.find(z => z[0] === S.cz)) S.cz = S.z === '3' ? (TO3[S.cz] || 'ov') : ({or: 'ar', ov: 'av'}[S.cz] || 'av');
    const opens = S.cz === 'iv' ? ['oai'] : OT.map(o => o[0]).filter(o => o !== 'oai');
    if (!opens.includes(S.co)) S.co = opens[0];
    const g = G[S.cz + '|' + S.co], zg = G[S.cz + '|*'];
    let body = '';
    if (!g || !g.n){
      body = `<div class="om-cres">В выборке нет дней с таким открытием.</div>`;
    } else {
      const parts = DT.map((t, i) => ({t, i, n: g.t[t[0]] || 0, p: (g.t[t[0]] || 0) / g.n * 100}));
      const bar = parts.filter(x => x.n).map(x =>
        `<div style="flex:${x.p} 1 0;background:${slot(x.i + 1)}" title="${x.t[1]}: ${f1(x.p)}% (${x.n} из ${g.n})">${x.p >= 7 ? f1(x.p) + '%' : ''}</div>`).join('');
      const bbar = DT.map((t, i) => ({i, p: base(t[0])})).filter(x => x.p > 0).map(x =>
        `<div style="flex:${x.p} 1 0;background:${slot(x.i + 1)}"></div>`).join('');
      const leg = parts.map(x => { const d = x.p - base(x.t[0]);
        return `<span><i style="background:${slot(x.i + 1)}"></i>${x.t[1]} <b>${f1(x.p)}%</b> <small>${x.n}</small>` +
          ` <small class="${d > 0 ? 'up' : d < 0 ? 'dn' : ''}" title="разница с частотой во всей выборке">${sg(d)}</small></span>`; }).join('');
      body = `<div class="om-cres"><b>${g.n}</b> дней с таким открытием · ${f1(g.n / zg.n * 100)}% дней зоны · ${periodLabel()}</div>` +
        `<div class="om-sbar" role="img" aria-label="вероятность типов дня">${bar}</div>` +
        `<div class="om-sbase" title="тонкая полоса: все дни выборки, для сравнения">${bbar}</div>` +
        `<div class="om-leg">${leg}</div>`;
    }
    host.innerHTML = `<div class="om-calc om-viz"><div class="om-cin controls"></div>${body}</div>`;
    host.querySelector('.om-cin').append(
      ctl('Точка открытия', seg(ZL.map(([z, n]) => [z, n]), S.cz, v => upd('cz', v))),
      ctl('Тип открытия', seg(opens.map(o => [o, OTN[o]]), S.co, v => upd('co', v))));
  }

  render();
  // данные графика приезжают отдельным файлом: когда доехали — пересчитываем
  if (!window.MPCHART) window.addEventListener('mpchart-data', () => render(), {once: true});
  new MutationObserver(render).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
})();
