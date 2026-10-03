#!/usr/bin/env python3
"""
Шаг 8. Тест 3, «Какая граница протестирована первой?»: порядок по минуткам для дней, где обе
границы IB протестированы в одном 30-минутном блоке (по блокам порядок не виден, обычно это блок C).

Остальные дни считаются по блокам в шаге 11, минутки для них не нужны.

Минутки берутся из cot-es-pipeline/data/es (как в шаге 1). Если их нет, скрипт докачивает из Databento
только нужные блоки (около 55 дней по 30 минут, копейки): нужен ключ DATABENTO_API_KEY в окружении или
в cot-es-pipeline/.env и пакет databento (pip install databento).

Выход: data/derived/ib_first_minutes.csv  (date, block, first: u хай / d лоу / s в одной минуте)
Дальше: scripts/11_test_open_matrix.py подхватывает файл сам.

Запуск: python3 scripts/08_ib_first_minutes.py           # минутки локально или оценка стоимости докачки
        python3 scripts/08_ib_first_minutes.py --confirm # докачать из Databento (списывает деньги)
"""
import argparse
import glob
import importlib.util
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config as C  # noqa: E402

OUT = C.DERIVED / "ib_first_minutes.csv"


def same_block_days() -> pd.DataFrame:
    """Дни, где первые тесты хая и лоу IB попали в один блок: date, block, ibh, ibl."""
    spec = importlib.util.spec_from_file_location("s11", Path(__file__).with_name("11_test_open_matrix.py"))
    s11 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s11)
    x = s11.ib_tests()
    x = x[(x["code"] == "b") & (x["fu"] == x["fd"])]
    p = pd.read_parquet(C.DERIVED / "periods_30m.parquet", columns=["date", "session", "period", "high", "low"])
    r = p[(p["session"] == "RTH") & (p["period"] < C.IB_PERIODS)]
    ib = r.groupby("date").agg(ibh=("high", "max"), ibl=("low", "min"))
    ib.index = pd.to_datetime(ib.index)
    return x[["fu"]].rename(columns={"fu": "block"}).astype(int).join(ib)


def block_window(day: pd.Timestamp, block: int) -> tuple[pd.Timestamp, pd.Timestamp]:
    h, m = map(int, C.RTH_START.split(":"))
    s = (day + pd.Timedelta(hours=h, minutes=m + block * C.PERIOD_MIN)).tz_localize(C.TZ)
    return s, s + pd.Timedelta(minutes=C.PERIOD_MIN)


def local_minutes() -> pd.DataFrame | None:
    if not glob.glob(str(C.ES_DIR / "es_1m_*.parquet")):
        return None
    from mp.sessions import load_minutes
    return load_minutes()


def databento_minutes(days: pd.DataFrame, confirm: bool) -> pd.DataFrame:
    key = os.environ.get("DATABENTO_API_KEY", "").strip()
    env = C.ROOT.parent / "cot-es-pipeline" / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            if line.strip().startswith("DATABENTO_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key or key.startswith("db-xxxx"):
        sys.exit("Нет минуток и нет ключа DATABENTO_API_KEY: докачать нечем.")
    import databento as db
    cl = db.Historical(key)
    wins = [block_window(d, b) for d, b in days["block"].items()]
    kw = dict(dataset="GLBX.MDP3", symbols="ES.v.0", stype_in="continuous", schema="ohlcv-1m")
    if not confirm:
        cost = sum(cl.metadata.get_cost(start=s.tz_convert("UTC"), end=e.tz_convert("UTC"), **kw) for s, e in wins)
        sys.exit(f"Докачка {len(wins)} блоков стоит около ${cost:.4f}. Запусти с --confirm.")
    parts = [cl.timeseries.get_range(start=s.tz_convert("UTC"), end=e.tz_convert("UTC"), **kw).to_df() for s, e in wins]
    m = pd.concat(parts)
    m.index = pd.to_datetime(m.index, utc=True).tz_convert(C.TZ)
    return m[["open", "high", "low", "close"]]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="докачать недостающие минутки из Databento")
    a = ap.parse_args()
    days = same_block_days()
    print(f"Дней с тестом обеих границ в одном блоке: {len(days)}")
    m = local_minutes()
    if m is None:
        m = databento_minutes(days, a.confirm)
    rows = []
    for day, x in days.iterrows():
        blk = int(x["block"])
        s, e = block_window(day, blk)
        w = m[(m.index >= s) & (m.index < e)]
        if w.empty:
            print(f"  {day.date()}: нет минуток блока, пропущен")
            continue
        tu = w.index[w["high"] >= x["ibh"]]
        td = w.index[w["low"] <= x["ibl"]]
        if not len(tu) or not len(td):
            print(f"  {day.date()}: по минуткам тест одной из границ не найден, пропущен")
            continue
        first = "u" if tu[0] < td[0] else "d" if td[0] < tu[0] else "s"
        rows.append({"date": day.date().isoformat(), "block": C.LETTERS[blk], "first": first})
    out = pd.DataFrame(rows)
    out.to_csv(OUT, index=False)
    print(out["first"].value_counts().to_dict() if len(out) else "пусто", f"→ {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
