"""
Профиль одной сессии: TPO-счёт и объём по строкам цены, POC, value area, хвосты, single prints.

Строка профиля высотой row пунктов. Индекс строки = floor(price / row), цена строки =
индекс × row (нижняя граница строки). Сетка привязана к нулю: при row = 2 строки 6030, 6032, …

TPO точный: блок (период) проходит все цены между своими low и high (минутки непрерывны),
поэтому отметка ставится в каждую строку от low до high блока.
Объём приближённый: объём минуты раскладывается поровну по строкам её диапазона.
"""
from dataclasses import dataclass

import numpy as np

import config as C


def row_of(price, row: float):
    return np.floor(np.asarray(price, dtype=float) / row + 1e-9).astype(np.int64)


@dataclass
class Profile:
    base: int            # индекс нижней строки
    counts: np.ndarray   # TPO или объём по строкам снизу вверх
    row: float

    def price(self, i: int) -> float:
        return (self.base + i) * self.row


def build(lows, highs, row: float, weights=None) -> Profile:
    """weights=None → TPO (по 1 на строку за блок); иначе объём, разложенный по строкам бара."""
    lo, hi = row_of(lows, row), row_of(highs, row)
    base = int(lo.min())
    n = int(hi.max()) - base + 1
    diff = np.zeros(n + 1)
    if weights is None:
        w = np.ones(len(lo))
    else:
        w = np.asarray(weights, dtype=float) / (hi - lo + 1)
    np.add.at(diff, lo - base, w)
    np.add.at(diff, hi - base + 1, -w)
    return Profile(base, np.cumsum(diff)[:n], row)


def poc_index(p: Profile) -> int:
    """Максимум; при равенстве ближайший к центру диапазона; дальше нижний."""
    c = p.counts
    cand = np.flatnonzero(np.isclose(c, c.max()))
    mid = (len(c) - 1) / 2
    return int(cand[np.argmin(np.abs(cand - mid))])


def value_area(p: Profile, poc: int) -> tuple[int, int]:
    """Классический CBOT: от POC сравниваются суммы двух строк сверху и двух снизу,
    добавляется большая пара; при равенстве обе. Возвращает индексы (low, high) строк VA."""
    c = p.counts
    n = len(c)
    target = C.VA_SHARE * c.sum()
    lo = hi = poc
    acc = c[poc]
    step = 2 if C.VA_METHOD == "two_row" else 1
    while acc < target - 1e-9 and (lo > 0 or hi < n - 1):
        up = c[hi + 1 : hi + 1 + step].sum() if hi < n - 1 else -1.0
        dn = c[max(lo - step, 0) : lo].sum() if lo > 0 else -1.0
        if up >= dn:
            acc += max(up, 0)
            hi = min(hi + step, n - 1)
        if dn >= up:
            acc += max(dn, 0)
            lo = max(lo - step, 0)
    return lo, hi


def edge_run(counts: np.ndarray, from_top: bool, stop=None) -> int:
    """Сколько строк подряд с одной отметкой от края профиля.
    stop: маска строк, на которых счёт обрывается (строки последнего блока)."""
    order = range(len(counts) - 1, -1, -1) if from_top else range(len(counts))
    k = 0
    for i in order:
        if counts[i] != 1 or (stop is not None and stop[i]):
            break
        k += 1
    return k


def single_runs(mask: np.ndarray, min_len: int) -> np.ndarray:
    """Маска строк, входящих в серии подряд идущих True длиной ≥ min_len."""
    out = np.zeros_like(mask)
    i, n = 0, len(mask)
    while i < n:
        if mask[i]:
            j = i
            while j < n and mask[j]:
                j += 1
            if j - i >= min_len:
                out[i:j] = True
            i = j
        else:
            i += 1
    return out


def tpo_stats(lows, highs, row: float) -> dict:
    """lows/highs по блокам сессии в хронологическом порядке (последний элемент = последний блок).

    VAH/VAL: границы value area (VAH = верх верхней строки), обрезанные по high / low сессии:
    строка шире тика, и без обрезки VAH могла оказаться выше реального хая.
    Excess (хвост): строки с одной отметкой подряд от края профиля, не меньше TAIL_MIN_ROWS.
      Строки, поставленные последним блоком, в excess не входят: цена не успела доказать
      отторжение (Dalton). Если одиночный край целиком от последнего блока, excess = 0,
      а флаг unconfirmed_up / unconfirmed_down = True.
    Single prints: строки с одной отметкой внутри профиля (не на краю), только серии
      не короче TAIL_MIN_ROWS.
    Poor high / low: на крайней строке не меньше 2 отметок.
    """
    p = build(lows, highs, row)
    c = p.counts
    n = len(c)
    poc = poc_index(p)
    va_lo, va_hi = value_area(p, poc)

    lo_r = row_of(lows, row) - p.base
    hi_r = row_of(highs, row) - p.base
    last = np.zeros(n, dtype=bool)
    last[lo_r[-1] : hi_r[-1] + 1] = True

    top_all, bot_all = edge_run(c, True), edge_run(c, False)
    top_ex, bot_ex = edge_run(c, True, last), edge_run(c, False, last)
    single = c == 1
    single[n - top_all :] = False
    single[:bot_all] = False
    sp = single_runs(single, C.TAIL_MIN_ROWS)
    return {
        "row": row,
        "n_rows": n,
        "poc": p.price(poc),
        # граница VA = край строки, но не дальше реально проторгованного диапазона
        "vah": min(p.price(va_hi) + row, float(np.max(highs))),
        "val": max(p.price(va_lo), float(np.min(lows))),
        "tpo_count": int(c.sum()),
        "tail_up_rows": top_ex if top_ex >= C.TAIL_MIN_ROWS else 0,
        "tail_down_rows": bot_ex if bot_ex >= C.TAIL_MIN_ROWS else 0,
        "unconfirmed_up": bool(top_all >= C.TAIL_MIN_ROWS and last[n - 1]),
        "unconfirmed_down": bool(bot_all >= C.TAIL_MIN_ROWS and last[0]),
        "poor_high": bool(c[-1] >= C.POOR_MIN_TPO),
        "poor_low": bool(c[0] >= C.POOR_MIN_TPO),
        "sp_above_poc": int(sp[poc + 1 :].sum()),
        "sp_below_poc": int(sp[:poc].sum()),
    }


def volume_stats(lows, highs, volumes, row: float) -> dict:
    """lows/highs/volumes по минуткам сессии."""
    p = build(lows, highs, row, volumes)
    poc = poc_index(p)
    va_lo, va_hi = value_area(p, poc)
    return {"vpoc": p.price(poc), "vvah": min(p.price(va_hi) + row, float(np.max(highs))),
            "vval": max(p.price(va_lo), float(np.min(lows)))}
