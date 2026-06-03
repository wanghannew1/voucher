"""
凭证生成模块：根据匹配结果生成进账凭证分录
"""
from typing import List, Dict
from dataclasses import dataclass, field


@dataclass
class VoucherEntry:
    """凭证分录"""
    row_no: int = 0                 # 行号
    accounting_book: str = "吉林省彩虹人才开发咨询服务有限公司-基准账簿"
    voucher_type: str = "记账凭证"
    voucher_no: int = 0             # 凭证号
    attachment: str = ""
    preparer: str = "赵中云"
    prepare_date: str = ""          # 制单日期
    summary: str = ""               # 摘要
    liability_center: str = ""
    subject_code: str = ""          # 科目编码
    subject_name: str = ""          # 科目名称
    currency: str = "人民币"
    debit_foreign: float = 0.0      # 原币借方金额
    debit_local: float = 0.0        # 本币借方金额
    unit_name: str = "吉林省彩虹人才开发咨询服务有限公司"
    aux1: str = ""                  # 辅助核算1
    aux2: str = ""                  # 辅助核算2
    cash_flow_code: str = ""        # 现金流量编码
    cash_flow_name: str = ""        # 现金流量名称


def generate_summary(business_type: str, bank_name: str, customer_name: str, project_name: str = "") -> str:
    """生成摘要"""
    parts = [business_type, bank_name, customer_name]
    if project_name:
        parts.append(project_name)
    return " ".join(parts)


def generate_voucher(match_result, voucher_no: int) -> List[VoucherEntry]:
    """根据匹配结果生成一张凭证的所有分录"""
    tx = match_result.transaction
    inv = match_result.matched_invoice
    entries = []
    date_str = tx.date

    # 摘要
    bank_short = tx.bank_name  # 吉林银行/工行/建行
    cust_name = match_result.customer_name
    summary = f"收往来派遣费 {bank_short} {cust_name}"

    if inv and inv.is_positive:
        # ====== 匹配到发票的完整凭证（4条分录）======
        total = inv.total_amount
        deduction = inv.deduction
        tax = inv.tax_amount
        # 管理费中收入部分 = 管理费 - 税额
        # 但注意：发票备注中的"管理费"可能已经是含税的，而收入是不含税的
        # 根据用户例子：管理费1520，税额86.04，收入1433.96
        # 所以收入 = 管理费 - 税额
        management_fee = inv.management_fee
        income_amount = management_fee - tax if management_fee > tax else inv.amount - deduction if inv.amount > deduction else total - deduction - tax

        # 分录1: 借 1002 银行存款
        entry1 = VoucherEntry(
            row_no=voucher_no,
            voucher_no=voucher_no,
            prepare_date=date_str,
            summary=summary,
            subject_code="1002",
            subject_name="银行存款",
            debit_foreign=total,
            debit_local=total,
            aux1=f"{tx.bank_code}:银行档案",
            cash_flow_code="1113",
            cash_flow_name="收到的其他与经营活动有关的现金"
        )
        entries.append(entry1)

        # 分录2: 贷 224101 其他应付款-客户往来（扣除额/工资部分）
        if deduction > 0:
            entry2 = VoucherEntry(
                row_no=voucher_no,
                voucher_no=voucher_no,
                prepare_date=date_str,
                summary=summary,
                subject_code="224101",
                subject_name="其他应付款-客户往来",
                debit_foreign=-deduction,  # 负数表示贷方
                debit_local=-deduction,
                aux1=f"{match_result.customer_code}:客户档案" if match_result.customer_code else "",
            )
            entries.append(entry2)

        # 分录3: 贷 222121 应交税费-简易计税（税额）
        if tax > 0:
            entry3 = VoucherEntry(
                row_no=voucher_no,
                voucher_no=voucher_no,
                prepare_date=date_str,
                summary=summary,
                subject_code="222121",
                subject_name="应交税费-简易计税",
                debit_foreign=-tax,
                debit_local=-tax,
            )
            entries.append(entry3)

        # 分录4: 贷 600101 派遣收入（管理费中的收入部分）
        if income_amount > 0:
            entry4 = VoucherEntry(
                row_no=voucher_no,
                voucher_no=voucher_no,
                prepare_date=date_str,
                summary=summary,
                subject_code="600101",
                subject_name="派遣收入",
                debit_foreign=-income_amount,
                debit_local=-income_amount,
                aux1="01:部门",
                aux2="PQ001:项目档案",
            )
            entries.append(entry4)

    else:
        # ====== 未匹配到发票的简化凭证（2条分录）======
        total = tx.credit

        # 分录1: 借 1002 银行存款
        entry1 = VoucherEntry(
            row_no=voucher_no,
            voucher_no=voucher_no,
            prepare_date=date_str,
            summary=summary,
            subject_code="1002",
            subject_name="银行存款",
            debit_foreign=total,
            debit_local=total,
            aux1=f"{tx.bank_code}:银行档案",
            cash_flow_code="1113",
            cash_flow_name="收到的其他与经营活动有关的现金"
        )
        entries.append(entry1)

        # 分录2: 贷 224101 其他应付款-客户往来
        entry2 = VoucherEntry(
            row_no=voucher_no,
            voucher_no=voucher_no,
            prepare_date=date_str,
            summary=summary,
            subject_code="224101",
            subject_name="其他应付款-客户往来",
            debit_foreign=-total,
            debit_local=-total,
            aux1=f"{match_result.customer_code}:客户档案" if match_result.customer_code else "",
        )
        entries.append(entry2)

    return entries


def generate_all_vouchers(match_results: List) -> List[List[VoucherEntry]]:
    """为所有匹配结果生成凭证"""
    vouchers = []
    for i, result in enumerate(match_results, start=1):
        entries = generate_voucher(result, voucher_no=i)
        vouchers.append(entries)
        result.voucher_entries = entries
    return vouchers


def export_vouchers_to_list(vouchers: List[List[VoucherEntry]]) -> List[Dict]:
    """将凭证分录导出为字典列表，便于DataFrame/Excel导出"""
    rows = []
    for entries in vouchers:
        for e in entries:
            rows.append({
                '行号': e.row_no,
                '财务核算账簿': e.accounting_book,
                '凭证类别': e.voucher_type,
                '凭证号': e.voucher_no,
                '制单人': e.preparer,
                '制单日期': e.prepare_date,
                '摘要': e.summary,
                '科目编码': e.subject_code,
                '科目名称': e.subject_name,
                '币种': e.currency,
                '借方金额': e.debit_foreign if e.debit_foreign > 0 else 0,
                '贷方金额': -e.debit_foreign if e.debit_foreign < 0 else 0,
                '业务单元': e.unit_name,
                '辅助核算1': e.aux1,
                '辅助核算2': e.aux2,
                '现金流量编码': e.cash_flow_code,
                '现金流量名称': e.cash_flow_name,
            })
    return rows
