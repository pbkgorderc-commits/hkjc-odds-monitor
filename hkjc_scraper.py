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
    
    # 目標日期 (2026-04-26 冠軍賽馬日)
    target_date = "2026-04-26"
    
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    filename_csv = f"data/all_odds_{target_date}.csv"
    filename_html = f"data/all_odds_{target_date}.html"

    print(f"🚀 [API 模式] 開始抓取: {target_date} | HKT: {hkt_now.strftime('%H:%M:%S')}")

    # 【修正重點：必須使用 bet.hkjc.com 作為域名】
    base_url = "https://hkjc.com"
    params = f"type=winplaodds&date={target_date}&venue=ST&start=1&end=12"
    full_url = f"{base_url}?{params}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://hkjc.com'
    }

    try:
        print(f"🔍 請求網址: {full_url}")
        resp = requests.get(full_url, headers=headers, timeout=20)
        
        if resp.status_code != 200:
            print(f"❌ 請求失敗，HTTP 狀態碼: {resp.status_code}")
            # 如果 403 代表 GitHub IP 被封鎖
            return

        # 解析 JSON 數據
        data = resp.json() 

        all_rows = []
        out_list = data.get('OUT', [])
        
        if not out_list:
            print("⚠️ API 回傳數據為空 (OUT list empty)，可能是馬會尚未開放賠率或目前非開售時段。")
        
        for race in out_list:
            r_no = race.get('RACENO')
            win_list = race.get('WIN', [])
            pla_list = race.get('PLA', [])
            
            for horse in win_list:
                h_no = horse.get('HNO')
                win_odds = horse.get('ODDS')
                # 尋找對應馬號的位置賠率
                pla_odds = next((p.get('ODDS') for p in pla_list if p.get('HNO') == h_no), "")
                
                all_rows.append({
                    'Capture_Time': hkt_now.strftime("%Y-%m-%d %H:%M"),
                    'Race_No': r_no,
                    '馬號': h_no,
                    '獨贏': win_odds,
                    '位置': pla_odds
                })

        if all_rows:
            df = pd.DataFrame(all_rows)
            # Accumulate: 累加至 CSV
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"✅ 成功獲取 {len(all_rows)} 筆賠率數據並累加。")
        else:
            print("ℹ️ 本次執行未獲取任何有效賠率。")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

    # --- 趨勢分析 HTML ---
    if os.path.exists(filename_csv):
        try:
            fdf = pd.read_csv(filename_csv)
            fdf['Capture_Time'] = fdf['Capture_Time'].astype(str)
            t_list = sorted(fdf['Capture_Time'].unique())
            if len(t_list) >= 2:
                cur = fdf[fdf['Capture_Time'] == t_list[-1]].copy()
                old = fdf[fdf['Capture_Time'] == t_list[-2]].copy()
                for c in ['獨贏', '位置']:
                    m = cur.merge(old[['Race_No', '馬號', c]], on=['Race_No', '馬號'], suffixes=('', '_o'), how='left')
                    def trend(r, col):
                        try:
                            v1, v2 = float(r[col]), float(r[col+'_o'])
                            if v1 < v2: return f"{v1} ↓"
                            if v1 > v2: return f"{v1} ↑"
                            return str(v1)
                        except: return str(r[col])
                    cur[c] = m.apply(lambda r: trend(r, c), axis=1)
                display_df = cur
            else:
                display_df = fdf

            style = "<style>body{font-family:sans-serif;padding:20px;} table{border-collapse:collapse;width:100%;} td,th{border:1px solid #ccc;padding:8px;text-align:center;} .down{color:red;font-weight:bold;} .up{color:green;}</style>"
            body = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><h2>{target_date} 賠率分析</h2>{body}</body></html>")
            print("📊 分析 HTML 已更新。")
        except:
            pass

    update_index(hkt_now)

if __name__ == "__main__":
    scrape()
