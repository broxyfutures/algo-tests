"""
Тип открытия и зона открытия (правила утверждены трейдером 22.09.2026, PROFILE_RULES.md, раздел 7).

Переменные: точка открытия (цена 09:30), опора (VA, high, low вчерашнего профиля или композита),
блоки A (09:30–10:00) и B (10:00–10:30), IB = A + B, цена в 10:30 (закрытие B), следующий час
(10:30–11:30). Касание уровня = с точностью до 1 тика. Пробой IB = хотя бы тик за экстремумом IB.

Тренд точки открытия: выше VA → лонг, ниже VA → шорт. Своя граница VA: VAH при лонге, VAL при шорте.

Открытие внутри VA → Open-Auction внутри VA (open_auction_in).

Открытие вне VA, по порядку:
  1. Своя граница VA коснулась за 09:30–10:30?
       да → цена в 10:30 внутри VA или прошла её насквозь → Open-Rejection-Reverse
            цена в 10:30 снова за VA со стороны открытия  → кандидат в Open-Test-Drive (шаг 3)
  2. VA не коснулась:
       открытие внутри вчерашнего диапазона:
            в B цена вернулась к экстремуму A против тренда (касание или проход) → кандидат (шаг 3)
            иначе → Open-Drive
       открытие за вчерашним диапазоном (триггер — граница диапазона):
            в B цена коснулась вчерашнего high (лонг) / low (шорт) → кандидат (шаг 3)
            иначе, если в B экстремум A против тренда не пробит → Open-Drive
            иначе (экстремум A пробит, до границы диапазона не дошли) → Open-Auction вне VA
  3. Кандидат: в 10:30–11:30 пробой IB по тренду (хай IB при лонге, лоу IB при шорте)?
       да → Open-Test-Drive, нет → Open-Auction вне VA (open_auction_out)

Направление (open_dir): Open-Drive и Open-Test-Drive — по тренду точки открытия,
Open-Rejection-Reverse — против, Open-Auction — без направления.
"""
import numpy as np

import config as C


def classify(lo, hi, cl, open_: float, vah: float, val: float, high: float, low: float,
             n_a: int = 30, n_ib: int = 60) -> dict:
    """lo/hi/cl — минутные low/high/close RTH-дня по порядку; первые n_a минут = A, n_ib = IB."""
    lo, hi, cl = np.asarray(lo, float), np.asarray(hi, float), np.asarray(cl, float)
    t = C.TICK
    res = {"open_type": "", "open_dir": "", "trigger": "", "c1030": np.nan, "ib_break": False}
    if len(lo) < n_ib:
        return res
    if val <= open_ <= vah:
        res["open_type"] = "open_auction_in"
        return res

    up = open_ > vah
    ib_hi, ib_lo = hi[:n_ib].max(), lo[:n_ib].min()
    a_lo, a_hi = lo[:n_a].min(), hi[:n_a].max()
    b_lo, b_hi = lo[n_a:n_ib].min(), hi[n_a:n_ib].max()
    c1030 = cl[n_ib - 1]
    res["c1030"] = c1030
    nxt_hi, nxt_lo = hi[n_ib:n_ib + 60], lo[n_ib:n_ib + 60]
    brk = bool(nxt_hi.size and nxt_hi.max() >= ib_hi + t) if up else bool(nxt_lo.size and nxt_lo.min() <= ib_lo - t)
    res["ib_break"] = brk
    bias, against = ("up", "down") if up else ("down", "up")

    def candidate(trigger):
        res["trigger"] = trigger
        if brk:
            res.update(open_type="open_test_drive", open_dir=bias)
        else:
            res["open_type"] = "open_auction_out"
        return res

    # 1. тест своей границы VA за первый час
    va_touch = ib_lo <= vah + t if up else ib_hi >= val - t
    if va_touch:
        back_out = c1030 > vah if up else c1030 < val
        if not back_out:
            res.update(open_type="open_rejection_reverse", open_dir=against, trigger="va")
            return res
        return candidate("va")

    # 2. VA не коснулась
    outside_range = open_ > high if up else open_ < low
    if not outside_range:
        b_tests_a = b_lo <= a_lo + t if up else b_hi >= a_hi - t
        if b_tests_a:
            return candidate("a_extreme")
        res.update(open_type="open_drive", open_dir=bias)
        return res

    b_touch_range = b_lo <= high + t if up else b_hi >= low - t
    if b_touch_range:
        return candidate("range")
    a_held = b_lo >= a_lo - t if up else b_hi <= a_hi + t
    if a_held:
        res.update(open_type="open_drive", open_dir=bias)
        return res
    res["open_type"] = "open_auction_out"
    res["trigger"] = "a_blurred"
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
