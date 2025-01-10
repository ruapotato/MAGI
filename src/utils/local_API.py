#!/usr/bin/env python3

import os
import json
import subprocess
import numpy as np
from pathlib import Path
from flask import Flask, request, render_template_string, jsonify, Response
import requests
import ssl

# Constants
SCRIPT_DIR = Path(__file__).parent.absolute()
STATIC_DIR = SCRIPT_DIR / 'static'
AUDIO_DIR = STATIC_DIR / 'audio'
CERT_FILE = SCRIPT_DIR / 'cert.pem'
KEY_FILE = SCRIPT_DIR / 'key.pem'

# Create directories
STATIC_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

# Initialize Flask
app = Flask(__name__)

# Simple HTML template
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Voice Assistant Test Interface</title>
    <style>
        body { 
            font-family: Arial;
            max-width: 800px;
            margin: 20px auto;
            padding: 20px;
        }
        .chat-container {
            border: 1px solid #ccc;
            padding: 20px;
            margin-bottom: 20px;
        }
        #messages {
            height: 400px;
            overflow-y: auto;
            margin-bottom: 20px;
        }
        .message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 5px;
        }
        .user { background: #e3f2fd; }
        .assistant { background: #f5f5f5; }
        #recordButton {
            background-color: #4CAF50;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        #recordButton.recording {
            background-color: #f44336;
        }
        .button-disabled {
            background-color: #cccccc !important;
            cursor: not-allowed;
        }
    </style>
</head>
<body>
    <div class="chat-container">
        <div id="messages"></div>
        <div>
            <textarea id="input" rows="3" style="width: 100%"></textarea>
            <button onclick="sendMessage()">Send</button>
            <button id="recordButton">Record</button>
        </div>
    </div>

    <script>
        let mediaRecorder = null;
        let audioChunks = [];

        function addMessage(text, type) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${type}`;
            msgDiv.textContent = text;
            document.getElementById('messages').appendChild(msgDiv);
            msgDiv.scrollIntoView();
        }

        async function sendMessage() {
            const input = document.getElementById('input');
            const text = input.value.trim();
            if (!text) return;

            addMessage(text, 'user');
            input.value = '';

            try {
                const response = await fetch('/api/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({text: text})
                });
                const data = await response.json();
                
                if (data.error) {
                    addMessage('Error: ' + data.error, 'system');
                } else {
                    addMessage(data.response, 'assistant');
                    console.log('Response:', data.response);
                }
            } catch (error) {
                addMessage('Error: ' + error, 'system');
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                console.error('Media devices not supported');
                const recordButton = document.getElementById('recordButton');
                recordButton.classList.add('button-disabled');
                recordButton.disabled = true;
                return;
            }
            
            initRecording();

            async function initRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                    stream.getTracks().forEach(track => track.stop());
                    
                    document.getElementById('recordButton').addEventListener('mousedown', startRecording);
                    document.getElementById('recordButton').addEventListener('mouseup', stopRecording);
                } catch (error) {
                    console.error('Microphone setup error:', error);
                    document.getElementById('recordButton').classList.add('button-disabled');
                    document.getElementById('recordButton').disabled = true;
                }
            }

            async function startRecording() {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({audio: true});
                    mediaRecorder = new MediaRecorder(stream);
                    audioChunks = [];

                    mediaRecorder.ondataavailable = (event) => {
                        audioChunks.push(event.data);
                    };

                    mediaRecorder.onstop = async () => {
                        const audioBlob = new Blob(audioChunks);
                        const formData = new FormData();
                        formData.append('audio', audioBlob);

                        try {
                            const response = await fetch('/api/transcribe', {
                                method: 'POST',
                                body: formData
                            });
                            const result = await response.json();
                            if (result.text) {
                                document.getElementById('input').value = result.text;
                            }
                        } catch (error) {
                            addMessage('Transcription failed: ' + error, 'system');
                        }
                        stream.getTracks().forEach(track => track.stop());
                    };

                    mediaRecorder.start();
                    document.getElementById('recordButton').classList.add('recording');
                } catch (error) {
                    addMessage('Recording error: ' + error, 'system');
                }
            }

            function stopRecording() {
                if (mediaRecorder && mediaRecorder.state === 'recording') {
                    mediaRecorder.stop();
                    document.getElementById('recordButton').classList.remove('recording');
                }
            }
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400

        full_response = ""
        response = requests.post(
            'http://localhost:11434/api/generate',
            json={
                'model': 'mistral',
                'prompt': data['text'],
                'stream': True
            },
            stream=True,
            timeout=30
        )
        
        if response.ok:
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line)
                    if 'response' in chunk:
                        full_response += chunk['response']
            return jsonify({'response': full_response})
        return jsonify({'error': f'Ollama error: {response.status_code}'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/speak', methods=['POST'])
def speak():
    try:
        data = request.get_json()
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': 'No text provided'}), 400

        filename = f"speech_{len(os.listdir(AUDIO_DIR))}.wav"
        audio_path = AUDIO_DIR / filename

        subprocess.run([
            'espeak',
            '-v', 'en-us',
            '-s', '175',
            '-w', str(audio_path),
            text
        ], check=True)

        return jsonify({'url': f'/static/audio/{filename}'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    try:
        audio_file = request.files['audio']
        
        cmd = ['ffmpeg', '-i', '-', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-']
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
        output, _ = process.communicate(audio_file.read())
        
        audio_data = np.frombuffer(output, dtype=np.float32)
        
        response = requests.post(
            'http://localhost:5000/transcribe',
            files={'audio': ('audio.wav', audio_data.tobytes())}
        )
        
        if response.ok:
            result = response.json()
            return jsonify({'text': result['transcription']})
        return jsonify({'error': 'Transcription failed'}), 500
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(CERT_FILE, KEY_FILE)
    app.run(host='0.0.0.0', port=8000, ssl_context=ssl_context)
