import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta, timezone

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"""
    <html><head><meta charset='UTF-8'><title>HKJC Index</title>
    <style>body{{font-family:sans-serif; padding:20px;}} a{{text-decoration:none; color:#0066cc;}}</style>
    </head><body>
    <h1>🏇 馬會賠率數據索引</h1>
    <p>最後更新 (HKT): {now_hkt.strftime('%Y-%m-%d %H:%M')}</p>
    <hr><ul>{links}</ul>
    </body></html>
    """
    with open('index.html', 'w', encoding='utf-8-sig') as f:
        f.write(html)

def scrape():
    # 1. 時間處理
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    
    # 目標日期
    target_date = "2026-04-26" 
    
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    filename_csv = f"data/all_odds_{target_date}.csv"
    filename_html = f"data/all_odds_{target_date}.html"
    
    # 模擬真實瀏覽器標頭
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8'
    }

    print(f"🚀 開始抓取: {target_date} | HKT: {hkt_now.strftime('%H:%M:%S')}")

    # 2. 執行抓取 R1 - R12
    # 嘗試兩個可能的場地：ST (沙田) 和 HV (跑馬地)
    for r in range(1, 13):
        success = False
        for venue in ["ST", "HV"]:
            # 【修正重點】網址拼接加上明確的斜槓，避免出現 hkjc.com2026
            url = f"https://hkjc.com{target_date}/{venue}/{r}"
            
            try:
                resp = requests.get(url, headers=headers, timeout=15)
                # 判斷是否抓得到表格
                dfs = pd.read_html(resp.text)
                
                df = None
                for d in dfs:
                    if '馬名' in str(d.values) or 'Horse' in str(d.values):
                        df = d
                        break
                
                if df is not None:
                    # 數據清洗
                    df = df.iloc[:, :4]
                    df.columns = ['馬號', '馬名', '獨贏', '位置']
                    df = df[df['馬名'].notna() & (df['馬名'] != '馬名')].copy()
                    
                    df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
                    df.insert(1, 'Race_No', r)
                    
                    # 累加至 CSV
                    df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
                    print(f"✅ 第 {r} 場 ({venue}): 抓取成功")
                    success = True
                    break # 如果 ST 成功就不必跑 HV
            except:
                continue # 如果這個場地不行，試下一個
        
        if not success:
            # 如果投注區抓不到，最後嘗試資訊版網址 (最穩定)
            try:
                url_info = f"https://hkjc.com{target_date.replace('-','/')}&RaceNo={r}"
                resp = requests.get(url_info, headers=headers, timeout=10)
                dfs = pd.read_html(resp.text)
                for d in dfs:
                    if '馬名' in str(d.values):
                        df = d
                        df = df.iloc[:, :4]
                        df.columns = ['馬號', '馬名', '獨贏', '位置']
                        df = df[df['馬名'].notna() & (df['馬名'] != '馬名')].copy()
                        df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
                        df.insert(1, 'Race_No', r)
                        df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
                        print(f"✅ 第 {r} 場 (Info): 抓取成功")
                        break
            except:
                print(f"⚠️ 第 {r} 場: 無法獲取數據")

        time.sleep(2)

    # 3. 趨勢分析
    if os.path.exists(filename_csv):
        try:
            full_df = pd.read_csv(filename_csv)
            full_df['Capture_Time'] = full_df['Capture_Time'].astype(str)
            times = sorted(full_df['Capture_Time'].unique())
            
            if len(times) >= 2:
                latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
                prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
                for col in ['獨贏', '位置']:
                    merged = latest.merge(prev[['Race_No', '馬號', col]], on=['Race_No', '馬號'], suffixes=('', '_old'), how='left')
                    def get_trend(row, c):
                        try:
                            v1, v2 = float(row[c]), float(row[c+'_old'])
                            if v1 < v2: return f"{v1} ↓"
                            if v1 > v2: return f"{v1} ↑"
                            return f"{v1}"
                        except: return str(row[c])
                    latest[col] = merged.apply(lambda r: get_trend(r, col), axis=1)
                display_df = latest
            else:
                display_df = full_df

            style = "<style>body{font-family:sans-serif; padding:20px;} table{border-collapse:collapse; width:100%;} td,th{border:1px solid #ccc; padding:8px; text-align:center;} .down{color:red; font-weight:bold;} .up{color:green;}</style>"
            table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
            
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body>")
                f.write(f"<h2>🏇 {target_date} 賠率分析預覽</h2><p>更新時間: {times[-1]}</p>{table_html}</body></html>")
        except Exception as e:
            print(f"❌ 分析失敗: {e}")

    update_index(hkt_now)

if __name__ == "__main__":
    scrape()
