"""
Расписание размера блока (высоты строки профиля) по неделям для двух режимов.

fixed:     день / неделя / месяц = config.ROW_FIXED на всю историю.
adaptive:  правило из config (раздел «Размер блока»):
  1. цель = медиана диапазона RTH за ROW_LOOKBACK_DAYS дней строго до понедельника / ROW_DAY_DIVISOR,
     округлённая до ближайшей ступени ROW_LADDER (в логарифмах);
  2. цель отличается от текущего блока на ROW_JUMP_STEPS+ ступеней → применяется сразу;
     на 1 ступень → применяется, если та же цель держится ROW_CONFIRM_WEEKS понедельника подряд;
  3. недельный = дневной × ROW_MULT["week"];
     месячный = дневной на неделе первого торгового дня месяца × ROW_MULT["month"].
Разгон: пока прошлых дней меньше ROW_LOOKBACK_DAYS, берётся сколько есть (первые недели 2010 года,
в тесты они не попадают).
"""
import numpy as np
import pandas as pd

import config as C

LADDER = np.array(C.ROW_LADDER)


def ladder_index(x: float) -> int:
    return int(np.argmin(np.abs(np.log(LADDER) - np.log(max(x, 1e-6)))))


def week_monday(dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(dates)
    return (d - pd.to_timedelta(d.dt.weekday, unit="D")).dt.normalize()


def schedule(daily: pd.DataFrame) -> pd.DataFrame:
    """daily: колонки date, high, low (RTH-дни). Возвращает строку на неделю:
    week_monday, day_median, target_day, fixed_day/week/month, adaptive_day/week/month, adaptive_changed."""
    d = daily[["date", "high", "low"]].copy()
    d["date"] = pd.to_datetime(d["date"])
    d["rng"] = d["high"] - d["low"]
    d = d.sort_values("date").reset_index(drop=True)
    weeks = sorted(week_monday(d["date"]).unique())

    rows, cur, pend, pend_n = [], None, None, 0
    for wk in weeks:
        past = d.loc[d["date"] < wk, "rng"].tail(C.ROW_LOOKBACK_DAYS)
        if past.empty:
            past = d["rng"].head(C.ROW_LOOKBACK_DAYS)
        med = float(past.median())
        tgt = ladder_index(med / C.ROW_DAY_DIVISOR)
        changed = False
        if cur is None:
            cur = tgt
        elif abs(tgt - cur) >= C.ROW_JUMP_STEPS:
            cur, pend, pend_n, changed = tgt, None, 0, True
        elif tgt != cur:
            pend_n = pend_n + 1 if tgt == pend else 1
            pend = tgt
            if pend_n >= C.ROW_CONFIRM_WEEKS:
                cur, pend, pend_n, changed = tgt, None, 0, True
        else:
            pend, pend_n = None, 0
        rows.append(
            {
                "week_monday": wk,
                "day_median": round(med, 2),
                "target_day": LADDER[tgt],
                "adaptive_day": LADDER[cur],
                "adaptive_changed": changed,
            }
        )
    s = pd.DataFrame(rows)
    s["adaptive_week"] = s["adaptive_day"] * C.ROW_MULT["week"]

    # для справки: месячный блок того месяца, на который приходится понедельник недели
    mr = month_rows(s, d["date"])
    s["adaptive_month"] = [mr.get(pd.Timestamp(w).to_period("M"), np.nan) for w in s["week_monday"]]

    for k in ("day", "week", "month"):
        s[f"fixed_{k}"] = C.ROW_FIXED[k]
    return s


def month_rows(sched: pd.DataFrame, daily_dates: pd.Series) -> dict:
    """{Period('YYYY-MM'): adaptive_month} — по неделе первого торгового дня месяца."""
    d = pd.to_datetime(daily_dates).sort_values()
    first = d.groupby(d.dt.to_period("M")).min()
    wk = week_monday(first.reset_index(drop=True))
    by_wk = dict(zip(sched["week_monday"], sched["adaptive_day"]))
    return {p: by_wk[w] * C.ROW_MULT["month"] for p, w in zip(first.index, wk)}
