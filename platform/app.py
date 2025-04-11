from flask import Flask, render_template, request, redirect, url_for, send_from_directory
import os
from werkzeug.utils import secure_filename
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB

# DB setup
def init_db():
    with sqlite3.connect('database.db') as con:
        con.execute('''CREATE TABLE IF NOT EXISTS firs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            description TEXT,
            anonymous INTEGER,
            filename TEXT,
            timestamp TEXT
        )''')
init_db()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form.get('name') if request.form.get('anon') != 'on' else 'Anonymous'
        email = request.form.get('email') if request.form.get('anon') != 'on' else 'hidden'
        description = request.form.get('description')
        file = request.files['file']
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        with sqlite3.connect('database.db') as con:
            con.execute("INSERT INTO firs (name, email, description, anonymous, filename, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                        (name, email, description, 1 if request.form.get('anon') == 'on' else 0, filename, datetime.now().isoformat()))
        return redirect(url_for('thankyou'))
    return render_template('index.html')

@app.route('/thankyou')
def thankyou():
    return "<h2>FIR submitted successfully! Your case is being processed.</h2>"

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)
