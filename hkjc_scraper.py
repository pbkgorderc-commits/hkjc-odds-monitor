import pandas as pd
import os
import time
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 強制初始化時區設定（針對 Linux 環境）
os.environ['TZ'] = 'Asia/Hong_Kong'
if hasattr(time, 'tzset'):
    time.tzset()

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_race_info(driver, date_str):
    try:
        # 修正 URL 拼接，加入馬會賠率頁面的路徑
        url = f"https://hkjc.com{date_str}"
        driver.get(url)
        time_element = WebDriverWait(driver, 8).until(
            EC.presence_of_element_located((By.XPATH, "//td[contains(text(), '開跑時間')]//following-sibling::td"))
        )
        race_time_str = time_element.text.replace(" ", "").strip()
        return datetime.strptime(f"{date_str} {race_time_str}", "%Y-%m-%d %H:%M")
    except:
        return None

def update_index_page():
    if not os.path.exists('data'): return
    
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    links_html = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    
    index_content = f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: -apple-system, sans-serif; margin: 40px; line-height: 1.6; background-color: #f4f4f9; color: #333; }}
            h1 {{ color: #004d99; border-bottom: 2px solid #004d99; padding-bottom: 10px; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ background: white; margin: 10px 0; padding: 15px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
            a {{ text-decoration: none; color: #004d99; font-weight: bold; display: block; }}
            a:hover {{ color: #ff6600; }}
            .time {{ font-size: 0.9em; color: #666; }}
        </style>
    </head>
    <body>
        <h1>🏇 HKJC 賠率數據索引</h1>
        <p class="time">最後更新 (HKT): {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <ul>{links_html}</ul>
    </body>
    </html>
    """
    with open('index.html', 'w', encoding='utf-8-sig') as f:
        f.write(index_content)

def scrape():
    driver = get_driver()
    now = datetime.now() # 此時已受 TZ 影響為香港時間
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"🚀 啟動紀錄 (HKT): {now.strftime('%Y-%m-%d %H:%M:%S')}")

    target_date = None
    # 邏輯判斷：優先看今天是否有賽事
    today_race_time = get_race_info(driver, today_str)
    if today_race_time:
        diff = (today_race_time - now).total_seconds() / 60
        if diff > 60: # 開賽前 60 分鐘停止更新，避免抓到封盤數據
            print(f"✅ [情境 B] 抓取今日賽事 ({today_str})")
            target_date = today_str
        else:
            print(f"🛑 [情境 B] 接近開賽或已結束，停止今日抓取。")

    # 如果今天沒賽事，檢查明天
    if not target_date:
        tomorrow_race_time = get_race_info(driver, tomorrow_str)
        if tomorrow_race_time:
            # 香港時間 12:30 PM 後才開始有明日賠率
            if now.hour > 12 or (now.hour == 12 and now.minute >= 30):
                print(f"✅ [情境 A] 抓取明日賽事 ({tomorrow_str})")
                target_date = tomorrow_str
            else:
                print(f"⏳ [情境 A] 未到 12:30 PM 受注時間。")

    if not target_date:
        print("ℹ️ [情境 C] 測試模式：生成一個虛擬檔案。")
        if not os.path.exists('data'): os.makedirs('data')
        with open('data/test_file.html', 'w') as f:
        f.write("<h1>這是測試檔案</h1>")
        update_index_page()
        driver.quit()
        return
    

    if not os.path.exists('data'): os.makedirs('data')
    
    # 清理舊檔 (30天)
    retention_days = 30
    for f in os.listdir('data'):
        f_path = os.path.join('data', f)
        if os.path.isfile(f_path) and (time.time() - os.path.getmtime(f_path)) / 86400 > retention_days:
            os.remove(f_path)
            print(f"🗑️ 刪除舊檔: {f}")

    venues = ['ST', 'HV']
    capture_time = now.strftime("%Y-%m-%d %H:%M")
    
    for venue in venues:
        filename_csv = f"data/all_odds_{target_date}_{venue}.csv"
        filename_html = f"data/all_odds_{target_date}_{venue}.html"
        venue_updated = False

        for race_num in range(1, 13):
            url = f"https://hkjc.com{target_date}&venue={venue}&raceno={race_num}"
            try:
                driver.get(url)
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
                dfs = pd.read_html(driver.page_source)
                df = max(dfs, key=len)
                df.insert(0, 'Capture_Time', capture_time)
                df.insert(1, 'Race_No', race_num)
                df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
                venue_updated = True
                print(f"   ∟ {venue} R{race_num} OK")
            except:
                continue

        if venue_updated:
            full_df = pd.read_csv(filename_csv).tail(100) # 僅顯示最近期數據
            style = "<style>body{font-family:sans-serif;margin:20px;}table{border-collapse:collapse;width:100%;}th{background:#004d99;color:white;padding:8px;}td{border:1px solid #ddd;padding:8px;text-align:center;}tr:nth-child(even){background:#f2f2f2;}</style>"
            html_content = f"<html><head><meta charset='UTF-8'>{style}</head><body><a href='../index.html'>⬅ 返回索引</a><h2>🏇 {target_date} {venue} 數據</h2>{full_df.to_html(index=False)}</body></html>"
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(html_content)

    update_index_page()
    driver.quit()

if __name__ == "__main__":
    scrape()
