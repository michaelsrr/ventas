from flask import Flask, render_template, request, jsonify
import speech_recognition as sr
import os
import subprocess
from werkzeug.utils import secure_filename
import spacy
from gtts import gTTS
import pygame  # Agregado para reproducción de audio
import time

app = Flask(__name__)

# Configura la carpeta de uploads
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def convert_to_wav(input_path, output_path):
    """Convertir el archivo de audio a WAV PCM usando FFmpeg"""
    try:
        command = [
            'ffmpeg', '-i', input_path, '-acodec', 'pcm_s16le', '-ar', '16000',
            '-ac', '1', output_path
        ]
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error al convertir el archivo de audio: {e}")
        raise

# Cargar el modelo de lenguaje en español
nlp = spacy.load("es_core_news_sm")

# Definir las etapas y las frases clave de la conversación
conversacion = [
    {
        "etapa": 1,
        "frases": [
            {"texto": "es un gusto tenerlo en crea", "palabras_claves": ["gusto", "tenerlo", "crea"]}
        ]
    },
    {
        "etapa": 2,
        "frases": [
            {"texto": "mi nombre es", "palabras_claves": ["nombre"]}
        ]
    },
    # Puedes agregar más etapas aquí
]

def speak(text):
    tts = gTTS(text, lang="es")
    tts.save("response.mp3")

    # Inicializar pygame mixer
    pygame.mixer.init()
    pygame.mixer.music.load("response.mp3")
    pygame.mixer.music.play()

    # Esperar hasta que el audio termine de reproducirse
    while pygame.mixer.music.get_busy():
        pygame.time.Clock().tick(10)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/record', methods=['POST'])
def record():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and allowed_file(file.filename):
        filename = secure_filename('recording.wav')
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Verificar y guardar el archivo
        try:
            file.save(file_path)
            print(f"File saved to {file_path}")  # Mensaje de depuración
        except Exception as e:
            return jsonify({"error": f"Error saving file: {str(e)}"}), 500

        # Archivo convertido
        converted_file_path = os.path.join(app.config['UPLOAD_FOLDER'], 'converted.wav')
        
        # Convertir el archivo a WAV PCM
        try:
            convert_to_wav(file_path, converted_file_path)
            print(f"File converted to {converted_file_path}")  # Mensaje de depuración
        except Exception as e:
            return jsonify({"error": f"Error converting file: {str(e)}"}), 500
        
        # Procesar el archivo de audio convertido
        recognizer = sr.Recognizer()
        try:
            with sr.AudioFile(converted_file_path) as source:
                audio = recognizer.record(source)
                text = recognizer.recognize_google(audio, language="es-ES").strip().lower()

                # Verificar la conversación
                etapa_actual = 1  # Inicialmente en la etapa 1
                response_text = "La frase no fue reconocida correctamente. Intentando nuevamente."
                continuar = False  # Para indicar si debe continuar o reintentar

                # Buscar la frase correcta en la etapa actual
                for etapa_info in conversacion:
                    if etapa_info["etapa"] == etapa_actual:
                        for frase_info in etapa_info["frases"]:
                            frase = frase_info["texto"].strip().lower()

                            # Comparación directa de frases
                            if frase == text:
                                etapa_actual += 1  # Avanzar a la siguiente etapa
                                response_text = "Frase reconocida correctamente. Por favor, diga la siguiente frase: " + conversacion[etapa_actual-1]["frases"][0]["texto"]
                                continuar = True
                                break
                        
                        # Si se reconoce la frase correctamente, salir del bucle
                        if continuar:
                            break

                speak(response_text)
                return jsonify({"text": text, "response": response_text, "continuar": continuar, "etapa": etapa_actual})

        except sr.UnknownValueError:
            return jsonify({"error": "No se pudo entender el audio"}), 400
        except sr.RequestError:
            return jsonify({"error": "Error de conexión con el servicio de reconocimiento"}), 500
        except Exception as e:
            return jsonify({"error": f"Error processing audio: {str(e)}"}), 500
    else:
        return jsonify({"error": "Formato de archivo no permitido"}), 400

if __name__ == '__main__':
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    app.run(debug=True)