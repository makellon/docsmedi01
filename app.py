import os
import threading
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
from dental_chatbot import DentalChatBot

app = Flask(__name__, static_folder='static', static_url_path='/static')

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB limit

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

chatbot = DentalChatBot()

class TimeoutError(Exception):
    pass

def timeout(seconds):
    def decorator(func):
        def wrapper(*args, **kwargs):
            result = [TimeoutError('Function call timed out')]
            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    result[0] = e
            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(seconds)
            if isinstance(result[0], Exception):
                raise result[0]
            return result[0]
        return wrapper
    return decorator

@app.route('/')
def index():
    print("Rendering index page")
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    print("Received upload request")
    if 'file' not in request.files:
        print("Error: No file part in the request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        print("Error: No selected file")
        return jsonify({'error': 'No selected file'}), 400
    
    if file and allowed_file(file.filename):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            print(f"File saved: {filepath}")
                    
            try:
                print("Starting dental X-ray analysis")
                analysis_result = timeout(30)(chatbot.analyze_dental_xray)(filepath)
                print("Analysis completed successfully")
            except TimeoutError:
                print("Error: Analysis timed out")
                return jsonify({'error': 'Analysis timed out'}), 504
            
            # Get the relative path of the annotated image
            annotated_image_path = os.path.relpath(analysis_result['annotated_image_path'], start=app.static_folder)
            
            print(f"Annotated image path: {annotated_image_path}")
            
            print("Sending analysis results to client")
            return jsonify({
            'message': 'File uploaded and analyzed successfully',
            'analysis': analysis_result,
            'annotated_image': '/static/' + annotated_image_path.replace('\\', '/')
        })
        except Exception as e:
            print(f"Unexpected error in upload process: {str(e)}")
            return jsonify({'error': 'An unexpected error occurred during processing'}), 500
    else:
        print(f"File type not allowed: {file.filename}")
        return jsonify({'error': 'File type not allowed'}), 400

@app.route('/chat', methods=['POST'])
def chat():
    print("Received chat request")
    data = request.json
    if not data or 'message' not in data:
        print("Error: No message provided in chat request")
        return jsonify({'error': 'No message provided'}), 400
    
    user_input = data['message']
    try:
        print(f"Processing chat message: {user_input}")
        response = timeout(15)(chatbot.continue_conversation)(user_input)
        print("Chat response generated successfully")
        return jsonify({'response': response})
    except TimeoutError:
        print("Error: Chat response timed out")
        return jsonify({'error': 'Chat response timed out'}), 504
    except Exception as e:
        print(f"Error in chat response: {str(e)}")
        return jsonify({'error': 'An error occurred while processing your message'}), 500

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.errorhandler(413)
def request_entity_too_large(error):
    print("Error: File too large")
    return jsonify({'error': 'File too large'}), 413

if __name__ == '__main__':
    print("Starting the Flask application")
    app.run(debug=True)