"""push/pull 核心逻辑，CLI 与 Python API（stash 上下文）共用。"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DIR = "artifacts"
REPO_ENV = "MLSTASH_REPO"
TOKEN_ENV = "MODELSCOPE_TOKEN"
REPO_TYPE = "dataset"
IGNORE_PATTERNS = [".ipynb_checkpoints/*", "**/.ipynb_checkpoints/*"]


class UsageError(Exception):
    """可预期的用法错误。"""


def resolve_repo(repo: str | None) -> str:
    repo = repo or os.environ.get(REPO_ENV)
    if not repo:
        raise UsageError(
            f"缺少目标仓库：请通过参数或环境变量 {REPO_ENV} 指定，"
            "例如 'username/my-project-artifacts'"
        )
    return repo


def require_token() -> str:
    token = os.environ.get(TOKEN_ENV)
    if not token:
        raise UsageError(
            f"未检测到 {TOKEN_ENV} 环境变量。请在 "
            "https://modelscope.cn/my/myaccesstoken 创建 SDK 令牌后 export。"
        )
    return token


def is_remote_missing(exc: Exception) -> bool:
    """判断异常是否为"远端仓库不存在"（首次运行的正常情况）。"""
    resp = getattr(exc, "response", None)
    if resp is not None and getattr(resp, "status_code", None) == 404:
        return True
    return "404" in str(exc) and "不存" in str(exc)


def push(path: str | Path = DEFAULT_DIR, repo: str | None = None,
         message: str | None = None, mirror: bool = False,
         path_in_repo: str = "") -> None:
    """把产物目录推送到 ModelScope（仓库不存在时自动创建为私有 dataset）。

    path_in_repo：推送到仓库内的子路径（run 级协作用，如 "runs/exp1"）。
    mirror=True 时远端【该子路径范围内】与本地保持一致（本地已删的远端也删，
    旧版本仍可从历史 commit 找回）；默认 False 只增不删。
    """
    from modelscope_hub import HubApi, RepoType, Visibility
    from modelscope_hub.errors import AlreadyExistsError

    repo = resolve_repo(repo)
    token = require_token()
    folder = Path(path)
    if not folder.is_dir():
        raise UsageError(f"目录不存在：{folder}")

    api = HubApi(token=token)
    try:
        api.create_repo(repo_id=repo, repo_type=RepoType.DATASET,
                        visibility=Visibility.PRIVATE)
    except AlreadyExistsError:
        pass
    message = message or datetime.now(timezone.utc).strftime(
        "snapshot %Y-%m-%dT%H:%M:%SZ"
    )
    api.upload_folder(
        repo_id=repo,
        repo_type=RepoType.DATASET,
        folder_path=str(folder),
        path_in_repo=path_in_repo.strip("/"),
        commit_message=message,
        ignore_patterns=IGNORE_PATTERNS,
        sync_remote_repo=mirror,
    )
    dest = f"https://modelscope.cn/datasets/{repo}"
    if path_in_repo:
        dest += f"/tree/master/{path_in_repo.strip('/')}"
    print(f"[mlstash] pushed {folder} -> {dest}")


def pull(path: str | Path = DEFAULT_DIR, repo: str | None = None,
         revision: str | None = None,
         allow_patterns: list[str] | None = None) -> None:
    """从 ModelScope 拉取产物目录到本地。公开仓库无需 token。

    allow_patterns：只拉匹配的文件（如 ["runs/exp1/**"] 只拉单个 run）。
    """
    from modelscope.hub.snapshot_download import snapshot_download

    repo = resolve_repo(repo)
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    snapshot_download(
        repo_id=repo,
        repo_type=REPO_TYPE,
        revision=revision,
        local_dir=str(target),
        allow_patterns=allow_patterns,
        token=os.environ.get(TOKEN_ENV),
    )
    print(f"[mlstash] pulled {repo} -> {target}")
