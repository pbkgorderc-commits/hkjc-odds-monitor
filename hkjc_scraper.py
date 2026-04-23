import pandas as pd
import time
import os
from datetime import datetime
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
    # 加入偽裝 User-Agent，避免被馬會阻擋
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def scrape():
    driver = get_driver()
    # 這裡的 date 格式必須符合馬會 URL 的要求，例如 2025-05-21
    target_date = datetime.now().strftime("%Y-%m-%d")
    capture_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    print(f"🚀 Starting scrape for date: {target_date} at {capture_time}")

    if not os.path.exists('data'):
        os.makedirs('data')

    venues = ['HV', 'ST']
    total_found = 0

    for venue in venues:
        print(f"🔎 Checking venue: {venue}")
        for race_num in range(1, 12):
            # 修正後的馬會標準賠率網址格式 (以獨贏/位置為例)
            url = f"https://hkjc.com{target_date}&venue={venue}&raceno={race_num}"
            
            try:
                driver.get(url)
                # 增加等待時間到 10 秒，因為馬會網站有時載入較慢
                wait = WebDriverWait(driver, 10)
                # 確保表格載入
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
                
                dfs = pd.read_html(driver.page_source)
                if not dfs:
                    continue
                    
                qpl_df = max(dfs, key=len)
                qpl_df.insert(0, 'Capture_Time', capture_time)
                
                filename = f"data/all_odds_{target_date}_{venue}_R{race_num}.csv"
                file_exists = os.path.isfile(filename)
                
                qpl_df.to_csv(filename, mode='a', index=False, header=not file_exists, encoding="utf-8-sig")
                print(f"  ✅ [FOUND] {venue} Race {race_num} - Data appended.")
                total_found += 1
            except Exception as e:
                # 這裡可以 Print 簡單錯誤，幫助排除網址是否正確
                continue 

    print(f"🏁 Scrape finished. Total files updated: {total_found}")
    driver.quit()

if __name__ == "__main__":
    scrape()
