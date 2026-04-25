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

def get_race_info(driver, date_str):
    """檢測日期是否有賽事：只要網頁能加載出賽事標記即視為成功"""
    for v in ["ST", "HV"]:
        url = f"https://hkjc.com{date_str}/{v}/1"
        try:
            driver.get(url)
            time.sleep(5) # 投注版加載極慢，給予充足時間
            
            # 判斷方式：如果標題包含 '獨贏' 或 'WP'，或頁面出現 '場次' 字樣，即視為有賽事
            page_source = driver.page_source
            if "獨贏" in page_source or "wpTable" in page_source:
                print(f"✅ 檢測成功: {date_str} [{v}] 有數據可抓取")
                return True, v
        except:
            continue
    return False, None

def update_index(now_hkt):
    if not os.path.exists('data'): os.makedirs('data')
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    html = f"<html><head><meta charset='UTF-8'><title>HKJC Index</title></head><body><h1>🏇 數據索引</h1><p>更新: {now_hkt.strftime('%Y-%m-%d %H:%M')}</p><ul>{links}</ul></body></html>"
    with open('index.html', 'w', encoding='utf-8-sig') as f: f.write(html)

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    today = hkt_now.strftime("%Y-%m-%d")
    tomorrow = (hkt_now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    driver = get_driver()
    target_date, venue = None, None

    print(f"🚀 啟動檢查 (HKT {hkt_now.strftime('%H:%M')})...")

    # 邏輯 A：如果是下午 12 點後，優先找明天的資料
    if hkt_now.hour >= 12:
        print(f"🔍 正在檢查明天 ({tomorrow}) 是否開售...")
        found, v = get_race_info(driver, tomorrow)
        if found:
            target_date, venue = tomorrow, v

    # 邏輯 B：如果明天沒比賽，或者現在是比賽當天
    if not target_date:
        print(f"🔍 正在檢查今天 ({today}) 是否有賽事...")
        found, v = get_race_info(driver, today)
        if found:
            target_date, venue = today, v

    if not target_date:
        print("ℹ️ 檢測失敗：目前非賽事前夕或賽事當天。")
        update_index(hkt_now)
        driver.quit()
        return

    # --- 執行抓取 ---
    print(f"🔥 開始抓取 {target_date} {venue} 的賠率...")
    if not os.path.exists('data'): os.makedirs('data')
    filename_csv = f"data/all_odds_{target_date}_{venue}.csv"
    filename_html = f"data/all_odds_{target_date}_{venue}.html"

    for r in range(1, 13):
        try:
            driver.get(f"https://hkjc.com{target_date}/{venue}/{r}")
            # 等待核心賠率表出現
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "wpTable")))
            
            # 使用 Pandas 提取
            dfs = pd.read_html(driver.page_source)
            df = max(dfs, key=len)
            
            # 欄位通常為：馬號, 馬名, 獨贏, 位置, ...
            # 我們強制取前幾欄並重新命名以防變動
            df = df.iloc[:, [1, 2, 3]] # 取 馬名, 獨贏, 位置
            df.columns = ['馬名', '獨贏', '位置']
            
            df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
            df.insert(1, 'Race_No', r)
            
            # 累加存檔 (Accumulate)
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"R{r} OK")
            time.sleep(2)
        except:
            continue

    # --- 生成變動分析 ---
    try:
        full_df = pd.read_csv(filename_csv)
        times = sorted(full_df['Capture_Time'].unique())
        if len(times) >= 2:
            latest = full_df[full_df['Capture_Time'] == times[-1]].copy()
            prev = full_df[full_df['Capture_Time'] == times[-2]].copy()
            
            for col in ['獨贏', '位置']:
                merged = latest.merge(prev[['Race_No', '馬名', col]], on=['Race_No', '馬名'], suffixes=('', '_old'), how='left')
                def get_trend(row, c):
                    try:
                        curr, old = float(row[c]), float(row[c+'_old'])
                        if curr < old: return f"{curr} ↓"
                        if curr > old: return f"{curr} ↑"
                        return str(curr)
                    except: return str(row[c])
                latest[col] = merged.apply(lambda r: get_trend(r, col), axis=1)
            display_df = latest
        else:
            display_df = full_df.tail(20)

        style = "<style>body{font-family:sans-serif;}table{border-collapse:collapse;width:100%;}td,th{border:1px solid #ccc;padding:8px;text-align:center;}.down{color:red;font-weight:bold;}.up{color:green;}</style>"
        table_html = display_df.to_html(index=False).replace("↓", "<span class='down'>↓</span>").replace("↑", "<span class='up'>↑</span>")
        with open(filename_html, 'w', encoding='utf-8-sig') as f:
            f.write(f"<html><head><meta charset='UTF-8'>{style}</head><body><a href='../index.html'>返回</a><h2>{target_date} {venue} 賠率分析</h2>{table_html}</body></html>")
    except:
        pass

    update_index(hkt_now)
    driver.quit()

if __name__ == "__main__":
    scrape()
