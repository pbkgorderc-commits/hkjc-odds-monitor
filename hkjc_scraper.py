import pandas as pd
import os
import time
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

def run_test():
    # --- [設定測試目標] ---
    test_date = "2026-04-26"  # 修改為你想測試的日期
    url_date = test_date.replace("-", "/")
    driver = get_driver()
    
    if not os.path.exists('data'): os.makedirs('data')
    filename_csv = f"data/test_odds_{test_date}.csv"
    filename_html = f"data/test_odds_{test_date}.html"

    print(f"🚀 開始測試即時抓取: {test_date}")

    results = []
    # 測試抓取前 3 場即可 (節省時間)
    for r in range(1, 4):
        url = f"https://hkjc.com{url_date}&RaceNo={r}"
        try:
            print(f"🔍 正在訪問 R{r}: {url}")
            driver.get(url)
            
            # 等待表格出現
            WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "table_bd")))
            
            # 讀取表格
            dfs = pd.read_html(driver.page_source)
            # 尋找包含「馬名」的表格
            target_df = None
            for d in dfs:
                if '馬名' in str(d.values):
                    target_df = d
                    break
            
            if target_df is not None:
                # 簡單清洗：假設前三欄為 馬號, 馬名, 獨贏
                target_df = target_df.iloc[:, [0, 2, 3]] 
                target_df.columns = ['馬號', '馬名', '獨贏']
                target_df.insert(0, 'Race_No', r)
                target_df.insert(0, 'Capture_Time', time.strftime("%H:%M:%S"))
                
                # 儲存
                target_df.to_csv(filename_csv, mode='a', index=False, header=not os.path.exists(filename_csv), encoding="utf-8-sig")
                results.append(target_df)
                print(f"✅ R{r} 成功抓取 {len(target_df)} 匹馬")
            else:
                print(f"❌ R{r} 找不到賠率表格")
                
        except Exception as e:
            print(f"💥 R{r} 錯誤: {str(e)[:100]}")
            driver.save_screenshot(f"error_R{r}.png")

    # 生成簡單 HTML
    if results:
        final_df = pd.concat(results)
        final_df.to_html(filename_html, index=False)
        print(f"✨ 測試完成！輸出已儲存至 {filename_csv} 及 {filename_html}")
    
    driver.quit()

if __name__ == "__main__":
    run_test()
