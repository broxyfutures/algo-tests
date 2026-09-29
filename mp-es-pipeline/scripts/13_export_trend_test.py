#!/usr/bin/env python3
"""
Шаг 13 (диагностика, вне цепочки тестов). Что будет с Trend, если закрытие мерить по блоку J.

Сценарий B: закрытие блока J (13:30–14:00) в крайних 25 % **итогового диапазона дня** вместо
закрытия блока M. Ничего в классификаторе не меняет и в статистику не входит: скрипт только читает
derived-файлы и выгружает список дней, которые были бы трендовыми при таком правиле.

Выход: workspace/assets/data/mp_trend_test.js — красный тумблер «тест» на странице графика.
Чтобы отменить эксперимент, достаточно удалить этот скрипт, файл данных и блок тумблера в
mp_chart.js: правила, config и результаты тестов эксперимент не трогает.

Запуск: python3 scripts/13_export_trend_test.py
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config as C  # noqa: E402

OUT = C.ROOT.parent / "workspace" / "assets" / "data" / "mp_trend_test.js"
CSV = C.ROOT / "data" / "derived" / "trend_test_J.csv"
J = 10  # закрытие меряем по 10-му блоку (J, 13:30–14:00)


def main() -> int:
    per = pd.read_parquet(C.DERIVED / "periods_30m.parquet")
    per = per[per.session == "RTH"].sort_values(["date", "period"])
    blocks = {d: (g.low.to_numpy(), g.high.to_numpy(), g.close.to_numpy()) for d, g in per.groupby("date")}

    kw = dict(parse_dates=["date"], keep_default_na=False)
    d = pd.read_csv(C.DERIVED / "mp_daytype_fixed.csv", **kw).drop(columns=["half_day"])
    day = pd.read_csv(C.DERIVED / "mp_daily_fixed.csv", parse_dates=["date"])[["date", "half_day", "open", "close"]]
    d = d.merge(day, on="date")
    d = d[~d.half_day].copy()
    d["re_up"] = d.re_up.astype(str) == "True"
    d["re_down"] = d.re_down.astype(str) == "True"
    d["dd"] = d.dd_split.astype(str) == "True"
    for c in ("tf_viol_up", "tf_viol_down"):
        d[c] = pd.to_numeric(d[c])

    rows = []
    for r in d.itertuples():
        if r.re_up == r.re_down or r.dd:
            continue
        up = r.re_up
        if (r.tf_viol_up if up else r.tf_viol_down) > C.TREND_MAX_VIOL:
            continue
        lo, hi, cl = blocks[r.date]
        if len(lo) < J:
            continue
        d_lo, d_hi = lo.min(), hi.max()
        pos = lambda c: (c - d_lo) / (d_hi - d_lo) if d_hi > d_lo else 0.5  # noqa: E731
        z = C.TREND_CLOSE_ZONE
        ok = lambda p: p >= 1 - z if up else p <= z  # noqa: E731
        p_j, p_m = pos(cl[J - 1]), pos(cl[-1])
        if not ok(p_j):
            continue                     # по новому правилу это не Trend
        rows.append({
            "date": r.date.date().isoformat(),
            "dir": "up" if up else "down",
            "range": round(float(d_hi - d_lo), 2),
            "close_j_pos": round(p_j if up else 1 - p_j, 3),
            "close_m_pos": round(p_m if up else 1 - p_m, 3),
            "trend_now": r.day_type == "trend",
        })

    t = pd.DataFrame(rows)
    CSV.parent.mkdir(parents=True, exist_ok=True)
    t.to_csv(CSV, index=False)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "built": date.today().isoformat(),
        "name": "Trend по новым критериям",
        "note": "закрытие блока J (14:00) в крайних 25 % диапазона дня вместо закрытия в 16:00",
        "days": t.date.tolist(),
    }
    OUT.write_text(
        "// Диагностическая выгрузка scripts/13_export_trend_test.py. В статистику не входит.\n"
        f"window.MPTREND_TEST={json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
        "window.dispatchEvent(new Event('mptrend-test'));\n", encoding="utf-8")

    now = int(t.trend_now.sum())
    print(f"дней по новому правилу: {len(t)} (вверх {int((t.dir == 'up').sum())} / вниз {int((t.dir == 'down').sum())})")
    print(f"   из них уже Trend сейчас: {now}, новых: {len(t) - now}")
    print(f"   медиана закрытия по тренду: к 14:00 {t.close_j_pos.median():.0%}, к 16:00 {t.close_m_pos.median():.0%}")
    print(f"   по годам: {t.date.str[:4].value_counts().sort_index().to_dict()}")
    print(f"\n{CSV}\n{OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
