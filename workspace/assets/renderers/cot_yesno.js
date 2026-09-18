// Рендерер cot_yesno: один вопрос «да / нет» у границ индекса.
// Ожидает window.DATA = {meta, rows} из results.json. Состояния в rows
// закодированы одной буквой: L / M / H (Low / Mid / High), отсутствие ключа = индекс ещё не рассчитан.
// На странице: #hdr-meta, .seg#c-*, #tgt-txt, #big, #tb, #note.
(function(){
  const W = window.DATA.rows;
  const M = window.DATA.meta;
  const S = {v:'', i:'contra', g:'lf', n:'52', t:'2080', w:'wc', p:'70'};
  try{ Object.assign(S, JSON.parse(localStorage.getItem('cot-yesno') || '{}')); }catch(e){}
  const f = v => Number.isFinite(v) ? v.toFixed(1) : '';
  function stateOf(w){
    if (S.g === 'both'){ const a = w[S.v+'lf'+S.n+'_'+S.t], b = w[S.v+'am'+S.n+'_'+S.t]; return a && a === b ? a : null; }
    return w[S.v+S.g+S.n+'_'+S.t] || null;
  }
  function render(){
    document.querySelectorAll('.seg[id^="c-"]').forEach(seg => { const key = seg.id.slice(2); seg.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', b.dataset.v === S[key])); });
    const T = +S.p; document.getElementById('tgt-txt').textContent = T;
    const ws = W.filter(w => !w.roll && stateOf(w));
    const low = ws.filter(w => stateOf(w) === 'L').map(w => w[S.w]);
    const high = ws.filter(w => stateOf(w) === 'H').map(w => w[S.w]);
    const contra = S.i === 'contra';
    const yesL = low.filter(v => contra ? v > 0 : v < 0).length, yesH = high.filter(v => contra ? v < 0 : v > 0).length;
    const pL = low.length ? yesL/low.length*100 : NaN, pH = high.length ? yesH/high.length*100 : NaN;
    const lo = +S.t.slice(0,2), hi = +S.t.slice(2);
    const hm = document.getElementById('hdr-meta');
    if (hm) hm.innerHTML = `<div><span class="dot"></span><b>${ws.length}</b> недель в выборке</div><div>${M.note}</div><div>Результаты собраны ${M.built}</div>`;
    const winName = S.w === 'wc' ? 'неделя' : 'понедельник';
    const tile = (title, p, yes, n, ok) => `<div class="tile"><div class="l">${title}</div><div class="v ${ok?'ok':'no'}">${f(p)}%</div><div class="s">${yes} из <b>${n}</b> · планка ${T}% · <b>${ok ? 'прошло' : 'не прошло'}</b>${n < 30 ? ' · n меньше 30, ненадёжно' : ''}</div></div>`;
    document.getElementById('big').innerHTML =
      tile(`Индекс ≤ ${lo} → ${winName} закрылась ${contra?'выше':'ниже'}?`, pL, yesL, low.length, pL >= T) +
      tile(`Индекс ≥ ${hi} → ${winName} закрылась ${contra?'ниже':'выше'}?`, pH, yesH, high.length, pH >= T);
    const row = (name, lbl, n, yes, p) => `<tr><td class="state">${name}<span class="lbl2">${lbl}</span></td><td>${n}</td><td class="${p>=T?'hit':''}"><span class="yes">${f(p)}</span></td><td>${f(100-p)}</td><td>${yes}</td><td>${n-yes}</td><td><span class="pill ${p>=T?'ok':'fail'}">${p>=T?'прошло':'не прошло'}</span></td></tr>`;
    document.getElementById('tb').innerHTML =
      row(`≤ ${lo}`, contra ? 'нижняя граница · закрылось выше' : 'нижняя граница · закрылось ниже', low.length, yesL, pL) +
      row(`≥ ${hi}`, contra ? 'верхняя граница · закрылось ниже' : 'верхняя граница · закрылось выше', high.length, yesH, pH);
    const gname = {lf:'Leveraged Funds', am:'Asset Managers', both:'LF и AM одновременно у одной границы'}[S.g];
    document.getElementById('note').textContent = `${gname} · ${S.v ? 'ΔNet: изменение чистой позиции за неделю' : 'Net = Long − Short'} · индекс, окно ${S.n} недель · границы ${lo} / ${hi} · идея ${contra ? 'контртренд' : 'моментум'} · ${S.w==='wc'?'закрытие пт RTH против открытия пн RTH':'закрытие пн RTH против открытия пн RTH'}. Считается только неделя, следующая за отчётом. Ролловые недели и отчёты, вышедшие с задержкой, исключены.`;
  }
  document.querySelectorAll('.seg[id^="c-"] button').forEach(b => b.addEventListener('click', () => { S[b.closest('.seg').id.slice(2)] = b.dataset.v; try{ localStorage.setItem('cot-yesno', JSON.stringify(S)); }catch(e){} render(); }));
  render();
})();
