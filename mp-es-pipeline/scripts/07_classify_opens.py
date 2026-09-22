#!/usr/bin/env python3
"""
Шаг 7. Тип открытия и зона открытия (правила в mp/opentype.py и PROFILE_RULES.md, раздел 7).

Выход: data/derived/mp_open_{fixed,adaptive}.csv, одна строка на RTH-день:
  date, open, ib_high, ib_low
  для опоры «вчерашний день» (суффикс _day) и «композит» (суффикс _comp, тумблер):
    open_type    open_auction_in / open_drive / open_test_drive / open_rejection_reverse /
                 open_auction_out (пусто: нет опоры)
    open_dir     up / down (у Open-Auction пусто)
    trigger      что сделало день кандидатом в Open-Test-Drive: va / a_extreme / range;
                 a_blurred — за диапазоном экстремум A пробит без касания границы диапазона
    c1030        цена в 10:30 (закрытие блока B)
    ib_break     пробой IB по тренду в 10:30–11:30
    open_zone    above_range / above_value / in_value / below_value / below_range
    open_accept  True: A и B торговались на общих уровнях внутри зоны открытия (принятие)

Запуск: python3 scripts/07_classify_opens.py   (после 02 и 06)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp import opentype as OT  # noqa: E402
from mp.sessions import load_minutes, tag  # noqa: E402


def main() -> int:
    m = tag(load_minutes())
    m = m[m.session == "RTH"]
    off = (m.index.hour * 60 + m.index.minute - (9 * 60 + 30)).to_numpy()
    m = m.assign(off=off)
    day_min = {d: (g["low"].to_numpy(), g["high"].to_numpy(), g["close"].to_numpy(),
                   int((g["off"] < C.PERIOD_MIN).sum()), int((g["off"] < C.IB_PERIODS * C.PERIOD_MIN).sum()),
                   g["open"].iloc[0])
               for d, g in m.groupby("date")}
    per = pd.read_parquet(C.DERIVED / "periods_30m.parquet")
    per = per[(per.session == "RTH") & (per.period < C.IB_PERIODS)]
    ab = {d: (g["low"].to_numpy(), g["high"].to_numpy()) for d, g in per.groupby("date")}

    for mode in C.ROW_MODES:
        daily = pd.read_csv(C.DERIVED / f"mp_daily_{mode}.csv", parse_dates=["date"])
        comp = pd.read_csv(C.DERIVED / f"mp_composite_{mode}.csv", parse_dates=["date"])
        df = daily.merge(comp[["date", "ref_source", "ref_vah", "ref_val", "ref_high", "ref_low"]], on="date")
        rows = []
        for b in df.itertuples(index=False):
            lo, hi, cl, n_a, n_ib, open_ = day_min[b.date]
            r = {"date": b.date.date(), "open": open_, "ib_high": hi[:n_ib].max(), "ib_low": lo[:n_ib].min()}
            refs = {
                "day": (b.prev_ref_valid, b.prev_vah, b.prev_val, b.prev_high, b.prev_low),
                "comp": (b.ref_source != "none", b.ref_vah, b.ref_val, b.ref_high, b.ref_low),
            }
            for sfx, (ok, vah, val, high, low) in refs.items():
                if not ok:
                    r.update({f"open_type_{sfx}": "", f"open_dir_{sfx}": "", f"trigger_{sfx}": "",
                              f"c1030_{sfx}": np.nan, f"ib_break_{sfx}": np.nan,
                              f"open_zone_{sfx}": "", f"open_accept_{sfx}": np.nan})
                    continue
                res = OT.classify(lo, hi, cl, open_, vah, val, high, low, n_a, n_ib)
                z, z_lo, z_hi = OT.zone(open_, val, vah, low, high)
                (a_lo, b_lo), (a_hi, b_hi) = ab[b.date]
                r.update({
                    f"open_type_{sfx}": res["open_type"],
                    f"open_dir_{sfx}": res["open_dir"],
                    f"trigger_{sfx}": res["trigger"],
                    f"c1030_{sfx}": res["c1030"],
                    f"ib_break_{sfx}": res["ib_break"],
                    f"open_zone_{sfx}": z,
                    f"open_accept_{sfx}": OT.accepted(z_lo, z_hi, a_lo, a_hi, b_lo, b_hi),
                })
            rows.append(r)
        out_df = pd.DataFrame(rows)
        out = C.DERIVED / f"mp_open_{mode}.csv"
        out_df.to_csv(out, index=False, float_format="%.2f")
        full = out_df[~daily["half_day"].to_numpy()]
        for sfx in ("day", "comp"):
            x = full[full[f"open_type_{sfx}"] != ""]
            share = (x[f"open_type_{sfx}"].value_counts(normalize=True) * 100).round(1).to_dict()
            acc = (x[f"open_accept_{sfx}"].astype(bool).mean() * 100).round(1)
            print(f"[{mode} · опора {sfx}] типы открытия, % полных дней: {share}; принятие в зоне открытия: {acc} %")
        print(f"  записано: {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
