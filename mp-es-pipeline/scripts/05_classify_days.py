#!/usr/bin/env python3
"""
Шаг 5. Тип дня по Mind Over Markets (правила в mp/daytype.py и PROFILE_RULES.md, раздел 6).

Выход: data/derived/mp_daytype_{fixed,adaptive}.csv, одна строка на RTH-день:
  date, r20 (медиана диапазона RTH за 20 прошлых дней), ib_width_r20, ib_narrow,
  ext_up_ib, ext_down_ib (выход за IB в долях IB), re_up, re_down (выход засчитан, > 20 % IB),
  max_tpo_row, thin_profile, tf_viol_up, tf_viol_down, close_pos (0 = low, 1 = high), open_is_extreme (low / high / ""),
  dd_split, day_type, day_dir

От размера блока зависят только max_tpo_row и dd_split (а значит Trend и Double-Distribution).

Запуск: python3 scripts/05_classify_days.py   (после 02)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp import daytype  # noqa: E402


def r20_series(daily: pd.DataFrame) -> pd.Series:
    rng = daily["high"] - daily["low"]
    return rng.shift(1).rolling(C.R20_DAYS, min_periods=5).median()


def main() -> int:
    per = pd.read_parquet(C.DERIVED / "periods_30m.parquet")
    per = per[per.session == "RTH"].sort_values(["date", "period"])
    by_day = {d: (g["low"].to_numpy(), g["high"].to_numpy()) for d, g in per.groupby("date")}

    for mode in C.ROW_MODES:
        daily = pd.read_csv(C.DERIVED / f"mp_daily_{mode}.csv", parse_dates=["date"])
        daily["r20"] = r20_series(daily)
        rows = []
        for b in daily.itertuples(index=False):
            lo, hi = by_day[b.date]
            r = {"date": b.date.date(), "half_day": b.half_day}
            r.update(daytype.classify(lo, hi, b.open, b.close, b.r20, float(b.row)))
            rows.append(r)
        df = pd.DataFrame(rows)
        out = C.DERIVED / f"mp_daytype_{mode}.csv"
        df.to_csv(out, index=False)
        full = df[~df.half_day]
        share = (full["day_type"].value_counts(normalize=True) * 100).round(1)
        print(f"\n[{mode}] типы дня, % полных дней:", share.to_dict())
        tr = full[full.day_type == "trend"]
        print(f"  trend вверх / вниз: {int((tr.day_dir == 'up').sum())} / {int((tr.day_dir == 'down').sum())}")
        print(f"  записано: {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
