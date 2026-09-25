"""stash 上下文管理器：训练代码只感知产物目录，不感知远端。"""

from __future__ import annotations

from pathlib import Path

from . import core


class stash:
    """进入时拉取产物目录，退出时（无论是否异常）推送。

    with stash("artifacts", repo="user/proj") as st:
        train(out=st.path)
        st.save("epoch 10")   # 可选：训练中手动存一次
    # 退出时自动 push
    """

    def __init__(self, path: str | Path = core.DEFAULT_DIR, *,
                 repo: str | None = None, revision: str | None = None,
                 message: str | None = None):
        self.path = Path(path)
        self.repo = repo
        self.revision = revision
        self.message = message

    def save(self, message: str | None = None, mirror: bool = False) -> None:
        """训练中手动保存一次快照。mirror=True 时远端与本地保持一致。"""
        core.push(self.path, repo=self.repo, message=message, mirror=mirror)

    def __enter__(self) -> "stash":
        self.path.mkdir(parents=True, exist_ok=True)
        try:
            core.pull(self.path, repo=self.repo, revision=self.revision)
        except Exception as exc:
            # 仅当未指定 revision 时，404 才意味着"仓库不存在=首次运行"；
            # 指定了 revision 的 404 是"版本不存在"，必须抛出让调用方知道
            if self.revision is not None or not core.is_remote_missing(exc):
                raise
            print(f"[mlstash] 远端无历史，全新开始：{self.path}")
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        # 即使训练抛异常也推送：保住中间结果正是本工具的目的
        self.save(self.message)
        return False
