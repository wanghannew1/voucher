"""
进账明细生成器 - 主程序（Streamlit UI）
启动: streamlit run main.py
"""
import streamlit as st
import pandas as pd
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers import parse_bank_statement, parse_invoices, parse_jilin_bank, parse_icbc, parse_ccb
from data_loaders import DataStore
from matcher import match_transactions
from voucher_generator import generate_all_vouchers, export_vouchers_to_list

st.set_page_config(page_title="进账明细生成器", page_icon="📊", layout="wide")
st.title("📊 进账明细生成器 Demo")

# 初始化 session_state
if "data_store" not in st.session_state:
    st.session_state.data_store = DataStore()
if "match_results" not in st.session_state:
    st.session_state.match_results = []
if "vouchers" not in st.session_state:
    st.session_state.vouchers = []

# ==== 侧边栏：文件上传与操作 ====
with st.sidebar:
    st.header("📁 文件上传")

    # 银行对账单：支持多文件
    if "bank_files" not in st.session_state:
        st.session_state.bank_files = [{"file": None, "type": "自动识别"}]

    st.subheader("银行对账单（可多个）")
    for i, bf in enumerate(st.session_state.bank_files):
        cols = st.columns([3, 2, 1])
        with cols[0]:
            f = st.file_uploader(f"文件 {i+1}", type=["xlsx", "xls"], key=f"bank_{i}")
            st.session_state.bank_files[i]["file"] = f
        with cols[1]:
            t = st.selectbox("银行", ["自动识别", "吉林银行", "工商银行", "建设银行"],
                             index=["自动识别", "吉林银行", "工商银行", "建设银行"].index(bf["type"]),
                             key=f"btype_{i}")
            st.session_state.bank_files[i]["type"] = t
        with cols[2]:
            if i > 0:
                if st.button("✕", key=f"del_bank_{i}"):
                    st.session_state.bank_files.pop(i)
                    st.rerun()

    if st.button("+ 添加银行对账单"):
        st.session_state.bank_files.append({"file": None, "type": "自动识别"})
        st.rerun()

    invoice_file = st.file_uploader("发票信息", type=["xlsx", "xls"], key="invoice")

    st.divider()
    st.header("⚙️ 匹配规则")
    strict_name = st.checkbox("名称精确匹配", value=True, key="strict_name",
                              help="勾选：银行户名必须与发票购买方完全一致；取消：允许子串/去后缀匹配")
    strict_amount = st.checkbox("金额精确匹配", value=True, key="strict_amount",
                                help="勾选：进账金额必须与发票价税合计完全一致；取消：允许1元内误差")
    require_date = st.checkbox("要求日期匹配", value=False, key="require_date",
                               help="勾选：开票日期必须在进账日期±N天内")
    days_range = st.slider("日期范围（天）", 7, 90, 30, key="days_range",
                           help="开票日期与进账日期允许的最大天数差")
    min_score = st.slider("最低匹配分数", 0.4, 1.0, 0.9, 0.1, key="min_score",
                          help="低于此分数视为未匹配")
    enable_multi = st.checkbox("多票组合匹配", value=True, key="enable_multi",
                               help="一笔进账对应多张发票时自动组合匹配（较慢）")
    multi_exclude = st.text_area(
        "排除多票匹配的单位（每行一个）",
        value="吉林大学\n吉林大学第一医院\n吉林大学第二医院\n吉林大学中日联谊医院",
        key="multi_exclude",
        help="这些单位不参与多票组合匹配，只做单票严格匹配"
    )

    st.subheader("银行→客户映射（外包业务用）")
    bank_cust_map = st.text_area(
        "银行名称=客户编码（每行一个）",
        value="吉林银行股份有限公司=GY040",
        key="bank_cust_map",
        help="格式: 银行流水中的名称=客户编码，如: 吉林银行股份有限公司=GY040"
    )
    col1, col2 = st.columns(2)
    load_btn = col1.button("加载数据", type="primary", use_container_width=True)
    match_btn = col2.button("自动匹配", type="primary", use_container_width=True)
    gen_btn = col1.button("生成凭证", type="primary", use_container_width=True)
    export_btn = col2.button("导出 Excel", type="primary", use_container_width=True)

    st.divider()
    st.header("📋 日志")
    log_area = st.empty()

def log(msg):
    with log_area.container():
        st.text(msg)

# ==== 加载数据 ====
if load_btn:
    bank_files_data = [bf for bf in st.session_state.bank_files if bf["file"]]
    if not bank_files_data or not invoice_file:
        st.warning("请先上传银行对账单和发票信息文件！")
    else:
        try:
            ds = st.session_state.data_store
            ds.bank_transactions = []

            for bf in bank_files_data:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                    tmp.write(bf["file"].read())
                    bank_path = tmp.name
                bank_type = bf["type"]
                if bank_type == "吉林银行":
                    txs = parse_jilin_bank(bank_path)
                elif bank_type == "工商银行":
                    txs = parse_icbc(bank_path)
                elif bank_type == "建设银行":
                    txs = parse_ccb(bank_path)
                else:
                    txs = parse_bank_statement(bank_path)
                os.unlink(bank_path)
                ds.bank_transactions.extend(txs)
                income = sum(1 for t in txs if t.is_income)
                log(f"{bf['file'].name}: {len(txs)} 笔，进账 {income} 笔")

            income_count = len(ds.get_income_transactions())
            log(f"银行流水汇总: 共 {len(ds.bank_transactions)} 笔，进账 {income_count} 笔")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as tmp:
                tmp.write(invoice_file.read())
                invoice_path = tmp.name
            ds.invoices = parse_invoices(invoice_path)
            os.unlink(invoice_path)
            positive_count = sum(1 for inv in ds.invoices if inv.is_positive)
            log(f"发票: 共 {len(ds.invoices)} 张，正数 {positive_count} 张")

            # 加载参考数据
            ref_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "代码资料")
            customers_path = os.path.join(ref_dir, "化简代码表/客户基本信息列表 (476)-化简版.xlsx")
            subjects_path = os.path.join(ref_dir, "化简代码表/现金流量表表项.txt")
            if os.path.exists(customers_path) and os.path.exists(subjects_path):
                ds.load_reference_data(customers_path, subjects_path)
                log(f"客户档案: {len(ds.customers)} 条")

            # 解析银行→客户映射
            for line in bank_cust_map.split('\n'):
                line = line.strip()
                if '=' in line:
                    parts = line.split('=', 1)
                    ds.bank_customer_map[parts[0].strip()] = parts[1].strip()
            log(f"银行→客户映射: {len(ds.bank_customer_map)} 条")

            st.success(f"数据加载完成！进账 {income_count} 笔，正数发票 {positive_count} 张")
        except Exception as e:
            st.error(f"加载失败: {e}")

# ==== 匹配 ====
if match_btn:
    ds = st.session_state.data_store
    if not ds.bank_transactions or not ds.invoices:
        st.warning("请先加载数据！")
    else:
        with st.spinner("正在匹配银行进账与发票..."):
            progress_bar = st.progress(0, text="准备中...")
            status_text = st.empty()

            exclude_list = [x.strip() for x in multi_exclude.split('\n') if x.strip()]

            def update_progress(current, total, name):
                pct = current / total
                progress_bar.progress(pct, text=f"匹配中 ({current}/{total}) {name}")
                if current % 50 == 0 or current == total:
                    status_text.text(f"进度: {current}/{total} ({pct:.0%})")

            st.session_state.match_results = match_transactions(
                ds,
                require_name=True,
                require_amount=True,
                require_date=require_date,
                strict_name=strict_name,
                strict_amount=strict_amount,
                days_range=days_range,
                min_score=min_score,
                enable_multi=enable_multi,
                multi_exclude=exclude_list,
                progress_callback=update_progress,
            )
            progress_bar.progress(1.0, text="匹配完成!")
            status_text.empty()
        matched = sum(1 for r in st.session_state.match_results if r.matched_invoice)
        unmatched = len(st.session_state.match_results) - matched
        st.success(f"匹配完成！已匹配 {matched} 笔，未匹配 {unmatched} 笔")

# ==== 生成凭证 ====
if gen_btn:
    if not st.session_state.match_results:
        st.warning("请先执行匹配！")
    else:
        with st.spinner("正在生成凭证..."):
            st.session_state.vouchers = generate_all_vouchers(st.session_state.match_results)
        total_entries = sum(len(v) for v in st.session_state.vouchers)
        st.success(f"凭证生成完成！共 {len(st.session_state.vouchers)} 张，{total_entries} 条分录")

# ==== 导出 Excel ====
if export_btn:
    if not st.session_state.vouchers:
        st.warning("请先生成凭证！")
    else:
        rows = export_vouchers_to_list(st.session_state.vouchers)
        df = pd.DataFrame(rows)
        buf = pd.ExcelWriter(os.path.join(tempfile.gettempdir(), "export.xlsx"), engine="openpyxl")
        df.to_excel(buf, index=False)
        buf.close()
        with open(os.path.join(tempfile.gettempdir(), "export.xlsx"), "rb") as f:
            st.download_button(
                label="📥 下载凭证 Excel",
                data=f.read(),
                file_name="进账凭证明细.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        st.success(f"共 {len(rows)} 条分录，点击上方按钮下载")

# ==== 主体内容 ====
ds = st.session_state.data_store

# 银行进账流水
st.subheader("🏦 银行进账流水")
income_txs = ds.get_income_transactions() if ds.bank_transactions else []
if income_txs:
    total = sum(tx.credit for tx in income_txs)
    st.metric("进账笔数", len(income_txs), f"总金额: ¥{total:,.2f}")
    bank_df = pd.DataFrame([{
        "日期": tx.date,
        "银行": tx.bank_name,
        "对方户名": tx.counterparty_name,
        "收入金额": tx.credit,
        "摘要": tx.summary,
    } for tx in income_txs])
    st.dataframe(bank_df, use_container_width=True, height=400)
else:
    st.info("暂无数据，请上传文件并加载")

# 匹配结果
if st.session_state.match_results:
    st.subheader("🔗 匹配结果")
    match_data = []
    for r in st.session_state.match_results:
        tx = r.transaction
        invs = r.matched_invoices if r.matched_invoices else (
            [r.matched_invoice] if r.matched_invoice else []
        )
        if invs:
            for i, inv in enumerate(invs):
                match_data.append({
                    "状态": "✅ 已匹配" if i == 0 else "",
                    "进账日期": tx.date if i == 0 else "",
                    "银行": tx.bank_name if i == 0 else "",
                    "对方户名": tx.counterparty_name if i == 0 else "",
                    "进账金额": tx.credit if i == 0 else None,
                    "客户编码": r.customer_code if i == 0 else "",
                    "匹配方式": r.match_type if i == 0 else "",
                    "发票号": inv.invoice_no,
                    "价税合计": inv.total_amount,
                    "扣除额": inv.deduction,
                    "管理费": inv.management_fee,
                    "税额": inv.tax_amount,
                })
        else:
            match_data.append({
                "状态": "❌ 未匹配",
                "进账日期": tx.date,
                "银行": tx.bank_name,
                "对方户名": tx.counterparty_name,
                "进账金额": tx.credit,
                "客户编码": r.customer_code,
                "匹配方式": r.match_type,
                "发票号": "",
                "价税合计": None,
                "扣除额": None,
                "管理费": None,
                "税额": None,
            })
    match_df = pd.DataFrame(match_data)
    st.dataframe(match_df, use_container_width=True, height=400)

# 凭证分录
if st.session_state.vouchers:
    st.subheader("📝 凭证分录预览")
    voucher_data = []
    for entries in st.session_state.vouchers:
        for e in entries:
            debit = e.debit_foreign if e.debit_foreign > 0 else 0
            credit = -e.debit_foreign if e.debit_foreign < 0 else 0
            cf_text = " | ".join(f"{c} {n} {a:,.2f}" for c, n, a in e.cash_flows) if e.cash_flows else ""
            voucher_data.append({
                "凭证号": e.voucher_no,
                "摘要": e.summary,
                "科目编码": e.subject_code,
                "科目名称": e.subject_name,
                "借方": debit if debit else None,
                "贷方": credit if credit else None,
                "辅助核算1": e.aux1,
                "辅助核算2": e.aux2,
                "现金流量": cf_text,
                "制单人": e.preparer,
                "制单日期": e.prepare_date,
                "凭证类别": e.voucher_type,
                "财务核算账簿": e.accounting_book,
                "币种": e.currency,
                "业务单元": e.unit_name,
            })
    voucher_df = pd.DataFrame(voucher_data)
    st.dataframe(voucher_df, use_container_width=True, height=500)
