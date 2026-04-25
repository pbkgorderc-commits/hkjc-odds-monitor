import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta, timezone

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><head><meta charset='UTF-8'></head><body><h1>🏇 馬會數據索引</h1><p>更新: {now_hkt}</p><ul>{links}</ul></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    target_date = "2026-04-26"
    url_date = target_date.replace("-", "/")
    
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    filename_csv = f"data/all_odds_{target_date}.csv"
    filename_html = f"data/all_odds_{target_date}.html"

    # --- ✨ 切換到資訊版 (Racing Info) 接口，繞過投注區封鎖 ---
    print(f"🚀 [資訊版模式] 開始抓取: {target_date}")

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://hkjc.com'
    }

    all_rows = []

    # 資訊版需要逐場抓取以確保穩定
    for r in range(1, 13):
        # 這是資訊版背後的數據源網址
        api_url = f"https://hkjc.com?RaceDate={url_date}&RaceNo={r}"
        
        try:
            resp = requests.get(api_url, headers=headers, timeout=20)
            if resp.status_code != 200: continue
            
            # 使用 pandas 直接從 HTML 原始碼解析 (資訊版不需要 JSON)
            dfs = pd.read_html(resp.text)
            df = None
            for d in dfs:
                if '馬名' in str(d.values):
                    df = d
                    break
            
            if df is not None:
                # 清洗數據
                df = df.iloc[:, :4]
                df.columns = ['馬號', '馬名', '獨贏', '位置']
                df = df[df['馬名'].notna() & (df['馬名'] != '馬名')].copy()
                
                df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
                df.insert(1, 'Race_No', r)
                
                # 累加數據
                df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
                all_rows.append(df)
                print(f"✅ 第 {r} 場抓取成功")
            
            time.sleep(2)
        except Exception as e:
            print(f"⚠️ 第 {r} 場跳過: {e}")

    # --- 生成分析 HTML ---
    if os.path.exists(filename_csv):
        try:
            fdf = pd.read_csv(filename_csv)
            t_list = sorted(fdf['Capture_Time'].astype(str).unique())
            if len(t_list) >= 2:
                latest = fdf[fdf['Capture_Time'] == t_list[-1]].copy()
                prev = fdf[fdf['Capture_Time'] == t_list[-2]].copy()
                for col in ['獨贏', '位置']:
                    merged = latest.merge(prev[['Race_No', '馬號', col]], on=['Race_No', '馬號'], suffixes=('', '_old'), how='left')
                    def trend(r, c):
                        try:
                            v1, v2 = float(r[c]), float(r[c+'_old'])
                            if v1 < v2: return f"{v1} ↓"
                            if v1 > v2: return f"{v1} ↑"
                            return str(v1)
                        except: return str(r[c])
                    latest[col] = merged.apply(lambda r: trend(r, col), axis=1)
                display_df = latest
            else:
                display_df = fdf

            style = "<style>body{font-family:sans-serif;padding:20px;} table{border-collapse:collapse;width:100%;} td,th{border:1px solid #ccc;padding:8px;text-align:center;} .down{color:red;font-weight:bold;} .up{color:green;}</style>"
            body = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><h2>{target_date} 趨勢分析</h2>{body}</body></html>")
        except:
            pass

    update_index(hkt_now)

if __name__ == "__main__":
    scrape()
