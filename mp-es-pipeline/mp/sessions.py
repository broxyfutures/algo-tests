"""
Минутки ES → разметка по торговым дням и сессиям.

Каждая минута получает:
  date     торговый день (дата RTH-сессии, к которой относится минута)
  session  RTH | ETH | POST | HOL
  period   номер 30-минутного периода внутри сессии (RTH 0…12 = A…M, ETH 0…30 от 18:00)

Правила:
  - Сессия Globex идёт 18:00 → 17:00 следующего дня. Минута в 18:00 и позже относится
    к следующей календарной дате, раньше 18:00 к своей. Воскресный вечер = понедельник.
  - Если в эту дату есть настоящая RTH-сессия: 09:30–16:00 это RTH, всё до 09:30 это ETH
    (ночь), 16:00–17:00 это POST (в профиль не входит).
  - Праздничная сессия Globex (NYSE закрыта, бары обрываются до 13:00, config.HOLIDAY_LAST_BAR)
    и дни вообще без RTH-баров (Страстная пятница): все минуты помечаются HOL и не используются.
    Ночь следующего дня начинается с 18:00 праздника.
"""
import glob
import sys

import numpy as np
import pandas as pd

import config as C


def load_minutes() -> pd.DataFrame:
    files = sorted(glob.glob(str(C.ES_DIR / "es_1m_*.parquet")))
    if not files:
        sys.exit(f"Нет минуток в {C.ES_DIR}. Они качаются COT-пайплайном: cot-es-pipeline/scripts/03_download_es.py")
    cols = ["instrument_id", "open", "high", "low", "close", "volume"]
    df = pd.concat([pd.read_parquet(f, columns=cols) for f in files])
    df = df[~df.index.duplicated(keep="last")].sort_index()
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    return df.tz_convert(C.TZ)


def _hhmm_to_min(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def tag(m: pd.DataFrame) -> pd.DataFrame:
    """Добавляет колонки date, session, period. Возвращает копию."""
    m = m.copy()
    idx = m.index
    tod = (idx.hour * 60 + idx.minute).to_numpy()
    cal = idx.normalize().tz_localize(None)
    rth_s, rth_e, eth_s = _hhmm_to_min(C.RTH_START), _hhmm_to_min(C.RTH_END), _hhmm_to_min(C.ETH_START)
    in_rth_window = (tod >= rth_s) & (tod < rth_e)

    # торговая дата Globex
    gdate = np.where(tod >= eth_s, cal + pd.Timedelta(days=1), cal)
    gdate = pd.DatetimeIndex(gdate)

    # настоящие RTH-дни: есть бары в окне RTH и последний бар не раньше порога праздничной сессии
    last_rth = pd.Series(tod[in_rth_window], index=cal[in_rth_window]).groupby(level=0).max()
    real = last_rth[last_rth >= _hhmm_to_min(C.HOLIDAY_LAST_BAR)].index
    is_real = gdate.isin(real)

    session = np.full(len(m), "HOL", dtype=object)
    session[is_real & in_rth_window] = "RTH"
    session[is_real & ((tod < rth_s) | (tod >= eth_s))] = "ETH"
    session[is_real & (tod >= rth_e) & (tod < eth_s)] = "POST"

    period = np.full(len(m), -1, dtype=np.int16)
    r = session == "RTH"
    period[r] = (tod[r] - rth_s) // C.PERIOD_MIN
    e = session == "ETH"
    since_eth = np.where(tod >= eth_s, tod - eth_s, tod + 24 * 60 - eth_s)
    period[e] = since_eth[e] // C.PERIOD_MIN

    m["date"] = gdate
    m["session"] = session
    m["period"] = period
    return m


def letter(period: int) -> str:
    return C.LETTERS[period] if 0 <= period < len(C.LETTERS) else "?"
