// Рендерер mp_zone_table: зона открытия × тип (дня или открытия), описательная статистика.
// Ожидает window.DATA = {test, outcome, meta, zones, types, variants, rows} из results.json
// (scripts/11_test_zone_types.py). rows: [date, f0 zone, f0 type, f0 dir, f1 …, a0 …, a1 …].
// На странице: #hdr-meta, #zt-controls, #zt-types, #zt-dirs, #zt-note.
(function(){
  const D = window.DATA, M = D.meta;
  const KEY = 'mp-zone-' + D.test;
  const S = {m:'f', c:'0', z:'5', p:'all', v:'pct'};
  try{ Object.assign(S, JSON.parse(localStorage.getItem(KEY) || '{}')); }catch(e){}
  const save = () => { try{ localStorage.setItem(KEY, JSON.stringify(S)); }catch(e){} };
  const f1 = v => Number.isFinite(v) ? v.toFixed(1) : '';
  const sg = v => (v > 0 ? '+' : '') + f1(v);

  const Z5 = D.zones;
  const Z3 = [['or', 'снаружи диапазона'], ['ov', 'снаружи VA, в диапазоне'], ['iv', 'внутри VA']];
  const TO3 = {ar:'or', br:'or', av:'ov', bv:'ov', iv:'iv'};
  const BIAS = {ar:'u', av:'u', bv:'d', br:'d', iv:''};
  const DIRT = D.types.filter(t => t[2]);

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
    h += `<tr class="mid"><td class="state">все дни<span class="lbl2">базовая частота</span></td><td class="n">${N}</td>${D.types.map(t => cell(all[t[0]] || 0, N, null)).join('')}</tr>`;
    ZL.forEach(([k, name]) => {
      const n = tot[k] || 0;
      h += `<tr><td class="state">${name}</td><td class="n">${n}</td>${D.types.map(t => cell((cnt[k] || {})[t[0]] || 0, n, (all[t[0]] || 0) / N * 100)).join('')}</tr>`;
    });
    document.getElementById('zt-types').innerHTML = h + '</tbody></table></div>';

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
    g += `<tr class="mid"><td class="state">все дни вне VA<span class="lbl2">открытие выше или ниже VA</span></td><td class="n">${dn._b || 0}</td>${DIRT.map(t => pair('_b', t[0], dn._b || 0, true)).join('')}</tr>`;
    ZL.forEach(([k, name]) => {
      const n = dn[k] || 0, trendSides = k !== 'iv';
      g += `<tr><td class="state">${name}${trendSides ? '' : '<span class="lbl2">тренда открытия нет</span>'}</td><td class="n">${n}</td>${DIRT.map(t => pair(k, t[0], n, trendSides)).join('')}</tr>`;
    });
    document.getElementById('zt-dirs').innerHTML = g + '</tbody></table></div>';

    const blk = S.m === 'f' ? 'фиксированный блок 2 пт' : 'адаптивный блок';
    const ref = S.c === '0' ? 'опора = вчерашний день' : 'опора = композит (если в нём от 2 дней, иначе вчерашний день)';
    document.getElementById('zt-note').textContent = `${blk} · ${ref} · ${S.p === 'all' ? '2010–2026' : S.p === 'a' ? '2010–2018' : '2019–2026'}. ` +
      `В первой таблице под процентом разница с базовой частотой в процентных пунктах. Во второй: доля дней зоны с этим типом по тренду открытия и против (для «внутри VA»: вверх и вниз); сумма двух чисел = доля типа в первой таблице.`;
  }
  render();
})();
