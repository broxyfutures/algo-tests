#!/usr/bin/env python3
"""
Шаг 7. Тип открытия и зона открытия (правила в mp/opentype.py и PROFILE_RULES.md, раздел 7).
Переменные только три: точка открытия, VA опоры, IB. События отслеживаются весь RTH-день.

Выход: data/derived/mp_open_{fixed,adaptive}.csv, одна строка на RTH-день:
  date, open, ib_high, ib_low
  для опоры «вчерашний день» (суффикс _day) и «композит» (суффикс _comp, тумблер):
    open_type        open_drive / open_test_drive / open_rejection_reverse / open_auction (пусто: нет опоры)
    open_dir         up / down: куда в итоге пошла цена
    open_test_level  ближайшая граница VA в направлении первого хода (у OTD / ORR), если есть
    first_leg        длина первого хода от открытия в пунктах (у OTD / ORR)
    first_leg_ambiguous  в первую минуту цена ушла от открытия в обе стороны, первый ход взят по закрытию минуты
    open_zone        above_range / above_value / in_value / below_value / below_range
    open_accept      True: A и B торговались на общих уровнях внутри зоны открытия (принятие)

Open-Drive от опоры не зависит; Open-Test-Drive / Open-Rejection-Reverse различаются тестом границы
VA опоры, поэтому тип может отличаться между _day и _comp. От режима блока зависят VAH / VAL.

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
                   int((g["off"] < C.IB_PERIODS * C.PERIOD_MIN).sum()), g["open"].iloc[0])
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
            lo, hi, cl, n_ib, open_ = day_min[b.date]
            r = {"date": b.date.date(), "open": open_, "ib_high": hi[:n_ib].max(), "ib_low": lo[:n_ib].min()}
            refs = {
                "day": (b.prev_ref_valid, b.prev_vah, b.prev_val, b.prev_high, b.prev_low),
                "comp": (b.ref_source != "none", b.ref_vah, b.ref_val, b.ref_high, b.ref_low),
            }
            for sfx, (ok, vah, val, high, low) in refs.items():
                if not ok:
                    r.update({f"open_type_{sfx}": "", f"open_dir_{sfx}": "", f"open_test_level_{sfx}": np.nan,
                              f"first_leg_{sfx}": np.nan, f"first_leg_ambiguous_{sfx}": np.nan,
                              f"open_zone_{sfx}": "", f"open_accept_{sfx}": np.nan})
                    continue
                res = OT.classify(lo, hi, cl, open_, vah, val, n_ib)
                z, z_lo, z_hi = OT.zone(open_, val, vah, low, high)
                (a_lo, b_lo), (a_hi, b_hi) = ab[b.date]
                r.update({
                    f"open_type_{sfx}": res["open_type"],
                    f"open_dir_{sfx}": res["open_dir"],
                    f"open_test_level_{sfx}": res["open_test_level"],
                    f"first_leg_{sfx}": res["first_leg"],
                    f"first_leg_ambiguous_{sfx}": res["ambiguous"],
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
