import pandas as pd
import os
import time
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def scrape():
    # 1. 時間處理
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    
    # 測試期間：強制指定 2026-04-26，正式運作時可改回自動判斷
    target_date = "2026-04-26" 
    url_date = target_date.replace("-", "/")
    
    driver = get_driver()
    if not os.path.exists('data'): os.makedirs('data')
    
    filename_csv = f"data/all_odds_{target_date}.csv"
    filename_html = f"data/all_odds_{target_date}.html"
    
    print(f"🚀 開始抓取 {target_date} 賠率 | HKT: {hkt_now.strftime('%H:%M:%S')}")

    # 2. 執行抓取 R1 - R11 (冠軍賽馬日通常 11 或 12 場)
    for r in range(1, 13):
        # 修正後的正確資訊版 URL
        url = f"https://hkjc.com{url_date}&RaceNo={r}"
        try:
            driver.get(url)
            # 等待表格內容加載
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "table_bd")))
            
            # 提取表格
            dfs = pd.read_html(driver.page_source)
            df = None
            for d in dfs:
                if '馬名' in str(d.values):
                    df = d
                    break
            
            if df is not None:
                # 數據清洗：只取前四欄 (通常是 馬號, 馬名, 獨贏, 位置)
                df = df.iloc[:, :4]
                df.columns = ['馬號', '馬名', '獨贏', '位置']
                # 過濾掉非馬匹資料的行
                df = df[df['馬名'].notna() & (df['馬名'] != '馬名')]
                
                df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
                df.insert(1, 'Race_No', r)
                
                # 🟢 核心功能：Accumulate (累加到 CSV)
                df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
                print(f"✅ R{r} OK")
            
            time.sleep(1)
        except Exception as e:
            # 如果某場還沒開售會跳過
            continue

    # 3. 📊 生成 HTML 與 趨勢分析
    try:
        full_df = pd.read_csv(filename_csv)
        times = sorted(full_df['Capture_Time'].unique())
        
        if len(times) >= 2:
            # 取最後兩次時間點做對比
            latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
            prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
            
            for col in ['獨贏', '位置']:
                merged = latest.merge(prev[['Race_No', '馬號', col]], on=['Race_No', '馬號'], suffixes=('', '_old'), how='left')
                def get_trend(row, c):
                    try:
                        curr, old = float(row[c]), float(row[c+'_old'])
                        if curr < old: return f"{curr} ↓" # 降賠變熱
                        if curr > old: return f"{curr} ↑" # 升賠變冷
                        return str(curr)
                    except: return str(row[c])
                latest[col] = merged.apply(lambda r: get_trend(r, col), axis=1)
            display_df = latest
        else:
            display_df = full_df.tail(20)

        # 樣式與輸出
        style = """
        <style>
            body { font-family: sans-serif; padding: 20px; }
            table { border-collapse: collapse; width: 100%; font-size: 14px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: center; }
            th { background-color: #f2f2f2; }
            .down { color: red; font-weight: bold; }
            .up { color: green; }
        </style>
        """
        table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
        
        with open(filename_html, 'w', encoding='utf-8-sig') as f:
            f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body>")
            f.write(f"<h2>🏇 HKJC {target_date} 賠率變動預覽</h2>")
            f.write(f"<p>更新時間: {times[-1]} (對比: {times[-2] if len(times)>1 else '首次抓取'})</p>")
            f.write(table_html)
            f.write("</body></html>")
            
        # 更新 index.html
        update_index(hkt_now)
            
    except Exception as e:
        print(f"分析失敗: {e}")

    driver.quit()

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data')
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><body><h1>馬會數據索引</h1><ul>{links}</ul><p>最後執行: {now_hkt}</p></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

if __name__ == "__main__":
    scrape()
