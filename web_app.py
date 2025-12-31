#!/usr/bin/env python3
"""
發票自動申報助手 - Web 介面

提供友善的網頁介面讓使用者上傳 PDF 並查看解析結果
"""
import os
import json
from pathlib import Path
from flask import Flask, request, render_template, jsonify, redirect, url_for

from config import UPLOAD_DIR, ALLOWED_EXTENSIONS
from src import InvoiceExtractor

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = str(UPLOAD_DIR)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16MB 上限


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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
