import requests
import json

def test_hkjc_connection():
    # 1. 設定測試參數
    # 注意：如果 4/29 沒有賽事，請手動改為最近的一個賽馬日進行測試
    target_date = "2026-04-29"
    url = "https://hkjc.com"
    
    test_params = {
        "type": "winplaodds",
        "date": target_date,
        "venue": "ST",
        "start": "1",
        "end": "1"  # 測試只抓第 1 場，速度較快
    }
    
    test_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Referer': 'https://hkjc.com'
    }

    print(f"🔍 正在測試連線至馬會接口... 日期: {target_date}")
    
    try:
        # 2. 發送請求
        response = requests.get(url, params=test_params, headers=test_headers, timeout=10)
        
        # 3. 檢查 HTTP 狀態
        print(f"🌐 HTTP 狀態碼: {response.status_code}")
        
        if response.status_code == 200:
            # 4. 嘗試解析 JSON
            try:
                data = response.json()
                print("✅ 成功獲取 JSON 數據！")
                
                # 印出部分數據結構供參考
                if 'out' in data:
                    print(f"📊 偵測到 {len(data['out'])} 場賽事數據")
                    # 顯示第一隻馬的賠率範例
                    if len(data['out']) > 0 and 'win' in data['out'][0]:
                        sample_horse = data['out'][0]['win'][0]
                        print(f"🐎 數據範例 -> 馬號: {sample_horse.get('no')}, 賠率: {sample_horse.get('odds')}")
                else:
                    print("⚠️ 連線成功但無數據 (可能是非賽馬日或數據尚未公佈)")
                    print(f"原始回傳內容: {response.text[:100]}...") 
                    
            except json.JSONDecodeError:
                print("❌ 無法解析 JSON。馬會可能回傳了 HTML 錯誤頁面（可能被封鎖 IP）。")
                print(f"內容節錄: {response.text[:200]}")
        else:
            print(f"❌ 伺服器拒絕請求，請檢查是否被防火牆攔截。")

    except Exception as e:
        print(f"💥 發生錯誤: {e}")

if __name__ == "__main__":
    test_hkjc_connection()
