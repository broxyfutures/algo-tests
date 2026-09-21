#!/usr/bin/env python3
"""
Тесты 1.1 и 1.2: зона открытия → тип дня / тип открытия. Описательная статистика, без порогов.

Зона открытия (относительно опоры): выше диапазона / выше VA в диапазоне / внутри VA /
ниже VA в диапазоне / ниже диапазона. Опора = вчерашний день (композит выкл) или композит (вкл).
Тренд открытия: открытие выше VA → вверх, ниже VA → вниз, внутри VA → нет.
Направленные типы (Trend, Double-Distribution, Normal Variation, Neutral-Extreme; Open-Drive,
Open-Test-Drive, Open-Rejection-Reverse) делятся на «по тренду открытия» и «против».

Выход: results.json в папках тестов workspace (страница пересчитывает таблицы сама):
  {test, meta, zones, types, variants, rows}
  rows: [date, f0 zone, f0 type, f0 dir, f1 …, a0 …, a1 …]
  варианты: f / a = fixed / adaptive, 0 / 1 = композит выкл / вкл

Исключены: укороченные дни, первый день истории и дни после дыр в данных (нет опоры), первые дни без R20.

Запуск: python3 scripts/11_test_zone_types.py   (после 07)
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config as C  # noqa: E402

WS = C.ROOT.parent / "workspace" / "Market Profile" / "Opening & Day Types"
OUT = {"1.1": WS / "1.1 Зона открытия → тип дня", "1.2": WS / "1.2 Зона открытия → тип открытия"}

ZONES = [
    ["ar", "выше диапазона"], ["av", "выше VA, в диапазоне"], ["iv", "внутри VA"],
    ["bv", "ниже VA, в диапазоне"], ["br", "ниже диапазона"],
]
ZONE_CODE = {"above_range": "ar", "above_value": "av", "in_value": "iv", "below_value": "bv", "below_range": "br"}
DAY_TYPES = [
    ["nm", "Normal", False], ["nt", "Nontrend", False], ["nv", "Normal Variation", True],
    ["tr", "Trend", True], ["dd", "Double-Distribution Trend", True],
    ["nc", "Neutral-Center", False], ["ne", "Neutral-Extreme", True],
]
DAY_CODE = {"normal": "nm", "nontrend": "nt", "normal_variation": "nv", "trend": "tr",
            "double_distribution_trend": "dd", "neutral_center": "nc", "neutral_extreme": "ne"}
OPEN_TYPES = [["od", "Open-Drive", True], ["otd", "Open-Test-Drive", True],
              ["orr", "Open-Rejection-Reverse", True], ["oa", "Open-Auction", False]]
OPEN_CODE = {"open_drive": "od", "open_test_drive": "otd", "open_rejection_reverse": "orr", "open_auction": "oa"}
DIR = {"up": "u", "down": "d", "": ""}


def load(mode: str) -> pd.DataFrame:
    kw = dict(parse_dates=["date"], keep_default_na=False)
    d = pd.read_csv(C.DERIVED / f"mp_daily_{mode}.csv", parse_dates=["date"])[["date", "half_day"]]
    t = pd.read_csv(C.DERIVED / f"mp_daytype_{mode}.csv", **kw)[["date", "r20", "day_type", "day_dir"]]
    o = pd.read_csv(C.DERIVED / f"mp_open_{mode}.csv", **kw).drop(columns=["open"])
    return d.merge(t, on="date").merge(o, on="date")


def main() -> int:
    data = {m: load(m) for m in C.ROW_MODES}
    base = data["fixed"]
    keep = (~base["half_day"]) & (base["r20"] != "") & (base["open_zone_day"] != "") & (base["open_type_day"] != "")
    for m in C.ROW_MODES:
        keep &= (data[m]["open_zone_comp"] != "").to_numpy()
    idx = base.index[keep]
    dates = base.loc[idx, "date"].dt.strftime("%Y-%m-%d").tolist()

    variants = [("f", "0", "fixed", "day"), ("f", "1", "fixed", "comp"), ("a", "0", "adaptive", "day"), ("a", "1", "adaptive", "comp")]
    rows11, rows12 = [], []
    for i, d in zip(idx, dates):
        r11, r12 = [d], [d]
        for _, _, mode, ref in variants:
            x = data[mode].loc[i]
            z = ZONE_CODE[x[f"open_zone_{ref}"]]
            r11 += [z, DAY_CODE[x["day_type"]], DIR[x["day_dir"]]]
            r12 += [z, OPEN_CODE[x[f"open_type_{ref}"]], DIR[x[f"open_dir_{ref}"]]]
        rows11.append(r11)
        rows12.append(r12)

    meta = {
        "built": date.today().isoformat(),
        "from": dates[0], "to": dates[-1], "days": len(dates),
        "note": "Полные RTH-дни ES, опора = вчерашний день или композит. Исключены укороченные дни и дни после дыр в данных.",
    }
    common = {"zones": ZONES, "variants": ["f0", "f1", "a0", "a1"], "meta": meta}
    res = {
        "1.1": {"test": "1.1", "outcome": "тип дня", "types": DAY_TYPES, "rows": rows11, **common},
        "1.2": {"test": "1.2", "outcome": "тип открытия", "types": OPEN_TYPES, "rows": rows12, **common},
    }
    for k, folder in OUT.items():
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "results.json").write_text(json.dumps(res[k], ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{k}: {len(res[k]['rows'])} дней → {folder / 'results.json'}")

    # сводка в консоль: fixed, композит выкл, вся история
    for k, types in (("1.1", DAY_TYPES), ("1.2", OPEN_TYPES)):
        df = pd.DataFrame([r[:4] for r in res[k]["rows"]], columns=["date", "z", "t", "dir"])
        tab = pd.crosstab(df["z"], df["t"], normalize="index").mul(100).round(1)
        tab = tab.reindex(index=[z for z, _ in ZONES], columns=[c for c, _, _ in types])
        tab.index = [n for _, n in ZONES]
        tab.columns = [n for _, n, _ in types]
        base_row = df["t"].value_counts(normalize=True).mul(100).round(1).reindex([c for c, _, _ in types])
        tab.loc["все дни"] = base_row.to_numpy()
        tab["n"] = list(df["z"].value_counts().reindex([z for z, _ in ZONES])) + [len(df)]
        print(f"\n{k} (fixed, композит выкл), % дней зоны:\n{tab.to_string()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
