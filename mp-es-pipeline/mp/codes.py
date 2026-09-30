"""
Короткие коды зон, типов открытия и типов дня для выгрузок на сайт.

Держим их в одном месте, чтобы таблица теста и график профилей подсвечивали одни и те же дни:
scripts/11_test_open_matrix.py (results.json) и scripts/12_export_chart.py (данные графика)
импортируют отсюда.
"""

ZONES = [["ar", "выше диапазона"], ["av", "выше VA, в диапазоне"], ["iv", "внутри VA"],
         ["bv", "ниже VA, в диапазоне"], ["br", "ниже диапазона"]]
ZONE_CODE = {"above_range": "ar", "above_value": "av", "in_value": "iv",
             "below_value": "bv", "below_range": "br", "": ""}

OPEN_TYPES = [["oai", "Open-Auction внутри VA"], ["od", "Open-Drive"], ["otd", "Open-Test-Drive"],
              ["orr", "Open-Rejection-Reverse"], ["oao", "Open-Auction вне VA"]]
OPEN_CODE = {"open_auction_in": "oai", "open_drive": "od", "open_test_drive": "otd",
             "open_rejection_reverse": "orr", "open_auction_out": "oao", "": ""}

DAY_TYPES = [["nm", "Normal", False], ["nt", "Nontrend", False], ["nv", "Normal Variation", True],
             ["tr", "Trend", True], ["dd", "Double-Distribution Trend", True],
             ["nc", "Neutral-Center", False], ["ne", "Neutral-Extreme", True]]
DAY_CODE = {"normal": "nm", "nontrend": "nt", "normal_variation": "nv", "trend": "tr",
            "double_distribution_trend": "dd", "neutral_center": "nc", "neutral_extreme": "ne", "": ""}

DIR = {"up": "u", "down": "d", "": ""}

# что случилось с днём в композите (mp_composite_*.csv, колонки action и start_reason).
# День либо добавлен в открытый композит, либо начал новый — и тогда важно, почему.
COMP_ACTION = {
    "added": 1,
    "start:first": 0,          # первый день истории
    "start:migration": 2,      # VA нового дня не совпала с VA композита
    "start:shape": 3,          # VA совпала, но склеенный профиль перестал быть колоколом
    "start:data_gap": 4,       # день после дыры в данных, опоры нет
}
