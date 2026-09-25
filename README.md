# tools

一组独立小工具的集合，每个工具解决一个小需求。工作原则与工具注册协议见 [AGENTS.md](AGENTS.md)。

## 工具列表

<!-- tools:begin -->
<!-- 由 scripts/sync_tools_readme.py 生成，请勿手改 -->

| 工具 | 简述 |
| --- | --- |
| [mlstash](mlstash/) | 在 Colab 等临时运行时与 ModelScope 之间同步 ML 产物（checkpoint / run / 最终模型），防止 runtime 回收导致重复工作 |

<!-- tools:end -->

## 新增一个工具

1. 建目录，内含 `pyproject.toml`、源码、`README.md`
2. README.md 顶部写 frontmatter 协议块：

   ```
   ---
   name: <工具名，与目录名一致>
   summary: <一句话简述>
   ---
   ```

3. 运行 `python3 scripts/sync_tools_readme.py` 重新生成上方列表，随代码一起提交

提交前 pre-commit hook 会自动校验列表是否过期（`git config core.hooksPath .githooks` 一次性启用，本仓库已配置）。
