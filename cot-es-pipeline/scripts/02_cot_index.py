#!/usr/bin/env python3
"""
Шаг 2. Из txt-файлов CFTC (TFF, Futures Only) собирает по инструменту
       «S&P 500 Consolidated» чистые позиции, COT Index (окно 52 недели)
       и состояния Low / Mid / High для порогов 20/80 и 10/90.

Запуск:  python3 scripts/02_cot_index.py
         python3 scripts/02_cot_index.py --market "E-MINI S&P 500"   # другая строка
         python3 scripts/02_cot_index.py --window 26                 # другое окно

Выход:   data/derived/cot_states.csv  — одна строка на отчёт (срез вторника)
"""
import argparse
import glob
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COT_DIR = ROOT / "data" / "cot"
OUT = ROOT / "data" / "derived" / "cot_states.csv"

# Периоды, когда отчёты не публиковались (шатдауны правительства США).
# Отчёты со срезом внутри этих дат вышли позже, задним числом → в момент
# «применения» они ещё не были известны. Помечаем delayed_release=True.
# Проверь и дополни при необходимости.
SHUTDOWN_RANGES = [
    ("2013-10-01", "2013-10-17"),
    ("2018-12-22", "2019-01-25"),
    ("2025-10-01", "2025-11-12"),
]

COLS = {
    "Market_and_Exchange_Names": "market",
    # Имя колонки с датой в разных годах разное (Report_Date_as_MM_DD_YYYY /
    # Report_Date_as_YYYY-MM-DD), поэтому берём стабильную YYMMDD.
    "As_of_Date_In_Form_YYMMDD": "report_date",
    "Open_Interest_All": "oi",
    "Dealer_Positions_Long_All": "dealer_long",
    "Dealer_Positions_Short_All": "dealer_short",
    "Asset_Mgr_Positions_Long_All": "am_long",
    "Asset_Mgr_Positions_Short_All": "am_short",
    "Lev_Money_Positions_Long_All": "lf_long",
    "Lev_Money_Positions_Short_All": "lf_short",
    "Contract_Units": "contract_units",
}


def third_friday(year: int, month: int) -> date:
    d = date(year, month, 15)
    return d + timedelta(days=(4 - d.weekday()) % 7)


def roll_week_flags(mondays: pd.Series) -> pd.Series:
    """True, если неделя (по понедельнику) — неделя квартальной экспирации
    (третья пятница мар/июн/сен/дек) или предшествующая ей."""
    roll_mondays = set()
    for y in range(2000, 2040):
        for m in (3, 6, 9, 12):
            tf = third_friday(y, m)
            exp_monday = tf - timedelta(days=tf.weekday())
            roll_mondays.add(exp_monday)
            roll_mondays.add(exp_monday - timedelta(days=7))
    return mondays.dt.date.isin(roll_mondays)


def next_monday_after_publication(report_date: pd.Timestamp) -> pd.Timestamp:
    """Срез вторника T → публикация пятница T+3 → применение с понедельника T+6.
    Для нестандартных дней среза — ближайший понедельник строго после публикации."""
    publication = report_date + pd.Timedelta(days=3)
    days = (7 - publication.weekday()) % 7
    if days == 0:
        days = 7
    return publication + pd.Timedelta(days=days)


def cot_index(net: pd.Series, window: int) -> pd.Series:
    lo = net.rolling(window, min_periods=window).min()
    hi = net.rolling(window, min_periods=window).max()
    rng = hi - lo
    idx = (net - lo) / rng.replace(0, np.nan) * 100
    return idx


def state(idx: pd.Series, low: float, high: float) -> pd.Series:
    s = pd.Series(np.where(idx <= low, "Low", np.where(idx >= high, "High", "Mid")), index=idx.index, dtype="object")
    s[idx.isna()] = np.nan
    return s


def load_all() -> pd.DataFrame:
    files = sorted(glob.glob(str(COT_DIR / "*.txt")))
    if not files:
        sys.exit(f"Нет файлов в {COT_DIR}. Сначала: python3 scripts/01_download_cot.py")
    # Архив 2006–2016 читаем первым, годовые файлы — после: при совпадении
    # дат ниже drop_duplicates(keep="last") оставит строку из годового файла.
    files = sorted(files, key=lambda f: (0 if "2006_2016" in f else 1, f))
    frames = []
    for f in files:
        df = pd.read_csv(f, low_memory=False)
        df.columns = [c.strip() for c in df.columns]
        missing = [c for c in COLS if c not in df.columns]
        if missing:
            sys.exit(f"{f}: нет колонок {missing}. Колонки в файле: {list(df.columns)[:12]}…")
        frames.append(df[list(COLS)].rename(columns=COLS))
    df = pd.concat(frames, ignore_index=True)
    df["market"] = df["market"].str.strip()
    df["report_date"] = pd.to_datetime(df["report_date"].astype(str).str.strip().str.zfill(6), format="%y%m%d")
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--market", default="S&P 500 Consolidated", help="подстрока названия рынка")
    ap.add_argument("--window", type=int, default=52)
    a = ap.parse_args()

    df = load_all()

    # 1) Показать все строки, похожие на S&P 500, с покрытием по датам
    sp = df[df["market"].str.contains("S&P 500", case=False, regex=False)]
    cov = sp.groupby("market")["report_date"].agg(["min", "max", "count"]).sort_values("min")
    print("Строки S&P 500 в файлах TFF:")
    print(cov.to_string())
    print()

    # 2) Выбрать инструмент
    sel = df[df["market"].str.contains(a.market, case=False, regex=False)].copy()
    if sel.empty:
        sys.exit(f"Не нашёл рынок '{a.market}'")
    names = sel["market"].unique()
    if len(names) > 1:
        sys.exit(f"'{a.market}' совпадает с несколькими строками: {names}. Уточни --market.")
    sel = sel.drop_duplicates("report_date", keep="last").sort_values("report_date").reset_index(drop=True)
    print(f"Инструмент: {names[0]}")
    print(f"Отчётов: {len(sel)}  ({sel['report_date'].min().date()} → {sel['report_date'].max().date()})")

    # Единица измерения: у Consolidated до 2023-05-02 позиции приведены к
    # полноразмерному SP ($250 × индекс), после — к E-mini ES ($50 × индекс).
    # Приводим всё к ES-эквиваленту (×5 для строк в единицах $250), иначе
    # абсолютный Net прыгает в 5 раз и ломает индекс на 52 недели.
    sel["contract_units"] = sel["contract_units"].astype(str).str.strip()
    units = sel["contract_units"].unique()
    print(f"Contract_Units: {list(units)}")
    mult = sel["contract_units"].map(lambda u: 5.0 if "$250" in u else (1.0 if "$50" in u else np.nan))
    if mult.isna().any():
        sys.exit(f"Неизвестная единица контракта: {sel.loc[mult.isna(), 'contract_units'].unique()}")
    pos_cols = ["oi"] + [f"{g}_{s}" for g in ("dealer", "am", "lf") for s in ("long", "short")]
    for c in pos_cols:
        sel[c] = sel[c] * mult
    sel["units_multiplier"] = mult
    switches = sel.loc[mult != mult.shift(), ["report_date", "contract_units"]].iloc[1:]
    if not switches.empty:
        print("Смена единицы измерения (позиции до неё умножены на 5):")
        print(switches.to_string(index=False))

    # 3) Чистые позиции
    for g in ("dealer", "am", "lf"):
        sel[f"{g}_net"] = sel[f"{g}_long"] - sel[f"{g}_short"]
        sel[f"{g}_net_pct_oi"] = sel[f"{g}_net"] / sel["oi"] * 100

    # 4) Индекс Уильямса и состояния
    w = a.window
    for g in ("am", "lf"):
        sel[f"{g}_idx{w}"] = cot_index(sel[f"{g}_net"], w)
        sel[f"{g}_state_2080"] = state(sel[f"{g}_idx{w}"], 20, 80)
        sel[f"{g}_state_1090"] = state(sel[f"{g}_idx{w}"], 10, 90)

    # 5) Выравнивание по времени и флаги
    sel["snapshot_weekday"] = sel["report_date"].dt.day_name()
    sel["apply_week_monday"] = sel["report_date"].apply(next_monday_after_publication)
    sel["is_roll_week"] = roll_week_flags(sel["apply_week_monday"])
    sel["delayed_release"] = False
    for lo, hi in SHUTDOWN_RANGES:
        m = (sel["report_date"] >= lo) & (sel["report_date"] <= hi)
        sel.loc[m, "delayed_release"] = True

    # Пропуски между отчётами (> 7 дней)
    gaps = sel["report_date"].diff().dt.days
    big = sel.loc[gaps > 7, ["report_date"]].assign(gap_days=gaps[gaps > 7])
    if not big.empty:
        print("\nПропуски между отчётами (дней):")
        print(big.to_string(index=False))

    # 6) Сводка
    print(f"\nСрезы не во вторник: {(sel['snapshot_weekday'] != 'Tuesday').sum()}")
    print(f"Ролловых недель: {int(sel['is_roll_week'].sum())}")
    print(f"Отчётов, вышедших с задержкой (шатдауны): {int(sel['delayed_release'].sum())}")
    for g, label in (("lf", "Leveraged Funds"), ("am", "Asset Managers")):
        print(f"\n{label}, индекс {w}w:")
        for thr in ("2080", "1090"):
            vc = sel[f"{g}_state_{thr}"].value_counts(dropna=False)
            print(f"  {thr[:2]}/{thr[2:]}: " + ", ".join(f"{k}={v}" for k, v in vc.items()))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    cols = (
        ["report_date", "apply_week_monday", "snapshot_weekday", "is_roll_week", "delayed_release", "units_multiplier", "oi"]
        + [f"{g}_{x}" for g in ("dealer", "am", "lf") for x in ("long", "short", "net", "net_pct_oi")]
        + [f"{g}_{x}" for g in ("am", "lf") for x in (f"idx{w}", "state_2080", "state_1090")]
    )
    sel[cols].to_csv(OUT, index=False, date_format="%Y-%m-%d")
    print(f"\nЗаписано: {OUT}  ({len(sel)} строк)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
