#!/usr/bin/env python3
"""
Сборка workspace: каждая папка превращается в index.html рядом со своими
исходниками, так что дерево папок и есть сайт. Открывается по file://.

Сайт в три уровня:
  - корень                     → баннер Algo Tests и плитки инструментов;
  - папка инструмента          → чарт (renderer в index.md) и плитки тестов по разделам (ключ group);
  - папка с test.md            → страница теста: идея, правила, статистика
                                 (интерактив встаёт в блок mount_in, по умолчанию «Результаты»).
Имена папок от корня → хлебные крошки. assets/ и скрытые папки пропускаются,
папки с archived: true собираются, но в плитках не показываются.

test.md = frontmatter (плоские key: value и списки «- item») + тело с
заголовками «## …». Ключ renderer выбирает, что вставить в раздел «Результаты»:
  markdown       ничего, только текст;
  cot_pa_tables  таблицы 3×5 (нужен results.json от scripts/06_export_results.py);
  mp_zone_table  зона открытия × тип (архивные тесты 1.1 и 1.2, results.json заморожен);
  mp_open_matrix точка открытия × тип открытия → тип дня и точка открытия → тип открытия
                 (results.json от mp-es-pipeline/scripts/11_test_open_matrix.py, исход в поле outcome);
  cot_yesno      вопрос да/нет у границ индекса (results.json от 08_export_yesno.py);
  mp_chart       смотрелка профилей и композитов без таблиц (данные от 12_export_chart.py).

Ключи рендерера: mount — блок в разделе «Результаты», pre — карточка над тестом,
extra — карточка после, js — инлайн-скрипт с window.DATA, js_extra — дополнительные
скрипты, data_js — файл данных из assets/data, подключается тегом <script defer>.

Запуск:  python3 build.py
"""
import html as H
import json
import re
import sys
import urllib.parse
from pathlib import Path

WS = Path(__file__).resolve().parent
ROOT_TITLE = "Algo Tests"
SKIP_DIRS = {"assets"}
FONTS = ('<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
         'family=IBM+Plex+Mono:wght@300;400;500;600;700&family=IBM+Plex+Sans:wght@400;500&display=swap">')

VERDICT_CLASS = {"прошло": "pass", "не прошло": "fail", "частично": "part"}
STATUS_CLASS = {"завершён": "pass", "закрыт": "dim", "заменён": "dim", "в работе": "part", "инструмент": "mid"}

# ставится в <head> до подключения style.css, чтобы выбранная тема
# применилась ещё до первой отрисовки страницы (без вспышки не той темы)
THEME_HEAD_SCRIPT = (
    '<script>try{if(localStorage.getItem("algo-tests-theme")==="light")'
    'document.documentElement.setAttribute("data-theme","light")}catch(e){}</script>'
)

# тумблер (трек + кружок) — тема ставится head-скриптом выше,
# здесь только синхронизация подписи и обработчик клика по всему блоку
THEME_TOGGLE_HTML = (
    '<div class="theme-toggle" id="theme-toggle" role="button" tabindex="0" aria-label="Переключить тему">'
    '<span class="label" id="theme-toggle-label">Тёмная</span>'
    '<div class="theme-toggle-track"><div class="theme-toggle-knob"></div></div></div>'
)
THEME_TOGGLE_SCRIPT = """<script>
(function(){
  var KEY = 'algo-tests-theme';
  var el = document.getElementById('theme-toggle');
  var label = document.getElementById('theme-toggle-label');
  if (!el) return;
  function sync(){
    var light = document.documentElement.getAttribute('data-theme') === 'light';
    label.textContent = light ? 'Светлая' : 'Тёмная';
  }
  function flip(){
    var light = document.documentElement.getAttribute('data-theme') === 'light';
    if (light) document.documentElement.removeAttribute('data-theme');
    else document.documentElement.setAttribute('data-theme', 'light');
    try { localStorage.setItem(KEY, light ? 'dark' : 'light'); } catch(e){}
    sync();
  }
  sync();
  el.addEventListener('click', flip);
  el.addEventListener('keydown', function(e){ if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); flip(); } });
})();
</script>"""


# ---------------------------------------------------------------- helpers
def esc(s) -> str:
    return H.escape(str(s), quote=True)


def rel(depth: int) -> str:
    return "../" * depth


def child_href(name: str) -> str:
    return urllib.parse.quote(name) + "/index.html"


def parse_frontmatter(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta: dict = {}
    key = None
    for ln in lines[1:end]:
        if not ln.strip():
            continue
        m = re.match(r"^\s+-\s+(.*)$", ln)
        if m and key is not None:
            if not isinstance(meta[key], list):
                meta[key] = []
            meta[key].append(m.group(1).strip())
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", ln)
        if m:
            key = m.group(1)
            val = m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):          # список в одну строку: [a, b, c]
                meta[key] = [x.strip() for x in val[1:-1].split(",") if x.strip()]
            else:
                meta[key] = val if val else []
    return meta, "\n".join(lines[end + 1:])


def inline(s: str) -> str:
    s = esc(s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2">\1</a>', s)
    return s


def md_to_html(body: str) -> str:
    """Минимальный markdown: h2/h3, абзацы, списки, pipe-таблицы, ```блоки```,
    **жирный**, `код`, [ссылки](url). Строки, начинающиеся с «<», идут как есть."""
    out: list[str] = []
    para: list[str] = []
    lines = body.splitlines()

    def flush():
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para.clear()

    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            flush()
            j = i + 1
            buf = []
            while j < len(lines) and not lines[j].startswith("```"):
                buf.append(lines[j])
                j += 1
            out.append('<div class="formula">' + esc("\n".join(buf)) + "</div>")
            i = j + 1
            continue
        if ln.startswith("### "):
            flush(); out.append("<h3>" + inline(ln[4:]) + "</h3>"); i += 1; continue
        if ln.startswith("## "):
            flush(); out.append("<h2>" + inline(ln[3:]) + "</h2>"); i += 1; continue
        if ln.lstrip().startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(lines[i].strip())
                i += 1
            cells = []
            for r in rows:
                if re.match(r"^\|[\s:\-|]+\|$", r):
                    continue
                cells.append([c.strip() for c in r.strip("|").split("|")])
            if cells:
                t = '<div class="twrap"><table class="plain md"><thead><tr>'
                t += "".join(f"<th>{inline(c)}</th>" for c in cells[0]) + "</tr></thead><tbody>"
                for r in cells[1:]:
                    t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                out.append(t + "</tbody></table></div>")
            continue
        m_ul = re.match(r"^\s*[-*]\s+(.*)$", ln)
        m_ol = re.match(r"^\s*\d+[.)]\s+(.*)$", ln)
        if m_ul or m_ol:
            flush()
            tag = "ul" if m_ul else "ol"
            pat = r"^\s*[-*]\s+(.*)$" if m_ul else r"^\s*\d+[.)]\s+(.*)$"
            items = []
            while i < len(lines):
                m = re.match(pat, lines[i])
                if not m:
                    break
                items.append(m.group(1))
                i += 1
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
            continue
        if ln.startswith("<"):
            flush(); out.append(ln); i += 1; continue
        if not ln.strip():
            flush(); i += 1; continue
        para.append(ln.strip())
        i += 1
    flush()
    return "\n".join(out)


def split_sections(body: str) -> list[tuple[str | None, str]]:
    """[(заголовок '## …' или None для преамбулы, текст раздела)]."""
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    in_code = False
    for ln in body.splitlines():
        if ln.startswith("```"):
            in_code = not in_code
        if not in_code and ln.startswith("## "):
            sections.append((ln[3:].strip(), []))
        else:
            sections[-1][1].append(ln)
    return [(h, "\n".join(b).strip()) for h, b in sections if h is not None or "\n".join(b).strip()]


def crumbs_html(crumbs: list[str], depth: int) -> str:
    parts = []
    for k, name in enumerate(crumbs):
        if k == len(crumbs) - 1:
            parts.append(f'<span class="cur">{esc(name)}</span>')
        else:
            parts.append(f'<a href="{rel(depth - k)}index.html">{esc(name)}</a>')
    return '<nav class="crumbs">' + '<span class="sep">/</span>'.join(parts) + "</nav>"


def page_shell(title: str, sub: str, crumbs: list[str], depth: int, body: str, meta_html: str = "", scripts: str = "") -> str:
    # корень: та же шапка, что на остальных страницах, без крошек и чуть крупнее
    head = (
        ("" if depth == 0 else f"{crumbs_html(crumbs, depth)}\n")
        + f'<header class="hdr{" hdr-root" if depth == 0 else ""}"><div><h1>{esc(title)}</h1>'
        + (f'<div class="sub">{esc(sub)}</div>' if sub else "")
        + f'</div><div class="meta" id="hdr-meta">{meta_html}</div></header>\n')
    return (
        f"<!doctype html>\n<html lang=\"ru\"><head><meta charset=\"utf-8\">"
        f"<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{esc(title)}</title>\n{THEME_HEAD_SCRIPT}\n{FONTS}\n"
        f'<link rel="stylesheet" href="{rel(depth)}assets/style.css"></head>\n<body>\n'
        f"{THEME_TOGGLE_HTML}\n"
        f'<div class="app">\n'
        + head
        + f"{body}\n"
        f"</div>\n{scripts}\n{THEME_TOGGLE_SCRIPT}\n</body></html>\n"
    )


def card(title: str | None, inner: str, hint: str = "", collapsed: bool = False) -> str:
    if collapsed and title:
        return ('<section class="card fold"><details><summary>' + esc(title)
                + (f'<span class="hint">{esc(hint)}</span>' if hint else "")
                + f'</summary><div class="prose">{inner}</div></details></section>')
    head = ""
    if title:
        head = f'<h2 class="card-title">{esc(title)}' + (f'<span class="hint">{esc(hint)}</span>' if hint else "") + "</h2>"
    return f'<section class="card">{head}<div class="prose">{inner}</div></section>'


def pill(text: str, cls_map: dict) -> str:
    cls = cls_map.get(str(text).lower(), "")
    return f'<span class="pill {cls}">{esc(text)}</span>'


def props_html(meta: dict) -> str:
    """Шапка страницы. Статус и вердикт не показываются: трейдер читает выводы из текста."""
    rows = []
    if meta.get("instrument"):
        rows.append(("Инструмент", f'<span class="sans">{esc(meta["instrument"])}</span>'))
    dates = []
    if meta.get("created"):
        dates.append(f"создан {esc(meta['created'])}")
    if meta.get("updated"):
        dates.append(f"обновлён {esc(meta['updated'])}")
    if dates:
        rows.append(("Даты", " · ".join(dates)))
    vs = meta.get("variables")
    if isinstance(vs, list) and vs:
        rows.append(("Переменные", '<ul class="sans">' + "".join(f"<li>{inline(x)}</li>" for x in vs) + "</ul>"))
    if meta.get("source"):
        rows.append(("Источник", f'<span class="sans">{inline(meta["source"])}</span>'))
    if meta.get("id"):
        rows.append(("ID", f"<code>{esc(meta['id'])}</code>"))
    if not rows:
        return ""
    return '<section class="card"><table class="kv">' + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in rows) + "</table></section>"


# ---------------------------------------------------------------- renderers
def mount_cot_pa_tables(meta: dict) -> str:
    return '<div class="controls" id="pa-controls"></div><div id="pa-results"></div>'


def extra_cot_pa_tables(meta: dict) -> str:
    return card("Воронка недель", '<div id="pa-funnel"></div>', "для выбранной группы и режима ролловых недель")


def mount_cot_yesno(meta: dict) -> str:
    def seg(cid, label, opts):
        btns = "".join(f'<button data-v="{esc(v)}">{esc(t)}</button>' for v, t in opts)
        return f'<div class="ctl"><span class="ctl-label">{label}</span><div class="seg" id="{cid}">{btns}</div></div>'
    controls = (
        seg("c-v", "Переменная", [("", "Net"), ("d", "ΔNet за неделю")])
        + seg("c-i", "Идея", [("contra", "Контртренд"), ("mom", "Моментум")])
        + seg("c-g", "Группа", [("lf", "LF"), ("am", "AM"), ("both", "LF + AM")])
        + seg("c-n", "Окно индекса", [("13", "13 нед"), ("26", "26 нед"), ("52", "52 нед")])
        + seg("c-t", "Порог", [("2080", "20 / 80"), ("1090", "10 / 90"), ("0595", "5 / 95")])
        + seg("c-w", "Окно", [("wc", "Неделя"), ("mc", "Понедельник")])
        + seg("c-p", "Планка", [("60", "60%"), ("65", "65%"), ("70", "70%"), ("75", "75%")])
    )
    return (
        '<p style="margin-top:0">Планка: закрытие в сторону идеи должно случаться не реже чем в '
        '<strong><span id="tgt-txt">70</span>%</strong> случаев.</p>'
        f'<div class="controls">{controls}</div>'
        '<div class="big" id="big"></div>'
        '<div class="twrap"><table class="res"><thead><tr><th>Граница</th><th>n</th><th>Закрылось в сторону идеи %</th>'
        '<th>Против %</th><th>В сторону, недель</th><th>Против, недель</th><th>Планка</th></tr></thead>'
        '<tbody id="tb"></tbody></table></div><p class="note" id="note"></p>'
    )


def mount_mp_zone_table(meta: dict) -> str:
    return ('<div class="controls" id="zt-controls"></div>'
            '<h3 class="card-title" style="margin-top:4px">Какой тип</h3><div id="zt-types"></div>'
            '<h3 class="card-title" style="margin-top:22px">По тренду открытия или против</h3><div id="zt-dirs"></div>'
            '<p class="note" id="zt-note"></p>')


def mount_mp_open_matrix(meta: dict) -> str:
    return ('<div class="controls" id="om-controls"></div>'
            '<div id="om-calc"></div>'
            '<p class="note" id="om-note"></p>')


def mount_mp_chart(meta: dict) -> str:
    return '<div class="mpc" id="mpc"></div>'


def mount_mp_chart_page(meta: dict) -> str:
    return '<div class="mpc" id="mpc" data-own="mode,ref,filter"></div>'


RENDERERS = {
    "markdown": {"mount": None, "extra": None, "js": None, "needs_results": False},
    "cot_pa_tables": {"mount": mount_cot_pa_tables, "extra": extra_cot_pa_tables, "js": "cot_pa_tables.js", "needs_results": True},
    "cot_yesno": {"mount": mount_cot_yesno, "extra": None, "js": "cot_yesno.js", "needs_results": True},
    "mp_zone_table": {"mount": mount_mp_zone_table, "extra": None, "js": "mp_zone_table.js", "needs_results": True},
    # данные графика нужны тесту для своей строки и сводок; сам чарт живёт на странице инструмента
    "mp_open_matrix": {"mount": mount_mp_open_matrix, "extra": None, "js": "mp_open_matrix.js", "needs_results": True,
                       "data_js": "mp_chart_data.js"},
    "mp_chart": {"mount": mount_mp_chart_page, "extra": None, "js": None, "needs_results": False,
                 "js_extra": ["mp_chart.js"], "data_js": "mp_chart_data.js"},
}


def scripts_html(r: dict, depth: int, results_text: str | None) -> str:
    """Файлы данных и скрипты рендерера для страницы."""
    sc = []
    for name in ([r["data_js"]] if isinstance(r.get("data_js"), str) else r.get("data_js") or []):
        sc.append(f'<script src="{rel(depth)}assets/data/{name}" defer></script>')
    if r.get("js") and results_text is not None:
        js = (WS / "assets" / "renderers" / r["js"]).read_text(encoding="utf-8")
        sc.append(f"<script>window.DATA = {results_text};</script>\n<script>\n{js}\n</script>")
    for name in r.get("js_extra", []):
        sc.append("<script>\n" + (WS / "assets" / "renderers" / name).read_text(encoding="utf-8") + "\n</script>")
    return "\n".join(sc)


def render_test(folder: Path, depth: int, crumbs: list[str], children: list[dict] | None = None) -> tuple[str, dict]:
    meta, body = parse_frontmatter((folder / "test.md").read_text(encoding="utf-8"))
    rname = meta.get("renderer", "markdown")
    if rname not in RENDERERS:
        sys.exit(f"{folder}: неизвестный renderer «{rname}». Допустимо: {', '.join(RENDERERS)}")
    r = RENDERERS[rname]
    results_text = None
    if r["needs_results"]:
        rj = folder / "results.json"
        if not rj.exists():
            sys.exit(f"{folder}: renderer={rname} требует results.json. Запусти экспорт из пайплайна.")
        results_text = json.dumps(json.loads(rj.read_text(encoding="utf-8")), ensure_ascii=False, separators=(",", ":"))
        results_text = results_text.replace("</", "<\\/")

    title = meta.get("title") or folder.name
    fold = set(meta.get("collapse") or [])
    parts = [props_html(meta)]
    if r.get("pre"):
        parts.append(r["pre"](meta))
    has_results_section = False
    mount_in = meta.get("mount_in", "Результаты")   # в какой блок вставить интерактив
    for head, content in split_sections(body):
        inner = md_to_html(content) if content else ""
        if head == mount_in and r["mount"]:
            has_results_section = True
            inner += r["mount"](meta)
            parts.append(card(head, inner, collapsed=head in fold))
            if r["extra"]:
                parts.append(r["extra"](meta))
        else:
            parts.append(card(head, inner, collapsed=head in fold))
    if r["mount"] and not has_results_section:
        parts.append(card("Результаты", r["mount"](meta)))
        if r["extra"]:
            parts.append(r["extra"](meta))

    scripts = scripts_html(r, depth, results_text)
    meta_html = ""
    if children:                                    # вложенные страницы теста (правила): плитками внизу
        parts.append('<div class="cards">' + "".join(tile(c, "Страница") for c in children) + "</div>")
    html = page_shell(title, meta.get("instrument", ""), crumbs, depth, "\n".join(p for p in parts if p), meta_html, scripts)
    return html, meta


def render_section(folder: Path, depth: int, crumbs: list[str], children: list[dict]) -> tuple[str, dict]:
    meta: dict = {}
    body = ""
    idx = folder / "index.md"
    if idx.exists():
        meta, body = parse_frontmatter(idx.read_text(encoding="utf-8"))
    title = meta.get("title") or (ROOT_TITLE if depth == 0 else folder.name)
    fold = set(meta.get("collapse") or [])          # заголовки блоков, которые свёрнуты
    r = RENDERERS.get(meta.get("renderer", "markdown"), RENDERERS["markdown"])
    mount_in = meta.get("mount_in", "Результаты")   # в какой блок вставить интерактив
    parts = []
    mounted = False
    for head, content in split_sections(body):
        inner = md_to_html(content) if content else ""
        if r["mount"] and head == mount_in:
            inner += r["mount"](meta)
            mounted = True
        parts.append(card(head, inner, collapsed=head in fold))
    if depth == 0:
        # главная: плитки инструментов и «+» (новый проект начинается в Claude Code)
        cards = [tile(c, "Инструмент") for c in children]
        cards.append('<a class="tcard tplus" href="https://claude.ai/code" target="_blank" rel="noopener" '
                     'title="Новый проект в Claude Code">+</a>')
        parts.append('<div class="tools-wrap"><div class="tools-panel"><div class="cards tools">' + "".join(cards) + "</div></div></div>")
    else:
        # страница инструмента: карточка Tests, внутри плитки разделов (ключ group в test.md, порядок —
        # по первому тесту раздела), в разделе тесты списком друг под другом; под Tests карточка Chart
        if children:
            groups: dict[str, list[dict]] = {}
            for c in children:
                groups.setdefault(c["meta"].get("group") or "", []).append(c)
            blocks = []
            for g, cs in groups.items():
                lst = '<div class="cards tlist">' + "".join(tile(c, "Тест" if c["is_test"] else "Раздел") for c in cs) + "</div>"
                blocks.append(f'<div class="tgroup"><div class="tgroup-title">{esc(g)}</div>{lst}</div>' if g else lst)
            parts.insert(0, '<section class="card"><h2 class="card-title">Tests</h2><div class="tgroups">'
                         + "".join(blocks) + "</div></section>")
        if r["mount"] and not mounted:
            parts.append(f'<section class="card"><h2 class="card-title">Chart</h2>{r["mount"](meta)}</section>')
        if not children and not r["mount"]:
            parts.append('<div class="empty">Пока пусто.</div>')
    return page_shell(title, meta.get("subtitle", ""), crumbs, depth, "\n".join(parts), "", scripts_html(r, depth, None)), meta


def tile(c: dict, kind: str) -> str:
    """Плитка дочерней страницы. У инструмента в подписи число тестов."""
    m = c["meta"]
    sub = m.get("summary") or ""
    if kind == "Инструмент":
        n = c["n_children"]
        sub += (" · " if sub else "") + (plural(n, "тест", "теста", "тестов") if n else "тестов пока нет")
    return (f'<a class="tcard" href="{child_href(c["name"])}"><div class="tcard-kind">{kind}</div>'
            f'<div class="tcard-name">{esc(m.get("title") or c["name"])}</div><div class="tcard-sub">{esc(sub)}</div></a>')


def plural(n: int, one: str, few: str, many: str) -> str:
    w = one if n % 10 == 1 and n % 100 != 11 else few if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else many
    return f"{n} {w}"


def walk(folder: Path, depth: int, crumbs: list[str], written: list[tuple[Path, int]]) -> dict:
    is_test = (folder / "test.md").exists()
    subs = sorted(
        [p for p in folder.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP_DIRS],
        key=lambda p: p.name.lower(),
    )
    children = [walk(p, depth + 1, crumbs + [p.name], written) for p in subs]
    children = [c for c in children if not c["meta"].get("archived")]   # архив собирается, но не показывается
    if is_test:
        html, meta = render_test(folder, depth, crumbs, children)   # у теста бывают вложенные страницы (правила)
        n = 0
    else:
        html, meta = render_section(folder, depth, crumbs, children)
        n = len(children)
    out = folder / "index.html"
    out.write_text(html, encoding="utf-8")
    written.append((out, len(html.encode("utf-8"))))
    return {"name": folder.name, "is_test": is_test, "meta": meta, "n_children": n}


def main() -> int:
    written: list[tuple[Path, int]] = []
    walk(WS, 0, [ROOT_TITLE], written)
    for p, size in written:
        print(f"{size // 1024:5d} KB  {p.relative_to(WS)}")
    print(f"\nСтраниц: {len(written)}. Открой: {WS / 'index.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
