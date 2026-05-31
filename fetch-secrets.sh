#!/usr/bin/env bash
# 從 AWS SSM Parameter Store 拉金鑰,生成 .env 給 docker-compose 用。
# 在 EC2 上執行,使用 instance role 的唯讀權限。請勿提交產生出來的 .env。
set -euo pipefail

PREFIX="/chargealert/prod"
REGION="ap-northeast-1"
OUT=".env"
TMP="$(mktemp)"

echo "# 由 fetch-secrets.sh 從 SSM ${PREFIX} 自動產生 — 請勿手動編輯或提交" > "$TMP"

aws ssm get-parameters-by-path \
  --region "$REGION" \
  --path "$PREFIX" \
  --with-decryption \
  --recursive \
  --query "Parameters[].[Name,Value]" \
  --output text \
| while IFS=$'\t' read -r name value; do
    printf '%s=%s\n' "${name##*/}" "$value" >> "$TMP"
  done

count=$(($(wc -l < "$TMP") - 1))
if [ "$count" -lt 1 ]; then
  echo "❌ 沒抓到任何參數,.env 未更新(檢查 IAM 權限 / region / 路徑)。"
  rm -f "$TMP"
  exit 1
fi

mv "$TMP" "$OUT"
chmod 600 "$OUT"
echo "✅ 已從 SSM 產生 $OUT,共 ${count} 筆參數。"
