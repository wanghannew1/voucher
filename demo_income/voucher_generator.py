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
    cash_flows: list = field(default_factory=list)  # 现金流量子表 [(code, name, amount), ...]


def generate_summary(business_type: str, bank_name: str, customer_name: str, project_name: str = "") -> str:
    """生成摘要"""
    parts = [business_type, bank_name, customer_name]
    if project_name:
        parts.append(project_name)
    return " ".join(parts)


def generate_voucher(match_result, voucher_no: int) -> List[VoucherEntry]:
    """根据匹配结果生成一张凭证的所有分录"""
    tx = match_result.transaction
    invoices = match_result.matched_invoices if match_result.matched_invoices else (
        [match_result.matched_invoice] if match_result.matched_invoice else []
    )
    entries = []
    date_str = tx.date

    # 摘要
    bank_short = tx.bank_name
    cust_name = match_result.customer_name

    # 判断是否外包业务
    is_outsource = any(inv.is_outsource for inv in invoices) if invoices else False

    if is_outsource:
        # ====== 外包业务凭证 ======
        summary = f"收外包业务费 {bank_short} {match_result.customer_name}"
        total_amount = sum(inv.total_amount for inv in invoices)

        # 分录1: 借 1002 银行存款
        entry1 = VoucherEntry(
            row_no=voucher_no, voucher_no=voucher_no, prepare_date=date_str,
            summary=summary, subject_code="1002", subject_name="银行存款",
            debit_foreign=tx.credit, debit_local=tx.credit,
            aux1=f"{tx.bank_code}:银行档案",
            cash_flows=[("1113", "收到的其他与经营活动有关的现金", tx.credit)]
        )
        entries.append(entry1)

        # 分录2+: 贷 1122 应收账款（每张发票一行）
        for inv in invoices:
            entry = VoucherEntry(
                row_no=voucher_no, voucher_no=voucher_no, prepare_date=date_str,
                summary=summary, subject_code="1122", subject_name="应收账款",
                debit_foreign=-inv.total_amount, debit_local=-inv.total_amount,
                aux1=f"{match_result.customer_code}:客户档案" if match_result.customer_code else "",
            )
            entries.append(entry)

    elif invoices:
        # ====== 派遣业务凭证（有备注，含扣除额/管理费）======
        summary = f"收往来派遣费 {bank_short} {cust_name}"
        total_deduction = sum(inv.deduction for inv in invoices)
        total_tax = sum(inv.tax_amount for inv in invoices)
        total_management = sum(inv.management_fee for inv in invoices)
        total_income = total_management - total_tax if total_management > total_tax else 0

        # 分录1: 借 1002 银行存款
        entry1 = VoucherEntry(
            row_no=voucher_no, voucher_no=voucher_no, prepare_date=date_str,
            summary=summary, subject_code="1002", subject_name="银行存款",
            debit_foreign=tx.credit, debit_local=tx.credit,
            aux1=f"{tx.bank_code}:银行档案",
            cash_flows=[
                ("1113", "收到的其他与经营活动有关的现金", total_deduction),
                ("1111", "销售商品、提供劳务收到的现金", total_management),
            ]
        )
        entries.append(entry1)

        # 分录2: 贷 224101 其他应付款-客户往来（扣除额合计）
        if total_deduction > 0:
            entry2 = VoucherEntry(
                row_no=voucher_no, voucher_no=voucher_no, prepare_date=date_str,
                summary=summary, subject_code="224101", subject_name="其他应付款-客户往来",
                debit_foreign=-total_deduction, debit_local=-total_deduction,
                aux1=f"{match_result.customer_code}:客户档案" if match_result.customer_code else "",
            )
            entries.append(entry2)

        # 分录3: 贷 222121 应交税费-简易计税（税额合计）
        if total_tax > 0:
            entry3 = VoucherEntry(
                row_no=voucher_no, voucher_no=voucher_no, prepare_date=date_str,
                summary=summary, subject_code="222121", subject_name="应交税费-简易计税",
                debit_foreign=-total_tax, debit_local=-total_tax,
            )
            entries.append(entry3)

        # 分录4: 贷 600101 派遣收入（管理费-税额）
        if total_income > 0:
            entry4 = VoucherEntry(
                row_no=voucher_no, voucher_no=voucher_no, prepare_date=date_str,
                summary=summary, subject_code="600101", subject_name="派遣收入",
                debit_foreign=-total_income, debit_local=-total_income,
                aux1="01:部门", aux2="PQ001:项目档案",
            )
            entries.append(entry4)

    else:
        # ====== 未匹配到发票的简化凭证（2条分录）======
        total = tx.credit

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
            cash_flows=[
                ("1113", "收到的其他与经营活动有关的现金", total),
            ]
        )
        entries.append(entry1)

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
    """将凭证分录导出为字典列表，对齐系统导入格式（72列）+ 现金流子表"""
    rows = []
    for entries in vouchers:
        for e in entries:
            rows.append({
                '财务核算账簿': e.accounting_book,
                '凭证类别': e.voucher_type,
                '凭证号': e.voucher_no,
                '附单据数': e.attachment,
                '制单人': e.preparer,
                '制单日期': e.prepare_date,
                '摘要': e.summary,
                '利润中心': '',
                '科目编码': e.subject_code,
                '币种': e.currency,
                '原币借方金额': e.debit_foreign if e.debit_foreign > 0 else 0,
                '本币借方金额': e.debit_local if e.debit_local > 0 else 0,
                '集团本币借方金额': '',
                '全局本币借方金额': '',
                '业务单元': e.unit_name,
                '单价': '',
                '借方数量': '',
                '贷方数量': '',
                '原币贷方金额': -e.debit_foreign if e.debit_foreign < 0 else 0,
                '本币贷方金额': -e.debit_local if e.debit_local < 0 else 0,
                '集团本币贷方金额': '',
                '全局本币贷方金额': '',
                '票据号': '',
                '结算业务日期': '',
                '结算方式': '',
                '核销号': '',
                '业务日期': '',
                '银行账户': '',
                '票据类型': '',
                '账簿本币汇率': '',
                '集团本币汇率': '',
                '全局本币汇率': '',
                '辅助核算1': e.aux1,
                '辅助核算2': e.aux2,
                '辅助核算3': '',
                '辅助核算4': '',
                '辅助核算5': '',
                '辅助核算6': '',
                '辅助核算7': '',
                '辅助核算8': '',
                '辅助核算9': '',
                '分录自定义项1': '',
                '分录自定义项2': '',
                '分录自定义项3': '',
                '分录自定义项4': '',
                '分录自定义项5': '',
                '分录自定义项6': '',
                '分录自定义项7': '',
                '分录自定义项8': '',
                '分录自定义项9': '',
                '分录自定义项10': '',
                '分录自定义项11': '',
                '分录自定义项12': '',
                '分录自定义项13': '',
                '分录自定义项14': '',
                '分录自定义项15': '',
                '分录自定义项16': '',
                '分录自定义项17': '',
                '分录自定义项18': '',
                '分录自定义项19': '',
                '分录自定义项20': '',
                '分录自定义项21': '',
                '分录自定义项22': '',
                '分录自定义项23': '',
                '分录自定义项24': '',
                '分录自定义项25': '',
                '分录自定义项26': '',
                '分录自定义项27': '',
                '分录自定义项28': '',
                '分录自定义项29': '',
                '分录自定义项30': '',
            })
            # 现金流子表：1002分录拆成多条现金流记录
            if e.subject_code == "1002" and e.cash_flows:
                for code, name, amount in e.cash_flows:
                    if amount > 0:
                        rows.append({
                            '财务核算账簿': '',
                            '凭证类别': '',
                            '凭证号': '',
                            '附单据数': '',
                            '制单人': '',
                            '制单日期': '',
                            '摘要': '',
                            '利润中心': '',
                            '科目编码': '',
                            '币种': '',
                            '原币借方金额': amount,
                            '本币借方金额': amount,
                            '集团本币借方金额': '',
                            '全局本币借方金额': '',
                            '业务单元': '',
                            '单价': '',
                            '借方数量': '',
                            '贷方数量': '',
                            '原币贷方金额': 0,
                            '本币贷方金额': 0,
                            '集团本币贷方金额': '',
                            '全局本币贷方金额': '',
                            '票据号': '',
                            '结算业务日期': '',
                            '结算方式': '',
                            '核销号': '',
                            '业务日期': '',
                            '银行账户': '',
                            '票据类型': '',
                            '账簿本币汇率': '',
                            '集团本币汇率': '',
                            '全局本币汇率': '',
                            '辅助核算1': '',
                            '辅助核算2': '',
                            '辅助核算3': '',
                            '辅助核算4': '',
                            '辅助核算5': '',
                            '辅助核算6': '',
                            '辅助核算7': '',
                            '辅助核算8': '',
                            '辅助核算9': '',
                            '分录自定义项1': '',
                            '分录自定义项2': '',
                            '分录自定义项3': '',
                            '分录自定义项4': '',
                            '分录自定义项5': '',
                            '分录自定义项6': '',
                            '分录自定义项7': '',
                            '分录自定义项8': '',
                            '分录自定义项9': '',
                            '分录自定义项10': '',
                            '分录自定义项11': '',
                            '分录自定义项12': '',
                            '分录自定义项13': '',
                            '分录自定义项14': '',
                            '分录自定义项15': '',
                            '分录自定义项16': '',
                            '分录自定义项17': '',
                            '分录自定义项18': '',
                            '分录自定义项19': '',
                            '分录自定义项20': '',
                            '分录自定义项21': '',
                            '分录自定义项22': '',
                            '分录自定义项23': '',
                            '分录自定义项24': '',
                            '分录自定义项25': '',
                            '分录自定义项26': '',
                            '分录自定义项27': '',
                            '分录自定义项28': '',
                            '分录自定义项29': '',
                            '分录自定义项30': '',
                            '现金流量编码': code,
                            '现金流量名称': name,
                        })
    return rows
