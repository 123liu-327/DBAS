# 核心代码人工改写清单

更新日期：2026-09-21。

## 标识约定与比例

源码仅在选定区域添加 `# 以下为待手写区域` 和结束标记，保留可运行参考实现。当前标记不代表已经由学生手写；完成本人改写后，才改成 `# 以下为手写`，并记录实际改动和验证结果。其余区域按本次约定默认归为 AI 生成，不逐段添加标签。底层 `storage` 和 `crud` 不纳入本次手写范围。

统计口径为 `models`、`schemas`、`services`、`algorithms` 中的顶层类和函数，类内方法及嵌套函数不重复计数。共 93 个设计单元，选中 37 个（39.8%）。这是核心设计单元的选择比例，不是全项目代码行占比，也不是已完成的人工贡献比例。

## 选定区域

| 文件 | 类或函数 | 当前状态 |
| --- | --- | --- |
| `src/app/services/book_service.py` | `create_book`、`update_book` | 待手写 |
| `src/app/services/bill_service.py` | `create_bill`、`update_bill`、`list_bills`、`detail`、`monthly_shares`、`preview` | 待手写 |
| `src/app/services/stay_service.py` | `update_stay` | 待手写 |
| `src/app/services/splitting_service.py` | `validate_members`、`calculate_shares` | 待手写 |
| `src/app/services/settlement_service.py` | `settlement_plan` | 待手写 |
| `src/app/algorithms/splitting.py` | `overlap_days`、`allocate_cents`、`split_bill` | 待手写 |
| `src/app/algorithms/settling.py` | `min_transfers` | 待手写 |
| `src/app/models/bill.py` | `SplitMethod`、`BillStatus`、`BillPeriod`、`Bill` | 待手写 |
| `src/app/models/member.py` | `Member` | 待手写 |
| `src/app/models/stay.py` | `StayInterval`、`Stay` | 待手写 |
| `src/app/schemas/bill.py` | `BillFields`、`BillCreate`、`BillPatch`、`BillItem`、`BillPage`、`BillShareItem`、`BillParticipant`、`BillDetail`、`BillPreview`、`MemberShare`、`MonthlyShares` | 待手写 |
| `src/app/schemas/common.py` | `PageParams`、`PageData` | 待手写 |
| `src/app/schemas/book.py` | `BookDetail` | 待手写 |

## 实施顺序

1. 模型与响应：理解 Member/Stay 分离、账单状态、请求字段、分页和组合详情。保留 API camelCase 契约。
2. 账单管理：创建、修改、预览、月份筛选、详情和月累计，保证跨账本隔离与状态限制。
3. 分摊与结算：日期交集、最大余数、权重验证、净余额及最少转账；保持整数分守恒。

不要求删除参考实现后才能练习。每次人工修改一小块，再运行对应测试，避免将所有函数一次性留空。

## 人工修改记录模板

| 实际完成日期 | 文件和函数 | 本人实际改动 | 原 AI 实现的问题或改写理由 | 测试证据 |
| --- | --- | --- | --- | --- |
| 待填写 | 待填写 | 待填写 | 待填写 | 待填写 |

不得把本清单当作已完成的“使用大模型后人工修改代码一览表”。课程附件模板未提供，本表仅供记录后转填。

## 验证

在 backend 目录运行 `python -m pytest`；静态检查运行 `ruff check src tests`。T01–T12、S01–S08 的现有用例与 HTTP 测试一起执行。F12 快照、确认、撤销及结清后防重复结算仍不在实现范围。
