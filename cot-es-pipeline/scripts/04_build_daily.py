#!/usr/bin/env python3
"""
Шаг 4. Из минутных баров ES (data/es/*.parquet) собирает:
  - дневные RTH-бары (09:30–16:00 New York)      → data/derived/es_daily_rth.csv
  - недельные ходы (open понедельника → close пятницы) → data/derived/es_weekly_rth.csv

Запуск: python3 scripts/04_build_daily.py

Также умеет читать любой CSV с минутками, если Databento нет:
  python3 scripts/04_build_daily.py --csv path/to/minutes.csv
  (колонки: ts_event (UTC), open, high, low, close, volume)
"""
import argparse
import glob
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ES_DIR = ROOT / "data" / "es"
DERIVED = ROOT / "data" / "derived"
TZ = "America/New_York"
RTH_START = "09:30"
RTH_END = "16:00"  # не включая: последний бар 15:59 закрывается в 16:00
FULL_DAY_BARS = 390  # 6.5 часов × 60


def load_minutes(csv: str | None) -> pd.DataFrame:
    if csv:
        df = pd.read_csv(csv)
        df["ts_event"] = pd.to_datetime(df["ts_event"], utc=True)
        df = df.set_index("ts_event")
    else:
        files = sorted(glob.glob(str(ES_DIR / "es_1m_*.parquet")))
        if not files:
            sys.exit(f"Нет файлов в {ES_DIR}. Сначала: python3 scripts/03_download_es.py --confirm")
        df = pd.concat([pd.read_parquet(f) for f in files])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df[["open", "high", "low", "close", "volume"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()

    m = load_minutes(a.csv)
    print(f"Минуток: {len(m)}  ({m.index.min()} → {m.index.max()})")

    m = m.tz_convert(TZ)
    rth = m.between_time(RTH_START, RTH_END, inclusive="left").copy()
    rth["date"] = rth.index.date

    daily = rth.groupby("date").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        n_bars=("close", "size"),
    )
    last_bar = rth.groupby("date").apply(lambda g: g.index.max().strftime("%H:%M"))
    first_bar = rth.groupby("date").apply(lambda g: g.index.min().strftime("%H:%M"))
    daily["first_bar"] = first_bar
    daily["last_bar"] = last_bar
    daily.index = pd.to_datetime(daily.index)
    daily.index.name = "date"
    daily["weekday"] = daily.index.day_name()
    # Укороченный день: сессия закрылась раньше 16:00 (напр. 13:00 после Дня благодарения)
    daily["half_day"] = daily["last_bar"] < "15:55"
    # Подозрительно мало баров при нормальном закрытии — пропуски данных
    daily["suspicious"] = (~daily["half_day"]) & (daily["n_bars"] < FULL_DAY_BARS * 0.9)
    daily["move_pct"] = (daily["close"] / daily["open"] - 1) * 100

    DERIVED.mkdir(parents=True, exist_ok=True)
    daily.to_csv(DERIVED / "es_daily_rth.csv", float_format="%.4f")
    print(f"Дней RTH: {len(daily)}  укороченных: {int(daily.half_day.sum())}  подозрительных: {int(daily.suspicious.sum())}")
    if daily.suspicious.any():
        print(daily.loc[daily.suspicious, ["n_bars", "first_bar", "last_bar"]].head(20).to_string())

    # Недели
    d = daily.reset_index()
    d["week_monday"] = d["date"] - pd.to_timedelta(d["date"].dt.weekday, unit="D")
    g = d.groupby("week_monday")
    weekly = pd.DataFrame(
        {
            "first_day": g["date"].first(),
            "last_day": g["date"].last(),
            "n_days": g["date"].size(),
            "n_half_days": g["half_day"].sum(),
            "n_suspicious": g["suspicious"].sum(),
            "week_open": g["open"].first(),
            "week_close": g["close"].last(),
            "week_high": g["high"].max(),
            "week_low": g["low"].min(),
        }
    )
    weekly["week_move_pct"] = (weekly["week_close"] / weekly["week_open"] - 1) * 100
    weekly["full_week"] = (
        (weekly["n_days"] == 5)
        & (weekly["n_half_days"] == 0)
        & (weekly["n_suspicious"] == 0)
        & (weekly["first_day"].dt.weekday == 0)
        & (weekly["last_day"].dt.weekday == 4)
    )
    mon = d[d["date"].dt.weekday == 0].set_index("week_monday")
    weekly["mon_open"] = mon["open"]
    weekly["mon_close"] = mon["close"]
    weekly["mon_half_day"] = mon["half_day"]
    weekly["mon_move_pct"] = (weekly["mon_close"] / weekly["mon_open"] - 1) * 100
    weekly.index.name = "week_monday"
    weekly.to_csv(DERIVED / "es_weekly_rth.csv", float_format="%.4f")
    print(f"Недель: {len(weekly)}  полных (5 дней, без укороченных): {int(weekly.full_week.sum())}")
    print(f"Записано: {DERIVED / 'es_daily_rth.csv'}, {DERIVED / 'es_weekly_rth.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
