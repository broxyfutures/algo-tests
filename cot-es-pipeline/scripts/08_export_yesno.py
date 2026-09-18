#!/usr/bin/env python3
"""
Шаг 8. Данные для теста «Границы индекса» (один вопрос, да / нет):
если индекс у нижней границы (Low), закрылось ли следующее окно выше открытия?
если у верхней (High), закрылось ли ниже? Контртренд и моментум, группы
LF / AM / LF+AM, окна индекса 13 / 26 / 52, пороги 20/80, 10/90, 5/95,
переменные Net и ΔNet. Всё переключается на странице.

Экспорт: ../workspace/COT Report/Price Action-Based/Границы индекса/results.json
Страницу собирает workspace/build.py (renderer cot_yesno).

Запуск: python3 scripts/08_export_yesno.py
"""
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DERIVED = ROOT / "data" / "derived"
OUT = ROOT.parent / "workspace" / "COT Report" / "Price Action-Based" / "Границы индекса" / "results.json"
WINDOWS = (13, 26, 52)
THRESHOLDS = {"2080": (20, 80), "1090": (10, 90), "0595": (5, 95)}
CODE = {"Low": "L", "Mid": "M", "High": "H"}


def main() -> int:
    P = json.load(open(DERIVED / "path.json"))["weeks"]
    cot = pd.read_csv(DERIVED / "cot_states.csv", parse_dates=["report_date", "apply_week_monday"]).sort_values("report_date")
    states = {}
    for g in ("lf", "am"):
        for var, net in (("", cot[f"{g}_net"]), ("d", cot[f"{g}_net"].diff(1))):
            for win in WINDOWS:
                lo, hi = net.rolling(win, min_periods=win).min(), net.rolling(win, min_periods=win).max()
                idx = (net - lo) / (hi - lo).replace(0, np.nan) * 100
                for thr, (a, b) in THRESHOLDS.items():
                    st = np.where(idx <= a, "Low", np.where(idx >= b, "High", "Mid"))
                    st = pd.Series(st, index=cot.index, dtype="object").where(idx.notna(), None)
                    states[f"{var}{g}{win}_{thr}"] = dict(zip(cot["apply_week_monday"].dt.strftime("%Y-%m-%d"), st))
    rows = []
    for w in P:
        if w["dly"]:
            continue
        r = {"wm": w["wm"], "roll": w["roll"], "wc": w["wc"], "mc": w["mc"]}
        for k, m in states.items():
            v = m.get(w["wm"])
            if v is not None:
                r[k] = CODE[v]
        rows.append(r)

    payload = {
        "meta": {
            "built": date.today().isoformat(),
            "weeks": len(rows),
            "windows": list(WINDOWS),
            "thresholds": list(THRESHOLDS),
            "codes": {v: k for k, v in CODE.items()},
            "note": "Ролловые недели и шатдауны исключены",
        },
        "rows": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if not (OUT.parent / "test.md").exists():
        print(f"Внимание: в {OUT.parent} нет test.md, страница не соберётся без него")
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    OUT.write_text(text, encoding="utf-8")
    print(f"Записано: {OUT} ({len(text) // 1024} KB), недель {len(rows)}")

    # консольная сводка: ΔNet, неделя, обе идеи
    for win in WINDOWS:
        print(f"\n== ΔNet, окно {win}, неделя   [контртренд: ниж→выше / верх→ниже]   [моментум: ниж→ниже / верх→выше]")
        for g in ("lf", "am"):
            for t in THRESHOLDS:
                k = f"d{g}{win}_{t}"
                ws = [x for x in rows if not x["roll"] and x.get(k)]
                L = [x["wc"] for x in ws if x[k] == "L"]
                H = [x["wc"] for x in ws if x[k] == "H"]
                pu = lambda v: sum(1 for z in v if z > 0) / len(v) * 100 if v else float("nan")
                print(f"  {g} {t}: контр {pu(L):5.1f}% (n={len(L):3d}) / {100-pu(H):5.1f}% (n={len(H):3d})   момент {100-pu(L):5.1f}% / {pu(H):5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
