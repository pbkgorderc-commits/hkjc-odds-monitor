import requests
import pandas as pd
import os
import time
from datetime import datetime, timedelta, timezone

def update_index(now_hkt):
    """更新根目錄的索引頁面"""
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"""
    <html><head><meta charset='UTF-8'><title>HKJC Data Index</title>
    <style>body{{font-family:sans-serif; padding:20px; line-height:1.6;}} a{{text-decoration:none; color:#0066cc;}}</style>
    </head><body>
    <h1>🏇 馬會賠率數據索引</h1>
    <p>最後更新時間 (HKT): {now_hkt.strftime('%Y-%m-%d %H:%M')}</p>
    <hr><ul>{links}</ul>
    </body></html>
    """
    with open('index.html', 'w', encoding='utf-8-sig') as f:
        f.write(html)

def scrape():
    # 1. 時間處理 (設定抓取目標日期)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    
    # 強制測試 2026-04-26 (冠軍賽馬日)
    target_date = "2026-04-26" 
    url_date = target_date.replace("-", "/")
    
    if not os.path.exists('data'): os.makedirs('data', exist_ok=True)
    filename_csv = f"data/all_odds_{target_date}.csv"
    filename_html = f"data/all_odds_{target_date}.html"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7'
    }

    print(f"🚀 開始抓取: {target_date} | 當前時間: {hkt_now.strftime('%H:%M:%S')}")

    # 2. 抓取 R1 - R12
    for r in range(1, 13):
        url = f"https://hkjc.com{url_date}&RaceNo={r}"
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            if "沒有賽事紀錄" in resp.text:
                continue
                
            dfs = pd.read_html(resp.text)
            df = None
            for d in dfs:
                if '馬名' in str(d.values):
                    df = d
                    break
            
            if df is not None:
                # 數據清洗 (取前四欄：馬號, 馬名, 獨贏, 位置)
                df = df.iloc[:, :4]
                df.columns = ['馬號', '馬名', '獨贏', '位置']
                df = df[df['馬名'].notna() & (df['馬名'] != '馬名')].copy()
                
                # 插入時間與場次
                df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
                df.insert(1, 'Race_No', r)
                
                # 🔴 累加至 CSV (Accumulate)
                df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
                print(f"✅ 第 {r} 場: 抓取成功")
            
            time.sleep(1.5) # 防止過快被封
        except Exception as e:
            print(f"⚠️ 第 {r} 場跳過: {e}")

    # 3. 📈 生成趨勢分析 HTML
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
                    def get_t(row, c):
                        try:
                            v1, v2 = float(row[c]), float(row[c+'_old'])
                            if v1 < v2: return f"{v1} ↓"
                            if v1 > v2: return f"{v1} ↑"
                            return f"{v1}"
                        except: return str(row[c])
                    latest[col] = merged.apply(lambda r: get_t(r, col), axis=1)
                display_df = latest
            else:
                display_df = full_df

            style = """
            <style>
                body { font-family: sans-serif; padding: 20px; }
                table { border-collapse: collapse; width: 100%; margin-top: 10px; }
                th, td { border: 1px solid #ccc; padding: 8px; text-align: center; }
                th { background: #f4f4f4; }
                .down { color: #d00; font-weight: bold; } /* 賠率降 = 熱門 */
                .up { color: #080; } /* 賠率升 = 冷門 */
            </style>
            """
            table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
            
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body>")
                f.write(f"<h2>🏇 {target_date} 賠率變動預覽</h2>")
                f.write(f"<p>更新時間: {times[-1]} (對比上次抓取)</p>")
                f.write(table_html)
                f.write("</body></html>")
            print("📊 HTML 分析頁面已更新")
        except Exception as e:
            print(f"❌ 分析失敗: {e}")

    update_index(hkt_now)

if __name__ == "__main__":
    scrape()
