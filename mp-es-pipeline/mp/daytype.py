"""
Тип дня по Mind Over Markets (гл. 2). Числа в config, раздел «Типы дня»; описание в PROFILE_RULES.md.

Порядок проверки:
  1. Neutral            выход за IB в обе стороны. Extreme: закрытие в крайних 20 % диапазона, иначе Center
  2. Normal / Nontrend  выхода за IB нет. IB ≥ 0.4 × R20 → Normal, уже → Nontrend
  3. Double-Distribution Trend   выход в одну сторону, IB узкий, две области распределения,
                        разделённые single prints (≥ 2 блоков), в каждой ≥ 25 % TPO
  4. Trend              выход в одну сторону ≥ 1 IB; one-timeframe: от B до блока, поставившего
                        экстремум дня, не больше 1 блока зашло за экстремум предыдущего против тренда
                        (равенство можно); закрытие в крайних 20 % диапазона по тренду.
                        «Не больше 5 TPO в строке» (книга: usually) = пометка thin_profile, не условие
  5. Normal Variation   выход в одну сторону, остальное
Выход за IB засчитывается, если он больше RE_TOL × ширины IB.
"""
import numpy as np

import config as C
from mp import profile as P


def dd_split(counts: np.ndarray) -> bool:
    """Есть ли внутри профиля серия single prints ≥ TAIL_MIN_ROWS, по обе стороны которой
    не меньше DD_MIN_SHARE всех TPO."""
    n = len(counts)
    top, bot = P.edge_run(counts, True), P.edge_run(counts, False)
    single = counts == 1
    single[n - top :] = False
    single[:bot] = False
    total = counts.sum()
    cum = np.cumsum(counts)
    i = 0
    while i < n:
        if single[i]:
            j = i
            while j < n and single[j]:
                j += 1
            if j - i >= C.TAIL_MIN_ROWS:
                below = cum[i - 1] if i > 0 else 0
                above = total - cum[j - 1]
                if below >= C.DD_MIN_SHARE * total and above >= C.DD_MIN_SHARE * total:
                    return True
            i = j
        else:
            i += 1
    return False


def tf_violations(lows, highs, up: bool) -> int:
    """Сколько блоков от B до блока, поставившего экстремум дня, зашли за экстремум
    предыдущего блока против тренда (равенство не нарушение)."""
    k = int(np.argmax(highs)) if up else int(np.argmin(lows))
    v = (lows[1:] < lows[:-1]) if up else (highs[1:] > highs[:-1])
    return int(v[:k].sum())


def classify(lows, highs, open_: float, close: float, r20: float, row: float) -> dict:
    lows, highs = np.asarray(lows, float), np.asarray(highs, float)
    ib_hi, ib_lo = highs[: C.IB_PERIODS].max(), lows[: C.IB_PERIODS].min()
    ibr = ib_hi - ib_lo
    hi, lo = highs.max(), lows.min()
    rng = hi - lo
    ext_up = (hi - ib_hi) / ibr if ibr > 0 else 0.0
    ext_dn = (ib_lo - lo) / ibr if ibr > 0 else 0.0
    re_up, re_dn = ext_up > C.RE_TOL, ext_dn > C.RE_TOL
    ib_width = ibr / r20 if r20 and r20 > 0 else np.nan
    narrow = bool(ib_width < C.IB_NARROW) if not np.isnan(ib_width) else False
    counts = P.build(lows, highs, row).counts
    max_tpo = int(counts.max())
    close_pos = (close - lo) / rng if rng > 0 else 0.5
    open_pos = (open_ - lo) / rng if rng > 0 else 0.5
    split = dd_split(counts)

    out = {
        "r20": round(r20, 2) if r20 else np.nan,
        "ib_width_r20": round(ib_width, 3),
        "ib_narrow": narrow,
        "ext_up_ib": round(ext_up, 3),
        "ext_down_ib": round(ext_dn, 3),
        "re_up": re_up,
        "re_down": re_dn,
        "max_tpo_row": max_tpo,
        "thin_profile": max_tpo <= C.TREND_MAX_TPO,
        "tf_viol_up": tf_violations(lows, highs, True),
        "tf_viol_down": tf_violations(lows, highs, False),
        "close_pos": round(close_pos, 3),
        "open_is_extreme": "low" if open_pos <= 0.1 else ("high" if open_pos >= 0.9 else ""),
        "dd_split": split,
    }

    z = C.NEUTRAL_EXTREME_ZONE
    if re_up and re_dn:
        if close_pos >= 1 - z:
            t, d = "neutral_extreme", "up"
        elif close_pos <= z:
            t, d = "neutral_extreme", "down"
        else:
            t, d = "neutral_center", ""
    elif not re_up and not re_dn:
        t, d = ("nontrend" if narrow else "normal"), ""
    else:
        up = re_up
        d = "up" if up else "down"
        ext = ext_up if up else ext_dn
        close_ok = close_pos >= 1 - C.TREND_CLOSE_ZONE if up else close_pos <= C.TREND_CLOSE_ZONE
        if narrow and split:
            t = "double_distribution_trend"
        elif (ext >= C.TREND_MIN_EXT and tf_violations(lows, highs, up) <= C.TREND_MAX_VIOL and close_ok):
            t = "trend"
        else:
            t = "normal_variation"
    out.update(day_type=t, day_dir=d)
    return out
