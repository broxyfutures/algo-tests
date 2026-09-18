#!/usr/bin/env python3
"""
Шаг 1. Скачивает исторические файлы CFTC COT
       Traders in Financial Futures (TFF), Futures Only, формат txt (CSV),
       по одному zip на год, и распаковывает их в data/cot/.

Запуск:  python3 scripts/01_download_cot.py
         python3 scripts/01_download_cot.py --from 2006   # если нужна более ранняя история

Источник: https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalCompressed/index.htm
Блок «Traders in Financial Futures ; Futures Only Reports».
"""
import argparse
import io
import sys
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "cot"
URL = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"
ARCHIVE_URL = "https://www.cftc.gov/files/dea/history/fin_fut_txt_2006_2016.zip"
HEADERS = {"User-Agent": "Mozilla/5.0 (research script; COT download)"}


def _ssl_context():
    """Python с python.org на Маке часто не видит системные сертификаты.
    Берём корневые сертификаты из certifi, если он установлен."""
    import ssl

    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as r:
            return r.read()
    except Exception as e:  # noqa: BLE001
        # Запасной вариант: системный curl (у него свои сертификаты)
        import subprocess

        res = subprocess.run(["curl", "-sSL", "--fail", url], capture_output=True, timeout=180)
        if res.returncode != 0:
            raise RuntimeError(f"urllib: {e}; curl: {res.stderr.decode(errors='ignore').strip()}")
        return res.stdout


def download(year: int) -> Path | None:
    url = URL.format(year=year)
    try:
        blob = fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"  {year}: ОШИБКА скачивания {url}: {e}")
        return None
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        names = [n for n in z.namelist() if n.lower().endswith(".txt")]
        if not names:
            print(f"  {year}: в архиве нет .txt: {z.namelist()}")
            return None
        target = OUT / f"fin_fut_{year}.txt"
        target.write_bytes(z.read(names[0]))
    return target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", type=int, default=2010)
    ap.add_argument("--to", dest="end", type=int, default=date.today().year)
    ap.add_argument("--force", action="store_true", help="перекачать даже если файл есть")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    ok, failed = [], []

    # Архив 2006–2016 одним файлом: даёт историю Consolidated с июня 2006,
    # тогда как годовой файл 2010 начинается только с июля 2010.
    arch = OUT / "fin_fut_2006_2016.txt"
    if arch.exists() and not a.force:
        print(f"  архив 2006–2016: уже есть ({arch.stat().st_size // 1024} KB), пропуск")
    else:
        try:
            blob = fetch(ARCHIVE_URL)
            with zipfile.ZipFile(io.BytesIO(blob)) as z:
                name = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
                arch.write_bytes(z.read(name))
            print(f"  архив 2006–2016: OK  {arch.stat().st_size // 1024} KB")
        except Exception as e:  # noqa: BLE001
            print(f"  архив 2006–2016: ОШИБКА {e} (не критично, история начнётся с 2010)")
    for year in range(a.start, a.end + 1):
        target = OUT / f"fin_fut_{year}.txt"
        if target.exists() and not a.force and year != a.end:
            print(f"  {year}: уже есть ({target.stat().st_size // 1024} KB), пропуск")
            ok.append(year)
            continue
        p = download(year)
        if p is None:
            failed.append(year)
        else:
            print(f"  {year}: OK  {p.stat().st_size // 1024} KB")
            ok.append(year)

    print(f"\nГотово: {len(ok)} файлов в {OUT}")
    if failed:
        print(f"Не скачались: {failed}")
        print("Скачай их руками со страницы Historical Compressed и положи .txt в data/cot/")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
