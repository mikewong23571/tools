"""Run：一次训练运行的档案管理 + run 级同步。

约定（与 README 的"Run / Checkpoint 管理"一节对应）：
- 协作单位是 run 目录（runs/<name>/），不是整个仓库：sync 只推自己的子树，
  resume 只拉自己的子树，并行实验互不干扰
- 新假设 = 新 run，默认不拉任何历史；resume=True 才拉回同名 run
- 每个 run 必须有 description（意图），落在 run.json 元数据里
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from . import core

META_FILE = "run.json"


def _natural_key(p: Path):
    """自然序：文件名中的数字段按数值比较，pull 后（mtime 失效）排序仍正确。"""
    return [int(t) if t.isdigit() else t
            for t in re.split(r"(\d+)", p.name)]


class Run:
    """with Run("artifacts", name="exp1", description="baseline lr=0.01") as run: ..."""

    def __init__(self, root: str | Path = "artifacts", *,
                 name: str | None = None, description: str,
                 repo: str | None = None, keep_last: int = 3,
                 resume: bool = False):
        if resume and not name:
            raise core.UsageError("resume=True 需要显式指定 name（续跑哪个 run）")
        self.root = Path(root)
        self.run_id = name or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.dir = self.root / "runs" / self.run_id
        self.path_in_repo = f"runs/{self.run_id}"
        self.description = description
        self.repo = repo
        self.keep_last = keep_last
        self.resume = resume
        (self.dir / "checkpoints").mkdir(parents=True, exist_ok=True)
        self._write_meta()

    def _write_meta(self) -> None:
        meta_path = self.dir / META_FILE
        if meta_path.exists():
            return  # 续跑/重进：保留原始 created_at 与描述
        meta = {
            "name": self.run_id,
            "description": self.description,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    def log(self, metrics: dict) -> None:
        """追加一行指标到 metrics.jsonl。"""
        record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  **metrics}
        with open(self.dir / "metrics.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def sync(self, message: str | None = None) -> None:
        """关键节点触发：修剪本地 checkpoint，镜像推送本 run 子树到远端。"""
        self._prune()
        core.push(self.dir, repo=self.repo, message=message,
                  mirror=True, path_in_repo=self.path_in_repo)

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
        if self.resume:
            try:
                core.pull(self.root, repo=self.repo,
                          allow_patterns=[f"{self.path_in_repo}/**"])
            except Exception as exc:
                if not core.is_remote_missing(exc):
                    raise
                print(f"[mlstash] 远端无此 run，全新开始：{self.path_in_repo}")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # 训练异常也要兜底同步一次（修剪 + 镜像推送本 run 子树），保住现场
        self.sync()
        return False
