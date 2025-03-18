from flask import Flask, render_template, request, send_from_directory, jsonify
from werkzeug.utils import secure_filename
import os
import subprocess
import shutil
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import psutil

app = Flask(__name__)

# Configuration
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'outputs'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max file size
ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv'}

# Create necessary folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

# Global progress tracking
processing_progress = {}

def process_video(file_info):
    filename, input_path, output_path, clip_type, task_id = file_info
    try:
        subprocess.run([
            'ffmpeg', '-y',
            '-i', input_path,
            '-ss', '0',
            '-t', clip_type,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-tune', 'zerolatency',
            '-profile:v', 'high',
            '-level', '4.2',
            '-maxrate', '4M',
            '-bufsize', '4M',
            '-threads', '2',
            '-movflags', '+faststart',
            '-c:a', 'aac',
            '-b:a', '192k',
            output_path
        ], check=True)
        processing_progress[task_id]['progress'] = 100
        return f'clip_{filename}'
    except Exception as e:
        processing_progress[task_id]['progress'] = -1
        raise e

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'videos' not in request.files:
        return render_template('index.html', error='No file selected')
    
    files = request.files.getlist('videos')
    clip_type = request.form.get('clip_type', '5')
    processed_files = []
    errors = []
    
    # Calculate available resources
    available_memory = psutil.virtual_memory().available
    max_concurrent = max(1, int(available_memory / (500 * 1024 * 1024)))
    max_workers = min(multiprocessing.cpu_count(), max_concurrent)
    
    video_tasks = []
    task_id = os.urandom(16).hex()
    processing_progress[task_id] = {'progress': 0}
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], f'clip_{filename}')
            file.save(input_path)
            video_tasks.append((filename, input_path, output_path, clip_type, task_id))
    
    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            processed_files = list(executor.map(process_video, video_tasks))
    except Exception as e:
        errors.append(f"Error in parallel processing: {str(e)}")
    finally:
        for _, input_path, _, _, _ in video_tasks:
            if os.path.exists(input_path):
                os.remove(input_path)
    
    return render_template('results.html', 
                         processed_files=processed_files,
                         errors=errors,
                         task_id=task_id)

@app.route('/progress/<task_id>')
def get_progress(task_id):
    progress = processing_progress.get(task_id, {}).get('progress', 0)
    if progress == 100:
        processing_progress.pop(task_id, None)
    return jsonify({'progress': progress})

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000, debug=True)