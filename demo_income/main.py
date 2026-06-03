"""
进账明细生成器 - 主程序（tkinter UI）
"""
try:
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox, scrolledtext
except ImportError:
    print("错误: 缺少 tkinter 模块，请安装：")
    print("  macOS:   brew install python-tk@$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)")
    print("  Ubuntu:  sudo apt-get install python3-tk")
    print("  Windows: 重新安装 Python 并勾选 tcl/tk 选项")
    print("\n或使用命令行版本: python demo_cli.py")
    sys.exit(1)
import pandas as pd
import os
import sys

# 将当前目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parsers import parse_bank_statement, parse_invoices
from data_loaders import DataStore
from matcher import match_transactions
from voucher_generator import generate_all_vouchers, export_vouchers_to_list


class IncomeVoucherApp:
    def __init__(self, root):
        self.root = root
        self.root.title("进账明细生成器 Demo")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 800)

        self.data_store = DataStore()
        self.bank_file = ""
        self.invoice_file = ""
        self.customers_file = ""
        self.subjects_file = ""
        self.match_results = []
        self.vouchers = []

        self._build_ui()

    def _build_ui(self):
        # ==== 顶部工具栏 ====
        toolbar = tk.Frame(self.root, padx=10, pady=10)
        toolbar.pack(fill=tk.X)

        tk.Label(toolbar, text="银行对账单:", font=("Microsoft YaHei", 10)).grid(row=0, column=0, sticky="w")
        self.bank_var = tk.StringVar(value="请选择银行对账单文件...")
        tk.Entry(toolbar, textvariable=self.bank_var, width=50, state="readonly").grid(row=0, column=1, padx=5)
        tk.Button(toolbar, text="浏览", command=self._select_bank).grid(row=0, column=2)

        tk.Label(toolbar, text="发票信息:", font=("Microsoft YaHei", 10)).grid(row=1, column=0, sticky="w", pady=5)
        self.invoice_var = tk.StringVar(value="请选择发票信息文件...")
        tk.Entry(toolbar, textvariable=self.invoice_var, width=50, state="readonly").grid(row=1, column=1, padx=5)
        tk.Button(toolbar, text="浏览", command=self._select_invoice).grid(row=1, column=2)

        # 操作按钮
        btn_frame = tk.Frame(toolbar)
        btn_frame.grid(row=0, column=3, rowspan=2, padx=20)
        tk.Button(btn_frame, text="加载数据", command=self._load_data, width=12, bg="#4CAF50", fg="white",
                  font=("Microsoft YaHei", 10, "bold")).pack(pady=2)
        tk.Button(btn_frame, text="自动匹配", command=self._match_data, width=12, bg="#2196F3", fg="white",
                  font=("Microsoft YaHei", 10, "bold")).pack(pady=2)
        tk.Button(btn_frame, text="生成凭证", command=self._generate_vouchers, width=12, bg="#FF9800", fg="white",
                  font=("Microsoft YaHei", 10, "bold")).pack(pady=2)
        tk.Button(btn_frame, text="导出Excel", command=self._export_excel, width=12, bg="#9C27B0", fg="white",
                  font=("Microsoft YaHei", 10, "bold")).pack(pady=2)

        # 状态标签
        self.status_var = tk.StringVar(value="就绪 - 请选择文件并加载数据")
        tk.Label(toolbar, textvariable=self.status_var, font=("Microsoft YaHei", 10), fg="blue").grid(row=2, column=0, columnspan=4, sticky="w", pady=5)

        # ==== 主体内容区（PanedWindow）====
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ---- 左侧：银行进账列表 ----
        left_frame = tk.LabelFrame(paned, text="银行进账流水", font=("Microsoft YaHei", 11, "bold"))
        paned.add(left_frame, minsize=400)

        # 统计信息
        self.stats_label = tk.Label(left_frame, text="进账笔数: 0 | 总金额: 0.00", font=("Microsoft YaHei", 9))
        self.stats_label.pack(anchor="w", padx=5, pady=2)

        # 表格
        cols = ("日期", "银行", "对方户名", "收入金额", "摘要")
        self.bank_tree = ttk.Treeview(left_frame, columns=cols, show="headings", height=20)
        for c in cols:
            self.bank_tree.heading(c, text=c)
        self.bank_tree.column("日期", width=90)
        self.bank_tree.column("银行", width=80)
        self.bank_tree.column("对方户名", width=150)
        self.bank_tree.column("收入金额", width=100)
        self.bank_tree.column("摘要", width=200)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.bank_tree.yview)
        self.bank_tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.bank_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.bank_tree.bind("<<TreeviewSelect>>", self._on_bank_select)

        # ---- 右侧：匹配结果与凭证预览 ----
        right_paned = tk.PanedWindow(paned, orient=tk.VERTICAL)
        paned.add(right_paned, minsize=600)

        # 匹配结果
        match_frame = tk.LabelFrame(right_paned, text="匹配结果", font=("Microsoft YaHei", 11, "bold"))
        right_paned.add(match_frame, minsize=200)

        match_cols = ("状态", "客户名称", "客户编码", "匹配方式", "价税合计", "扣除额", "管理费", "税额")
        self.match_tree = ttk.Treeview(match_frame, columns=match_cols, show="headings", height=8)
        for c in match_cols:
            self.match_tree.heading(c, text=c)
        self.match_tree.column("状态", width=60)
        self.match_tree.column("客户名称", width=150)
        self.match_tree.column("客户编码", width=80)
        self.match_tree.column("匹配方式", width=100)
        self.match_tree.column("价税合计", width=90)
        self.match_tree.column("扣除额", width=80)
        self.match_tree.column("管理费", width=80)
        self.match_tree.column("税额", width=80)
        m_scroll = ttk.Scrollbar(match_frame, orient="vertical", command=self.match_tree.yview)
        self.match_tree.configure(yscrollcommand=m_scroll.set)
        m_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.match_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 凭证分录预览
        voucher_frame = tk.LabelFrame(right_paned, text="凭证分录预览", font=("Microsoft YaHei", 11, "bold"))
        right_paned.add(voucher_frame, minsize=300)

        v_cols = ("凭证号", "科目编码", "科目名称", "借方", "贷方", "辅助核算1", "辅助核算2", "现金流量")
        self.voucher_tree = ttk.Treeview(voucher_frame, columns=v_cols, show="headings", height=12)
        for c in v_cols:
            self.voucher_tree.heading(c, text=c)
        self.voucher_tree.column("凭证号", width=60)
        self.voucher_tree.column("科目编码", width=80)
        self.voucher_tree.column("科目名称", width=130)
        self.voucher_tree.column("借方", width=90)
        self.voucher_tree.column("贷方", width=90)
        self.voucher_tree.column("辅助核算1", width=120)
        self.voucher_tree.column("辅助核算2", width=120)
        self.voucher_tree.column("现金流量", width=150)
        v_scroll = ttk.Scrollbar(voucher_frame, orient="vertical", command=self.voucher_tree.yview)
        self.voucher_tree.configure(yscrollcommand=v_scroll.set)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.voucher_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # ==== 底部：日志区 ====
        log_frame = tk.LabelFrame(self.root, text="处理日志", font=("Microsoft YaHei", 10))
        log_frame.pack(fill=tk.X, padx=10, pady=5)
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, wrap=tk.WORD, font=("Consolas", 9))
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def _log(self, msg):
        self.log_text.insert(tk.END, f"{msg}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _select_bank(self):
        path = filedialog.askopenfilename(
            title="选择银行对账单",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if path:
            self.bank_file = path
            self.bank_var.set(os.path.basename(path))
            self._log(f"已选择银行对账单: {path}")

    def _select_invoice(self):
        path = filedialog.askopenfilename(
            title="选择发票信息文件",
            filetypes=[("Excel files", "*.xlsx *.xls"), ("All files", "*.*")]
        )
        if path:
            self.invoice_file = path
            self.invoice_var.set(os.path.basename(path))
            self._log(f"已选择发票文件: {path}")

    def _load_data(self):
        if not self.bank_file or not self.invoice_file:
            messagebox.showwarning("提示", "请先选择银行对账单和发票信息文件！")
            return

        try:
            self.status_var.set("正在解析银行对账单...")
            self._log("开始解析银行对账单...")
            self.data_store.bank_transactions = parse_bank_statement(self.bank_file)
            income_count = len(self.data_store.get_income_transactions())
            self._log(f"银行流水解析完成: 共 {len(self.data_store.bank_transactions)} 笔，其中进账 {income_count} 笔")

            self.status_var.set("正在解析发票信息...")
            self._log("开始解析发票信息...")
            self.data_store.invoices = parse_invoices(self.invoice_file)
            positive_count = sum(1 for inv in self.data_store.invoices if inv.is_positive)
            self._log(f"发票解析完成: 共 {len(self.data_store.invoices)} 张，其中正数发票 {positive_count} 张")

            # 尝试加载参考数据
            ref_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "代码资料")
            customers_path = os.path.join(ref_dir, "客户编码.xlsx")
            subjects_path = os.path.join(ref_dir, "科目代码.xlsx")
            if os.path.exists(customers_path) and os.path.exists(subjects_path):
                self.data_store.load_reference_data(customers_path, subjects_path)
                self._log(f"基础数据加载完成: 客户 {len(self.data_store.customers)} 条")
            else:
                self._log("警告: 未找到基础数据文件，名称匹配功能将受限")

            self._refresh_bank_tree()
            self.status_var.set(f"数据加载完成 | 进账: {income_count} 笔 | 正数发票: {positive_count} 张")
            messagebox.showinfo("完成", f"数据加载成功！\n银行流水: {len(self.data_store.bank_transactions)} 笔\n进账: {income_count} 笔\n发票: {len(self.data_store.invoices)} 张")
        except Exception as e:
            self.status_var.set(f"加载失败: {str(e)}")
            self._log(f"错误: {str(e)}")
            messagebox.showerror("错误", f"数据加载失败:\n{str(e)}")

    def _refresh_bank_tree(self):
        # 清空
        for item in self.bank_tree.get_children():
            self.bank_tree.delete(item)
        # 填充进账数据
        total = 0.0
        count = 0
        for tx in self.data_store.bank_transactions:
            if tx.is_income:
                self.bank_tree.insert("", tk.END, values=(
                    tx.date, tx.bank_name, tx.counterparty_name,
                    f"{tx.credit:,.2f}", tx.summary
                ))
                total += tx.credit
                count += 1
        self.stats_label.config(text=f"进账笔数: {count} | 总金额: {total:,.2f}")

    def _match_data(self):
        if not self.data_store.bank_transactions or not self.data_store.invoices:
            messagebox.showwarning("提示", "请先加载数据！")
            return

        try:
            self.status_var.set("正在匹配银行进账与发票...")
            self._log("开始匹配进账与发票...")
            self.match_results = match_transactions(self.data_store)

            # 统计
            matched = sum(1 for r in self.match_results if r.matched_invoice)
            unmatched = len(self.match_results) - matched
            self._log(f"匹配完成: 已匹配 {matched} 笔，未匹配 {unmatched} 笔")

            self._refresh_match_tree()
            self.status_var.set(f"匹配完成 | 已匹配: {matched} | 未匹配: {unmatched}")
            messagebox.showinfo("完成", f"匹配完成！\n已匹配: {matched} 笔\n未匹配: {unmatched} 笔")
        except Exception as e:
            self.status_var.set(f"匹配失败: {str(e)}")
            self._log(f"错误: {str(e)}")
            messagebox.showerror("错误", f"匹配失败:\n{str(e)}")

    def _refresh_match_tree(self):
        for item in self.match_tree.get_children():
            self.match_tree.delete(item)
        for r in self.match_results:
            if r.matched_invoice:
                inv = r.matched_invoice
                status = "已匹配"
                tag = "matched"
                values = (
                    status, r.customer_name, r.customer_code, r.match_type,
                    f"{inv.total_amount:,.2f}",
                    f"{inv.deduction:,.2f}",
                    f"{inv.management_fee:,.2f}",
                    f"{inv.tax_amount:,.2f}"
                )
            else:
                status = "未匹配"
                tag = "unmatched"
                values = (status, r.customer_name, r.customer_code, "-", "-", "-", "-", "-")
            item_id = self.match_tree.insert("", tk.END, values=values, tags=(tag,))
        self.match_tree.tag_configure("matched", foreground="green")
        self.match_tree.tag_configure("unmatched", foreground="red")

    def _generate_vouchers(self):
        if not self.match_results:
            messagebox.showwarning("提示", "请先执行匹配！")
            return

        try:
            self.status_var.set("正在生成凭证...")
            self._log("开始生成凭证分录...")
            self.vouchers = generate_all_vouchers(self.match_results)

            # 统计
            total_entries = sum(len(v) for v in self.vouchers)
            self._log(f"凭证生成完成: 共 {len(self.vouchers)} 张凭证，{total_entries} 条分录")

            self._refresh_voucher_tree()
            self.status_var.set(f"凭证生成完成 | 共 {len(self.vouchers)} 张凭证")
            messagebox.showinfo("完成", f"凭证生成成功！\n共 {len(self.vouchers)} 张凭证\n{total_entries} 条分录")
        except Exception as e:
            self.status_var.set(f"生成失败: {str(e)}")
            self._log(f"错误: {str(e)}")
            messagebox.showerror("错误", f"凭证生成失败:\n{str(e)}")

    def _refresh_voucher_tree(self):
        for item in self.voucher_tree.get_children():
            self.voucher_tree.delete(item)
        for entries in self.vouchers:
            for e in entries:
                debit = e.debit_foreign if e.debit_foreign > 0 else 0
                credit = -e.debit_foreign if e.debit_foreign < 0 else 0
                cf = f"{e.cash_flow_code} {e.cash_flow_name}" if e.cash_flow_code else ""
                self.voucher_tree.insert("", tk.END, values=(
                    e.voucher_no, e.subject_code, e.subject_name,
                    f"{debit:,.2f}" if debit else "",
                    f"{credit:,.2f}" if credit else "",
                    e.aux1, e.aux2, cf
                ))

    def _on_bank_select(self, event):
        selection = self.bank_tree.selection()
        if not selection:
            return
        # 获取选中的索引
        item = selection[0]
        idx = self.bank_tree.index(item)
        # 找到对应的进账交易
        income_txs = self.data_store.get_income_transactions()
        if idx < len(income_txs):
            tx = income_txs[idx]
            self._log(f"选中进账: {tx.date} {tx.counterparty_name} {tx.credit:,.2f}")
            # 如果有匹配结果，显示对应的匹配详情
            if idx < len(self.match_results):
                r = self.match_results[idx]
                if r.matched_invoice:
                    inv = r.matched_invoice
                    self._log(f"  → 匹配发票: {inv.invoice_no}")
                    self._log(f"  → 购买方: {inv.buyer_name}")
                    self._log(f"  → 扣除额: {inv.deduction:,.2f}, 管理费: {inv.management_fee:,.2f}, 税额: {inv.tax_amount:,.2f}")

    def _export_excel(self):
        if not self.vouchers:
            messagebox.showwarning("提示", "请先生成凭证！")
            return

        path = filedialog.asksaveasfilename(
            title="导出凭证Excel",
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")]
        )
        if not path:
            return

        try:
            rows = export_vouchers_to_list(self.vouchers)
            df = pd.DataFrame(rows)
            df.to_excel(path, index=False, engine='openpyxl')
            self._log(f"凭证已导出到: {path}")
            self.status_var.set(f"导出成功: {os.path.basename(path)}")
            messagebox.showinfo("完成", f"凭证已导出到:\n{path}\n共 {len(rows)} 条分录")
        except Exception as e:
            self._log(f"导出失败: {str(e)}")
            messagebox.showerror("错误", f"导出失败:\n{str(e)}")


def main():
    root = tk.Tk()
    app = IncomeVoucherApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
