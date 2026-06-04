"""
匹配模块：银行进账与发票匹配
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, timedelta
from itertools import combinations


@dataclass
class MatchResult:
    """匹配结果"""
    transaction: object           # BankTransaction
    matched_invoices: List[object] = field(default_factory=list)  # 支持多张发票
    matched_invoice: Optional[object] = None   # 兼容旧接口，取第一张
    match_type: str = ''          # 'exact', 'multi', 'unmatched'
    confidence: float = 0.0
    customer_code: str = ''
    customer_name: str = ''
    notes: str = ''
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


def match_multi_invoices(tx, candidates, strict_amount=False, amount_tolerance=0.01) -> tuple:
    """尝试匹配多张发票（同一天，金额合计=进账金额）
    candidates: 已按名称过滤的 (inv, cust) 列表
    返回: (是否匹配, 发票列表, 客户信息, 置信度)
    """
    if len(candidates) < 2:
        return False, [], None, 0.0

    tx_amount = tx.credit

    # 按金额降序排序
    candidates.sort(key=lambda x: x[0].total_amount, reverse=True)

    # 剪枝：如果最小的2张都超过目标，或最大的1张就超过，跳过
    if candidates[-1][0].total_amount * 2 > tx_amount + amount_tolerance * 10:
        return False, [], None, 0.0

    # 尝试 2~4 张组合（限制最多4张）
    max_size = min(len(candidates), 4)
    for size in range(2, max_size + 1):
        for combo in combinations(candidates, size):
            combo_invs = [c[0] for c in combo]
            total = sum(inv.total_amount for inv in combo_invs)
            if abs(total - tx_amount) < amount_tolerance:
                cust = combo[0][1]
                return True, combo_invs, cust, 0.95
            if strict_amount:
                continue
            if abs(total - tx_amount) < 1.0:
                cust = combo[0][1]
                return True, combo_invs, cust, 0.9

    return False, [], None, 0.0


def match_transactions(data_store, days_range: int = 30,
                       require_name: bool = True, require_amount: bool = True,
                       require_date: bool = False,
                       strict_name: bool = False, strict_amount: bool = False,
                       amount_tolerance: float = 0.01,
                       min_score: float = 0.4,
                       enable_multi: bool = True,
                       multi_exclude: List[str] = None,
                       progress_callback=None) -> List[MatchResult]:
    """将银行进账与发票进行匹配（两轮：先单票严格匹配，再多票组合匹配）"""
    if multi_exclude is None:
        multi_exclude = []

    income_txs = data_store.get_income_transactions()
    invoices = data_store.invoices
    results = {}
    used_invoices = set()
    total = len(income_txs)

    # 预过滤正数发票
    positive_invoices = [inv for inv in invoices if inv.is_positive]

    # ========== 第一轮：单票严格匹配 ==========
    for idx, tx in enumerate(income_txs):
        if progress_callback:
            progress_callback(idx + 1, total, f"[单票] {tx.counterparty_name}")

        # 检查是否有映射表覆盖
        mapped_cust = None
        if data_store.bank_customer_map:
            for bank_name, cust_code in data_store.bank_customer_map.items():
                if bank_name in tx.counterparty_name or tx.counterparty_name in bank_name:
                    if cust_code in data_store.customers:
                        mapped_cust = data_store.customers[cust_code]
                        break

        same_name_invs = []
        if mapped_cust:
            # 有映射：优先用映射，精确匹配发票购买方
            for inv in positive_invoices:
                if id(inv) in used_invoices:
                    continue
                # 精确匹配：发票购买方 = 银行户名
                if inv.buyer_name == tx.counterparty_name:
                    same_name_invs.append((inv, mapped_cust))
        else:
            # 无映射：按名称匹配
            for inv in positive_invoices:
                if id(inv) in used_invoices:
                    continue
                name_match, _, cust = match_by_name(tx, inv, data_store, strict_name)
                if name_match:
                    same_name_invs.append((inv, cust))

        if not same_name_invs:
            continue

        # 单张匹配
        best_match = None
        best_score = 0.0
        best_inv = None
        tx_date = normalize_date(tx.date)

        for inv, cust in same_name_invs:
            amount_match, amount_conf = match_by_amount(tx, inv, strict_amount, amount_tolerance)
            inv_date = normalize_date(inv.issue_date)
            date_match = dates_within_range(tx_date, inv_date, days_range)

            if require_amount and not amount_match:
                continue
            if require_date and not date_match:
                continue

            score = 0.0
            match_type = 'unmatched'
            if amount_match and date_match:
                score = 1.0
                match_type = 'exact'
            elif amount_match:
                score = 0.9
                match_type = 'name_amount'
            elif date_match:
                score = 0.7
                match_type = 'name_date'
            else:
                score = 0.5
                match_type = 'name_only'

            if score > best_score:
                best_score = score
                best_match = cust
                best_inv = inv
                best_type = match_type

        if best_inv and best_score >= min_score:
            used_invoices.add(id(best_inv))
            results[id(tx)] = MatchResult(
                transaction=tx, matched_invoice=best_inv, matched_invoices=[best_inv],
                match_type=best_type, confidence=best_score,
                customer_code=best_match['code'] if best_match else '',
                customer_name=best_match['name'] if best_match else tx.counterparty_name,
                notes=f"匹配方式: {best_type}"
            )

    # ========== 第二轮：多票组合匹配（仅未匹配的、未排除的）==========
    if enable_multi:
        for idx, tx in enumerate(income_txs):
            if id(tx) in results:
                continue

            # 检查是否在排除名单中
            if any(ex in tx.counterparty_name for ex in multi_exclude):
                if progress_callback:
                    progress_callback(idx + 1, total, f"[跳过] {tx.counterparty_name}")
                continue

            if progress_callback:
                progress_callback(idx + 1, total, f"[多票] {tx.counterparty_name}")

            # 检查映射表
            mapped_cust = None
            if data_store.bank_customer_map:
                for bank_name, cust_code in data_store.bank_customer_map.items():
                    if bank_name in tx.counterparty_name or tx.counterparty_name in bank_name:
                        if cust_code in data_store.customers:
                            mapped_cust = data_store.customers[cust_code]
                            break

            # 预过滤同名、同天发票
            tx_date = normalize_date(tx.date)
            candidates = []
            for inv in positive_invoices:
                if id(inv) in used_invoices:
                    continue
                if mapped_cust:
                    # 有映射：精确匹配购买方
                    if inv.buyer_name == tx.counterparty_name:
                        candidates.append((inv, mapped_cust))
                else:
                    # 无映射：按名称匹配
                    name_match, _, cust = match_by_name(tx, inv, data_store, strict_name)
                    if not name_match:
                        continue
                    inv_date = normalize_date(inv.issue_date)
                    if not dates_within_range(tx_date, inv_date, 1):
                        continue
                    candidates.append((inv, cust))

            multi_ok, multi_invs, cust, conf = match_multi_invoices(
                tx, candidates, strict_amount, amount_tolerance
            )
            if multi_ok and conf >= min_score:
                for inv in multi_invs:
                    used_invoices.add(id(inv))
                inv_notes = ", ".join(f"{inv.total_amount:,.2f}" for inv in multi_invs)
                results[id(tx)] = MatchResult(
                    transaction=tx, matched_invoice=multi_invs[0], matched_invoices=multi_invs,
                    match_type='multi', confidence=conf,
                    customer_code=cust['code'] if cust else '',
                    customer_name=cust['name'] if cust else tx.counterparty_name,
                    notes=f"多票组合匹配({len(multi_invs)}张): {inv_notes}"
                )

    # ========== 第三轮：未匹配的 ==========
    for tx in income_txs:
        if id(tx) not in results:
            cust = data_store.find_customer_by_name(tx.counterparty_name)
            results[id(tx)] = MatchResult(
                transaction=tx, matched_invoice=None, matched_invoices=[],
                match_type='unmatched', confidence=0.0,
                customer_code=cust['code'] if cust else '',
                customer_name=cust['name'] if cust else tx.counterparty_name,
                notes='未匹配到对应发票'
            )

    return [results[id(tx)] for tx in income_txs]
