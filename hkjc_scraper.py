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

def get_driver():
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_race_info(driver, date_str):
    try:
        url = f"https://hkjc.com{date_str}"
        driver.get(url)
        time_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//td[contains(text(), '開跑時間')]//following-sibling::td"))
        )
        race_time_str = time_element.text.replace(" ", "").strip()
        return datetime.strptime(f"{date_str} {race_time_str}", "%Y-%m-%d %H:%M")
    except:
        return None

def scrape():
    driver = get_driver()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"🚀 啟動時間: {now.strftime('%Y-%m-%d %H:%M')}")

    target_date = None
    today_race_time = get_race_info(driver, today_str)
    if today_race_time:
        diff = (today_race_time - now).total_seconds() / 60
        if diff > 90:
            print(f"✅ [情境 B] 今日有賽事 ({today_str})，開始抓取。")
            target_date = today_str
        else:
            print(f"🛑 [情境 B] 距離開賽不足 90 分鐘，停止更新。")
            driver.quit()
            return

    if not target_date:
        tomorrow_race_time = get_race_info(driver, tomorrow_str)
        if tomorrow_race_time:
            if now.hour > 12 or (now.hour == 12 and now.minute >= 30):
                print(f"✅ [情境 A] 明日有賽事 ({tomorrow_str})，執行抓取。")
                target_date = tomorrow_str
            else:
                print(f"⏳ [情境 A] 尚未到受注時間 (12:30 PM)，跳過。")

    if not target_date:
        print("ℹ️ [情境 C] 目前無賽事需抓取。")
        driver.quit()
        return

    # --- 執行數據抓取與清理邏輯 ---
    if not os.path.exists('data'): os.makedirs('data')
    
    # 清理 30 天前的舊檔
    print("🧹 檢查過期檔案...")
    retention_days = 30
    curr_time = time.time()
    for f in os.listdir('data'):
        f_path = os.path.join('data', f)
        if os.path.isfile(f_path) and "all_odds" in f:
            if (curr_time - os.path.getmtime(f_path)) / (24 * 3600) > retention_days:
                os.remove(f_path)
                print(f"   🗑️ 已刪除: {f}")

    venues = ['ST', 'HV']
    capture_time = now.strftime("%Y-%m-%d %H:%M")
    total_count = 0

    for venue in venues:
        filename = f"data/all_odds_{target_date}_{venue}.csv"
        for race_num in range(1, 13):
            url = f"https://hkjc.com{target_date}&venue={venue}&raceno={race_num}"
            try:
                driver.get(url)
                WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
                dfs = pd.read_html(driver.page_source)
                df = max(dfs, key=len)
                df.insert(0, 'Capture_Time', capture_time)
                df.insert(1, 'Race_No', race_num)
                df.to_csv(filename, mode='a', index=False, header=not os.path.exists(filename), encoding="utf-8-sig")
                print(f"   ∟ {venue} R{race_num} OK")
                total_count += 1
            except:
                continue

    print(f"🏁 任務完成。更新場次: {total_count}")
    driver.quit()

if __name__ == "__main__":
    scrape()
