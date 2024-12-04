#!/usr/bin/env python3

import os
import json
import base64
import queue
import secrets
import hashlib
import threading
import requests
import numpy as np
import subprocess
import time
from pathlib import Path
from functools import wraps
from flask import Flask, request, render_template_string, jsonify, Response, session, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import ssl

# Constants
SCRIPT_DIR = Path(__file__).parent.absolute()
CREDS_FILE = SCRIPT_DIR / 'web_creds.txt'
SESSION_KEY = secrets.token_hex(32)
STATIC_DIR = SCRIPT_DIR / 'static'
AUDIO_DIR = STATIC_DIR / 'audio'

# Create audio cache directory
STATIC_DIR.mkdir(exist_ok=True)
AUDIO_DIR.mkdir(exist_ok=True)

# Initialize Flask
app = Flask(__name__)
app.secret_key = SESSION_KEY

# Thread-safe queue for prompts
prompt_queue = queue.Queue()

# HTML template with enhanced features
HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>MAGI Web Interface</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        :root {
            --lcars-orange: #ff9c00;
            --lcars-blue: #99ccff;
            --lcars-purple: #cc99cc;
            --lcars-bg: #000000;
            --lcars-text: #ffffff;
            --font-trek: "Helvetica Neue", Arial, sans-serif;
        }

        body { 
            background: var(--lcars-bg);
            color: var(--lcars-text);
            font-family: var(--font-trek);
            margin: 0;
            padding: 2rem;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }

        .chat-container {
            flex: 1;
            max-width: 1200px;
            margin: 0 auto;
            background: linear-gradient(rgba(0,0,0,0.7), rgba(0,0,0,0.9));
            border: 2px solid var(--lcars-orange);
            border-radius: 15px;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            position: relative;
            overflow: hidden;
            box-shadow: 0 0 20px rgba(255, 156, 0, 0.2);
            height: calc(100vh - 4rem);
        }

        .chat-header {
            display: flex;
            gap: 1rem;
            padding: 1rem;
            background: rgba(0, 0, 0, 0.5);
            border-bottom: 1px solid var(--lcars-orange);
            margin-bottom: 1rem;
        }

        .model-select {
            background: rgba(153, 204, 255, 0.1);
            border: 1px solid var(--lcars-blue);
            color: var(--lcars-text);
            padding: 0.5rem;
            border-radius: 4px;
            font-family: var(--font-trek);
            min-width: 200px;
        }

        .model-select:focus {
            outline: none;
            border-color: var(--lcars-orange);
            box-shadow: 0 0 10px rgba(255, 156, 0, 0.3);
        }

        .chat-header::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, 
                var(--lcars-orange) 0%, 
                var(--lcars-blue) 50%, 
                var(--lcars-purple) 100%);
        }

        #messages {
            flex: 1;
            overflow-y: auto;
            padding: 1rem;
            display: flex;
            flex-direction: column;
            gap: 1rem;
            scrollbar-width: thin;
            scrollbar-color: var(--lcars-orange) transparent;
            margin-bottom: 1rem;
        }

        #messages::-webkit-scrollbar {
            width: 6px;
        }

        #messages::-webkit-scrollbar-thumb {
            background: var(--lcars-orange);
            border-radius: 3px;
        }

        .message {
            padding: 1rem;
            border-radius: 8px;
            max-width: 80%;
            position: relative;
            animation: messageAppear 0.3s ease-out;
        }

        .message-content {
            margin-bottom: 0.5rem;
        }

        .message-actions {
            display: flex;
            gap: 0.5rem;
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        .message:hover .message-actions {
            opacity: 1;
        }

        @keyframes messageAppear {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .message.user {
            align-self: flex-end;
            background: var(--lcars-orange);
            color: var(--lcars-bg);
            margin-left: 20%;
        }

        .message.assistant {
            align-self: flex-start;
            background: rgba(153, 204, 255, 0.1);
            border: 1px solid var(--lcars-blue);
            margin-right: 20%;
        }

        .input-area {
            display: flex;
            gap: 1rem;
            padding: 1rem;
            background: rgba(0, 0, 0, 0.5);
            border-top: 1px solid var(--lcars-orange);
            position: sticky;
            bottom: 0;
        }

        #input {
            flex: 1;
            background: rgba(153, 204, 255, 0.1);
            border: 1px solid var(--lcars-blue);
            color: var(--lcars-text);
            padding: 0.8rem;
            border-radius: 4px;
            font-family: var(--font-trek);
            min-height: 20px;
            max-height: 150px;
            resize: vertical;
        }

        #input:focus {
            outline: none;
            border-color: var(--lcars-orange);
            box-shadow: 0 0 10px rgba(255, 156, 0, 0.3);
        }

        button {
            background: var(--lcars-orange);
            color: var(--lcars-bg);
            border: none;
            padding: 0.8rem 1.5rem;
            border-radius: 4px;
            cursor: pointer;
            font-family: var(--font-trek);
            font-weight: bold;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        button:hover:not(:disabled) {
            background: var(--lcars-blue);
            transform: translateY(-1px);
        }

        button:disabled {
            background: #333;
            cursor: not-allowed;
        }

        button.icon-button {
            padding: 0.5rem;
            min-width: 36px;
            justify-content: center;
        }

        #voice.recording {
            background: var(--lcars-purple);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(1); }
            50% { transform: scale(1.05); }
            100% { transform: scale(1); }
        }

        #status {
            position: fixed;
            top: 1rem;
            right: 1rem;
            padding: 0.8rem 1.5rem;
            background: rgba(0, 0, 0, 0.8);
            border: 1px solid var(--lcars-orange);
            color: var(--lcars-text);
            border-radius: 4px;
            display: none;
            animation: statusAppear 0.3s ease-out;
            z-index: 1000;
        }

        @keyframes statusAppear {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .loading {
            opacity: 0.5;
        }

        .code {
            font-family: monospace;
            background: #1a1a1a;
            color: var(--lcars-text);
            padding: 1rem;
            border-radius: 4px;
            overflow-x: auto;
            border: 1px solid var(--lcars-blue);
        }

        .system-info {
            color: var(--lcars-purple);
            font-style: italic;
            text-align: center;
            margin: 0.5rem 0;
        }

        /* Audio player styling */
        .audio-player {
            background: rgba(153, 204, 255, 0.1);
            border: 1px solid var(--lcars-blue);
            border-radius: 4px;
            padding: 0.5rem;
            margin-top: 0.5rem;
        }

        .audio-player audio {
            width: 100%;
        }

        /* Tooltip */
        [data-tooltip] {
            position: relative;
        }

        [data-tooltip]:before {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            padding: 0.5rem;
            background: rgba(0, 0, 0, 0.8);
            color: var(--lcars-text);
            border-radius: 4px;
            font-size: 0.8rem;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
        }

        [data-tooltip]:hover:before {
            opacity: 1;
            visibility: visible;
        }
    </style>
</head>
<body>
    <div id="status"></div>
    <div class="chat-container">
        <div class="chat-header">
            <select id="model-select" class="model-select">
                <option value="">Loading models...</option>
            </select>
            <button id="refresh-models" class="icon-button" data-tooltip="Refresh Models">🔄</button>
        </div>
        <div id="messages"></div>
        <div class="input-area">
            <button id="voice" title="Hold to record" disabled class="icon-button">🎤</button>
            <textarea id="input" placeholder="Enter command..." rows="1"></textarea>
            <button id="send">Send</button>
        </div>
    </div>

    <script>
        let isRecording = false;
        let mediaRecorder = null;
        let audioChunks = [];
        let currentModel = 'mistral';
        
        // Initialize available models
        async function loadModels() {
            try {
                const response = await fetch('/models');
                const models = await response.json();
                const select = document.getElementById('model-select');
                select.innerHTML = models.map(model => 
                    `<option value="${model.name}" ${model.name === currentModel ? 'selected' : ''}>
                        ${model.name} (${formatSize(model.size)})
                    </option>`
                ).join('');
            } catch (error) {
                console.error('Failed to load models:', error);
                showStatus('Failed to load models');
            }
        }

        function formatSize(bytes) {
            const units = ['B', 'KB', 'MB', 'GB'];
            let size = bytes;
            let unitIndex = 0;
            while (size >= 1024 && unitIndex < units.length - 1) {
                size /= 1024;
                unitIndex++;
            }
            return `${size.toFixed(1)} ${units[unitIndex]}`;
        }

        // Load models on page load and when refresh button is clicked
        loadModels();
        document.getElementById('refresh-models').onclick = loadModels;
        
        // Update current model when selection changes
        document.getElementById('model-select').onchange = function(e) {
            currentModel = e.target.value;
        };
        
        async function initializeMicrophone() {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                document.getElementById('voice').disabled = false;
                showStatus('Microphone ready');
                stream.getTracks().forEach(track => track.stop());
            } catch (error) {
                showStatus('Microphone access denied');
                console.error('Mic access error:', error);
            }
        }
        
        initializeMicrophone();

        function createMessage(text, type) {
            const msgDiv = document.createElement('div');
            msgDiv.className = `message ${type}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.className = 'message-content';
            contentDiv.textContent = text;
            
            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'message-actions';
            
            // Add speak button
            const speakButton = document.createElement('button');
            speakButton.className = 'icon-button';
            speakButton.innerHTML = '🔊';
            speakButton.setAttribute('data-tooltip', 'Speak message');
            // Use a closure to capture the current text content
            speakButton.onclick = () => {
                // Get the current text from the content div
                const currentText = msgDiv.querySelector('.message-content').textContent;
                console.log('Speaking text:', currentText);  // Debug log
                if (currentText && currentText.trim()) {
                    speakText(currentText, msgDiv);
                } else {
                    showStatus('No text to speak');
                }
            };
            
            // Add copy button
            const copyButton = document.createElement('button');
            copyButton.className = 'icon-button';
            copyButton.innerHTML = '📋';
            copyButton.setAttribute('data-tooltip', 'Copy to clipboard');
            copyButton.onclick = () => {
                const currentText = msgDiv.querySelector('.message-content').textContent;
                if (currentText) {
                    navigator.clipboard.writeText(currentText)
                        .then(() => showStatus('Copied to clipboard'))
                        .catch(err => showStatus('Failed to copy'));
                }
            };
            
            actionsDiv.appendChild(speakButton);
            actionsDiv.appendChild(copyButton);
            
            msgDiv.appendChild(contentDiv);
            msgDiv.appendChild(actionsDiv);
            
            document.getElementById('messages').appendChild(msgDiv);
            scrollToBottom();
            return msgDiv;
        }

        function scrollToBottom() {
            const messages = document.getElementById('messages');
            messages.scrollTop = messages.scrollHeight;
        }

        async function speakText(text, messageDiv) {
            try {
                console.log('Starting speech generation for:', text.substring(0, 100));
                
                const response = await fetch('/speak', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json'
                    },
                    body: JSON.stringify({text: text})
                });
                
                const contentType = response.headers.get('content-type');
                console.log('Response content type:', contentType);
                
                if (!response.ok) {
                    const errorText = await response.text();
                    console.error('Server error:', response.status, errorText);
                    throw new Error(`Server error: ${response.status} ${errorText}`);
                }
                
                const data = await response.json();
                console.log('Server response:', data);
                
                if (data.error) {
                    throw new Error(data.error);
                }
                
                if (!data.url) {
                    throw new Error('No audio URL in response');
                }
                
                // Create audio player
                const audioDiv = document.createElement('div');
                audioDiv.className = 'audio-player';
                
                // Remove any existing audio players in this message
                const existingAudio = messageDiv.querySelector('.audio-player');
                if (existingAudio) {
                    existingAudio.remove();
                }
                
                // Add loading indicator
                audioDiv.innerHTML = '<div class="audio-loading">Generating audio...</div>';
                messageDiv.appendChild(audioDiv);
                
                // Create and load audio element
                const audio = new Audio(data.url);
                
                // Wait for audio to be loaded
                await new Promise((resolve, reject) => {
                    audio.oncanplay = resolve;
                    audio.onerror = () => reject(new Error('Failed to load audio'));
                    audio.load();
                });
                
                // Replace loading indicator with audio player
                audioDiv.innerHTML = '';
                audioDiv.appendChild(audio);
                audio.controls = true;
                audio.autoplay = true;
                
                console.log('Audio player created and loaded');
                
            } catch (error) {
                console.error('Speech error:', error);
                showStatus(`Speech error: ${error.message}`);
                
                // Show error in message
                const errorDiv = document.createElement('div');
                errorDiv.className = 'speech-error';
                errorDiv.style.color = '#ff4444';
                errorDiv.textContent = `🔊 Error: ${error.message}`;
                
                // Replace any existing error or audio player
                const existing = messageDiv.querySelector('.speech-error, .audio-player');
                if (existing) {
                    existing.replaceWith(errorDiv);
                } else {
                    messageDiv.appendChild(errorDiv);
                }
            }
        }

        function sendMessage() {
            const input = document.getElementById('input');
            const text = input.value.trim();
            if (!text) return;

            // Create user message
            createMessage(text, 'user');
            input.value = '';

            // Reset input height
            input.style.height = 'auto';

            // Create assistant message container
            const assistantMsg = createMessage('', 'assistant');
            let assistantResponse = '';

            // First send the message
            fetch('/chat', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    text: text,
                    model: currentModel
                })
            })
            .then(() => {
                // Then create EventSource for the response
                const chatSource = new EventSource('/chat');
                
                chatSource.onopen = function(event) {
                    console.log('Chat connection opened');
                };

                chatSource.onmessage = function(event) {
                    try {
                        const data = JSON.parse(event.data);
                        console.log('Received message:', data);
                        
                        switch(data.type) {
                            case 'start':
                                console.log('Starting new message');
                                break;
                                
                            case 'stream':
                                assistantResponse += data.text;
                                const contentDiv = assistantMsg.querySelector('.message-content');
                                contentDiv.textContent = assistantResponse;
                                scrollToBottom();
                                break;
                                
                            case 'error':
                                showStatus('Error: ' + data.text);
                                chatSource.close();
                                break;
                                
                            case 'end':
                                console.log('Message complete');
                                chatSource.close();
                                break;
                        }
                    } catch (error) {
                        console.error('Error parsing message:', error, event.data);
                    }
                };

                chatSource.onerror = function(event) {
                    console.error('SSE Error:', event);
                    if (chatSource.readyState === EventSource.CLOSED) {
                        console.log('Connection was closed');
                    }
                    if (!assistantResponse) {
                        showStatus('Connection error. Please try again.');
                    }
                    chatSource.close();
                };
            })
            .catch(error => {
                console.error('Fetch error:', error);
                showStatus('Failed to send message');
            });
        }

        // Auto-expanding textarea
        document.getElementById('input').addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = (this.scrollHeight) + 'px';
        });

        document.getElementById('voice').addEventListener('mousedown', async () => {
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ 
                    audio: {
                        channelCount: 1,
                        sampleRate: 16000
                    }
                });
                
                mediaRecorder = new MediaRecorder(stream, {
                    mimeType: 'audio/webm;codecs=opus'
                });
                
                audioChunks = [];
                
                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };
                
                mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
                    const formData = new FormData();
                    formData.append('audio', audioBlob);
                    
                    try {
                        const response = await fetch('/transcribe', {
                            method: 'POST',
                            body: formData
                        });
                        const result = await response.json();
                        if (result.error) {
                            showStatus(result.error);
                        } else {
                            document.getElementById('input').value = result.text;
                            document.getElementById('input').focus();
                            // Trigger input event to adjust height
                            document.getElementById('input').dispatchEvent(new Event('input'));
                        }
                    } catch (error) {
                        showStatus('Transcription failed: ' + error);
                    } finally {
                        stream.getTracks().forEach(track => track.stop());
                    }
                };
                
                mediaRecorder.start();
                isRecording = true;
                document.getElementById('voice').classList.add('recording');
                showStatus('Recording...');
            } catch (error) {
                showStatus('Microphone error: ' + error);
            }
        });

        document.getElementById('voice').addEventListener('mouseup', () => {
            if (isRecording && mediaRecorder) {
                mediaRecorder.stop();
                isRecording = false;
                document.getElementById('voice').classList.remove('recording');
                showStatus('Processing...');
            }
        });

        document.getElementById('send').onclick = sendMessage;
        document.getElementById('input').onkeydown = (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        };

        function showStatus(message) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.style.display = 'block';
            setTimeout(() => {
                status.style.display = 'none';
            }, 3000);
        }

        // Keep session alive
        setInterval(() => {
            fetch('/ping').catch(() => {});
        }, 60000);
    </script>
</body>
</html>
'''

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>MAGI Login</title>
    <style>
        body {
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: #f0f0f0;
            font-family: system-ui, sans-serif;
        }
        form {
            background: white;
            padding: 2rem;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        input {
            display: block;
            margin: 1rem 0;
            padding: 0.5rem;
            width: 200px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            width: 100%;
            padding: 0.5rem;
            background: #1976d2;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover { background: #1565c0; }
        .error { color: #d32f2f; }
    </style>
</head>
<body>
    <form method="post" action="/login">
        <h2>MAGI Login</h2>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
        <input type="text" name="username" placeholder="Username" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Login</button>
    </form>
</body>
</html>
'''


def init_creds():
    """Initialize credentials file if it doesn't exist"""
    if not CREDS_FILE.exists():
        default_password = secrets.token_urlsafe(16)
        with open(CREDS_FILE, 'w') as f:
            f.write(f"admin:{generate_password_hash(default_password)}\n")
        print(f"\nCreated default credentials:")
        print(f"Username: admin")
        print(f"Password: {default_password}")
        print("Please change these credentials as soon as possible.\n")


def load_creds():
    """Load credentials from file"""
    creds = {}
    with open(CREDS_FILE) as f:
        for line in f:
            if ':' in line:
                username, password_hash = line.strip().split(':', 1)
                creds[username] = password_hash
    return creds

def login_required(f):
    """Decorator for requiring login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return render_template_string(LOGIN_HTML)
        return f(*args, **kwargs)
    return decorated_function

def create_ssl_cert():
    """Create self-signed certificate if it doesn't exist"""
    cert_file = SCRIPT_DIR / 'cert.pem'
    key_file = SCRIPT_DIR / 'key.pem'
    
    if not cert_file.exists() or not key_file.exists():
        from OpenSSL import crypto
        
        # Generate key
        k = crypto.PKey()
        k.generate_key(crypto.TYPE_RSA, 2048)
        
        # Generate self-signed certificate
        cert = crypto.X509()
        cert.get_subject().CN = "localhost"
        cert.set_serial_number(1000)
        cert.gmtime_adj_notBefore(0)
        cert.gmtime_adj_notAfter(10*365*24*60*60)  # 10 years
        cert.set_issuer(cert.get_subject())
        cert.set_pubkey(k)
        cert.sign(k, 'sha256')
        
        # Save certificate
        with open(cert_file, "wb") as f:
            f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
        with open(key_file, "wb") as f:
            f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k))
        
        print("\nCreated self-signed SSL certificate")


@app.route('/')
@login_required
def index():
    return render_template_string(HTML)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        creds = load_creds()
        
        if username in creds and check_password_hash(creds[username], password):
            session['username'] = username
            return render_template_string(HTML)
        
        return render_template_string(LOGIN_HTML, error='Invalid credentials')
    
    return render_template_string(LOGIN_HTML)


@app.route('/logout')
def logout():
    session.clear()
    return render_template_string(LOGIN_HTML)

@app.route('/models')
@login_required
def get_models():
    try:
        response = requests.get('http://localhost:11434/api/tags')
        if response.ok:
            models = response.json()['models']
            return jsonify(models)
        return jsonify([]), 500
    except Exception as e:
        print(f"Error fetching models: {e}")
        return jsonify([]), 500

@app.route('/speak', methods=['POST'])
@login_required
def speak():
    try:
        data = request.get_json()
        if not data:
            print("No JSON data received")
            return jsonify({'error': 'No data received'}), 400
        
        if 'text' not in data:
            print("No text field in JSON data")
            return jsonify({'error': 'No text field in request'}), 400
        
        text = data['text'].strip()
        if not text:
            print("Empty text after stripping")
            return jsonify({'error': 'Empty text'}), 400
            
        print(f"Received text for speech: {text[:100]}...")  # Print first 100 chars
        
        # Create unique filename
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"speech_{timestamp}_{text_hash}.wav"
        audio_path = AUDIO_DIR / filename
        
        # Write text to temporary file to avoid command line issues
        text_file = AUDIO_DIR / f"temp_{text_hash}.txt"
        with open(text_file, 'w', encoding='utf-8') as f:
            f.write(text)
        
        print(f"Generating speech to: {audio_path}")
        
        # Use text file as input
        cmd = [
            'espeak',
            '-v', 'en-us',
            '-s', '175',
            '-p', '50',
            '-f', str(text_file),
            '-w', str(audio_path)
        ]
        
        process = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero return
        )
        
        # Clean up text file
        text_file.unlink()
        
        if process.returncode != 0:
            print(f"Espeak failed with return code {process.returncode}")
            print(f"Stderr: {process.stderr}")
            return jsonify({'error': f'Speech generation failed: {process.stderr}'}), 500
            
        if not audio_path.exists():
            print("Audio file was not created")
            return jsonify({'error': 'Speech generation failed - no file created'}), 500
            
        if audio_path.stat().st_size == 0:
            print("Audio file is empty")
            audio_path.unlink()  # Clean up empty file
            return jsonify({'error': 'Speech generation failed - empty file'}), 500

        print(f"Successfully generated audio file of size {audio_path.stat().st_size} bytes")
        
        audio_url = f'/static/audio/{filename}'
        return jsonify({
            'url': audio_url,
            'size': audio_path.stat().st_size,
            'text': text[:50] + '...' if len(text) > 50 else text
        })
        
    except Exception as e:
        print(f"Exception in speak endpoint: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Add favicon route
@app.route('/favicon.ico')
def favicon():
    # Create a simple SVG favicon
    svg = '''<?xml version="1.0" encoding="UTF-8"?>
    <svg width="32" height="32" version="1.1" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
        <rect width="32" height="32" fill="#000"/>
        <circle cx="16" cy="16" r="12" fill="none" stroke="#ff9c00" stroke-width="2"/>
        <circle cx="16" cy="16" r="6" fill="#ff9c00"/>
    </svg>'''
    
    return Response(svg, mimetype='image/svg+xml')


@app.route('/ping')
@login_required
def ping():
    """Keep session alive"""
    return jsonify({'status': 'ok'})

@app.route('/transcribe', methods=['POST'])
@login_required
def transcribe():
    if 'audio' not in request.files:
        return jsonify({'error': 'No audio file'}), 400
    
    try:
        audio_file = request.files['audio']
        # Convert WebM audio to raw PCM data
        cmd = ['ffmpeg', '-i', '-', '-ac', '1', '-ar', '16000', '-f', 'f32le', '-']
        process = subprocess.Popen(
            cmd, 
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        
        # Send audio data to ffmpeg
        output, error = process.communicate(audio_file.read())
        
        if process.returncode != 0:
            print(f"FFmpeg error: {error.decode()}")
            return jsonify({'error': 'Audio conversion failed'}), 500
        
        # Convert to numpy array
        audio_data = np.frombuffer(output, dtype=np.float32)
        
        # Send to Whisper
        try:
            response = requests.post(
                'http://localhost:5000/transcribe',
                files={'audio': ('audio.wav', audio_data.tobytes())},
                timeout=30
            )
            
            if response.ok:
                result = response.json()
                return jsonify({'text': result['transcription']})
            else:
                print(f"Whisper error: {response.text}")
                return jsonify({'error': 'Transcription failed'}), 500
                
        except requests.exceptions.RequestException as e:
            print(f"Whisper request error: {e}")
            return jsonify({'error': 'Whisper service unavailable'}), 503
            
    except Exception as e:
        print(f"Transcription error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/stream')
@login_required
def stream():
    """SSE stream for real-time updates"""
    def generate():
        yield "data: {\"type\": \"connected\"}\n\n"
    return Response(generate(), mimetype='text/event-stream')

@app.route('/chat', methods=['GET', 'POST'])
@login_required
def chat():
    if request.method == 'POST':
        data = request.get_json()
        if not data or 'text' not in data:
            return jsonify({'error': 'No text provided'}), 400
        
        # Store the prompt and model in queue
        prompt_queue.put({
            'text': data['text'],
            'model': data.get('model', 'mistral')
        })
        return jsonify({'status': 'ok'})
    
    # GET method - handle streaming
    if request.method == 'GET':
        def generate_response():
            try:
                # Get prompt from queue
                data = prompt_queue.get(timeout=5)
                prompt = data['text']
                model = data['model']
                
                yield f"data: {json.dumps({'type': 'start'})}\n\n"
                
                response = requests.post(
                    'http://localhost:11434/api/generate',
                    json={
                        'model': model,
                        'prompt': prompt,
                        'stream': True
                    },
                    stream=True,
                    timeout=60
                )
                
                if not response.ok:
                    yield f"data: {json.dumps({'type': 'error', 'text': f'Ollama error: {response.status_code}'})}\n\n"
                    return
                
                for line in response.iter_lines():
                    if line:
                        try:
                            chunk = json.loads(line.decode())
                            if 'response' in chunk:
                                yield f"data: {json.dumps({'type': 'stream', 'text': chunk['response']})}\n\n"
                        except json.JSONDecodeError:
                            continue
                            
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                
            except queue.Empty:
                yield f"data: {json.dumps({'type': 'error', 'text': 'No prompt available'})}\n\n"
            except Exception as e:
                print(f"Error in generate_response: {e}")
                yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        
        response = Response(generate_response(), mimetype='text/event-stream')
        response.headers['Cache-Control'] = 'no-cache'
        response.headers['Connection'] = 'keep-alive'
        return response


def main():
    # Initialize credentials and SSL certificate
    init_creds()
    create_ssl_cert()
    
    # Start Flask with SSL
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(
        SCRIPT_DIR / 'cert.pem',
        SCRIPT_DIR / 'key.pem'
    )
    
    port = 8443
    print(f"\nStarting MAGI Web Interface on port {port}")
    print(f"Access at: https://localhost:{port}")
    print("Note: You'll need to accept the self-signed certificate warning in your browser")
    app.static_folder = str(STATIC_DIR)
    
    app.run(
        host='0.0.0.0',
        port=port,
        ssl_context=ssl_context,
        threaded=True
    )

if __name__ == "__main__":
    main()
