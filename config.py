"""
發票自動申報助手 - 配置文件
"""
import os
from pathlib import Path

# 專案根目錄
BASE_DIR = Path(__file__).parent.absolute()

# 上傳目錄
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# 允許的文件類型
ALLOWED_EXTENSIONS = {".pdf"}

# 財政部電子發票整合服務平台網址
# 注意：實際使用時請確認最新的官方網址
MOF_INVOICE_URL = "https://www.einvoice.nat.gov.tw/"

# Chrome 瀏覽器設定
CHROME_OPTIONS = {
    "headless": False,  # 設為 True 可隱藏瀏覽器視窗
    "window_size": (1920, 1080),
    "implicit_wait": 10,  # 隱式等待時間（秒）
    "page_load_timeout": 30,  # 頁面載入超時時間（秒）
}

# 發票欄位對應（可根據實際需求調整）
INVOICE_FIELDS = {
    "invoice_number": "發票號碼",
    "invoice_date": "發票日期",
    "seller_id": "賣方統一編號",
    "seller_name": "賣方名稱",
    "buyer_id": "買方統一編號",
    "buyer_name": "買方名稱",
    "items": "品項明細",
    "amount": "金額",
    "tax": "稅額",
    "total": "總計",
}

# 發票類型
INVOICE_TYPES = {
    "B2B": "營業人對營業人",
    "B2C": "營業人對消費者",
}
