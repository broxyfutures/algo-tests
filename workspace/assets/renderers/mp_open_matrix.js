// Рендерер mp_open_matrix: описательная статистика двух тестов на одной подаче.
//   outcome 'day'  (тест 1): точка + тип открытия → тип дня, rows: [date, f0 zone, f0 open, f0 day, f0 dir, f1 …, a0 …, a1 …];
//   outcome 'open' (тест 2): точка открытия → тип открытия, rows: [date, f0 zone, f0 open, f1 …, a0 …, a1 …];
//   outcome 'ib'   (тест 3): точка + тип открытия → тест границ IB, rows как в тесте 2 и в конце код дня
//                  u только верх, d только низ, b обе, n ни одной (от размера блока не зависит), затем при b:
//                  first (u хай / d лоу / s в одной минуте: в плитке не показывается) и gap (блоков между тестами).
//                  Плитка «Какая граница протестирована первой?» под калькулятором берёт дни b из его выбора.
//   outcome 'ext'  (тест 4): точка + тип открытия → время худшего и лучшего отклонения дня по тренду открытия,
//                  в конце строки hb, lb: блок RTH 0…12, где впервые достигнут хай / лоу дня. Своя подача: два кольца
//                  рядом (худшее и лучшее отклонение) и две полосы в калькуляторе, см. renderExt.
// Ожидает window.DATA = {test, outcome, fields, meta, zones, open_types, day_types, variants, rows} из results.json
// (mp-es-pipeline/scripts/11_test_open_matrix.py).
// Режим «своя строка» пересчитывает точку и тип открытия, Double-Distribution и композиты прямо здесь,
// из цен блоков window.MPCHART (assets/data/mp_chart_data.js), теми же правилами, что пайплайн.
// На странице: #hdr-meta, #om-controls, #om-calc, #om-note. Страница: большое кольцо исхода по всем дням
// выборки → калькулятор (точка, в тесте 1 ещё тип открытия) с разницей против всех дней выборки.
// «Показать на графике» кладёт дни в localStorage (mp-chart-pick) и открывает страницу инструмента с #pick.
(function(){
  const D = window.DATA, M = D.meta;
  const KEY = 'mp-open-matrix-' + D.test + '-v2';
  const OPEN = D.outcome === 'open';                     // исход: тип открытия (тест 2) или тип дня (тест 1)
  const IB = D.outcome === 'ib';                         // исход: тест границ IB (тест 3)
  const EXT = D.outcome === 'ext';                       // исход: время экстремума дня (тест 4)
  const NF = (D.fields || ['zone', 'open', 'day', 'dir']).length;   // полей на вариант в строке results.json
  // nv: 1 учитывать, 0 исключить из выборки исход EX (Normal Variation в тесте 1, Open-Auction внутри VA в тесте 2)
  // cz / co: выбранные точки и типы открытия, пустой список = любые
  // v (тест 3): вид исхода, '3' нет / одна / обе, '4' верх / низ / обе / нет, 't' по тренду открытия / против / обе / нет
  // fg / fn (тест 3): фильтр разрыва между тестами границ, 'all' все, '0' в этот же блок, 'n' через fn блоков
  const S = {m:'f', c:'0', from:'', to:'', ticks:8, cz:['av'], co:['od'], nv:1, v:'4', fg:'all', fn:1, fv:1, tm:'w'};
  try{ Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); }catch(e){}
  if (!['f', 'a', 'x'].includes(S.m)) S.m = 'f';
  ['cz', 'co'].forEach(k => { if (!Array.isArray(S[k])) S[k] = !S[k] || S[k] === '*' ? [] : [S[k]]; });
  if (OPEN) S.co = [];
  if (IB || EXT) S.nv = 1;
  if (EXT){ if (!['t', 'u', 'd'].includes(S.v)) S.v = 't'; }
  else if (!['3', '4', 't'].includes(S.v)) S.v = '4';
  if (!['w', 'b'].includes(S.tm)) S.tm = 'w';
  if (!['all', '0', 'n'].includes(S.fg)) S.fg = 'all';
  S.fn = Math.max(1, Math.min(10, Math.round(+S.fn || 1)));
  const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} };
  const f1 = v => Number.isFinite(v) ? v.toFixed(1) : '';
  const sg = v => (v > 0 ? '+' : '') + f1(v);
  const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;'}[c]));

  const ZN = Object.fromEntries(D.zones);
  const OT = D.open_types, OTN = Object.fromEntries(OT);
  const DT = D.day_types;
  const EX = OPEN ? 'oai' : 'nv';  // исключаемый тумблером исход
  const EXN = OPEN ? 'Open-Auction внутри VA' : 'Normal Variation';
  const OUTN = EXT ? 'время экстремума' : IB ? 'тест границ IB' : OPEN ? 'тип открытия' : 'тип дня';
  // тест 4: окна дня и блоки. S.v: t все дни с трендом открытия, u лонговые дни, d шортовые. S.tm: w окна, b блоки
  // по 30 минут. S.fv: учитывать ли открытия внутри VA (их тренд = сторона выхода из VA в 10:30).
  const WIN = [['w0', 'Open 09:30–10:30'], ['w1', 'Drive 10:30–12:30'], ['w2', 'Mid day 12:30–14:00'], ['w3', 'Close 14:00–16:00']];
  const WOF = [0, 0, 1, 1, 1, 1, 2, 2, 2, 3, 3, 3, 3];   // окно блока A…M
  const blkT = i => { const m = 570 + i * 30; return String(Math.floor(m / 60)).padStart(2, '0') + ':' + String(m % 60).padStart(2, '0'); };
  const BLK = WOF.map((_, i) => ['b' + i, 'ABCDEFGHIJKLM'[i] + ' ' + blkT(i) + '–' + blkT(i + 1)]);
  const EXTV = {t: 'лонговые и шортовые дни', u: 'лонговые дни', d: 'шортовые дни'};
  const TRV = () => IB && S.v === 't';                  // вид по тренду открытия в тесте 3
  const extOk = (tr, z) => !!tr && (S.v === 't' || tr === S.v) && (S.fv || z !== 'iv');
  // тренд открытия: выше VA лонг, ниже VA шорт; внутри VA = сторона выхода из VA в 10:30 (у Open-Auction внутри VA тренда нет)
  const trendOf = (z, dir) => z === 'ar' || z === 'av' ? 'u' : z === 'br' || z === 'bv' ? 'd' : z === 'iv' ? (dir || '') : '';
  const ibView = (code, tr) => {
    if (S.v === '4') return code;
    if (S.v === '3') return code === 'u' || code === 'd' ? 'o' : code;
    if (!tr) return '';                                  // тренда нет: в этом виде не участвует
    if (code !== 'u' && code !== 'd') return code;
    return code === tr ? 'w' : 'a';
  };
  const outList = () => IB ? IBV[S.v] : OPEN ? OT : DT;
  // какая граница первой: в виде «по тренду» по тренду открытия / против, в остальных хай / лоу
  const FIRSTV = {
    hl: [['u', 'Первым тест хая IB'], ['d', 'Первым тест лоу IB']],
    t: [['w', 'Первым тест границы по тренду'], ['a', 'Первым тест границы против тренда']]};
  const firstView = (fi, tr) => {
    if (S.v !== 't' || fi === 's') return fi;
    return fi === tr ? 'w' : 'a';
  };
  // исход теста 3 по дате: от размера блока и опоры не зависит, своя строка берёт его отсюда
  const IBROW = IB ? Object.fromEntries(D.rows.map(r => [r[0], r.slice(-3)])) : {};
  const EXROW = EXT ? Object.fromEntries(D.rows.map(r => [r[0], r.slice(-2)])) : {};
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
.om-sec{border-top:1px solid var(--border);margin-top:14px;padding-top:16px}
.om-lab0{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--t3);font-weight:600;margin-bottom:12px}
.om-res{display:flex;gap:20px 40px;align-items:center;flex-wrap:wrap}
.om-donut{flex:0 1 680px;max-width:100%}
.om-donut svg{display:block;width:100%;height:auto;overflow:visible}
.om-donut .om-lead{stroke:var(--t4);fill:none;stroke-width:1}
.om-donut .om-lab{font-family:var(--mono);font-size:12px;fill:var(--t2)}
.om-donut .om-lab tspan{fill:var(--t1);font-weight:600}
.om-donut .om-lab tspan.om-l2{fill:var(--t2);font-weight:400}
.om-side{flex:1 1 340px;min-width:0;font-family:var(--mono)}
.om-two{display:flex;gap:28px 48px;flex-wrap:wrap}
.om-two > div{flex:1 1 320px;min-width:0;font-family:var(--mono)}
.om-dn2{width:100%;max-width:460px;margin:0 auto 12px}
.om-donut .om-lab.om-lab-b{font-size:18px}
.om-head{font-size:11px;letter-spacing:.06em;color:var(--t3);margin-bottom:10px;line-height:1.6}
.om-head b{color:var(--t1);font-weight:600}
table.om-leg{border-collapse:collapse;width:100%;font-size:12.5px}
.om-leg th{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3);font-weight:500;text-align:right;padding:0 0 8px 12px;border-bottom:1px solid var(--border)}
.om-leg th:first-child{text-align:left;padding-left:0}
.om-leg td{padding:7px 0 7px 12px;border-bottom:1px solid var(--border);text-align:right;color:var(--t1);font-variant-numeric:tabular-nums}
.om-leg td:first-child{text-align:left;padding-left:0;color:var(--t2)}
.om-leg td.n{color:var(--t3)}
i.om-sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:9px;vertical-align:-1px}
.om-go{display:inline-block;margin-top:12px;font-size:11px;color:var(--up)}
.om-go:hover{color:var(--t1)}
/* калькулятор: [точка] + [тип открытия] = типы дня по убыванию */
.om-eq{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-family:var(--mono)}
.om-op{font-size:16px;color:var(--t3);font-weight:300}
.om-sel{position:relative;user-select:none}
.om-sel-t{font:inherit;font-size:11px;color:var(--t1);background:var(--surface-2);border:1px solid var(--border-2);padding:7px 30px 7px 12px;cursor:pointer;min-width:220px;text-align:left;border-radius:2px;position:relative;letter-spacing:.02em}
.om-sel-t small{display:block;font-size:9px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3);margin-bottom:2px}
.om-sel-t::after{content:'';position:absolute;right:11px;top:50%;border-left:4px solid transparent;border-right:4px solid transparent;border-top:5px solid var(--t3)}
.om-sel.open .om-sel-t,.om-sel-t:hover{border-color:var(--border-hi)}
.om-sel-dd{display:none;position:absolute;top:calc(100% + 2px);left:0;min-width:100%;background:var(--surface);border:1px solid var(--border-2);z-index:50;border-radius:2px;box-shadow:0 6px 22px rgba(0,0,0,.35)}
.om-sel.open .om-sel-dd{display:block}
.om-sel-o{font-size:11px;color:var(--t2);padding:7px 12px;cursor:pointer;white-space:nowrap;border-bottom:1px solid var(--border)}
.om-sel-o:last-child{border-bottom:none}
.om-sel-o:hover{color:var(--t1);background:var(--surface-2)}
.om-sel-o.on{color:var(--t1);font-weight:600}
.om-ck{display:inline-block;width:12px;margin-right:8px;color:var(--up);font-weight:700}
.om-eqres{font-size:11px;color:var(--t3);letter-spacing:.04em}
.om-eqres b{color:var(--t1);font-weight:600}
.om-sbar{display:flex;height:30px;gap:2px;margin-top:14px}
.om-sbar div{display:flex;align-items:center;justify-content:center;min-width:0;font-family:var(--mono);font-size:11px;color:#fff;white-space:nowrap;overflow:hidden}
.om-sbar div:first-child{border-radius:2px 0 0 2px}.om-sbar div:last-child{border-radius:0 2px 2px 0}
.om-rank{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.om-rank > div{flex:1 1 150px;border:1px solid var(--border);border-radius:2px;padding:8px 10px;background:var(--surface-2);font-family:var(--mono);min-width:0}
.om-rank .k{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3);display:flex;align-items:flex-start;line-height:1.4}
.om-rank .k i{margin-right:7px;flex:0 0 10px;margin-top:1px}
.om-rank .v{font-size:17px;font-weight:600;color:var(--t1);margin-top:4px}
.om-rank .s{font-size:10.5px;color:var(--t3);margin-top:1px}
.om-rank .s .up{color:var(--up)}.om-rank .s .dn{color:var(--dn)}
.om-rank > div.zero{opacity:.45}
.om-first .om-rank{margin-bottom:14px}
.om-fctl{display:flex;gap:10px 24px;flex-wrap:wrap;align-items:center;margin-top:4px}`;
  document.head.appendChild(st);
  const slot = i => `var(--d${i})`;

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
  // mp/opentype.py: classify по ценам блоков A, B (IB), закрытию B и обычному IB (медиана 20 прошлых дней)
  function openType(L, H, o, c1030, r, ibMed){
    const t = TICK;
    if (L.length < 2) return '';
    const inside = r.val <= o && o <= r.vah;
    if (inside && r.val <= c1030 && c1030 <= r.vah) return 'oai';
    const up = inside ? c1030 > r.vah : o > r.vah;    // открытие внутри VA: тренд = сторона выхода в 10:30
    const ibH = Math.max(H[0], H[1]), ibL = Math.min(L[0], L[1]);
    if (inside) return ((up ? o - ibL : ibH - o) * 5 > ibMed) ? 'otd' : 'od';
    const trendSide = up ? c1030 > o : c1030 < o;
    const vaTouch = up ? ibL <= r.vah + t : ibH >= r.val - t;
    if (vaTouch){
      const backOut = up ? c1030 > r.vah : c1030 < r.val;
      return !backOut ? 'orr' : trendSide ? 'otd' : 'oao';
    }
    const adv = up ? o - ibL : ibH - o;               // откат за цену открытия против тренда
    if (!(adv * 5 > ibMed)) return 'od';              // порог 20 % обычного IB
    return trendSide ? 'otd' : 'oao';
  }
  // направление открытия внутри VA: сторона выхода из VA в 10:30 ('' если остались внутри)
  const exitDir = (o, c1030, r) => !(r.val <= o && o <= r.vah) ? '' : c1030 > r.vah ? 'u' : c1030 < r.val ? 'd' : '';
  // обычный IB: медиана ширины IB за 20 прошлых дней (scripts/07_classify_opens.py), у первого дня своя ширина
  function ibMedians(blocks){
    const w = blocks.map(([L, H]) => L.length < 2 ? NaN : Math.max(H[0], H[1]) - Math.min(L[0], L[1]));
    return w.map((own, i) => {
      const a = w.slice(Math.max(0, i - 20), i).filter(Number.isFinite).sort((x, y) => x - y), n = a.length;
      return !n ? own : n % 2 ? a[(n - 1) / 2] : (a[n / 2 - 1] + a[n / 2]) / 2;
    });
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
    const ibMed = ibMedians(blocks);
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
      const ibH = Math.max(H[0], H[1]), ibL = Math.min(L[0], L[1]);
      const up = H.slice(2).some(v => v >= ibH), dn = L.slice(2).some(v => v <= ibL);
      out.push({dt, ib: up && dn ? 'b' : up ? 'u' : dn ? 'd' : 'n',
        z0: refDay ? zoneOf(o, refDay) : '', t0: refDay ? openType(L, H, o, c1030, refDay, ibMed[i]) : '',
        d0: refDay && L.length > 1 ? exitDir(o, c1030, refDay) : '',
        z1: refComp ? zoneOf(o, refComp) : '', t1: refComp ? openType(L, H, o, c1030, refComp, ibMed[i]) : '',
        d1: refComp && L.length > 1 ? exitDir(o, c1030, refComp) : ''});
    });
    engineCache.set(ticks, out);
    return out;
  }
  window.OMEngine = engine;   // для проверки: при 8 тиках обязан совпасть с фиксированным режимом пайплайна


  // ================================================================ большое кольцо
  function donut(parts, total, compact){
    const R = 128, r = 80, cx = 400, cy = 175;
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
      if (f >= 0.02){
        // длинное название переносим на вторую строку по пробелу ближе к середине
        let lines = [p.label];
        if (p.label.length > 22){
          const sp = [...p.label].map((ch, i) => ch === ' ' ? i : -1).filter(i => i > 0);
          const cut = sp.sort((a, b) => Math.abs(a - p.label.length / 2) - Math.abs(b - p.label.length / 2))[0];
          if (cut) lines = [p.label.slice(0, cut), p.label.slice(cut + 1)];
        }
        labs.push({f, mid, lines, h: compact ? 25 : lines.length > 1 ? 32 : 17});
      }
      a0 = a1;
    });
    // подписи разводим по вертикали внутри своей половины, чтобы не наезжали друг на друга
    let leads = '';
    ['r', 'l'].forEach(side => {
      const Lb = labs.filter(l => (Math.cos(l.mid) >= 0 ? 'r' : 'l') === side)
        .map(l => ({...l, y: Pt(R + 22, l.mid)[1]})).sort((a, b) => a.y - b.y);
      const gap = (a, b) => (a.h + b.h) / 2;
      for (let i = 1; i < Lb.length; i++) if (Lb[i].y - Lb[i - 1].y < gap(Lb[i], Lb[i - 1])) Lb[i].y = Lb[i - 1].y + gap(Lb[i], Lb[i - 1]);
      for (let i = Lb.length - 2; i >= 0; i--) if (Lb[i + 1].y - Lb[i].y < gap(Lb[i], Lb[i + 1])) Lb[i].y = Lb[i + 1].y - gap(Lb[i], Lb[i + 1]);
      Lb.forEach(l => {
        const x1 = cx + (side === 'r' ? 1 : -1) * (R + 26), x2 = x1 + (side === 'r' ? 14 : -14);
        const [px0, py0] = Pt(R + 3, l.mid);
        leads += `<polyline class="om-lead" points="${px0.toFixed(1)},${py0.toFixed(1)} ${x1.toFixed(1)},${l.y.toFixed(1)} ${x2.toFixed(1)},${l.y.toFixed(1)}"/>` +
          (() => { const tx = (x2 + (side === 'r' ? 5 : -5)).toFixed(1), two = l.lines.length > 1, pc = ` <tspan>${f1(l.f * 100)}%</tspan>`;
            return `<text class="om-lab${compact ? ' om-lab-b' : ''}" x="${tx}" y="${(l.y + (two ? -3 : compact ? 6 : 4)).toFixed(1)}" text-anchor="${side === 'r' ? 'start' : 'end'}">` +
              (two ? `${l.lines[0]}<tspan class="om-l2" x="${tx}" dy="14">${l.lines[1]}</tspan>${pc}` : l.lines[0] + pc) + `</text>`; })();
      });
    });
    return `<svg viewBox="${compact ? '95 -30 610 410' : '0 0 800 350'}" role="img" aria-label="распределение: ${OUTN}">${arcs}${leads}` +
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
        const o = S.c === '0' ? e.t0 : e.t1;
        const z5 = S.c === '0' ? e.z0 : e.z1, tr = trendOf(z5, S.c === '0' ? e.d0 : e.d1);
        const [ib, fi, gap] = IBROW[d] || [e.ib, '', -1];
        if (EXT){ const x = EXROW[d]; if (x) out.push({date: d, i, z5, o, tr, t: extOk(tr, z5) ? 'x' : '', bb: tr === 'u' ? x[0] : x[1], wb: tr === 'u' ? x[1] : x[0]}); return; }
        out.push({date: d, i, z5, o, tr, t: IB ? ibView(ib, tr) : OPEN ? o : e.dt, ib, fi, gap});
      });
      return IB || EXT ? out.filter(r => r.t) : out;
    }
    const off = 1 + NF * D.variants.indexOf(S.m + S.c);
    const out = D.rows.filter(r => inRange(r[0])).map(r => {
      const [ib, fi, gap] = IB ? r.slice(-3) : ['', '', -1];
      const tr = IB || EXT ? trendOf(r[off], r[off + 2]) : '';
      if (EXT){ const [hb, lb] = r.slice(-2); return {date: r[0], z5: r[off], o: r[off + 1], tr, t: extOk(tr, r[off]) ? 'x' : '', bb: tr === 'u' ? hb : lb, wb: tr === 'u' ? lb : hb}; }
      return {date: r[0], z5: r[off], o: r[off + 1], tr, t: IB ? ibView(ib, tr) : OPEN ? r[off + 1] : r[off + 2], ib, fi, gap};
    });
    return IB || EXT ? out.filter(r => r.t) : out;
  }

  // «показать на графике»: дни уходят на страницу инструмента через localStorage
  function pick(dates, label){
    if (!window.MPCHART) return;
    const idx = dates.map(d => idxOf()[d]).filter(i => i !== undefined);
    // фильтры графика ставятся теми же, что в калькуляторе: точки, типы открытия, типы дня (без NV, если исключён);
    // в тесте 2 исключённый Open-Auction внутри VA уходит из фильтра типов открытия.
    // Список дней (idx) нужен только там, где фильтры графика его не повторят: своя строка или свой период.
    // В тесте 3 исхода нет среди фильтров графика, поэтому список дней передаётся всегда.
    const exact = IB || EXT || S.m === 'x' || !!S.from || !!S.to;
    try{ localStorage.setItem('mp-chart-pick', JSON.stringify({idx: exact ? idx : null, label, m: S.m === 'x' ? 'f' : S.m, c: S.c,
      ticks: S.m === 'x' ? S.ticks : 0, fz: S.cz,
      fo: OPEN ? (S.nv ? [] : OT.map(t => t[0]).filter(t => t !== EX)) : S.co,
      ft: OPEN || S.nv ? [] : DT.map(t => t[0]).filter(t => t !== EX)})); }catch(e){}
  }

  // ================================================================ выпадающий мультивыбор в стиле COT Report
  // пустой список = «любые»; список остаётся открытым, пока щёлкаешь по вариантам
  let openDD = '';
  function multiDropdown(key, label, anyName, opts, cur, cb){
    const w = document.createElement('div'); w.className = 'om-sel' + (openDD === key ? ' open' : '');
    const t = document.createElement('button'); t.type = 'button'; t.className = 'om-sel-t';
    const names = opts.filter(o => cur.includes(o[0])).map(o => o[1]);
    t.innerHTML = `<small>${label}</small>${esc(!names.length ? anyName : names.length === 1 ? names[0] : names.length + ' выбрано')}`;
    if (names.length > 1) t.title = names.join(', ');
    const dd = document.createElement('div'); dd.className = 'om-sel-dd';
    const item = (v, n, on) => { const o = document.createElement('div'); o.className = 'om-sel-o' + (on ? ' on' : '');
      o.innerHTML = `<span class="om-ck">${on ? '✓' : ''}</span>${esc(n)}`;
      o.addEventListener('click', e => { e.stopPropagation(); openDD = key;
        cb(v === '*' ? [] : cur.includes(v) ? cur.filter(x => x !== v) : cur.concat(v)); });
      dd.appendChild(o); };
    item('*', anyName, !cur.length);
    opts.forEach(([v, n]) => item(v, n, cur.includes(v)));
    t.addEventListener('click', e => { e.stopPropagation(); const was = openDD === key; openDD = was ? '' : key;
      document.querySelectorAll('.om-sel.open').forEach(x => x.classList.remove('open')); if (!was) w.classList.add('open'); });
    w.append(t, dd);
    return w;
  }
  document.addEventListener('click', () => { openDD = ''; document.querySelectorAll('.om-sel.open').forEach(x => x.classList.remove('open')); });

  // ================================================================ тест 3: какая граница протестирована первой
  // Только дни с тестом обеих границ IB. Полоса и плитки по выбору калькулятора (пустой выбор = все дни)
  // с разницей в п.п. к доле среди всех дней выборки. Тумблер «Открытие внутри VA»: учитывать / исключить такие дни. Фильтр разрыва: все / в этот же блок / через N блоков (ровно N).
  function gapInput(){
    const w = document.createElement('span'); w.className = 'om-inl';
    const a = document.createElement('span'); a.textContent = 'через';
    const inp = document.createElement('input');
    inp.type = 'number'; inp.min = 1; inp.max = 10; inp.step = 1; inp.className = 'om-num'; inp.value = S.fn;
    inp.title = 'через сколько 30-минутных блоков после первого теста протестирована вторая граница';
    const apply = () => { const v = Math.max(1, Math.min(10, Math.round(+inp.value || 0))); if (v !== S.fn || S.fg !== 'n') updMany({fn: v, fg: 'n'}); };
    inp.addEventListener('change', apply);
    inp.addEventListener('keydown', e => { if (e.key === 'Enter') apply(); });
    const b = document.createElement('span'); b.textContent = 'блок.';
    w.append(a, inp, b);
    return w;
  }
  function renderFirst(host, R, sel, title){
    const gapOk = r => S.fg === 'all' || (S.fg === '0' ? r.gap === 0 : r.gap === S.fn);
    const pick2 = rows => rows.filter(r => r.ib === 'b' && r.fi !== 's' && (S.fv || r.z5 !== 'iv') && gapOk(r)).map(r => ({...r, f: firstView(r.fi, r.tr)}));
    const all = pick2(R), mine = pick2(sel);
    const kinds = FIRSTV[S.v === 't' ? 't' : 'hl'].map(([code, name], i) => ({code, name, color: slot(i + 1)}));
    const cnt = rows => { const c = {}; rows.forEach(r => { c[r.f] = (c[r.f] || 0) + 1; }); return c; };
    const ca = cnt(all), cm = cnt(mine), pa = k => all.length ? (ca[k] || 0) / all.length * 100 : 0;
    const strip = (rows, c) => `<div class="om-sbar">` + kinds.filter(k => c[k.code]).map(k => { const v = c[k.code] / rows.length * 100;
      return `<div style="flex:${v} 1 0;background:${k.color}" title="${k.name}: ${f1(v)}% (${c[k.code]} из ${rows.length})">${v >= 8 ? f1(v) + '%' : ''}</div>`; }).join('') + `</div>`;
    const gapN = S.fg === 'all' ? '' : S.fg === '0' ? ' · в этот же блок' : ` · через ${S.fn} блок.`;
    host.innerHTML = `<div class="om-lab0" style="color:var(--t1)">Какая граница протестирована первой?</div>` +
      `<div class="om-head">Только дни, когда протестированы обе границы IB.</div><div class="om-fctl"></div>`;
    host.querySelector('.om-fctl').append(
      ctl('Открытие внутри VA', seg([[1, 'Учитывать'], [0, 'Исключить']], S.fv, v => upd('fv', v))),
      ctl('Вторая граница', seg([['all', 'Все'], ['0', 'В этот же блок'], ['n', 'Через N блоков']], S.fg, v => upd('fg', v)), gapInput()));
    const out = document.createElement('div'); host.appendChild(out);
    if (!all.length){ out.innerHTML = '<p class="om-busy">В выборке нет таких дней.</p>'; return; }
    let html = `<div class="om-head" style="margin-top:12px"><b>${esc(title)}</b> · ${mine.length ? mine.length + ' дней' : 'нет таких дней'}${gapN}</div>`;
    if (mine.length){
      const ranked = kinds.map(k => ({...k, n: cm[k.code] || 0})).map(k => ({...k, p: k.n / mine.length * 100, d: k.n / mine.length * 100 - pa(k.code)}))
        .sort((a, b) => b.n - a.n);
      html += strip(mine, cm) + `<div class="om-rank">` + ranked.map(k => `<div class="${k.n ? '' : 'zero'}"><span class="k"><i class="om-sw" style="background:${k.color}"></i>${k.name}</span>` +
        `<div class="v">${f1(k.p)}%</div><div class="s">${k.n} дн · <span class="${k.d > 0.05 ? 'up' : k.d < -0.05 ? 'dn' : ''}" title="разница с долей среди всех дней выборки с тестом обеих границ">${sg(k.d)} п.п.</span></div></div>`).join('') + `</div>`;
    }
    out.innerHTML = html;
  }

  // ================================================================ тест 4: время худшего и лучшего отклонения
  // Худшее = экстремум дня против тренда открытия, лучшее = по тренду. Наверху два кольца рядом по всем дням
  // раздела, в калькуляторе две полосы друг под другом по его выбору, «п.п.» = разница с долей во всех днях раздела.
  function renderExt(calc, R){
    const types = (S.tm === 'w' ? WIN : BLK).map((t, i) => ({code: t[0], name: t[1], color: slot(S.tm === 'b' ? WOF[i] + 1 : i + 1)}));
    const code = b => S.tm === 'w' ? 'w' + WOF[b] : 'b' + b;
    const KINDS = [['wb', 'Худшее отклонение', 'Когда худшая цена дня'], ['bb', 'Лучшее отклонение', 'Когда лучшая цена дня']];
    const count = (rows, k) => { const c = {}; rows.forEach(r => { const x = code(r[k]); c[x] = (c[x] || 0) + 1; }); return c; };
    const scope = EXTV[S.v] + (S.fv ? '' : ' · без открытий внутри VA');
    calc.innerHTML = '<div class="om-viz"><div class="om-sec om-all"></div><div class="om-sec om-calc"></div></div>';
    const all = calc.querySelector('.om-all');
    if (!R.length) all.innerHTML = '<p class="om-busy">В выборке нет дней.</p>';
    else all.innerHTML = `<div class="om-head"><b>Все дни выборки</b> · ${R.length} дней · ${periodLabel()} · ${scope}</div><div class="om-two">` +
      KINDS.map(([k, nm, th]) => { const c = count(R, k), by = types.slice().sort((a, b) => (c[b.code] || 0) - (c[a.code] || 0));
        return `<div><div class="om-lab0" style="color:var(--t1)">${nm}</div>` +
          `<div class="om-donut om-dn2">${donut(types.map(t => ({label: S.tm === 'w' ? t.name.split(' ').slice(0, -1).join(' ') : t.name[0], value: c[t.code] || 0, color: t.color})), R.length, true)}</div>` +
          `<table class="om-leg"><thead><tr><th>${th}</th><th>Доля</th><th>Дней</th></tr></thead><tbody>` +
          by.map(t => `<tr><td><i class="om-sw" style="background:${t.color}"></i>${t.name}</td><td>${f1((c[t.code] || 0) / R.length * 100)}%</td><td class="n">${c[t.code] || 0}</td></tr>`).join('') +
          `</tbody></table></div>`; }).join('') + `</div>`;

    const box = calc.querySelector('.om-calc');
    // точки открытия раздела: у лонговых дней выше VA и внутри VA, у шортовых ниже VA и внутри VA
    const zones = D.zones.filter(([z]) => (S.fv || z !== 'iv') && (S.v === 't' || z === 'iv' || (S.v === 'u') === (z === 'ar' || z === 'av')));
    S.cz = S.cz.filter(z => zones.some(x => x[0] === z));
    const opens = OT.map(o => o[0]).filter(o => o !== 'oai');
    S.co = S.co.filter(o => opens.includes(o));
    const sel = R.filter(r => (!S.cz.length || S.cz.includes(r.z5)) && (!S.co.length || S.co.includes(r.o)));
    const title = [S.cz.length ? S.cz.map(z => ZN[z]).join(', ') : 'любая точка', S.co.length ? S.co.map(o => OTN[o]).join(', ') : 'любой тип открытия'].join(' · ');
    box.innerHTML = '<div class="om-lab0">Калькулятор</div><div class="om-eq"></div><div class="om-out"></div>';
    const eqRes = document.createElement('span'); eqRes.className = 'om-eqres';
    eqRes.innerHTML = sel.length ? `<b>время отклонений</b> · ${sel.length} дней${R.length ? ' · ' + f1(sel.length / R.length * 100) + '% выборки' : ''}` : `<b>время отклонений</b> · нет таких дней`;
    const op = t => { const e = document.createElement('span'); e.className = 'om-op'; e.textContent = t; return e; };
    box.querySelector('.om-eq').append(
      multiDropdown('z', 'Точка открытия', 'любая', zones.map(([z, n]) => [z, n]), S.cz, v => upd('cz', v)), op('+'),
      multiDropdown('o', 'Тип открытия', 'любой', opens.map(o => [o, OTN[o]]), S.co, v => upd('co', v)), op('='), eqRes);
    if (sel.length){
      box.querySelector('.om-out').innerHTML = KINDS.map(([k, nm]) => { const cs = count(sel, k), cb = count(R, k);
        const ranked = types.map(t => ({...t, n: cs[t.code] || 0})).map(t => ({...t, p: t.n / sel.length * 100, d: t.n / sel.length * 100 - (cb[t.code] || 0) / R.length * 100}))
          .sort((a, b) => b.n - a.n || (cb[b.code] || 0) - (cb[a.code] || 0));
        const bar = ranked.filter(t => t.n).map(t =>
          `<div style="flex:${t.p} 1 0;background:${t.color}" title="${t.name}: ${f1(t.p)}% (${t.n} из ${sel.length})">${t.p >= 8 ? f1(t.p) + '%' : ''}</div>`).join('');
        const chips = ranked.map(t => `<div class="${t.n ? '' : 'zero'}"><span class="k"><i class="om-sw" style="background:${t.color}"></i>${t.name}</span>` +
          `<div class="v">${f1(t.p)}%</div><div class="s">${t.n} дн · <span class="${t.d > 0.05 ? 'up' : t.d < -0.05 ? 'dn' : ''}" title="разница с долей среди всех дней выборки">${sg(t.d)} п.п.</span></div></div>`).join('');
        return `<div class="om-lab0" style="color:var(--t1);margin:18px 0 0">${nm}</div><div class="om-sbar" style="margin-top:8px">${bar}</div><div class="om-rank">${chips}</div>`; }).join('') +
        `<a class="om-go" href="../index.html#pick">показать эти дни на графике →</a>`;
      box.querySelector('.om-go').addEventListener('click', () => pick(sel.map(r => r.date), title + ' · ' + scope));
    }
    const blkN = S.m === 'f' ? 'фикс. 2 пт' : S.m === 'a' ? 'адаптивный блок' : `своя строка ${S.ticks} тиков`;
    document.getElementById('om-note').textContent = `${blkN} · опора: ${S.c === '0' ? 'вчерашний день' : 'композит'} · ${periodLabel()} · ${scope}. ` +
      `Худшее отклонение: экстремум дня против тренда открытия, лучшее: по тренду. «п.п.»: разница с долей этого времени среди всех дней выборки.`;
  }

  // ================================================================ страница
  function render(){
    const host = document.getElementById('om-controls'); host.innerHTML = '';
    host.append(
      ctl('Блок', seg([['f', 'Фикс. 2 пт'], ['a', 'Адаптивный'], ['x', 'Своя строка']], S.m, v => upd('m', v)), ...(S.m === 'x' ? [tickInput()] : [])),
      ctl('Опора', seg([['0', 'Вчерашний день'], ['1', 'Композит']], S.c, v => upd('c', v))),
      ctl('Период', seg(PRESETS.map(p => [p[0], p[1]]), presetNow(), v => { const p = PRESETS.find(x => x[0] === v); updMany({from: p[2], to: p[3]}); }), dateRange()),
      ...(EXT ? [ctl('Отклонения', seg([['t', 'По тренду'], ['u', 'Лонговых дней'], ['d', 'Шортовых дней']], S.v, v => upd('v', v))),
                 ctl('Открытие внутри VA', seg([[1, 'Учитывать'], [0, 'Исключить']], S.fv, v => upd('fv', v))),
                 ctl('Время', seg([['w', 'Окна'], ['b', 'Блоки 30 мин']], S.tm, v => upd('tm', v)))] : []),
      ...(EXT ? [] : [IB ? ctl('Исход', seg([['3', 'Нет / одна / обе'], ['4', 'Хай / лоу / обе / нет'], ['t', 'По тренду открытия']], S.v, v => upd('v', v)))
         : ctl(EXN, seg([[1, 'Учитывать'], [0, 'Исключить']], S.nv, v => upd('nv', v)))]),
    );
    const calc = document.getElementById('om-calc');
    let R = rowsNow();
    if (!R){ calc.innerHTML = '<p class="om-busy">Загружаю цены блоков для пересчёта…</p>'; return; }
    if (EXT){ renderExt(calc, R); return; }
    if (!S.nv) R = R.filter(r => r.t !== EX);
    const types = outList().map((t, i) => ({code: t[0], name: t[1], color: slot(i + 1)})).filter(t => S.nv || t.code !== EX);
    const count = rows => { const c = {}; rows.forEach(r => { c[r.t] = (c[r.t] || 0) + 1; }); return c; };
    const cb = count(R), base = code => R.length ? (cb[code] || 0) / R.length * 100 : 0;
    const noNV = (S.nv ? '' : ' · без ' + EXN) + (TRV() ? ' · без Open-Auction внутри VA' : '');
    calc.innerHTML = '<div class="om-viz"><div class="om-sec om-all"></div><div class="om-sec om-calc"></div>' +
      (IB ? '<div class="om-sec om-first"></div>' : '') + '</div>';

    // ---------------------------------------------------------------- общая диаграмма: все дни выборки
    const all = calc.querySelector('.om-all');
    if (!R.length) all.innerHTML = '<p class="om-busy">В выборке нет дней.</p>';
    else {
      const byShare = types.slice().sort((a, b) => (cb[b.code] || 0) - (cb[a.code] || 0));
      all.innerHTML = `<div class="om-res"><div class="om-donut">${donut(types.map(t => ({label: t.name, value: cb[t.code] || 0, color: t.color})), R.length)}</div>` +
        `<div class="om-side"><div class="om-head"><b>Все дни выборки</b><br>${R.length} дней · ${periodLabel()}${noNV}</div>` +
        `<table class="om-leg"><thead><tr><th>${IB ? 'Тест границ IB' : OPEN ? 'Тип открытия' : 'Тип дня'}</th><th>Доля</th><th>Дней</th></tr></thead><tbody>` +
        byShare.map(t => `<tr><td><i class="om-sw" style="background:${t.color}"></i>${t.name}</td><td>${f1(base(t.code))}%</td><td class="n">${cb[t.code] || 0}</td></tr>`).join('') +
        `</tbody></table></div></div>`;
    }

    // ---------------------------------------------------------------- калькулятор: точка (+ тип открытия) = исход
    const box = calc.querySelector('.om-calc');
    // в списке всегда все типы открытия; несочетаемый выбор (точка вне VA + Open-Auction внутри VA) даёт 0 дней
    const zones = D.zones;
    S.cz = S.cz.filter(z => zones.some(x => x[0] === z));
    const opens = OT.map(o => o[0]).filter(o => !(TRV() && o === 'oai'));
    S.co = S.co.filter(o => opens.includes(o));
    const sel = R.filter(r => (!S.cz.length || S.cz.includes(r.z5)) && (OPEN || !S.co.length || S.co.includes(r.o)));
    const cs = count(sel);
    const title = [S.cz.length ? S.cz.map(z => ZN[z]).join(', ') : 'любая точка',
                   ...(OPEN ? [] : [S.co.length ? S.co.map(o => OTN[o]).join(', ') : 'любой тип открытия'])].join(' · ');
    box.innerHTML = '<div class="om-lab0">Калькулятор</div><div class="om-eq"></div><div class="om-out"></div>';
    const eqRes = document.createElement('span'); eqRes.className = 'om-eqres';
    eqRes.innerHTML = sel.length ? `<b>${OUTN}</b> · ${sel.length} дней${R.length ? ' · ' + f1(sel.length / R.length * 100) + '% выборки' : ''}` : `<b>${OUTN}</b> · нет таких дней`;
    const op = t => { const e = document.createElement('span'); e.className = 'om-op'; e.textContent = t; return e; };
    box.querySelector('.om-eq').append(
      multiDropdown('z', 'Точка открытия', 'любая', zones.map(([z, n]) => [z, n]), S.cz, v => upd('cz', v)),
      ...(OPEN ? [] : [op('+'), multiDropdown('o', 'Тип открытия', 'любой', opens.map(o => [o, OTN[o]]), S.co, v => upd('co', v))]),
      op('='), eqRes);
    if (sel.length){
      const ranked = types.map(t => ({...t, n: cs[t.code] || 0})).map(t => ({...t, p: t.n / sel.length * 100, d: t.n / sel.length * 100 - base(t.code)}))
        .sort((a, b) => b.n - a.n || base(b.code) - base(a.code));
      const bar = ranked.filter(t => t.n).map(t =>
        `<div style="flex:${t.p} 1 0;background:${t.color}" title="${t.name}: ${f1(t.p)}% (${t.n} из ${sel.length})">${t.p >= 8 ? f1(t.p) + '%' : ''}</div>`).join('');
      const chips = ranked.map(t => `<div class="${t.n ? '' : 'zero'}"><span class="k"><i class="om-sw" style="background:${t.color}"></i>${t.name}</span>` +
        `<div class="v">${f1(t.p)}%</div><div class="s">${t.n} дн · <span class="${t.d > 0.05 ? 'up' : t.d < -0.05 ? 'dn' : ''}" title="разница с долей среди всех дней выборки">${sg(t.d)} п.п.</span></div></div>`).join('');
      box.querySelector('.om-out').innerHTML = `<div class="om-sbar">${bar}</div><div class="om-rank">${chips}</div>` +
        `<a class="om-go" href="../index.html#pick">показать эти дни на графике →</a>`;
      box.querySelector('.om-go').addEventListener('click', () => pick(sel.map(r => r.date), title + (S.nv ? '' : ' · без ' + EXN)));
    }

    if (IB) renderFirst(calc.querySelector('.om-first'), R, sel, title);

    const blkN = S.m === 'f' ? 'фикс. 2 пт' : S.m === 'a' ? 'адаптивный блок' : `своя строка ${S.ticks} тиков`;
    document.getElementById('om-note').textContent = `${blkN} · опора: ${S.c === '0' ? 'вчерашний день' : 'композит'} · ${periodLabel()}${noNV}. ` +
      `«п.п.» в калькуляторе: разница с долей ${IB ? 'этого исхода' : 'этого типа'} среди всех дней выборки.` +
      (S.m === 'x' ? ' Своя строка пересчитывает VA, открытия, DD и композиты, при 8 тиках совпадает с фикс. 2 пт.' : '');
  }

  render();
  // данные графика приезжают отдельным файлом: когда доехали — пересчитываем
  if (!window.MPCHART) window.addEventListener('mpchart-data', () => render(), {once: true});
})();
