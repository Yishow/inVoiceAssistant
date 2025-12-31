#!/usr/bin/env python3
"""
Claude Code 瀏覽器自動化控制腳本

這個腳本專門設計給 Claude Code 使用，讓您可以直接在 Claude Code
對話中控制瀏覽器自動登入財政部官網並開發票。

使用方式：
1. 在 Claude Code 中執行此腳本
2. 輸入自然語言指令
3. 腳本會自動控制瀏覽器執行操作

範例指令：
- python claude_code_automation.py "開啟電子發票平台"
- python claude_code_automation.py "填寫發票資料" --invoice invoice.pdf
- python claude_code_automation.py interactive  # 進入互動模式
"""

import argparse
import json
import sys
import time
from pathlib import Path

# 添加專案路徑
sys.path.insert(0, str(Path(__file__).parent))

from src.ai_automation import AIBrowserController, create_ai_controller, BrowserConfig
from src.invoice_extractor import InvoiceExtractor, InvoiceData


class ClaudeCodeAutomation:
    """Claude Code 專用的瀏覽器自動化控制器"""

    def __init__(self, headless: bool = False):
        """
        初始化控制器

        Args:
            headless: 是否使用無頭模式（不顯示瀏覽器視窗）
        """
        self.controller = create_ai_controller(
            use_claude=False,  # 使用本地解析器（Claude Code 本身就是 AI）
            headless=headless
        )
        self.invoice_data: InvoiceData = None
        self.session_started = False

    def start(self):
        """啟動瀏覽器會話"""
        if not self.session_started:
            print("[INFO] 正在啟動 Chrome 瀏覽器...")
            self.controller.start_session()
            self.session_started = True
            print("[OK] 瀏覽器已啟動")

    def stop(self):
        """停止瀏覽器會話"""
        if self.session_started:
            print("[INFO] 正在關閉瀏覽器...")
            self.controller.end_session()
            self.session_started = False
            print("[OK] 瀏覽器已關閉")

    def load_invoice(self, pdf_path: str) -> dict:
        """
        載入發票 PDF

        Args:
            pdf_path: PDF 文件路徑

        Returns:
            解析後的發票資料
        """
        print(f"[INFO] 正在解析發票: {pdf_path}")
        extractor = InvoiceExtractor()
        self.invoice_data = extractor.extract_from_pdf(pdf_path)
        result = self.invoice_data.to_dict()
        print(f"[OK] 發票解析完成，識別率: {result.get('confidence', 0)*100:.1f}%")
        return result

    def execute(self, prompt: str) -> dict:
        """
        執行自然語言指令

        Args:
            prompt: 自然語言指令

        Returns:
            執行結果
        """
        if not self.session_started:
            self.start()

        print(f"[EXEC] 執行指令: {prompt}")
        result = self.controller.process_prompt(prompt, self.invoice_data)

        if result.get("success"):
            print(f"[OK] {result.get('message', '執行成功')}")
            if result.get("actions"):
                for i, action in enumerate(result["actions"], 1):
                    print(f"   {i}. {action.get('description', action.get('action_type'))}")
        else:
            print(f"[ERROR] {result.get('error', '執行失敗')}")

        return result

    def screenshot(self, filename: str = None) -> str:
        """
        擷取螢幕截圖

        Args:
            filename: 輸出檔案名稱

        Returns:
            截圖檔案路徑
        """
        if not self.session_started:
            print("[ERROR] 瀏覽器尚未啟動")
            return None

        import datetime
        if not filename:
            filename = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        self.controller.browser.take_screenshot(filename)
        print(f"[OK] 截圖已儲存: {filename}")
        return filename

    def get_page_info(self) -> dict:
        """取得當前頁面資訊"""
        if not self.session_started:
            return {"error": "瀏覽器尚未啟動"}

        driver = self.controller.browser.driver
        return {
            "url": driver.current_url,
            "title": driver.title,
        }


def interactive_mode(automation: ClaudeCodeAutomation):
    """互動模式"""
    print("\n" + "="*60)
    print("  發票自動申報助手 - Claude Code 互動模式")
    print("="*60)
    print("\n可用指令:")
    print("  開啟電子發票平台  - 前往財政部電子發票平台")
    print("  前往 [網址]       - 導航到指定網址")
    print("  點擊 [元素]       - 點擊頁面元素")
    print("  輸入 [文字] 到 [欄位] - 在欄位中輸入文字")
    print("  填寫發票資料      - 自動填寫發票表單")
    print("  截圖              - 擷取當前頁面截圖")
    print("  等待 [秒數] 秒    - 等待指定時間")
    print("  info              - 顯示當前頁面資訊")
    print("  load [PDF路徑]    - 載入發票 PDF")
    print("  quit/exit         - 退出")
    print("\n")

    while True:
        try:
            prompt = input(">>> ").strip()

            if not prompt:
                continue

            if prompt.lower() in ("quit", "exit", "q"):
                break

            if prompt.lower() == "info":
                info = automation.get_page_info()
                print(f"   URL: {info.get('url', 'N/A')}")
                print(f"   Title: {info.get('title', 'N/A')}")
                continue

            if prompt.lower().startswith("load "):
                pdf_path = prompt[5:].strip()
                automation.load_invoice(pdf_path)
                continue

            automation.execute(prompt)

        except KeyboardInterrupt:
            print("\n[INFO] 收到中斷信號")
            break
        except Exception as e:
            print(f"[ERROR] {e}")

    automation.stop()
    print("[INFO] 已退出互動模式")


def main():
    parser = argparse.ArgumentParser(
        description="Claude Code 瀏覽器自動化控制腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
  %(prog)s "開啟電子發票平台"
  %(prog)s "填寫發票資料" --invoice invoice.pdf
  %(prog)s interactive
  %(prog)s --headless "截圖"
        """
    )

    parser.add_argument(
        "command",
        nargs="?",
        default="interactive",
        help="要執行的指令，或 'interactive' 進入互動模式"
    )

    parser.add_argument(
        "--invoice", "-i",
        help="發票 PDF 文件路徑"
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用無頭模式（不顯示瀏覽器視窗）"
    )

    parser.add_argument(
        "--output", "-o",
        help="輸出結果到 JSON 文件"
    )

    args = parser.parse_args()

    # 建立自動化實例
    automation = ClaudeCodeAutomation(headless=args.headless)

    try:
        # 載入發票（如果有指定）
        if args.invoice:
            automation.load_invoice(args.invoice)

        # 執行指令
        if args.command.lower() == "interactive":
            interactive_mode(automation)
        else:
            result = automation.execute(args.command)

            # 輸出結果
            if args.output:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                print(f"[OK] 結果已儲存到: {args.output}")

    except KeyboardInterrupt:
        print("\n[INFO] 操作已取消")
    finally:
        automation.stop()


if __name__ == "__main__":
    main()
