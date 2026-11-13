# 进阶邮件单标签与多标签分类比较

| 方法 | 识别业务意图 | 漏检业务意图 | 覆盖率 |
|---|---|---|---:|
| 单标签 | registration_inquiry | accommodation_inquiry, invoice_request | 33% |
| 多标签 | registration_inquiry, accommodation_inquiry, invoice_request | 无 | 100% |

## 分析

单标签分类只识别出一个业务主题，遗漏了同一封邮件中的住宿和发票请求；多标签分类完整覆盖注册、住宿和发票三类业务意图。

单标签方法会压缩邮件中并列的业务主题，适合只记录一个工单主类别的场景；多标签方法更适合跨部门协作的复杂咨询邮件。
