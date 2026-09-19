"""
Тип открытия по Mind Over Markets (гл. 4) и зона открытия. Числа в config, раздел «Типы открытия».

Обозначения: O = цена 09:30, OR = диапазон первых OR_MIN минут, окно = первый час (до 10:30),
D = DRIVE_R20 × R20, m = ORR_MIN_R20 × R20, уровни теста = VAH / VAL опорного профиля
(вчерашний день или композит).

Порядок проверки (первый подошедший):
  1. Open-Drive        после OR цена до 10:30 не заходит за противоположную границу OR
                       и уходит от OR на ≥ D в пределах A (до 10:00, OD_DRIVE_MIN)
  2. Open-Test-Drive   в первый час цена касается (до 1 тика) или пробивает уровень теста
                       против будущего направления, после этого экстремума уходит от
                       противоположной границы OR на ≥ D; экстремум теста до 10:30 не обновлён
  3. Open-Rejection-Reverse   первый ход от OR ≥ m в одну сторону, затем до 10:30 цена
                       торгуется за противоположной границей OR. Флаг orr_tested_va: был ли
                       в первом ходе тест VAH / VAL
  4. Open-Auction      всё остальное
open_dir = направление итогового хода (у ORR направление разворота).

Зона открытия относительно опоры: above_range / above_value / in_value / below_value / below_range.
Принятие (accept): блоки A и B торговались на общих уровнях внутри зоны открытия (двойные TPO).
"""
import numpy as np

import config as C


def classify(lo, hi, n_or: int, open_: float, r20: float, vah: float, val: float) -> dict:
    """lo/hi — минутные low/high первого часа по порядку; первые n_or минут = диапазон открытия."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    or_hi, or_lo = hi[:n_or].max(), lo[:n_or].min()
    D, m = C.DRIVE_R20 * r20, C.ORR_MIN_R20 * r20
    a_lo, a_hi = lo[n_or:], hi[n_or:]
    res = {"or_high": or_hi, "or_low": or_lo, "open_type": "open_auction", "open_dir": "", "orr_tested_va": False}
    if len(a_lo) == 0 or not r20 or np.isnan(r20):
        res["open_type"] = ""
        return res

    # 1. Open-Drive: весь час не за противоположной границей OR, драйв ≥ D в пределах A
    k = max(C.OD_DRIVE_MIN - n_or, 0)
    if a_lo.min() >= or_lo and a_hi[:k].size and a_hi[:k].max() - or_hi >= D:
        res.update(open_type="open_drive", open_dir="up")
        return res
    if a_hi.max() <= or_hi and a_lo[:k].size and or_lo - a_lo[:k].min() >= D:
        res.update(open_type="open_drive", open_dir="down")
        return res

    # 2. Open-Test-Drive (уровни VAH / VAL; тест против будущего направления)
    levels = [x for x in (vah, val) if x is not None and not np.isnan(x)]
    if levels:
        t_lo = int(np.argmin(lo))  # тест снизу → драйв вверх
        if any(lo[t_lo] <= e + C.TICK and e <= open_ for e in levels):
            if hi[t_lo + 1 :].size and hi[t_lo + 1 :].max() - or_hi >= D:
                res.update(open_type="open_test_drive", open_dir="up")
                return res
        t_hi = int(np.argmax(hi))  # тест сверху → драйв вниз
        if any(hi[t_hi] >= e - C.TICK and e >= open_ for e in levels):
            if lo[t_hi + 1 :].size and or_lo - lo[t_hi + 1 :].min() >= D:
                res.update(open_type="open_test_drive", open_dir="down")
                return res

    # 3. Open-Rejection-Reverse
    up_hit = np.flatnonzero(a_hi >= or_hi + m)
    dn_hit = np.flatnonzero(a_lo <= or_lo - m)
    first_up = up_hit[0] if up_hit.size else None
    first_dn = dn_hit[0] if dn_hit.size else None
    if first_up is not None and (first_dn is None or first_up < first_dn):
        if (a_lo[first_up + 1 :] < or_lo).any():
            k = first_up + np.argmax(a_lo[first_up + 1 :] < or_lo) + 1
            tested = any(a_hi[: k].max() >= e - C.TICK and e >= or_hi for e in levels)
            res.update(open_type="open_rejection_reverse", open_dir="down", orr_tested_va=bool(tested))
            return res
    if first_dn is not None and (first_up is None or first_dn < first_up):
        if (a_hi[first_dn + 1 :] > or_hi).any():
            k = first_dn + np.argmax(a_hi[first_dn + 1 :] > or_hi) + 1
            tested = any(a_lo[: k].min() <= e + C.TICK and e <= or_lo for e in levels)
            res.update(open_type="open_rejection_reverse", open_dir="up", orr_tested_va=bool(tested))
            return res
    return res


def zone(open_: float, val: float, vah: float, low: float, high: float) -> tuple[str, float, float]:
    """Зона открытия и её границы по цене."""
    if open_ > high:
        return "above_range", high, np.inf
    if open_ > vah:
        return "above_value", vah, high
    if open_ < low:
        return "below_range", -np.inf, low
    if open_ < val:
        return "below_value", low, val
    return "in_value", val, vah


def accepted(z_lo: float, z_hi: float, a_lo: float, a_hi: float, b_lo: float, b_hi: float) -> bool:
    """A и B торговались на общих уровнях внутри зоны."""
    return max(z_lo, a_lo, b_lo) <= min(z_hi, a_hi, b_hi)
