from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
import sqlite3
import os
import datetime
from werkzeug.utils import secure_filename
from PIL import Image, ImageChops
import fitz

app = Flask(__name__)
app.secret_key = 'your_secret_key'
UPLOAD_FOLDER = 'static/signatures'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def init_db():
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (
            KhachID INTEGER PRIMARY KEY AUTOINCREMENT,
            Khach_Name TEXT,
            Position TEXT,
            Email TEXT UNIQUE,
            Sign TEXT,
            Password TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS signed_invoices (
            InvoiceID INTEGER PRIMARY KEY AUTOINCREMENT,
            PDF_Name TEXT,
            KhachID INTEGER,
            Timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(KhachID) REFERENCES users(KhachID)
        )''')
        conn.commit()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        position = request.form['position']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        signature = request.files['signature']
        
        if password != confirm_password:
            flash("Mật khẩu không khớp!", "danger")
            return redirect(url_for('register'))
        
        signature_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(signature.filename))
        signature.save(signature_path)
        
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (Khach_Name, Position, Email, Sign, Password) VALUES (?, ?, ?, ?, ?)",
                           (name, position, email, signature_path, password))
            conn.commit()
        flash("Đăng ký thành công!", "success")
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Khach_Name, Position, Sign FROM users WHERE Email = ? AND Password = ?", (email, password))
            user = cursor.fetchone()
            if user:
                session['username'] = user[0]
                session['position'] = user[1]
                session['signature'] = user[2]
                return redirect(url_for('home'))
        flash("Sai thông tin đăng nhập!", "danger")
    return render_template('login.html')

# Add a route for handling forgotten password
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Khach_Name FROM users WHERE Email = ?", (email,))
            user = cursor.fetchone()
            
            if user:
                new_password = "newpass123"  # For simplicity, a static password reset (you can generate a random one)
                cursor.execute("UPDATE users SET Password = ? WHERE Email = ?", (new_password, email))
                conn.commit()
                flash(f"Mật khẩu mới của bạn là: {new_password}", "success")
                return redirect(url_for('login'))
            else:
                flash("Email không tồn tại trong hệ thống!", "danger")
                return redirect(url_for('forgot_password'))
    
    return render_template('forgot_password.html')

@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            flash("Mật khẩu mới không khớp!", "danger")
            return redirect(url_for('change_password'))
        
        with sqlite3.connect('users.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT Password FROM users WHERE Khach_Name = ?", (session['username'],))
            stored_password = cursor.fetchone()
            
            if stored_password and stored_password[0] == current_password:
                cursor.execute("UPDATE users SET Password = ? WHERE Khach_Name = ?", (new_password, session['username']))
                conn.commit()
                flash("Đổi mật khẩu thành công!", "success")
                return redirect(url_for('home'))
            else:
                flash("Mật khẩu hiện tại không đúng!", "danger")
                return redirect(url_for('change_password'))
    
    return render_template('change_password.html', username=session['username'])

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template("home.html", username=session['username'])

@app.route('/upload1', methods=['GET', 'POST'])
def upload1():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        if "pdf" not in request.files:
            flash("Vui lòng tải lên PDF!", "danger")
            return redirect(url_for("upload1"))

        pdf_file = request.files["pdf"]

        if pdf_file.filename == "":
            flash("Tên tệp không hợp lệ!", "danger")
            return redirect(url_for("upload1"))

        pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], secure_filename(pdf_file.filename))
        pdf_file.save(pdf_path)
        
        if not session.get('signature'):
            flash("Người dùng chưa có chữ ký trong hệ thống!", "danger")
            return redirect(url_for("upload1"))

        output_pdf = os.path.join(app.config["UPLOAD_FOLDER"], "signed_" + pdf_file.filename)
        position = get_signature_position(session['position'])
        add_signature_to_pdf(pdf_path, session['signature'], output_pdf, position)

        return send_file(output_pdf, as_attachment=True)
    
    return render_template("upload1.html", username=session['username'])

@app.route('/show_signed_files')
def show_signed_files():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''SELECT si.PDF_Name, u.Khach_Name, si.Timestamp
                          FROM signed_invoices si
                          JOIN users u ON si.KhachID = u.KhachID
                          ORDER BY si.Timestamp DESC''')
        signed_files = cursor.fetchall()
    
    return render_template('show_signed_files.html', signed_files=signed_files)

@app.route('/upload2', methods=['GET', 'POST'])
def upload2():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if request.method == "POST":
        if "pdf" not in request.files:
            flash("Vui lòng tải lên PDF!", "danger")
            return redirect(url_for("upload2"))

        pdf_file = request.files["pdf"]
        pdf_path = os.path.join("static/uploads", secure_filename(pdf_file.filename))
        os.makedirs("static/uploads", exist_ok=True)
        pdf_file.save(pdf_path)
        session['pdf_path'] = pdf_path
        return jsonify({"pdf_url": pdf_path})
    
    return render_template("upload2.html", username=session['username'], pdf_url=session.get('pdf_path'))

@app.route('/sign_pdf', methods=['POST'])
def sign_pdf():
    if 'username' not in session:
        return jsonify({"error": "Bạn chưa đăng nhập"}), 401

    if 'pdf' not in request.files or 'x' not in request.form or 'y' not in request.form:
        return jsonify({"error": "Dữ liệu không hợp lệ"}), 400

    pdf_file = request.files['pdf']
    x, y = float(request.form['x']), float(request.form['y'])

    pdf_filename = secure_filename(pdf_file.filename)
    pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], pdf_filename)
    pdf_file.save(pdf_path)

    if not session.get('signature'):
        return jsonify({"error": "Chưa có chữ ký"}), 400

    # Check if user has already signed this PDF
    with sqlite3.connect('users.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT KhachID FROM users WHERE Khach_Name = ?", (session['username'],))
        user_id = cursor.fetchone()
        
        if user_id:
            cursor.execute("SELECT * FROM signed_invoices WHERE PDF_Name = ? AND KhachID = ?", (pdf_filename, user_id[0]))
            if cursor.fetchone():
                return jsonify({"error": "Bạn đã ký tài liệu này rồi!"}), 400
        
        # Record the signature
        cursor.execute("INSERT INTO signed_invoices (PDF_Name, KhachID) VALUES (?, ?)", (pdf_filename, user_id[0]))
        conn.commit()

    signature_path = session['signature']
    output_pdf = os.path.join(app.config["UPLOAD_FOLDER"], "signed_" + pdf_filename)

    add_signature_to_pdf_1(pdf_path, signature_path, output_pdf, (x, y))

    return send_file(output_pdf, as_attachment=True, mimetype='application/pdf')


def get_signature_position(position):
    positions = {
        "Staff": (90, 405),
        "Manager": (220, 405),
        "Director": (370, 405),
        "EVGM": (500, 405)
    }
    return positions.get(position, (90, 405))

def remove_white_background(image_path):
    image = Image.open(image_path).convert("RGBA")
    bg = Image.new("RGBA", image.size, (255, 255, 255, 255))
    diff = ImageChops.difference(image, bg)
    bbox = diff.getbbox()
    if bbox:
        image = image.crop(bbox)
    cleaned_path = os.path.join(os.path.dirname(image_path), "cleaned_signature.png")
    image.save(cleaned_path)
    return cleaned_path

def add_signature_to_pdf(pdf_path, sig_path, output_pdf, position, page_number=0):
    doc = fitz.open(pdf_path)
    page = doc[page_number]
    sig_path = remove_white_background(sig_path)
    sig_img = Image.open(sig_path)
    sig_width, sig_height = sig_img.size
    target_height = 34
    scale_factor = target_height / sig_height
    new_width = int(sig_width * scale_factor)
    new_height = target_height
    sig_img = sig_img.resize((new_width, new_height), Image.LANCZOS)
    resized_sig_path = os.path.join(app.config["UPLOAD_FOLDER"], "resized_signature.png")
    sig_img.save(resized_sig_path)
    img_rect = fitz.Rect(position[0], position[1], position[0] + new_width, position[1] + new_height)
    page.insert_image(img_rect, filename=resized_sig_path)

    timestamp = datetime.datetime.now().strftime(" %H:%M:%S\n %d-%m-%Y")
    page.insert_text((position[0] , position[1] + new_height + 10), f" {timestamp}", fontsize=10, color=(0, 0, 0))

    doc.save(output_pdf)
    doc.close()

def add_signature_to_pdf_1(pdf_path, sig_path, output_pdf, position, page_number=0):
    doc = fitz.open(pdf_path)
    page = doc[page_number]

    sig_img = Image.open(sig_path)
    sig_width, sig_height = sig_img.size
    scale_factor = 34 / sig_height
    new_width, new_height = int(sig_width * scale_factor), 34
    sig_img = sig_img.resize((new_width, new_height), Image.LANCZOS)

    img_rect = fitz.Rect(position[0], position[1], position[0] + new_width, position[1] + new_height)
    page.insert_image(img_rect, filename=sig_path)

    timestamp = datetime.datetime.now().strftime(" %H:%M:%S\n %d-%m-%Y")
    page.insert_text((position[0] , position[1] + new_height + 10), f" {timestamp}", fontsize=10, color=(0, 0, 0))

    try:
        doc.save(output_pdf)
        doc.close()
    except Exception as e:
        print(f"Lỗi khi lưu PDF: {e}")
    # Kiểm tra nếu file PDF có thể mở được
    try:
        with fitz.open(output_pdf) as test_pdf:
            if len(test_pdf) == 0:
                print("Lỗi: File PDF bị trống!")
    except Exception as e:
        print(f"Lỗi khi mở file PDF: {e}")


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
