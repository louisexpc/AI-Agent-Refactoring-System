# curl -X POST http://localhost:8000/ingestion/runs \
#   -H "Content-Type: application/json" \
#   -d '{
#     "repo_url": "https://github.com/emilybache/Racing-Car-Katas",
#     "start_prompt": "Start processing",
#     "options": {},
#     "save_path": "/workspace/car"
#   }'

# curl -X POST http://localhost:8000/ingestion/runs \
#   -H "Content-Type: application/json" \
#   -d '{
#     "repo_url": "https://github.com/louisexpc/ICU_AF_Prediction",
#     "start_prompt": "Start processing",
#     "options": {},
#     "save_path": "/workspace/icu"
#   }'


# curl -X GET http://localhost:8000/ingestion/runs/b7c1e89483f546fbbbabd42766119358/status
# echo "Car Katas Repo Test"
# curl -X GET http://localhost:8000/ingestion/runs/baba5ca084b8413f93e9c76f2cd697a3

# echo "\nICU Prediction Repo Test"
# curl -X GET http://localhost:8000/ingestion/runs/5e6540160d4b413a975085bf1625ae2a
# echo "Fetch file"
# curl get http://localhost:8000/ingestion/runs/5e6540160d4b413a975085bf1625ae2a/artifacts/dep_graph_light
curl -X GET http://localhost:8000/ingestion/runs/5e6540160d4b413a975085bf1625ae2a/depgraph/python/reverse -o dep_reverse_index.json
