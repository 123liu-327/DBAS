# 宿舍账单分摊管家后端

FastAPI 文件型后端，覆盖 F1–F11；F12 结算快照、确认与撤销按要求不实现。成员档案与入住记录已经分离：`Member` 是全局费用参与人，`Stay` 表示成员在某个账本中的入住关系，不包含登录认证。

## 安装、测试与启动

在 `backend` 目录使用项目已有环境：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m uvicorn --app-dir src app.main:app
```

也可运行：

```powershell
.\.venv\Scripts\python.exe -m uvicorn --app-dir src app.main:app --reload
```

启动后访问：

- `http://127.0.0.1:8000/health`
- `http://127.0.0.1:8000/docs`

不要使用缺少 FastAPI、filelock 等依赖的全局 Python。依赖声明位于 `pyproject.toml`。

## 数据结构

```text
data/
├── sequences.json              # nextBookId、nextMemberId
├── members.json                # 全局 Member 档案
└── books/{bookId}/
    ├── book.json
    ├── stays.json              # 当前账本的入住关系
    ├── bills.jsonl
    └── attachments/
```

账本 ID 和成员 ID 是递增正整数；账单 ID 仍是字符串。`Bill.participants`、`payerId` 和分摊结果中的 `memberId` 都使用数字成员 ID。`ShareDetail` 查询时计算，不另建文件。

首次启动空数据目录会注入十个空演示账本，不创建虚构成员。可以通过 `DORMBILL_DATA_DIR` 指定目录，通过 `DORMBILL_SEED_DEMO_BOOKS=false` 关闭注入。

## 旧数据迁移

旧的逐账本 `members.json` 必须显式迁移。启动检测到旧结构时会停止并提示命令：

```powershell
.\.venv\Scripts\python.exe -m app.storage.migrate_members --data-dir data
```

迁移会创建全局 `members.json`、逐账本 `stays.json`，改写账单参与人、垫付人和权重键，并在数据目录旁保留带时间戳的完整备份。迁移时应停止应用。

更早的字符串账本 ID 格式使用：

```powershell
.\.venv\Scripts\python.exe -m app.storage.migrate `
  --source .\examples\legacy-data --target .\converted-data
```

## 文档

- [API](docs/API.md)
- [F1–F5 手工测试说明](docs/MANUAL_TEST.md)
- [前端响应设计](docs/FRONTEND_RESPONSE_DESIGN.md)
- [项目说明](docs/PROJECT.md)
- [提交自检](docs/SELF_CHECK.md)

除 CSV 和附件下载外，成功响应使用 `code/message/data`，错误使用 `error.code/message/field`，删除返回空响应体的 HTTP 204。

## 核心代码阅读与人工改写

见 [人工改写清单](docs/HANDWRITTEN_PLAN.md)：37/93 个核心设计单元（39.8%）已使用 `##以下为手写` 和 `##手写区域结束` 标出。其余区域默认 AI 生成，底层存储不纳入手写范围。验收结果见 [自检报告](docs/SELF_CHECK.md)。测试使用临时数据目录，不依赖迁移备份目录。
