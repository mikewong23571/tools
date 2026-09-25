---
name: mlstash
summary: 在 Colab 等临时运行时与 ModelScope 之间同步 ML 产物（checkpoint / run / 最终模型），防止 runtime 回收导致重复工作
---

# mlstash

在 Colab 等**临时运行时**与 ModelScope 之间同步 ML 产物（中间结果、checkpoint、最终模型），避免 runtime 回收导致的重复工作。

## 设计决策

- **存储后端：ModelScope（dataset 仓库，私有）**
  - 链路两端都要通：国内环境推送数据集 / 拉取结果，Colab 端保存训练产物。HF Hub 国内不可达，GitHub 有单文件 100MB 硬限制且 LFS 免费额度仅 1GB，均不适合
  - 无人值守友好：仅需 `MODELSCOPE_TOKEN` 环境变量，无交互式登录
  - 每次 `push` 是一个 commit，天然带版本历史，可恢复到任一快照
  - `upload_folder` 支持断点续传与失败重试，适合大 checkpoint
- **只做 push / pull 原语 + 一个上下文管理器**：定时保存、训练框架 hook 等由调用方决定，工具不内置。CLI 与 Python API 共用 `core.py` 同一份逻辑。

## 协作模式假设

本工具按以下使用模式设计，超出这些假设的场景**不在支持范围内**：

- **单身份**：你和你的 coding agent 共用同一个 token、同一批私有仓库。多人权限协作、团队 ACL 不在设计范围
- **协作单位是 run 目录，不是整仓**：`Run.sync()` 只镜像推送 `runs/<name>/` 子树（镜像删除也限定在子树内，已核实 SDK 源码），并行跑多个实验（不同 run 名）是安全的
- **单 run 单写者**：同一个 run 名同一时刻只允许一个训练在写；不同 run 名可并行
- **新假设不需要历史**：`Run` 默认不拉取任何远端数据；只有显式 `resume=True` 才拉回同名 run 的子树续跑
- **repo = 项目边界**：不同项目用不同仓库（首次 push 自动创建，零成本）；同一项目的多个实验共用仓库、用 run 名区分

## Run / Checkpoint 管理（训练脚本内）

训练代码**不需要感知远端存储**，只感知 run 目录；`Run` 对象在关键节点触发同步：

```python
from mlstash import Run

# description 必填：写清本次 run 的意图，落在 run.json 元数据里
# 默认不拉取任何历史（新假设 = 新 run）；退出时自动修剪 + 推送本 run 子树
with Run("artifacts", name="exp1", description="baseline lr=0.01",
         repo="your-username/proj", keep_last=3) as run:
    for epoch in range(epochs):
        train_one_epoch(out=run.dir)
        run.log({"epoch": epoch, "loss": loss})     # 追加 metrics.jsonl
        if epoch % 5 == 0 or is_best:               # 关键节点才同步
            run.sync(f"epoch {epoch}, loss {loss:.3f}")

# 续跑（如 runtime 回收后）：显式 resume=True，只拉回 runs/exp1/ 子树
with Run("artifacts", name="exp1", description="baseline lr=0.01", resume=True) as run:
    start = load(run.latest_checkpoint()) if run.latest_checkpoint() else 0
    ...
```

目录约定：

```
artifacts/
  runs/
    exp1/
      run.json             # 元数据：name / description / created_at（生成后不覆盖）
      checkpoints/         # epoch=003.pt；best* 开头的文件永不修剪
      metrics.jsonl        # 每行 {"ts", ...}
```

原则：

- **一切属于某次运行的东西都进它的 run 目录**——同步单位就是 run 目录
- **每个 run 必须有意图描述**：`description` 是必填参数，写入 `run.json` 随产物一起同步
- **关键节点才 `sync()`**：epoch 结束、刷新 best、训练结束。不要每个 step 同步（同步是网络 IO）
- **保留策略**：本地只留最近 `keep_last` 个 checkpoint + `best*`；`sync()` 是本 run 子树的镜像推送（远端该子树与本地一致），被修剪的旧 checkpoint 仍可从远端历史 commit 找回
- **续跑**：`resume=True` 只拉回该 run 子树，用 `latest_checkpoint()` 定位断点；远端无此 run 时视为全新开始

## 作为库使用（通用产物目录）

训练代码**不需要感知远端存储**，只感知产物目录：

```python
from mlstash import stash

# 进入：自动 pull 恢复历史进度（首次运行则全新开始）
# 退出：自动 push（即使训练抛异常也推送，保住中间结果）
with stash("artifacts", repo="your-username/my-project-artifacts") as st:
    model = train(out_dir=st.path)   # 训练只往 st.path 写
    st.save("epoch 10, loss 0.32")   # 可选：训练中手动存一次快照
```

- 仓库/repo、token 解析规则与 CLI 相同（参数优先，缺省读环境变量）
- 进入时若远端仓库不存在，视为首次运行继续；其他错误（鉴权、网络）照常抛出
- 退出时 push 失败会直接抛异常（不打断原有异常的传播链，return False）

## Token 管理（一次性，本机）

token 的真实存放点只有一个：仓库根目录的 `.env.local`（已在 `.gitignore` 中，600 权限）。不进 git、不进代码、不进与 agent 的对话。

```bash
# 在 https://modelscope.cn/my/myaccesstoken 创建 SDK 令牌后，
# 编辑仓库根目录的 .env.local，取消注释并粘贴：
export MODELSCOPE_TOKEN=ms-xxx
```

使用时先 `source .env.local`（或由 agent 在执行命令前 source）。注入到 Colab runtime 走 colab CLI 的 `--env`（已实测支持）：命令里只写变量名 `$MODELSCOPE_TOKEN`，由本机 shell 展开，token 不出现在 agent 上下文中。

注意：`google.colab.userdata`（Secrets 面板）依赖 notebook 前端通道，**CLI/headless 模式下不可用**，仅当你也用 notebook 时才需要维护它。

## 端到端流程（Colab CLI 模式，命令已实测）

mlstash 以 git+https 直接从公开仓库安装（子目录包，无需凭证）：

```bash
# --- 每次训练任务（agent 驱动，在仓库根目录执行）---
# 1. 开 runtime，一行装好 mlstash
source .env.local
colab new -s train --gpu T4
colab install "git+https://github.com/mikewong23571/tools.git#subdirectory=mlstash"

# 2. 跑训练脚本；token 由本机 shell 展开注入，agent 只见变量名
#    --timeout 按训练时长设置（默认只有 30s）
colab exec -s train --timeout 86400 \
  --env "MODELSCOPE_TOKEN=$MODELSCOPE_TOKEN" \
  --env "MLSTASH_REPO=your-username/proj" \
  -f train.py

# 3. 结束释放
colab stop -s train
```

- `train.py` 内部用 `Run`（见上文"Run / Checkpoint 管理"），sync 由训练脚本在关键节点触发——**agent 不需要为"保存"单独发命令**
- runtime 被回收：重跑步骤 1–2 即可，训练脚本里 `Run(..., name="exp1", resume=True)` 只拉回该 run 断点续跑
- 结果回国内本机，只拉关心的那个 run：`mlstash pull artifacts --repo your-username/proj --subdir runs/exp1`
- 安装指定版本：git URL 后加 `@<tag或commit>`，如 `tools.git@v0.4.0#subdirectory=mlstash`

## 作为 CLI 使用（本机）

CLI 的真实用途在**本机**：推数据集、拉结果、手动查看。**runtime 上的同步由训练脚本内的 `Run` 完成，不依赖 CLI。**

```bash
# 保存：把产物目录推送到 ModelScope（训练循环中或结束后调用）
mlstash push artifacts --message "epoch 10, loss 0.32"

# 恢复：runtime 回收重开后拉回产物目录
mlstash pull artifacts

# 只拉取某个 run（run 级协作）
mlstash pull artifacts --subdir runs/exp1

# 恢复到指定版本
mlstash pull artifacts --revision <commit-sha>
```

- 路径参数缺省为 `./artifacts`
- `--repo` 参数优先于 `MLSTASH_REPO` 环境变量
- `.ipynb_checkpoints` 会被自动忽略
- 公开仓库的 `pull` 不需要 token；`push` 始终需要
- 成功退出码 0；用法错误 2（信息打在 stderr，方便 agent 解析）

## 本机直接训练（无 Colab）

```bash
mlstash pull artifacts || true   # 有历史进度则续上
python train.py --out artifacts  # 脚本内 Run.sync 在关键节点推送
mlstash push artifacts --message "final"
```
