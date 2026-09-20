# F1–F5 手工测试说明

本文用于在 Swagger UI 中手工验收成员管理、账单录入、分摊、账单维护和结算报表。请求中的 `bookId`、`memberId`、`billId` 必须替换成接口实际返回值。

## 当前手工测试进度

你已经完成 F1 的前三项字段测试：

- [x] 新增成员时姓名必填且不超过 10 个字符；
- [x] 登记入住时入住日期必填；
- [x] 退宿日期可空，且不得早于入住日期。

接下来应从 F1 的“查询指定账本成员列表”开始，继续验证修改、删除保护、按天重算，然后依次测试 F2–F5。下文仍保留前三项的请求和预期，便于最后形成完整测试记录。

## 1. 启动与准备

在项目根目录启动：

```powershell
.\.venv\Scripts\python.exe -m uvicorn --app-dir src app.main:app --reload
```

打开 `http://127.0.0.1:8000/docs`。先调用 `GET /health`，预期 HTTP 200：

```json
{"code":200,"message":"success","data":{"status":"ok"}}
```

### 创建测试账本

调用 `POST /api/books`：

```json
{"name":"F1-F5手工测试","description":"Swagger 手工验收数据"}
```

预期 HTTP 201。记录响应中的数字 `id`，以下称为 `bookId`。

### 创建四个全局成员并登记入住

分别调用四次 `POST /api/members`：

```json
{"name":"张三"}
```

姓名依次使用张三、李四、王五、赵六，记录四个数字 `memberId`。然后分别调用 `POST /api/books/{bookId}/stays`：

```json
{"memberId":1,"joinDate":"2026-03-01","leaveDate":null}
```

后续示例假设四个成员 ID 依次为 `1、2、3、4`。实际操作必须使用刚才获得的 ID。

## 2. F1 成员管理

### 尚未完成的 F1 测试顺序

1. 查询当前账本入住成员列表；
2. 修改全局成员姓名；
3. 修改入住或退宿日期；
4. 创建按天账单并确认日期修改后重新计算；
5. 验证参加过账单的成员不能直接删除。

### 正常流程

1. `GET /api/books/{bookId}/stays?page=1&pageSize=10`：预期 `total=4`，每项同时包含 Stay 和 `member` 档案。
2. `GET /api/members/{memberId}`：预期 `stayCount=1`，`stays` 中包含当前账本。
3. `PATCH /api/members/{memberId}`，请求 `{"name":"张小三"}`：预期 HTTP 200，姓名改变，`createdAt` 不变，`updatedAt` 更新。
4. `PATCH /api/books/{bookId}/stays/{memberId}`，请求 `{"leaveDate":"2026-03-31"}`：预期 HTTP 200。
5. 再次 PATCH，传 `{"leaveDate":null}`：预期退宿日期被清空。

### 字段和删除保护

| 操作 | 请求 | 预期 |
| --- | --- | --- |
| 姓名缺失 | `POST /api/members`，`{}` | HTTP 422，字段为 `name` |
| 姓名超过 10 字 | `{"name":"12345678901"}` | HTTP 422 |
| 入住日期缺失 | `POST /stays`，只传 `memberId` | HTTP 422，字段为 `joinDate` |
| 退宿早于入住 | `joinDate=2026-03-10`、`leaveDate=2026-03-09` | HTTP 422 |
| 重复登记 | 相同 `bookId + memberId` 再 POST | HTTP 409，`STAY_EXISTS` |
| 删除仍有入住的 Member | `DELETE /api/members/{memberId}` | HTTP 409，`MEMBER_IN_USE` |

完成 F2 的账单创建后，再调用 `DELETE /api/books/{bookId}/stays/{memberId}`，预期 HTTP 409、错误码 `STAY_IN_USE`。修改 Stay 日期后重新查询按天账单详情，`effectiveDays` 和 `shareCents` 应使用最新日期重新计算。

## 3. F2 账单录入

当前 API 直接接收整数分 `amountCents`，因此 `62.35` 元应传 `6235`，可以精确表达最多两位小数且不会产生浮点误差。

### 保存前预览

调用 `POST /api/books/{bookId}/bill-previews`：

```json
{
  "title":"3月电费",
  "amountCents":6200,
  "date":"2026-03-31",
  "method":"BY_DAYS",
  "participants":[1,2,3],
  "payerId":1,
  "period":{"start":"2026-03-01","end":"2026-03-31"}
}
```

预期 HTTP 200，`shares` 合计为 6200，调用后 `GET /bills` 的数量不增加。

### 保存账单

把相同请求发送到 `POST /api/books/{bookId}/bills`。预期 HTTP 201，默认 `status=POSTED`，记录返回的 `billId`。

### 非法请求

| 场景 | 修改内容 | 预期 |
| --- | --- | --- |
| 名称缺失或超过 20 字 | 删除 `title` 或传 21 字 | HTTP 422 |
| 金额非法 | `amountCents` 为 0、负数、小数或布尔值 | HTTP 422 |
| 记账日期缺失 | 删除 `date` | HTTP 422 |
| 没有参与人 | `participants: []` | HTTP 422 |
| 垫付人不在参与人中 | `payerId: 4`、参与人 `[1,2,3]` | HTTP 422 |
| 成员没有当前账本 Stay | 使用其他账本成员 ID | HTTP 422，`STAY_NOT_FOUND` |
| BY_DAYS 无周期 | 删除 `period` | HTTP 422 |
| 周期倒置 | `start` 晚于 `end` | HTTP 422 |
| BY_WEIGHT 权重缺失 | 权重没有覆盖每位参与人 | HTTP 422 |
| BY_WEIGHT 权重非正整数 | 权重为 0、负数或小数 | HTTP 422 |

权重账单示例：

```json
{
  "title":"公共用品",
  "amountCents":5000,
  "date":"2026-03-20",
  "method":"BY_WEIGHT",
  "participants":[1,2],
  "payerId":2,
  "weights":{"1":2,"2":1}
}
```

## 4. F3 分摊计算

手工检查时，对预览或账单详情中的 `shares[].shareCents` 求和，必须等于 `bill.amountCents`。

| 用例 | 金额 | 权重或天数 | 预期分摊 |
| --- | ---: | --- | --- |
| T01 EVEN | 60000 | 1:1:1 | 20000, 20000, 20000 |
| T02 EVEN | 10000 | 1:1:1 | 3334, 3333, 3333 |
| T03 EVEN | 10000 | 1:1:1:1 | 2500, 2500, 2500, 2500 |
| T04 EVEN | 10001 | 1:1:1:1 | 2501, 2500, 2500, 2500 |
| T05 BY_DAYS | 6200 | 31:31 | 3100, 3100 |
| T06 BY_DAYS | 6200 | 31:21:31 | 2316, 1569, 2315 |
| T07 BY_DAYS | 7000 | 10:30:30 | 1000, 3000, 3000 |
| T08 BY_DAYS | 5000 | 0:10:10 | 0, 2500, 2500 |
| T09 BY_WEIGHT | 5000 | 2:1 | 3333, 1667 |
| T10 BY_WEIGHT | 4000 | 3:1 | 3000, 1000 |

自动复核命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_splitting.py -q
```

## 5. F4 账单查询与维护

先创建至少三笔账单：两笔记账日期为 `2026-03`，一笔为 `2026-04`。

1. `GET /api/books/{bookId}/bills?page=1&pageSize=10`：预期返回三笔。
2. 加 `month=2026-03`：预期只返回两笔，`total=2`。
3. 加 `month=2026-04`：预期只返回一笔。
4. `GET /api/books/{bookId}/bills/{billId}`：核对 `bill`、`payer`、`participants` 和 `shares`。
5. `PATCH /api/books/{bookId}/bills/{billId}`，传 `{"amountCents":8300}`。
6. 再查详情：`createdAt` 不变、`updatedAt` 更新，所有分摊之和变为 8300。
7. `GET /api/books/{bookId}/statistics/member-shares?month=2026-03`：把每笔三月账单详情中同一成员的分摊相加，应与这里的 `shareCents` 一致。
8. `DELETE /api/books/{bookId}/bills/{billId}`：预期 HTTP 204；再次查询该 ID 返回 404。

草稿验证：创建 `{"status":"DRAFT","title":"待补账单"}`，它可以出现在账单列表，但不能计入月度累计、结算和 CSV。字段不完整时 PATCH 为 `POSTED` 应返回 422。

## 6. F5 结算报表与 T11–T12

使用四名成员创建三笔 `2026-03` 的 EVEN 账单：

| 账单 | 金额（分） | 垫付人 | 参与人 |
| --- | ---: | --- | --- |
| 电费 | 40000 | 成员 1 | 1、2、3、4 |
| 水费 | 20000 | 成员 2 | 1、2、3、4 |
| 纸巾 | 10000 | 成员 3 | 1、2、3 |

调用 `POST /api/books/{bookId}/settlement-plans`：

```json
{"startMonth":"2026-03","endMonth":"2026-03"}
```

T11 预期四人的 `netCents` 按成员顺序为：

```text
21666, 1667, -8333, -15000
```

同时满足：

- `netSumCents = 0`；
- `balanced = true`；
- `transfers` 是金额为正的可执行转账；
- 本例最少转账笔数为 3。

T12 手工核对方法：建立 `memberId -> netCents` 表。对每条转账执行：

```text
付款人的余额 += amountCents
收款人的余额 -= amountCents
```

执行全部转账后，每位成员余额都必须为 0。再新增四月账单，分别请求三月范围和三月至四月范围，确认月份过滤正确；草稿不得进入余额。

自动复核命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_reports_attachments_api.py -k "t11_t12 or settlement" -q
```

## 7. 测试记录建议

每个用例记录：测试日期、接口、请求 JSON、HTTP 状态码、实际响应、是否通过。异常用例重点保留 `error.code/message/field`；分摊和结算用例保留金额求和过程。完成后删除“F1-F5手工测试”账本，若账本仍有关联 Stay 或账单，需先删除账单，再删除 Stay，最后删除账本和不再使用的全局 Member。
