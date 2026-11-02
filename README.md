# Enterprise Procurement Agent

企业采购报价审核与采购建议 Agent 的组合工程。

本仓库把两个开源项目组合为可扩展底座，并加入面向制造业采购的第一批扩展：

- 采购业务 Skill：继承并整理 `procurement-agent-skills` 的 RFQ、报价比较、TCO、谈判、供应商评分和管理汇报能力。
- 确定性比价内核：保留 `rfqdiff` 的 CSV / JSON / XLSX 输入、显式权重、可解释评分、来源追溯和报告导出。
- 企业扩展：`procurement_agent.reasonableness` 对报价相对本批报价和历史价格的偏离做可解释预警；不替代技术评审和最终定标。

## 目标边界

第一版解决：多家报价读取、字段统一、可比性检查、价格/交期/付款比较、历史价格偏离提醒和采购建议草稿。

第一版不自动执行：下单、付款、签合同、最终定标、向供应商发送未经人工审核的承诺。

## 目录

```text
skills/                 采购 Agent Skill 与输出规范
company-profiles/       企业和采购规则（不得提交真实敏感数据）
global/                 安全、术语、通用原则和输出格式
rfqdiff-upstream/       上游 rfqdiff 的可运行比价内核及其 MIT License
procurement_agent/      企业扩展：价格合理性分析
rfqdiff-upstream/samples/  可公开演示样例
```

## 快速运行比价内核

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./rfqdiff-upstream
rfqdiff rfqdiff-upstream/samples/quotations.csv --json
rfqdiff rfqdiff-upstream/samples/quotations.csv --report comparison.xlsx
```

## 运行价格合理性扩展

```python
from procurement_agent import analyze_price_reasonableness

result = analyze_price_reasonableness(
    [
        {"supplier": "供应商A", "price": 100},
        {"supplier": "供应商B", "price": 102},
        {"supplier": "供应商C", "price": 55, "missing_fields": ["运费"]},
    ],
    historical_prices=[98, 101, 100],
)
```

此函数只接受已经完成单位、币种、税价和可比性处理的标准化报价。原始 PDF / 图片解析和技术规格等效判断必须在进入评分前完成。

## 许可证与来源

- 上游 `rfqdiff`：MIT，许可证副本保留在 `rfqdiff-upstream/LICENSE`。
- 上游采购 Skill 仓库未随仓库提供明确 LICENSE 文件；本仓库保留其原始内容并在 `docs/UPSTREAM.md` 记录来源、提交版本和使用边界。发布或再分发前应继续确认其许可证状态。
- 本仓库新增代码默认采用 MIT，见 `LICENSE`。

## 数据安全

不要提交真实报价、供应商价格、合同、客户信息、API Key 或企业内部人员信息。`company-profiles/` 只放脱敏规则和字段定义；真实业务数据放在仓库外部。
