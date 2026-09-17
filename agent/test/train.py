import os

import joblib
import pandas as pd
import lightgbm as lgb

import config
from features import make_features


def main():
    fund_code = input("请输入基金代码: ").strip()

    path = config.data_file(fund_code)
    if not os.path.exists(path):
        print(f"找不到数据文件 {path}，请先运行 data_fetch.py 下载数据。")
        return

    df = pd.read_csv(path, parse_dates=["FSRQ"])
    last_nav_date = df["FSRQ"].iloc[-1]  # 数据集中最新一天的日期

    data = make_features(df, lookback=config.LOOKBACK, horizon=config.HORIZON)

    # 排除日期、原始净值、目标、官方日增长率，剩下的都是特征
    drop_cols = {"FSRQ", "DWJZ", "target", "JZZZL"}
    features = [c for c in data.columns if c not in drop_cols]

    # 留出最后一条样本不训练，用来验证预测是否准确
    holdout = data.iloc[-1:]
    train_data = data.iloc[:-1]

    X_train, y_train = train_data[features], train_data["target"]

    model = lgb.LGBMRegressor(
        n_estimators=300, learning_rate=0.05, num_leaves=31, random_state=42
    )
    model.fit(X_train, y_train)

    # 用留出的样本预测最新一天的净值，和真实值对比
    y_true = holdout["target"].iloc[0]
    y_pred = model.predict(holdout[features])[0]

    print(f"预测目标: {last_nav_date.date()} 的净值")
    print(f"真实净值: {y_true:.4f}")
    print(f"预测净值: {y_pred:.4f}")
    print(f"误差: {abs(y_true - y_pred):.4f}  ({abs(y_true - y_pred) / y_true * 100:.2f}%)")

    joblib.dump({"model": model, "features": features}, config.model_file(fund_code))
    print(f"模型已保存 -> {config.model_file(fund_code)}")


if __name__ == "__main__":
    main()
