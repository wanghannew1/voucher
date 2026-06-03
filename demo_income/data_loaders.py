"""
基础数据加载模块：客户编码、科目代码等
"""
import pandas as pd
from typing import Dict, Optional


def load_customers(file_path: str) -> Dict[str, Dict]:
    """加载客户编码表
    注意：该Excel文件的列名存在错位，实际数据映射为：
      - 客户名称列 = 客户编码（如 ch001, CBS0025）
      - 客户基本分类列 = 客户名称（如 吉林省兽药饲料检验监测所）
    返回: {客户编码: {name, classification, ...}}
    """
    df = pd.read_excel(file_path, sheet_name=0, header=0)
    customers = {}
    for _, row in df.iterrows():
        # 使用正确的列映射
        code_raw = row.get('客户名称', '')
        name_raw = row.get('客户基本分类', '')
        if pd.isna(code_raw) or pd.isna(name_raw):
            continue
        code = str(code_raw).strip()
        name = str(name_raw).strip()
        if not code or not name:
            continue
        if code.lower() in ['nan', 'none', 'null']:
            continue
        if name.lower() in ['nan', 'none', 'null']:
            continue
        # 客户编码应该是较短的字符串（如 ch001, CBS0025）
        if len(code) > 20 or '公司' in code:
            continue
        customers[code] = {
            'name': name,
            'classification': '',
            'code': code
        }
    return customers


def load_subject_codes(file_path: str) -> Dict[str, str]:
    """加载现金流量科目代码"""
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    subjects = {}
    for _, row in df.iterrows():
        val = str(row[0]).strip()
        if val and val != '现金流量表表项':
            # 格式: "1111销售商品、提供劳务收到的现金"
            code = val[:4]
            name = val[4:]
            subjects[code] = name
    return subjects


class DataStore:
    """数据存储中心"""
    def __init__(self):
        self.customers: Dict[str, Dict] = {}          # 客户编码表
        self.subject_codes: Dict[str, str] = {}       # 现金流量科目
        self.bank_transactions: list = []               # 银行流水
        self.invoices: list = []                      # 发票
        self.matched_results: list = []               # 匹配结果
        self.vouchers: list = []                      # 生成的凭证

    def load_reference_data(self, customers_path: str, subjects_path: str):
        """加载基础参考数据"""
        self.customers = load_customers(customers_path)
        self.subject_codes = load_subject_codes(subjects_path)

    def find_customer_by_name(self, name: str) -> Optional[Dict]:
        """根据名称查找客户编码"""
        if not name:
            return None
        name = name.strip()
        # 1. 精确匹配
        for code, info in self.customers.items():
            if info['name'] == name:
                return info
        # 2. 子串包含匹配
        for code, info in self.customers.items():
            if name in info['name'] or info['name'] in name:
                return info
        # 3. 去后缀匹配（去掉"有限公司"等）
        simplified = name.replace('有限公司', '').replace('有限责任公司', '').replace('股份有限公司', '').strip()
        if simplified and simplified != name:
            for code, info in self.customers.items():
                cust_simp = info['name'].replace('有限公司', '').replace('有限责任公司', '').replace('股份有限公司', '').strip()
                if simplified == cust_simp or simplified in cust_simp or cust_simp in simplified:
                    return info
        return None

    def get_income_transactions(self):
        """获取所有进账（收入）交易"""
        return [tx for tx in self.bank_transactions if tx.is_income]
