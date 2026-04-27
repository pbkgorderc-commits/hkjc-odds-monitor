import requests
import pandas as pd
import os
from datetime import datetime

def scrape():
    # 1. 設定時間與路徑
    target_date = datetime.now().strftime("%Y-%m-%d")
    if not os.path.exists('data'): os.makedirs('data')
    
    # 2. 馬會賠率 API (獨贏/位置)
    # 注意：這是馬會後台數據接口範例，實際需根據比賽日調整
    url = "https://hkjc.com{}&venue=ST&start=1&end=12".format(target_date)
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Referer': 'https://hkjc.com'
    }

    print(f"🚀 開始抓取 {target_date} 數據...")

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            print(f"❌ 抓取失敗，狀態碼: {resp.status_code}")
            return

        data = resp.json()
        
        # 3. 解析數據 (假設接口回傳名為 'out' 的數據列)
        all_data = []
        for match in data.get('out', []):
            race_no = match.get('rno')
            for horse in match.get('win', []):
                all_data.append({
                    'Capture_Time': datetime.now().strftime("%Y-%m-%d %H:%M"),
                    'Race_No': race_no,
                    '馬號': horse.get('no'),
                    '獨贏': horse.get('odds'),
                    '位置': horse.get('p1') # 簡化範例
                })

        # 4. 儲存數據
        df = pd.DataFrame(all_data)
        if not df.empty:
            filename = f"data/all_odds_{target_date}.csv"
            df.to_csv(filename, index=False, encoding="utf-8-sig")
            print(f"✅ 成功儲存至 {filename}")
        else:
            print("⚠️ 今日可能非賽馬日，無數據。")

    except Exception as e:
        print(f"💥 程式出錯: {e}")

if __name__ == "__main__":
    scrape()
