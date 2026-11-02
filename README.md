# 企业采购报价审核 Agent

面向原材料、模具和设备采购的本地报价审核工具。上传多家供应商的 Excel、CSV 或 JSON，得到有原始证据的比价表、风险清单、中文采购建议和可重算的人工复核记录。

**当前交付：V1 本地单人试用版。** 数值、评分和风险门禁由确定性程序完成，无需配置大模型 API Key。当前网页版仅监听本机 `127.0.0.1`；企业多人使用、账号权限和审批身份认证属于后续部署阶段。

## 直接使用

Windows 双击仓库根目录的 **启动采购审核.cmd**，浏览器访问 `http://127.0.0.1:8511`。首次启动会在项目目录建立 `.venv` 并安装依赖，需要网络；安装后报价处理可在本机完成。

也可在 PowerShell 中运行：

```powershell
pwsh -NoProfile -File scripts/install.ps1
pwsh -NoProfile -File scripts/start.ps1
```

网页操作：上传报价 → 可选上传历史采购/报价、市场参考 → 设置权重和分析日期 → 生成审核结果 → 下载 JSON、Excel、中文建议或复核模板。页面提供三类采购模拟样例用于体验。关闭启动终端后，重新执行启动文件即可恢复服务。

生成可直接填写的 Excel 输入模板：

```powershell
.venv/Scripts/python.exe -m procurement_agent templates
```

默认保存到 `output/当天日期/templates/`。模板内所有报价均为模拟数据。已有旧版最小字段样例仍可读取；由于其税价、规格、数量等信息不足，V1 会要求补全，不能直接用于最终建议。

## 已实现的审核流程

| 环节 | 当前行为 |
|---|---|
| 读取 | CSV 支持 UTF-8/BOM 与 GB18030；Excel 多工作表，识别表头前最多30行说明；JSON 支持单条、数组或 quotes/records 包装 |
| 字段 | 供应商、物料、规格配置、数量单位、币种、含税/未税单价总价、税率、运费安装费、交期、付款、质保等；支持常见中文表头 |
| 证据 | 保留原值、文件 SHA256、实际工作表/单元格、CSV 行、JSON 路径；Excel 公式需要人工确认数值 |
| 统一口径 | 明确单价/总价、税率、附加费含税口径和各自税率后计算；空白费用保留为未知 |
| 可比性 | 逐物料检查规格、配置、品牌、材质、牌号、数量、单位、币种和账期起点；差异报价进入人工复核 |
| 评分 | 价格50%、交期30%、账期20%，可以配置；展示每项得分贡献；并列第一保留人工选择 |
| 价格证据 | 本批有效报价、匹配的企业历史采购、同供应商历史报价、有效市场参考分别计算；不相关、过期和重复参考列明排除原因 |
| 风险判断 | 正常、低价已解释、异常低价、高价配置/服务已解释、信息不足五类；解释需具名复核及书面证据引用 |
| 输出 | 综合 JSON、含证据和复核日志的 Excel、中文采购建议；所有投影遵循同一决策状态 |
| 人工闭环 | 复核文件绑定输入及规则摘要，修改后全量重算；保留原始值、修正值、原因、人员、时间和证据 |

任何未闭环的关键缺项、不可比条件、异常低价或其他阻断风险，会使整批结果显示“待人工复核”。可以查看候选人和评分，但各处的推荐字段均为空。风险闭环后输出**供人工审批的条件性建议**。本程序没有定标、订单、付款、签约或供应商发送接口。

## 输入约定

完整字段、接口及输出契约见 [DATA_CONTRACT.md](docs/DATA_CONTRACT.md)。推荐从输入模板开始：每行代表一家供应商对一个采购项的有效报价，同一供应商的不同版本需先选定有效版本。

核心字段：

```text
supplier,item_id,item_name,category,specification,configuration,
quantity,unit,currency,unit_price_excl_tax,tax_rate,
freight,installation,fee_basis,freight_tax_rate,installation_tax_rate,
lead_time_days,payment_days,payment_terms,payment_anchor,
warranty_months,scope_complete,quote_date,valid_until
```

采购类型 `category`：`raw_material`、`mold`、`equipment`，也接受“原材料”“模具”“设备”。税率接受 `13%`、`13` 或 `0.13`。报价范围完整填 `true` 或“是”。明确不适用的费用可填0或“不适用”；实际未确认的费用应留空。

`unit_price_excl_tax` 可由含税单价或明确总价替代。`freight` 等另列费用按**整条报价一次**计入，货品总价应不含这些另列费用。非零费用需填 `fee_basis=excl_tax/incl_tax` 和其自身税率；不将货品税率自动套给运费、安装费。

历史/市场记录须有同口径物料、数量、单位、规格、币种、完整范围及费用信息，并提供 `record_date`。历史记录须明确 `record_type=purchase`（企业已采购）或 `quotation`（供应商历史报价）。本批报价本身不能作为独立历史或市场证据。市场参考是用户提供的数据，本程序不自动采集行情。

## 计算方法

统一未税总成本 = 未税货品单价 × 数量 + 另列未税费用。含税现金支出另行列出；程序不推定企业可抵扣税额。含税与未税总价按金额精度直接核对，避免大数量掩盖税价矛盾。

价格得分 = 本物料最低可计算未税总成本 ÷ 本报价成本 × 价格权重 ×100。

交期得分 = 最短交期 ÷ 本报价交期 × 交期权重 ×100；零天交期使用明确的零值规则。账期得分 = 本报价账期 ÷ 最长账期 × 账期权重 ×100；全部零账期时该项同分。先按未舍入得分排名，再格式化展示。

偏离率 =（本报价金额 − 同口径参考中位数）÷ 参考中位数。默认低/高价阈值20%，历史时效365天，市场时效90天。这些是可配置的初始筛查规则，需按物料类别和企业制度调整。正常分类表示在当前证据和规则下未触发异常，并非对市场公允价或供应商真实性的认证。

```json
{"low_threshold":0.2,"high_threshold":0.2,"history_max_age_days":365,"market_max_age_days":90,"require_full_package":false}
```

`require_full_package=true` 检查每家供应商是否覆盖整包物料。默认按物料独立比较，不把不同物料或币种混成一个总排名。阶段付款及预付条款需人工确认其标准化账期，原付款条款始终保留。

## 命令行与演示

```powershell
pwsh -NoProfile -File scripts/run-demo.ps1
```

生成正常报价、异常低价报告和输入模板，位置为 `output/当天日期/`。演示分析日期固定为2026-11-02，使模拟参考的时效可复现。

```powershell
.venv/Scripts/python.exe -m procurement_agent compare --quotes samples/v1/quotes.json --history samples/v1/history.json --market samples/v1/market.json --as-of 2026-11-02 --output output/2026-11-02/comparison.json --report output/2026-11-02/comparison.xlsx --advice output/2026-11-02/采购建议.md --review-template output/2026-11-02/review.json
```

`--quotes`、`--history`、`--market` 均可跟多个文件。`--weights weights.json` 设置三项合计1的权重；`--policy policy.json` 设置阈值及时效。JSON 中每条报价都有稳定 `quote_id`，用于复核定位。

## 人工复核并重新计算

下载/导出复核模板，保留 `input_digest`，填写人员、带时区时间、具体修正或解释。示例中的报价编号和摘要必须换成当前模板的真实值：

```json
{
  "input_digest":"从本批模板保留的摘要",
  "reviewer":"采购复核人",
  "reviewed_at":"2026-11-02T15:00:00+08:00",
  "corrections":[
    {"quote_id":"本批报价编号","field":"freight","value":0,"reason":"供应商书面确认运费已含","evidence":"确认函编号及页码"}
  ],
  "explanations":[
    {"quote_id":"本批报价编号","kind":"low_price","reason":"已核实的低价具体原因","evidence":"折扣说明及技术范围确认文件编号"}
  ]
}
```

解释类型支持 `low_price`、`premium`、`payment_terms`。说明低价原因不能同时清除缺失费用或技术不一致；这些业务字段需提供依据后修正，再由相同规则重新校验。多轮复核应保留累计修正，程序每次对原始输入完整回放。

将复核JSON上传到网页复核区域重新计算，或在原命令增加 `--review 已填写的复核.json`。改变报价内容、历史/市场输入、分析日期、权重或阈值后须重新生成匹配的模板。复核人是本地自报身份，记录不等同于企业审批签名。

## 数据与部署边界

报价处理在本机进行。网页上传副本保存在会话临时目录，正式留档请保存原文件并下载 JSON、Excel、建议及累计复核文件；命令行输出保存在指定目录。正式企业多人上线需要增加持久化证据库、账号认证、审批授权、备份和运维。

仓库在本次实施时被 GitHub 标记为公开。提交内容只包含程序、说明、测试和模拟数据；真实价格、合同、供应商身份和凭证应放在仓库外。`output/`、`.venv/`、生成Excel和密钥文件已加入忽略规则。

第一版支持表格型结构化输入。任意版式报价、扫描件、图片OCR、原材料牌号语义匹配、设备/模具技术等效评估、供应商履约数据、全生命周期成本及ERP/SRM仍见 [路线图](docs/ROADMAP.md)。

## 开发与验证

```powershell
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -m ruff check procurement_agent tests
$env:PYTHONPATH = "$PWD/rfqdiff-upstream"
.venv/Scripts/python.exe -m pytest rfqdiff-upstream/rfqdiff-tests -q
```

测试覆盖不同输入格式、实际单元格证据、异常值、税费、历史匹配、跨来源污染、人工复核、推荐门禁、报表及网页。具体执行结果见 [验证记录](docs/VERIFICATION.md)。项目按 Trellis 保存需求、设计、实现及验证记录。

## 来源与许可证

企业计算流程和本仓库新增代码采用 MIT。价格/交期/账期比例评分基于保留的 MIT `rfqdiff` 规则，增加 Decimal 精度、零交期、风险门禁等企业处理；上游回归测试保留。业务 Skill 的上游版本没有明确许可证，商业复用和再分发应按原仓库授权情况确认。来源、固定提交及边界见 [UPSTREAM.md](docs/UPSTREAM.md)。
