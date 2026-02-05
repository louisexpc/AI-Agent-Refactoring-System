curl -X POST http://localhost:8000/ingestion/runs \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/louisexpc/TSMC-2026-Hackathon",
    "start_prompt": "Start processing",
    "options": {},
    "save_path": "/workspace/round1"
  }'
