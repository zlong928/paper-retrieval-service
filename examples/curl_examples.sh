#!/usr/bin/env bash
# HTTP API 调用示例（需先启动服务: python -m paper_retrieval.main）
BASE="${PAPER_RETRIEVAL_URL:-http://127.0.0.1:8080}"
KEY="${API_KEY:-}"

auth=()
if [ -n "$KEY" ]; then auth=(-H "X-API-Key: $KEY"); fi

echo "== health =="
curl -s "$BASE/health" | python3 -m json.tool

echo ""
echo "== search =="
curl -s -X POST "$BASE/v1/search" "${auth[@]}" \
  -H "Content-Type: application/json" \
  -d '{"query":"aqueous two phase PEG","limit":3}' | python3 -m json.tool

echo ""
echo "== download pdf (first result doi) =="
DOI=$(curl -s -X POST "$BASE/v1/search" "${auth[@]}" \
  -H "Content-Type: application/json" \
  -d '{"query":"aqueous two phase PEG","limit":1}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['results'][0]['doi'])")

curl -s -X POST "$BASE/v1/download/pdf" "${auth[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"doi\":\"$DOI\"}" \
  -o "/tmp/${DOI//\//_}.pdf" -D /tmp/headers.txt

echo "Saved /tmp/${DOI//\//_}.pdf"
grep -i x-download-source /tmp/headers.txt || true
