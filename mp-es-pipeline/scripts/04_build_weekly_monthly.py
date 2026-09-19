#!/usr/bin/env python3
"""
Шаг 4. Недельные и месячные профили в двух режимах размера блока.

Выход:
  data/derived/rolls.csv                   спред в момент каждого переключения ES.v.0 (новый − старый)
  data/derived/mp_weekly_{fixed,adaptive}.csv   одна строка на неделю
  data/derived/mp_monthly_{fixed,adaptive}.csv  одна строка на месяц

Что входит:
  - все торги Globex: ночь, RTH, 16:00–17:00, праздничные сессии. Неделя = с 18:00 воскресенья
    до 17:00 пятницы, месяц = все сутки Globex, чья торговая дата в этом месяце;
  - недельный блок TPO = 4 часа от 18:00 (18–22, 22–02, 02–06, 06–10, 10–14, 14–17);
  - месячный блок TPO = одни сутки Globex (18:00 → 17:00).

Ролл внутри недели / месяца: минутки уходящего контракта сдвигаются на спред в момент
переключения, чтобы весь профиль был в ценах последнего контракта (бэк-адъюст). Форма
профиля не меняется. prev_* (прошлая неделя / месяц) тоже приведены к ценам текущего контракта.

Колонки: key (понедельник недели / YYYY-MM), start, end (первая и последняя торговая дата),
n_days, n_blocks, contract, roll_inside, spread_applied, open, high, low, close, volume, row,
n_rows, poc, vah, val, tpo_count, tail_up_rows, tail_down_rows, poor_high, poor_low,
sp_above_poc, sp_below_poc, vpoc, vvah, vval, prev_high, prev_low, prev_close, prev_poc,
prev_vah, prev_val

Запуск: python3 scripts/04_build_weekly_monthly.py   (после 02: нужен row_schedule.csv)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp import profile as P  # noqa: E402
from mp.rows import month_rows  # noqa: E402
from mp.sessions import load_minutes, tag  # noqa: E402


def main() -> int:
    sched_path = C.DERIVED / "row_schedule.csv"
    if not sched_path.exists():
        sys.exit("Нет row_schedule.csv. Сначала: python3 scripts/02_build_profiles.py")
    sched = pd.read_csv(sched_path, parse_dates=["week_monday"])
    daily = pd.read_csv(C.DERIVED / "mp_daily_fixed.csv", usecols=["date"], parse_dates=["date"])

    m = tag(load_minutes())
    m = m[m["session"].isin(["RTH", "ETH", "POST", "HOL"])]

    # последовательность контрактов и спреды в момент переключения
    ctr = m["instrument_id"].to_numpy()
    sw = np.flatnonzero(ctr[1:] != ctr[:-1]) + 1
    spreads = m["open"].to_numpy()[sw] - m["close"].to_numpy()[sw - 1]
    rolls = pd.DataFrame({"switch_ny": m.index[sw].tz_localize(None), "old": ctr[sw - 1], "new": ctr[sw], "spread": spreads})
    rolls.to_csv(C.DERIVED / "rolls.csv", index=False)
    ci = np.zeros(len(m), dtype=np.int64)
    ci[sw] = 1
    ci = np.cumsum(ci)                       # номер контракта по порядку
    cum = np.r_[0.0, np.cumsum(spreads)]     # накопленный спред к контракту с номером k

    idx = m.index
    tod = (idx.hour * 60 + idx.minute).to_numpy()
    eth_s = int(C.ETH_START[:2]) * 60 + int(C.ETH_START[3:])
    since = np.where(tod >= eth_s, tod - eth_s, tod + 24 * 60 - eth_s)
    date = pd.DatetimeIndex(m["date"])
    base = pd.DataFrame(
        {
            "date": date,
            "ci": ci,
            "contract": ctr,
            "open": m["open"].to_numpy(),
            "high": m["high"].to_numpy(),
            "low": m["low"].to_numpy(),
            "close": m["close"].to_numpy(),
            "vol": m["volume"].to_numpy().astype(float),
            "wblock": since // C.WEEK_BLOCK_MIN,
        }
    )
    base["week"] = (date - pd.to_timedelta(date.weekday, unit="D")).normalize()
    base["month"] = date.to_period("M")

    wk_rows = {mode: dict(zip(sched["week_monday"], sched[f"{mode}_week"])) for mode in C.ROW_MODES}
    mo_rows = {"fixed": {}, "adaptive": month_rows(sched, daily["date"])}

    def row_for(kind, mode, key):
        if kind == "week":
            if key in wk_rows[mode]:
                return wk_rows[mode][key]
            prior = [k for k in wk_rows[mode] if k <= key]  # неделя без RTH-дней: берём предыдущую
            return wk_rows[mode][max(prior)] if prior else C.ROW_FIXED["week"]
        return C.ROW_FIXED["month"] if mode == "fixed" else mo_rows[mode].get(key, np.nan)

    for kind, key_col, block_cols in (("week", "week", ["date", "wblock"]), ("month", "month", ["date"])):
        groups = list(base.groupby(key_col, sort=True))
        for mode in C.ROW_MODES:
            out = []
            for key, g in groups:
                last = int(g["ci"].iloc[-1])
                adj = cum[last] - cum[g["ci"].to_numpy()]
                lo, hi = g["low"].to_numpy() + adj, g["high"].to_numpy() + adj
                blk = pd.DataFrame({"lo": lo, "hi": hi}).groupby([g[c].to_numpy() for c in block_cols]).agg(
                    lo=("lo", "min"), hi=("hi", "max")
                )
                row = row_for(kind, mode, key)
                r = {
                    "key": key.strftime("%Y-%m-%d") if kind == "week" else str(key),
                    "start": g["date"].iloc[0].date(),
                    "end": g["date"].iloc[-1].date(),
                    "n_days": g["date"].nunique(),
                    "n_blocks": len(blk),
                    "contract": int(g["contract"].iloc[-1]),
                    "roll_inside": bool(g["ci"].iloc[0] != last),
                    "spread_applied": float(cum[last] - cum[int(g["ci"].iloc[0])]),
                    "_ci": last,
                    "open": g["open"].iloc[0] + adj[0],
                    "high": hi.max(),
                    "low": lo.min(),
                    "close": g["close"].iloc[-1],
                    "volume": int(g["vol"].sum()),
                }
                r.update(P.tpo_stats(blk["lo"].to_numpy(), blk["hi"].to_numpy(), row))
                r.update(P.volume_stats(lo, hi, g["vol"].to_numpy(), row))
                out.append(r)
            df = pd.DataFrame(out)
            # прошлый период в ценах текущего контракта
            shift = cum[df["_ci"].to_numpy()] - cum[df["_ci"].shift(1).fillna(0).astype(int).to_numpy()]
            for k in ("high", "low", "close", "poc", "vah", "val"):
                df[f"prev_{k}"] = df[k].shift(1) + shift
            df = df.drop(columns="_ci")
            name = "weekly" if kind == "week" else "monthly"
            path = C.DERIVED / f"mp_{name}_{mode}.csv"
            df.to_csv(path, index=False, float_format="%.2f")
            bad = int(((df.vah < df.poc) | (df.poc < df.val)).sum())
            print(
                f"[{name} · {mode}] {len(df)} шт., блок {df.row.min():g}–{df.row.max():g} пт, "
                f"рядов (медиана) {df.n_rows.median():.0f}, блоков TPO (медиана) {df.n_blocks.median():.0f}, "
                f"с роллом внутри {int(df.roll_inside.sum())}, нарушений VA {bad} → {path.name}"
            )
    print(f"Роллов: {len(rolls)}, спред новый − старый: медиана {np.median(spreads):.2f}, "
          f"от {spreads.min():.2f} до {spreads.max():.2f} пт → rolls.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
