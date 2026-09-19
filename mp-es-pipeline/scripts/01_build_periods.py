#!/usr/bin/env python3
"""
Шаг 1. Минутки ES → 30-минутные периоды (буквы профиля) для RTH и ночной сессии.

Выход: data/derived/periods_30m.parquet, одна строка на период:
  date, session (RTH/ETH), period, letter, start, open, high, low, close, volume, n_bars, contract

Запуск: python3 scripts/01_build_periods.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config as C  # noqa: E402
from mp.sessions import letter, load_minutes, tag  # noqa: E402


def main() -> int:
    m = load_minutes()
    print(f"Минуток: {len(m)}  ({m.index.min()} → {m.index.max()})")
    m = tag(m)
    print("Минуты по сессиям:", m["session"].value_counts().to_dict())

    w = m[m["session"].isin(["RTH", "ETH"])].copy()
    w["start"] = w.index.tz_localize(None)
    g = w.groupby(["date", "session", "period"], sort=True)
    per = g.agg(
        start=("start", "first"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        n_bars=("close", "size"),
        contract=("instrument_id", "first"),
        n_contracts=("instrument_id", "nunique"),
    ).reset_index()
    per["start"] = per["start"].dt.floor(f"{C.PERIOD_MIN}min")
    per["letter"] = [letter(p) if s == "RTH" else "" for s, p in zip(per["session"], per["period"])]
    if (per["n_contracts"] > 1).any():
        print(f"ВНИМАНИЕ: периодов со сменой контракта внутри: {int((per.n_contracts > 1).sum())}")
    per = per.drop(columns="n_contracts")

    C.DERIVED.mkdir(parents=True, exist_ok=True)
    out = C.DERIVED / "periods_30m.parquet"
    per.to_parquet(out, index=False)

    rth = per[per.session == "RTH"]
    n_per = rth.groupby("date").size()
    hol_days = m.loc[(m.session == "HOL") & (m.index.hour == 10), "date"].nunique()
    print(f"RTH-дней: {n_per.size}  ({n_per.index.min().date()} → {n_per.index.max().date()})")
    print("Периодов в RTH-дне:", n_per.value_counts().sort_index().to_dict())
    print(f"Праздничных сессий Globex (исключены): {hol_days}")
    print(f"Записано: {out}  ({len(per)} периодов)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
