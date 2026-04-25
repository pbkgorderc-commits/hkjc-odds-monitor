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
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_race_info(driver, date_str):
    """檢查賽事並獲取第一場開跑時間 (HKT)"""
    for v in ["ST", "HV"]:
        try:
            url = f"https://hkjc.com{date_str}/{v}/1"
            driver.get(url)
            xpath = "//span[contains(@class, 'startTime')]"
            element = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, xpath)))
            time_text = element.text.replace("開跑時間 : ", "").strip()
            return datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %H:%M"), v
        except:
            continue
    return None, None

def update_index(now_hkt):
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
    target_date, venue = None, None

    # 1. 檢查明天 (賽前一天 12:00 PM 後開始)
    if hkt_now.hour >= 12:
        tomorrow_hkt, v = get_race_info(driver, tomorrow)
        if tomorrow_hkt:
            target_date, venue = tomorrow, v

    # 2. 檢查今天 (開賽後 10 小時內持續更新，覆蓋整天賽事)
    if not target_date:
        today_hkt, v = get_race_info(driver, today)
        if today_hkt and hkt_now < (today_hkt + timedelta(hours=10)):
            target_date, venue = today, v

    if not target_date:
        print(f"ℹ️ {hkt_now.strftime('%Y-%m-%d %H:%M')} 非抓取時段")
        update_index(hkt_now)
        driver.quit()
        return

    if not os.path.exists('data'): os.makedirs('data')
    filename_csv = f"data/all_odds_{target_date}_{venue}.csv"
    filename_html = f"data/all_odds_{target_date}_{venue}.html"

    # 執行抓取 1-12 場
    for r in range(1, 13):
        try:
            driver.get(f"https://hkjc.com{target_date}/{venue}/{r}")
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "wpTable")))
            
            # 抓取表格
            df = max(pd.read_html(driver.page_source), key=len)
            
            # 清洗數據：保留馬名、獨贏、位置
            df = df.iloc[:, [2, 3, 4]] # 通常是 馬名, 獨贏, 位置
            df.columns = ['馬名', '獨贏', '位置']
            
            df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
            df.insert(1, 'Race_No', r)
            
            # Accumulate: 附加到 CSV
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"R{r} OK")
            time.sleep(1)
        except:
            continue

    # 趨勢分析
    try:
        full_df = pd.read_csv(filename_csv)
        full_df['Capture_Time'] = full_df['Capture_Time'].astype(str)
        times = sorted(full_df['Capture_Time'].unique())
        
        if len(times) >= 2:
            latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
            prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
            
            for col in ['獨贏', '位置']:
                merged = latest.merge(prev[['Race_No', '馬名', col]], on=['Race_No', '馬名'], suffixes=('', '_old'), how='left')
                def get_trend(row, c):
                    try:
                        curr, old = float(row[c]), float(row[c+'_old'])
                        if curr < old: return f"{curr} ↓" # 降熱
                        if curr > old: return f"{curr} ↑" # 冷了
                        return f"{curr}"
                    except: return row[c]
                latest[col] = merged.apply(lambda r: get_trend(r, col), axis=1)
            display_df = latest
        else:
            display_df = full_df.tail(20)
        
        style = "<style>body{font-family:sans-serif;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ccc;padding:8px;text-align:center;}.down{color:red;font-weight:bold;}.up{color:green;}</style>"
        table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
        
        with open(filename_html, 'w', encoding='utf-8-sig') as f:
            f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><a href='../index.html'>返回首頁</a><h2>{target_date} {venue} 賠率變動 (比對上次抓取)</h2>{table_html}</body></html>")
    except Exception as e:
        print(f"Analysis Error: {e}")

    update_index(hkt_now)
    driver.quit()

if __name__ == "__main__":
    scrape()
