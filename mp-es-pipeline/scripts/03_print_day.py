#!/usr/bin/env python3
"""
Шаг 3. ASCII TPO-профиль одного дня: сверка с графиком на своей платформе.

Запуск:
  python3 scripts/03_print_day.py 2026-09-15                   блок фиксированный (2 пт, как в терминале)
  python3 scripts/03_print_day.py 2026-09-15 --mode adaptive   блок по адаптивному правилу этой недели

Числа POC / VA / IB / хвосты берутся из mp_daily_<mode>.csv и посчитаны с тем же блоком,
который нарисован.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config as C  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("date")
    ap.add_argument("--mode", choices=C.ROW_MODES, default="fixed")
    a = ap.parse_args()

    day = pd.Timestamp(a.date)
    per = pd.read_parquet(C.DERIVED / "periods_30m.parquet")
    g = per[(per.date == day) & (per.session == "RTH")].sort_values("period")
    if g.empty:
        sys.exit(f"{a.date}: нет RTH-сессии (выходной, праздник или вне диапазона данных)")
    d = pd.read_csv(C.DERIVED / f"mp_daily_{a.mode}.csv", parse_dates=["date"]).set_index("date").loc[day]

    row = float(d.row)
    top = np.floor(g.high.max() / row) * row
    bot = np.floor(g.low.min() / row) * row
    n = int(round((top - bot) / row)) + 1
    print(f"\n{day.date()} {day.day_name()}   RTH {C.RTH_START}–{C.RTH_END} NY   блок {row:g} пт ({a.mode})\n")
    for i in range(n):
        p = top - i * row
        letters = "".join(
            L for L, lo, hi in zip(g.letter, g.low, g.high) if np.floor(lo / row) * row <= p <= np.floor(hi / row) * row
        )
        marks = []
        if np.floor(d.poc / row) * row == p:
            marks.append("POC")
        if np.floor(d.vah / row) * row - row == p:
            marks.append("VAH")
        if np.floor(d.val / row) * row == p:
            marks.append("VAL")
        if np.floor(d.ib_high / row) * row == p:
            marks.append("IBH")
        if np.floor(d.ib_low / row) * row == p:
            marks.append("IBL")
        in_va = d.val <= p < d.vah
        print(f"{p:10.2f} {'|' if in_va else ' '} {letters:<14} {' '.join(marks)}")

    def f(x):
        return "—" if pd.isna(x) or x == "" else x

    print(
        f"\nOpen {d.open}  High {d.high}  Low {d.low}  Close {d.close}   объём RTH {d.volume:,}".replace(",", " ")
        + f"\nPOC {d.poc}   VA {d.val} – {d.vah}   (объём: VPOC {d.vpoc}, VA {d.vval} – {d.vvah})"
        + f"\nIB {d.ib_low} – {d.ib_high} ({d.ib_range} пт)   выход вверх: {f(d.ext_up)}   вниз: {f(d.ext_down)}"
        + f"\nExcess сверху {d.tail_up_rows} бл., снизу {d.tail_down_rows} бл."
        + ("   (край сверху от последнего блока, не excess)" if d.unconfirmed_up else "")
        + ("   (край снизу от последнего блока, не excess)" if d.unconfirmed_down else "")
        + f"\nPoor high {d.poor_high}, poor low {d.poor_low}   single prints: выше POC {d.sp_above_poc} бл., ниже {d.sp_below_poc} бл."
        + f"\nНочь: {d.on_low} – {d.on_high}, ON POC {d.on_poc}, ON VPOC {d.on_vpoc}"
        + f"\nВчера: VA {d.prev_val} – {d.prev_vah}, POC {d.prev_poc}, диапазон {d.prev_low} – {d.prev_high}"
        + f"   открытие: {f(d.open_location)}"
    )
    flags = [k for k in ("roll_day", "expiring_contract", "half_day", "suspicious") if bool(d[k])]
    if flags:
        print("Флаги:", ", ".join(flags))
    return 0


if __name__ == "__main__":
    sys.exit(main())
