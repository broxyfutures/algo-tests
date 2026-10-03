"""
Тип открытия и зона открытия (правила трейдера от 03.10.2026, PROFILE_RULES.md, раздел 7).

Переменные: точка открытия (цена 09:30), опора (VA, high, low вчерашнего профиля или композита),
IB = блоки A + B (09:30–10:30), цена в 10:30 (закрытие B). Касание VA = с точностью до 1 тика.

Тренд точки открытия: выше VA → лонг, ниже VA → шорт. Своя граница VA: VAH при лонге, VAL при шорте.
Откат = насколько цена за 09:30–10:30 зашла за цену открытия против тренда.
Порог = 20 % обычного IB (медиана ширины IB за 20 прошлых дней, ib_med).

Открытие внутри VA → Open-Auction внутри VA (open_auction_in).

Открытие вне VA:
  1. Своя граница VA коснулась за 09:30–10:30 (Open-Drive уже невозможен):
       цена в 10:30 внутри VA или прошла её насквозь       → Open-Rejection-Reverse
       цена в 10:30 за VA и по тренду от цены открытия      → Open-Test-Drive
       цена в 10:30 за VA, но не по тренду от цены открытия → Open-Auction вне VA
  2. VA не коснулась:
       откат не больше порога                               → Open-Drive
       откат больше порога, цена в 10:30 по тренду от цены открытия → Open-Test-Drive
       откат больше порога, цена в 10:30 не по тренду        → Open-Auction вне VA

Все типы известны в 10:30. Пробой IB в 10:30–11:30 (ib_break) считается справочно, в правилах не участвует.

Направление (open_dir): Open-Drive и Open-Test-Drive — по тренду точки открытия,
Open-Rejection-Reverse — против, Open-Auction — без направления.
"""
import numpy as np

import config as C

PULLBACK_DIV = 5      # порог отката = обычный IB / 5 (20 %); сравнение adv * 5 > ib_med точное в тиках
IB_MED_DAYS = 20      # сколько прошлых дней в медиане ширины IB


def classify(lo, hi, cl, open_: float, vah: float, val: float, high: float, low: float,
             n_a: int = 30, n_ib: int = 60, ib_med: float = np.nan) -> dict:
    """lo/hi/cl — минутные low/high/close RTH-дня по порядку; первые n_ib минут = IB; ib_med — обычный IB."""
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
    c1030 = cl[n_ib - 1]
    res["c1030"] = c1030
    nxt_hi, nxt_lo = hi[n_ib:n_ib + 60], lo[n_ib:n_ib + 60]
    res["ib_break"] = bool(nxt_hi.size and nxt_hi.max() >= ib_hi + t) if up else bool(nxt_lo.size and nxt_lo.min() <= ib_lo - t)
    bias, against = ("up", "down") if up else ("down", "up")
    trend_side = c1030 > open_ if up else c1030 < open_

    def drive_or_auction():
        if trend_side:
            res.update(open_type="open_test_drive", open_dir=bias)
        else:
            res["open_type"] = "open_auction_out"
        return res

    # 1. тест своей границы VA за первый час
    va_touch = ib_lo <= vah + t if up else ib_hi >= val - t
    if va_touch:
        res["trigger"] = "va"
        back_out = c1030 > vah if up else c1030 < val
        if not back_out:
            res.update(open_type="open_rejection_reverse", open_dir=against)
            return res
        return drive_or_auction()

    # 2. VA не коснулась: решает откат за цену открытия против тренда
    adv = open_ - ib_lo if up else ib_hi - open_
    if not adv * PULLBACK_DIV > ib_med:
        res.update(open_type="open_drive", open_dir=bias)
        return res
    res["trigger"] = "pullback"
    return drive_or_auction()


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
