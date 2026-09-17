import os

import joblib
import pandas as pd
import numpy as np

import config
from features import make_features


def predict_next(model, features, df):
    """用当前数据最后一行特征，预测未来第 1 天的净值。"""
    data = make_features(
        df, lookback=config.LOOKBACK, horizon=config.HORIZON, dropna=False
    )
    last = data[features].iloc[-1:]  # 保留 DataFrame 和列名，避免特征名警告
    return model.predict(last)[0]


def main():
    # 迭代预测依赖"预测明天"的模型，HORIZON 必须是 1
    if config.HORIZON != 1:
        print(f"迭代预测需要 HORIZON=1，当前是 {config.HORIZON}。")
        print("请把 config.py 里的 HORIZON 改成 1，重新训练后再预测。")
        return

    fund_code = input("请输入基金代码: ").strip()

    path = config.model_file(fund_code)
    if not os.path.exists(path):
        print(f"找不到模型文件 {path}，请先运行 train.py 训练。")
        return

    bundle = joblib.load(path)
    model, features = bundle["model"], bundle["features"]

    df = pd.read_csv(config.data_file(fund_code), parse_dates=["FSRQ"])
    start_date = df["FSRQ"].iloc[-1]  # 预测起点 = 最新数据日期

    name = config.get_fund_name(fund_code)
    print(f"基金: {name or fund_code}({fund_code})")
    print(f"从 {start_date.date()} 开始预测：")

    try:
        count = int(input("请输入要预测的天数 count: "))
    except ValueError:
        print("输入的不是整数")
        return
    if count <= 0:
        print("count 必须是正整数")
        return

    work = df.copy()
    for _ in range(count):
        pred = predict_next(model, features, work)
        # 把预测值当作真实净值追加到末尾，用于下一步迭代预测
        next_date = work["FSRQ"].iloc[-1] + pd.offsets.BDay(1)  # 下一个工作日
        work = pd.concat(
            [work, pd.DataFrame([{"FSRQ": next_date, "DWJZ": pred, "JZZZL": np.nan}])],
            ignore_index=True,
        )
        print(f"{next_date.date()} 预测净值: {pred:.4f}")


if __name__ == "__main__":
    main()