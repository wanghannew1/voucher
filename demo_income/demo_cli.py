"""
进账明细生成器 - 命令行演示版
无需GUI，直接展示完整处理流程
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers import parse_bank_statement, parse_invoices
from data_loaders import DataStore
from matcher import match_transactions
from voucher_generator import generate_all_vouchers, export_vouchers_to_list
import pandas as pd


def demo():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 70)
    print("           进账明细生成器 Demo - 命令行演示")
    print("=" * 70)

    # 1. 加载数据
    print("\n【步骤1】加载银行对账单和发票数据...")
    ds = DataStore()

    ref_dir = os.path.join(base_dir, "代码资料")
    bank_files = [
        os.path.join(ref_dir, "银行流水/彩虹吉林银行4月对账单.xlsx"),
        os.path.join(ref_dir, "银行流水/彩虹工行4月对账单.xls"),
        os.path.join(ref_dir, "银行流水/彩虹建行4月对账单.xls"),
    ]
    invoice_file = os.path.join(ref_dir, "4月901张发票.xlsx")
    customers_file = os.path.join(ref_dir, "化简代码表/客户基本信息列表 (476)-化简版.xlsx")
    subjects_file = os.path.join(ref_dir, "化简代码表/现金流量表表项.txt")

    all_transactions = []
    for bf in bank_files:
        if os.path.exists(bf):
            txs = parse_bank_statement(bf)
            all_transactions.extend(txs)
            income = [t for t in txs if t.is_income]
            print(f"  ✓ {os.path.basename(bf)}: 总{len(txs)}笔, 进账{len(income)}笔")
        else:
            print(f"  ✗ 未找到: {os.path.basename(bf)}")

    ds.bank_transactions = all_transactions
    ds.invoices = parse_invoices(invoice_file)
    ds.load_reference_data(customers_file, subjects_file)

    total_income = len([t for t in all_transactions if t.is_income])
    print(f"\n  汇总: 共 {len(all_transactions)} 笔银行流水，其中进账 {total_income} 笔")
    print(f"       发票 {len(ds.invoices)} 张（正数{sum(1 for i in ds.invoices if i.is_positive)}张）")
    print(f"       客户档案 {len(ds.customers)} 条")

    # 2. 匹配
    print("\n【步骤2】进账与发票自动匹配...")
    results = match_transactions(ds)
    matched = [r for r in results if r.matched_invoice]
    unmatched = [r for r in results if not r.matched_invoice]
    print(f"  ✓ 匹配完成: 已匹配 {len(matched)} 笔，未匹配 {len(unmatched)} 笔")
    print(f"    匹配率: {len(matched)/len(results)*100:.1f}%")

    # 3. 展示几个匹配示例
    print("\n【步骤3】匹配示例展示（前3笔）:")
    for i, r in enumerate(matched[:3], 1):
        tx = r.transaction
        inv = r.matched_invoice
        print(f"\n  示例{i}:")
        print(f"    银行流水: {tx.date} {tx.bank_name} {tx.counterparty_name}")
        print(f"              收入: {tx.credit:,.2f}")
        print(f"    匹配发票: {inv.buyer_name}")
        print(f"              价税合计: {inv.total_amount:,.2f}")
        print(f"    解析明细:")
        print(f"      - 扣除额（工资）: {inv.deduction:,.2f}  → 贷: 224101 其他应付款")
        print(f"      - 管理费（收入）: {inv.management_fee:,.2f}")
        print(f"      - 税额:           {inv.tax_amount:,.2f}  → 贷: 222121 应交税费")
        print(f"      - 收入净额:      {inv.management_fee - inv.tax_amount:,.2f}  → 贷: 600101 派遣收入")

    # 4. 生成凭证
    print("\n【步骤4】生成凭证分录...")
    vouchers = generate_all_vouchers(results)
    print(f"  ✓ 生成凭证: {len(vouchers)} 张")
    total_entries = sum(len(v) for v in vouchers)
    print(f"    总分录数: {total_entries} 条")

    # 展示第一张完整凭证
    print("\n【步骤5】凭证分录示例（第一张匹配到发票的凭证）:")
    for entries in vouchers:
        if len(entries) > 2:
            print(f"\n  凭证号: {entries[0].voucher_no}")
            print(f"  日期: {entries[0].prepare_date}")
            print(f"  摘要: {entries[0].summary}")
            print(f"  {'科目编码':<10} {'科目名称':<16} {'借方金额':>14} {'贷方金额':>14}   辅助核算")
            print(f"  {'-'*70}")
            total_debit = 0
            total_credit = 0
            for e in entries:
                debit = e.debit_foreign if e.debit_foreign > 0 else 0
                credit = -e.debit_foreign if e.debit_foreign < 0 else 0
                total_debit += debit
                total_credit += credit
                d_str = f"{debit:>14,.2f}" if debit else f"{'':>14}"
                c_str = f"{credit:>14,.2f}" if credit else f"{'':>14}"
                aux = f"{e.aux1} {e.aux2}".strip()
                print(f"  {e.subject_code:<10} {e.subject_name:<16} {d_str} {c_str}   {aux}")
            print(f"  {'-'*70}")
            print(f"  {'合计':<10} {'':<16} {total_debit:>14,.2f} {total_credit:>14,.2f}")
            if abs(total_debit - total_credit) < 0.01:
                print(f"  ✓ 借贷平衡")
            break

    # 5. 导出
    print("\n【步骤6】导出到Excel...")
    rows = export_vouchers_to_list(vouchers)
    df = pd.DataFrame(rows)
    output_path = os.path.join(base_dir, "进账凭证明细.xlsx")
    df.to_excel(output_path, index=False, engine='openpyxl')
    print(f"  ✓ 已导出: {output_path}")
    print(f"    共 {len(rows)} 行")

    print("\n" + "=" * 70)
    print("                    Demo 演示完成!")
    print("=" * 70)
    print("\n提示: 运行 python demo_income/main.py 可启动图形界面版本")


if __name__ == "__main__":
    demo()
