"""
發票自動申報助手 - 核心模組
"""
from .pdf_parser import PDFParser
from .invoice_extractor import InvoiceExtractor
from .browser_automation import BrowserAutomation, EInvoiceAutomation
from .ai_automation import (
    AIBrowserController,
    AICommandParser,
    ClaudeAutomationAgent,
    create_ai_controller,
    BrowserAction,
    ActionType,
)

__all__ = [
    "PDFParser",
    "InvoiceExtractor",
    "BrowserAutomation",
    "EInvoiceAutomation",
    "AIBrowserController",
    "AICommandParser",
    "ClaudeAutomationAgent",
    "create_ai_controller",
    "BrowserAction",
    "ActionType",
]
