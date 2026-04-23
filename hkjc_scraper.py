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

def update_index_page():
    """掃描 data 目錄並更新根目錄的 index.html"""
    if not os.path.exists('data'): return
    
    files = sorted([f for f in os.listdir('data') if f.endswith('.html')], reverse=True)
    
    links_html = "".join([f'<li><a href="data/{f}">{f.replace("all_odds_", "").replace(".html", "")}</a></li>' for f in files])
    
    index_content = f"""
    <html>
    <head>
        <meta charset='UTF-8'>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: sans-serif; margin: 40px; line-height: 1.6; background-color: #f4f4f9; }}
            h1 {{ color: #004d99; border-bottom: 2px solid #004d99; }}
            ul {{ list-style: none; padding: 0; }}
            li {{ background: white; margin: 10px 0; padding: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
            a {{ text-decoration: none; color: #004d99; font-weight: bold; font-size: 1.1em; display: block; }}
            a:hover {{ color: #ff6600; }}
        </style>
    </head>
    <body>
        <h1>🏇 HKJC 賠率數據索引</h1>
        <p>最後更新時間: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        <ul>{links_html}</ul>
    </body>
    </html>
    """
    with open('index.html', 'w', encoding='utf-8-sig') as f:
        f.write(index_content)
    print("🏠 索引頁 index.html 已更新")

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
            print(f"✅ [情境 B] 抓取今日賽事 ({today_str})")
            target_date = today_str
        else:
            print(f"🛑 [情境 B] 接近開賽，停止抓取。")
            driver.quit()
            return

    if not target_date:
        tomorrow_race_time = get_race_info(driver, tomorrow_str)
        if tomorrow_race_time:
            if now.hour > 12 or (now.hour == 12 and now.minute >= 30):
                print(f"✅ [情境 A] 抓取明日賽事 ({tomorrow_str})")
                target_date = tomorrow_str
            else:
                print(f"⏳ [情境 A] 未到 12:30 PM 受注時間。")

    if not target_date:
        print("ℹ️ [情境 C] 無賽事需處理。")
        update_index_page() # 即使不抓取也更新一下 index 以反映最新狀態
        driver.quit()
        return

    if not os.path.exists('data'): os.makedirs('data')
    
    # 清理 30 天前舊檔
    retention_days = 30
    curr_time = time.time()
    for f in os.listdir('data'):
        f_path = os.path.join('data', f)
        if os.path.isfile(f_path) and (curr_time - os.path.getmtime(f_path)) / (24 * 3600) > retention_days:
            os.remove(f_path)
            print(f"   🗑️ 已刪除: {f}")

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
                WebDriverWait(driver, 6).until(EC.presence_of_element_located((By.CLASS_NAME, "oddsTable")))
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
            full_df = pd.read_csv(filename_csv)
            style = """
            <style>
                body { font-family: sans-serif; margin: 20px; background: #f9f9f9; }
                table { border-collapse: collapse; width: 100%; background: white; }
                th { background: #004d99; color: white; padding: 10px; position: sticky; top: 0; }
                td { border: 1px solid #ddd; padding: 8px; text-align: center; }
                tr:nth-child(even) { background: #f2f2f2; }
                h2 { color: #004d99; }
                .back { display: inline-block; margin-bottom: 20px; text-decoration: none; color: #004d99; font-weight: bold; }
            </style>
            """
            back_link = '<a class="back" href="../index.html">⬅ 回到清單</a>'
            html_content = f"<html><head><meta charset='UTF-8'>{style}</head><body>{back_link}<h2>🏇 {target_date} ({venue}) 賠率表</h2>{full_df.to_html(index=False)}</body></html>"
            with open(filename_html, 'w', encoding='utf-8-sig') as f:
                f.write(html_content)

    update_index_page()
    driver.quit()

if __name__ == "__main__":
    scrape()
