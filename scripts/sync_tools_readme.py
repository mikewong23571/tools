#!/usr/bin/env python3
"""从各工具 README.md 的 frontmatter 生成根 README.md 的工具列表。

协议：每个工具目录（含 pyproject.toml）的 README.md 必须以 YAML frontmatter
开头，声明两个字段：

    ---
    name: <工具名>
    summary: <一句话简述>
    ---

用法：
    python3 scripts/sync_tools_readme.py          # 重新生成根 README 的工具列表
    python3 scripts/sync_tools_readme.py --check  # 只校验不写文件，不一致时退出码 1
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ROOT_README = ROOT / "README.md"
BEGIN = "<!-- tools:begin -->"
END = "<!-- tools:end -->"

FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


class RegistryError(Exception):
    pass


def parse_frontmatter(readme: Path) -> dict[str, str]:
    text = readme.read_text(encoding="utf-8")
    m = FRONTMATTER_RE.match(text)
    if not m:
        raise RegistryError(f"{readme.relative_to(ROOT)}: 缺少 frontmatter 块")
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
    for required in ("name", "summary"):
        if not fields.get(required):
            raise RegistryError(
                f"{readme.relative_to(ROOT)}: frontmatter 缺少字段 {required!r}")
    return fields


def collect_tools() -> list[dict[str, str]]:
    tools = []
    for path in sorted(ROOT.iterdir()):
        if not path.is_dir() or path.name.startswith((".", "scripts")):
            continue
        if not (path / "pyproject.toml").is_file():
            continue  # 不是工具目录
        tools.append(parse_frontmatter(path / "README.md"))
    return tools


def render(tools: list[dict[str, str]]) -> str:
    lines = [
        BEGIN,
        "<!-- 由 scripts/sync_tools_readme.py 生成，请勿手改 -->",
        "",
        "| 工具 | 简述 |",
        "| --- | --- |",
    ]
    for t in tools:
        lines.append(f"| [{t['name']}]({t['name']}/) | {t['summary']} |")
    lines += ["", END]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    check = "--check" in argv
    tools = collect_tools()
    text = ROOT_README.read_text(encoding="utf-8")
    if BEGIN not in text or END not in text:
        raise RegistryError(f"根 README.md 缺少标记 {BEGIN} / {END}")
    new_text = re.sub(
        re.escape(BEGIN) + ".*?" + re.escape(END),
        lambda _: render(tools),
        text,
        flags=re.DOTALL,
    )
    if check:
        if new_text != text:
            print("error: 根 README.md 的工具列表已过期，"
                  "请运行 python3 scripts/sync_tools_readme.py 后重新提交",
                  file=sys.stderr)
            return 1
        print(f"ok: 工具列表已是最新（{len(tools)} 个工具）")
        return 0
    if new_text != text:
        ROOT_README.write_text(new_text, encoding="utf-8")
        print(f"已更新工具列表（{len(tools)} 个工具）")
    else:
        print(f"无变化（{len(tools)} 个工具）")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except RegistryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(2)
