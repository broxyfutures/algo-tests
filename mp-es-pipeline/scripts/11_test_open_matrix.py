#!/usr/bin/env python3
"""
Тест 1: точка открытия × тип открытия → тип дня. Описательная статистика, без порогов.

Точка открытия: цена 09:30 против опоры (5 зон или 3 группы). Тип открытия: mp/opentype.py
(утверждено 22.09.2026). Исход: тип дня (mp/daytype.py); у направленных типов — по тренду точки
открытия или против (тренд: открытие выше VA → вверх, ниже VA → вниз, внутри VA → нет).

Выход: results.json в папке теста workspace (страница пересчитывает таблицы сама):
  {test, meta, zones, open_types, day_types, variants, rows}
  rows: [date, f0 zone, f0 open_type, f0 day_type, f0 day_dir, f1 …, a0 …, a1 …]
  варианты: f / a = fixed / adaptive, 0 / 1 = опора вчерашний день / композит

Исключены: укороченные дни, дни без опоры (первый день истории, дни после дыр в данных).

Запуск: python3 scripts/11_test_open_matrix.py   (после 05 и 07)
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp.codes import DAY_CODE, DAY_TYPES, DIR, OPEN_CODE, OPEN_TYPES, ZONE_CODE, ZONES  # noqa: E402

OUT = C.ROOT.parent / "workspace" / "Market Profile" / "Opening & Day Types" / "1 Точка открытия × тип открытия → тип дня"


def load(mode: str) -> pd.DataFrame:
    kw = dict(parse_dates=["date"], keep_default_na=False)
    d = pd.read_csv(C.DERIVED / f"mp_daily_{mode}.csv", parse_dates=["date"])[["date", "half_day"]]
    t = pd.read_csv(C.DERIVED / f"mp_daytype_{mode}.csv", **kw)[["date", "day_type", "day_dir"]]
    o = pd.read_csv(C.DERIVED / f"mp_open_{mode}.csv", **kw)
    return d.merge(t, on="date").merge(o, on="date")


def main() -> int:
    data = {m: load(m) for m in C.ROW_MODES}
    base = data["fixed"]
    keep = ~base["half_day"]
    for m in C.ROW_MODES:
        for ref in ("day", "comp"):
            keep &= (data[m][f"open_type_{ref}"] != "").to_numpy()
    idx = base.index[keep]
    variants = [("fixed", "day"), ("fixed", "comp"), ("adaptive", "day"), ("adaptive", "comp")]
    rows = []
    for i in idx:
        r = [base.at[i, "date"].strftime("%Y-%m-%d")]
        for mode, ref in variants:
            x = data[mode].loc[i]
            r += [ZONE_CODE[x[f"open_zone_{ref}"]], OPEN_CODE[x[f"open_type_{ref}"]], DAY_CODE[x["day_type"]], DIR[x["day_dir"]]]
        rows.append(r)
    res = {
        "test": "1", "zones": ZONES, "open_types": OPEN_TYPES, "day_types": DAY_TYPES,
        "variants": ["f0", "f1", "a0", "a1"], "rows": rows,
        "meta": {"built": date.today().isoformat(), "from": rows[0][0], "to": rows[-1][0], "days": len(rows),
                 "note": "Полные RTH-дни ES. Исключены укороченные дни и дни без опоры."},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "results.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{len(rows)} дней → {OUT / 'results.json'}")

    df = pd.DataFrame([r[:5] for r in rows], columns=["date", "z", "o", "t", "dir"])
    tab = pd.crosstab([df.z, df.o], df.t)
    tab["n"] = tab.sum(axis=1)
    pct = tab.drop(columns="n").div(tab["n"], axis=0).mul(100).round(1)
    pct["n"] = tab["n"]
    print("\n(fixed, опора вчера), % дней ячейки:")
    print(pct.reindex(columns=[c for c, _, _ in DAY_TYPES] + ["n"]).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
