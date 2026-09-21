# 核心服务函数核查与补全计划

## 当前核查结果

本计划只针对后端核心函数，不涉及前端或交付打包。当前 `backend/src/app/services` 与 `backend/src/app/algorithms` 中没有 `pass`、`TODO`、省略号或 `NotImplemented` 的函数体；下面列出的函数**在当前版本均已实现**。如果课程另有带留白的代码版本，应以那份文件为准，再按本清单补全。

## 三步核查与补全

| 步骤 | 重点函数 | 留白版本需要补齐的行为 | 验收 |
| --- | --- | --- | --- |
| 1. 账本与账单管理 | `book_service.create_book/update_book`；`bill_service.create_bill/update_bill/list_bills/detail/monthly_shares` | 创建、修改与文件 CRUD 对接；草稿补齐入账；按月筛选；修改后重新计算分摊；保留 `createdAt` 并更新 `updatedAt`。 | 账本隔离、账单增删改查、草稿校验和时间戳接口测试通过。 |
| 2. 分摊服务 | `splitting_service.calculate_shares`；`algorithms.splitting.allocate_cents/split_bill` | 校验成员归属；实现 `EVEN`、`BY_DAYS`、`BY_WEIGHT`，按最大余数分配整数分，保证总额守恒。 | T01–T10 与非法周期、权重、零有效天数测试通过。 |
| 3. 结算服务 | `settlement_service.settlement_plan`；`algorithms.settling.min_transfers` | 按月份范围汇总 `POSTED` 账单，计算净余额及总和，生成最多六人的最少转账方案。 | T11–T12、S01–S08、跨月和草稿排除测试通过。 |

## 执行判断

当前版本无需填空；在 `backend` 运行一次 `python -m pytest` 即可验证上述函数，本轮测试结果见 [SELF_CHECK.md](SELF_CHECK.md)。若要补全另一份留白版本，先确认具体文件和函数头，再按三步移植实现与测试。F12 快照功能仍不在范围内。

## 人工改写区域

当前可运行实现已按 [核心代码人工改写清单](HANDWRITTEN_PLAN.md) 添加局部待手写标记，覆盖模型、响应结构、账单管理、分摊和结算。标记不是空函数，也不代表已完成人工修改。
