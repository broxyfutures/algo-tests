// Рендерер mp_zone_table: зона открытия × тип (дня или открытия), описательная статистика.
// Ожидает window.DATA = {test, outcome, meta, zones, types, variants, rows} из results.json
// (scripts/11_test_zone_types.py). rows: [date, f0 zone, f0 type, f0 dir, f1 …, a0 …, a1 …].
// На странице: #hdr-meta, #zt-controls, #zt-types, #zt-dirs, #zt-note.
(function(){
  const D = window.DATA, M = D.meta;
  const KEY = 'mp-zone-' + D.test;
  const S = {m:'f', c:'0', z:'5', p:'all', v:'pct', sel:'_all'};
  try{ Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); }catch(e){}
  const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} };
  const f1 = v => Number.isFinite(v) ? v.toFixed(1) : '';
  const sg = v => (v > 0 ? '+' : '') + f1(v);

  const Z5 = D.zones;
  const Z3 = [['or', 'снаружи диапазона'], ['ov', 'снаружи VA, в диапазоне'], ['iv', 'внутри VA']];
  const TO3 = {ar:'or', br:'or', av:'ov', bv:'ov', iv:'iv'};
  const BIAS = {ar:'u', av:'u', bv:'d', br:'d', iv:''};
  const DIRT = D.types.filter(t => t[2]);

  // палитра: категориальные слоты в фиксированном порядке (цвет закреплён за типом, не за рангом)
  const st = document.createElement('style');
  st.textContent = `.zt-viz{--z1:#3987e5;--z2:#d95926;--z3:#199e70;--z4:#c98500;--z5:#d55181;--z6:#008300;--z7:#9085e9;--z0:#5f5e5a}
:root[data-theme="light"] .zt-viz{--z1:#2a78d6;--z2:#eb6834;--z3:#1baf7a;--z4:#eda100;--z5:#e87ba4;--z6:#008300;--z7:#4a3aa7;--z0:#b4b2a9}
.zt-wrap{display:flex;gap:20px;align-items:flex-start;flex-wrap:wrap}
.zt-wrap .twrap{flex:1 1 560px;min-width:0}
.zt-pie{flex:0 0 230px;font-family:var(--sans);font-size:12px;color:var(--t2)}
.zt-pie .zt-pt{font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:var(--t3);margin:2px 0 8px}
.zt-pie ul{list-style:none;margin:10px 0 0;padding:0}
.zt-pie li{display:flex;align-items:center;gap:8px;padding:2px 0}
.zt-pie li i{width:10px;height:10px;border-radius:2px;flex:0 0 10px}
.zt-pie li b{margin-left:auto;font-weight:500;color:var(--t1)}
.res tr.zt-row{cursor:pointer}
.res tr.zt-sel td{background:var(--surface-2)}`;
  document.head.appendChild(st);
  const slot = i => `var(--z${i})`;
  function pie(title, parts){
    // parts: [{label, value, color}]
    const tot = parts.reduce((a, p) => a + p.value, 0);
    const R = 80, r = 50, cx = 100, cy = 100;
    let a0 = -Math.PI / 2, arcs = '';
    parts.forEach(p => {
      if (!p.value) return;
      const f = p.value / tot, a1 = a0 + f * 2 * Math.PI, big = f > 0.5 ? 1 : 0;
      const P = (rad, ang) => `${(cx + rad * Math.cos(ang)).toFixed(2)} ${(cy + rad * Math.sin(ang)).toFixed(2)}`;
      const d = f >= 0.9999
        ? `M${P(R, a0)} A${R} ${R} 0 1 1 ${P(R, a0 + Math.PI)} A${R} ${R} 0 1 1 ${P(R, a0)} M${P(r, a0)} A${r} ${r} 0 1 0 ${P(r, a0 + Math.PI)} A${r} ${r} 0 1 0 ${P(r, a0)}Z`
        : `M${P(R, a0)} A${R} ${R} 0 ${big} 1 ${P(R, a1)} L${P(r, a1)} A${r} ${r} 0 ${big} 0 ${P(r, a0)}Z`;
      arcs += `<path d="${d}" fill="${p.color}" stroke="var(--surface)" stroke-width="2" fill-rule="evenodd"><title>${p.label}: ${f1(f * 100)}% (${p.value})</title></path>`;
      a0 = a1;
    });
    const legend = parts.map(p => `<li><i style="background:${p.color}"></i>${p.label}<b>${tot ? f1(p.value / tot * 100) : ''}%</b></li>`).join('');
    return `<div class="zt-pie zt-viz"><div class="zt-pt">${title}</div><svg viewBox="0 0 200 200" width="200" height="200" role="img" aria-label="${title}">${arcs}` +
      `<text x="100" y="97" text-anchor="middle" fill="var(--t1)" font-size="20" font-weight="500">${tot}</text><text x="100" y="116" text-anchor="middle" fill="var(--t3)" font-size="11">дней</text></svg><ul>${legend}</ul></div>`;
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
    const off = 1 + 3 * D.variants.indexOf(S.m + S.c);
    return D.rows.filter(r => { const y = +r[0].slice(0, 4); return S.p === 'all' || (S.p === 'a' ? y <= 2018 : y >= 2019); })
      .map(r => ({z: r[off], t: r[off + 1], d: r[off + 2]}));
  }

  function render(){
    const host = document.getElementById('zt-controls'); host.innerHTML = '';
    host.append(
      ctl('Блок', seg([['f', 'Фикс. 2 пт'], ['a', 'Адаптивный']], S.m, v => upd('m', v))),
      ctl('Композит', seg([['0', 'Выкл · опора вчера'], ['1', 'Вкл · опора композит']], S.c, v => upd('c', v))),
      ctl('Зоны', seg([['5', '5 зон'], ['3', '3 группы']], S.z, v => upd('z', v))),
      ctl('Период', seg([['all', '2010–2026'], ['a', '2010–2018'], ['b', '2019–2026']], S.p, v => upd('p', v))),
      ctl('Показать', seg([['pct', '% дней'], ['n', 'дни']], S.v, v => upd('v', v))),
    );
    const R = rowsNow();
    const zkey = r => S.z === '3' ? TO3[r.z] : r.z;
    const ZL = S.z === '3' ? Z3 : Z5;

    // Таблица 1: доля типов по зонам + все дни
    const cnt = {}, tot = {}, all = {};
    R.forEach(r => { const k = zkey(r); cnt[k] = cnt[k] || {}; cnt[k][r.t] = (cnt[k][r.t] || 0) + 1; tot[k] = (tot[k] || 0) + 1; all[r.t] = (all[r.t] || 0) + 1; });
    const N = R.length;
    const cell = (c, n, base) => {
      if (!n) return '<td class="muted">—</td>';
      const p = c / n * 100;
      if (S.v === 'n') return `<td><div class="cell"><span class="pct">${c}</span></div></td>`;
      const dd = base === null ? '' : `<span class="d ${p - base > 0 ? 'up' : p - base < 0 ? 'dn' : ''}">${sg(p - base)}</span>`;
      return `<td><div class="cell"><span class="pct">${f1(p)}</span>${dd}</div></td>`;
    };
    let h = `<div class="twrap"><table class="res"><thead><tr><th>Зона открытия</th><th>n</th>${D.types.map(t => `<th>${t[1]}</th>`).join('')}</tr></thead><tbody>`;
    if (S.sel !== '_all' && !ZL.some(z => z[0] === S.sel)) S.sel = '_all';
    const selc = k => `zt-row${S.sel === k ? ' zt-sel' : ''}`;
    h += `<tr class="mid ${selc('_all')}" data-k="_all"><td class="state">все дни<span class="lbl2">базовая частота</span></td><td class="n">${N}</td>${D.types.map(t => cell(all[t[0]] || 0, N, null)).join('')}</tr>`;
    ZL.forEach(([k, name]) => {
      const n = tot[k] || 0;
      h += `<tr class="${selc(k)}" data-k="${k}"><td class="state">${name}</td><td class="n">${n}</td>${D.types.map(t => cell((cnt[k] || {})[t[0]] || 0, n, (all[t[0]] || 0) / N * 100)).join('')}</tr>`;
    });
    const selName = S.sel === '_all' ? 'все дни' : ZL.find(z => z[0] === S.sel)[1];
    const src = S.sel === '_all' ? all : (cnt[S.sel] || {});
    const pie1 = pie(selName, D.types.map((t, i) => ({label: t[1], value: src[t[0]] || 0, color: slot(i + 1)})));
    document.getElementById('zt-types').innerHTML = `<div class="zt-wrap">${h}</tbody></table></div>${pie1}</div>`;

    // Таблица 2: направление направленных типов относительно тренда открытия
    const dc = {}, dn = {};
    const addd = (k, t, side) => { dc[k] = dc[k] || {}; dc[k][t + side] = (dc[k][t + side] || 0) + 1; };
    R.forEach(r => {
      const k = zkey(r); dn[k] = (dn[k] || 0) + 1;
      const b = BIAS[r.z];
      if (b) { dn._b = (dn._b || 0) + 1; }
      if (!r.d) return;
      if (b) { const side = r.d === b ? '+' : '-'; addd(k, r.t, side); addd('_b', r.t, side); }
      else addd(k, r.t, r.d === 'u' ? '^' : 'v');
    });
    const pair = (k, t, n, trendSides) => {
      const c = dc[k] || {};
      const a = trendSides ? (c[t + '+'] || 0) : (c[t + '^'] || 0), b = trendSides ? (c[t + '-'] || 0) : (c[t + 'v'] || 0);
      if (!n) return '<td class="muted">—</td>';
      const la = trendSides ? 'по тренду' : 'вверх', lb = trendSides ? 'против' : 'вниз';
      const va = S.v === 'n' ? a : f1(a / n * 100), vb = S.v === 'n' ? b : f1(b / n * 100);
      return `<td><div class="cell"><span class="pct">${va} · ${vb}</span><span class="d">${la} · ${lb}</span></div></td>`;
    };
    let g = `<div class="twrap"><table class="res"><thead><tr><th>Зона открытия</th><th>n</th>${DIRT.map(t => `<th>${t[1]}</th>`).join('')}</tr></thead><tbody>`;
    g += `<tr class="mid ${selc('_all')}" data-k="_all"><td class="state">все дни вне VA<span class="lbl2">открытие выше или ниже VA</span></td><td class="n">${dn._b || 0}</td>${DIRT.map(t => pair('_b', t[0], dn._b || 0, true)).join('')}</tr>`;
    ZL.forEach(([k, name]) => {
      const n = dn[k] || 0, trendSides = k !== 'iv';
      g += `<tr class="${selc(k)}" data-k="${k}"><td class="state">${name}${trendSides ? '' : '<span class="lbl2">тренда открытия нет</span>'}</td><td class="n">${n}</td>${DIRT.map(t => pair(k, t[0], n, trendSides)).join('')}</tr>`;
    });
    const dk = S.sel === '_all' ? '_b' : S.sel, trendPie = dk !== 'iv';
    const dcc = dc[dk] || {}, nsel = dk === '_b' ? (dn._b || 0) : (dn[dk] || 0);
    const sum = side => DIRT.reduce((a, t) => a + (dcc[t[0] + side] || 0), 0);
    const pa = trendPie ? sum('+') : sum('^'), pb = trendPie ? sum('-') : sum('v');
    const pie2 = pie(S.sel === '_all' ? 'все дни вне VA' : selName, [
      {label: trendPie ? 'по тренду открытия' : 'вверх', value: pa, color: slot(1)},
      {label: trendPie ? 'против тренда' : 'вниз', value: pb, color: slot(2)},
      {label: 'без направления', value: Math.max(nsel - pa - pb, 0), color: slot(0)},
    ]);
    document.getElementById('zt-dirs').innerHTML = `<div class="zt-wrap">${g}</tbody></table></div>${pie2}</div>`;
    document.querySelectorAll('#zt-types tr[data-k], #zt-dirs tr[data-k]').forEach(tr => tr.addEventListener('click', () => upd('sel', tr.dataset.k)));

    const blk = S.m === 'f' ? 'фиксированный блок 2 пт' : 'адаптивный блок';
    const ref = S.c === '0' ? 'опора = вчерашний день' : 'опора = композит (если в нём от 2 дней, иначе вчерашний день)';
    document.getElementById('zt-note').textContent = `${blk} · ${ref} · ${S.p === 'all' ? '2010–2026' : S.p === 'a' ? '2010–2018' : '2019–2026'}. ` +
      `В первой таблице под процентом разница с базовой частотой в процентных пунктах. Во второй: доля дней зоны с этим типом по тренду открытия и против (для «внутри VA»: вверх и вниз); сумма двух чисел = доля типа в первой таблице. Кольцо справа показывает выбранную строку: кликни по строке таблицы, чтобы переключить.`;
  }
  render();
})();
