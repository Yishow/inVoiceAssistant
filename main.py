#!/usr/bin/env python3
"""
發票自動申報助手 - 主程式

功能：
1. 上傳發票 PDF 文件
2. 自動識別發票內容（項目、金額、統一編號等）
3. 透過 Chrome 瀏覽器自動填寫財政部電子發票平台

使用方式：
    # 命令列模式
    python main.py --pdf invoice.pdf

    # Web 介面模式
    python main.py --web

作者：Invoice Assistant Team
"""
import argparse
import json
import sys
from pathlib import Path

from src import PDFParser, InvoiceExtractor, BrowserAutomation
from src.browser_automation import EInvoiceAutomation, BrowserConfig


def parse_invoice(pdf_path: str) -> dict:
    """
    解析發票 PDF 文件

    Args:
        pdf_path: PDF 文件路徑

    Returns:
        dict: 解析結果
    """
    extractor = InvoiceExtractor()
    invoice_data = extractor.extract_from_pdf(pdf_path)
    return invoice_data.to_dict()


def print_invoice_info(invoice_dict: dict):
    """列印發票資訊"""
    print("\n" + "=" * 50)
    print("📄 發票資訊解析結果")
    print("=" * 50)

    print(f"\n【基本資訊】")
    print(f"  發票號碼: {invoice_dict.get('invoice_number', '未識別')}")
    print(f"  發票日期: {invoice_dict.get('invoice_date', '未識別')}")

    print(f"\n【賣方資訊】")
    seller = invoice_dict.get('seller', {})
    print(f"  統一編號: {seller.get('id', '未識別')}")
    print(f"  公司名稱: {seller.get('name', '未識別')}")

    print(f"\n【買方資訊】")
    buyer = invoice_dict.get('buyer', {})
    print(f"  統一編號: {buyer.get('id', '未識別')}")
    print(f"  公司名稱: {buyer.get('name', '未識別')}")

    print(f"\n【金額資訊】")
    amounts = invoice_dict.get('amounts', {})
    print(f"  小計（未稅）: ${amounts.get('subtotal', 0):,.0f}")
    print(f"  稅額: ${amounts.get('tax_amount', 0):,.0f}")
    print(f"  總計: ${amounts.get('total', 0):,.0f}")

    items = invoice_dict.get('items', [])
    if items:
        print(f"\n【品項明細】")
        for i, item in enumerate(items, 1):
            print(f"  {i}. {item['name']}")
            print(f"     數量: {item['quantity']} | 單價: ${item['unit_price']:,.0f} | 金額: ${item['amount']:,.0f}")

    confidence = invoice_dict.get('confidence', 0)
    print(f"\n【識別信心度】: {confidence * 100:.1f}%")
    print("=" * 50)


def run_automation(invoice_dict: dict, headless: bool = False):
    """
    執行瀏覽器自動化

    Args:
        invoice_dict: 發票資料字典
        headless: 是否使用無頭模式
    """
    from src.invoice_extractor import InvoiceData, InvoiceItem

    # 將字典轉換回 InvoiceData 物件
    invoice_data = InvoiceData(
        invoice_number=invoice_dict.get('invoice_number', ''),
        invoice_date=invoice_dict.get('invoice_date', ''),
        seller_id=invoice_dict.get('seller', {}).get('id', ''),
        seller_name=invoice_dict.get('seller', {}).get('name', ''),
        buyer_id=invoice_dict.get('buyer', {}).get('id', ''),
        buyer_name=invoice_dict.get('buyer', {}).get('name', ''),
        subtotal=invoice_dict.get('amounts', {}).get('subtotal', 0),
        tax_amount=invoice_dict.get('amounts', {}).get('tax_amount', 0),
        total_amount=invoice_dict.get('amounts', {}).get('total', 0),
    )

    # 轉換品項
    for item in invoice_dict.get('items', []):
        invoice_data.items.append(InvoiceItem(
            name=item['name'],
            quantity=item['quantity'],
            unit_price=item['unit_price'],
            amount=item['amount'],
        ))

    # 建立瀏覽器配置
    config = BrowserConfig(headless=headless)
    automation = EInvoiceAutomation(config)

    try:
        print("\n🌐 正在啟動 Chrome 瀏覽器...")
        automation.start_browser()

        print("📡 正在開啟電子發票平台...")
        automation.open_einvoice_platform()

        print("\n⚠️  注意事項：")
        print("1. 請先手動登入您的帳號（使用憑證或帳號密碼）")
        print("2. 登入後，導航到發票申報頁面")
        print("3. 程式將自動協助填寫發票資料")

        input("\n按 Enter 繼續自動填寫表單...")

        print("📝 正在填寫發票資料...")
        success = automation.fill_invoice_form(invoice_data)

        if success:
            print("✅ 表單填寫完成！")
            print("⚠️  請檢查填寫內容，確認無誤後再手動提交")
        else:
            print("❌ 表單填寫過程中發生錯誤")

        input("\n按 Enter 關閉瀏覽器...")

    except Exception as e:
        print(f"❌ 發生錯誤: {e}")

    finally:
        automation.close_browser()
        print("🔒 瀏覽器已關閉")


def run_cli():
    """命令列模式"""
    parser = argparse.ArgumentParser(
        description="發票自動申報助手",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例：
  解析發票 PDF：
    python main.py --pdf invoice.pdf

  解析並自動填寫：
    python main.py --pdf invoice.pdf --auto

  啟動 Web 介面：
    python main.py --web

  輸出 JSON 格式：
    python main.py --pdf invoice.pdf --json
        """
    )

    parser.add_argument(
        "--pdf",
        type=str,
        help="發票 PDF 文件路徑"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="自動開啟瀏覽器填寫表單"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="啟動 Web 介面"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以 JSON 格式輸出結果"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="使用無頭瀏覽器模式"
    )

    args = parser.parse_args()

    # 啟動 Web 介面
    if args.web:
        print("🌐 正在啟動 Web 介面...")
        from web_app import app
        app.run(host="0.0.0.0", port=5000, debug=True)
        return

    # 處理 PDF 文件
    if args.pdf:
        pdf_path = Path(args.pdf)

        if not pdf_path.exists():
            print(f"❌ 找不到文件: {pdf_path}")
            sys.exit(1)

        print(f"📄 正在解析發票: {pdf_path}")

        try:
            invoice_dict = parse_invoice(str(pdf_path))

            if args.json:
                print(json.dumps(invoice_dict, ensure_ascii=False, indent=2))
            else:
                print_invoice_info(invoice_dict)

            # 自動填寫
            if args.auto:
                run_automation(invoice_dict, headless=args.headless)

        except Exception as e:
            print(f"❌ 解析失敗: {e}")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    run_cli()
