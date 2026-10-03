#!/usr/bin/env python3
"""
Тест 1: точка открытия × тип открытия → тип дня. Описательная статистика, без порогов.
Тест 2: точка открытия → тип открытия (TEST_PLAN, Opening Types & Day Types 2). Та же выборка и те же
варианты, в строках только зона и тип открытия.
Тест 3: точка и тип открытия → тест границ IB (TEST_PLAN, Strong Points 1, правила 03.10.2026).
Тест границы: в 10:30–16:00 цена дошла до хая IB или выше / до лоу IB или ниже, ровно уровень, без допуска.
Исход дня от размера блока не зависит: u только верх, d только низ, b обе, n ни одной.
При тесте обеих границ: какая первой (u хай, d лоу, s порядок неизвестен: одна минута, а без шага 08 один блок; на сайте такие дни в плитку не входят) и разрыв в
блоках между первым и вторым тестом (0 = один блок). Порядок внутри блока берётся из минуток
(data/derived/ib_first_minutes.csv, scripts/08_ib_first_minutes.py), если файл есть.

Точка открытия: цена 09:30 против опоры (5 зон или 3 группы). Тип открытия: mp/opentype.py
(утверждено 22.09.2026). Исход: тип дня (mp/daytype.py); у направленных типов — по тренду точки
открытия или против (тренд: открытие выше VA → вверх, ниже VA → вниз, внутри VA → нет).

Выход: results.json в папках тестов workspace (страница пересчитывает таблицы сама):
  {test, outcome, fields, meta, zones, open_types, day_types, variants, rows}
  тест 1: rows = [date, f0 zone, f0 open_type, f0 day_type, f0 day_dir, f1 …, a0 …, a1 …]
  тест 2: rows = [date, f0 zone, f0 open_type, f1 …, a0 …, a1 …]
  тест 3: rows = [date, f0 zone, f0 open_type, f0 open_dir, f1 …, a0 …, a1 …, ib, first, gap]
  тест 4: rows = [date, f0 zone, f0 open_type, f0 open_dir, f1 …, a0 …, a1 …, hb, lb]
          (first и gap заполнены только при ib = b, иначе "" и -1)
  варианты: f / a = fixed / adaptive, 0 / 1 = опора вчерашний день / композит

Исключены: укороченные дни, дни без опоры (первый день истории, дни после дыр в данных).

Запуск: python3 scripts/11_test_open_matrix.py   (после 05 и 07)
"""
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd  # noqa: E402

import config as C  # noqa: E402
from mp.codes import DAY_CODE, DAY_TYPES, DIR, OPEN_CODE, OPEN_TYPES, ZONE_CODE, ZONES  # noqa: E402

MP = C.ROOT.parent / "workspace" / "Market Profile"
OUT = MP / "Место и тип открытия → тип дня"
OUT2 = MP / "Место открытия → тип открытия"
OUT3 = MP / "Место и тип открытия → тест границ IB"
OUT4 = MP / "Место и тип открытия → время экстремумов дня"


def extremes() -> pd.DataFrame:
    """По дате: hb / lb — блок RTH (0 = A … 12 = M), где впервые достигнут хай / лоу дня (по ценам, первое касание)."""
    p = pd.read_parquet(C.DERIVED / "periods_30m.parquet", columns=["date", "session", "period", "high", "low"])
    r = p[(p["session"] == "RTH") & (p["period"] < len(C.LETTERS))]
    hi = r.pivot(index="date", columns="period", values="high")
    lo = r.pivot(index="date", columns="period", values="low")
    return pd.DataFrame({"hb": hi.fillna(-1e18).to_numpy().argmax(1), "lb": lo.fillna(1e18).to_numpy().argmin(1)},
                        index=pd.to_datetime(hi.index))


def ib_tests() -> pd.DataFrame:
    """По дате: code теста границ IB (u / d / b / n), first и gap при b.
    Блоки A + B = IB, блоки C…M (10:30–16:00) ищут тест: цена дошла до уровня или дальше."""
    p = pd.read_parquet(C.DERIVED / "periods_30m.parquet", columns=["date", "session", "period", "high", "low"])
    r = p[p["session"] == "RTH"]
    ib = r[r["period"] < C.IB_PERIODS].groupby("date").agg(ibh=("high", "max"), ibl=("low", "min"))
    later = r[r["period"] >= C.IB_PERIODS].join(ib, on="date")
    later["tu"] = later["high"] >= later["ibh"]
    later["td"] = later["low"] <= later["ibl"]
    fu = later[later["tu"]].groupby("date")["period"].min()     # первый блок теста хая
    fd = later[later["td"]].groupby("date")["period"].min()     # первый блок теста лоу
    x = pd.DataFrame(index=ib.index).join(fu.rename("fu")).join(fd.rename("fd"))
    up, dn = x["fu"].notna(), x["fd"].notna()
    x["code"] = "n"
    x.loc[up & ~dn, "code"], x.loc[dn & ~up, "code"], x.loc[up & dn, "code"] = "u", "d", "b"
    b = x["code"] == "b"
    x["first"] = ""
    x.loc[b & (x["fu"] < x["fd"]), "first"] = "u"
    x.loc[b & (x["fd"] < x["fu"]), "first"] = "d"
    x.loc[b & (x["fu"] == x["fd"]), "first"] = "s"
    x["gap"] = -1
    x.loc[b, "gap"] = (x.loc[b, "fu"] - x.loc[b, "fd"]).abs().astype(int)
    x.index = pd.to_datetime(x.index)
    mf = C.DERIVED / "ib_first_minutes.csv"                    # порядок внутри одного блока по минуткам
    if mf.exists():
        m = pd.read_csv(mf, parse_dates=["date"], keep_default_na=False).set_index("date")["first"]
        m = m[m.index.isin(x.index[x["first"] == "s"])]
        x.loc[m.index, "first"] = m
        print(f"Порядок по минуткам: {len(m)} дней с тестом обеих границ в одном блоке")
    return x


def load(mode: str) -> pd.DataFrame:
    kw = dict(parse_dates=["date"], keep_default_na=False)
    d = pd.read_csv(C.DERIVED / f"mp_daily_{mode}.csv", parse_dates=["date"])[["date", "half_day"]]
    t = pd.read_csv(C.DERIVED / f"mp_daytype_{mode}.csv", **kw)[["date", "day_type", "day_dir"]]
    o = pd.read_csv(C.DERIVED / f"mp_open_{mode}.csv", **kw)
    return d.merge(t, on="date").merge(o, on="date")


def main() -> int:
    data = {m: load(m) for m in C.ROW_MODES}
    base = data["fixed"]
    keep = ~base["half_day"]
    for m in C.ROW_MODES:
        for ref in ("day", "comp"):
            keep &= (data[m][f"open_type_{ref}"] != "").to_numpy()
    idx = base.index[keep]
    variants = [("fixed", "day"), ("fixed", "comp"), ("adaptive", "day"), ("adaptive", "comp")]
    rows = []
    for i in idx:
        r = [base.at[i, "date"].strftime("%Y-%m-%d")]
        for mode, ref in variants:
            x = data[mode].loc[i]
            r += [ZONE_CODE[x[f"open_zone_{ref}"]], OPEN_CODE[x[f"open_type_{ref}"]], DAY_CODE[x["day_type"]], DIR[x["day_dir"]]]
        rows.append(r)
    meta = {"built": date.today().isoformat(), "from": rows[0][0], "to": rows[-1][0], "days": len(rows),
            "note": "Полные RTH-дни ES. Исключены укороченные дни и дни без опоры."}
    common = {"zones": ZONES, "open_types": OPEN_TYPES, "day_types": DAY_TYPES, "variants": ["f0", "f1", "a0", "a1"], "meta": meta}
    rows2 = [[r[0]] + [v for k in range(4) for v in r[1 + 4 * k:3 + 4 * k]] for r in rows]
    ibc = ib_tests()
    rows3 = []
    for i, r in zip(idx, rows2):
        x = ibc.loc[pd.Timestamp(r[0])]
        # тест 3: к точке и типу открытия добавлено направление открытия (нужно для тренда при открытии внутри VA)
        r3 = [r[0]]
        for k, (mode, ref) in enumerate(variants):
            r3 += r[1 + 2 * k:3 + 2 * k] + [DIR[data[mode].at[i, f"open_dir_{ref}"]]]
        rows3.append(r3 + [x["code"], x["first"], int(x["gap"])])
    ext = extremes()
    rows4 = []
    for r in rows3:
        x = ext.loc[pd.Timestamp(r[0])]
        rows4.append(r[:-3] + [int(x["hb"]), int(x["lb"])])
    for out, res in ((OUT4, {"test": "4", "outcome": "ext", "fields": ["zone", "open", "odir"], **common, "rows": rows4}),
                     (OUT, {"test": "1", "outcome": "day", "fields": ["zone", "open", "day", "dir"], **common, "rows": rows}),
                     (OUT2, {"test": "2", "outcome": "open", "fields": ["zone", "open"], **common, "rows": rows2}),
                     (OUT3, {"test": "3", "outcome": "ib", "fields": ["zone", "open", "odir"], **common, "rows": rows3})):
        out.mkdir(parents=True, exist_ok=True)
        (out / "results.json").write_text(json.dumps(res, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{len(rows)} дней → {out / 'results.json'}")

    df = pd.DataFrame([r[:5] for r in rows], columns=["date", "z", "o", "t", "dir"])
    tab = pd.crosstab([df.z, df.o], df.t)
    tab["n"] = tab.sum(axis=1)
    pct = tab.drop(columns="n").div(tab["n"], axis=0).mul(100).round(1)
    pct["n"] = tab["n"]
    print("\n(fixed, опора вчера), % дней ячейки:")
    print(pct.reindex(columns=[c for c, _, _ in DAY_TYPES] + ["n"]).to_string())

    tab2 = pd.crosstab(df.z, df.o)
    pct2 = tab2.div(tab2.sum(axis=1), axis=0).mul(100).round(1)
    pct2["n"] = tab2.sum(axis=1)
    print("\nТест 2 (fixed, опора вчера), % дней зоны:")
    print(pct2.reindex(columns=[c for c, _ in OPEN_TYPES] + ["n"]).to_string())

    ib3 = pd.Series([r[-3] for r in rows3])
    f3 = pd.Series([r[-2] for r in rows3 if r[-3] == "b"])
    print("Тест 3, какая граница первой (дни с обеими), %:", f3.value_counts(normalize=True).mul(100).round(1).to_dict())
    print("\nТест 3, тест границ IB (все дни), %:", ib3.value_counts(normalize=True).mul(100).round(1).to_dict())
    return 0


if __name__ == "__main__":
    sys.exit(main())
