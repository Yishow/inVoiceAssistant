#!/usr/bin/env python3
"""
發票自動申報助手 - Web 介面

提供友善的網頁介面讓使用者上傳 PDF 並查看解析結果
支援 AI 對話自動化控制瀏覽器
"""
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from flask import Flask, request, render_template, jsonify, redirect, url_for

from config import UPLOAD_DIR, ALLOWED_EXTENSIONS
from src import InvoiceExtractor
from src.ai_automation import AIBrowserController, create_ai_controller, BrowserConfig
from src.invoice_extractor import InvoiceData

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB 上限

# 全域 AI 控制器實例（會話管理）
ai_controller: Optional[AIBrowserController] = None
current_invoice_data: Optional[InvoiceData] = None


def allowed_file(filename: str) -> bool:
    """檢查文件類型是否允許"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    """首頁"""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    """處理文件上傳"""
    if "file" not in request.files:
        return jsonify({"error": "沒有選擇文件"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"error": "沒有選擇文件"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "只支援 PDF 文件"}), 400

    # 儲存文件
    filename = Path(file.filename).name
    filepath = UPLOAD_DIR / filename
    file.save(str(filepath))

    # 解析發票
    try:
        extractor = InvoiceExtractor()
        invoice_data = extractor.extract_from_pdf(str(filepath))
        result = invoice_data.to_dict()
        result["filename"] = filename
        result["success"] = True

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": f"解析失敗: {str(e)}",
            "success": False
        }), 500


@app.route("/api/parse", methods=["POST"])
def api_parse():
    """API: 解析發票"""
    if "file" not in request.files:
        return jsonify({"error": "沒有提供文件", "success": False}), 400

    file = request.files["file"]

    if not allowed_file(file.filename):
        return jsonify({"error": "只支援 PDF 文件", "success": False}), 400

    # 暫存文件
    filename = Path(file.filename).name
    filepath = UPLOAD_DIR / filename
    file.save(str(filepath))

    try:
        extractor = InvoiceExtractor()
        invoice_data = extractor.extract_from_pdf(str(filepath))
        result = invoice_data.to_dict()
        result["success"] = True

        return jsonify(result)

    except Exception as e:
        return jsonify({
            "error": str(e),
            "success": False
        }), 500

    finally:
        # 清理暫存文件
        if filepath.exists():
            filepath.unlink()


@app.route("/health")
def health():
    """健康檢查"""
    return jsonify({"status": "ok"})


# ============ AI 自動化 API ============

@app.route("/api/ai/start", methods=["POST"])
def start_ai_session():
    """
    啟動 AI 瀏覽器自動化會話

    Request Body:
        use_claude: bool - 是否使用 Claude API（需要設定 ANTHROPIC_API_KEY）
        headless: bool - 是否使用無頭模式
    """
    global ai_controller

    data = request.get_json() or {}
    use_claude = data.get("use_claude", False)
    headless = data.get("headless", False)
    api_key = data.get("api_key") or os.environ.get("ANTHROPIC_API_KEY")

    try:
        # 如果已有會話，先結束
        if ai_controller:
            try:
                ai_controller.end_session()
            except Exception:
                pass

        # 創建新控制器
        ai_controller = create_ai_controller(
            use_claude=use_claude,
            api_key=api_key,
            headless=headless
        )

        # 啟動會話
        session = ai_controller.start_session()

        return jsonify({
            "success": True,
            "session_id": session.session_id,
            "message": "AI 自動化會話已啟動",
            "use_claude": use_claude
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/ai/stop", methods=["POST"])
def stop_ai_session():
    """停止 AI 瀏覽器自動化會話"""
    global ai_controller

    if ai_controller:
        try:
            ai_controller.end_session()
            ai_controller = None
            return jsonify({
                "success": True,
                "message": "會話已結束"
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    else:
        return jsonify({
            "success": True,
            "message": "沒有進行中的會話"
        })


@app.route("/api/ai/execute", methods=["POST"])
def execute_ai_prompt():
    """
    執行 AI 指令

    Request Body:
        prompt: str - 自然語言指令
        invoice_data: dict - 可選的發票資料
    """
    global ai_controller, current_invoice_data

    data = request.get_json() or {}
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return jsonify({
            "success": False,
            "error": "請輸入指令"
        }), 400

    # 如果沒有會話，自動啟動
    if not ai_controller:
        try:
            ai_controller = create_ai_controller(use_claude=False, headless=False)
            ai_controller.start_session()
        except Exception as e:
            return jsonify({
                "success": False,
                "error": f"無法啟動瀏覽器: {str(e)}"
            }), 500

    # 取得發票資料（如果有的話）
    invoice_data = None
    if data.get("invoice_data"):
        try:
            invoice_data = InvoiceData(**data["invoice_data"])
        except Exception:
            pass
    elif current_invoice_data:
        invoice_data = current_invoice_data

    try:
        result = ai_controller.process_prompt(prompt, invoice_data)
        return jsonify(result)
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/ai/status", methods=["GET"])
def get_ai_status():
    """取得 AI 會話狀態"""
    global ai_controller

    if ai_controller and ai_controller.session:
        session = ai_controller.session
        return jsonify({
            "active": True,
            "session_id": session.session_id,
            "status": session.status,
            "current_step": session.current_step,
            "total_steps": session.total_steps
        })
    else:
        return jsonify({
            "active": False
        })


@app.route("/api/ai/screenshot", methods=["POST"])
def take_screenshot():
    """擷取當前瀏覽器截圖"""
    global ai_controller

    if not ai_controller or not ai_controller.browser.driver:
        return jsonify({
            "success": False,
            "error": "沒有進行中的瀏覽器會話"
        }), 400

    try:
        import datetime
        import base64

        # 取得截圖
        screenshot = ai_controller.browser.driver.get_screenshot_as_base64()

        return jsonify({
            "success": True,
            "screenshot": screenshot,
            "timestamp": datetime.datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route("/api/ai/commands", methods=["GET"])
def get_available_commands():
    """取得可用的指令列表"""
    commands = [
        {
            "command": "開啟電子發票平台",
            "description": "前往財政部電子發票整合服務平台",
            "example": "開啟電子發票平台"
        },
        {
            "command": "前往 [網址]",
            "description": "導航到指定網址",
            "example": "前往 https://www.einvoice.nat.gov.tw/"
        },
        {
            "command": "點擊 [元素]",
            "description": "點擊頁面上的按鈕或連結",
            "example": "點擊 登入按鈕"
        },
        {
            "command": "輸入 [文字] 到 [欄位]",
            "description": "在輸入框中填入文字",
            "example": "輸入 12345678 到 統一編號"
        },
        {
            "command": "填寫發票資料",
            "description": "使用解析的發票資料自動填表",
            "example": "填寫發票資料"
        },
        {
            "command": "等待 [秒數] 秒",
            "description": "等待指定時間",
            "example": "等待 3 秒"
        },
        {
            "command": "截圖",
            "description": "擷取當前頁面截圖",
            "example": "截圖"
        },
        {
            "command": "登入",
            "description": "執行登入操作（需要帳號密碼）",
            "example": "登入"
        },
        {
            "command": "提交",
            "description": "提交當前表單",
            "example": "提交"
        },
        {
            "command": "滾動 [方向]",
            "description": "滾動頁面（上/下/到底）",
            "example": "滾動到底"
        }
    ]

    return jsonify({
        "success": True,
        "commands": commands
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
