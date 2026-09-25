"""Run：一次训练运行的档案管理 + 关键节点同步。

约定（与 README 的"Run / Checkpoint 管理"一节对应）：
- run 目录 = 同步单位，checkpoints/ 放快照，metrics.jsonl 记指标
- 复用 run 名 = 续跑；进入上下文时 pull 恢复
- sync() 在关键节点调用：修剪本地 checkpoint 后镜像推送到远端
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .stash import stash


def _natural_key(p: Path):
    """自然序：文件名中的数字段按数值比较，pull 后（mtime 失效）排序仍正确。"""
    return [int(t) if t.isdigit() else t
            for t in re.split(r"(\d+)", p.name)]


class Run:
    """with Run("artifacts", name="exp1") as run: ..."""

    def __init__(self, root: str | Path = "artifacts", *,
                 name: str | None = None, repo: str | None = None,
                 keep_last: int = 3):
        run_id = name or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.root = Path(root)
        self.dir = self.root / "runs" / run_id
        self.run_id = run_id
        self.keep_last = keep_last
        self._stash = stash(self.root, repo=repo)
        (self.dir / "checkpoints").mkdir(parents=True, exist_ok=True)

    def log(self, metrics: dict) -> None:
        """追加一行指标到 metrics.jsonl。"""
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  **metrics}
        with open(self.dir / "metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def sync(self, message: str | None = None) -> None:
        """关键节点触发：修剪本地 checkpoint，然后把 root 镜像推送到远端。"""
        self._prune()
        self._stash.save(message, mirror=True)

    def latest_checkpoint(self) -> Path | None:
        """最近一个 checkpoint（不含 best*），用于续跑定位断点。"""
        ckpts = self._prunable()
        return ckpts[-1] if ckpts else None

    def _prunable(self) -> list[Path]:
        ckpts = [p for p in (self.dir / "checkpoints").iterdir()
                 if p.is_file() and not p.name.startswith("best")]
        return sorted(ckpts, key=_natural_key)

    def _prune(self) -> None:
        if self.keep_last <= 0:
            return
        for p in self._prunable()[:-self.keep_last]:
            p.unlink()

    def __enter__(self) -> "Run":
        self._stash.__enter__()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # 训练异常也要兜底同步一次（修剪 + 镜像推送），保住现场
        self._prune()
        self._stash.save(self._stash.message, mirror=True)
        return False
