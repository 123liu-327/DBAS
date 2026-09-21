# 宿舍账单分摊管家：项目说明

## 架构

| 层 | 职责 |
| --- | --- |
| `src/app/api`、`src/app/schemas` | 请求解析、分页参数、前端响应结构 |
| `src/app/services` | 组合 Member、Stay、Bill，执行状态与跨资源校验 |
| `src/app/crud` | 对全局成员、逐账本入住、账本和账单做文件 CRUD |
| `src/app/algorithms` | 最大余数分摊、在住天数、最少转账纯计算 |
| `src/app/storage` | 安全路径、JSON/JSONL、文件锁、临时文件原子替换和迁移 |

简单成员和账本操作由 CRUD 完成；账单、入住日期影响、统计和结算通过服务协调。F12 快照、确认与撤销不实现。

## 核心模型

- `Member(id, name, createdAt, updatedAt)`：全局费用参与人，不是登录用户。
- `Stay(bookId, memberId, joinDate, leaveDate, createdAt, updatedAt)`：复合主键入住关系。
- `Bill`：保留字符串账单 ID，参与人和垫付人引用数字 Member ID。
- `ShareDetail`：详情、预览和统计时计算，不写入数据文件。
- `MemberBalance`、`Transfer`：无持久化结算建议。

```text
data/
  sequences.json
  members.json
  books/{bookId}/book.json
  books/{bookId}/stays.json
  books/{bookId}/bills.jsonl
  books/{bookId}/attachments/
```

全局锁保护数字 ID 分配和 Member 更新；逐账本锁保护 Stay、Bill 与附件。创建 Stay 时按“全局锁 → 账本锁”顺序取得锁，防止成员删除与入住创建产生孤立引用。写文件使用同目录临时文件、`fsync` 和 `os.replace`。

## 业务规则

- Member 姓名最长 10 字，可重名；存在任意 Stay 时不能删除。
- 同一成员在一个账本只能有一条 Stay；`leaveDate` 不得早于 `joinDate`。
- 已参与该账本账单的 Stay 不能删除；删除 Stay 不删除 Member。
- 账单垫付人和参与人必须具有当前账本 Stay。
- `EVEN`、`BY_DAYS`、`BY_WEIGHT` 均使用整数分和最大余数法，结果金额守恒。
- `BY_DAYS` 使用账单周期和 Stay 的闭区间交集天数。
- 草稿不进入月度分摊、结算建议或 CSV。
- Member 改名不会改写历史账单，组合查询和导出实时读取最新档案。

## 迁移与限制

启动只检测旧的逐账本 `members.json`，不会自动改写。`app.storage.migrate_members` 在应用停止时复制到暂存目录、转换成员和账单引用、验证分摊后交换目录，并保留原目录备份。旧 `(bookId, oldMemberId)` 分别映射为新的全局数字成员，不按姓名合并。

文件后端适合课程规模。分页和聚合需要扫描文件，多文件组合查询不提供数据库事务快照。结算建议不会修改账单状态或记录付款。

## 请求链路与改写入口

启动时 create_app 注册 `/api` 路由、依赖和统一异常处理。创建账单经过 BillCreate → bill_service.create_bill → Bill 校验 → splitting_service → 纯算法 → bill_crud → FileStore。详情查询组合 Bill、全局 Member、账本 Stay 和即时 ShareDetail，再由 ApiResponse 输出。

同一 Book 可以包含多笔 Bill，月份筛选依据 Bill.date，先筛选再分页。结算建议仅读取 POSTED，月累计排除 DRAFT。数据修改操作的具体锁范围以服务和 CRUD 实现为准，文件原子替换不等同于多文件数据库事务。

人工改写范围、计数方法与待填写的实际修改记录见 [HANDWRITTEN_PLAN.md](HANDWRITTEN_PLAN.md)。
