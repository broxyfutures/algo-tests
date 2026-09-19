#!/usr/bin/env python3
"""
Шаг 5. Дневные композиты (тумблер COMPOSITE_MODES в тестах) в обоих режимах размера блока.

Выход: data/derived/mp_composite_{fixed,adaptive}.csv, одна строка на RTH-день.

Что произошло с днём:
  date, row, action           start (день начал новый композит) / added / skipped_shape
  start_reason                first / migration (VA не совпала) / roll (новый контракт)
  overlap                     доля VA дня внутри VA композита до этого дня
  poc_pos, bimodal, va_sym    форма пробного профиля (композит + день), если была проверка
Состояние композита после дня:
  comp_id, comp_start, comp_days, comp_high, comp_low, comp_poc, comp_vah, comp_val
Опора для этого дня (известна до открытия, без заглядывания вперёд):
  ref_source                  composite (открыт композит от 2 дней) / day (вчерашний профиль) /
                              older_day (композит из 1 дня, а следующие дни пропущены по форме) / none (ролл)
  ref_days, ref_high, ref_low, ref_poc, ref_vah, ref_val
  open_location_ref           открытие относительно опоры: above_range / above_value / in_value / below_value / below_range

Тумблер off = опора всегда вчерашний день (prev_* в mp_daily_*.csv).
Тумблер on  = ref_* отсюда: композит, если он открыт и в нём не меньше 2 дней, иначе вчерашний день.

Запуск: python3 scripts/05_build_day_composites.py   (после 01 и 02)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp import profile as P  # noqa: E402
from mp.composite import overlap_share, shape  # noqa: E402


def open_location(o, v_lo, v_hi, lo, hi):
    if o > hi:
        return "above_range"
    if o > v_hi:
        return "above_value"
    if o < lo:
        return "below_range"
    if o < v_lo:
        return "below_value"
    return "in_value"


def main() -> int:
    per = pd.read_parquet(C.DERIVED / "periods_30m.parquet")
    per = per[per.session == "RTH"].sort_values(["date", "period"])
    by_day = {d: (g["low"].to_numpy(), g["high"].to_numpy()) for d, g in per.groupby("date")}

    for mode in C.ROW_MODES:
        daily = pd.read_csv(C.DERIVED / f"mp_daily_{mode}.csv", parse_dates=["date"])
        rows = []
        comp_lo = comp_hi = None  # массивы блоков открытого композита
        comp_id, comp_start, comp_days = 0, None, 0
        state = None              # состояние композита после предыдущего дня
        prev_date = None
        for b in daily.itertuples(index=False):
            lo, hi = by_day[b.date]
            row = float(b.row)
            r = {"date": b.date.date(), "row": row}

            # опора на сегодня = состояние после вчера
            if state is None or b.roll_day:
                r.update(ref_source="none", ref_days=0)
            else:
                r.update({k: v for k, v in state.items() if k != "_start"})
                if state["ref_days"] >= 2:
                    r["ref_source"] = "composite"
                else:
                    r["ref_source"] = "day" if state["_start"] == prev_date else "older_day"
            if r["ref_source"] != "none":
                r["open_location_ref"] = open_location(b.open, r["ref_val"], r["ref_vah"], r["ref_low"], r["ref_high"])

            # что делаем с сегодняшним днём
            r.update(overlap=np.nan, poc_pos=np.nan, bimodal=None, va_sym=np.nan)
            if comp_lo is None or b.roll_day:
                action, reason = "start", "first" if comp_lo is None else "roll"
            else:
                cs = P.tpo_stats(comp_lo, comp_hi, row)
                ov = overlap_share(b.val, b.vah, cs["val"], cs["vah"])
                r["overlap"] = round(ov, 3)
                if ov > C.COMP_MIN_OVERLAP:
                    tl, th = np.r_[comp_lo, lo], np.r_[comp_hi, hi]
                    sh = shape(tl, th, row)
                    r.update(poc_pos=sh["poc_pos"], bimodal=sh["bimodal"], va_sym=sh["va_sym"])
                    action, reason = ("added", "") if sh["shape_ok"] else ("skipped_shape", "")
                else:
                    action, reason = "start", "migration"
            if action == "start":
                comp_id += 1
                comp_lo, comp_hi, comp_start, comp_days = lo.copy(), hi.copy(), b.date.date(), 1
            elif action == "added":
                comp_lo, comp_hi, comp_days = np.r_[comp_lo, lo], np.r_[comp_hi, hi], comp_days + 1
            r.update(action=action, start_reason=reason)

            cs = P.tpo_stats(comp_lo, comp_hi, row)
            after = {
                "comp_id": comp_id,
                "comp_start": comp_start,
                "comp_days": comp_days,
                "comp_high": float(comp_hi.max()),
                "comp_low": float(comp_lo.min()),
                "comp_poc": cs["poc"],
                "comp_vah": cs["vah"],
                "comp_val": cs["val"],
            }
            r.update(after)
            prev_date = b.date.date()
            state = {
                "_start": comp_start,
                "ref_days": comp_days,
                "ref_high": after["comp_high"],
                "ref_low": after["comp_low"],
                "ref_poc": after["comp_poc"],
                "ref_vah": after["comp_vah"],
                "ref_val": after["comp_val"],
            }
            rows.append(r)

        df = pd.DataFrame(rows)
        cols = ["date", "row", "action", "start_reason", "overlap", "poc_pos", "bimodal", "va_sym",
                "comp_id", "comp_start", "comp_days", "comp_high", "comp_low", "comp_poc", "comp_vah", "comp_val",
                "ref_source", "ref_days", "ref_high", "ref_low", "ref_poc", "ref_vah", "ref_val", "open_location_ref"]
        df = df[cols]
        out = C.DERIVED / f"mp_composite_{mode}.csv"
        df.to_csv(out, index=False, float_format="%.2f")

        lengths = df.groupby("comp_id")["comp_days"].max()
        print(f"\n[{mode}] композитов: {len(lengths)}, из них от 2 дней: {int((lengths >= 2).sum())}, "
              f"от 3 дней: {int((lengths >= 3).sum())}, самый длинный: {int(lengths.max())} дн.")
        print("  длина (дней → сколько композитов):", lengths.value_counts().sort_index().to_dict())
        print("  действия с днями:", df["action"].value_counts().to_dict())
        print("  почему начинался новый:", df.loc[df.action == "start", "start_reason"].value_counts().to_dict())
        sk = df[df.action == "skipped_shape"]
        print(f"  пропущено по форме: {len(sk)} (двойное распределение {int(sk.bimodal.sum())}, "
              f"POC не в центре {int(((sk.poc_pos < C.COMP_POC_POS[0]) | (sk.poc_pos > C.COMP_POC_POS[1])).sum())}, "
              f"VA несимметрична {int((sk.va_sym < C.COMP_VA_SYM).sum())})")
        print("  опора дня:", df["ref_source"].value_counts().to_dict())
        print(f"  записано: {out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
