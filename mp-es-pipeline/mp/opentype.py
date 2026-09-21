"""
Тип открытия по Mind Over Markets (гл. 4) и зона открытия. Только три переменные:
точка открытия O (цена 09:30), VA опоры (вчерашний день или композит) и IB (блоки A + B).
Никаких диапазонов открытия и порогов; события отслеживаются в течение всего RTH-дня.
Касание уровня = с точностью до 1 тика. Выход за IB = как в типах дня (больше RE_TOL × IB).
Ограничение минуток: если в одной минуте цена ушла от открытия в обе стороны (так в ~70 % дней
в первую же минуту), порядок ходов неизвестен; первый ход берётся по закрытию этой минуты
(флаг ambiguous). Точно это решается только тиковыми данными.

Порядок проверки (первый подошедший), направление = куда в итоге пошла цена:
  1. Open-Drive        открытие = экстремум IB: за весь IB цена не ушла за точку открытия против
                       направления больше чем на 1 тик. Направление = сторона, где построен IB.
  2. Open-Test-Drive   первый ход от открытия в одну сторону касается ближайшей границы VA
                       в этом направлении; затем цена возвращается через открытие и выходит за IB
                       с другой стороны; экстремум первого хода до этого выхода не обновлён.
  3. Open-Rejection-Reverse   то же, что Open-Test-Drive, но первый ход до границы VA не дошёл
                       (или в этом направлении границы VA нет).
  4. Open-Auction      всё остальное: цена ходит по обе стороны открытия, экстремумы ходов
                       переписываются, либо разворота с выходом за IB не было.

Ближайшая граница VA в направлении теста: вниз от открытия — VAH, если открылись выше VA,
VAL, если внутри VA; вверх — VAL, если открылись ниже VA, VAH, если внутри VA. Если в этом
направлении границы VA нет (например, вниз при открытии ниже VA), тест невозможен.

Зона открытия относительно опоры: above_range / above_value / in_value / below_value / below_range.
Принятие (accept): блоки A и B торговались на общих уровнях внутри зоны открытия (двойные TPO).
"""
import numpy as np

import config as C


def nearest_level(open_: float, vah: float, val: float, down: bool):
    """Ближайшая граница VA от точки открытия в направлении хода (None, если её нет)."""
    if vah is None or val is None or np.isnan(vah) or np.isnan(val):
        return None
    if down:
        return vah if open_ > vah else (val if open_ >= val else None)
    return val if open_ < val else (vah if open_ <= vah else None)


def classify(lo, hi, cl, open_: float, vah: float, val: float, n_ib: int = 60) -> dict:
    """lo/hi/cl — минутные low/high/close всего RTH-дня по порядку; первые n_ib минут = IB."""
    lo, hi, cl = np.asarray(lo, float), np.asarray(hi, float), np.asarray(cl, float)
    t = C.TICK
    ib_hi, ib_lo = hi[:n_ib].max(), lo[:n_ib].min()
    res = {"open_type": "open_auction", "open_dir": "", "open_test_level": np.nan, "first_leg": np.nan, "ambiguous": False}

    # 1. Open-Drive: открытие — экстремум IB
    up_od, dn_od = ib_lo >= open_ - t, ib_hi <= open_ + t
    if up_od != dn_od:
        res.update(open_type="open_drive", open_dir="up" if up_od else "down")
        return res

    # первый ход: куда цена первой ушла от открытия больше чем на тик
    away_dn = np.flatnonzero(lo < open_ - t)
    away_up = np.flatnonzero(hi > open_ + t)
    if not away_dn.size and not away_up.size:
        return res
    if away_dn.size and away_up.size and away_dn[0] == away_up[0]:
        # в одной минуте цена ушла от открытия в обе стороны: порядок внутри минуты неизвестен.
        # Симметричное правило: первый ход — туда, где минута закрылась; при закрытии на открытии —
        # в сторону большего отклонения; при равенстве — Open-Auction
        k = int(away_dn[0])
        if cl[k] != open_:
            first_down = cl[k] < open_
        elif (open_ - lo[k]) != (hi[k] - open_):
            first_down = (open_ - lo[k]) > (hi[k] - open_)
        else:
            res["ambiguous"] = True
            return res
        res["ambiguous"] = True
    else:
        first_down = away_up.size == 0 or (away_dn.size and away_dn[0] < away_up[0])

    tol = C.RE_TOL * (ib_hi - ib_lo)
    # возврат через открытие ищется после минуты первого ухода (внутри минуты порядок неизвестен)
    if first_down:
        a0 = int(away_dn[0])
        back = np.flatnonzero(hi[a0 + 1:] > open_ + t) + a0 + 1   # возврат через открытие вверх
        if not back.size:
            return res
        x = int(back[0])
        leg = lo[:x].min()                                 # экстремум первого хода
        re = np.flatnonzero(hi[n_ib:] > ib_hi + tol)       # выход за IB вверх
        if not re.size:
            return res
        r = int(re[0]) + n_ib
        if r <= x or lo[x:r + 1].min() < leg:
            return res
        e = nearest_level(open_, vah, val, down=True)
        tested = e is not None and leg <= e + t
        res.update(open_type="open_test_drive" if tested else "open_rejection_reverse", open_dir="up",
                   open_test_level=e if e is not None else np.nan, first_leg=round(open_ - leg, 2))
        return res

    a0 = int(away_up[0])
    back = np.flatnonzero(lo[a0 + 1:] < open_ - t) + a0 + 1       # возврат через открытие вниз
    if not back.size:
        return res
    x = int(back[0])
    leg = hi[:x].max()
    re = np.flatnonzero(lo[n_ib:] < ib_lo - tol)
    if not re.size:
        return res
    r = int(re[0]) + n_ib
    if r <= x or hi[x:r + 1].max() > leg:
        return res
    e = nearest_level(open_, vah, val, down=False)
    tested = e is not None and leg >= e - t
    res.update(open_type="open_test_drive" if tested else "open_rejection_reverse", open_dir="down",
               open_test_level=e if e is not None else np.nan, first_leg=round(leg - open_, 2))
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
