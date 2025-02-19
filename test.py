import os
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
import fitz  # PyMuPDF
from PIL import Image
import tkinter as tk

def get_mouse_position(event):
    print(f"Mouse clicked at: ({event.x}, {event.y})")

root = tk.Tk()
root.title("Mouse Click Position")

root.bind("<Button-1>", get_mouse_position)  # Lắng nghe click chuột trái


app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
EDITED_FOLDER = "static/edited_pdfs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(EDITED_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["EDITED_FOLDER"] = EDITED_FOLDER

pdf_path = None
image_path = None

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload_pdf", methods=["POST"])
def upload_pdf():
    global pdf_path
    file = request.files["file"]
    if file:
        filename = secure_filename(file.filename)
        pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(pdf_path)
        return jsonify({"message": "PDF uploaded", "pdf_url": pdf_path})
    return jsonify({"error": "No file uploaded"})

@app.route("/upload_image", methods=["POST"])
def upload_image():
    global image_path
    file = request.files["file"]
    if file:
        filename = secure_filename(file.filename)
        image_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(image_path)
        return jsonify({"message": "Image uploaded", "image_url": image_path})
    return jsonify({"error": "No file uploaded"})

@app.route("/insert_image", methods=["POST"])
def insert_image():
    global pdf_path, image_path

    if not pdf_path or not image_path:
        return jsonify({"error": "PDF or image not uploaded"})

    data = request.json
    page_number = int(data["page"])
    click_x, click_y = float(data["x"]), float(data["y"])
    canvas_width, canvas_height = float(data["canvas_width"]), float(data["canvas_height"])

    doc = fitz.open(pdf_path)
    page = doc[page_number]
    page_width, page_height = page.rect.width, page.rect.height

    # Tính toán tọa độ thực của ảnh trên PDF
    pdf_x = (click_x / canvas_width) * page_width
    pdf_y = page_height - ((click_y / canvas_height) * page_height)  # Đảo ngược trục Y

    img = Image.open(image_path)
    img_width, img_height = img.size
    scale = 0.3  # Thu nhỏ ảnh để tránh quá to
    img_rect = fitz.Rect(pdf_x, pdf_y, pdf_x + img_width * scale, pdf_y + img_height * scale)

    page.insert_image(img_rect, filename=image_path)

    edited_pdf_path = os.path.join(app.config["EDITED_FOLDER"], "edited_" + os.path.basename(pdf_path))
    doc.save(edited_pdf_path)
    doc.close()

    return jsonify({"message": "Image inserted", "edited_pdf_url": edited_pdf_path})

@app.route("/download_pdf")
def download_pdf():
    edited_pdf_path = os.path.join(app.config["EDITED_FOLDER"], "edited_" + os.path.basename(pdf_path))
    return send_file(edited_pdf_path, as_attachment=True)

if __name__ == "__main__":
    app.run(debug=True)
