#!/usr/bin/env python3
"""
發票自動申報助手 - Web 介面

提供友善的網頁介面讓使用者上傳 PDF 並查看解析結果
"""
import os
from pathlib import Path
from flask import Flask, request, render_template, jsonify
from werkzeug.utils import secure_filename
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect

from config import UPLOAD_DIR, ALLOWED_EXTENSIONS
from src import InvoiceExtractor

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB 上限

# CSRF 保護 - 使用環境變數設定密鑰，若無則使用隨機值（開發用）
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or os.urandom(32)
csrf = CSRFProtect(app)

# 速率限制 - 防止濫用
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)


def allowed_file(filename: str) -> bool:
    """檢查文件類型是否允許"""
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    """首頁"""
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
@limiter.limit("10 per minute")
def upload_file():
    """處理文件上傳"""
    if "file" not in request.files:
        return jsonify({"error": "沒有選擇文件"}), 400

    file = request.files["file"]

    if not file or not file.filename:
        return jsonify({"error": "沒有選擇文件"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "只支援 PDF 文件"}), 400

    # 安全化文件名，防止路徑遍歷攻擊
    filename = secure_filename(file.filename)
    filepath = UPLOAD_DIR / filename
    
    try:
        file.save(str(filepath))

        # 解析發票
        extractor = InvoiceExtractor()
        invoice_data = extractor.extract_from_pdf(str(filepath))
        result = invoice_data.to_dict()
        result["filename"] = filename
        result["success"] = True

        return jsonify(result)

    except PermissionError:
        return jsonify({
            "error": "檔案儲存失敗：權限不足",
            "success": False
        }), 500
    except Exception as e:
        return jsonify({
            "error": f"解析失敗: {str(e)}",
            "success": False
        }), 500
    finally:
        # 清理暫存文件
        if filepath.exists():
            try:
                filepath.unlink()
            except Exception:
                pass  # 清理失敗不影響回應


@app.route("/api/parse", methods=["POST"])
@limiter.limit("10 per minute")
def api_parse():
    """API: 解析發票"""
    if "file" not in request.files:
        return jsonify({"error": "沒有提供文件", "success": False}), 400

    file = request.files["file"]

    if not file or not file.filename:
        return jsonify({"error": "沒有選擇文件", "success": False}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "只支援 PDF 文件", "success": False}), 400

    # 安全化文件名，防止路徑遍歷攻擊
    filename = secure_filename(file.filename)
    filepath = UPLOAD_DIR / filename

    try:
        file.save(str(filepath))
        
        extractor = InvoiceExtractor()
        invoice_data = extractor.extract_from_pdf(str(filepath))
        result = invoice_data.to_dict()
        result["success"] = True

        return jsonify(result)

    except PermissionError:
        return jsonify({
            "error": "檔案儲存失敗：權限不足",
            "success": False
        }), 500
    except ValueError as e:
        return jsonify({
            "error": f"資料格式錯誤: {str(e)}",
            "success": False
        }), 400
    except Exception as e:
        return jsonify({
            "error": f"解析失敗: {str(e)}",
            "success": False
        }), 500

    finally:
        # 清理暫存文件
        if filepath.exists():
            try:
                filepath.unlink()
            except Exception:
                pass  # 清理失敗不影響回應


@app.route("/health")
def health():
    """健康檢查"""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    # Only enable debug mode in development environments
    debug_mode = os.environ.get("FLASK_ENV") == "development" or os.environ.get("FLASK_DEBUG") == "1"
    # Use 127.0.0.1 for local development instead of 0.0.0.0
    # For production deployment, use a proper WSGI server like gunicorn
    app.run(host="127.0.0.1", port=5000, debug=debug_mode)
