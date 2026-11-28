#!/usr/bin/env python3
"""DoxaizOS: проверка относительных ссылок в Markdown-документации.

Находит все ссылки вида [текст](путь) в *.md и проверяет, что относительные
цели существуют в репозитории. Внешние (http://, https://, mailto:) и якоря
(#...) пропускаются. Выход с кодом 1, если хоть одна цель не найдена.
"""

import os
import re
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

def iter_markdown_files():
    yield os.path.join(REPO_ROOT, "README.md")
    docs_dir = os.path.join(REPO_ROOT, "docs")
    for root, _dirs, files in os.walk(docs_dir):
        for name in files:
            if name.endswith(".md"):
                yield os.path.join(root, name)

def main() -> int:
    missing = 0
    checked = 0
    for md_path in iter_markdown_files():
        with open(md_path, "r", encoding="utf-8") as fh:
            content = fh.read()
        md_dir = os.path.dirname(md_path)
        for match in LINK_RE.finditer(content):
            target = match.group(1).strip()
            # Отрезаем якорь и заголовок: "file.md#section" -> "file.md"
            path_part = target.split("#", 1)[0].strip()
            if not path_part:
                continue  # чистый якорь
            if path_part.startswith(("http://", "https://", "mailto:", "ftp://")):
                continue
            if path_part.startswith("/"):
                candidate = os.path.join(REPO_ROOT, path_part.lstrip("/"))
            else:
                candidate = os.path.normpath(os.path.join(md_dir, path_part))
            checked += 1
            if not os.path.exists(candidate):
                rel_md = os.path.relpath(md_path, REPO_ROOT)
                print(f"FAIL {rel_md}: ссылка ведёт в никуда -> {target}")
                missing += 1
    print(f"проверено ссылок: {checked}, битых: {missing}")
    return 1 if missing else 0

if __name__ == "__main__":
    sys.exit(main())
