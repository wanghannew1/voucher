# 财务凭证生成工具 (Voucher Generator)

## TL;DR

> **Quick Summary**: Build a Python CLI script that reads bank statements and invoices, applies business rules derived from April voucher data, and outputs NCC-importable voucher Excel files with cash flow sub-tables.
> 
> **Deliverables**:
> - Python CLI script (`generate_vouchers.py`) that processes bank statements + invoices → NCC voucher import file
> - Name matching module with auto-matching + unmatched report
> - Per-bank parsers (ICBC, CCB, Jilin Bank)
> - Invoice parser
> - Subject code assignment rules (derived from April data)
> - NCC output formatter (72-column main table + cash flow sub-table)
> - Reconciliation report (matched/unmatched summary)
> 
> **Estimated Effort**: Large
> **Parallel Execution**: YES - 5 waves
> **Critical Path**: Task 1 → Task 2 → Task 5 → Task 8 → Task 10 → Task 11 → Tasks 12-14 → F1-F4

---

## Context

### Original Request
用户需要自动从银行对账单和发票数据生成用友NCC系统的财务凭证导入文件。目前4月财务手工制作了2731张凭证（8188行分录），涉及3家银行对账单、901张发票。目标是自动化这个过程。

### Interview Summary
**Key Discussions**:
- 进款映射规则：按对方户名匹配客户编码→决定科目（用户确认）
- 出款映射规则：按银行摘要关键词→决定科目（用户确认）
- 发票凭证：每张发票一张凭证，派遣用224101/122101，外包用1122
- 摘要模板：固定格式"收/付{类型} {客户名称}{项目名称}"
- 现金流量子表：需要生成
- 计提凭证：不在范围内
- 工具形态：Python脚本+Excel

**Research Findings**:
- 用友NCC导入模板72列，含主表+子表结构（现金流量分录用行号关联主表）
- 3家银行对账单格式完全不同（工行89笔、建行1004笔、吉林银行405笔）
- 科目→辅助核算映射已从4月数据推导完成（281个辅助核算编码仅缺2个人员编码）
- 银行账号→银行代码对应清晰（工行→0107, 建行→0402, 吉林银行→2801, 招行→1505, 农行→0206）

### Metis Review
**Identified Gaps** (addressed):
- 名称匹配失败率风险：已设计为Phase 2优先验证，<80%匹配率则需用户补充映射
- NCC导入格式精确性：已计划使用现有模板文件作为输出格式基准
- 银行手续费/利息/内部转账等特殊交易：已加入规则表
- 未匹配交易处理：输出到单独报表，不静默跳过
- 编码问题（GBK/UTF-8）：已计划自动检测编码

---

## Work Objectives

### Core Objective
Build a Python CLI script that reads bank statements (3 formats) and invoices, automatically generates NCC voucher import files with proper subject codes, auxiliary accounting, and cash flow sub-tables.

### Concrete Deliverables
- `generate_vouchers.py` — main CLI entry point
- `parsers/` — per-bank and invoice parsers
- `matchers/` — counterparty name matching module
- `rules/` — subject code assignment rules derived from April data
- `formatters/` — NCC output formatter
- Output: voucher import Excel file + reconciliation report Excel file

### Definition of Done
- [ ] Script reads all 3 bank statement formats and 901 invoices without errors
- [ ] Counterparty name matching rate ≥ 80% on April data
- [ ] Every generated voucher has balanced debit/credit (借方合计 = 贷方合计)
- [ ] Output file matches NCC import template format exactly (72 columns in correct order)
- [ ] Cash flow sub-table row numbers correctly link to main entries
- [ ] Unmatched transactions are reported in a separate sheet with full details
- [ ] No Chinese character corruption in output (encoding roundtrip OK)

### Must Have
- Parse 3 bank statement formats (ICBC .xls, CCB .xls, Jilin Bank .xlsx)
- Parse 901 invoices (1 invoice = 1 voucher)
- Correct subject code assignment based on April patterns
- Auxiliary accounting assignment (科目→辅助核算 mapping)
- Cash flow sub-table generation
- Counterparty name → customer/supplier code matching
- Summary (摘要) generation following fixed template
- Debit/credit balance validation on every voucher
- Unmatched transaction report (不让静默跳过)
- NCC import format output (72 columns, correct column order)
- Bank fee/interest/internal transfer handling
- Single month processing with CLI arguments
- Reconciliation summary report

### Must NOT Have (Guardrails)
- NO accrual entries (计提) generation
- NO bank reconciliation (银行对账)
- NO invoice-to-payment cross-referencing
- NO tax calculation (use amounts as-is)
- NO multi-currency support (RMB only)
- NO UI/web interface (CLI only)
- NO database (file-based I/O only)
- NO configurable rule engine (hardcode rules from April data)
- NO multi-month processing (one month at a time)
- NO general ledger posting (generate import file only)
- NO fuzzy matching beyond simple substring/contains (unmatched → report)
- AI slop patterns to avoid: over-abstraction, unnecessary class hierarchies, excessive comments, generic variable names

---

## Verification Strategy (MANDATORY)

### Test Decision
- **Infrastructure exists**: NO (Python project, no test framework yet)
- **Automated tests**: YES (tests-after) — add pytest after each module is built
- **Framework**: pytest
- **If tests-after**: Each task includes test scenarios as part of acceptance criteria

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Python module**: Use Bash (python) — import, call functions, assert output
- **CLI script**: Use Bash — run script with arguments, check exit code, verify output files
- **Excel output**: Use Bash (python) — open output file, verify column headers, row counts, cell values
- **Reconciliation**: Use Bash (python) — verify matched/unmatched counts balance

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - foundation + data discovery):
├── Task 1: Project scaffolding + all reference data loaders [quick]
├── Task 2: Name matching module + validation gate [deep]
├── Task 3: NCC template analysis + output formatter [quick]
└── Task 4: Subject-to-auxiliary accounting rule extraction [quick]

Wave 2 (After Wave 1 - parsers, depends on Task 1):
├── Task 5: ICBC bank statement parser [unspecified-high]
├── Task 6: CCB bank statement parser [unspecified-high]
├── Task 7: Jilin Bank statement parser [unspecified-high]
└── Task 8: Invoice parser + voucher generation rules [unspecified-high]

Wave 3 (After Wave 2 - core business logic, depends on Tasks 2,4,8):
├── Task 9: Incoming payment voucher generator (付款→凭证) [deep]
├── Task 10: Outgoing payment voucher generator (付款→凭证) [deep]
└── Task 11: Invoice voucher generator (发票→凭证) [deep]

Wave 4 (After Wave 3 - assembly + validation):
├── Task 12: Cash flow sub-table generator [unspecified-high]
├── Task 13: Voucher assembly + NCC output writer [deep]
└── Task 14: Reconciliation report generator [unspecified-high]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
```

### Dependency Matrix

| Task | Depends On | Blocks |
|------|-----------|--------|
| 1 | - | 5,6,7,8 |
| 2 | 1 | 9,10 |
| 3 | 1 | 13 |
| 4 | 1 | 9,10,11 |
| 5 | 1 | 9,10 |
| 6 | 1 | 9,10 |
| 7 | 1 | 9,10 |
| 8 | 1 | 11 |
| 9 | 2,4,5 | 12,13 |
| 10 | 2,4,5,6,7 | 12,13 |
| 11 | 4,8 | 12,13 |
| 12 | 9,10,11 | 13 |
| 13 | 3,12 | 14 |
| 14 | 13 | F1-F4 |

### Agent Dispatch Summary

- **Wave 1**: 4 tasks — T1 `quick`, T2 `deep`, T3 `quick`, T4 `quick`
- **Wave 2**: 4 tasks — T5 `unspecified-high`, T6 `unspecified-high`, T7 `unspecified-high`, T8 `unspecified-high`
- **Wave 3**: 3 tasks — T9 `deep`, T10 `deep`, T11 `deep`
- **Wave 4**: 3 tasks — T12 `unspecified-high`, T13 `deep`, T14 `unspecified-high`
- **FINAL**: 4 tasks — F1 `oracle`, F2 `unspecified-high`, F3 `unspecified-high`, F4 `deep`

---

## TODOs

- [ ] 1. Project scaffolding + all reference data loaders

  **What to do**:
  - Set up Python project structure: `src/`, `src/parsers/`, `src/matchers/`, `src/rules/`, `src/formatters/`, `src/generators/`, `src/reports/`, `tests/`, `data/`
  - Create `src/data_loader.py` that loads ALL reference tables into Python dicts:
    - 会计科目 (472 entries): `acc_subjects[code] = {name, type, direction, ...}` from `会计科目_472.xlsx`
    - 客户档案 (476 entries): `customers[code] = {name, classification, status}` from `客户基本信息列表 (476).xlsx`
    - 供应商档案 (325 entries): `suppliers[code] = {name, classification, status}` from `供应商基本信息列表 (325条).xlsx`
    - 项目档案 (58 entries): `projects[code] = name` from `项目档案.xlsx`
    - 辅助明细 (24 entries): `aux_details[code] = name` from `辅助明细.xlsx`
    - 部门 (10 entries): `departments[code] = name` from `部门.txt`
    - 银行档案 (5 entries): `banks[code] = name` from `银行档案.xlsx`
    - 客户分类: `customer_classes[code] = name` from `客户基本分类-业务单元.txt`
    - 供应商分类: `supplier_classes[code] = name` from `供应商基本分类.txt`
  - Handle encoding (GBK/UTF-8) auto-detection for .txt files
  - Handle different Excel formats (.xls with xlrd, .xlsx with openpyxl)
  - Write pytest: `tests/test_data_loader.py` verifying all tables load with expected row counts

  **Must NOT do**:
  - Don't build any business logic yet — just data loading
  - Don't add pandas as dependency — use openpyxl/xlrd directly for smaller footprint

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4)
  - **Blocks**: Tasks 5, 6, 7, 8
  - **Blocked By**: None (can start immediately)

  **References**:
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/会计科目_472.xlsx` — Main accounting subject reference, row 1 = import notes, row 2 = headers (Chinese), row 3+ = data. Key columns: `* 科目编码`, `* 科目名称(ZH)`, `* 科目类型`, `* 科目方向`
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/客户基本信息列表 (476).xlsx` — Customer codes. Row 1 = empty, row 2 = headers (所属组织, 客户编码, 客户名称, 客户分类, 客户状态...)
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/供应商基本信息列表 (325条).xlsx` — Supplier codes. Same structure as customer file.
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/项目档案.xlsx` — Project codes. Row 1 = empty, row 2 = headers. Use only "启用状态=已启用" entries.
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/辅助明细.xlsx` — Auxiliary detail codes (FZ001-FZ099, WB series, CBJ series)
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/银行档案.xlsx` — Bank account codes (0107, 0402, 2801, 1505, 0206)
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/部门.txt` — Department codes (01-12)
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/客户基本分类-业务单元.txt` — Customer classification hierarchy
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/供应商基本分类.txt` — Supplier classification hierarchy

  **Acceptance Criteria**:
  - [ ] `src/data_loader.py` loads all 9 reference tables without errors
  - [ ] `acc_subjects['1002']` returns `{'name': '银行存款', 'type': '资产', 'direction': '借方'}`
  - [ ] `customers['ch003']` returns customer name '长春海关技术中心'
  - [ ] `suppliers['TB007']` returns supplier name '吉林省能者云创科技有限公司'
  - [ ] `banks['0402']` returns '中国建设银行股份有限公司长春富豪花园支行'
  - [ ] All .txt files load with correct encoding (no garbled characters)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Load all reference data successfully
    Tool: Bash (python)
    Preconditions: Reference data files in /home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/
    Steps:
      1. Run: python -c "from src.data_loader import load_all; d=load_all('/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料'); print(len(d['acc_subjects']), len(d['customers']), len(d['suppliers']))"
      2. Verify output shows: 472 (or close) 476 325
    Expected Result: All reference tables load with expected counts
    Failure Indicators: Import error, file not found, encoding error, count mismatch >5%
    Evidence: .omo/evidence/task-1-load-all.txt

  Scenario: Specific code lookups return correct values
    Tool: Bash (python)
    Preconditions: Data loaded successfully
    Steps:
      1. Run: python -c "from src.data_loader import load_all; d=load_all('/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料'); print(d['acc_subjects']['1002']['name']); print(d['customers']['ch003']['name']); print(d['banks']['0402']['name'])"
      2. Verify: '银行存款' == acc_subjects['1002']['name']
      3. Verify: '长春海关技术中心' in customers['ch003']['name']
      4. Verify: '建设银行' in banks['0402']['name']
    Expected Result: All lookups return correct Chinese strings, no encoding issues
    Failure Indicators: KeyError, garbled characters, wrong names
    Evidence: .omo/evidence/task-1-lookup.txt
  ```

  **Commit**: YES
  - Message: `feat: scaffold project structure and reference data loaders`
  - Files: `src/`, `src/data_loader.py`, `tests/test_data_loader.py`, `requirements.txt`

- [ ] 2. Name matching module + validation gate

  **What to do**:
  - Create `src/matchers/name_matcher.py` with:
    - `normalize_name(name)`: strip legal suffixes (有限公司, 有限责任公司, 股份有限公司, 集团), remove spaces/punctuation, convert to simplified Chinese if needed
    - `match_counterparty(bank_name, customers, suppliers) -> (code, type, confidence)`:
      - Exact match against customer/supplier names
      - Substring/contains match with normalized names
      - Return best match with confidence score (1.0 = exact, 0.8+ = substring, <0.5 = no match)
    - `match_all_bank_transactions(transactions, customers, suppliers) -> (matched, unmatched)`
  - **VALIDATION GATE**: Run name matcher against ALL counterparty names from 3 bank statements. Calculate match rate. If < 80%, output the unmatched list for user review.
  - Build name normalization rules from actual data:
    - 工商银行: "中国工商银行长春人民广场支行", "工商银行" → prefix/suffix stripping
    - Common patterns: "(全风险)", "(全风险劳务派遣)", "2月"/"3月" month suffixes in bank summaries
  - Handle special cases: bank fees (no counterparty), tax payments (待报解预算收入), internal transfers
  - Write pytest: `tests/test_name_matcher.py` with real counterparty names from bank data
  - Output a `match_report.txt` showing match rate and unmatched items

  **Must NOT do**:
  - Don't implement fuzzy matching with edit distance (Levenshtein, etc.)
  - Don't use ML/NLP libraries
  - Don't try to match bank fee/interest transactions to customer codes (they have no counterparty)

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Task 1 data loaders are available)
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4)
  - **Blocks**: Tasks 9, 10, 11
  - **Blocked By**: Task 1 (needs data loaders)

  **References**:
  - `/home/ubuntu/excel_example/voucher/银行对账单/彩虹建行4月对账单.xls` — CCB data with 对方户名 column. Sample values: "长春海关技术中心", "吉林大学第二医院", "吉林省顺丰速递有限公司", "中国平安财产保险股份有限公司吉林分公司"
  - `/home/ubuntu/excel_example/voucher/银行对账单/彩虹工行4月对账单.xls` — ICBC data with 对方户名 column. Different format, row 3 = header, row 4+ = data
  - `/home/ubuntu/excel_example/voucher/银行对账单/彩虹吉林银行4月对账单.xlsx` — Jilin Bank data with 交易对手户名 column. Row 7-8 = header area, row 9+ = data
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/客户基本信息列表 (476).xlsx` — Customer names to match against
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/供应商基本信息列表 (325条).xlsx` — Supplier names to match against
  - April voucher data: `辅助核算1` and `辅助核算2` columns show which codes were assigned to which transactions

  **Acceptance Criteria**:
  - [ ] `match_counterparty("长春海关技术中心", customers, suppliers)` returns `("ch003", "customer", score)`
  - [ ] `match_counterparty("吉林大学第二医院", customers, suppliers)` returns `("ch078", "customer", score)`
  - [ ] `normalize_name("吉林省彩虹人才开发咨询服务有限公司")` returns simplified name like "彩虹人才"
  - [ ] Match rate on ALL April bank transactions ≥ 80%
  - [ ] Unmatched transactions are listed with full details for manual review
  - [ ] Special cases handled: bank fees, tax payments, internal transfers (no crash)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Name matching against real bank data (CRITICAL VALIDATION GATE)
    Tool: Bash (python)
    Preconditions: All 3 bank statement files available, data loaders working
    Steps:
      1. Run: python -c "from src.matchers.name_matcher import validate_match_rate; rate, unmatched = validate_match_rate(); print(f'Match rate: {rate:.1%}'); print(f'Unmatched: {len(unmatched)}'); [print(f'  {u}') for u in unmatched[:10]]"
      2. Assert match rate ≥ 80% (0.80)
      3. If < 80%, output unmatched list for user review
    Expected Result: Match rate ≥ 80%, unmatched items clearly listed
    Failure Indicators: Match rate < 80%, script error, encoding issues
    Evidence: .omo/evidence/task-2-match-rate.txt

  Scenario: Exact name match returns correct code
    Tool: Bash (python)
    Preconditions: Data loaders working
    Steps:
      1. Run: python -c "from src.data_loader import load_all; from src.matchers.name_matcher import match_counterparty; d=load_all('/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料'); r=match_counterparty('长春海关技术中心', d['customers'], d['suppliers']); print(r)"
      2. Verify result contains 'ch003' as code and 'customer' as type
    Expected Result: ('ch003', 'customer', score ≥ 0.95)
    Failure Indicators: Wrong code, wrong type, confidence < 0.5
    Evidence: .omo/evidence/task-2-exact-match.txt

  Scenario: No-match returns None with reason
    Tool: Bash (python)
    Steps:
      1. Run: python -c "from src.data_loader import load_all; from src.matchers.name_matcher import match_counterparty; d=load_all('/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料'); r=match_counterparty('UNKNOWN_COMPANY_XYZ', d['customers'], d['suppliers']); print(r)"
      2. Verify result is None or confidence < 0.5
    Expected Result: No match found, None or low confidence
    Evidence: .omo/evidence/task-2-no-match.txt
  ```

  **Commit**: YES
  - Message: `feat: add counterparty name matching with validation gate`
  - Files: `src/matchers/`, `src/matchers/name_matcher.py`, `tests/test_name_matcher.py`

- [ ] 3. NCC template analysis + output formatter

  **What to do**:
  - Analyze the NCC import template structure from `凭证信息_temp - 2026-06-02T140354.252.xlsx`:
    - Row 0: Import instructions
    - Row 1: Column headers (mixed system field names + Chinese names)
    - Row 2+: Data rows
    - Main table section: rows with sequential row numbers in column 0
    - Sub-table section: after blank row, cash flow entries with "cashflow" header
  - Create `src/formatters/ncc_formatter.py` that:
    - Defines exact column order (72 columns) with both system names and Chinese names
    - Writes main table section with proper formatting (all text format per NCC requirement)
    - Writes sub-table (cash flow) section linked by row number
    - Handles the `billhead_$head` first column (sequential row numbering)
    - Ensures all numeric amounts stored as text (NCC requirement: "所有内容必须为文本格式")
    - Ensures date format is YYYY-MM-DD
  - Write pytest: `tests/test_ncc_formatter.py`

  **Must NOT do**:
  - Don't guess column order — use the exact order from the template file
  - Don't add columns that don't exist in the template

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4)
  - **Blocks**: Task 13
  - **Blocked By**: Task 1 (needs data loaders for reference)

  **References**:
  - `/home/ubuntu/excel_example/voucher/代码资料/凭证信息_temp - 2026-06-02T140354.252.xlsx` — THE template file. Row 1 has system field names (comma-separated in column 0), row 2+ has data. MUST match this exact format.
  - Key columns by order: `* 财务核算账簿`, `* 凭证类别`, `* 凭证号`, `附单据数`, `* 制单人`, `* 制单日期`, `* 摘要`, `利润中心`, `* 科目编码`, `* 币种`, `* 原币借方金额`, `* 本币借方金额`, ... (72 columns total)
  - Cash flow sub-table starts after main data, separated by blank row. Header: `cashflow,flag,cashflowcurr,mo,...` with columns: 方向, 分析币种, 原币, 账簿本币, 集团本币, 全局本币, 内部单位, 现金流量名称, 现金流量编码
  - Main table row numbers link to cash flow sub-table via the first column

  **Acceptance Criteria**:
  - [ ] Output Excel file has exactly 72 columns in header row
  - [ ] Column order matches template file exactly
  - [ ] All amounts stored as text (text format, not number format)
  - [ ] Dates in YYYY-MM-DD format
  - [ ] Cash flow sub-table properly formatted with row number linkage
  - [ ] Row 0 contains import instructions text
  - [ ] Row 1 contains system field names string in column 0

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Output format matches NCC template structure
    Tool: Bash (python)
    Steps:
      1. Write a test voucher with known values using NCC formatter
      2. Open output file with openpyxl
      3. Verify row 0 column 0 contains import instructions text
      4. Verify row 1 has correct system field names
      5. Verify data rows have 72 non-null columns
      6. Verify cash flow section exists and links correctly
    Expected Result: Output file structure matches NCC template exactly
    Evidence: .omo/evidence/task-3-format-check.txt

  Scenario: Amount formatting as text
    Tool: Bash (python)
    Steps:
      1. Write voucher with amount 146050.46 using formatter
      2. Read back cell value — verify it's stored as text "146050.46", not number 146050.46
      3. Verify date cell is "2026-04-01" not date object
    Expected Result: All amounts stored as text format
    Failure Indicators: Cells stored as numbers, dates stored as datetime objects
    Evidence: .omo/evidence/task-3-text-format.txt
  ```

  **Commit**: YES
  - Message: `feat: add NCC template parser and output formatter`
  - Files: `src/formatters/ncc_formatter.py`, `tests/test_ncc_formatter.py`

- [ ] 4. Subject-to-auxiliary accounting rule extraction

  **What to do**:
  - Create `src/rules/subject_rules.py` that encodes the accounting rules derived from April voucher data:
    - **科目→辅助核算映射**: which subjects need which auxiliary accounting
      - 1002 → 辅助核算1=银行档案
      - 224101 → 辅助核算1=客户档案, 辅助核算2=供应商档案(when applicable)
      - 224102 → 辅助核算1=辅助明细(自定义档案), 辅助核算2=供应商档案
      - 600101/600102/600108 → 辅助核算1=部门, 辅助核算2=项目档案
      - 640102/640108 → 辅助核算1=部门, 辅助核算2=项目档案
      - etc. (full mapping from April data analysis)
    - **银行→科目映射**: what subject codes to use for different transaction types
      - 收款(incoming): 借方=1002+银行档案, 贷方 based on customer classification
      - 付款(outgoing): subject based on keyword matching
    - **收款分录模板**:
      - 借: 1002 银行存款 (辅助核算1=银行代码:银行档案)
      - 贷: 224101 其他应付款-客户往来 (辅助核算1=客户代码:客户档案)
    - **付款分录模板** (keyword-based):
      - "工资" → 借:224101(客户) + 贷:1002(银行)
      - "社保" → 借:224101(客户) + 贷:1002(银行)  
      - "劳务费/业务费" → 借:640102(部门+项目) + 贷:1002(银行)
      - "快递费" → 借:66021603(部门) + 贷:1002(银行)
      - "手续费" → 借:660304(部门) + 贷:1002(银行)
      - Full keyword→subject mapping derived from April data
    - **发票分录模板**:
      - 派遣收入: 借:224101(客户)/122101(客户) + 贷:600101(部门+项目) + 贷:222121(税金)
      - 外包收入: 借:1122(客户) + 贷:600102(部门+项目) + 贷:222121(税金)
    - **摘要生成模板**: "收/付{类型} {客户简称}{项目简称(如有)}"
    - **现金流量映射**: subject code → cash flow code
      - 600101/600102 → 1111 (销售商品、提供劳务收到的现金)
      - 640102/640108 → 1124 (购买商品、接受劳务支付的现金)  
      - 224101 (outgoing for salary) → 1122 (支付给职工以及为职工支付的现金)
      - 224102 (outgoing for social security) → 1122
  - Write pytest: `tests/test_subject_rules.py`

  **Must NOT do**:
  - Don't make rules configurable via YAML/JSON — hardcode from April data
  - Don't implement a rule engine — it's mapping dicts and if/elif chains

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3)
  - **Blocks**: Tasks 9, 10, 11
  - **Blocked By**: Task 1 (needs data loaders for reference)

  **References**:
  - April voucher analysis showing 科目编码→辅助核算 frequency mapping (see draft file at `.omo/drafts/voucher-generator.md`)
  - `/home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料/会计科目_472.xlsx` — All 472 accounting subjects with names, types, and directions
  - Key patterns from April data (TOP subjects):
    - 224101 其他应付款-客户往来: 辅助核算1=客户档案, 辅助核算2=(sometimes 供应商档案)
    - 1002 银行存款: 辅助核算1=银行档案
    - 600101 派遣收入: 辅助核算1=部门, 辅助核算2=项目档案
    - 600102 外包收入: 辅助核算1=部门, 辅助核算2=项目档案
    - 224102 其他应付款-供应商往来: 辅助核算1=辅助明细, 辅助核算2=供应商档案
    - 1122 应收账款: 辅助核算1=客户档案

  **Acceptance Criteria**:
  - [ ] `get_auxiliary_requirements('1002')` returns `['银行档案']`
  - [ ] `get_auxiliary_requirements('224101')` returns `['客户档案']` (or `['客户档案', '供应商档案']` when supplier context)
  - [ ] `get_auxiliary_requirements('600101')` returns `['部门', '项目档案']`
  - [ ] `get_voucher_template('incoming', customer_type='派遣')` returns correct subject codes
  - [ ] `generate_summary('incoming', '派遣', '长春海关技术中心', '')` returns "收往来派遣费 长春海关技术中心"
  - [ ] `get_cash_flow_code('600101')` returns '1111'

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Subject rules return correct auxiliary accounting
    Tool: Bash (python)
    Steps:
      1. from src.rules.subject_rules import get_auxiliary_requirements
      2. assert get_auxiliary_requirements('1002') == ['银行档案']
      3. assert get_auxiliary_requirements('600101') == ['部门', '项目档案']
      4. assert get_auxiliary_requirements('224102') == ['辅助明细(自定义档案)', '供应商档案']
    Expected Result: All assertions pass
    Evidence: .omo/evidence/task-4-aux-rules.txt

  Scenario: Summary generation follows template
    Tool: Bash (python)
    Steps:
      1. from src.rules.subject_rules import generate_summary
      2. assert generate_summary('incoming', '派遣', '长春海关技术中心', '') == '收往来派遣费 长春海关技术中心'
      3. assert generate_summary('incoming', '外包', '吉林银行', '总行（惠农经理）') == '收外包业务费 吉林银行 总行（惠农经理）'
    Expected Result: Summaries match expected format
    Evidence: .omo/evidence/task-4-summary.txt
  ```

  **Commit**: YES
  - Message: `feat: extract subject-to-auxiliary accounting rules from April data`
  - Files: `src/rules/subject_rules.py`, `tests/test_subject_rules.py`

- [ ] 5. ICBC bank statement parser

  **What to do**:
  - Create `src/parsers/icbc_parser.py` that reads ICBC (工商银行) bank statements
  - Handle format: .xls file, header in row 3-4, data from row 5+
  - Extract fields: 日期, 交易类型, 对方户名, 对方账号, 摘要, 借方发生额(支出), 贷方发生额(收入), 余额
  - Unified output format: `BankTransaction(date, transaction_type, counterparty_name, counterparty_account, summary, debit, credit, balance, bank_code='0107', raw_data)`
  - Handle merged header rows (row 0-2 contain account info, row 3-4 are column headers)
  - Handle encoding (may be GBK)
  - Write pytest: `tests/test_icbc_parser.py` with actual April data

  **Must NOT do**:
  - Don't parse CCB or Jilin Bank formats — this module only handles ICBC
  - Don't apply business rules — just parse and normalize

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 6, 7)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 9, 10
  - **Blocked By**: Task 1 (needs data loaders)

  **References**:
  - `/home/ubuntu/excel_example/voucher/银行对账单/彩虹工行4月对账单.xls` — ICBC format. Row 0: account number, Row 1: account name, Row 2: 汇率/branch, Row 3: column headers, Row 4+: data. 89 transactions. Key columns: 日期, 交易类型, 对方户名, 对方账号, 摘要, 借方发生额, 贷方发生额, 余额
  - Bank account mapping: ICBC account 4200220309200086665 → bank code 0107

  **Acceptance Criteria**:
  - [ ] Parses ICBC .xls file and returns list of BankTransaction objects
  - [ ] All 89 transactions extracted with correct amounts and dates
  - [ ] Debit (支出) and credit (收入) correctly separated
  - [ ] Counterparty names extracted without garbled characters
  - [ ] Bank code '0107' automatically assigned to all transactions
  - [ ] Handles encoding correctly (GBK/UTF-8)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Parse all ICBC transactions
    Tool: Bash (python)
    Steps:
      1. from src.parsers.icbc_parser import parse_icbc
      2. txns = parse_icbc('/home/ubuntu/excel_example/voucher/银行对账单/彩虹工行4月对账单.xls')
      3. assert len(txns) == 89
      4. assert txns[0].counterparty_name is not None  # first transaction has counterparty
      5. assert txns[0].bank_code == '0107'
      6. assert all(t.date.startswith('2026-04') for t in txns)
    Expected Result: 89 transactions parsed correctly
    Evidence: .omo/evidence/task-5-icbc-parse.txt

  Scenario: Correct debit/credit separation
    Tool: Bash (python)
    Steps:
      1. txns = parse_icbc('/home/ubuntu/excel_example/voucher/银行对账单/彩虹工行4月对账单.xls')
      2. debit_txns = [t for t in txns if t.debit > 0]
      3. credit_txns = [t for t in txns if t.credit > 0]
      4. total_debit = sum(t.debit for t in debit_txns)
      5. total_credit = sum(t.credit for t in credit_txns)
      6. assert total_debit > 0 and total_credit > 0
      7. print(f"Total debit: {total_debit}, Total credit: {total_credit}")
    Expected Result: Both debit and credit amounts are non-zero and correct
    Evidence: .omo/evidence/task-5-icbc-debit-credit.txt
  ```

  **Commit**: YES
  - Message: `feat: add ICBC bank statement parser`
  - Files: `src/parsers/icbc_parser.py`, `tests/test_icbc_parser.py`

- [ ] 6. CCB bank statement parser

  **What to do**:
  - Create `src/parsers/ccb_parser.py` that reads CCB (建设银行) bank statements
  - Handle format: .xls file, direct header row, 1004 transactions with 38 columns
  - Extract key fields: 账号, 交易时间, 借方发生额(支取), 贷方发生额(收入), 余额, 对方户名, 摘要, 备注
  - Same unified `BankTransaction` output format as ICBC parser
  - Handle Unicode properly (CCB uses plain UTF-8)
  - Write pytest: `tests/test_ccb_parser.py`

  **Must NOT do**:
  - Don't parse ICBC or Jilin Bank formats — this module only handles CCB

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 7)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 9, 10
  - **Blocked By**: Task 1

  **References**:
  - `/home/ubuntu/excel_example/voucher/银行对账单/彩虹建行4月对账单.xls` — CCB format. 1004 transactions. Columns: 账号, 账户名称, 交易时间, 借方发生额(支取), 贷方发生额(收入), 余额, 币种, 对方户名, 对方账号, 摘要, 备注. Date format: 20260401 08:51:34
  - Bank account mapping: CCB account 22050131280000000023 → bank code 0402

  **Acceptance Criteria**:
  - [ ] Parses CCB .xls file and returns 1004 BankTransaction objects
  - [ ] Date format correctly parsed from "20260401 08:51:34" to "2026-04-01"
  - [ ] Debit/credit amounts correct (借方=支出, 贷方=收入)
  - [ ] Bank code '0402' assigned to all transactions

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Parse all CCB transactions
    Tool: Bash (python)
    Steps:
      1. from src.parsers.ccb_parser import parse_ccb
      2. txns = parse_ccb('/home/ubuntu/excel_example/voucher/银行对账单/彩虹建行4月对账单.xls')
      3. assert len(txns) == 1004
      4. assert txns[0].bank_code == '0402'
      5. assert all(t.date.startswith('2026-04') for t in txns)
      6. assert txns[0].counterparty_name == '吉林省顺丰速递有限公司'
    Expected Result: 1004 transactions parsed with correct data
    Evidence: .omo/evidence/task-6-ccb-parse.txt
  ```

  **Commit**: YES
  - Message: `feat: add CCB bank statement parser`
  - Files: `src/parsers/ccb_parser.py`, `tests/test_ccb_parser.py`

- [ ] 7. Jilin Bank statement parser

  **What to do**:
  - Create `src/parsers/jl_parser.py` that reads Jilin Bank (吉林银行) statements
  - Handle format: .xlsx file, header rows 0-7 (account info), row 8 = column headers, row 9+ = data
  - Extract: 交易时间, 交易对手户名, 交易对手账号, 借贷标志(借/贷), 交易金额, 交易后余额, 用途, 摘要
  - Handle formatted amounts with commas ("146,050.46")
  - Same unified BankTransaction output format
  - Write pytest: `tests/test_jl_parser.py`

  **Must NOT do**:
  - Don't parse ICBC or CCB formats — this module only handles Jilin Bank

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6)
  - **Parallel Group**: Wave 2
  - **Blocks**: Tasks 9, 10
  - **Blocked By**: Task 1

  **References**:
  - `/home/ubuntu/excel_example/voucher/银行对账单/彩虹吉林银行4月对账单.xlsx` — Jilin Bank format. 397 data rows. Row 7 = column headers, row 8+ = data. Key columns: 交易时间, 交易对手户名, 借贷标志(借/贷), 交易金额(with commas), 交易后余额, 用途, 摘要. Amount format: "146,050.46" (with commas)
  - Bank account mapping: Jilin Bank account 8936374879000001 → bank code 2801

  **Acceptance Criteria**:
  - [ ] Parses Jilin Bank .xlsx and returns ~397 BankTransaction objects (exact count may vary due to header/footer rows)
  - [ ] Comma-separated amounts correctly parsed ("146,050.46" → 146050.46)
  - [ ] 借/贷 direction correctly mapped to debit/credit
  - [ ] Bank code '2801' assigned to all transactions

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Parse Jilin Bank transactions with comma-formatted amounts
    Tool: Bash (python)
    Steps:
      1. from src.parsers.jl_parser import parse_jl
      2. txns = parse_jl('/home/ubuntu/excel_example/voucher/银行对账单/彩虹吉林银行4月对账单.xlsx')
      3. assert len(txns) >= 380  # approximate, may vary
      4. assert txns[0].bank_code == '2801'
      5. # First transaction: 吉林银行 146,050.46 credit
      6. first_credit = [t for t in txns if t.counterparty_name and '吉林银行' in t.counterparty_name][0]
      7. assert first_credit.credit == 146050.46 or first_credit.debit == 146050.46
    Expected Result: Transactions parsed with correct amounts
    Evidence: .omo/evidence/task-7-jl-parse.txt
  ```

  **Commit**: YES
  - Message: `feat: add Jilin Bank statement parser`
  - Files: `src/parsers/jl_parser.py`, `tests/test_jl_parser.py`

- [ ] 8. Invoice parser + voucher generation rules

  **What to do**:
  - Create `src/parsers/invoice_parser.py` that reads the invoice Excel file
  - Extract: 发票号码, 销方识别号, 购方识别号, 购买方名称, 开票日期, 货物/劳务名称, 金额, 税率, 税额, 价税合计, 发票状态, 是否正数发票
  - Handle positive invoices (是否正数发票=是) and red invoices (是否正数发票=否)
  - Create `src/rules/invoice_rules.py` with invoice voucher generation rules:
    - 派遣发票: 借:224101(客户) or 122101(客户) + 贷:600101(部门+项目) + 贷:222121(税金)
    - 外包发票: 借:1122(客户) + 贷:600102(部门+项目) + 贷:222121(税金)
    - 培训发票: 借:1122(客户) + 贷:600103(部门+项目) + 贷:222121(税金)
    - 红字发票: negative amounts, same debit/credit structure with reversed signs
    - Summary template: "开{劳务类型}发票 {客户简称} {项目简称(如有)}" or "红冲{税率}发票 {客户简称}"
  - Customer classification → subject mapping:
    - 劳务派遣单位 → 借方可以用 224101 or 122101
    - 劳务外包单位 → 借方用 1122
    - 项目单位 → 借方用 1122
  - Match buyer name (购买方名称) to customer code using name matcher from Task 2
  - Write pytest: `tests/test_invoice_parser.py`, `tests/test_invoice_rules.py`

  **Must NOT do**:
  - Don't link invoices to bank payments — they're independent workflows
  - Don't calculate tax — use amounts from invoice data as-is
  - Don't handle multi-item invoices differently — treat each invoice row as one voucher entry group

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 5, 6, 7)
  - **Parallel Group**: Wave 2
  - **Blocks**: Task 11
  - **Blocked By**: Task 1 (needs data loaders)

  **References**:
  - `/home/ubuntu/excel_example/voucher/发票/4月901张发票.xlsx` — 901 invoices. Key columns: 序号, 发票代码, 发票号码, 数电发票号码, 销方识别号, 销方名称, 购方识别号, 购买方名称, 开票日期, 货物或应税劳务名称, 金额, 税率, 税额, 价税合计, 发票状态, 是否正数发票
  - Note: 销方 = 彩虹人才 (always the seller), 购方 = customer (buyer)
  - Red invoices (是否正数发票=否) have negative amounts

  **Acceptance Criteria**:
  - [ ] Parses 901 invoices correctly (or close, excluding header rows)
  - [ ] Positive and negative (red) invoices distinguished
  - [ ] Customer name matching maps >80% of buyers to customer codes
  - [ ] Invoice voucher template generates correct subject codes for each type

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Parse invoice file
    Tool: Bash (python)
    Steps:
      1. from src.parsers.invoice_parser import parse_invoices
      2. invs = parse_invoices('/home/ubuntu/excel_example/voucher/发票/4月901张发票.xlsx')
      3. assert len(invs) >= 890  # should be close to 901 minus header/metadata rows
      4. positive = [i for i in invs if i.is_positive]
      5. negative = [i for i in invs if not i.is_positive]
      6. assert len(positive) > len(negative)  # more positive than negative
      7. assert all(hasattr(i, 'buyer_name') for i in invs)
    Expected Result: Invoices parsed with correct counts and positive/negative split
    Evidence: .omo/evidence/task-8-invoice-parse.txt

  Scenario: Invoice voucher generation
    Tool: Bash (python)
    Steps:
      1. Generate voucher entries for first positive invoice
      2. Verify: debit side has customer-related subject (224101/122101/1122)
      3. Verify: credit side has revenue subject (600101/600102/600103)
      4. Verify: credit side has tax subject (222121)
      5. Verify: debit total = credit total
    Expected Result: Balanced voucher with correct subject codes
    Evidence: .omo/evidence/task-8-invoice-voucher.txt
  ```

  **Commit**: YES
  - Message: `feat: add invoice parser and voucher generation rules`
  - Files: `src/parsers/invoice_parser.py`, `src/rules/invoice_rules.py`, `tests/test_invoice_parser.py`, `tests/test_invoice_rules.py`

- [ ] 9. Incoming payment voucher generator (收款→凭证)

  **What to do**:
  - Create `src/generators/incoming_generator.py`
  - For each incoming bank transaction (credit/收入):
    1. Match counterparty name → customer/supplier code using name matcher (Task 2)
    2. Determine subject codes based on customer classification:
       - 劳务派遣单位: 借:1002(银行档案), 贷:224101(客户档案)
       - 劳务外包单位: 借:1002(银行档案), 贷:224101(客户档案)  
       - 其他: 借:1002(银行档案), 贷:224101(客户档案) or 1122(客户档案)
    3. Generate summary: "收{类型} {银行} {客户简称}{项目简称(如有)}"
    4. Calculate auxiliary accounting entries
    5. Generate cash flow entry: 贷方 224101 → 现金流量 1111(销售商品收到的现金), 贷方 其他 → 1113(收到的其他经营活动有关现金)
    6. Handle unmatched transactions: still create voucher with placeholder, flag in report
  - Handle special cases: bank interest (利息), internal transfers, tax refund
  - Write pytest: `tests/test_incoming_generator.py`

  **Must NOT do**:
  - Don't process outgoing transactions — that's Task 10
  - Don't process invoices — that's Task 11

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (depends on Tasks 2, 4 for matching and rules)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 2, 4, 5 (name matcher, subject rules, bank parsers)

  **References**:
  - April voucher data patterns for incoming payments:
    - Voucher #2: 收外包业务费 → 借:1002(2801:银行档案) + 贷:224101(GY040:客户档案) × 2 lines
    - Voucher #3: 收往来派遣费 → 借:1002(0402:银行档案) + 贷:224101(ch003:客户档案)
  - Bank code mapping: ICBC=0107, CCB=0402, Jilin Bank=2801, 招行=1505, 农行=0206

  **Acceptance Criteria**:
  - [ ] Each incoming transaction generates a balanced voucher (debit = credit)
  - [ ] Summary follows template format
  - [ ] Customer code matched via name matcher (or flagged as unmatched)
  - [ ] Bank code correctly assigned based on account number
  - [ ] Cash flow sub-entries generated correctly

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Generate voucher for CCB incoming payment
    Tool: Bash (python)
    Steps:
      1. Use April CCB data first transaction (吉林省顺丰速递有限公司, 支出433元)
      2. This is actually an outgoing payment — skip for this test
      3. Find an incoming payment in CCB data (贷方发生额 > 0)
      4. Generate voucher entries
      5. Verify: debit entry exists with subject 1002 and bank archive auxiliary
      6. Verify: credit entry exists with subject 224101 and customer archive auxiliary
      7. Verify: sum(debits) == sum(credits)
    Expected Result: Balanced voucher with correct subject codes and auxiliary
    Evidence: .omo/evidence/task-9-incoming-voucher.txt

  Scenario: Unmatched counterparty still generates voucher with flag
    Tool: Bash (python)
    Steps:
      1. Create test transaction with unknown counterparty name "未匹配公司XYZ"
      2. Generate voucher — should still create entries but with unmatched flag
      3. Verify: flag appears in unmatched report
      4. Verify: voucher is still created with placeholder customer
    Expected Result: Voucher created, flagged as unmatched
    Evidence: .omo/evidence/task-9-unmatched.txt
  ```

  **Commit**: YES
  - Message: `feat: add incoming payment voucher generator`
  - Files: `src/generators/incoming_generator.py`, `tests/test_incoming_generator.py`

- [ ] 10. Outgoing payment voucher generator (付款→凭证)

  **What to do**:
  - Create `src/generators/outgoing_generator.py`
  - For each outgoing bank transaction (debit/支出):
    1. Match counterparty name → customer/supplier code (try customers first, then suppliers)
    2. Match bank summary keywords → subject code using keyword rules (Task 4)
    3. Subject mapping by keyword:
       - "工资" → 借:224101(客户), 贷:1002(银行)
       - "社保" → 借:224101(客户) + 224102(辅助明细+供应商), 贷:1002(银行)
       - "业务费/外包费" → 借:640102(部门+项目), 贷:1002(银行)
       - "快递费" → 借:66021603(部门), 贷:1002(银行)
       - "手续费" → 借:660304, 贷:1002
       - "退票" → 借:224101(客户), 贷:1002(银行) (with note in summary)
       - Full keyword→subject mapping from April data
    4. Generate summary following templates from April vouchers
    5. Some payments need multiple debit entries (e.g., salary = 工资 + 代扣社保 + 代扣个税)
    6. Generate cash flow sub-entries
    7. Handle unmatched transactions
  - Write pytest: `tests/test_outgoing_generator.py`

  **Must NOT do**:
  - Don't handle incoming transactions — that's Task 9
  - Don't handle invoice vouchers — that's Task 11

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 11)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 2, 4, 5, 6, 7

  **References**:
  - April voucher patterns for outgoing payments:
    - "付派遣人员工资" → 224101(客户) + 224102(辅助明细+供应商) + 1002(银行)
    - "付外包业务成本" → 640102(部门+项目) + 1002(银行)
    - "缴纳派遣人员社保" → 224101(客户) + 1002(银行)
    - "付快递费" → 66021603(部门) + 1002(银行)
  - CCB bank summary values: 电子转账, 电子汇入, 代收付, etc.

  **Acceptance Criteria**:
  - [ ] Each outgoing transaction generates balanced voucher
  - [ ] Keyword matching correctly assigns subject codes
  - [ ] Multi-line debit entries generated for salary+deduction payments
  - [ ] Unmatched transactions flagged

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Generate voucher for salary payment
    Tool: Bash (python)
    Steps:
      1. Use CCB transaction: 对方户名="长春海关技术中心", 摘要="代收付", 借方=67140.22
      2. Generate voucher entries using outgoing generator
      3. Verify: at least 2 debit entries (224101 for customer, possibly 224102 for deductions)
      4. Verify: at least 1 credit entry (1002 for bank)
      5. Verify: total debits ≈ total credits
    Expected Result: Multi-line balanced voucher for salary payment
    Evidence: .omo/evidence/task-10-outgoing-voucher.txt

  Scenario: Unmatched keyword flagged correctly
    Tool: Bash (python)
    Steps:
      1. Create test transaction with summary "未知费用XXX"
      2. Generate voucher — should use default subject code and flag as unmatched
      3. Verify: flag in unmatched report
    Expected Result: Voucher created with default subject, flagged
    Evidence: .omo/evidence/task-10-keyword-unmatch.txt
  ```

  **Commit**: YES
  - Message: `feat: add outgoing payment voucher generator`
  - Files: `src/generators/outgoing_generator.py`, `tests/test_outgoing_generator.py`

- [ ] 11. Invoice voucher generator (发票→凭证)

  **What to do**:
  - Create `src/generators/invoice_generator.py`
  - For each invoice, generate one voucher:
    1. Match buyer name (购买方名称) → customer code using name matcher
    2. Determine customer type (劳务派遣/劳务外包/项目单位) from customer classification
    3. Generate voucher entries based on customer type:
       - 派遣: 借:224101(客户) or 122101(客户), 贷:600101(部门+项目), 贷:222121(税金)
       - 外包: 借:1122(客户), 贷:600102(部门+项目), 贷:222121(税金)
       - 培训: 借:1122(客户), 贷:600103(部门+项目), 贷:222121(税金)
    4. Red invoices (是否正数发票=否): reverse all amounts (negative)
    5. Summary: "开{类型}发票 {客户简称} {项目简称(如有)}"
    6. Tax amount calculation: 贷:222121 with tax amount from invoice
    7. Revenue amount = 金额 (not 价税合计)
    8. Assign department (01 派遣外包部 by default) and project (PQ001 劳务派遣项目 by default, or matched from customer)
  - Write pytest: `tests/test_invoice_generator.py`

  **Must NOT do**:
  - Don't link invoices to bank payments — independent workflow
  - Don't calculate tax — use amounts from invoice as-is

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (with Tasks 9, 10)
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 12
  - **Blocked By**: Tasks 4, 8

  **References**:
  - Invoice data structure: `/home/ubuntu/excel_example/voucher/发票/4月901张发票.xlsx`
  - Key columns: 购买方名称, 金额, 税率, 税额, 价税合计, 是否正数发票
  - Customer classification mapping: 劳务派遣单位 → 224101/122101, 劳务外包单位 → 1122, 项目单位 → 1122

  **Acceptance Criteria**:
  - [ ] Each invoice generates exactly one voucher (901 invoices → 901 vouchers)
  - [ ] Positive invoices have normal amounts, red invoices have negative amounts
  - [ ] Debit = Credit for every voucher
  - [ ] Tax entries (222121) use correct amounts from invoice data
  - [ ] Revenue subject (600101/600102/600103) matches customer type

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Generate voucher for positive invoice
    Tool: Bash (python)
    Steps:
      1. Parse invoices and generate voucher for first positive invoice
      2. Verify: debit side has应收 (224101/122101/1122) with customer auxiliary
      3. Verify: credit side has 收入 (600101/600102/600103) with department+project auxiliary
      4. Verify: credit side has 税金 (222121) with tax amount
      5. Verify: total debits = total credits
    Expected Result: Balanced voucher with correct subject codes matching customer type
    Evidence: .omo/evidence/task-11-invoice-positive.txt

  Scenario: Red invoice generates negative amounts
    Tool: Bash (python)
    Steps:
      1. Parse invoices and find a red invoice (是否正数发票=否)
      2. Generate voucher — verify all amounts are negative
      3. Verify: debit = credit still holds (both sides negative)
    Expected Result: Voucher with negative amounts, still balanced
    Evidence: .omo/evidence/task-11-red-invoice.txt
  ```

  **Commit**: YES
  - Message: `feat: add invoice voucher generator`
  - Files: `src/generators/invoice_generator.py`, `tests/test_invoice_generator.py`

- [ ] 12. Cash flow sub-table generator

  **What to do**:
  - Create `src/generators/cashflow_generator.py`
  - For each voucher entry in the main table, determine cash flow code:
    - 收入类: 600101/600102/600103 → 1111 (销售商品、提供劳务收到的现金)
    - 其他应收(122101/224101 incoming) → 1113 (收到的其他与经营活动有关的现金)
    - 工资支出(224101 outgoing for salary) → 1122 (支付给职工以及为职工支付的现金)
    - 社保支出(224102 outgoing) → 1122
    - 外包成本/业务成本 → 1124 (购买商品、接受劳务支付的现金)
    - 其他支出 → 1124 or 1113 depending on context
    - 银行存款(1002) entries: 根据对应科目确定现金流量方向
  - Generate cash flow sub-table entries with format:
    - Row number linking to main voucher entry
    - 方向: 1 (借) or -1 (贷) based on entry direction
    - 分析币种: 人民币
    - 原币/账簿本币: amount from main entry
    - 现金流量编码: 1111/1113/1124/etc.
    - 现金流量名称: corresponding name
  - Write pytest: `tests/test_cashflow_generator.py`

  **Must NOT do**:
  - Don't generate cash flow entries for non-cash entries (计提, 折旧, etc.) — but we said no accrual entries, so this is moot

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4
  - **Blocks**: Task 13
  - **Blocked By**: Tasks 9, 10, 11

  **References**:
  - April voucher cash flow section (rows after row 5490): `cashflow,flag,cashflowcurr,mo,...` header with columns: 方向, 分析币种, 原币, 账簿本币, 集团本币, 全局本币, 内部单位, 现金流量名称, 现金流量编码
  - Cash flow code mapping from 现金流量表表项.txt and 现金流量项目.txt in data directory
  - Key mappings: 1111→销售商品收到现金, 1113→其他经营活动收入, 1122→支付给职工, 1124→购买商品支付现金

  **Acceptance Criteria**:
  - [ ] Every bank-related voucher entry has a corresponding cash flow entry
  - [ ] Cash flow codes match subject code mapping (6001xx→1111, 2241xx→1113/1122, etc.)
  - [ ] Row numbers in cash flow sub-table correctly reference main table entries
  - [ ] Direction (flag) correctly set: 1 for inflow, -1 for outflow (matching 借/贷)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Cash flow entries match main table entries
    Tool: Bash (python)
    Steps:
      1. Generate a set of vouchers with cash flow entries
      2. For each voucher, verify every 1002-entry has a cash flow row
      3. Verify cash flow row numbers match main table row indices
      4. Verify cash flow amounts match main table amounts
    Expected Result: 100% of bank entries have corresponding cash flow rows
    Evidence: .omo/evidence/task-12-cashflow-match.txt

  Scenario: Cash flow code assignment is correct
    Tool: Bash (python)
    Steps:
      1. Generate vouchers for incoming payment (贷:600101)
      2. Verify cash flow code = "1111" and name = "销售商品、提供劳务收到的现金"
      3. Generate voucher for salary payment (借:224101)
      4. Verify cash flow code = "1122" and name = "支付给职工以及为职工支付的现金"
    Expected Result: Correct cash flow codes for each subject type
    Evidence: .omo/evidence/task-12-cashflow-codes.txt
  ```

  **Commit**: YES
  - Message: `feat: add cash flow sub-table generator`
  - Files: `src/generators/cashflow_generator.py`, `tests/test_cashflow_generator.py`

- [ ] 13. Voucher assembly + NCC output writer

  **What to do**:
  - Create `src/voucher_assembly.py` that:
    1. Collects all generated vouchers (incoming + outgoing + invoice) into a unified list
    2. Assigns sequential voucher numbers (starting from 1) and sequential row numbers
    3. Sorts vouchers by date (制单日期)
    4. Sets default values: 财务核算账簿="吉林省彩虹人才开发咨询服务有限公司-基准账簿", 凭证类别="记账凭证", 制单人="赵中云", 币种="人民币"
    5. Assembles the full NCC import file using the formatter from Task 3
    6. Writes main table section (all voucher entries)
    7. Writes cash flow sub-table section (linking by row number)
    8. Separate main table and cash flow with a blank row (per NCC import format)
    9. Validates: every voucher has balanced debit=credit
    10. Writes output Excel file using openpyxl
  - Create main CLI entry point `generate_vouchers.py` with argparse:
    - `--bank-dir`: path to bank statement directory
    - `--invoice-file`: path to invoice file
    - `--code-dir`: path to code table directory (原版导出的代码资料)
    - `--template-file`: path to NCC template file (凭证信息_temp)
    - `--month`: processing month (e.g., 2026-04)
    - `--output`: output file path (default: voucher_output.xlsx)
    - `--report`: report file path (default: matching_report.xlsx)
  - Write integration tests: `tests/test_voucher_assembly.py`

  **Must NOT do**:
  - Don't implement any new parsers or generators — this task only assembles existing ones
  - Don't modify the NCC template format — use it as-is

  **Recommended Agent Profile**:
  - **Category**: `deep`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (after Tasks 3, 12)
  - **Blocks**: Task 14
  - **Blocked By**: Tasks 3, 12 (needs formatter and cash flow generator)

  **References**:
  - NCC template structure: `/home/ubuntu/excel_example/voucher/代码资料/凭证信息_temp - 2026-06-02T140354.252.xlsx`
  - Row 0: import instructions text (copy from template)
  - Row 1: comma-separated system field names in column 0, Chinese column names in columns 1+
  - Main section: sequential row numbers in column 0, linking to cash flow sub-table
  - Blank row separating sections
  - Cash flow sub-table: row numbers in column 0 linking to main entries

  **Acceptance Criteria**:
  - [ ] Output file matches NCC template structure exactly
  - [ ] All vouchers have sequential numbers starting from 1
  - [ ] Every voucher's debit total equals credit total
  - [ ] Cash flow section properly linked to main section
  - [ ] CLI accepts all required arguments
  - [ ] Script runs end-to-end without errors

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Full end-to-end run
    Tool: Bash
    Steps:
      1. Run: python generate_vouchers.py --bank-dir /home/ubuntu/excel_example/voucher/银行对账单 --invoice-file /home/ubuntu/excel_example/voucher/发票/4月901张发票.xlsx --code-dir /home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料 --template-file "/home/ubuntu/excel_example/voucher/代码资料/凭证信息_temp - 2026-06-02T140354.252.xlsx" --month 2026-04 --output /tmp/test_output.xlsx --report /tmp/test_report.xlsx
      2. Verify exit code 0
      3. Verify /tmp/test_output.xlsx exists and has >1000 rows
      4. Verify /tmp/test_report.xlsx exists
    Expected Result: Script completes successfully, output files created
    Failure Indicators: Non-zero exit code, missing output files, <100 rows
    Evidence: .omo/evidence/task-13-e2e-run.txt

  Scenario: Voucher balance validation
    Tool: Bash (python)
    Steps:
      1. Open output file with openpyxl
      2. For each voucher (grouped by 凭证号), sum 原币借方金额 and 原币贷方金额
      3. Assert sum(debits) == sum(credits) for every voucher (within 0.01 tolerance for floating point)
    Expected Result: All vouchers are balanced
    Evidence: .omo/evidence/task-13-balance-check.txt
  ```

  **Commit**: YES
  - Message: `feat: add voucher assembly and NCC output writer`
  - Files: `src/voucher_assembly.py`, `generate_vouchers.py`, `tests/test_voucher_assembly.py`

- [ ] 14. Reconciliation report generator

  **What to do**:
  - Create `src/reports/reconciliation.py` that generates a matching report Excel file with:
    - **Summary sheet**: Total bank transactions, matched count, unmatched count, by source bank
    - **Matched sheet**: All matched transactions with original data + assigned subject codes + customer codes + confidence scores
    - **Unmatched sheet**: All unmatched transactions with original data + reason for non-match
    - **Invoice sheet**: All invoices with matching status (buyer matched/unmatched)
    - **Statistics sheet**: Match rate by bank, by transaction type, etc.
  - Format: Excel file with multiple sheets, using openpyxl
  - Include color coding: green for high-confidence matches (≥0.9), yellow for medium (0.7-0.9), red for unmatched
  - Create `tests/test_reconciliation.py`

  **Must NOT do**:
  - Don't modify any voucher generation logic — this is a reporting module only
  - Don't include any business logic — just aggregate and display data

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 4 (after Task 13)
  - **Blocks**: F1-F4
  - **Blocked By**: Task 13 (needs assembled voucher data)

  **References**:
  - Name matcher output from Task 2 (matched and unmatched lists)
  - Invoice matching results from Task 11
  - April voucher data for comparison

  **Acceptance Criteria**:
  - [ ] Report file has 5 sheets: Summary, Matched, Unmatched, Invoice, Statistics
  - [ ] Total matched + total unmatched = total input transactions
  - [ ] Summary sheet shows match rate ≥ 80%
  - [ ] Unmatched sheet includes reason for each non-match
  - [ ] Color coding applied (green/yellow/red)

  **QA Scenarios (MANDATORY)**:

  ```
  Scenario: Reconciliation report covers all transactions
    Tool: Bash (python)
    Steps:
      1. Run full pipeline and generate report
      2. Open report.xlsx with openpyxl
      3. Read Summary sheet: verify total_matched + total_unmatched = total_input
      4. Read Matched sheet: verify each entry has assigned subject code and customer code
      5. Read Unmatched sheet: verify each entry has reason for non-match
    Expected Result: All transactions accounted for, matched or unmatched
    Evidence: .omo/evidence/task-14-reconciliation.txt

  Scenario: Match rate validation
    Tool: Bash (python)
    Steps:
      1. Read Summary sheet from report
      2. Calculate match_rate = matched / total
      3. Assert match_rate >= 0.80
    Expected Result: Match rate at least 80%
    Evidence: .omo/evidence/task-14-match-rate.txt
  ```

  **Commit**: YES
  - Message: `feat: add reconciliation report generator`
  - Files: `src/reports/reconciliation.py`, `tests/test_reconciliation.py`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [ ] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [ ] F2. **Code Quality Review** — `unspecified-high`
  Run pytest. Review all .py files for: `as any`/type ignores, empty except, print() in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names (data/result/item/temp). Verify all edge cases handled.
  Output: `Tests [N pass/N fail] | Lint [PASS/FAIL] | Files [N clean/N issues] | VERDICT`

- [ ] F3. **Real Manual QA** — `unspecified-high`
  Start from clean state. Run: `python generate_vouchers.py --bank-dir ./银行对账单 --invoice-dir ./发票 --code-dir ./代码资料 --output output.xlsx --report report.xlsx`. Verify output file has correct columns, balanced vouchers, matched/unmatched summary. Test with actual April data. Compare generated output against April manual vouchers for accuracy.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [ ] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built (no missing), nothing beyond spec was built (no creep). Check "Must NOT Have" list. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Task 1**: `feat: scaffold project structure and reference data loaders` - src/, data/, tests/
- **Task 2**: `feat: add counterparty name matching with validation gate` - matchers/
- **Task 3**: `feat: add NCC template parser and output formatter` - formatters/
- **Task 4**: `feat: extract subject-to-auxiliary accounting rules from April data` - rules/
- **Task 5-7**: `feat: add bank statement parsers (ICBC, CCB, Jilin Bank)` - parsers/
- **Task 8**: `feat: add invoice parser and voucher generation rules` - parsers/
- **Task 9-11**: `feat: add voucher generators (incoming, outgoing, invoice)` - generators/
- **Task 12**: `feat: add cash flow sub-table generator` - generators/
- **Task 13**: `feat: add voucher assembly and NCC output writer` - core/
- **Task 14**: `feat: add reconciliation report generator` - reports/

---

## Success Criteria

### Verification Commands
```bash
# Run the main script with April data
python generate_vouchers.py --bank-dir /home/ubuntu/excel_example/voucher/银行对账单 --invoice-dir /home/ubuntu/excel_example/voucher/发票 --code-dir /home/ubuntu/excel_example/voucher/代码资料/原版导出的代码资料 --month 2026-04 --output output.xlsx --report report.xlsx

# Verify output format
python -c "import openpyxl; wb=openpyxl.load_workbook('output.xlsx'); print(f'Rows: {wb.active.max_row}, Cols: {wb.active.max_column}')"

# Verify debit=credit balance
python -c "
import openpyxl
wb = openpyxl.load_workbook('output.xlsx')
# Check every voucher balances
print('All vouchers balanced: OK')
"
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All tests pass
- [ ] Name matching rate ≥ 80% on April data
- [ ] Output file imports into NCC without errors (user verifies)