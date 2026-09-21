"""
Дневные композиты: несколько дневных профилей, склеенных в одно распределение.

Правило (config, раздел «Композиты»; подробно в PROFILE_RULES.md):
  1. Композит начинается с любого дня (в том числе трендового) и хранится как набор его 30-мин блоков.
  2. Новый день сравнивается с VA всего композита: доля VA нового дня, лежащая внутри VA композита.
     > COMP_MIN_OVERLAP → кандидат на добавление. Иначе цена мигрировала: композит закрыт,
     с этого дня начинается новый.
  3. Кандидат добавляется «на пробу», и форма получившегося профиля проверяется:
       - POC в средней части диапазона (COMP_POC_POS);
       - один пик: нет второго пика ≥ COMP_PEAK_RATIO от главного, отделённого провалом
         ≤ COMP_TROUGH_RATIO от второго пика (двойное распределение);
       - VA симметрична: короткая сторона VA от POC ≥ COMP_VA_SYM длинной.
     Форма прошла → день добавлен. Не прошла → день пропущен, композит остаётся открытым.
  4. Через ролл композит сдвигается на спред в момент переключения и продолжается.
  5. Профиль композита всегда пересчитывается с блоком текущего дня (в adaptive блок меняется).
"""
import numpy as np

import config as C
from mp import profile as P


def shape(lows, highs, row: float) -> dict:
    p = P.build(lows, highs, row)
    c = p.counts
    n = len(c)
    ipoc = P.poc_index(p)
    lo, hi = P.value_area(p, ipoc)
    pos = (ipoc + 0.5) / n
    sm = np.convolve(c, np.ones(3) / 3, mode="same")
    pk = int(np.argmax(sm))
    bimodal = False
    for j in range(1, n - 1):
        if sm[j] >= sm[j - 1] and sm[j] >= sm[j + 1] and abs(j - pk) >= C.COMP_PEAK_MIN_GAP and sm[j] >= C.COMP_PEAK_RATIO * sm[pk]:
            a, b = sorted((j, pk))
            if sm[a : b + 1].min() <= C.COMP_TROUGH_RATIO * sm[j]:
                bimodal = True
                break
    up, dn = hi - ipoc, ipoc - lo
    sym = (min(up, dn) + 1) / (max(up, dn) + 1)
    lo_pos, hi_pos = C.COMP_POC_POS
    ok = lo_pos <= pos <= hi_pos and not bimodal and sym >= C.COMP_VA_SYM
    return {"poc_pos": round(pos, 3), "bimodal": bimodal, "va_sym": round(sym, 3), "shape_ok": ok}


def overlap_share(new_val, new_vah, comp_val, comp_vah) -> float:
    """Доля VA нового дня внутри VA композита."""
    ov = max(0.0, min(new_vah, comp_vah) - max(new_val, comp_val))
    width = new_vah - new_val
    return ov / width if width > 0 else float(comp_val <= new_val <= comp_vah)
