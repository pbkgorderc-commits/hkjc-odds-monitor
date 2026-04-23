import pandas as pd
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

def get_race_info(driver, date_str):
    """檢查特定日期是否有賽事，並回傳第一場開賽時間"""
    try:
        # 使用排位表頁面來確認賽事
        url = f"https://hkjc.com{date_str}"
        driver.get(url)
        # 等待開跑時間欄位出現
        time_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//td[contains(text(), '開跑時間')]//following-sibling::td"))
        )
        race_time_str = time_element.text.replace(" ", "").strip() # 格式 "13:00"
        return datetime.strptime(f"{date_str} {race_time_str}", "%Y-%m-%d %H:%M")
    except:
        return None

def scrape():
    driver = get_driver()
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    print(f"🚀 當前時間: {now.strftime('%Y-%m-%d %H:%M')}")

    target_date = None
    
    # 【情境 B】檢查今日是否有賽事
    today_race_time = get_race_info(driver, today_str)
    if today_race_time:
        diff = (today_race_time - now).total_seconds() / 60
        if diff > 90:
            print(f"✅ [情境 B] 今日有賽事 ({today_str})，距離開賽還有 {int(diff)} 分鐘，執行抓取。")
            target_date = today_str
        else:
            print(f"🛑 [情境 B] 今日有賽事但距離開賽僅 {int(diff)} 分鐘 (不足90分鐘)，停止更新。")
            driver.quit()
            return

    # 【情境 A】若今日無效，檢查明日是否有賽事
    if not target_date:
        tomorrow_race_time = get_race_info(driver, tomorrow_str)
        if tomorrow_race_time:
            if now.hour > 12 or (now.hour == 12 and now.minute >= 30):
                print(f"✅ [情境 A] 明日有賽事 ({tomorrow_str})，且已過前日 12:30 PM，執行抓取。")
                target_date = tomorrow_str
            else:
                print(f"⏳ [情境 A] 明日有賽事，但尚未到受注時間 (12:30 PM)，跳過。")

    # 【情境 C】
    if not target_date:
        print("ℹ️ [情境 C] 目前無賽事需抓取，或未到受注時段。")
        driver.quit()
        return

    # --- 數據抓取主邏輯 ---
    if not os.path.exists('data'): os.makedirs('data')
    venues = ['ST', 'HV']
    capture_time = now.strftime("%Y-%m-%d %H:%M")
    total_files = 0

    for venue in venues:
        for race_num in range(1, 13):
            url = f"https://hkjc.com{target_date}&venue={venue}&raceno={race_num}"
            try:
                driver.get(url)
                # 等待賠率表載入
                WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
                dfs = pd.read_html(driver.page_source)
                df = max(dfs, key=len)
                df.insert(0, 'Capture_Time', capture_time)
                
                filename = f"data/all_odds_{target_date}_{venue}_R{race_num}.csv"
                df.to_csv(filename, mode='a', index=False, header=not os.path.exists(filename), encoding="utf-8-sig")
                print(f"   ∟ {venue} R{race_num} 資料已更新")
                total_files += 1
            except:
                continue

    print(f"🏁 任務完成。更新了 {total_files} 個場次的數據。")
    driver.quit()

if __name__ == "__main__":
    scrape()
