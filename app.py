import io
import os
import socket
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS
import qrcode

from database import (
    add_registration,
    check_in,
    get_admin_status,
    get_all_registrations,
    get_registration,
    setup_admin,
    verify_admin,
)

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
@app.route("/index.html")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/login.html")
def login_page():
    return send_from_directory(BASE_DIR, "login.html")


@app.route("/main.html")
def main_page():
    return send_from_directory(BASE_DIR, "main.html")


@app.route("/scanner.html")
def scanner_page():
    return send_from_directory(BASE_DIR, "scanner.html")


@app.route("/welcome.html")
def welcome_page():
    return send_from_directory(BASE_DIR, "welcome.html")


# Serves images (img1.jpeg, img2.jpeg, etc.) and assets directly from BASE_DIR
@app.route("/<path:filename>")
def serve_static_files(filename):
    return send_from_directory(BASE_DIR, filename)


@app.route("/health")
def health():
    return jsonify({"status": "running"})


@app.route("/api/admin/status", methods=["GET"])
def admin_status():
    try:
        return jsonify(get_admin_status())
    except Exception as e:
        return jsonify({"exists": False, "error": str(e)}), 500


@app.route("/api/admin/setup", methods=["POST"])
def admin_setup():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400

    try:
        success, msg = setup_admin(username, password)
        return jsonify({"success": success, "message": msg}), (200 if success else 400)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username")
    password = data.get("password")

    if not username or not password:
        return jsonify({"success": False, "message": "Username and password required"}), 400

    try:
        success, msg = verify_admin(username, password)
        return jsonify({"success": success, "message": msg}), (200 if success else 401)
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/register", methods=["POST"])
@app.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    # Name, phone, and age range are mandatory; ideas and guest questions are optional
    if not data.get("name") or not data.get("phone") or not data.get("age"):
        return jsonify({"success": False, "message": "Please fill all required fields."}), 400

    try:
        reg_id, error = add_registration(data)
        if error:
            return jsonify({"success": False, "message": error}), 400
        return jsonify({"success": True, "registrationId": reg_id, "registration_id": reg_id})
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"}), 500


@app.route("/api/registration/<reg_id>")
def registration(reg_id):
    try:
        user = get_registration(reg_id)
        if not user:
            return jsonify({"success": False, "message": "Registration not found"}), 404
        return jsonify({"success": True, "user": user})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/registrations")
def registrations():
    try:
        users = get_all_registrations()
        return jsonify({"success": True, "users": users})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/check-in", methods=["POST"])
def checkin():
    data = request.get_json(silent=True) or {}
    reg_id = data.get("registrationId")

    if not reg_id:
        return jsonify({"success": False, "message": "Registration ID required"}), 400

    try:
        user, already_checked = check_in(reg_id)
        if not user:
            return jsonify({"success": False, "message": "Attendee not found"}), 404
        return jsonify({"success": True, "alreadyCheckedIn": already_checked, "user": user})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/qr/<reg_id>")
def qr(reg_id):
    qr_matrix = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr_matrix.add_data(reg_id)
    qr_matrix.make(fit=True)

    img = qr_matrix.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(buffer, mimetype="image/png")


@app.route("/favicon.ico")
def favicon():
    return "", 204


def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    local_ip = get_local_ip()

    print("\n" + "=" * 65)
    print("  SWAYAM SERVER RUNNING")
    print("=" * 65)
    print(f"  * Localhost:          http://localhost:{port}")
    print(f"  * Localhost IP:       http://127.0.0.1:{port}")
    print(f"  * Network (LAN/WiFi): http://{local_ip}:{port}")
    print("=" * 65 + "\n")

    app.run(host="0.0.0.0", port=port, debug=False)