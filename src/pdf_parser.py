"""
PDF 解析模組 - 提取 PDF 發票內容
"""
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

try:
    import pdfplumber
except ImportError:
    pdfplumber = None

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None


@dataclass
class PDFContent:
    """PDF 內容資料結構"""
    file_path: str
    pages: list[str] = field(default_factory=list)
    tables: list[list] = field(default_factory=list)
    total_pages: int = 0
    raw_text: str = ""

    def get_full_text(self) -> str:
        """取得完整文字內容"""
        return "\n".join(self.pages)


class PDFParser:
    """PDF 解析器"""

    def __init__(self):
        self._check_dependencies()

    def _check_dependencies(self):
        """檢查必要的套件是否已安裝"""
        if pdfplumber is None and PdfReader is None:
            raise ImportError(
                "請安裝 PDF 解析套件: pip install pdfplumber PyPDF2"
            )

    def parse(self, file_path: str | Path) -> PDFContent:
        """
        解析 PDF 文件

        Args:
            file_path: PDF 文件路徑

        Returns:
            PDFContent: 解析後的內容
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"找不到文件: {file_path}")

        if file_path.suffix.lower() != ".pdf":
            raise ValueError(f"不支援的文件格式: {file_path.suffix}")

        # 優先使用 pdfplumber（更好的表格解析能力）
        if pdfplumber is not None:
            return self._parse_with_pdfplumber(file_path)
        else:
            return self._parse_with_pypdf2(file_path)

    def _parse_with_pdfplumber(self, file_path: Path) -> PDFContent:
        """使用 pdfplumber 解析 PDF"""
        content = PDFContent(file_path=str(file_path))

        with pdfplumber.open(file_path) as pdf:
            content.total_pages = len(pdf.pages)

            for page in pdf.pages:
                # 提取文字
                text = page.extract_text() or ""
                content.pages.append(text)

                # 提取表格
                tables = page.extract_tables()
                if tables:
                    content.tables.extend(tables)

        content.raw_text = content.get_full_text()
        return content

    def _parse_with_pypdf2(self, file_path: Path) -> PDFContent:
        """使用 PyPDF2 解析 PDF（備用方案）"""
        content = PDFContent(file_path=str(file_path))

        reader = PdfReader(str(file_path))
        content.total_pages = len(reader.pages)

        for page in reader.pages:
            text = page.extract_text() or ""
            content.pages.append(text)

        content.raw_text = content.get_full_text()
        return content

    def extract_text_blocks(self, file_path: str | Path) -> list[str]:
        """
        提取 PDF 中的文字區塊

        Args:
            file_path: PDF 文件路徑

        Returns:
            文字區塊列表
        """
        content = self.parse(file_path)

        # 分割成區塊（以空行分隔）
        blocks = []
        for page_text in content.pages:
            page_blocks = re.split(r'\n\s*\n', page_text)
            blocks.extend([b.strip() for b in page_blocks if b.strip()])

        return blocks


# 測試用
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        parser = PDFParser()
        result = parser.parse(sys.argv[1])
        print(f"總頁數: {result.total_pages}")
        print(f"表格數: {len(result.tables)}")
        print("\n--- 文字內容 ---")
        print(result.raw_text[:2000])  # 只顯示前2000字
    else:
        print("用法: python pdf_parser.py <PDF文件路徑>")
