"""
匹配模块：银行进账与发票匹配
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta


@dataclass
class MatchResult:
    """匹配结果"""
    transaction: object           # BankTransaction
    matched_invoice: Optional[object] = None   # Invoice
    match_type: str = ''          # 'exact', 'fuzzy', 'manual', 'unmatched'
    confidence: float = 0.0         # 匹配置信度 0-1
    customer_code: str = ''       # 匹配到的客户编码
    customer_name: str = ''       # 匹配到的客户名称
    notes: str = ''               # 备注说明
    voucher_entries: List[dict] = field(default_factory=list)


def normalize_date(date_str: str) -> str:
    """标准化日期字符串"""
    if not date_str:
        return ''
    date_str = date_str.strip()
    # 处理 2026/4/9 -> 2026-04-09
    if '/' in date_str:
        parts = date_str.split('/')
        if len(parts) == 3:
            y, m, d = parts[0], parts[1].zfill(2), parts[2].zfill(2)
            return f"{y}-{m}-{d}"
    return date_str


def dates_within_range(date1: str, date2: str, days: int = 30) -> bool:
    """判断两个日期是否在指定天数范围内"""
    try:
        d1 = datetime.strptime(date1, '%Y-%m-%d')
        d2 = datetime.strptime(date2, '%Y-%m-%d')
        return abs((d1 - d2).days) <= days
    except Exception:
        return False


def match_by_name(tx, invoice, data_store, strict_name: bool = False) -> tuple:
    """按客户名称匹配
    返回: (是否匹配, 置信度, 客户信息)
    """
    tx_name = tx.counterparty_name.strip()
    inv_name = invoice.buyer_name.strip()
    if not tx_name or not inv_name:
        return False, 0.0, None
    # 精确匹配
    if tx_name == inv_name:
        cust = data_store.find_customer_by_name(tx_name)
        return True, 1.0, cust
    if strict_name:
        return False, 0.0, None
    # 子串匹配
    if tx_name in inv_name or inv_name in tx_name:
        cust = data_store.find_customer_by_name(tx_name) or data_store.find_customer_by_name(inv_name)
        return True, 0.8, cust
    # 去后缀匹配
    tx_simp = tx_name.replace('有限公司', '').replace('有限责任公司', '').strip()
    inv_simp = inv_name.replace('有限公司', '').replace('有限责任公司', '').strip()
    if tx_simp == inv_simp:
        cust = data_store.find_customer_by_name(tx_name) or data_store.find_customer_by_name(inv_name)
        return True, 0.7, cust
    return False, 0.0, None


def match_by_amount(tx, invoice, strict_amount: bool = False, amount_tolerance: float = 0.01) -> tuple:
    """按金额匹配
    返回: (是否匹配, 置信度)
    """
    tx_amount = tx.credit  # 进账金额
    inv_amount = invoice.total_amount  # 价税合计
    if tx_amount <= 0 or inv_amount <= 0:
        return False, 0.0
    # 精确匹配
    if abs(tx_amount - inv_amount) < amount_tolerance:
        return True, 1.0
    if strict_amount:
        return False, 0.0
    # 允许小误差（四舍五入等）
    if abs(tx_amount - inv_amount) < 1.0:
        return True, 0.95
    return False, 0.0


def match_transactions(data_store, days_range: int = 30,
                       require_name: bool = True, require_amount: bool = True,
                       require_date: bool = False,
                       strict_name: bool = False, strict_amount: bool = False,
                       amount_tolerance: float = 0.01,
                       min_score: float = 0.4) -> List[MatchResult]:
    """将银行进账与发票进行匹配

    可配置参数:
      require_name   - 必须名称匹配
      require_amount - 必须金额匹配
      require_date   - 必须日期匹配
      strict_name    - 名称必须精确匹配（不允许子串/去后缀）
      strict_amount  - 金额必须精确匹配（不允许误差）
      amount_tolerance - 金额误差阈值
      min_score      - 最低匹配分数
    """
    income_txs = data_store.get_income_transactions()
    invoices = data_store.invoices
    results = []
    used_invoices = set()

    for tx in income_txs:
        best_match = None
        best_score = 0.0
        best_inv = None

        for inv in invoices:
            if id(inv) in used_invoices:
                continue
            if not inv.is_positive:
                continue  # 跳过红字发票

            # 名称匹配
            name_match, name_conf, cust = match_by_name(tx, inv, data_store, strict_name)
            # 金额匹配
            amount_match, amount_conf = match_by_amount(tx, inv, strict_amount, amount_tolerance)
            # 日期匹配
            tx_date = normalize_date(tx.date)
            inv_date = normalize_date(inv.issue_date)
            date_match = dates_within_range(tx_date, inv_date, days_range)

            # 按要求过滤
            if require_name and not name_match:
                continue
            if require_amount and not amount_match:
                continue
            if require_date and not date_match:
                continue

            # 计算综合得分
            score = 0.0
            match_type = 'unmatched'

            if name_match and amount_match and date_match:
                score = 1.0
                match_type = 'exact'
            elif name_match and amount_match:
                score = 0.9
                match_type = 'name_amount'
            elif name_match and date_match:
                score = 0.7
                match_type = 'name_date'
            elif amount_match and date_match:
                score = 0.6
                match_type = 'amount_date'
            elif name_match:
                score = 0.5
                match_type = 'name_only'
            elif amount_match:
                score = 0.4
                match_type = 'amount_only'

            if score > best_score:
                best_score = score
                best_match = cust
                best_inv = inv
                best_type = match_type

        if best_inv and best_score >= min_score:
            used_invoices.add(id(best_inv))
            result = MatchResult(
                transaction=tx,
                matched_invoice=best_inv,
                match_type=best_type,
                confidence=best_score,
                customer_code=best_match['code'] if best_match else '',
                customer_name=best_match['name'] if best_match else tx.counterparty_name,
                notes=f"匹配方式: {best_type}, 发票备注: {best_inv.remark[:50]}..." if len(best_inv.remark) > 50 else f"匹配方式: {best_type}, 发票备注: {best_inv.remark}"
            )
        else:
            # 未匹配 - 尝试只按名称找客户
            cust = data_store.find_customer_by_name(tx.counterparty_name)
            result = MatchResult(
                transaction=tx,
                matched_invoice=None,
                match_type='unmatched',
                confidence=0.0,
                customer_code=cust['code'] if cust else '',
                customer_name=cust['name'] if cust else tx.counterparty_name,
                notes='未匹配到对应发票'
            )
        results.append(result)

    return results
