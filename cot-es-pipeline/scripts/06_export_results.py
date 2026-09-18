#!/usr/bin/env python3
"""
Шаг 6. Считает таблицы тестов 1.1 / 1.2 для всех комбинаций
(группа × порог × ролловые недели вкл/искл) и экспортирует их в workspace:

  ../workspace/COT Report/Price Action-Based/1.1 Ход недели/results.json
  ../workspace/COT Report/Price Action-Based/1.2 Ход понедельника/results.json

Нарратив тестов (идея, метод, вердикт, журнал) живёт в test.md рядом,
скрипт его не трогает. Страницы собирает workspace/build.py.

Запуск: python3 scripts/06_export_results.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
WS = ROOT.parent / "workspace" / "COT Report" / "Price Action-Based"
OUT = {
    "week": WS / "1.1 Ход недели" / "results.json",
    "mon": WS / "1.2 Ход понедельника" / "results.json",
}
STATES = ["Low", "Mid", "High"]
MIN_N = 30
MIN_LIFT = 10.0
START_YEAR = 2011

TESTS = {
    "week": {
        "col": "week_move_pct",
        "edges": [-2.0, -0.5, 0.5, 2.0],
        "labels": ["< −2%", "−2…−0.5%", "±0.5%", "+0.5…+2%", "> +2%"],
    },
    "mon": {
        "col": "mon_move_pct",
        "edges": [-1.0, -0.3, 0.3, 1.0],
        "labels": ["< −1%", "−1…−0.3%", "±0.3%", "+0.3…+1%", "> +1%"],
    },
}


def table(df: pd.DataFrame, col: str, state_col: str, edges: list[float], labels: list[str]) -> dict:
    bins = [-np.inf] + edges + [np.inf]
    q = pd.cut(df[col], bins=bins, labels=labels, include_lowest=True)
    ct = (pd.crosstab(df[state_col], q, normalize="index") * 100).reindex(STATES).reindex(columns=labels)
    g = df.groupby(state_col)[col]
    rows = {}
    for st in STATES:
        s = g.get_group(st) if st in g.groups else pd.Series(dtype=float)
        rows[st] = {
            "n": int(len(s)),
            "pct": [None if pd.isna(v) else round(float(v), 1) for v in ct.loc[st]],
            "mean": None if s.empty else round(float(s.mean()), 2),
            "median": None if s.empty else round(float(s.median()), 2),
            "pup": None if s.empty else round(float((s > 0).mean() * 100), 1),
        }
    diff = {}
    hits = []
    for st in ("Low", "High"):
        d = []
        for i, lab in enumerate(labels):
            a, b = rows[st]["pct"][i], rows["Mid"]["pct"][i]
            v = None if a is None or b is None else round(a - b, 1)
            d.append(v)
            if v is not None and abs(v) >= MIN_LIFT:
                hits.append({"state": st, "bucket": lab, "diff": v, "n_ok": rows[st]["n"] >= MIN_N})
        diff[st] = d
    return {"rows": rows, "diff": diff, "hits": hits}


def main() -> int:
    cot = pd.read_csv(DERIVED / "cot_states.csv", parse_dates=["report_date", "apply_week_monday"])
    wk = pd.read_csv(DERIVED / "es_weekly_rth.csv", parse_dates=["week_monday", "first_day", "last_day"])
    base = wk.merge(cot, left_on="week_monday", right_on="apply_week_monday", how="left")

    results = {}
    funnels = {}
    for group in ("lf", "am"):
        s2080, s1090 = f"{group}_state_2080", f"{group}_state_1090"
        for roll in ("excl", "incl"):
            df = base[base["week_monday"].dt.year >= START_YEAR]
            f = {"all": int(len(base)), "year": int(len(df))}
            df = df[df["full_week"]]
            f["full"] = int(len(df))
            if roll == "excl":
                df = df[df["is_roll_week"] == False]  # noqa: E712
            f["roll"] = int(len(df))
            df = df[df["delayed_release"] == False]  # noqa: E712
            f["delay"] = int(len(df))
            df = df[df[s2080].notna() & df["week_move_pct"].notna() & df["mon_move_pct"].notna()].copy()
            f["state"] = int(len(df))
            funnels[f"{group}_{roll}"] = f
            for thr, scol in (("2080", s2080), ("1090", s1090)):
                for tkey, t in TESTS.items():
                    results[f"{group}_{roll}_{thr}_{tkey}"] = table(df, t["col"], scol, t["edges"], t["labels"])
            # «Прошло» = та же ячейка ≥10 п.п. с тем же знаком на обоих порогах, n ≥ 30 на обоих
            for tkey in TESTS:
                a = results[f"{group}_{roll}_2080_{tkey}"]
                b = results[f"{group}_{roll}_1090_{tkey}"]
                passed = []
                for h in a["hits"]:
                    for k in b["hits"]:
                        if h["state"] == k["state"] and h["bucket"] == k["bucket"] and np.sign(h["diff"]) == np.sign(k["diff"]) and h["n_ok"] and k["n_ok"]:
                            passed.append({"state": h["state"], "bucket": h["bucket"], "d2080": h["diff"], "d1090": k["diff"]})
                results[f"{group}_{roll}_{tkey}_passed"] = passed

    daily = pd.read_csv(DERIVED / "es_daily_rth.csv", parse_dates=["date"])
    meta = {
        "built": date.today().isoformat(),
        "cot_reports": int(len(cot)),
        "cot_from": cot["report_date"].min().date().isoformat(),
        "cot_to": cot["report_date"].max().date().isoformat(),
        "es_from": daily["date"].min().date().isoformat(),
        "es_to": daily["date"].max().date().isoformat(),
        "es_days": int(len(daily)),
        "es_weeks": int(len(wk)),
        "roll_weeks": int(cot["is_roll_week"].sum()),
        "delayed": int(cot["delayed_release"].sum()),
        "state_counts": {
            f"{g}_{thr}": {k: int(v) for k, v in cot[f"{g}_state_{thr}"].value_counts().items()}
            for g in ("lf", "am") for thr in ("2080", "1090")
        },
        "tests": TESTS,
        "min_n": MIN_N,
        "min_lift": MIN_LIFT,
    }

    for tkey, out in OUT.items():
        payload = {
            "test": tkey,
            "meta": meta,
            "funnels": funnels,
            "results": {k: v for k, v in results.items() if k.endswith(f"_{tkey}") or k.endswith(f"_{tkey}_passed")},
        }
        out.parent.mkdir(parents=True, exist_ok=True)
        if not (out.parent / "test.md").exists():
            print(f"Внимание: в {out.parent} нет test.md, страница не соберётся без него")
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        out.write_text(text, encoding="utf-8")
        print(f"Записано: {out}  ({len(text) // 1024} KB)")

    for g in ("lf", "am"):
        for t in TESTS:
            print(f"  {g} {t} прошло: {results[f'{g}_excl_{t}_passed']}")
    print(f"\nТеперь: python3 \"{ROOT.parent / 'workspace' / 'build.py'}\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
