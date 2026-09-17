import pandas as pd


def make_features(df, lookback=10, horizon=1, dropna=True):
    """把净值序列转成监督学习样本。

    horizon 表示预测未来第几天（1 = 明天）。
    dropna=False 时保留最新一行（target 为 NaN），用于预测未来。
    """
    df = df.copy()

    # 目标：未来第 horizon 天的净值
    df["target"] = df["DWJZ"].shift(-horizon)

    # 特征：过去 lookback 天的净值
    for i in range(1, lookback + 1):
        df[f"nav_lag_{i}"] = df["DWJZ"].shift(i)

    # 技术指标
    df["ret_1"] = df["DWJZ"].pct_change()        # 日涨跌幅
    df["ma_5"] = df["DWJZ"].rolling(5).mean()    # 5 日均线
    df["ma_20"] = df["DWJZ"].rolling(20).mean()  # 20 日均线
    df["std_20"] = df["DWJZ"].rolling(20).std()  # 20 日波动率

    if dropna:
        df = df.dropna().reset_index(drop=True)
    return df