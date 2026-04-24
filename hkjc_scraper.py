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
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_race_info(driver, date_str):
    try:
        # 嘗試從第一場頁面獲取開跑時間
        url = f"https://hkjc.com{date_str}/HV/1"
        driver.get(url)
        # 兼容多種可能的時間顯示位置
        xpath = "//div[@id='racebar']//span[contains(text(), '開跑時間')]/following-sibling::span"
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
        time_text = element.text.strip()
        hkt_race = datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %H:%M")
        return hkt_race - timedelta(hours=8) # 回傳 UTC
    except:
        return None

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data')
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><head><meta charset='UTF-8'><title>Index</title></head><body><h1>🏇 HKJC 數據索引</h1><p>更新時間: {now_hkt.strftime('%Y-%m-%d %H:%M')}</p><ul>{links}</ul></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    today, tomorrow = hkt_now.strftime("%Y-%m-%d"), (hkt_now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    driver = get_driver()
    target_date = None

    # 情境 A: 檢查明日賽事 (12:00 PM 後)
    if hkt_now.hour >= 12:
        tomorrow_race_utc = get_race_info(driver, tomorrow)
        if tomorrow_race_utc: target_date = tomorrow

    # 情境 B: 檢查今日賽事 (開賽前 2 小時截止)
    if not target_date:
        today_race_utc = get_race_info(driver, today)
        if today_race_utc and now_utc < (today_race_utc - timedelta(hours=2)):
            target_date = today

    if not target_date:
        print("ℹ️ 當前不在抓取時段")
        update_index(hkt_now)
        driver.quit()
        return

    # 執行抓取
    if not os.path.exists('data'): os.makedirs('data')
    venue = "ST" if "ST" in driver.current_url else "HV"
    filename_csv = f"data/all_odds_{target_date}_{venue}.csv"
    filename_html = f"data/all_odds_{target_date}_{venue}.html"

    for r in range(1, 13):
        try:
            driver.get(f"https://hkjc.com{target_date}/{venue}/{r}")
            WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
            df = max(pd.read_html(driver.page_source), key=len)
            df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
            df.insert(1, 'Race_No', r)
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"R{r} OK")
        except: continue

    # 趨勢分析預覽
    try:
        full_df = pd.read_csv(filename_csv)
        times = full_df['Capture_Time'].unique()
        if len(times) >= 2:
            latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
            prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
            # 針對含「賠率」字眼的欄位計算趨勢
            for col in latest.columns:
                if '賠率' in col:
                    merged = latest.merge(prev[['Race_No', '馬名', col]], on=['Race_No', '馬名'], suffixes=('', '_old'), how='left')
                    def trend(r, c):
                        try:
                            curr, old = float(r[c]), float(r[c+'_old'])
                            return "↓" if curr < old else ("↑" if curr > old else "—")
                        except: return ""
                    latest[f'{col}_趨勢'] = merged.apply(lambda r: trend(r, col), axis=1)
            display_df = latest
        else:
            display_df = full_df.tail(30)
        
        style = "<style>body{font-family:sans-serif;font-size:12px;}table{border-collapse:collapse;width:100%;}th{background:#eee;}td,th{border:1px solid #ccc;padding:4px;text-align:center;}.down{color:red;font-weight:bold;}.up{color:green;}</style>"
        table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
        with open(filename_html, 'w', encoding='utf-8-sig') as f:
            f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><a href='../index.html'>返回</a><h2>{target_date} {venue} 趨勢預覽</h2>{table_html}</body></html>")
    except Exception as e: print(f"HTML Error: {e}")

    update_index(hkt_now)
    driver.quit()

if __name__ == "__main__":
    scrape()
