from flask import Flask, render_template, request, send_from_directory
from werkzeug.utils import secure_filename
import os
import subprocess
import shutil
from dotenv import load_dotenv

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

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'videos' not in request.files:
        return render_template('index.html', error='No file selected')
    
    files = request.files.getlist('videos')
    clip_type = request.form.get('clip_type', '5')
    clip_duration = request.form.get('clip_duration', '30')
    processed_files = []
    errors = []

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            try:
                file.save(input_path)
                
                if clip_type == 'full':
                    # Get video duration using ffprobe
                    duration_cmd = subprocess.run([
                        'ffprobe', '-v', 'error', '-show_entries',
                        'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
                        input_path
                    ], capture_output=True, text=True)
                    
                    total_duration = float(duration_cmd.stdout)
                    clip_dur = int(clip_duration)
                    
                    # Generate multiple clips
                    for start_time in range(0, int(total_duration), clip_dur):
                        output_filename = f'clip_{start_time}_{filename}'
                        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
                        
                        subprocess.run([
                            'ffmpeg', '-y',
                            '-i', input_path,
                            '-ss', str(start_time),
                            '-t', str(clip_dur),
                            output_path
                        ], check=True)
                        
                        processed_files.append(output_filename)
                else:
                    # Extract first X seconds
                    output_path = os.path.join(app.config['OUTPUT_FOLDER'], f'clip_{filename}')
                    subprocess.run([
                        'ffmpeg', '-y',
                        '-i', input_path,
                        '-t', clip_type,
                        output_path
                    ], check=True)
                    
                    processed_files.append(f'clip_{filename}')
                
            except Exception as e:
                errors.append(f"Error processing {filename}: {str(e)}")
            finally:
                # Clean up upload
                if os.path.exists(input_path):
                    os.remove(input_path)
        else:
            if file.filename:
                errors.append(f"Invalid file type: {file.filename}")

    return render_template('results.html', 
                         processed_files=processed_files,
                         errors=errors)

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(app.config['OUTPUT_FOLDER'], filename)

if __name__ == '__main__':
    app.run(debug=True)