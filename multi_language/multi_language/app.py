from flask import Flask, render_template, request, jsonify, send_from_directory, session
from deep_translator import GoogleTranslator
from gtts import gTTS
import os
import uuid
import google.generativeai as genai
import json

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/audio'

# Allowed languages
allowed_languages = {'en', 'hi', 'mr', 'kn', 'gu', 'ml', 'de', 'fr'}
gtts_supported = {
    'af', 'ar', 'bn', 'bs', 'ca', 'cs', 'cy', 'da', 'de', 'el', 'en', 'eo', 'es',
    'et', 'fi', 'fr', 'gu', 'hi', 'hr', 'hu', 'hy', 'id', 'is', 'it', 'ja', 'jw',
    'km', 'kn', 'ko', 'la', 'lv', 'ml', 'mr', 'ms', 'my', 'ne', 'nl', 'no', 'pl',
    'pt', 'ro', 'ru', 'si', 'sk', 'sq', 'sr', 'su', 'sv', 'sw', 'ta', 'te', 'th',
    'tl', 'tr', 'uk', 'ur', 'vi', 'zh-CN', 'zh-TW'
}


@app.route('/')
def index():
    session.setdefault('history', [])
    return render_template('index.html')


@app.route('/translate', methods=['POST'])
def translate():
    text = request.form.get('text', '').strip()
    language = request.form.get('language', 'en')
    play_audio = request.form.get('playAudio') == 'true'

    if not text:
        return jsonify({'translated': 'Error: No text provided.'})

    try:
        translated = GoogleTranslator(source='auto', target=language).translate(text)
        audio_path = ''

        if play_audio and language in gtts_supported:
            tts = gTTS(text=translated, lang=language)
            filename = f"{uuid.uuid4()}.mp3"
            full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            tts.save(full_path)
            audio_path = f"/static/audio/{filename}"

        return jsonify({'translated': translated, 'audio_path': audio_path})

    except Exception as e:
        return jsonify({'translated': f"Error: {str(e)}"})


@app.route('/translate-multi', methods=['POST'])
def translate_multi():
    data = request.get_json()
    text = data.get('text', '').strip()
    selected_languages = data.get('languages', [])
    play_audio = data.get('playAudio', False)

    if not text or not selected_languages:
        return jsonify({'error': 'No text or languages provided.'}), 400

    results = []
    history = session.get('history', [])

    try:
        for lang in selected_languages:
            translated = GoogleTranslator(source='auto', target=lang).translate(text)
            audio_file = ''

            if play_audio and lang in gtts_supported:
                tts = gTTS(text=translated, lang=lang)
                filename = f"{uuid.uuid4()}.mp3"
                full_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                tts.save(full_path)
                audio_file = f"/static/audio/{filename}"

            results.append({
                'language': lang,
                'translated_text': translated,
                'audio_path': audio_file
            })

            # Store in session history
            history.insert(0, {
                'target_lang': lang,
                'original_text': text,
                'translated_text': translated,
                'audio_file': os.path.basename(audio_file) if audio_file else ''
            })

        session['history'] = history
        return jsonify(results)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/history')
def show_history():
    selected_lang = request.args.get('lang')
    history = session.get('history', [])

    if selected_lang:
        history = [entry for entry in history if entry['target_lang'] == selected_lang]

    available_languages = sorted(set(item['target_lang'] for item in session.get('history', [])))

    return render_template('history.html',
                           history=history,
                           languages=available_languages,
                           selected_lang=selected_lang)


@app.route('/static/audio/<filename>')
def get_audio(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


# --- Gemini Chatbot Setup ---

# Configure Generative AI
try:
    # Use your actual API key here. It's best practice to load this from an environment variable.
    genai.configure(api_key="AIzaSyCfuw8a1pX3oBGg8BWkThCnFGpYVgrTj4U")
except Exception as e:
    print(f"API Key configuration error: {e}")
    # In a production app, you might want to log this and indicate a service outage.
    # For now, we'll let the app run but the chatbot won't work.
    pass


model = None

try:
    model = genai.GenerativeModel('gemini-2.0-flash')
except Exception as e:
    print(f"Error initializing model: {e}")
    pass

chat = None
if model:
    chat = model.start_chat(history=[])


# Route to serve the chatbot interface (chatbot.html)
@app.route('/chatbot')
def chatbot_interface():
    return render_template('chatbot.html')

# Route to handle chat messages
@app.route('/chat', methods=['POST'])
def handle_chat():
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    if chat: # Check if the chat object was successfully initialized
        try:
            response = chat.send_message(user_message)
            return jsonify({'response': response.text})
        except Exception as e:
            return jsonify({"error": f"Error interacting with AI: {str(e)}"}), 500
    else:
        return jsonify({"error": "Chatbot is not initialized. Check server logs for API key or model issues."}), 500



if __name__ == '__main__':
    app.run(debug=True)
