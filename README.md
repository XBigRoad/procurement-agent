# Enterprise Procurement Agent

企业采购报价审核与采购建议 Agent 的组合工程。

本仓库把采购 Skill 和确定性报价引擎组合起来，并加入制造业采购第一批扩展：

- 采购业务 Skill：RFQ、报价比较、TCO、谈判、供应商评分和管理汇报。
- 确定性比价内核：CSV / JSON / XLSX 输入、显式权重、可解释评分、来源追溯和报告导出。
- 价格合理性扩展：对比本批报价和历史价格，提示异常低价、高价、缺项和信息不足。
- 当前 MVP 还不做 PDF / 图片 OCR，也不自动判断模具和设备的技术等效性；真实报价必须先整理成标准字段。

## 当前可运行能力

```text
报价 CSV / JSON / Excel
        ↓
统一字段和币种检查
        ↓
价格、交期、付款条件评分
        ↓
历史价格偏离分析
        ↓
综合 JSON + Excel 报告
```

第一版不自动执行：下单、付款、签合同、最终定标、向供应商发送未经人工审核的承诺。

## 安装

建议 Python 3.12：

```bash
git clone https://github.com/XBigRoad/procurement-agent.git
cd procurement-agent
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./rfqdiff-upstream
```

如果只运行综合 Agent CLI，依赖安装后还需要把仓库根目录加入 Python 路径：

```bash
export PYTHONPATH="$PWD"
```

## 一键比较报价并分析价格合理性

```bash
python -m procurement_agent compare \
  --quotes samples/quotes-demo.csv \
  --history samples/history-demo.csv \
  --output output/comparison.json \
  --report output/comparison.xlsx
```

输出：

- `output/comparison.json`：机器可读的综合结果
- `output/comparison.xlsx`：排名、评分、价格、交期和付款条件表

JSON 中会包含：

- 推荐供应商
- 第二名和分差
- 最低价供应商
- 最快交期供应商
- 最优付款条件供应商
- 每家供应商的评分拆解
- 报价来源文件和行号
- 本批报价中位数
- 历史价格中位数
- 异常低价 / 高价标记
- 缺少字段提示
- 采购决策状态：异常低价或信息不足时只输出“待人工复核”，不会自动形成定标建议

## 输入格式

CSV、Excel 或 JSON 至少需要这些字段：

```text
name,currency,price,lead_time_weeks,payment_days
```

例如：

```csv
name,currency,price,lead_time_weeks,payment_days
供应商A,CNY,842000,8,30
供应商B,CNY,794000,14,0
供应商C,CNY,560000,10,30
```

注意：当前报价金额必须先统一口径。含税 / 未税、运费、安装费、模具费和配置差异，不能直接混在 `price` 里比较。

## 自定义权重

准备 `weights.json`：

```json
{
  "price": 0.4,
  "lead_time": 0.4,
  "payment_terms": 0.2
}
```

运行：

```bash
python -m procurement_agent compare \
  --quotes quotations.xlsx \
  --history historical_prices.csv \
  --weights weights.json \
  --output output/equipment.json \
  --report output/equipment.xlsx
```

## 采购员实际工作方式

将多家报价先整理为标准字段后运行；Agent 输出后，采购员重点复核：

1. 规格和配置是否真的等效；
2. 最低报价有没有漏项；
3. 是否含税、运费、安装和调试；
4. 交期是否满足生产需求；
5. 当前报价是否偏离历史价格；
6. 供应商质量和交付记录是否支持推荐结论。

## 后续扩展

- PDF / 图片报价解析并保留页码、行号和图片区域证据；
- 原材料、模具、设备三类采购专用字段；
- 物料规格和设备配置的可比性判断；
- 历史价格库、供应商质量库和交付库；
- 全生命周期成本；
- 采购员人工复核队列；
- 网页上传界面和中文管理汇报。

## 许可证与来源

- 上游 `rfqdiff`：MIT，许可证副本保留在 `rfqdiff-upstream/LICENSE`。
- 上游采购 Skill 仓库未随仓库提供明确 LICENSE 文件；来源、提交版本和使用边界见 `docs/UPSTREAM.md`。
- 本仓库新增代码采用 MIT，见 `LICENSE`。

## 数据安全

不要提交真实报价、供应商价格、合同、客户信息、API Key 或企业内部人员信息。`company-profiles/` 只放脱敏规则和字段定义；真实业务数据放在仓库外部。
