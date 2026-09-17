# 基金估值预测项目的统一配置

import requests

LOOKBACK = 10    # 用过去多少天的净值做特征
HORIZON = 1      # 预测未来第几天（1 = 明天）

DATA_DIR = "data"    # 历史净值数据存放目录


def data_file(fund_code):
    """某只基金的历史净值数据文件路径。"""
    return f"{DATA_DIR}/{fund_code}_nav.csv"


def model_file(fund_code):
    """某只基金训练好的模型文件路径。"""
    return f"{fund_code}_model.pkl"


def get_fund_name(fund_code):
    """通过东方财富搜索接口获取基金名称，失败时返回 None。"""
    url = (
        "https://fundsuggest.eastmoney.com/FundSearch/api/"
        f"FundSearchAPI.ashx?m=1&key={fund_code}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "http://fund.eastmoney.com/",
    }
    try:
        data = requests.get(url, headers=headers, timeout=10).json()
        for item in data.get("Datas") or []:
            if item.get("CODE") == fund_code:
                return item.get("NAME")
    except Exception:
        pass
    return None
