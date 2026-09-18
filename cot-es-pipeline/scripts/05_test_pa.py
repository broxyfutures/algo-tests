#!/usr/bin/env python3
"""
Шаг 5. Тесты 1.1 и 1.2 (Price Action Based).

  1.1  Ход недели  (Close пт RTH / Open пн RTH − 1), в %
  1.2  Ход понедельника (Close пн RTH / Open пн RTH − 1), в %

Состояние: COT Index 52w по выбранной группе (по умолчанию Leveraged Funds),
Low / Mid / High для порогов 20/80 и 10/90. Применяется к неделе, начинающейся
в понедельник после пятничной публикации (apply_week_monday из cot_states.csv).

Бакеты: фиксированные границы в %, крайние бакеты открытые (любой ход попадает
в выборку). Неделя: < -2 / -2..-0.5 / ±0.5 / +0.5..+2 / > +2.
Понедельник: < -1 / -1..-0.3 / ±0.3 / +0.3..+1 / > +1.
Опция --quintiles: вместо фиксированных границ квинтили по всей выборке.

Исключения: недели до --from (2011), неполные недели (праздники, укороченные
дни), ролловые недели (третья пятница мар/июн/сен/дек и предшествующая),
отчёты, вышедшие с задержкой (шатдауны), недели без состояния (первые 52).

Запуск:
  python3 scripts/05_test_pa.py                # LF, с 2011
  python3 scripts/05_test_pa.py --group am     # Asset Managers
  python3 scripts/05_test_pa.py --from 2015 --keep-roll

Выход: data/derived/results_pa_<group>.md и таблицы в консоль.
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
STATES = ["Low", "Mid", "High"]
MIN_N = 30
MIN_LIFT_PP = 10.0


FIXED_EDGES = {
    "week_move_pct": [-2.0, -0.5, 0.5, 2.0],
    "mon_move_pct": [-1.0, -0.3, 0.3, 1.0],
}


def bucket_labels(edges: list[float]) -> list[str]:
    a, b, c, d = edges
    return [f"< {a:+g}%", f"{a:+g}…{b:+g}%", f"±{c:g}%", f"{c:+g}…{d:+g}%", f"> {d:+g}%"]


def quintile_table(
    df: pd.DataFrame, move_col: str, state_col: str, quintiles: bool = False
) -> tuple[pd.DataFrame, list[float]]:
    """3×5 таблица: % недель каждого состояния в каждом бакете + n + средний ход."""
    x = df[move_col]
    if quintiles:
        edges = list(np.quantile(x, [0, 0.2, 0.4, 0.6, 0.8, 1.0]))
        labels = ["Q1 (сильно вниз)", "Q2", "Q3 (около 0)", "Q4", "Q5 (сильно вверх)"]
    else:
        inner = FIXED_EDGES[move_col]
        edges = [-np.inf] + inner + [np.inf]
        labels = bucket_labels(inner)
    q = pd.cut(x, bins=edges, labels=labels, include_lowest=True)
    ct = pd.crosstab(df[state_col], q, normalize="index") * 100
    ct = ct.reindex(STATES).reindex(columns=labels)
    out = ct.round(1)
    out.insert(0, "n", df.groupby(state_col)[move_col].size().reindex(STATES).fillna(0).astype(int))
    out["mean %"] = df.groupby(state_col)[move_col].mean().reindex(STATES).round(2)
    out["median %"] = df.groupby(state_col)[move_col].median().reindex(STATES).round(2)
    out["P(up)"] = (df.groupby(state_col)[move_col].apply(lambda s: (s > 0).mean() * 100)).reindex(STATES).round(1)
    return out, edges


def diff_vs_mid(tbl: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in tbl.columns if c not in ("n", "mean %", "median %", "P(up)")]
    d = tbl.loc[["Low", "High"], cols] - tbl.loc["Mid", cols]
    return d.round(1)


def flag_hits(diff: pd.DataFrame, tbl: pd.DataFrame) -> list[str]:
    hits = []
    for st in ("Low", "High"):
        n = int(tbl.loc[st, "n"])
        for c in diff.columns:
            v = diff.loc[st, c]
            if pd.notna(v) and abs(v) >= MIN_LIFT_PP:
                ok = "n OK" if n >= MIN_N else f"n={n} < {MIN_N}, не засчитывается"
                hits.append(f"{st} · {c}: {v:+.1f} п.п. к Mid ({ok})")
    return hits


def md_table(tbl: pd.DataFrame) -> str:
    cols = list(tbl.columns)
    lines = ["| state | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    for st, row in tbl.iterrows():
        vals = []
        for c in cols:
            v = row[c]
            vals.append(f"{int(v)}" if c == "n" else ("" if pd.isna(v) else f"{v:.1f}"))
        lines.append(f"| {st} | " + " | ".join(vals) + " |")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--group", choices=["lf", "am"], default="lf")
    ap.add_argument("--from", dest="start_year", type=int, default=2011)
    ap.add_argument("--keep-roll", action="store_true", help="не исключать ролловые недели")
    ap.add_argument("--quintiles", action="store_true", help="квинтили вместо фиксированных границ")
    a = ap.parse_args()

    cot = pd.read_csv(DERIVED / "cot_states.csv", parse_dates=["report_date", "apply_week_monday"])
    wk = pd.read_csv(DERIVED / "es_weekly_rth.csv", parse_dates=["week_monday", "first_day", "last_day"])

    df = wk.merge(cot, left_on="week_monday", right_on="apply_week_monday", how="left")
    total = len(df)
    df = df[df["week_monday"].dt.year >= a.start_year]
    n_year = len(df)
    df = df[df["full_week"]]
    n_full = len(df)
    if not a.keep_roll:
        df = df[df["is_roll_week"] == False]  # noqa: E712
    n_roll = len(df)
    df = df[df["delayed_release"] == False]  # noqa: E712
    n_delay = len(df)
    state_2080 = f"{a.group}_state_2080"
    state_1090 = f"{a.group}_state_1090"
    df = df[df[state_2080].notna()].copy()
    n_state = len(df)
    df = df[df["week_move_pct"].notna() & df["mon_move_pct"].notna()]

    group_name = {"lf": "Leveraged Funds", "am": "Asset Managers"}[a.group]
    out = []
    out.append(f"# Тесты 1.1 / 1.2 — COT Index 52w, {group_name}, S&P 500 Consolidated\n")
    out.append("Воронка недель:\n")
    out.append(f"- всего недель в ценовом ряде: {total}")
    out.append(f"- с {a.start_year}: {n_year}")
    out.append(f"- полные недели (5 дней, без укороченных): {n_full}")
    out.append(f"- без ролловых недель: {n_roll}" + (" (ролловые оставлены)" if a.keep_roll else ""))
    out.append(f"- без отчётов с задержкой (шатдауны): {n_delay}")
    out.append(f"- с рассчитанным состоянием COT: {n_state}")
    out.append(f"- итого в тесте: {len(df)}\n")
    out.append(f"Критерии: n ≥ {MIN_N} в состоянии, |разница с Mid| ≥ {MIN_LIFT_PP} п.п. в бакете, тот же знак на 20/80 и 10/90.\n")
    if not a.quintiles:
        out.append("Бакеты фиксированные, крайние открытые: в выборку попадает любой ход.\n")

    tests = [
        ("1.1 Ход недели (Close пт / Open пн − 1), %", "week_move_pct"),
        ("1.2 Ход понедельника (Close пн / Open пн − 1), %", "mon_move_pct"),
    ]
    for title, col in tests:
        out.append(f"\n## {title}\n")
        for thr, scol in (("20/80", state_2080), ("10/90", state_1090)):
            tbl, edges = quintile_table(df, col, scol, a.quintiles)
            diff = diff_vs_mid(tbl)
            out.append(f"\n### Порог {thr}\n")
            kind = "Границы квинтилей" if a.quintiles else "Фиксированные границы"
            out.append(f"{kind} (%): " + " | ".join(f"{e:+.2f}" for e in edges if np.isfinite(e)) + "\n")
            out.append(md_table(tbl))
            out.append("\nРазница с Mid, п.п.:\n")
            out.append(md_table(diff.assign(n=tbl.loc[["Low", "High"], "n"])[["n"] + list(diff.columns)]))
            hits = flag_hits(diff, tbl)
            out.append("\nЯчейки с |разницей| ≥ 10 п.п.: " + ("; ".join(hits) if hits else "нет"))

    text = "\n".join(out)
    print(text)
    path = DERIVED / f"results_pa_{a.group}{'_quintiles' if a.quintiles else ''}.md"
    path.write_text(text)
    print(f"\nЗаписано: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
