import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta, timezone

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><head><meta charset='UTF-8'><title>HKJC Index</title></head><body><h1>🏇 馬會數據索引</h1><p>更新 (HKT): {now_hkt.strftime('%Y-%m-%d %H:%M')}</p><hr><ul>{links}</ul></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    target_date = "2026-04-26" 
    
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    filename_csv = f"data/all_odds_{target_date}.csv"
    filename_html = f"data/all_odds_{target_date}.html"

    print(f"🚀 [API 模式] 開始抓取: {target_date}")

    # 馬會 API 網址 (WIN/PLA 賠率)
    # 這裡使用馬會 Web API，格式較為穩定
    url = f"https://hkjc.com{target_date}&venue=ST&start=1&end=12"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://hkjc.com'
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        data = resp.json() # 解析 JSON

        all_rows = []
        # 解析 JSON 結構 (馬會 API 格式)
        for race in data.get('OUT', []):
            r_no = race.get('RACENO')
            for horse in race.get('WIN', []):
                h_no = horse.get('HNO')
                win_odds = horse.get('ODDS')
                # 尋找對應的位置賠率
                pla_odds = ""
                for p in race.get('PLA', []):
                    if p.get('HNO') == h_no:
                        pla_odds = p.get('ODDS')
                        break
                
                all_rows.append({
                    'Capture_Time': hkt_now.strftime("%Y-%m-%d %H:%M"),
                    'Race_No': r_no,
                    '馬號': h_no,
                    '獨贏': win_odds,
                    '位置': pla_odds
                })

        if all_rows:
            df = pd.DataFrame(all_rows)
            # Accumulate (累加至 CSV)
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"✅ 成功獲取 {len(all_rows)} 筆賠率數據")
        else:
            print("⚠️ API 回傳空數據 (可能尚未開售或被封鎖)")

    except Exception as e:
        print(f"❌ API 抓取失敗: {e}")

    # --- 趨勢分析 HTML (邏輯同前) ---
    if os.path.exists(filename_csv):
        try:
            full_df = pd.read_csv(filename_csv)
            times = sorted(full_df['Capture_Time'].unique())
            if len(times) >= 2:
                latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
                prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
                for col in ['獨贏', '位置']:
                    merged = latest.merge(prev[['Race_No', '馬號', col]], on=['Race_No', '馬號'], suffixes=('', '_old'), how='left')
                    def get_trend(row, c):
                        try:
                            v1, v2 = float(row[c]), float(row[c+'_old'])
                            return f"{v1} ↓" if v1 < v2 else (f"{v1} ↑" if v1 > v2 else f"{v1}")
                        except: return str(row[c])
                    latest[col] = merged.apply(lambda r: get_trend(r, col), axis=1)
                display_df = latest
            else: display_df = full_df

            style = "<style>body{font-family:sans-serif;padding:20px;} table{border-collapse:collapse;width:100%;} td,th{border:1px solid #ccc;padding:8px;text-align:center;} .down{color:red;font-weight:bold;} .up{color:green;}</style>"
            table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><h2>{target_date} 賠率分析</h2>{table_html}</body></html>")
        except: pass

    update_index(hkt_now)

if __name__ == "__main__":
    scrape()
