#!/usr/bin/env python3
"""
Шаг 3. Скачивает минутные бары ES из Databento.

  Датасет   GLBX.MDP3   (CME Globex)
  Символ    ES.v.0      (континуальный контракт, ролл по объёму)
  Схема     ohlcv-1m    (минутные бары; из них сами режем RTH 09:30–16:00 NY)
  Период    2010-06-06 → сегодня, по одному году за запрос

Запуск:
  python3 scripts/03_download_es.py            # только оценка стоимости, ничего не качает
  python3 scripts/03_download_es.py --confirm  # качает (списывает деньги со счёта Databento)

Ключ: файл .env в корне проекта со строкой DATABENTO_API_KEY=db-...
      (или переменная окружения с тем же именем).

Выход: data/es/es_1m_YYYY.parquet — по одному файлу на год. Уже скачанные годы пропускаются.
"""
import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "es"
DATASET = "GLBX.MDP3"
SYMBOL = "ES.v.0"
SCHEMA = "ohlcv-1m"
START = date(2010, 6, 6)


def load_key() -> str:
    key = os.environ.get("DATABENTO_API_KEY", "").strip()
    env = ROOT / ".env"
    if not key and env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            if line.startswith("DATABENTO_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
    if not key or key.startswith("db-xxxx"):
        sys.exit("Нет ключа. Скопируй .env.example в .env и вставь DATABENTO_API_KEY.")
    return key


def year_ranges(end: date):
    y = START.year
    while y <= end.year:
        s = max(START, date(y, 1, 1))
        e = min(end, date(y, 12, 31) + timedelta(days=1))
        if s < e:
            yield y, s, e
        y += 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--confirm", action="store_true", help="реально скачать (иначе только оценка стоимости)")
    ap.add_argument("--end", default=None, help="конечная дата YYYY-MM-DD (по умолчанию сегодня)")
    a = ap.parse_args()

    try:
        import databento as db
    except ImportError:
        sys.exit("pip3 install databento")

    client = db.Historical(load_key())
    end = date.fromisoformat(a.end) if a.end else date.today()

    avail = client.metadata.get_dataset_range(DATASET)
    print(f"Доступный диапазон {DATASET}: {avail}")

    OUT.mkdir(parents=True, exist_ok=True)
    todo = []
    for y, s, e in year_ranges(end):
        target = OUT / f"es_1m_{y}.parquet"
        if target.exists() and y != end.year:
            print(f"  {y}: уже есть, пропуск")
            continue
        todo.append((y, s, e, target))

    total = 0.0
    for y, s, e, _ in todo:
        cost = client.metadata.get_cost(
            dataset=DATASET, symbols=[SYMBOL], stype_in="continuous", schema=SCHEMA, start=s, end=e
        )
        total += cost
        print(f"  {y}: {s} → {e}  ≈ ${cost:.2f}")
    print(f"\nИтого к оплате ≈ ${total:.2f} за {len(todo)} лет")

    if not a.confirm:
        print("Это только оценка. Чтобы скачать: python3 scripts/03_download_es.py --confirm")
        return 0

    for y, s, e, target in todo:
        print(f"  {y}: скачиваю…", end=" ", flush=True)
        data = client.timeseries.get_range(
            dataset=DATASET, symbols=[SYMBOL], stype_in="continuous", schema=SCHEMA, start=s, end=e
        )
        df = data.to_df()
        df.to_parquet(target)
        print(f"{len(df)} баров → {target.name}")

    print("\nГотово. Дальше: python3 scripts/04_build_daily.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
