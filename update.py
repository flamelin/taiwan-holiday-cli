#!/usr/bin/env python3
"""從 data.gov.tw 下載今年與明年的「中華民國政府行政機關辦公日曆表」JSON 到 data/。

資料來源：https://data.gov.tw/dataset/14718
"""

import hashlib
import json
import ssl
import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

DATASET_ID = 14718
DATASET_API = f"https://data.gov.tw/api/v2/rest/dataset/{DATASET_ID}"
# 「檢視資料」的 JSON 下載端點，md5_url 為原始資源下載網址的 MD5
JSON_API = "https://quality.data.gov.tw/dq_download_json.php"
DATA_DIR = Path(__file__).resolve().parent / "data"
USER_AGENT = "Mozilla/5.0 (taiwan-holiday-cli)"

# quality.data.gov.tw 憑證缺少 Subject Key Identifier，Python 3.13+ 預設的 X509 嚴格模式會拒絕；
# 僅關閉嚴格模式，仍保留一般憑證鏈驗證。
SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30, context=SSL_CONTEXT) as resp:
        return resp.read()


def find_resources() -> dict[str, str]:
    """回傳 {資源名稱: 原始下載網址}。"""
    meta = json.loads(fetch(DATASET_API))
    return {
        r["resourceDescription"]: r["resourceDownloadUrl"]
        for r in meta["result"]["distribution"]
    }


def json_url(download_url: str) -> str:
    md5 = hashlib.md5(download_url.encode()).hexdigest()
    return f"{JSON_API}?{urllib.parse.urlencode({'nid': DATASET_ID, 'md5_url': md5})}"


def main() -> int:
    DATA_DIR.mkdir(exist_ok=True)
    resources = find_resources()
    this_year = date.today().year
    failed = False

    for year in (this_year, this_year + 1):
        name = f"{year - 1911}年中華民國政府行政機關辦公日曆表"
        download_url = resources.get(name)
        if not download_url:
            print(f"略過 {year}：尚未發布「{name}」")
            continue

        try:
            days = json.loads(fetch(json_url(download_url)))
        except Exception as e:  # noqa: BLE001
            print(f"失敗 {year}：{e}", file=sys.stderr)
            failed = True
            continue

        if not isinstance(days, list) or not days or not str(days[0].get("西元日期", "")).startswith(str(year)):
            print(f"失敗 {year}：資料內容與年份不符", file=sys.stderr)
            failed = True
            continue

        out = DATA_DIR / f"{year}.json"
        out.write_text(json.dumps(days, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"已更新 {out.relative_to(DATA_DIR.parent)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
