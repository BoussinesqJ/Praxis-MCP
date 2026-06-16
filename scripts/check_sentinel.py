import akshare as ak
import pandas as pd

def get_sentinel_value():
    # 定义 8 只核心哨兵 ETF
    etfs = {
        '510300': '沪深300ETF',
        '510500': '中证500ETF',
        '588000': '科创50ETF',
        '512760': '芯片ETF',
        '515070': 'AI ETF',
        '560010': '绿电ETF',
        '512000': '证券ETF',
        '513180': '恒指科技ETF'
    }

    results = []
    bull_count = 0

    print(f"{'名称':<10} | {'现价':<6} | {'MA20':<6} | {'信号'}")
    print("-" * 40)

    for code, name in etfs.items():
        try:
            # 修正 symbol 映射逻辑：51/56/58 开头为上海 (1.)，15 开头为深圳 (0.)，恒指科技 513180 为上海 (1.)
            if code.startswith(('51', '56', '58')):
                secid = f"1.{code}"
            else:
                secid = f"0.{code}"

            url = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
            params = {
                "secid": secid,
                "fields1": "f1,f2,f3,f4,f5",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
                "klt": "101", # 日线
                "fqt": "1",   # 前复权
                "beg": "0",
                "end": "20500101",
                "lmt": "40"   # 获取最近40天
            }

            import requests
            # 强制不使用代理
            response = requests.get(url, params=params, proxies={"http": None, "https": None}, timeout=10)
            data = response.json()

            if data and data['data'] and data['data']['klines']:
                klines = [x.split(',') for x in data['data']['klines']]
                df = pd.DataFrame(klines, columns=['date', 'open', 'close', 'high', 'low', 'vol', 'amt', 'pct'])
                df['close'] = pd.to_numeric(df['close'])

                current_price = df['close'].iloc[-1]
                ma20 = df['close'].rolling(20).mean().iloc[-1]

            is_bull = current_price > ma20
            signal = "🟢 多" if is_bull else "🔴 空"

            if is_bull:
                bull_count += 1

            print(f"{name:<10} | {current_price:<8.3f} | {ma20:<8.3f} | {signal}")
        except Exception as e:
            print(f"{name:<10} | 数据获取失败")

    print("-" * 40)
    print(f"最终哨兵值: {bull_count}/8")

if __name__ == "__main__":
    get_sentinel_value()
