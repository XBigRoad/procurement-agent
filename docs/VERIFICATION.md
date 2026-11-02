# V1 验证记录

验证日期：2026-11-02。环境：Windows、Python 3.13.13，使用本仓库
`requirements-lock.txt` 和项目 `.venv`。数据均为模拟报价。

## 已执行结果

| 检查 | 实际结果 |
|---|---|
| 应用测试 `python -m pytest tests -q` | 257 passed，18.04s，退出码0 |
| Ruff `python -m ruff check procurement_agent tests` | All checks passed，退出码0 |
| 保留上游回归测试 | 38 passed，1.11s，退出码0 |
| 安装脚本 `pwsh -NoProfile -File scripts/install.ps1` | 退出码0，安装后 CLI 帮助可运行 |
| `python scripts/acceptance_smoke.py` | 退出码0，三种业务场景通过 |
| 本地服务 `http://127.0.0.1:8511/_stcore/health` | HTTP 200，响应 `ok` |
| 真实浏览器操作 | 上传、异常拦截、复核上传重算及 JSON/Excel 下载已实际执行 |
| `git diff --check` | 退出码0 |

合计295项自动化测试通过。安装工具提示跨磁盘硬链接不可用，自动改用复制，
安装正常完成。上表记录本地运行结果；远端平台验证由 GitHub Actions 另行报告。

## 可复现命令

在仓库根目录使用 PowerShell，每条命令分别检查退出码：

```powershell
pwsh -NoProfile -File scripts/install.ps1
.venv/Scripts/python.exe -m pytest tests -q
.venv/Scripts/python.exe -m ruff check procurement_agent tests
$env:PYTHONPATH = "$PWD/rfqdiff-upstream"
.venv/Scripts/python.exe -m pytest rfqdiff-upstream/rfqdiff-tests -q
Remove-Item Env:PYTHONPATH
.venv/Scripts/python.exe scripts/acceptance_smoke.py
pwsh -NoProfile -File scripts/run-demo.ps1
git diff --check
```

验收脚本使用固定分析日期2026-11-02，生成文件保存在
`output/运行当天日期/`。该目录保持为本地资料。

## 业务验收

| 场景 | 已核实结果 |
|---|---|
| 原材料、模具、设备共9条正常报价 | 形成3个逐物料结果，状态为供人工审批的条件性推荐 |
| 异常低价 | 状态为 `manual_review_required`，推荐字段为空，保留候选和确认问题 |
| 具名复核并提供低价说明依据 | 全量重算，低价转为 `low_explained`，保留审计记录 |
| 原始字段追溯 | 从结果中的工作表和单元格读取原文件，数值与原值一致，SHA256一致 |
| 三种状态的 Excel 导出 | 每份13个工作表，含建议、评分、字段对照、计算、风险、参考、证据与复核 |
| Excel 表格样式和内容 | 微软雅黑、无填充色、冻结表头；用户文本以文本单元格导出 |
| 原件保留 | 全部验收输入文件在计算前后的文件哈希一致 |
| 浏览器复核闭环 | 低价拦截后上传模拟复核文件，重算为条件性推荐，1条复核记录，下载成功 |

本地详细证据为 `acceptance-summary.json`、三组
`acceptance-*.json/.xlsx/.md`、`browser-acceptance-summary.json` 和浏览器截图。
它们位于忽略目录，未作为真实采购记录或审批文件提交。

## 已修复并覆盖回归的问题

1. 推荐状态统一：阻断状态在 JSON、Excel、中文建议及网页中保持推荐为空。
2. 历史参考独立性：本批报价不能重复上传为历史/市场证据来稀释异常基准。
3. 历史范围完整性：缺项或未知范围的参考记录排除，并列明原因。
4. 大数量税价校验：直接核对含税/未税总额，避免除以数量后掩盖金额矛盾。
5. 复核跨会话复用：相同文件内容与规则在不同上传目录仍可复核；实质输入变化会使旧复核失效。
6. 网页和引擎权重一致：默认价格50%、交期30%、账期20%。
7. 上游证据字节一致：为保留的黄金样本指定LF，避免Windows换行改变哈希；用户文件保持原始字节。

相关回归见 `tests/test_engine.py`、`tests/test_app.py`、
`tests/test_reports_v2.py`；输入边界与位置证据见 `tests/test_ingest.py`。

## 适用范围

当前交付为本地单人试用版，支持表格型 XLSX、CSV、JSON。市场参考由用户提供，
技术等效确认由采购与技术人员负责。复核身份为本地填写，尚未接入企业认证、
审批签名和持久化证据库。PDF/OCR、复杂技术等效、ERP/SRM及多人部署属于后续阶段。

所有建议均供企业授权人员审批。程序提供比较、证据、风险和复核能力，
没有定标、下单、付款、签约或向供应商发出承诺的执行接口。
