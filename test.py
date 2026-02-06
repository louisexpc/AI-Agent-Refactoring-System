import requests

# 設定 API 端點網址
url = "http://localhost:9000/ingestion/runs"

# 設定要傳送的資料 (Payload)
data = {
    "repo_url": "https://github.com/Careerhack-2026-TSID/xml_parser",
    "start_prompt": "Start processing",
    "options": {},
    "save_path": "/workspace/init",
}

try:
    # 發送 POST 請求
    # 使用 json= 參數會自動將字典轉換為 JSON 字串，並加上正確的 Header
    response = requests.post(url, json=data)

    # 檢查請求是否成功 (狀態碼為 2xx)
    response.raise_for_status()

    # 輸出回傳結果
    print("狀態碼:", response.status_code)
    print("回傳內容:", response.json())

except requests.exceptions.RequestException as e:
    print(f"發送請求時發生錯誤: {e}")


# run_id = "7aeacda3153749249ae6493e38bef115"
# url = f"http://localhost:9000/ingestion/runs/{run_id}/depgraph/python/reverse"
# output_file = "dep_reverse_index.json"

# try:
#     # 發送 GET 請求，並開啟串流模式以利儲存檔案
#     response = requests.get(url, stream=True)

#     # 檢查 HTTP 狀態碼
#     response.raise_for_status()

#     # 將內容寫入檔案 (對應 curl 的 -o 參數)
#     with open(output_file, "wb") as f:
#         for chunk in response.iter_content(chunk_size=8192):
#             f.write(chunk)

#     print(f"檔案已成功儲存至: {output_file}")

# except requests.exceptions.RequestException as e:
#     print(f"請求失敗: {e}")
