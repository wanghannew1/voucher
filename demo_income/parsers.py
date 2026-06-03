"""
数据解析模块：银行流水和发票解析
"""
import pandas as pd
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime


@dataclass
class BankTransaction:
    """银行流水记录"""
    date: str                      # 交易日期 YYYY-MM-DD
    time: str                      # 交易时间
    counterparty_name: str         # 对方户名
    counterparty_account: str      # 对方账号
    summary: str                   # 摘要/用途
    debit: float                   # 借方发生额（支出）
    credit: float                  # 贷方发生额（收入）
    balance: float                 # 余额
    bank_code: str                 # 银行代码
    bank_name: str                 # 银行名称
    raw_data: Dict = field(default_factory=dict)

    @property
    def is_income(self) -> bool:
        """是否为进账（收入）"""
        return self.credit > 0

    @property
    def amount(self) -> float:
        """交易金额（收入为正，支出为负）"""
        return self.credit if self.credit > 0 else -self.debit


@dataclass
class Invoice:
    """发票记录"""
    invoice_no: str                # 发票号码
    buyer_name: str                # 购买方名称
    seller_name: str               # 销方名称
    issue_date: str                # 开票日期 YYYY-MM-DD
    service_name: str              # 货物/劳务名称
    amount: float                  # 金额（不含税）
    tax_rate: str                  # 税率
    tax_amount: float              # 税额
    total_amount: float            # 价税合计
    is_positive: bool              # 是否正数发票
    remark: str                    # 备注（包含扣除额和管理费）
    deduction: float = 0.0         # 扣除额（工资部分，不计税）
    management_fee: float = 0.0    # 管理费（收入部分，计税）
    raw_data: Dict = field(default_factory=dict)


def parse_amount(val):
    """解析金额，处理逗号分隔符"""
    if pd.isna(val):
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(',', '').replace('，', '').strip()
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_jilin_bank(file_path: str) -> List[BankTransaction]:
    """解析吉林银行对账单"""
    df = pd.read_excel(file_path, sheet_name=0, header=8)
    transactions = []
    for _, row in df.iterrows():
        try:
            date_str = str(row.get('交易时间', '')).strip()
            if not date_str or date_str in ['交易时间', 'nan', 'None']:
                continue
            # 日期格式: 2026-04-01 09:57:28
            date_part = date_str.split(' ')[0] if ' ' in date_str else date_str
            direction = str(row.get('借贷标志', '')).strip()
            amount = parse_amount(row.get('交易金额', 0))
            debit = amount if direction == '借' else 0.0
            credit = amount if direction == '贷' else 0.0
            tx = BankTransaction(
                date=date_part,
                time=date_str.split(' ')[1] if ' ' in date_str else '',
                counterparty_name=str(row.get('交易对手户名', '')).strip(),
                counterparty_account=str(row.get('交易对手账号', '')).strip(),
                summary=str(row.get('用途', '')).strip(),
                debit=debit,
                credit=credit,
                balance=parse_amount(row.get('交易后余额', 0)),
                bank_code='2801',
                bank_name='吉林银行',
                raw_data=row.to_dict()
            )
            transactions.append(tx)
        except Exception:
            continue
    return transactions


def parse_icbc(file_path: str) -> List[BankTransaction]:
    """解析工商银行对账单"""
    df = pd.read_excel(file_path, sheet_name=0, header=4)
    transactions = []
    for _, row in df.iterrows():
        try:
            date_val = row.get('日期', '')
            if pd.isna(date_val):
                continue
            # 处理日期格式
            if isinstance(date_val, datetime):
                date_str = date_val.strftime('%Y-%m-%d')
            else:
                date_str = str(date_val).strip()
                # 尝试转换 20260401 -> 2026-04-01
                if len(date_str) == 8 and date_str.isdigit():
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            debit = parse_amount(row.get('借方发生额', 0))
            credit = parse_amount(row.get('贷方发生额', 0))
            tx = BankTransaction(
                date=date_str,
                time='',
                counterparty_name=str(row.get('对方户名', '')).strip(),
                counterparty_account=str(row.get('对方账号', '')).strip(),
                summary=str(row.get('摘要', '')).strip(),
                debit=debit,
                credit=credit,
                balance=parse_amount(row.get('余额', 0)),
                bank_code='0107',
                bank_name='工商银行',
                raw_data=row.to_dict()
            )
            transactions.append(tx)
        except Exception:
            continue
    return transactions


def parse_ccb(file_path: str) -> List[BankTransaction]:
    """解析建设银行对账单"""
    df = pd.read_excel(file_path, sheet_name=0, header=0)
    transactions = []
    for _, row in df.iterrows():
        try:
            date_val = row.get('交易时间', '')
            if pd.isna(date_val):
                continue
            # 处理日期格式 20260401 08:51:34
            date_str = str(date_val).strip()
            if len(date_str) >= 8 and date_str[:8].isdigit():
                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
            else:
                date_str = ''
            debit = parse_amount(row.get('借方发生额（支取）', 0))
            credit = parse_amount(row.get('贷方发生额（收入）', 0))
            # 备注中包含更多信息
            remark = str(row.get('备注', '')).strip()
            summary = str(row.get('摘要', '')).strip()
            full_summary = f"{summary} {remark}".strip()
            tx = BankTransaction(
                date=date_str,
                time=str(date_val).split(' ')[1] if ' ' in str(date_val) else '',
                counterparty_name=str(row.get('对方户名', '')).strip(),
                counterparty_account=str(row.get('对方账号', '')).strip(),
                summary=full_summary,
                debit=debit,
                credit=credit,
                balance=parse_amount(row.get('余额', 0)),
                bank_code='0402',
                bank_name='建设银行',
                raw_data=row.to_dict()
            )
            transactions.append(tx)
        except Exception:
            continue
    return transactions


def parse_bank_statement(file_path: str) -> List[BankTransaction]:
    """自动识别银行类型并解析"""
    fname = file_path.lower()
    if '吉林银行' in fname or 'jilin' in fname:
        return parse_jilin_bank(file_path)
    elif '工行' in fname or 'icbc' in fname:
        return parse_icbc(file_path)
    elif '建行' in fname or 'ccb' in fname:
        return parse_ccb(file_path)
    else:
        # 尝试根据文件内容自动识别
        try:
            df = pd.read_excel(file_path, sheet_name=0, nrows=10)
            cols = [str(c).lower() for c in df.columns]
            if any('交易对手' in c for c in cols):
                return parse_jilin_bank(file_path)
            elif any('对方户名' in c and '借方发生额' in c for c in cols):
                return parse_icbc(file_path)
            elif any('借方发生额（支取）' in c for c in cols):
                return parse_ccb(file_path)
        except Exception:
            pass
        raise ValueError(f"无法识别银行对账单格式: {file_path}")


def parse_invoice_deduction(remark: str) -> tuple:
    """从发票备注中解析扣除额和管理费
    格式示例: "扣除额:112567.63 管理费：1520"
    """
    deduction = 0.0
    management_fee = 0.0
    if not remark or pd.isna(remark):
        return deduction, management_fee
    # 匹配扣除额
    m = re.search(r'扣除额[:：]\s*([0-9,\.]+)', str(remark))
    if m:
        deduction = parse_amount(m.group(1))
    # 匹配管理费
    m = re.search(r'管理费[:：]\s*([0-9,\.]+)', str(remark))
    if m:
        management_fee = parse_amount(m.group(1))
    return deduction, management_fee


def parse_invoices(file_path: str) -> List[Invoice]:
    """解析发票Excel文件"""
    df = pd.read_excel(file_path, sheet_name=0, header=0)
    invoices = []
    for _, row in df.iterrows():
        try:
            remark = str(row.get('备注', '')).strip()
            if not remark or remark in ['nan', 'None', '备注']:
                continue
            # 跳过没有有效购买方名称的行
            buyer = str(row.get('购买方名称', '')).strip()
            if not buyer or buyer in ['nan', 'None']:
                continue
            # 解析日期
            date_val = row.get('开票日期', '')
            if isinstance(date_val, datetime):
                date_str = date_val.strftime('%Y-%m-%d')
            else:
                date_str = str(date_val).split(' ')[0] if ' ' in str(date_val) else str(date_val)
            is_positive = str(row.get('是否正数发票', '')).strip() == '是'
            deduction, management_fee = parse_invoice_deduction(remark)
            inv = Invoice(
                invoice_no=str(row.get('数电发票号码', '')).strip(),
                buyer_name=buyer,
                seller_name=str(row.get('销方名称', '')).strip(),
                issue_date=date_str,
                service_name=str(row.get('货物或应税劳务名称', '')).strip(),
                amount=parse_amount(row.get('金额', 0)),
                tax_rate=str(row.get('税率', '')).strip(),
                tax_amount=parse_amount(row.get('税额', 0)),
                total_amount=parse_amount(row.get('价税合计', 0)),
                is_positive=is_positive,
                remark=remark,
                deduction=deduction,
                management_fee=management_fee,
                raw_data=row.to_dict()
            )
            invoices.append(inv)
        except Exception:
            continue
    return invoices
