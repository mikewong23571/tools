"""mlstash 命令行入口：argparse 薄壳，逻辑在 core。"""

from __future__ import annotations

import argparse
import sys

from . import core


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mlstash",
        description="在临时运行时（如 Colab）与 ModelScope 之间同步 ML 产物目录。",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_push = sub.add_parser("push", help="把本地产物目录推送到 ModelScope（断点续传、单 commit）")
    p_push.add_argument("path", nargs="?", default=core.DEFAULT_DIR,
                        help=f"产物目录，默认 {core.DEFAULT_DIR}")
    p_push.add_argument("--repo", help=f"目标仓库，默认取环境变量 {core.REPO_ENV}")
    p_push.add_argument("--message", "-m", help="commit 信息，默认当前 UTC 时间戳")
    p_push.set_defaults(func=lambda a: core.push(a.path, repo=a.repo,
                                                 message=a.message))

    p_pull = sub.add_parser("pull", help="从 ModelScope 拉取产物目录到本地（用于恢复进度）")
    p_pull.add_argument("path", nargs="?", default=core.DEFAULT_DIR,
                        help=f"恢复到该目录，默认 {core.DEFAULT_DIR}")
    p_pull.add_argument("--repo", help=f"源仓库，默认取环境变量 {core.REPO_ENV}")
    p_pull.add_argument("--revision", help="指定 commit/分支，默认 master")
    p_pull.set_defaults(func=lambda a: core.pull(a.path, repo=a.repo,
                                                 revision=a.revision))

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except core.UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # 网络/鉴权等错误：给 agent 可读的一行信息
        print(f"error: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


def entry() -> None:
    sys.exit(main())
