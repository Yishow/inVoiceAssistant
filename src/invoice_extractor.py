"""
發票識別模組 - 判別發票項目與金額
"""
import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from .pdf_parser import PDFParser, PDFContent


@dataclass
class InvoiceItem:
    """發票品項"""
    name: str  # 品名
    quantity: float = 1.0  # 數量
    unit_price: float = 0.0  # 單價
    amount: float = 0.0  # 金額

    def __post_init__(self):
        if self.amount == 0 and self.unit_price > 0:
            self.amount = self.quantity * self.unit_price


@dataclass
class InvoiceData:
    """發票資料結構"""
    # 發票基本資訊
    invoice_number: str = ""  # 發票號碼
    invoice_date: str = ""  # 發票日期
    invoice_type: str = ""  # 發票類型

    # 賣方資訊
    seller_id: str = ""  # 賣方統一編號
    seller_name: str = ""  # 賣方名稱
    seller_address: str = ""  # 賣方地址

    # 買方資訊
    buyer_id: str = ""  # 買方統一編號
    buyer_name: str = ""  # 買方名稱
    buyer_address: str = ""  # 買方地址

    # 金額資訊
    subtotal: float = 0.0  # 小計（未稅）
    tax_rate: float = 0.05  # 稅率（預設5%）
    tax_amount: float = 0.0  # 稅額
    total_amount: float = 0.0  # 總計（含稅）

    # 品項明細
    items: list[InvoiceItem] = field(default_factory=list)

    # 其他資訊
    raw_text: str = ""  # 原始文字
    confidence: float = 0.0  # 識別信心度

    def to_dict(self) -> dict:
        """轉換為字典"""
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "invoice_type": self.invoice_type,
            "seller": {
                "id": self.seller_id,
                "name": self.seller_name,
                "address": self.seller_address,
            },
            "buyer": {
                "id": self.buyer_id,
                "name": self.buyer_name,
                "address": self.buyer_address,
            },
            "amounts": {
                "subtotal": self.subtotal,
                "tax_rate": self.tax_rate,
                "tax_amount": self.tax_amount,
                "total": self.total_amount,
            },
            "items": [
                {
                    "name": item.name,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "amount": item.amount,
                }
                for item in self.items
            ],
            "confidence": self.confidence,
        }


class InvoiceExtractor:
    """發票資訊提取器"""

    # 正則表達式模式
    PATTERNS = {
        # 發票號碼：第1碼 A-Z，第2碼 A-D + 8碼數字（符合財政部電子發票格式）
        "invoice_number": r"[A-Z][A-D][-\s]?\d{8}",
        # 統一編號：8碼數字
        "tax_id": r"\b\d{8}\b",
        # 日期格式：民國年或西元年
        "date_tw": r"(\d{2,3})\s*[年/]\s*(\d{1,2})\s*[月/]\s*(\d{1,2})\s*日?",
        "date_western": r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        # 金額：數字可能有逗號
        "amount": r"\$?\s*([\d,]+(?:\.\d{2})?)",
        # 稅額關鍵字
        "tax_keywords": r"(營業稅|稅額|稅金|Tax)",
        # 總計關鍵字
        "total_keywords": r"(合計|總計|總額|應付|Total)",
    }

    def __init__(self):
        self.pdf_parser = PDFParser()

    def extract_from_pdf(self, file_path: str | Path) -> InvoiceData:
        """
        從 PDF 文件提取發票資訊

        Args:
            file_path: PDF 文件路徑

        Returns:
            InvoiceData: 提取的發票資料
        """
        # 解析 PDF
        pdf_content = self.pdf_parser.parse(file_path)

        # 提取發票資訊
        invoice_data = self._extract_invoice_data(pdf_content)
        invoice_data.raw_text = pdf_content.raw_text

        return invoice_data

    def extract_from_text(self, text: str) -> InvoiceData:
        """
        從文字內容提取發票資訊

        Args:
            text: 發票文字內容

        Returns:
            InvoiceData: 提取的發票資料
        """
        pdf_content = PDFContent(
            file_path="",
            pages=[text],
            raw_text=text,
            total_pages=1,
        )
        return self._extract_invoice_data(pdf_content)

    def _extract_invoice_data(self, pdf_content: PDFContent) -> InvoiceData:
        """從 PDF 內容提取發票資訊"""
        text = pdf_content.raw_text
        invoice = InvoiceData()
        matched_fields = 0
        # 動態計算實際檢查的欄位數
        expected_fields = []

        # 提取發票號碼
        invoice.invoice_number = self._extract_invoice_number(text)
        if invoice.invoice_number:
            matched_fields += 1
        expected_fields.append("invoice_number")

        # 提取日期
        invoice.invoice_date = self._extract_date(text)
        if invoice.invoice_date:
            matched_fields += 1
        expected_fields.append("invoice_date")

        # 提取統一編號（賣方和買方）
        tax_ids = self._extract_tax_ids(text)
        if len(tax_ids) >= 1:
            invoice.seller_id = tax_ids[0]
            matched_fields += 1
        expected_fields.append("seller_id")
        
        if len(tax_ids) >= 2:
            invoice.buyer_id = tax_ids[1]
            matched_fields += 1
        expected_fields.append("buyer_id")

        # 提取公司名稱
        names = self._extract_company_names(text)
        if len(names) >= 1:
            invoice.seller_name = names[0]
            matched_fields += 1
        expected_fields.append("seller_name")
        
        if len(names) >= 2:
            invoice.buyer_name = names[1]
            matched_fields += 1
        expected_fields.append("buyer_name")

        # 提取金額
        amounts = self._extract_amounts(text)
        if amounts:
            invoice.total_amount = amounts.get("total", 0)
            invoice.tax_amount = amounts.get("tax", 0)
            invoice.subtotal = amounts.get("subtotal", 0)
            if invoice.total_amount > 0:
                matched_fields += 1
        expected_fields.append("total_amount")

        # 從表格提取品項
        if pdf_content.tables:
            invoice.items = self._extract_items_from_tables(pdf_content.tables)
            if invoice.items:
                matched_fields += 1
            expected_fields.append("items")

        # 計算信心度（使用實際欄位數）
        total_fields = len(expected_fields)
        invoice.confidence = matched_fields / total_fields if total_fields > 0 else 0

        return invoice

    def _extract_invoice_number(self, text: str) -> str:
        """提取發票號碼"""
        pattern = self.PATTERNS["invoice_number"]
        match = re.search(pattern, text)
        if match:
            # 移除空格和連字符
            return match.group().replace(" ", "").replace("-", "")
        return ""

    def _extract_date(self, text: str) -> str:
        """提取發票日期"""
        # 嘗試民國年格式
        pattern_tw = self.PATTERNS["date_tw"]
        match = re.search(pattern_tw, text)
        if match:
            year, month, day = match.groups()
            # 轉換民國年為西元年（僅在合理的民國年份範圍內）
            year = int(year)
            # 民國年範圍：1-150（避免誤將西元年 200-1911 視為民國年）
            if 1 <= year <= 150:
                year += 1911
            return f"{year}/{int(month):02d}/{int(day):02d}"

        # 嘗試西元年格式
        pattern_western = self.PATTERNS["date_western"]
        match = re.search(pattern_western, text)
        if match:
            year, month, day = match.groups()
            return f"{year}/{int(month):02d}/{int(day):02d}"

        return ""

    def _is_valid_taiwan_tax_id(self, tax_id: str) -> bool:
        """
        驗證台灣統一編號（稅籍編號）的檢查碼
        
        Args:
            tax_id: 8位數字的統一編號
            
        Returns:
            bool: 是否為有效的統一編號
        """
        # 必須是正好 8 位數字
        if len(tax_id) != 8 or not tax_id.isdigit():
            return False

        # 台灣統一編號檢查碼演算法的權重
        weights = [1, 2, 1, 2, 1, 2, 4, 1]
        total = 0

        for digit_char, weight in zip(tax_id, weights):
            product = int(digit_char) * weight
            # 將乘積的各位數字相加（例如 12 -> 1 + 2）
            q, r = divmod(product, 10)
            total += q + r

        # 基本規則：總和能被 10 整除
        if total % 10 == 0:
            return True

        # 特殊規則：如果第 7 位是 7，且 (總和 + 1) 能被 10 整除，也視為有效
        if tax_id[6] == "7" and (total + 1) % 10 == 0:
            return True

        return False

    def _extract_tax_ids(self, text: str) -> list[str]:
        """提取統一編號"""
        pattern = self.PATTERNS["tax_id"]
        # 找出所有8位數字
        matches = re.findall(pattern, text)

        # 使用統一編號檢查碼驗證，過濾掉無效的統編
        valid_ids = []
        for match in matches:
            if self._is_valid_taiwan_tax_id(match) and match not in valid_ids:
                valid_ids.append(match)

        return valid_ids[:2]  # 只返回前兩個（賣方和買方）

    def _extract_company_names(self, text: str) -> list[str]:
        """提取公司名稱"""
        names = []

        # 常見的公司名稱關鍵字
        company_patterns = [
            r"([\u4e00-\u9fff]+(?:股份有限公司|有限公司|公司|企業|行號|商行|工廠|事務所))",
            r"賣方[：:]\s*([\u4e00-\u9fff]+)",
            r"買方[：:]\s*([\u4e00-\u9fff]+)",
            r"營業人[：:]\s*([\u4e00-\u9fff]+)",
        ]

        for pattern in company_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if match and match not in names and len(match) >= 2:
                    names.append(match)

        return names[:2]

    def _extract_amounts(self, text: str) -> dict[str, float]:
        """提取金額資訊"""
        amounts = {}

        # 尋找總計金額
        total_pattern = r"(?:合計|總計|總額|應付|Total)[^\d]*([\d,]+(?:\.\d{2})?)"
        total_match = re.search(total_pattern, text, re.IGNORECASE)
        if total_match:
            amounts["total"] = self._parse_amount(total_match.group(1))

        # 尋找稅額
        tax_pattern = r"(?:營業稅|稅額|稅金|Tax)[^\d]*([\d,]+(?:\.\d{2})?)"
        tax_match = re.search(tax_pattern, text, re.IGNORECASE)
        if tax_match:
            amounts["tax"] = self._parse_amount(tax_match.group(1))

        # 尋找小計（未稅）
        subtotal_pattern = r"(?:小計|未稅|銷售額|Subtotal)[^\d]*([\d,]+(?:\.\d{2})?)"
        subtotal_match = re.search(subtotal_pattern, text, re.IGNORECASE)
        if subtotal_match:
            amounts["subtotal"] = self._parse_amount(subtotal_match.group(1))

        # 如果沒有小計但有總計和稅額，計算小計
        if "subtotal" not in amounts and "total" in amounts and "tax" in amounts:
            amounts["subtotal"] = amounts["total"] - amounts["tax"]

        return amounts

    def _parse_amount(self, amount_str: str) -> float:
        """解析金額字串"""
        # 移除逗號和空格
        clean_str = amount_str.replace(",", "").replace(" ", "")
        try:
            return float(clean_str)
        except ValueError:
            return 0.0

    def _extract_items_from_tables(self, tables: list[list]) -> list[InvoiceItem]:
        """從表格提取品項明細"""
        items = []

        for table in tables:
            if not table or len(table) < 2:
                continue

            # 尋找表頭
            header_row = None
            for i, row in enumerate(table):
                if row and any(
                    keyword in str(cell) for cell in row if cell
                    for keyword in ["品名", "品項", "項目", "商品", "名稱"]
                ):
                    header_row = i
                    break

            if header_row is None:
                continue

            # 分析表頭以確定欄位位置
            headers = [str(cell).strip() if cell else "" for cell in table[header_row]]

            name_col = self._find_column(headers, ["品名", "品項", "項目", "商品", "名稱"])
            qty_col = self._find_column(headers, ["數量", "數", "Qty"])
            price_col = self._find_column(headers, ["單價", "價格", "Price"])
            amount_col = self._find_column(headers, ["金額", "小計", "Amount"])

            # 提取資料列
            for row in table[header_row + 1:]:
                if not row or len(row) <= name_col:
                    continue

                name = str(row[name_col]).strip() if row[name_col] else ""
                if not name:
                    continue

                item = InvoiceItem(name=name)

                if qty_col is not None and len(row) > qty_col and row[qty_col]:
                    try:
                        item.quantity = float(str(row[qty_col]).replace(",", ""))
                    except ValueError:
                        # 無法解析數量為數字時，保留預設數量
                        pass

                if price_col is not None and len(row) > price_col and row[price_col]:
                    try:
                        item.unit_price = float(str(row[price_col]).replace(",", ""))
                    except ValueError:
                        # 無法解析單價為數字時，保留預設單價
                        pass

                if amount_col is not None and len(row) > amount_col and row[amount_col]:
                    try:
                        item.amount = float(str(row[amount_col]).replace(",", ""))
                    except ValueError:
                        # 無法解析金額為數字時，保留預設金額
                        pass

                items.append(item)

        return items

    def _find_column(self, headers: list[str], keywords: list[str]) -> Optional[int]:
        """在表頭中尋找特定欄位"""
        for i, header in enumerate(headers):
            for keyword in keywords:
                if keyword in header:
                    return i
        return None


# 測試用
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) > 1:
        extractor = InvoiceExtractor()
        result = extractor.extract_from_pdf(sys.argv[1])
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("用法: python invoice_extractor.py <PDF文件路徑>")
