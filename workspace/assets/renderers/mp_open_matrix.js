// Рендерер mp_open_matrix: точка открытия × тип открытия → тип дня, описательная статистика.
// Ожидает window.DATA = {test, meta, zones, open_types, day_types, variants, rows} из results.json
// (mp-es-pipeline/scripts/11_test_open_matrix.py). rows: [date, f0 zone, f0 open, f0 day, f0 dir, f1 …, a0 …, a1 …].
// На странице: #hdr-meta, #om-controls, #om-types, #om-dirs, #om-note.
(function(){
  const D = window.DATA, M = D.meta;
  const KEY = 'mp-open-matrix-' + D.test;
  const S = {m:'f', c:'0', z:'5', p:'all', v:'pct', sel:'_all', hs:'row', cell:''};
  try{ Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); }catch(e){}
  const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} };
  const f1 = v => Number.isFinite(v) ? v.toFixed(1) : '';
  const sg = v => (v > 0 ? '+' : '') + f1(v);

  const Z5 = D.zones;
  const Z3 = [['or', 'снаружи диапазона'], ['ov', 'снаружи VA, в диапазоне'], ['iv', 'внутри VA']];
  const TO3 = {ar:'or', br:'or', av:'ov', bv:'ov', iv:'iv'};
  const BIAS = {ar:'u', av:'u', bv:'d', br:'d', iv:''};
  const OT = D.open_types, OTN = Object.fromEntries(OT);
  const DT = D.day_types, DIRT = DT.filter(t => t[2]);

  const st = document.createElement('style');
  st.textContent = `.om-viz{--z1:#3987e5;--z2:#d95926;--z3:#199e70;--z4:#c98500;--z5:#d55181;--z6:#008300;--z7:#9085e9;--z0:#5f5e5a}
:root[data-theme="light"] .om-viz{--z1:#2a78d6;--z2:#eb6834;--z3:#1baf7a;--z4:#eda100;--z5:#e87ba4;--z6:#008300;--z7:#4a3aa7;--z0:#b4b2a9}
.om-wrap{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
.om-wrap .twrap{flex:1 1 600px;min-width:0}
.om-pie{flex:0 0 340px;font-family:var(--sans);font-size:12px;color:var(--t2)}
.om-pie svg{overflow:visible}
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
.om-heat{overflow-x:auto}
table.om-hm{border-collapse:separate;border-spacing:3px;font-size:12.5px;min-width:640px}
.om-hm th{font-size:9.5px;letter-spacing:.1em;text-transform:uppercase;color:var(--t3);font-weight:500;padding:6px 8px;text-align:center;vertical-align:bottom;line-height:1.4}
.om-hm th.om-rowh{text-align:left;white-space:nowrap;text-transform:none;font-size:12px;letter-spacing:.02em;color:var(--t2);padding-right:12px}
.om-hm th .om-n{display:block;color:var(--t4);letter-spacing:.06em}
.om-hm td{padding:9px 10px;text-align:center;border-radius:3px;min-width:74px;font-variant-numeric:tabular-nums}
.om-hm td.om-base{background:var(--surface-2)!important;color:var(--t2)!important}
.om-hm .om-colsel{outline:1px solid var(--border-hi);outline-offset:-1px}
.om-hm tbody td[data-k]{cursor:pointer}
.om-hm td.om-cellsel{outline:2px solid var(--t1);outline-offset:-2px}
.om-scale{display:flex;align-items:center;gap:10px;margin-top:12px;font-size:11px;color:var(--t3);font-family:var(--sans)}
.om-scale .om-bar{height:10px;width:190px;border-radius:2px}`;
  document.head.appendChild(st);
  const slot = i => `var(--z${i})`;
  // короткие имена для подписей у секторов: длинные не помещаются рядом с кольцом
  const SHORT = {'Double-Distribution Trend':'DD-Trend', 'Normal Variation':'Normal Var.',
                 'Neutral-Center':'Neutral-C', 'Neutral-Extreme':'Neutral-E',
                 'Open-Auction внутри VA':'O-A в VA', 'Open-Auction вне VA':'O-A вне VA',
                 'Open-Drive':'O-Drive', 'Open-Test-Drive':'O-T-Drive', 'Open-Rejection-Reverse':'O-R-R',
                 'по тренду точки открытия':'по тренду', 'против тренда':'против',
                 'без направления':'без напр.'};
  function pie(title, parts, extra){
    const tot = parts.reduce((a, p) => a + p.value, 0);
    const R = 66, r = 40, cx = 165, cy = 108;
    const P = (rad, ang) => [cx + rad * Math.cos(ang), cy + rad * Math.sin(ang)];
    const xy = (rad, ang) => P(rad, ang).map(v => v.toFixed(2)).join(' ');
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
      const L = labs.filter(l => (Math.cos(l.mid) >= 0 ? 'r' : 'l') === side)
        .map(l => ({...l, y0: P(R, l.mid)[1], y: P(R + 16, l.mid)[1]}))
        .sort((a, b) => a.y - b.y);
      for (let i = 1; i < L.length; i++) if (L[i].y - L[i - 1].y < 13) L[i].y = L[i - 1].y + 13;
      for (let i = L.length - 2; i >= 0; i--) if (L[i + 1].y - L[i].y < 13) L[i].y = L[i + 1].y - 13;
      L.forEach(l => {
        const x1 = cx + (side === 'r' ? 1 : -1) * (R + 18), x2 = x1 + (side === 'r' ? 12 : -12);
        const [px0, py0] = P(R + 2, l.mid);
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

  // подробности по выбранной строке: считаются из данных графика (assets/data/mp_chart_data.js)
  const med = a => { if (!a.length) return NaN; const b = a.slice().sort((x, y) => x - y), i = b.length >> 1;
    return b.length % 2 ? b[i] : (b[i - 1] + b[i]) / 2; };
  function stats(dates){
    const M = window.MPCHART;
    if (!M || !dates.length) return '';
    if (!pie._idx) pie._idx = Object.fromEntries(M.dates.map((d, i) => [d, i]));
    const days = dates.map(d => pie._idx[d]).filter(i => i !== undefined).map(i => M.modes[S.m].days[i]);
    if (!days.length) return '';
    const rng = days.map(d => d[9] - d[10]), ib = days.map(d => d[6] - d[7]);
    const share = days.map(d => (d[6] - d[7]) / (d[9] - d[10]) * 100);
    const cl = days.map(d => (d[11] - d[10]) / (d[9] - d[10]) * 100);
    const up = days.filter(d => d[9] > d[6]).length, dn = days.filter(d => d[10] < d[7]).length;
    const roll = days.filter(d => d[23] & 1).length, gap = days.filter(d => d[23] & 8).length;
    const row = (k, v) => `<tr><td>${k}</td><td>${v}</td></tr>`;
    return '<div class="om-stat"><table>' +
      row('Медианный диапазон', f1(med(rng)) + ' пт') +
      row('Медианный IB', f1(med(ib)) + ' пт · ' + f1(med(share)) + '% диапазона') +
      row('Вышли за IB вверх', f1(up / days.length * 100) + '%') +
      row('Вышли за IB вниз', f1(dn / days.length * 100) + '%') +
      row('Закрытие в диапазоне', f1(med(cl)) + '% (медиана)') +
      row('Дней ролла · после дыр', roll + ' · ' + gap) +
      '</table></div>';
  }

  const hm = document.getElementById('hdr-meta');
  if (hm) hm.innerHTML = `<div><span class="dot"></span><b>${M.days}</b> дней · ${M.from} → ${M.to}</div><div>${M.note}</div><div>Результаты собраны ${M.built}</div>`;

  function seg(opts, cur, cb){
    const el = document.createElement('div'); el.className = 'seg';
    opts.forEach(([v, label]) => { const b = document.createElement('button'); b.textContent = label; b.setAttribute('aria-pressed', v === cur); b.addEventListener('click', () => cb(v)); el.appendChild(b); });
    return el;
  }
  function ctl(label, node){ const w = document.createElement('div'); w.className = 'ctl'; const l = document.createElement('span'); l.className = 'ctl-label'; l.textContent = label; w.append(l, node); return w; }
  const upd = (k, v) => { S[k] = v; save(); render(); };

  function rowsNow(){
    const off = 1 + 4 * D.variants.indexOf(S.m + S.c);
    return D.rows.filter(r => { const y = +r[0].slice(0, 4); return S.p === 'all' || (S.p === 'a' ? y <= 2018 : y >= 2019); })
      .map(r => ({date: r[0], z5: r[off], o: r[off + 1], t: r[off + 2], d: r[off + 3]}));
  }

  function render(){
    const host = document.getElementById('om-controls'); host.innerHTML = '';
    host.append(
      ctl('Блок', seg([['f', 'Фикс. 2 пт'], ['a', 'Адаптивный']], S.m, v => upd('m', v))),
      ctl('Композит', seg([['0', 'Выкл · опора вчера'], ['1', 'Вкл · опора композит']], S.c, v => upd('c', v))),
      ctl('Зоны', seg([['5', '5 зон'], ['3', '3 группы']], S.z, v => upd('z', v))),
      ctl('Период', seg([['all', '2010–2026'], ['a', '2010–2018'], ['b', '2019–2026']], S.p, v => upd('p', v))),
      ctl('Показать', seg([['pct', '% дней'], ['n', 'дни']], S.v, v => upd('v', v))),
      ctl('Шкала карты', seg([['row', 'по строке'], ['all', 'общая']], S.hs, v => upd('hs', v))),
    );
    const R = rowsNow();
    const zk = r => S.z === '3' ? TO3[r.z5] : r.z5;
    const ZL = S.z === '3' ? Z3 : Z5;

    // группы строк: зона целиком + зона × тип открытия
    const G = {};
    const add = (k, r) => { const g = G[k] = G[k] || {n: 0, t: {}, side: {}, dates: []}; g.n++; g.t[r.t] = (g.t[r.t] || 0) + 1; g.dates.push(r.date);
      if (r.d) { const b = BIAS[r.z5]; const s = b ? (r.d === b ? '+' : '-') : (r.d === 'u' ? '^' : 'v'); g.side[r.t + s] = (g.side[r.t + s] || 0) + 1; } };
    R.forEach(r => { add('_all', r); add(zk(r) + '|*', r); add(zk(r) + '|' + r.o, r); });
    const allN = G._all ? G._all.n : 0;
    const base = t => allN ? (G._all.t[t] || 0) / allN * 100 : 0;
    const order = [];
    order.push({k: '_all', label: 'все дни', sub: 'базовая частота', cls: 'mid'});
    ZL.forEach(([z, name]) => {
      order.push({k: z + '|*', label: name, sub: 'вся зона', cls: 'om-zone', zone: z});
      OT.forEach(([o]) => { if (G[z + '|' + o]) order.push({k: z + '|' + o, label: OTN[o], cls: 'om-sub', zone: z}); });
    });
    if (!G[S.sel]) S.sel = '_all';

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
    const selName = selRow.zone ? (S.z === '3' ? Z3 : Z5).find(z => z[0] === selRow.zone)[1] + (selRow.cls === 'om-sub' ? ' · ' + selRow.label : '') : 'все дни';
    const pie1 = pie(selName, DT.map((t, i) => ({label: t[1], value: sg1.t[t[0]] || 0, color: slot(i + 1)})), stats(sg1.dates));
    document.getElementById('om-types').innerHTML = `<div class="om-wrap">${h}</tbody></table></div>${pie1}</div>`;

    // направление направленных типов дня
    const pair = (g, t, trend) => {
      if (!g.n) return '<td class="muted">—</td>';
      const a = trend ? (g.side[t + '+'] || 0) : (g.side[t + '^'] || 0), b = trend ? (g.side[t + '-'] || 0) : (g.side[t + 'v'] || 0);
      const va = S.v === 'n' ? a : f1(a / g.n * 100), vb = S.v === 'n' ? b : f1(b / g.n * 100);
      return `<td><div class="cell"><span class="pct">${va} · ${vb}</span><span class="d">${trend ? 'по тренду · против' : 'вверх · вниз'}</span></div></td>`;
    };
    let q = `<div class="twrap"><table class="res"><thead><tr><th>Точка открытия · тип открытия</th><th>n</th>${DIRT.map(t => `<th>${t[1]}</th>`).join('')}</tr></thead><tbody>`;
    order.filter(o => o.k !== '_all').forEach(o => {
      const g = G[o.k], trend = o.zone !== 'iv';
      q += `<tr class="${o.cls} ${selc(o.k)}" data-k="${o.k}"><td class="state">${o.label}${o.sub ? `<span class="lbl2">${o.sub}</span>` : ''}</td><td class="n">${g.n}</td>${DIRT.map(t => pair(g, t[0], trend)).join('')}</tr>`;
    });
    const trendSel = !selRow.zone || selRow.zone !== 'iv';
    const sumSide = s => DIRT.reduce((a, t) => a + (sg1.side[t[0] + s] || 0), 0);
    let pa, pb;
    if (S.sel === '_all') { pa = 0; pb = 0; order.filter(o => o.cls === 'om-zone' && o.zone !== 'iv').forEach(o => { const g = G[o.k]; pa += DIRT.reduce((a, t) => a + (g.side[t[0] + '+'] || 0), 0); pb += DIRT.reduce((a, t) => a + (g.side[t[0] + '-'] || 0), 0); }); }
    else { pa = trendSel ? sumSide('+') : sumSide('^'); pb = trendSel ? sumSide('-') : sumSide('v'); }
    const nDir = S.sel === '_all' ? order.filter(o => o.cls === 'om-zone' && o.zone !== 'iv').reduce((a, o) => a + G[o.k].n, 0) : sg1.n;
    const pie2 = pie(S.sel === '_all' ? 'все дни вне VA' : selName, [
      {label: trendSel ? 'по тренду точки открытия' : 'вверх', value: pa, color: slot(1)},
      {label: trendSel ? 'против тренда' : 'вниз', value: pb, color: slot(2)},
      {label: 'без направления', value: Math.max(nDir - pa - pb, 0), color: slot(0)},
    ]);
    document.getElementById('om-dirs').innerHTML = `<div class="om-wrap">${q}</tbody></table></div>${pie2}</div>`;
    document.querySelectorAll('#om-types tr[data-k], #om-dirs tr[data-k]').forEach(tr =>
      tr.addEventListener('click', () => { S.cell = ''; upd('sel', tr.dataset.k); }));

    // тепловая карта: тип дня (Y) × тип открытия (X) внутри выбранной зоны
    const hz = selRow.zone || null;
    const cols = OT.map(([o, name]) => ({o, name, g: G[(hz ? hz : '_zoneless') + '|' + o]}))
      .filter(c => hz ? !!c.g : true);
    const colsOut = hz ? cols : OT.map(([o, name]) => {
      const g = {n: 0, t: {}};
      ZL.forEach(([z]) => { const x = G[z + '|' + o]; if (!x) return; g.n += x.n; DT.forEach(t => { g.t[t[0]] = (g.t[t[0]] || 0) + (x.t[t[0]] || 0); }); });
      return {o, name, g};
    }).filter(c => c.g.n);
    const val = (c, t) => (c.g.t[t] || 0) / c.g.n * 100;
    const rowMax = {}, rowMin = {};
    DT.forEach(t => {
      const v = colsOut.map(c => val(c, t[0]));
      rowMax[t[0]] = Math.max(...v, 0.1); rowMin[t[0]] = Math.min(...v, rowMax[t[0]]);
    });
    const mxAll = Math.max(...DT.map(t => rowMax[t[0]]), 1);
    // «по строке»: минимум строки синий, максимум розовый; «общая»: 0 → максимум карты
    const norm = (p, t) => S.hs === 'row'
      ? (rowMax[t] - rowMin[t] < 1e-9 ? 0.5 : (p - rowMin[t]) / (rowMax[t] - rowMin[t]))
      : p / mxAll;
    const cs = getComputedStyle(document.documentElement);
    const rgb = v => (cs.getPropertyValue(v).trim() || '#888').replace('#', '').match(/../g).map(x => parseInt(x, 16));
    const LO = rgb('--up'), HI = rgb('--dn'), BG = rgb('--surface');
    // относительная яркость sRGB (WCAG) и контраст двух цветов
    const relLum = v => v.reduce((s, x, i) => {
      const u = x / 255, l = u <= 0.03928 ? u / 12.92 : Math.pow((u + 0.055) / 1.055, 2.4);
      return s + [0.2126, 0.7152, 0.0722][i] * l;
    }, 0);
    const contrast = (a, b) => {
      const l1 = relLum(a), l2 = relLum(b);
      return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
    };
    const INK_D = [11, 11, 11], INK_L = [255, 255, 255];
    const paint = t => {
      const a = 0.12 + 0.88 * t;
      const c = LO.map((l, i) => Math.round(l + (HI[i] - l) * t));
      // цвет цифр по фактическому цвету ячейки: подложка просвечивает через прозрачность
      const eff = c.map((x, i) => a * x + (1 - a) * BG[i]);
      const ink = contrast(eff, INK_D) >= contrast(eff, INK_L) ? INK_D : INK_L;
      return `background:rgba(${c[0]},${c[1]},${c[2]},${a.toFixed(3)});color:rgb(${ink.join(',')})`;
    };
    let hm = `<table class="om-hm"><thead><tr><th class="om-rowh">Тип дня \\ тип открытия</th><th>все дни<span class="om-n">${(hz ? G[hz + '|*'] : G._all).n}</span></th>` +
      colsOut.map(c => `<th class="${selRow.k === (hz || '') + '|' + c.o ? 'om-colsel' : ''}">${c.name.replace('Open-', 'O-')}<span class="om-n">${c.g.n}</span></th>`).join('') + '</tr></thead><tbody>';
    const baseG = hz ? G[hz + '|*'] : G._all;
    DT.forEach(t => {
      hm += `<tr><th class="om-rowh">${t[1]}</th><td class="om-base">${f1((baseG.t[t[0]] || 0) / baseG.n * 100)}%</td>` +
        colsOut.map(c => {
          const p = val(c, t[0]), k = c.o + '|' + t[0];
          return `<td data-k="${k}" class="${S.cell === k ? 'om-cellsel' : ''}" style="${paint(norm(p, t[0]))}" ` +
            `title="${t[1]} · ${c.name}: ${f1(p)}% (${c.g.t[t[0]] || 0} из ${c.g.n}) — клик подсветит эти дни на графике">${f1(p)}%</td>`;
        }).join('') + '</tr>';
    });
    const g1 = `rgb(${HI.join(',')})`;
    hm += `</tbody></table><div class="om-scale"><span class="om-bar" style="background:linear-gradient(90deg, rgba(${LO.join(',')},.12), ${g1})"></span>` +
      `<span>${S.hs === 'row' ? 'синий — реже всего в строке, розовый — чаще всего (шкала своя у каждого типа дня)' : `общая шкала 0% → ${f1(mxAll)}%: синий — реже, розовый — чаще`}</span></div>`;
    document.getElementById('om-heat').innerHTML = `<div class="om-heat">${hm}</div>`;
    const sub = document.getElementById('om-heat-sub');
    if (sub) sub.textContent = (hz ? selRow.label.startsWith('Open') ? (S.z === '3' ? Z3 : Z5).find(z => z[0] === hz)[1] : selName : 'все зоны') + ' · колонка = 100%';

    document.querySelectorAll('#om-heat td[data-k]').forEach(td =>
      td.addEventListener('click', () => upd('cell', S.cell === td.dataset.k ? '' : td.dataset.k)));

    // выбор уезжает в смотрелку профилей над тестом
    const zoneCodes = selRow.zone
      ? (S.z === '3' ? Z5.filter(z => TO3[z[0]] === selRow.zone).map(z => z[0]) : [selRow.zone])
      : [];
    const rowOpen = S.sel.includes('|') && !S.sel.endsWith('|*') ? S.sel.split('|')[1] : '';
    const cellSel = S.cell ? S.cell.split('|') : null;
    const open = cellSel ? cellSel[0] : rowOpen, dayType = cellSel ? cellSel[1] : '';
    const zoneName = selRow.zone ? (S.z === '3' ? Z3 : Z5).find(z => z[0] === selRow.zone)[1] : '';
    const bits = cellSel
      ? [zoneName, OTN[open], DT.find(t => t[0] === dayType)[1]]
      : [selName === 'все дни' ? '' : selName];
    const label = bits.filter(Boolean).join(' · ') || 'все дни';
    window.dispatchEvent(new CustomEvent('mp-selection', {detail: {
      mode: S.m, ref: S.c, zones: zoneCodes, open, dayType, label}}));

    const blk = S.m === 'f' ? 'фиксированный блок 2 пт' : 'адаптивный блок';
    const ref = S.c === '0' ? 'опора = вчерашний день' : 'опора = композит (от 2 дней, иначе вчерашний день)';
    document.getElementById('om-note').textContent = `${blk} · ${ref} · ${S.p === 'all' ? '2010–2026' : S.p === 'a' ? '2010–2018' : '2019–2026'}. ` +
      `«% зоны» — доля дней зоны с этим типом открытия. Под процентом типа дня — разница с базовой частотой (все дни) в процентных пунктах. ` +
      `Во второй таблице — доля дней строки с этим типом дня по тренду точки открытия и против (для «внутри VA» — вверх и вниз). Тепловая карта и кольцо показывают выбранную строку: кликни по строке таблицы, чтобы переключить. Клик по ячейке карты подсвечивает эти дни на графике вверху страницы.`;
  }
  render();
  // данные графика приезжают отдельным файлом: когда доехали — пересчитываем карточку статистики
  if (!window.MPCHART) window.addEventListener('mpchart-data', () => render(), {once: true});
  new MutationObserver(render).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
})();
