#!/usr/bin/env python3
"""
Шаг 2. Дневные профили (RTH, блок 30 мин) в двух режимах размера блока.

Выход:
  data/derived/row_schedule.csv       размер блока по неделям: fixed_* и adaptive_* (день / неделя / месяц)
  data/derived/mp_daily_fixed.csv     одна строка на RTH-день, блок config.ROW_FIXED["day"]
  data/derived/mp_daily_adaptive.csv  то же, блок по адаптивному правилу (config, mp/rows.py)

Колонки (одинаковые в обоих файлах):
  сессия     date, weekday, contract, roll_day, expiring_contract, half_day, suspicious, n_periods, n_bars
  RTH        open, high, low, close, volume
  блок       row (высота строки, пт), n_rows
  TPO        poc (нижняя граница строки POC), vah / val (границы value area), tpo_count
  IB         ib_high, ib_low, ib_range, ext_up, ext_down (буква первого выхода за IB, пусто если не было)
  края       tail_up_rows, tail_down_rows (≥ TAIL_MIN_ROWS блоков с одной буквой, иначе 0),
             poor_high, poor_low (на крайней строке ≥ 2 буквы), sp_above_poc, sp_below_poc
  объём      vpoc, vvah, vval (приближённо: объём минуты поровну по её диапазону)
  ночь       on_high, on_low, on_poc, on_vpoc, on_volume, on_complete (18:00 накануне → 09:29)
  вчера      prev_high, prev_low, prev_close, prev_poc, prev_vah, prev_val, prev_ref_valid, prev_shift,
             open_location (above_range / above_value / in_value / below_value / below_range)

Не зависят от блока: сессия, RTH, IB, ночь high/low. Зависят: всё остальное.

Ночь на день ролла считается только по минуткам нового контракта (ролл ES.v.0 в 00:00 UTC),
on_complete=False. В день ролла вчерашние уровни (prev_*) сдвинуты на спред новый − старый контракт
в момент переключения (prev_shift), чтобы сравнивать сегодняшние цены со вчерашними в одном контракте.
Вчера = предыдущий RTH-день (праздничные сессии Globex не считаются днём). После дыры в данных
(config.DATA_HOLES) сравнение со вчера отключено: prev_ref_valid=False, after_data_hole=True.

expiring_contract=True: день в окне ролла CME (с четверга за 8 дней до третьей пятницы
мар/июн/сен/дек), когда ES.v.0 ещё не переключился. Объём уходящего контракта ниже нормы,
цена и TPO-форма те же (спред между контрактами за день почти не меняется). Дни остаются
в тестах, флаг нужен только для объёмных метрик.

Запуск: python3 scripts/02_build_profiles.py   (после 01)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp import profile as P  # noqa: E402
from mp.rows import schedule, week_monday  # noqa: E402
from mp.sessions import letter, load_minutes, tag  # noqa: E402


def slices(dates: np.ndarray):
    """Границы блоков одинаковых дат в отсортированном массиве."""
    cut = np.flatnonzero(dates[1:] != dates[:-1]) + 1
    starts = np.r_[0, cut]
    ends = np.r_[cut, len(dates)]
    return {pd.Timestamp(dates[s]): (s, e) for s, e in zip(starts, ends)}


def third_friday(y: int, mo: int) -> pd.Timestamp:
    first = pd.Timestamp(y, mo, 1)
    return first + pd.Timedelta(days=(4 - first.weekday()) % 7 + 14)


def expiring_flags(dates: pd.Series, roll_day: pd.Series) -> list[bool]:
    """True, если день в окне ролла и переключения на новый контракт ещё не было."""
    exp = sorted(third_friday(y, mo) for y in range(dates.min().year, dates.max().year + 2) for mo in (3, 6, 9, 12))
    rolls = set(dates[roll_day])
    out = []
    for d in dates:
        e = next(x for x in exp if x >= d)
        start = e - pd.Timedelta(days=8)
        switched = any(start <= r <= d for r in rolls)
        out.append(bool(start <= d and not switched))
    return out


def open_location(o, pv_lo, pv_hi, p_lo, p_hi):
    if o > p_hi:
        return "above_range"
    if o > pv_hi:
        return "above_value"
    if o < p_lo:
        return "below_range"
    if o < pv_lo:
        return "below_value"
    return "in_value"


def main() -> int:
    per_path = C.DERIVED / "periods_30m.parquet"
    if not per_path.exists():
        sys.exit("Нет periods_30m.parquet. Сначала: python3 scripts/01_build_periods.py")
    per = pd.read_parquet(per_path)

    m = tag(load_minutes())
    # спред в момент переключения ES.v.0: новый контракт → (первая цена нового − последняя старого)
    ctr_all = m["instrument_id"].to_numpy()
    sw = np.flatnonzero(ctr_all[1:] != ctr_all[:-1]) + 1
    spread_by_new = dict(zip(ctr_all[sw], m["open"].to_numpy()[sw] - m["close"].to_numpy()[sw - 1]))
    m = m[m["session"].isin(["RTH", "ETH"])]
    mins = {}
    for s in ("RTH", "ETH"):
        x = m[m.session == s].sort_values("date", kind="stable")
        mins[s] = {
            "date": x["date"].to_numpy(),
            "low": x["low"].to_numpy(),
            "high": x["high"].to_numpy(),
            "vol": x["volume"].to_numpy().astype(float),
            "ctr": x["instrument_id"].to_numpy(),
        }
        mins[s]["idx"] = slices(mins[s]["date"])

    rth = per[per.session == "RTH"].sort_values(["date", "period"])
    eth = per[per.session == "ETH"].sort_values(["date", "period"])
    eth_by = {d: g for d, g in eth.groupby("date")}
    rth_by = list(rth.groupby("date"))

    # размер блока по неделям
    hl = rth.groupby("date").agg(high=("high", "max"), low=("low", "min")).reset_index()
    sched = schedule(hl)
    sched.to_csv(C.DERIVED / "row_schedule.csv", index=False, date_format="%Y-%m-%d")
    row_by_week = {mode: dict(zip(sched["week_monday"], sched[f"{mode}_day"])) for mode in C.ROW_MODES}

    # часть, не зависящая от блока
    base = []
    for d, g in rth_by:
        lo, hi = g["low"].to_numpy(), g["high"].to_numpy()
        ctr = int(g["contract"].mode().iloc[0])
        n_bars = int(g["n_bars"].sum())
        r = {
            "date": d,
            "weekday": d.day_name(),
            "contract": ctr,
            "n_periods": len(g),
            "n_bars": n_bars,
            "half_day": len(g) < len(C.LETTERS),
            "open": g["open"].iloc[0],
            "high": hi.max(),
            "low": lo.min(),
            "close": g["close"].iloc[-1],
            "volume": int(g["volume"].sum()),
        }
        r["suspicious"] = (not r["half_day"]) and n_bars < C.FULL_DAY_BARS * 0.9
        ib = g.iloc[: C.IB_PERIODS]
        r["ib_high"], r["ib_low"] = ib["high"].max(), ib["low"].min()
        r["ib_range"] = r["ib_high"] - r["ib_low"]
        after = g.iloc[C.IB_PERIODS :]
        up = after[after["high"] > r["ib_high"]]
        dn = after[after["low"] < r["ib_low"]]
        r["ext_up"] = letter(int(up["period"].iloc[0])) if len(up) else ""
        r["ext_down"] = letter(int(dn["period"].iloc[0])) if len(dn) else ""
        r.update(on_high=np.nan, on_low=np.nan, on_volume=0, on_complete=False)
        E = mins["ETH"]
        if d in E["idx"]:
            s, e = E["idx"][d]
            same = E["ctr"][s:e] == ctr
            if same.any():
                r["on_high"] = E["high"][s:e][same].max()
                r["on_low"] = E["low"][s:e][same].min()
                r["on_volume"] = int(E["vol"][s:e][same].sum())
                r["on_complete"] = bool(same.all())
        base.append(r)
    base = pd.DataFrame(base)
    prev_ctr = base["contract"].shift(1)
    base["roll_day"] = (base["contract"] != prev_ctr) & prev_ctr.notna()
    base["expiring_contract"] = expiring_flags(base["date"], base["roll_day"])
    # после дыры в данных (config.DATA_HOLES) «вчера» — не предыдущий торговый день: сравнение отключено
    holes = pd.to_datetime(list(C.DATA_HOLES))
    prev_date = base["date"].shift(1)
    after_hole = [bool(((holes > p) & (holes < d)).any()) if pd.notna(p) else False for p, d in zip(prev_date, base["date"])]
    base["after_data_hole"] = after_hole
    base["prev_ref_valid"] = prev_ctr.notna() & ~base["after_data_hole"]
    base["prev_shift"] = [float(spread_by_new.get(c, 0.0)) if r else 0.0 for c, r in zip(base["contract"], base["roll_day"])]
    base["week_monday"] = week_monday(base["date"])

    for mode in C.ROW_MODES:
        rows = []
        for (d, g), b in zip(rth_by, base.itertuples(index=False)):
            row = row_by_week[mode][b.week_monday]
            r = P.tpo_stats(g["low"].to_numpy(), g["high"].to_numpy(), row)
            s, e = mins["RTH"]["idx"][d]
            M = mins["RTH"]
            r.update(P.volume_stats(M["low"][s:e], M["high"][s:e], M["vol"][s:e], row))
            r.update(on_poc=np.nan, on_vpoc=np.nan)
            E = mins["ETH"]
            if d in E["idx"] and d in eth_by:
                s, e = E["idx"][d]
                same = E["ctr"][s:e] == b.contract
                ge = eth_by[d]
                ge = ge[ge["contract"] == b.contract]
                if same.any() and len(ge):
                    r["on_poc"] = P.tpo_stats(ge["low"].to_numpy(), ge["high"].to_numpy(), row)["poc"]
                    r["on_vpoc"] = P.volume_stats(E["low"][s:e][same], E["high"][s:e][same], E["vol"][s:e][same], row)["vpoc"]
            rows.append(r)
        df = pd.concat([base.drop(columns="week_monday"), pd.DataFrame(rows)], axis=1)
        prev = df.shift(1)
        for k in ("high", "low", "close", "poc", "vah", "val"):
            df[f"prev_{k}"] = prev[k] + df["prev_shift"]
        df["open_location"] = [
            open_location(o, pl, ph, ql, qh) if ok else ""
            for o, pl, ph, ql, qh, ok in zip(df.open, df.prev_val, df.prev_vah, df.prev_low, df.prev_high, df.prev_ref_valid)
        ]
        out = C.DERIVED / f"mp_daily_{mode}.csv"
        df.to_csv(out, index=False, float_format="%.2f", date_format="%Y-%m-%d")

        print(f"\n[{mode}]  дней: {len(df)}  блок: {df.row.min():g}–{df.row.max():g} пт, рядов в дне (медиана): {df.n_rows.median():.0f}")
        bad_va = int(((df.vah < df.poc) | (df.poc < df.val)).sum())
        print(f"  нарушений VAL ≤ POC ≤ VAH: {bad_va}")
        print("  открытие относительно вчера:", df.loc[df.prev_ref_valid, "open_location"].value_counts().to_dict())
        print(f"  записано: {out.name}")

    print(f"\nУкороченных: {int(base.half_day.sum())}  подозрительных: {int(base.suspicious.sum())}  "
          f"роллов: {int(base.roll_day.sum())}  дней на уходящем контракте: {int(base.expiring_contract.sum())}")
    bad_ib = int(((base.ib_high > base.high) | (base.ib_low < base.low)).sum())
    print(f"IB вне диапазона дня: {bad_ib}   ночь неполная (день ролла): {int((~base.on_complete).sum())}")
    ch = sched.groupby(pd.to_datetime(sched.week_monday).dt.year)["adaptive_changed"].sum()
    print("Смен адаптивного блока по годам:", ch.astype(int).to_dict())
    print(f"Записано: row_schedule.csv ({len(sched)} недель)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
