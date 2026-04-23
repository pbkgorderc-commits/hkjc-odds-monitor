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
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def scrape():
    driver = get_driver()
    today = datetime.now().strftime("%Y-%m-%d")
    capture_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # 建立資料夾存放數據
    if not os.path.exists('data'):
        os.makedirs('data')

    venues = ['HV', 'ST']
    found_any = False

    for venue in venues:
        for race_num in range(1, 12):
            url = f"https://hkjc.com{today}/{venue}/{race_num}"
            try:
                driver.get(url)
                # 等待賠率表格，縮短等待時間以利快速掃描
                wait = WebDriverWait(driver, 7)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
                
                dfs = pd.read_html(driver.page_source)
                qpl_df = max(dfs, key=len)
                
                # 合併邏輯：加入時間戳記列
                qpl_df.insert(0, 'Capture_Time', capture_time)
                
                # 檔名：每一場比賽一個合併表
                filename = f"data/all_odds_{today}_{venue}_R{race_num}.csv"
                file_exists = os.path.isfile(filename)
                
                # 寫入 (Append 模式)
                qpl_df.to_csv(filename, mode='a', index=False, header=not file_exists, encoding="utf-8-sig")
                print(f"Match found: {venue} R{race_num} appended.")
                found_any = True
            except:
                continue # 找不到該場次就跳過
        if found_any: break 

    driver.quit()

if __name__ == "__main__":
    scrape()
