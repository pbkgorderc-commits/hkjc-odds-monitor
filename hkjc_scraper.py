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
    # 加入更真實的 User-Agent 避免被封鎖
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_race_info(driver, date_str):
    """檢查指定日期是否有賽事並獲取場地與開賽時間"""
    for v in ["ST", "HV"]:
        # 修正後的完整 URL 格式
        url = f"https://hkjc.com{date_str}/{v}/1"
        try:
            driver.get(url)
            # 等待開跑時間元件
            xpath = "//span[contains(@class, 'startTime')]"
            element = WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, xpath)))
            time_text = element.text.replace("開跑時間 : ", "").strip()
            # 成功獲取代表該日期有賽事
            return datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %H:%M"), v
        except:
            continue
    return None, None

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data')
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><head><meta charset='UTF-8'><title>HKJC Odds Tracker</title></head><body><h1>🏇 HKJC 賠率數據索引</h1><p>最後更新: {now_hkt.strftime('%Y-%m-%d %H:%M')}</p><ul>{links}</ul></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    today = hkt_now.strftime("%Y-%m-%d")
    tomorrow = (hkt_now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    driver = get_driver()
    target_date, venue = None, None

    print(f"🚀 啟動檢查... 當前 HKT: {hkt_now.strftime('%Y-%m-%d %H:%M')}")

    # 1. 檢查明天 (若現在是前一天中午 12:00 後)
    if hkt_now.hour >= 12:
        print(f"🔍 檢查明天 ({tomorrow}) 是否有賽事預售...")
        tomorrow_hkt, v = get_race_info(driver, tomorrow)
        if tomorrow_hkt:
            print(f"✅ 發現賽事前夕數據: {tomorrow} [{v}]")
            target_date, venue = tomorrow, v

    # 2. 檢查今天 (若明天沒資料，或者現在就是比賽日)
    if not target_date:
        print(f"🔍 檢查今天 ({today}) 是否為比賽日...")
        today_hkt, v = get_race_info(driver, today)
        # 只要在今天開賽時間後的 10 小時內都繼續抓（涵蓋整場賽事）
        if today_hkt and hkt_now < (today_hkt + timedelta(hours=10)):
            print(f"✅ 發現今日賽事數據: {today} [{v}]")
            target_date, venue = today, v

    if not target_date:
        print("ℹ️ 當前非賽事期間，停止抓取。")
        update_index(hkt_now)
        driver.quit()
        return

    # --- 開始抓取邏輯 ---
    if not os.path.exists('data'): os.makedirs('data')
    filename_csv = f"data/all_odds_{target_date}_{venue}.csv"
    filename_html = f"data/all_odds_{target_date}_{venue}.html"

    all_data = []
    for r in range(1, 13):
        try:
            url = f"https://hkjc.com{target_date}/{venue}/{r}"
            driver.get(url)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "wpTable")))
            
            # 使用 pandas 提取表格
            df = max(pd.read_html(driver.page_source), key=len)
            # 只要前三欄：馬號/馬名、獨贏、位置 (視網頁結構調整)
            df = df.iloc[:, [1, 2, 3]] 
            df.columns = ['馬名', '獨贏', '位置']
            
            df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
            df.insert(1, 'Race_No', r)
            
            # 儲存 (Accumulate)
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            all_data.append(df)
            print(f"第 {r} 場: 抓取成功")
            time.sleep(1)
        except:
            print(f"第 {r} 場: 尚未開售或跳過")
            continue

    # --- 趨勢分析 HTML 製作 ---
    try:
        full_df = pd.read_csv(filename_csv)
        times = sorted(full_df['Capture_Time'].unique())
        
        if len(times) >= 2:
            latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
            prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
            
            for col in ['獨贏', '位置']:
                merged = latest.merge(prev[['Race_No', '馬名', col]], on=['Race_No', '馬名'], suffixes=('', '_old'), how='left')
                def calc_trend(row, c):
                    try:
                        curr, old = float(row[c]), float(row[c+'_old'])
                        if curr < old: return f"{curr} ↓" # 賠率下調 (變熱)
                        if curr > old: return f"{curr} ↑" # 賠率上升 (變冷)
                        return f"{curr}"
                    except: return row[c]
                latest[col] = merged.apply(lambda r: calc_trend(r, col), axis=1)
            display_df = latest
        else:
            display_df = full_df.tail(20)

        style = "<style>body{font-family:sans-serif;background:#f4f4f4;padding:20px;}table{border-collapse:collapse;width:100%;background:#fff;}td,th{border:1px solid #ddd;padding:10px;text-align:center;}th{background:#333;color:white;}.down{color:#e74c3c;font-weight:bold;}.up{color:#2ecc71;}</style>"
        table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
        
        with open(filename_html, 'w', encoding='utf-8-sig') as f:
            f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><a href='../index.html'>← 返回索引</a><h2>{target_date} {venue} 賠率變動分析</h2><p>比較時間: {times[-2] if len(times)>1 else 'N/A'} ➔ {times[-1]}</p>{table_html}</body></html>")
    except Exception as e:
        print(f"分析失敗: {e}")

    update_index(hkt_now)
    driver.quit()

if __name__ == "__main__":
    scrape()
