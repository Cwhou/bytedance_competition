# CUA-Lark（M1）

本文件汇总 **M1 单步阶段** 的交付内容、使用方式与注意事项，与《cua-lark_test_agent开发计划》中的 M1 里程碑对齐。

---

## 一、交付内容概览

| 类别 | 内容 |
|------|------|
| **脚手架** | `pyproject.toml`、`.env.example`、可编辑安装的 Python 包 `cua-lark`（入口脚本 `cua-lark`） |
| **Bridge（Node）** | `bridge-node/worker.mjs`：stdin 一行一条 JSON 指令；stdout 仅输出 JSONL；日志走 stderr；`GUIAgent` + `NutJSOperator` 单例；JSON 的 `op` 支持 `run` / `pause` / `resume` / `stop` / `shutdown`（与下方 **CLI 调用方式** 不是一回事） |
| **Bridge 加载方式** | 通过环境变量 **`UI_TARS_DESKTOP_ROOT`**（运行期由 Python 注入）从该路径下 `packages/ui-tars/sdk/dist`、`packages/ui-tars/operators/nut-js/dist` **动态 import**，无需在 `bridge-node` 下单独安装 `@ui-tars/*` |
| **Python** | `src/cua_lark/`：`config`、`schemas`、`state`、`tools/bridge.py`（`BridgeClient`）、`nodes/*`、`graph.py`（最小状态图）、`cli.py` |
| **LangGraph 流程** | `START → load_case → execute → verify → report → END`（无独立 `plan` 节点、无 Checkpoint） |
| **用例** | `cases/im/` 下 **5 条** IM 单步 YAML：`m1_click_messages_tab`、`m1_click_contacts_tab`、`m1_click_search`、`m1_click_calendar_tab`、`m1_click_workspace_tab` |

---

## 二、使用方式

### 2.1 前置条件

1. **UI-TARS-desktop**（与 `cua-lark` 为**兄弟目录**时，可不设 `UI_TARS_DESKTOP_ROOT`；否则请在 `.env` 中设为该仓库根目录的**绝对路径**）。
2. 在 `UI-TARS-desktop` 根目录执行 **`pnpm install`**，确保各包 `prepare` 已构建出 **`dist`**（含 `sdk` 与 `operator-nut-js`）。
3. **Python 3.10+**，本机已安装 **Node.js**（`node` 在 PATH 中）。

### 2.2 安装 Python 包

在 `cua-lark` 目录下：

```bash
cd cua-lark
pip install -e .
```

若完整安装时 pip 解依赖报错，可先安装运行时依赖，再仅安装本包（不重新解依赖）：

```bash
pip install langgraph langchain-core langchain-openai pydantic-settings typer rich pillow pyyaml python-dotenv
pip install -e . --no-deps
```

### 2.3 环境变量

**「复制 `.env.example` 为 `.env`」是什么意思？**  
在 `cua-lark` 目录里**再建一个配置文件**，内容与 `.env.example` 相同，但**文件名改成 `.env`**。`.env.example` 是仓库里的**模板**（不含真实密钥，可提交 Git）；`.env` 放你自己的密钥，一般**不要提交**（若 `.gitignore` 已忽略 `.env` 则更安全）。程序启动时会读取 **`.env`**（见 `pydantic-settings` / `python-dotenv`）。

在资源管理器中可复制粘贴后重命名，或在终端执行：

```bash
# macOS / Linux / Git Bash
cp .env.example .env
```

```powershell
# Windows PowerShell（在 cua-lark 目录下）
Copy-Item .env.example .env
```

然后编辑 **`.env`**，至少填写：

- **`VLM_API_KEY`**：火山方舟 / OpenAI 兼容接口密钥（须为 **ASCII**，勿把中文说明当密钥）。
- **`VLM_BASE_URL`**、**`VLM_MODEL`**：可按 `.env.example` 默认或按你的方舟配置修改。
- **`UI_TARS_DESKTOP_ROOT`**（可选）：填 **UI-TARS-desktop 仓库根**（含 `packages/ui-tars`），不是 `cua-lark`。与 `cua-lark` 为兄弟目录时可不写。**不要**写 `UI_TARS_DESKTOP_ROOT=` 且右侧留空（易被解析成当前目录，进而报 `cua-lark\packages\ui-tars\...` 找不到）；不需要自定义时直接删掉该变量。代码侧已将空串视为未设置并回退到兄弟目录推断。

### 2.4 运行用例

当前 CLI 只有一个 Typer 命令，**第一个参数直接写用例 YAML 路径**，中间**不要**再加子命令 `run`（否则 `run` 会被当成文件路径，报错 `File 'run' does not exist`）。

```bash
cua-lark cases/im/m1_click_messages_tab.yaml
```

Windows PowerShell 示例：

```powershell
cua-lark cases\im\m1_click_messages_tab.yaml
```

查看帮助：`cua-lark --help`。

运行前请保证：**飞书客户端已打开**、窗口可操作；模型与网络可用。

### 2.5 输出

- 报告路径：**`reports/runs/<写入时间>_<yaml文件名不含扩展名>/report.md`**（时间在 `report` 节点写入时生成，含微秒以避免同用例连续运行目录冲突）
- Bridge 调试信息会出现在**终端（stderr）**，不混入 JSONL 协议行。

---

## 三、说明

### 3.1 M1 范围与后续里程碑

以下项**未在 M1 实现**（见开发计划 M2 及以后）：

- 独立 **Planner** 节点、**SqliteSaver Checkpoint**、**replay / report / doctor** 全量子命令  
- Verifier 的 **OCR 故障回退**、**Reflector** 自愈、多步循环与条件边扩展  

### 3.2 Bridge 单行长度（为何曾出现「执行失败」但 Node 日志已是 end）

Node 在 `done` 事件里会带上 `last_screenshot_base64`，一行 JSON 可达数 MB。Python `asyncio` 默认 **`readline()` 单行上限为 64 KiB**，超过会报 `Separator is not found, and chunk exceed the limit`，导致 Python 侧收不到 `done`、执行节点判失败。当前已在 `BridgeClient` 子进程上提高 **`limit`**（约 32 MiB）。若仍超限，可在后续版本改为截图落盘、stdout 只传路径。

### 3.3 执行与断言的成功判定

- **执行（Bridge / GUIAgent）**：以结束状态为 **`end`** 作为 **`ok: true`**（与 UI-TARS 的 `StatusEnum.END` 一致）。  
- **断言（Verify）**：另一次 VLM 调用，根据截图与 YAML 中 `asserts` 的 `query` 判断；与真实界面、模型稳定性强相关，可能出现「执行成功但断言失败」。

### 3.4 本地验证 Bridge 时的注意点

单独启动 `worker.mjs` 且不输入任何内容时，进程会**阻塞等待 stdin**，属正常行为；验证链路请优先使用 **`cua-lark <某条 yaml>`**（见 §2.4）端到端跑通。

### 3.5 目录布局约定

默认假定磁盘布局为：

```text
<workspace>/
  UI-TARS-desktop/     # pnpm install 过
  cua-lark/            # 本仓库
```

若你的 `cua-lark` 与 `UI-TARS-desktop` 不同级，务必设置 **`UI_TARS_DESKTOP_ROOT`**。

---

## 四、Bridge 协议（摘要）

- **Python → Node**：向子进程 stdin 写入一行 JSON，例如：`{"op":"run","instruction":"...","maxLoopCount":15}`  
- **Node → Python**：stdout 每行一条 JSON；业务上以 **`type":"done"` 且 `op":"run"`** 作为单次 `run` 结束；执行结果中含 `ok`、`status`、`last_screenshot_base64`（可能较大）等字段。  
- 子进程 **`cwd`** 为 `UI_TARS_DESKTOP_ROOT`，与动态 import 路径一致，便于解析传递依赖。

更多架构与路线图见仓库根目录 **`cua-lark_test_agent开发计划.md`**。
