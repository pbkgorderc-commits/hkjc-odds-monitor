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
    # 必須加入 User-Agent
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

def get_race_info(driver, date_str):
    try:
        # 使用投注版網址格式
        url = f"https://hkjc.com{date_str}/ST/1"
        driver.get(url)
        
        # 等待時間欄位出現 (投注版的時間通常在 .startTime)
        xpath = "//div[contains(@class, 'raceNo')]//span[contains(@class, 'startTime')]"
        element = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, xpath)))
        
        time_text = element.text.replace("開跑時間 : ", "").strip()
        hkt_race = datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %H:%M")
        return hkt_race - timedelta(hours=8) # 回傳 UTC
    except:
        # 如果 ST 沒比賽，嘗試 HV
        try:
            url = f"https://hkjc.com{date_str}/HV/1"
            driver.get(url)
            element = WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.XPATH, "//span[contains(@class, 'startTime')]")))
            time_text = element.text.replace("開跑時間 : ", "").strip()
            hkt_race = datetime.strptime(f"{date_str} {time_text}", "%Y-%m-%d %H:%M")
            return hkt_race - timedelta(hours=8)
        except:
            return None

def scrape():
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    hkt_now = now_utc + timedelta(hours=8)
    today, tomorrow = hkt_now.strftime("%Y-%m-%d"), (hkt_now + timedelta(days=1)).strftime("%Y-%m-%d")
    
    driver = get_driver()
    target_date = None

    # 檢查明天或今天
    tomorrow_race_utc = get_race_info(driver, tomorrow)
    if tomorrow_race_utc: 
        target_date = tomorrow
    else:
        today_race_utc = get_race_info(driver, today)
        if today_race_utc and now_utc < (today_race_utc - timedelta(hours=-3)): # 賽後3小時內仍可抓
            target_date = today

    if not target_date:
        print("ℹ️ 當前不在抓取時段（無賽事或已過時）")
        driver.quit()
        return

    # 偵測當前場地 (從 URL 判斷)
    venue = "HV" if "/HV/" in driver.current_url else "ST"
    
    if not os.path.exists('data'): os.makedirs('data')
    filename_csv = f"data/all_odds_{target_date}_{venue}.csv"
    filename_html = f"data/all_odds_{target_date}_{venue}.html"

    for r in range(1, 13):
        try:
            driver.get(f"https://hkjc.com{target_date}/{venue}/{r}")
            # 等待賠率表格載入
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "wpTable")))
            
            # 投注版 Table 讀取
            dfs = pd.read_html(driver.page_source)
            df = max(dfs, key=len)
            
            df.insert(0, 'Capture_Time', hkt_now.strftime("%Y-%m-%d %H:%M"))
            df.insert(1, 'Race_No', r)
            df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
            print(f"R{r} OK")
            time.sleep(2) # 避免過快被封
        except Exception as e:
            print(f"R{r} Skip: {e}")
            continue

    # ... (後續趨勢分析與 update_index 邏輯保持不變) ...
