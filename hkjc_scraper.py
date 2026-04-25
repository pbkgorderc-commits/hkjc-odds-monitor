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
    # 關鍵：模擬真實瀏覽器，避免被馬會阻擋
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_race_info(driver, date_str):
    """檢查指定日期是否有賽事並獲取首場開賽時間"""
    try:
        # 修正後的投注版 URL
        url = f"https://hkjc.com{date_str}/ST/1"
        driver.get(url)
        
        # 等待開跑時間元素出現
        xpath = "//span[contains(@class, 'startTime')]"
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
        
        time_text = element.text.replace("開跑時間 : ", "").strip()
        hkt_race = datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %H:%M")
        return hkt_race - timedelta(hours=8) # 返回 UTC 時間
    except:
        try:
            # 嘗試跑馬地場地
            url = f"https://hkjc.com{date_str}/HV/1"
            driver.get(url)
            element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//span[contains(@class, 'startTime')]")))
            time_text = element.text.replace("開跑時間 : ", "").strip()
            hkt_race = datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %H:%M")
            return hkt_race - timedelta(hours=8)
        except:
            return None

def update_index(now_hkt):
    """更新 index.html 以便在 GitHub Pages 瀏覽"""
    if not os.path.exists('data'): os.makedirs('data')
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><head><meta charset='UTF-8'><title>Index</title></head><body><h1>🏇 HKJC 數據索引</h1><p>更新時間: {now_hkt.strftime('%Y-%m-%d %H:%M')}</p><ul>{links}</ul></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    today = hkt_now.strftime("%Y-%m-%d")
    tomorrow = (hkt_now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    driver = get_driver()
    target_date = None

    # 1. 檢查明天是否有賽事 (通常前一天中午預售)
    tomorrow_race_utc = get_race_info(driver, tomorrow)
    if tomorrow_race_utc and hkt_now.hour >= 12:
        target_date = tomorrow
    
    # 2. 如果明天沒賽事，檢查今天 (賽後 3 小時內仍執行)
    if not target_date:
        today_race_utc = get_race_info(driver, today)
        if today_race_utc and now_utc < (today_race_utc + timedelta(hours=10)):
            target_date = today

    if not target_date:
        print("ℹ️ 當前不在抓取時段")
        update_index(hkt_now)
        driver.quit()
        return

    # 確定場地
    venue = "HV" if "/HV/" in driver.current_url else "ST"
    if not os.path.exists('data'): os.makedirs('data')
    filename_csv = f"data/all_odds_{target_date}_{venue}.csv"
    filename_html = f"data/all_odds_{target_date}_{venue}.html"

    # 開始抓取 1-12 場
    for r in range(1, 13):
        try:
            driver.get(f"https://hkjc.com{target_date}/{venue}/{r}")
            # 等待表格載入
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "wpTable")))
            
            # 讀取表格資料
            dfs = pd.read_html(driver.page_source)
            df = max(dfs, key=len)
            
            df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
            df.insert(1, 'Race_No', r)
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"R{r} OK")
            time.sleep(1) # 稍微停頓
        except:
            continue

    # 生成趨勢分析 HTML
    try:
        full_df = pd.read_csv(filename_csv)
        times = full_df['Capture_Time'].unique()
        if len(times) >= 2:
            latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
            prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
            
            for col in latest.columns:
                if '獨贏' in str(col) or '位置' in str(col):
                    # 邏輯合併計算趨勢
                    latest[f'{col}_趨勢'] = "—" # 簡化邏輯
            display_df = latest
        else:
            display_df = full_df.tail(20)
        
        style = "<style>body{font-family:sans-serif;font-size:12px;}table{border-collapse:collapse;width:100%;}th{background:#eee;}td,th{border:1px solid #ccc;padding:4px;text-align:center;}.down{color:red;font-weight:bold;}.up{color:green;}</style>"
        table_html = display_df.to_html(index=False)
        with open(filename_html, 'w', encoding='utf-8-sig') as f:
            f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><a href='../index.html'>返回</a><h2>{target_date} {venue} 賠率預覽</h2>{table_html}</body></html>")
    except Exception as e:
        print(f"HTML Error: {e}")

    update_index(hkt_now)
    driver.quit()

if __name__ == "__main__":
    scrape()
