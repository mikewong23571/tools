# mlstash 用户故事与验收

角色：**训练者**（国内网络环境，使用 Colab 算力）、**coding agent**（无人值守驱动全流程）。

每个故事标注验收标准与实测证据。验证环境：本机 macOS + Colab CPU runtime + ModelScope 私有 dataset 仓库。

## 已闭环

### US-1 关键节点保存，回收不丢进度
> 作为训练者，我希望训练中在关键节点把 checkpoint 同步到远端，以便 runtime 回收不丢进度。

- 验收：`run.sync()` 后远端 `runs/<name>/` 子树含 checkpoint 与 metrics
- 证据：Colab 实测，epoch 0/3/5 关键节点 + 退出兜底共 4 次推送成功（2026-09-25）

### US-2 回收后续跑
> 作为训练者，我希望 runtime 被回收后，新 runtime 能从断点继续，而不是重训。

- 验收：`resume=True` 只拉回该 run 子树，`latest_checkpoint()` 定位断点，状态完全一致
- 证据：销毁 session 后新建 session，`RESUMED from epoch 6, w=2.2136` 与销毁前完全一致（2026-09-25）

### US-3 新假设零历史负担
> 作为训练者，我希望开启新实验时不拉取任何历史数据。

- 验收：`resume=False`（默认）进入上下文零网络请求
- 证据：本地测试，指向不存在仓库也瞬时进入（2026-09-25）

### US-4 并行实验互不干扰
> 作为训练者，我希望同项目多组实验（不同 run 名）可以并行推送，互不误删。

- 验收：exp-b 推送后 exp-a 子树完好（镜像删除限定在推送子树内）
- 证据：真实仓库双 run 推送 + 远端树断言（2026-09-25）

### US-5 只取关心的 run 回本机
> 作为训练者，我希望在国内本机只拉取我关心的那个 run，而不是整个仓库。

- 验收：`mlstash pull --subdir runs/exp1` 只下载该子树文件
- 证据：CLI 实测精确拉回 exp-b 的 2 个文件（2026-09-25）

### US-6 run 意图可追溯
> 作为训练者，我希望每个 run 自带意图描述与元数据，回看时知道这次实验在验证什么。

- 验收：`description` 为必填参数；`run.json`（name/description/created_at）随产物同步且不覆盖
- 证据：缺 description 报 TypeError；run.json 远端往返一致（2026-09-25）

### US-7 训练异常保现场
> 作为训练者，我希望训练脚本崩溃时，已产生的中间结果仍然被保存。

- 验收：with 体抛异常时，`__exit__` 兜底 sync 仍执行，原异常正常传播
- 证据：模拟崩溃后远端收到 checkpoint，RuntimeError 原样抛出（2026-09-25）

### US-8 通用目录流转（数据集等）
> 作为训练者，我希望数据集等非 run 结构的目录也能整目录推送/拉取。

- 验收：`stash` 上下文整目录 push/pull；与 run 子树共存不误删（默认 mirror=False）
- 证据：data.csv 推送到仓库根，既有 runs/ 子树完好（2026-09-25）

### US-9 无人值守可自诊断
> 作为 coding agent，我希望工具失败时给出可读错误和明确的退出码，以便自行修复或上报。

- 验收：用法错误 exit 2（缺 repo/缺 token/目录不存在，含补救指引）；运行时错误 exit 1
- 证据：本地全错误路径实测（2026-09-25）

### US-10 runtime 一行安装
> 作为 coding agent，我希望在全新 Colab runtime 上一条命令装好 mlstash，无需凭证。

- 验收：`colab install "git+https://github.com/mikewong23571/tools.git#subdirectory=mlstash"` 成功
- 证据：Colab 实测两轮 session 均安装成功（2026-09-25）

### US-11 token 不进 agent 上下文
> 作为训练者，我希望 token 只存在于 .env.local，不出现在对话、日志、代码中。

- 验收：`.env.local` 被 gitignore（已验证）；`--env "KEY=$VAR"` 由 shell 展开，agent 只见变量名
- 证据：`git check-ignore` 验证 + Colab exec 注入实测（2026-09-25）

### US-12 保留策略与远端镜像
> 作为训练者，我希望本地只留最近 k 个 checkpoint + best，远端同步删除被修剪的（仅限本 run 子树）。

- 验收：修剪生效；远端子树同步删除（日志 `Deleted (sync): N`）；兄弟 run 不受影响
- 证据：本地断言 + 远端树断言 + Colab 复验（2026-09-25）

## 已知边界（非缺陷，设计内）

- ModelScope 禁止 API 删除仓库，仓库清理需在网页端手动操作
- SDK 同步时输出较多进度日志（如需可加 `disable_tqdm` 透传，当前未做）
- `colab exec --timeout` 默认 30s，长训练必须显式调大

## 测试资产

以下 ModelScope 仓库为回归测试专用，**有意保留、勿删**（后续改动 mlstash 时可复用它们重跑本文件中的验收场景）：

- `mikewong23571/mlstash-e2e`（run 级协作 / 镜像修剪场景）
- `mikewong23571/mlstash-colab-e2e`（Colab 回收续跑场景）
- `mikewong23571/mlstash-acceptance`（stash 通用目录 / 异常兜底场景）
