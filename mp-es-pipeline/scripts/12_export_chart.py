#!/usr/bin/env python3
"""
Шаг 12. Данные для смотрелки профилей на сайте (окно над тестом и отдельная страница).

Выход: workspace/assets/data/mp_chart_data.js — один файл на обе страницы, ~2 МБ (0.5 МБ в gzip).
Подключается тегом <script defer>, поэтому работает и на Netlify, и локально по file://.

Формат (коды зон / типов — из mp/codes.py, те же, что в results.json теста 1):

  window.MPCHART = {built, from, to, dates:[...], zones, open_types, day_types,
                    modes: {f: {days, comps}, a: {days, comps}}}

  день = [ row, base, pr, poc, vah, val, ibh, ibl, open, high, low, close,
           dt, dd, z0, t0, z1, t1, ref0, ref1, cid, cact, cdays, flags ]
    pr    [lo0,hi0, lo1,hi1, ...] индексы строк блоков A…M относительно base;
          цена строки i = (base + i) * row — та же сетка, что в mp/profile.py
    dt    код типа дня, dd направление ('u' / 'd' / '')
    z0/t0 точка и тип открытия при опоре «вчерашний день», z1/t1 — при опоре «композит»
    ref0  [poc, vah, val, high, low] вчерашнего профиля (в день ролла уже со сдвигом),
    ref1  то же для опоры-композита (иначе вчерашний день), null если опоры нет
    cid   номер композита, cact 0 start / 1 added / 2 skipped_shape / 3 skipped_daytype,
          cdays длина композита после этого дня
    flags биты: 1 ролл · 2 уходящий контракт · 4 укороченный день · 8 день после дыры в данных ·
          16 день не входит в статистику теста 1
  comps[id] = {s: индекс первого дня, d: [индексы дней-участников], r, b, c: [TPO по строкам],
               poc, vah, val, hi, lo}   — только композиты от 2 дней

Запуск: python3 scripts/12_export_chart.py   (после 05, 06 и 07)
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp import profile as P  # noqa: E402
from mp.codes import COMP_ACTION, DAY_CODE, DAY_TYPES, DIR, OPEN_CODE, OPEN_TYPES, ZONE_CODE, ZONES  # noqa: E402

OUT = C.ROOT.parent / "workspace" / "assets" / "data" / "mp_chart_data.js"
MODE_KEY = {"fixed": "f", "adaptive": "a"}


def num(x):
    """NaN и пустая ячейка → None, иначе цена с двумя знаками (в JSON числа короче строк)."""
    if x is None or x == "" or (isinstance(x, float) and np.isnan(x)):
        return None
    return round(float(x), 2)


def levels(r, keys):
    """r — строка pandas или namedtuple из itertuples."""
    v = [num(r[k] if isinstance(r, pd.Series) else getattr(r, k)) for k in keys]
    return None if v[0] is None else v


def main() -> int:
    per = pd.read_parquet(C.DERIVED / "periods_30m.parquet")
    per = per[per.session == "RTH"].sort_values(["date", "period"])
    by_day = {d: (g["low"].to_numpy(), g["high"].to_numpy()) for d, g in per.groupby("date")}

    kw = dict(parse_dates=["date"], keep_default_na=False)
    daily = {m: pd.read_csv(C.DERIVED / f"mp_daily_{m}.csv", parse_dates=["date"]) for m in C.ROW_MODES}
    dtype = {m: pd.read_csv(C.DERIVED / f"mp_daytype_{m}.csv", **kw).set_index("date") for m in C.ROW_MODES}
    opens = {m: pd.read_csv(C.DERIVED / f"mp_open_{m}.csv", **kw).set_index("date") for m in C.ROW_MODES}
    comps = {m: pd.read_csv(C.DERIVED / f"mp_composite_{m}.csv", **kw).set_index("date") for m in C.ROW_MODES}
    cprof = {m: json.loads((C.DERIVED / f"mp_comp_profile_{m}.json").read_text()) for m in C.ROW_MODES}

    dates = [d.strftime("%Y-%m-%d") for d in daily["fixed"]["date"]]

    # день не входит в статистику теста 1: укороченный или без опоры хотя бы в одном варианте
    in_test = ~daily["fixed"]["half_day"].to_numpy()
    for m in C.ROW_MODES:
        for ref in ("day", "comp"):
            in_test &= (opens[m][f"open_type_{ref}"] != "").to_numpy()

    out = {}
    for mode in C.ROW_MODES:
        days, members = [], {}
        for i, b in enumerate(daily[mode].itertuples(index=False)):
            lo, hi = by_day[b.date]
            row = float(b.row)
            li, hj = P.row_of(lo, row), P.row_of(hi, row)
            base = int(li.min())
            pr = [int(x) for pair in zip(li - base, hj - base) for x in pair]

            t, o, c = dtype[mode].loc[b.date], opens[mode].loc[b.date], comps[mode].loc[b.date]
            # сверка с профилем из пайплайна: POC пересчитанного профиля должен совпасть
            pf = P.build(lo, hi, row)
            assert abs(pf.price(P.poc_index(pf)) - b.poc) < 1e-6, f"{b.date} {mode}: POC не сошёлся"

            flags = (1 * bool(b.roll_day) + 2 * bool(b.expiring_contract) + 4 * bool(b.half_day)
                     + 8 * bool(b.after_data_hole) + 16 * (not in_test[i]))
            days.append([
                row, base, pr,
                num(b.poc), num(b.vah), num(b.val), num(b.ib_high), num(b.ib_low),
                num(b.open), num(b.high), num(b.low), num(b.close),
                DAY_CODE[t.day_type], DIR[t.day_dir],
                ZONE_CODE[o.open_zone_day], OPEN_CODE[o.open_type_day],
                ZONE_CODE[o.open_zone_comp], OPEN_CODE[o.open_type_comp],
                levels(b, ["prev_poc", "prev_vah", "prev_val", "prev_high", "prev_low"]),
                levels(c, ["ref_poc", "ref_vah", "ref_val", "ref_high", "ref_low"]),
                int(c.comp_id), COMP_ACTION[c.action], int(c.comp_days), int(flags),
            ])
            if c.action in ("start", "added"):
                members.setdefault(int(c.comp_id), []).append(i)

        cc = {}
        for cid, p in cprof[mode].items():
            counts = np.array(p["c"], dtype=float)
            pf = P.Profile(p["b"], counts, p["r"])
            ip = P.poc_index(pf)
            vlo, vhi = P.value_area(pf, ip)
            mem = members[int(cid)]
            cc[cid] = {
                "s": mem[0], "d": mem, "r": p["r"], "b": p["b"], "c": p["c"],
                "poc": round(pf.price(ip), 2),
                "vah": round(min(pf.price(vhi) + p["r"], max(daily[mode].high.iloc[j] for j in mem)), 2),
                "val": round(max(pf.price(vlo), min(daily[mode].low.iloc[j] for j in mem)), 2),
                "hi": round(max(daily[mode].high.iloc[j] for j in mem), 2),
                "lo": round(min(daily[mode].low.iloc[j] for j in mem), 2),
            }
        out[MODE_KEY[mode]] = {"days": days, "comps": cc}
        print(f"[{mode}] дней {len(days)}, композитов от 2 дней {len(cc)}")

    data = {
        "built": date.today().isoformat(), "from": dates[0], "to": dates[-1],
        "dates": dates, "zones": ZONES, "open_types": OPEN_TYPES, "day_types": DAY_TYPES,
        "modes": out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(
        "// Данные смотрелки профилей. Собирается scripts/12_export_chart.py, руками не править.\n"
        f"window.MPCHART={body};\n"
        "window.dispatchEvent(new Event('mpchart-data'));\n", encoding="utf-8")
    print(f"{len(dates)} дней, {len(body) / 1e6:.2f} МБ → {OUT}")
    print(f"в статистике теста 1: {int(in_test.sum())} дней, вне статистики: {int((~in_test).sum())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
