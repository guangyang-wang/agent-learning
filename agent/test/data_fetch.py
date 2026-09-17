import os
import time

import requests
import pandas as pd

import config

HEADERS = {
    "Referer": "http://fundf10.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def fetch_nav(fund_code, page_size=20, max_pages=500):
    """拉取基金全部历史净值，返回按日期升序的 DataFrame。

    该接口每页最多只返回 20 条，所以用 TotalCount 判断要翻多少页。
    """
    all_rows = []
    total = None
    for page in range(1, max_pages + 1):
        url = (
            f"https://api.fund.eastmoney.com/f10/lsjz"
            f"?fundCode={fund_code}&pageIndex={page}&pageSize={page_size}"
        )
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if total is None:
            total = data.get("TotalCount", 0)
        rows = data["Data"]["LSJZList"]
        if not rows:
            break
        all_rows.extend(rows)
        if total and len(all_rows) >= total:
            break
        if page % 20 == 0:
            print(f"  已下载 {len(all_rows)}/{total} 条...")
        time.sleep(0.1)  # 限速，避免触发反爬

    df = pd.DataFrame(all_rows)
    df["DWJZ"] = pd.to_numeric(df["DWJZ"], errors="coerce")  # 单位净值
    df["JZZZL"] = pd.to_numeric(df["JZZZL"], errors="coerce")  # 日增长率
    df["FSRQ"] = pd.to_datetime(df["FSRQ"])  # 日期
    df = df.dropna(subset=["DWJZ"]).sort_values("FSRQ").reset_index(drop=True)
    return df[["FSRQ", "DWJZ", "JZZZL"]]


def main():
    fund_code = input("请输入基金代码: ").strip()

    name = config.get_fund_name(fund_code)
    print(f"基金: {name or '未知'}({fund_code})")

    os.makedirs(config.DATA_DIR, exist_ok=True)
    nav = fetch_nav(fund_code)
    if nav.empty:
        print(f"未获取到 {fund_code} 的数据，请检查基金代码是否正确。")
        return

    nav.to_csv(config.data_file(fund_code), index=False)
    print(f"已下载 {len(nav)} 条净值数据 -> {config.data_file(fund_code)}")
    print(f"数据范围: {nav['FSRQ'].iloc[0].date()} ~ {nav['FSRQ'].iloc[-1].date()}")


if __name__ == "__main__":
    main()