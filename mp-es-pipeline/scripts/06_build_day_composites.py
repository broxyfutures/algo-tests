#!/usr/bin/env python3
"""
Шаг 6. Дневные композиты (тумблер COMPOSITE_MODES в тестах) в обоих режимах размера блока.

Выход: data/derived/mp_composite_{fixed,adaptive}.csv, одна строка на RTH-день.

Что произошло с днём:
  date, row, action           start (день начал новый композит) / added / skipped_shape /
                              skipped_daytype (Trend или Double-Distribution Trend, VA совпала)
  start_reason                first / migration (VA не совпала) / data_gap (день после дыры в данных)
В день ролла открытый композит сдвигается на спред новый − старый контракт (prev_shift) и живёт дальше.
  overlap                     доля VA дня внутри VA композита до этого дня
  poc_pos, bimodal, va_sym    форма пробного профиля (композит + день), если была проверка
Состояние композита после дня:
  comp_id, comp_start, comp_days, comp_high, comp_low, comp_poc, comp_vah, comp_val
Опора для этого дня (известна до открытия, без заглядывания вперёд):
  ref_source                  composite (открыт композит от 2 дней) / day (вчерашний профиль) /
                              none (первый день истории или день после дыры в данных)
  ref_days, ref_high, ref_low, ref_poc, ref_vah, ref_val
  open_location_ref           открытие относительно опоры: above_range / above_value / in_value / below_value / below_range

Рядом пишется mp_comp_profile_{mode}.json: состав каждого композита от 2 дней — дни-участники
и сдвиг их цен на роллы внутри композита. Из него график на сайте собирает склеенный профиль
с любой высотой строки.

Тумблер off = опора всегда вчерашний день (prev_* в mp_daily_*.csv).
Тумблер on  = ref_* отсюда: композит, если он открыт и в нём не меньше 2 дней, иначе вчерашний день.

Запуск: python3 scripts/06_build_day_composites.py   (после 02 и 05)
"""
import json
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
        dtype = pd.read_csv(C.DERIVED / f"mp_daytype_{mode}.csv", parse_dates=["date"])
        daily = daily.merge(dtype[["date", "day_type"]], on="date", how="left")
        rows = []
        comp_members = {}         # comp_id → [(дата, сдвиг на роллы)] участников (для графика)
        members = []              # участники открытого композита
        comp_lo = comp_hi = None  # массивы блоков открытого композита
        comp_id, comp_start, comp_days = 0, None, 0
        state = None              # состояние композита после предыдущего дня
        prev_date = None
        for b in daily.itertuples(index=False):
            lo, hi = by_day[b.date]
            row = float(b.row)
            r = {"date": b.date.date(), "row": row}

            # ролл: композит и опора переводятся в цены нового контракта
            if b.roll_day and comp_lo is not None:
                comp_lo, comp_hi = comp_lo + b.prev_shift, comp_hi + b.prev_shift
                members = [(d, sh + b.prev_shift) for d, sh in members]
                state = {k: (v + b.prev_shift if k.startswith("ref_") and k != "ref_days" else v) for k, v in state.items()}

            # опора на сегодня: открытый композит от 2 дней, иначе вчерашний профиль
            if state is None or not b.prev_ref_valid:
                r.update(ref_source="none", ref_days=0)
            elif state["ref_days"] >= 2:
                r.update({k: v for k, v in state.items() if k != "_start"})
                r["ref_source"] = "composite"
            else:
                r.update(ref_source="day", ref_days=1, ref_high=b.prev_high, ref_low=b.prev_low,
                         ref_poc=b.prev_poc, ref_vah=b.prev_vah, ref_val=b.prev_val)
            if r["ref_source"] != "none":
                r["open_location_ref"] = open_location(b.open, r["ref_val"], r["ref_vah"], r["ref_low"], r["ref_high"])

            # что делаем с сегодняшним днём
            r.update(overlap=np.nan, poc_pos=np.nan, bimodal=None, va_sym=np.nan)
            if comp_lo is None:
                action, reason = "start", "first"
            elif not b.prev_ref_valid:
                action, reason = "start", "data_gap"
            else:
                cs = P.tpo_stats(comp_lo, comp_hi, row)
                ov = overlap_share(b.val, b.vah, cs["val"], cs["vah"])
                r["overlap"] = round(ov, 3)
                if ov > C.COMP_MIN_OVERLAP and b.day_type in C.COMP_EXCLUDE_DAY_TYPES:
                    action, reason = "skipped_daytype", ""
                elif ov > C.COMP_MIN_OVERLAP:
                    tl, th = np.r_[comp_lo, lo], np.r_[comp_hi, hi]
                    sh = shape(tl, th, row)
                    r.update(poc_pos=sh["poc_pos"], bimodal=sh["bimodal"], va_sym=sh["va_sym"])
                    action, reason = ("added", "") if sh["shape_ok"] else ("skipped_shape", "")
                else:
                    action, reason = "start", "migration"
            if action == "start":
                comp_id += 1
                comp_lo, comp_hi, comp_start, comp_days = lo.copy(), hi.copy(), b.date.date(), 1
                members = [(b.date.date(), 0.0)]
            elif action == "added":
                comp_lo, comp_hi, comp_days = np.r_[comp_lo, lo], np.r_[comp_hi, hi], comp_days + 1
                members.append((b.date.date(), 0.0))
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
            comp_members[comp_id] = list(members)
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

        # состав композитов от 2 дней: дни-участники и сдвиг их цен на роллы внутри композита
        # (график собирает профиль композита сам, с любой высотой строки)
        final = df.groupby("comp_id")["comp_days"].max()
        prof = {}
        for cid, days in final.items():
            if days < 2:
                continue
            mem = comp_members[cid]
            prof[int(cid)] = {"d": [str(d) for d, _ in mem], "sh": [round(float(s), 2) for _, s in mem]}
        pout = C.DERIVED / f"mp_comp_profile_{mode}.json"
        pout.write_text(json.dumps(prof, separators=(",", ":")), encoding="utf-8")

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
        print(f"  записано: {out.name}, композитов от 2 дней в выгрузке для графика: {len(prof)} → {pout.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
