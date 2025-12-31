# 發票自動申報助手 (Invoice Filing Assistant)

自動解析發票 PDF 並協助填寫財政部電子發票平台的小助手。

## 功能特色

- 📄 **PDF 解析**：自動提取發票 PDF 中的文字和表格內容
- 🔍 **智能識別**：自動判別發票號碼、統一編號、金額、品項等資訊
- 🌐 **瀏覽器自動化**：透過 Chrome 瀏覽器自動填寫表單
- 💻 **雙介面支援**：提供命令列工具和 Web 圖形介面

## 系統需求

- Python 3.10+
- Google Chrome 瀏覽器
- 作業系統：Windows / macOS / Linux

## 安裝步驟

### 1. 複製專案

```bash
git clone <repository-url>
cd inVoiceAssistant
```

### 2. 建立虛擬環境（建議）

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. 安裝依賴套件

```bash
pip install -r requirements.txt
```

## 使用方式

### 命令列模式

#### 解析發票 PDF

```bash
python main.py --pdf invoice.pdf
```

#### 解析並輸出 JSON 格式

```bash
python main.py --pdf invoice.pdf --json
```

#### 解析並自動開啟瀏覽器填寫

```bash
python main.py --pdf invoice.pdf --auto
```

### Web 介面模式

```bash
python main.py --web
# 或
python web_app.py
```

然後在瀏覽器開啟 http://localhost:5000

## 專案結構

```
inVoiceAssistant/
├── main.py                 # 主程式入口
├── web_app.py             # Web 介面應用
├── config.py              # 配置文件
├── requirements.txt       # Python 依賴
├── README.md              # 說明文件
├── src/                   # 核心模組
│   ├── __init__.py
│   ├── pdf_parser.py      # PDF 解析模組
│   ├── invoice_extractor.py   # 發票識別模組
│   └── browser_automation.py  # 瀏覽器自動化模組
├── templates/             # Web 介面模板
│   └── index.html
└── uploads/               # 上傳文件暫存目錄
```

## 模組說明

### PDFParser（PDF 解析器）

負責讀取 PDF 文件並提取文字和表格內容。

```python
from src import PDFParser

parser = PDFParser()
content = parser.parse("invoice.pdf")
print(content.raw_text)
```

### InvoiceExtractor（發票識別器）

從 PDF 內容中智能識別發票欄位資訊。

```python
from src import InvoiceExtractor

extractor = InvoiceExtractor()
invoice = extractor.extract_from_pdf("invoice.pdf")
print(invoice.to_dict())
```

支援識別的欄位：
- 發票號碼（格式：XX-00000000 或 XX00000000，連字號為可選）
- 發票日期（支援民國年和西元年）
- 賣方/買方統一編號
- 賣方/買方公司名稱
- 金額（小計、稅額、總計）
- 品項明細

### BrowserAutomation（瀏覽器自動化）

控制 Chrome 瀏覽器自動填寫表單。

```python
from src.browser_automation import EInvoiceAutomation, BrowserConfig

config = BrowserConfig(headless=False)
automation = EInvoiceAutomation(config)

automation.start_browser()
automation.open_einvoice_platform()
automation.fill_invoice_form(invoice_data)
automation.close_browser()
```

## 注意事項

1. **登入驗證**：本工具不會儲存任何登入資訊，使用者需自行登入財政部平台
2. **資料確認**：自動填寫後請務必確認資料正確性再提交
3. **網站結構**：財政部網站若有更新，可能需要調整程式中的元素定位
4. **憑證登入**：需要工商憑證或自然人憑證的功能需要額外配置

## 開發計畫

- [ ] 支援更多發票格式
- [ ] 加入 OCR 支援（掃描版發票）
- [ ] 批次處理多張發票
- [ ] 匯出 Excel/CSV 報表
- [ ] 憑證自動登入支援

## 授權

MIT License

## 貢獻

歡迎提交 Issue 和 Pull Request！
