import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta, timezone

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><head><meta charset='UTF-8'></head><body><h1>馬會賠率索引</h1><p>更新: {now_hkt}</p><ul>{links}</ul></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    target_date = "2026-04-26"
    
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    filename_csv = f"data/all_odds_{target_date}.csv"
    filename_html = f"data/all_odds_{target_date}.html"

    # --- 🟢 這裡絕對包含 ://hkjc.com 網址 🟢 ---
    host = "bet" + ".hkjc" + ".com"
    api_url = f"https://{host}/racing/getJSON.aspx?type=winplaodds&date={target_date}&venue=ST&start=1&end=12"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': f'https://{host}/ch/racing/wp/'
    }

    print(f"🚀 開始抓取: {api_url}")

    try:
        resp = requests.get(api_url, headers=headers, timeout=20)
        data = resp.json()
        all_rows = []
        
        for race in data.get('OUT', []):
            r_no = race.get('RACENO')
            win_list = race.get('WIN', [])
            pla_list = race.get('PLA', [])
            for h in win_list:
                h_no = h.get('HNO')
                all_rows.append({
                    'Capture_Time': hkt_now.strftime("%Y-%m-%d %H:%M"),
                    'Race_No': r_no,
                    '馬號': h_no,
                    '獨贏': h.get('ODDS'),
                    '位置': next((p.get('ODDS') for p in pla_list if p.get('HNO') == h_no), "")
                })

        if all_rows:
            df = pd.DataFrame(all_rows)
            # 數據累加 (Accumulate)
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"✅ 成功存入 {len(all_rows)} 筆數據")

            # 生成變動 HTML
            fdf = pd.read_csv(filename_csv)
            times = sorted(fdf['Capture_Time'].astype(str).unique())
            if len(times) >= 2:
                latest = fdf[fdf['Capture_Time'] == times[-1]].copy()
                prev = fdf[fdf['Capture_Time'] == times[-2]].copy()
                for c in ['獨贏', '位置']:
                    m = latest.merge(prev[['Race_No', '馬號', c]], on=['Race_No', '馬號'], suffixes=('', '_old'), how='left')
                    def trend(r, col):
                        try:
                            v1, v2 = float(r[col]), float(r[col+'_old'])
                            return f"{v1} ↓" if v1 < v2 else (f"{v1} ↑" if v1 > v2 else str(v1))
                        except: return str(r[col])
                    latest[col] = m.apply(lambda r: trend(r, c), axis=1)
                display_df = latest
            else:
                display_df = fdf

            style = "<style>body{font-family:sans-serif;} table{border-collapse:collapse;width:100%;} td,th{border:1px solid #ccc;padding:8px;text-align:center;} .down{color:red;font-weight:bold;} .up{color:green;}</style>"
            body = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><h2>{target_date} 趨勢預覽</h2>{body}</body></html>")
        else:
            print("ℹ️ 無數據")

    except Exception as e:
        print(f"❌ 錯誤: {e}")

    update_index(hkt_now)

if __name__ == "__main__":
    scrape()
