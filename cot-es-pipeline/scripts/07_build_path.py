#!/usr/bin/env python3
"""
Шаг 7. Строит «путь» каждой недели и понедельника для конструктора тестов.

Для каждой полной недели с 2011:
  - ATR20 (дневной, RTH, с учётом гэпа к прошлому закрытию) на закрытие
    последней сессии перед понедельником;
  - неделя: RTH-минутки с открытия пн 09:30 до закрытия пт 16:00, и
    понедельник: RTH-минутки одной сессии;
  - для каждого окна два монотонных списка событий в единицах ATR от
    RTH-открытия понедельника: новые максимумы вверх (u) и новые минимумы
    вниз (d), с квантованием 0.02 ATR. Из них в браузере считается первое
    касание любого барьера, MAE и MFE в любую сторону.

Выход: data/derived/path.json
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ES_DIR = ROOT / "data" / "es"
DERIVED = ROOT / "data" / "derived"
TZ = "America/New_York"
STEP = 0.02
START_YEAR = 2011


def events(up: np.ndarray, dn: np.ndarray) -> tuple[list, list]:
    """Индексы минут и уровни, когда бегущий максимум вверх / вниз
    впервые превысил очередной шаг 0.02 ATR."""
    out = []
    for arr in (up, dn):
        cm = np.maximum.accumulate(arr)
        q = np.floor(cm / STEP + 1e-9).astype(int)
        idx = np.flatnonzero(np.diff(q, prepend=-1) > 0)
        idx = idx[q[idx] > 0]  # уровень 0 не событие
        out.append([[int(i), round(float(q[i] * STEP), 2)] for i in idx])
    return out[0], out[1]


def main() -> int:
    files = sorted(glob.glob(str(ES_DIR / "es_1m_*.parquet")))
    if not files:
        sys.exit("Нет минуток в data/es/. Сначала scripts/03_download_es.py --confirm")
    m = pd.concat([pd.read_parquet(f) for f in files])
    m = m[~m.index.duplicated(keep="last")].sort_index().tz_convert(TZ)
    rth = m.between_time("09:30", "16:00", inclusive="left")[["open", "high", "low", "close"]].copy()
    rth["date"] = rth.index.normalize()

    daily = pd.read_csv(DERIVED / "es_daily_rth.csv", parse_dates=["date"]).set_index("date").sort_index()
    pc = daily["close"].shift()
    tr = pd.concat([daily["high"] - daily["low"], (daily["high"] - pc).abs(), (daily["low"] - pc).abs()], axis=1).max(axis=1)
    daily["atr20"] = tr.rolling(20).mean()

    wk = pd.read_csv(DERIVED / "es_weekly_rth.csv", parse_dates=["week_monday", "first_day", "last_day"])
    cot = pd.read_csv(DERIVED / "cot_states.csv", parse_dates=["report_date", "apply_week_monday"])
    df = wk.merge(cot, left_on="week_monday", right_on="apply_week_monday", how="left")
    df = df[(df["week_monday"].dt.year >= START_YEAR) & df["full_week"]].copy()

    prev_idx = daily.index.searchsorted(df["week_monday"].values) - 1
    df["atr"] = daily["atr20"].values[prev_idx]
    df = df[df["atr"].notna() & df["lf_state_2080"].notna()]

    rth_dates = rth["date"].values
    weeks = []
    for _, r in df.iterrows():
        wm = r["week_monday"]
        lo, hi = rth_dates.searchsorted(np.datetime64(wm)), rth_dates.searchsorted(np.datetime64(wm + pd.Timedelta(days=5)))
        w = rth.iloc[lo:hi]
        if w.empty:
            continue
        o = float(w["open"].iloc[0]); a = float(r["atr"])
        up = ((w["high"].values - o) / a).clip(min=0)
        dn = ((o - w["low"].values) / a).clip(min=0)
        wu, wd = events(up, dn)
        mon = w[w["date"] == w["date"].iloc[0]]
        mu, md = events(((mon["high"].values - o) / a).clip(min=0), ((o - mon["low"].values) / a).clip(min=0))
        weeks.append({
            "wm": wm.strftime("%Y-%m-%d"),
            "s": {k: r[f"{g}_state_{t}"] for g in ("lf", "am") for t in ("2080", "1090") for k in [f"{g}{t}"]},
            "roll": bool(r["is_roll_week"]),
            "dly": bool(r["delayed_release"]),
            "atr": round(a, 2),
            "wo": o,
            "wc": round((float(w["close"].iloc[-1]) - o) / a, 3),
            "mc": round((float(mon["close"].iloc[-1]) - o) / a, 3),
            "wu": wu, "wd": wd, "mu": mu, "md": md,
            "nmin": int(len(w)),
        })

    payload = {"step": STEP, "weeks": weeks}
    (DERIVED / "path.json").write_text(json.dumps(payload, separators=(",", ":")))
    size = (DERIVED / "path.json").stat().st_size // 1024
    print(f"Недель: {len(weeks)}  → data/derived/path.json ({size} KB)")
    ev = np.mean([len(w["wu"]) + len(w["wd"]) for w in weeks])
    print(f"Событий на неделю в среднем: {ev:.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
