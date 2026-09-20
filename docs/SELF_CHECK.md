# 个人项目提交自检

在项目 `.venv` 中执行：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\ruff.exe check src tests
```

结果为 **76 passed**、**All checks passed**。

## 功能核对

| 功能 | 结果 | 主要证据 |
| --- | --- | --- |
| F1 成员管理 | 已覆盖 | 全局数字 Member CRUD、Stay CRUD、删除保护、并发 ID |
| F2 账单录入 | 已覆盖 | 默认 POSTED、草稿补齐、预览和字段校验 |
| F3 分摊计算 | 已覆盖 | T01–T10、最大余数、金额守恒、无有效天数 |
| F4 账单维护 | 已覆盖 | 月筛选、分页、组合详情、修改重算、月累计 |
| F5 结算报表 | 已覆盖 | T11–T12、跨月、草稿排除、余额归零 |
| F6 CSV | 已覆盖 | 固定表头、UTF-8、逐账单守恒、最新成员姓名 |
| F7 多账本 | 已覆盖 | Stay 隔离、账单引用校验、非空删除保护 |
| F8 文件并发 | 已覆盖 | 跨进程锁、并发数字 ID、写入失败保留旧文件 |
| F9 最少转账 | 已覆盖 | S01–S08 |
| F10 趋势 | 已覆盖 | 六个月、空月份、人均支出 |
| F11 附件 | 已覆盖 | 格式、大小、数量、隔离、下载和删除 |

## 本次成员与入住整改

- [x] `Member` 只保存全局档案，主键为递增数字。
- [x] `Stay` 以 `(bookId, memberId)` 唯一定位并保存入住日期。
- [x] 全局 `/api/members` 与账本 `/api/books/{bookId}/stays` 均分页。
- [x] 原逐账本 `/members` 路由不再出现在 OpenAPI。
- [x] 账单参与人、垫付人、权重、分摊、余额和转账统一使用数字成员 ID。
- [x] BillDetail 和 BookDetail 返回组合后的 Member、Stay 与分摊信息。
- [x] 改名后历史账单详情实时显示新姓名。
- [x] 已参与账单的 Stay 不能删除；仍有 Stay 的 Member 不能删除。
- [x] `LOCKED/SETTLED` 账单禁止会改变分摊的 Stay 日期修改。
- [x] 旧逐账本成员数据必须显式迁移；测试验证备份、引用改写和分摊守恒。

## 未实施

F12 的快照创建、成员确认、撤销以及 `LOCKED → SETTLED` 业务流转仍未实现，也没有对应路由。当前结算接口只计算建议，不记录付款；模型中的 `LOCKED/SETTLED` 仅用于预留状态和防护校验。
