import pandas as pd
import time
import os
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

def get_first_race_time(driver, date_str, venue):
    """
    爬取第一場的開賽時間並轉為 datetime 物件
    """
    try:
        # 前往排位表頁面
        url = f"https://hkjc.com{date_str}&Venue={venue}"
        driver.get(url)
        # 這裡根據馬會結構抓取時間，簡單的做法是抓取頁面上的時間文字
        # 注意：若當天無賽事，此處會噴錯進入 except
        time_element = driver.find_element(By.XPATH, "//span[contains(text(), '開跑時間')]//following::td[1]")
        race_time_str = time_element.text.strip() # 格式通常為 "13:00"
        
        full_time_str = f"{date_str} {race_time_str}"
        return datetime.strptime(full_time_str, "%Y-%m-%d %H:%M")
    except:
        return None

def scrape():
    driver = get_driver()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    capture_time = now.strftime("%Y-%m-%d %H:%M")
    
    print(f"🚀 啟動檢查: {capture_time}")

    # --- 關鍵邏輯：開賽時間判斷 ---
    # 我們檢查 ST 或 HV 隨便一個，只要有比賽就判斷
    first_race_dt = None
    for v in ['ST', 'HV']:
        first_race_dt = get_first_race_time(driver, today_str, v)
        if first_race_dt: break

    if first_race_dt:
        # 計算距離開賽還有多久
        time_diff = (first_race_dt - now).total_seconds() / 60
        print(f"🕒 今日第一場開賽時間: {first_race_dt.strftime('%H:%M')}")
        print(f"⏳ 距離開賽還有: {int(time_diff)} 分鐘")

        if time_diff < 115: # 1小時55分鐘 = 115分鐘
            print("🛑 距離開賽不足 1 小時 55 分鐘，停止本次自動抓取。")
            driver.quit()
            return
    else:
        print("ℹ️ 無法取得今日賽事時間，可能是非賽馬日或網頁尚未更新。")

    # --- 原有的爬蟲邏輯 ---
    if not os.path.exists('data'):
        os.makedirs('data')

    venues = ['HV', 'ST']
    total_found = 0

    for venue in venues:
        for race_num in range(1, 12):
            url = f"https://hkjc.com{today_str}&venue={venue}&raceno={race_num}"
            try:
                driver.get(url)
                wait = WebDriverWait(driver, 8)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
                
                dfs = pd.read_html(driver.page_source)
                qpl_df = max(dfs, key=len)
                qpl_df.insert(0, 'Capture_Time', capture_time)
                
                filename = f"data/all_odds_{today_str}_{venue}_R{race_num}.csv"
                file_exists = os.path.isfile(filename)
                qpl_df.to_csv(filename, mode='a', index=False, header=not file_exists, encoding="utf-8-sig")
                print(f"  ✅ 成功抓取: {venue} R{race_num}")
                total_found += 1
            except:
                continue

    print(f"🏁 抓取結束。更新檔案數: {total_found}")
    driver.quit()

if __name__ == "__main__":
    scrape()
