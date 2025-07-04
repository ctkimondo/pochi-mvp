from flask import Flask, request, render_template, redirect, url_for, session, send_from_directory
import os, random, uuid
from werkzeug.utils import secure_filename
import qrcode
from io import BytesIO
from flask import send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone
import secrets

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///pochi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.secret_key = secrets.token_hex(32)
UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Stores the documents in memory
user_documents = {}

class User(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    documents = db.relationship('Document', backref='user', lazy=True)

class Document(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    filename = db.Column(db.String(200), nullable=False)
    verified = db.Column(db.Boolean, default=False)
    doc_id = db.Column(db.String(20), unique=True, nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if not user:
            user = User(email=email)
            db.session.add(user)
            db.session.commit()
        session['user_id'] = user.id
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    return render_template('dashboard.html', documents=user.documents, email=user.email)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    file = request.files['document']
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        doc = Document(
            filename=filename,
            # Generate fake verification
            verified = random.choice([True, False]),
            doc_id = str(uuid.uuid4())[:8],
            user_id=session['user_id']
        )

        db.session.add(doc)
        db.session.commit()
        return redirect(url_for('dashboard'))
    return 'No file uploaded'

@app.route('/doc/<doc_id>')
def view_doc(doc_id):
    doc = Document.query.filter_by(doc_id=doc_id).first()
    if not doc:
        return "Document not found"
    status = "Verified" if doc.verified else  "Not Verified"
    color = "text-green-600" if doc.verified else "text-red-600"
    file_url = url_for('uploaded_file', filename=doc.filename)
    qr_url = url_for('generate_qr', doc_id=doc.doc_id)

    return f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Pochi Verification</title>
        <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="bg-gray-100 h-[100dvh] flex items-center justify-center px-4 py-8">
        <div class="w-full max-w-md bg-white shadow-xl rounded-xl p-6 space-y-6">
            <div class="text-center">
            <h2 class="text-2xl font-bold text-gray-800 mb-2">Document Verification</h2>
            <p class="text-sm text-gray-500 mb-4">Powered by Pochi</p>
            </div>

            <div class="space-y-1">
            <p class="text-sm text-gray-600">Filename:</p>
            <p class="text-lg font-medium">{doc.filename}</p>
            </div>

            <div class="space-y-1">
            <p class="text-sm text-gray-600">Status:</p>
            <p class="text-lg font-bold {color}">{status}</p>
            </div>

            <a href="{file_url}" target="_blank"
            class="block w-full text-center bg-blue-600 text-white py-2 rounded-lg hover:bg-blue-700 transition">
            View Document
            </a>

            <div class="text-center pt-4">
            <p class="text-sm text-gray-600 mb-2">Scan to view:</p>
            <img src="{qr_url}" alt="QR Code" class="mx-auto w-40 h-40" />
            </div>
        </div>
        </body>
        </html>
    """


@app.route('/qrcode/<doc_id>')
def generate_qr(doc_id):
    doc_url = url_for('view_doc', doc_id=doc_id, _external=True)
    img = qrcode.make(doc_url)
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return send_file(buffer, mimetype='image/png')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/delete/<doc_id>', methods=['POST'])
def delete_doc(doc_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    doc = Document.query.filter_by(doc_id=doc_id, user_id=session['user_id']).first()
    if doc:
        db.session.delete(doc)
        db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)
