// Рендерер cot_pa_tables: таблицы 3×5 теста 1.1 / 1.2.
// Ожидает window.DATA = {test, meta, funnels, results} из results.json
// и на странице: #hdr-meta, #pa-controls, #pa-results, #pa-funnel.
(function(){
  const D = window.DATA;
  const M = D.meta;
  const T = D.test;
  const GROUPS = {lf:'Leveraged Funds', am:'Asset Managers'};
  const fmt = (v, d=1) => v === null || v === undefined ? '' : v.toFixed(d);
  const sgn = v => v > 0 ? '+' + fmt(v) : fmt(v);
  const esc = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;');

  const hm = document.getElementById('hdr-meta');
  if (hm) hm.innerHTML =
    `<div><span class="dot"></span>COT <b>${M.cot_from} → ${M.cot_to}</b> · ${M.cot_reports} отчётов</div>` +
    `<div>ES RTH <b>${M.es_from} → ${M.es_to}</b> · ${M.es_days} сессий · ${M.es_weeks} недель</div>` +
    `<div>Результаты собраны ${M.built}</div>`;

  const s = {g:'lf', thr:'2080', roll:'excl'};
  try{ Object.assign(s, JSON.parse(localStorage.getItem('cot-pa-' + T) || '{}')); }catch(e){}
  const save = () => { try{ localStorage.setItem('cot-pa-' + T, JSON.stringify(s)); }catch(e){} };

  function seg(opts, cur, cb){
    const el = document.createElement('div'); el.className = 'seg';
    opts.forEach(([v, label]) => {
      const b = document.createElement('button'); b.textContent = label;
      b.setAttribute('aria-pressed', v === cur);
      b.addEventListener('click', () => cb(v));
      el.appendChild(b);
    });
    return el;
  }
  function ctl(label, node){
    const w = document.createElement('div'); w.className = 'ctl';
    const l = document.createElement('span'); l.className = 'ctl-label'; l.textContent = label;
    w.append(l, node); return w;
  }
  const upd = (k, v) => { s[k] = v; save(); renderControls(); renderResults(); };
  function renderControls(){
    const host = document.getElementById('pa-controls'); host.innerHTML = '';
    host.appendChild(ctl('Группа', seg([['lf','LF'],['am','AM']], s.g, v => upd('g', v))));
    host.appendChild(ctl('Порог', seg([['2080','20 / 80'],['1090','10 / 90']], s.thr, v => upd('thr', v))));
    host.appendChild(ctl('Ролловые недели', seg([['excl','Исключены'],['incl','Включены']], s.roll, v => upd('roll', v))));
  }

  function renderFunnel(){
    const host = document.getElementById('pa-funnel'); if (!host) return;
    const F = D.funnels[`${s.g}_${s.roll}`];
    const steps = [['Недель в ценовом ряде', F.all],['С 2011', F.year],['Полные недели (5 сессий, без укороченных)', F.full],
      [s.roll === 'excl' ? 'Без ролловых недель' : 'Ролловые недели оставлены', F.roll],['Без отчётов с задержкой', F.delay],['С рассчитанным состоянием COT', F.state]];
    let prev = null;
    host.innerHTML = '<div class="funnel">' + steps.map(([k, v]) => { const d = prev === null ? '' : `<small>−${prev - v}</small>`; prev = v; return `<div class="frow"><div class="k">${k}</div><div class="v">${v}${d}</div></div>`; }).join('') + '</div>';
  }

  function renderResults(){
    const key = `${s.g}_${s.roll}_${s.thr}_${T}`;
    const R = D.results[key];
    const passed = D.results[`${s.g}_${s.roll}_${T}_passed`];
    const labels = M.tests[T].labels;
    const F = D.funnels[`${s.g}_${s.roll}`];
    const host = document.getElementById('pa-results');
    const rows = R.rows;

    let html = '<div class="tiles">';
    const pdn = st => rows[st].pup === null ? null : 100 - rows[st].pup;
    html += `<div class="tile"><div class="l">Low · перепродано → вверх?</div><div class="v up">${fmt(rows.Low.pup)}%</div><div class="s">недель вверх · n ${rows.Low.n} · Mid ${fmt(rows.Mid.pup)}% · ${sgn(rows.Low.pup - rows.Mid.pup)} п.п.</div></div>`;
    html += `<div class="tile"><div class="l">High · перекуплено → вниз?</div><div class="v dn">${fmt(pdn('High'))}%</div><div class="s">недель вниз · n ${rows.High.n} · Mid ${fmt(pdn('Mid'))}% · ${sgn(pdn('High') - pdn('Mid'))} п.п.</div></div>`;
    html += `<div class="tile"><div class="l">Mid · база</div><div class="v">${fmt(rows.Mid.pup,0)} / ${fmt(pdn('Mid'),0)}</div><div class="s">вверх / вниз, % · n ${rows.Mid.n}</div></div>`;
    html += `<div class="tile"><div class="l">В тесте</div><div class="v">${F.state}</div><div class="s">из ${F.all} недель</div></div>`;
    html += '</div>';

    if (passed.length){
      html += `<div class="verdict"><span class="pill pass">Прошло</span><div>${passed.map(p => `<b>${p.state}</b> · ${esc(p.bucket)}: ${sgn(p.d2080)} п.п. на 20/80, ${sgn(p.d1090)} п.п. на 10/90`).join('<br>')}</div></div>`;
    } else {
      const hits = R.hits.filter(h => h.n_ok);
      html += `<div class="verdict"><span class="pill fail">Не прошло</span><div>${hits.length ? 'На этом пороге есть ячейки ≥ 10 п.п. (' + hits.map(h => `${h.state} · ${esc(h.bucket)} ${sgn(h.diff)}`).join('; ') + '), но на втором пороге та же ячейка не подтверждается.' : 'Ни одна ячейка не отличается от Mid на 10 п.п. и больше.'}</div></div>`;
    }

    html += '<div class="twrap"><table class="res"><thead><tr><th>Состояние</th><th>n</th>';
    labels.forEach((l, i) => html += `<th class="${i===0?'sep':''}">${esc(l)}</th>`);
    html += '<th class="sep">mean %</th><th>median %</th><th>В сторону идеи %</th></tr></thead><tbody>';
    ['Low','Mid','High'].forEach(st => {
      const r = rows[st]; const isMid = st === 'Mid';
      html += `<tr class="${isMid?'mid':''}"><td class="state">${st}</td><td class="n">${r.n}</td>`;
      r.pct.forEach((p, i) => {
        let cls = i === 0 ? 'sep' : '';
        let d = '';
        if (!isMid){
          const dv = R.diff[st][i];
          const dcls = dv > 0 ? 'up' : dv < 0 ? 'dn' : '';
          if (dv !== null && Math.abs(dv) >= M.min_lift) cls += dv > 0 ? ' hit-up' : ' hit-dn';
          d = `<span class="d ${dcls}">${sgn(dv)}</span>`;
        } else {
          d = '<span class="d">база</span>';
        }
        html += `<td class="${cls}"><div class="cell"><span class="pct">${fmt(p)}</span>${d}</div></td>`;
      });
      const mc = r.mean > 0 ? 'up' : r.mean < 0 ? 'dn' : '';
      const idea = st === 'Low' ? `<span class="up">${fmt(r.pup)}</span> вверх` : st === 'High' ? `<span class="dn">${fmt(100 - r.pup)}</span> вниз` : `<span class="muted">${fmt(r.pup,0)} / ${fmt(100 - r.pup,0)}</span>`;
      html += `<td class="sep"><span class="${mc}">${sgn(r.mean)}</span></td><td>${sgn(r.median)}</td><td>${idea}</td></tr>`;
    });
    html += '</tbody></table></div>';

    html += '<div class="bars">';
    ['Low','Mid','High'].forEach(st => {
      html += `<div class="bar-row"><div class="bar-lbl">${st}</div><div class="bar">` +
        rows[st].pct.map((p, i) => `<span class="b${i}" style="width:${p||0}%" title="${esc(labels[i])}: ${fmt(p)}%"></span>`).join('') +
        '</div></div>';
    });
    html += '</div><div class="bar-legend">' + labels.map((l, i) => `<span><i class="b${i}" style="background:var(--${['dn-bg-2','dn-bg','surface-2','up-bg','up-bg-2'][i]})"></i>${esc(l)}</span>`).join('') + '</div>';
    html += `<div class="note">Под каждым процентом у Low и High стоит разница с Mid в процентных пунктах. Подсвечены ячейки с |разницей| ≥ ${M.min_lift} п.п. Синий сдвиг вверх, розовый вниз. Колонка «В сторону идеи»: для Low доля недель вверх (перепродано → рост), для High доля недель вниз (перекуплено → падение), для Mid база вверх / вниз. ${GROUPS[s.g]}, порог ${s.thr.slice(0,2)}/${s.thr.slice(2)}, ролловые недели ${s.roll==='excl'?'исключены':'включены'}.</div>`;
    host.innerHTML = html;
    renderFunnel();
  }
  renderControls(); renderResults();
})();
