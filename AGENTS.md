# 项目工作原则

本仓库是一组**独立小工具**的集合，每个工具解决一个小需求。

## 目录约定

- 每个工具一个独立目录（如 `mlstash/`），目录内自包含：自己的 `pyproject.toml`、README、源码。
- 工具之间不共享代码、不互相依赖；需要复用时先复制，复用模式稳定出现三次以上再考虑抽取。
- 仓库公开托管于 GitHub，工具经 `pip install "git+https://github.com/mikewong23571/tools.git#subdirectory=<目录名>"` 分发到 Colab 等远端环境——因此**工具必须保持纯 Python、依赖全部来自 PyPI**，不引入编译步骤或私有依赖。

## 工具注册协议

- 每个工具的 `README.md` 顶部必须有 frontmatter 块，声明 `name`（与目录名一致）和 `summary`（一句话简述）两个字段。
- 根 `README.md` 的工具列表由 `python3 scripts/sync_tools_readme.py` 从 frontmatter 生成，**禁止手工编辑**标记区内容。
- 提交前必须保证列表最新：pre-commit hook 会执行 `--check`，过期则拒绝提交（hook 经 `git config core.hooksPath .githooks` 启用）。

## 设计与实现原则

1. 优先参考社区最佳实践和准则；动手前先思考方案是否符合普适设计原则，不符合的代码不落地。
2. 需求未明确时，不引入解决"未来问题"的复杂抽象（不多后端、不预留插件机制、不提前泛化）。
3. 严格按用户给出的上下文实现，不自行拓展需求边界。
4. 工具面向无人值守场景：非交互、鉴权走环境变量、退出码明确、错误信息可读。
