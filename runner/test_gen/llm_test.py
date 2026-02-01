import os
from pathlib import Path

import google.auth
import vertexai
from vertexai.generative_models import GenerativeModel

print("--- GCP Environment Diagnostic ---")

# 1. 自動偵測並設定 Key File (針對你的環境)
known_key_path = Path(
    "/home/yoyo/projects/TSMC-2026-Hackathon/hackathon-485006-fc9be8263cae.json"
)
env_key_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

if env_key_path:
    print(f"✅ GOOGLE_APPLICATION_CREDENTIALS is set to: {env_key_path}")
    if not os.path.exists(env_key_path):
        print(f"❌ Error: The file at {env_key_path} does not exist!")
elif known_key_path.exists():
    print(f"⚠️  Env var not set, but found key file at: {known_key_path}")
    print("   -> Automatically setting environment variable for this run.")
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(known_key_path)
else:
    print("❌ Error: GOOGLE_APPLICATION_CREDENTIALS not set and key file not found.")

print("\nAttempting to authenticate and call Vertex AI...")

try:
    # 2. 取得憑證資訊 (驗證是否能讀取 JSON)
    credentials, project_id = google.auth.default()
    print(f"✅ Authenticated with Project ID: {project_id}")

    # 3. 初始化 Vertex AI
    location = os.environ.get("GCP_REGION", "us-central1")
    print(f"ℹ️  Using Region: {location}")

    vertexai.init(project=project_id, location=location, credentials=credentials)

    # 4. 呼叫模型
    model_name = "gemini-2.5-pro"
    print(f"   -> Loading model '{model_name}'...")
    model = GenerativeModel(model_name)

    print("   -> Sending test prompt...")
    response = model.generate_content("Hello, are you working?")

    print("\n🎉 Success! Model Response:")
    print(response.text.strip())

except Exception as e:
    print(f"\n❌ An error occurred: {e}")
    print("\nPlease check the following:")
    print(
        "1. If the error is '403 PermissionDenied', "
        "ensure the Service Account has 'Vertex AI User' role."
    )
    print(
        "2. If the error is 'API not enabled', run: "
        "gcloud services enable aiplatform.googleapis.com"
    )
    print(
        "3. If the error is '404 Not Found', check if the model "
        "name is correct and available in the region."
    )
