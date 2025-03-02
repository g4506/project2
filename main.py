from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import os
from google.cloud import speech
from google.cloud import texttospeech_v1
from google.protobuf import wrappers_pb2
# v1 from google.cloud import language_v1
from google.cloud import language_v2
app = Flask(__name__)

# Configure upload folder
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'wav'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Google Cloud clients
speech_client = speech.SpeechClient()
text_to_speech_client = texttospeech_v1.TextToSpeechClient()
# v1  language_client = language_v1.LanguageServiceClient()
language_client = language_v2.LanguageServiceClient()

# Utility function to check allowed file types
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Function for sentiment analysis
#def analyze_sentiment(text):
#    document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
#    response = language_client.analyze_sentiment(request={'document': document})
#    sentiment_score = response.document_sentiment.score
#    sentiment_magnitude = response.document_sentiment.magnitude

#    if sentiment_score > 0.2:
#        sentiment = 'Positive'
#    elif sentiment_score < -0.2:
#        sentiment = 'Negative'
#    else:
#        sentiment = 'Neutral'

#    return sentiment, sentiment_score, sentiment_magnitude

#def analyze_sentiment(text):
 #   document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
  #  response = language_client.analyze_sentiment(request={'document': document})
    
   # sentiment_score = response.document_sentiment.score
    #sentiment_magnitude = response.document_sentiment.magnitude

    # New logic to capture mixed sentiments better
    #if sentiment_magnitude >= 0.3 and -0.3 <= sentiment_score <= 0.8
     #   sentiment = 'Mixed'
    #elif sentiment_score > 0.2:
     #   sentiment = 'Positive'
    #elif sentiment_score < -0.2:
     #   sentiment = 'Negative'
    #else:
     #   sentiment = 'Neutral'

    #return sentiment, sentiment_score, sentiment_magnitude
def analyze_sentiment(text):
    # V1  document = language_v1.Document(content=text, type_=language_v1.Document.Type.PLAIN_TEXT)
    document = language_v2.Document(content=text, type_=language_v2.Document.Type.PLAIN_TEXT)
    
    response = language_client.analyze_sentiment(request={'document': document})
    sentiment_score = response.document_sentiment.score
    sentiment_magnitude = response.document_sentiment.magnitude
    #print(f"Document sentiment score: {response.document_sentiment.score}")
    #print(f"Document sentiment magnitude: {response.document_sentiment.magnitude}")
   # Calculate Sentiment Strength
    sentiment_strength = sentiment_score * sentiment_magnitude

    # Classify sentiment based on strength
    if sentiment_strength > 0.75:
        sentiment = 'Positive'
    elif sentiment_strength < -0.75:
        sentiment = 'Negative'
    else:
        sentiment = 'Neutral'

    return sentiment, sentiment_score, sentiment_magnitude 
   










# Function to list files in the upload folder
def get_files():
    files = []
    tts_files = []
    
    for filename in os.listdir(UPLOAD_FOLDER):
        if allowed_file(filename):
            files.append(filename)
            
    tts_folder = os.path.join(UPLOAD_FOLDER, 'tts')
    if os.path.exists(tts_folder):
        for filename in os.listdir(tts_folder):
            if allowed_file(filename):
                tts_files.append(f'tts/{filename}')
    
    files.sort(reverse=True)
    tts_files.sort(reverse=True)
    return files + tts_files

# Route to the home page
@app.route('/')
def index():
    files = get_files()
    sentiment_results = []
    
    for file in files:
        if file.endswith('.txt'):
            with open(os.path.join(UPLOAD_FOLDER, file), 'r') as f:
                transcript = f.read()
            sentiment, _, _ = analyze_sentiment(transcript)
            sentiment_results.append(f"Sentiment for {file}: {sentiment}")

    return render_template('index.html', files=files, sentiment_results=sentiment_results)

# Route to upload audio
@app.route('/upload', methods=['POST'])
def upload_audio():
    if 'audio_data' not in request.files:
        flash('No audio data')
        return redirect(request.url)

    file = request.files['audio_data']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file:
        # Generate a unique filename based on the current timestamp
        filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        # Call the Google Cloud Speech-to-Text API and save the transcript
        with open(file_path, 'rb') as f:
            audio_content = f.read()

        # Recognize speech
        audio = speech.RecognitionAudio(content=audio_content)
        config = speech.RecognitionConfig(
            language_code="en-US",
            audio_channel_count=1,
            enable_word_confidence=True,
            enable_word_time_offsets=True,
        )
        operation = speech_client.long_running_recognize(config=config, audio=audio)
#### try this response = operation.result(timeout=90)
        try:
          response = operation.result(timeout=90)
        except Exception as e:
          flash(f"Error processing audio: {str(e)}")
          return redirect(url_for('index'))       


########
       # Debugging: Print the response to check transcription
        #print("Speech-to-Text API Response:", response)
        
        # Save the transcript
        transcript = "\n".join([result.alternatives[0].transcript for result in response.results])
       # ✅ Debugging: Print the transcript before saving
        #print("Extracted Transcript:", transcript)
        transcript_file = file_path + '.txt'
        #print(f"Saving transcript to: {transcript_file}")
        with open(transcript_file, 'w') as f:
            f.write(transcript)

        # Analyze sentiment for the transcript
        sentiment, sentiment_score, sentiment_magnitude = analyze_sentiment(transcript)
        #sentiment, sentiment_score, sentiment_magnitude, sentiment_strength = analyze_sentiment(text)
        


        # Save sentiment result in the same file or a new file
        #sentiment_file = file_path + '_sentiment.txt'
        #sentiment_file = os.path.join(app.config['UPLOAD_FOLDER'], filename + '_sentiment.txt')
        #sentiment_file = os.path.join(app.config['UPLOAD_FOLDER'], filename.replace('.wav', '') + '_sentiment.txt')
        sentiment_file = os.path.join(app.config['UPLOAD_FOLDER'], filename[:-4] + '_sentiment.txt')  # Remove '.wav'

        with open(sentiment_file, 'w') as f:
            f.write(f"Sentiment: {sentiment}\nSentiment Score: {sentiment_score}\nSentiment Magnitude: {sentiment_magnitude}")
        

        # Optionally save sentiment in the same text file as the transcript
        with open(transcript_file, 'a') as f:
            f.write(f"\nSentiment: {sentiment}\nSentiment Score: {sentiment_score}\nSentiment Magnitude: {sentiment_magnitude}")

    return redirect('/')  # Redirect back to the index

# Route to serve the uploaded file
#@app.route('/uploads/<path:filename>')
#def uploaded_file(filename):
 #   return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    # Log file path for debugging
    #print(f"Requesting file: {file_path}")
    
    # Check if file exists before serving
    if os.path.exists(file_path):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    else:
        return "File not found", 404





# Route to upload text for TTS (Text-to-Speech)
@app.route('/upload_text', methods=['POST'])
def upload_text():
    text = request.form['text']

    # Perform Sentiment Analysis
    sentiment, sentiment_score, sentiment_magnitude = analyze_sentiment(text)

    # Save the sentiment result
    sentiment_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '_text_sentiment.txt'
    sentiment_path = os.path.join(app.config['UPLOAD_FOLDER'], sentiment_filename)

    with open(sentiment_path, 'w') as f:
        f.write(f"Original Text: {text}\n")
        f.write(f"Sentiment: {sentiment}\nSentiment Score: {sentiment_score}\nSentiment Magnitude: {sentiment_magnitude}")

    # Call Google Cloud Text-to-Speech API (existing logic)
    synthesis_input = texttospeech_v1.SynthesisInput(text=text)
    voice = texttospeech_v1.VoiceSelectionParams(
        language_code="en-UK", ssml_gender=texttospeech_v1.SsmlVoiceGender.MALE
    )
    audio_config = texttospeech_v1.AudioConfig(audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16)
    response = text_to_speech_client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )

    # Save the TTS audio file
    tts_filename = datetime.now().strftime("%Y%m%d-%I%M%S%p") + '.wav'
    tts_path = os.path.join(app.config['UPLOAD_FOLDER'], 'tts', tts_filename)
    os.makedirs(os.path.dirname(tts_path), exist_ok=True)

    with open(tts_path, 'wb') as out:
        out.write(response.audio_content)

    return redirect('/')  # Redirect to home page after saving


# Serve static JS file
@app.route('/scripts.js', methods=['GET'])
def scripts_js():
    return send_from_directory('.', 'script.js')

if __name__ == '__main__':
    #app.run(debug=True, port=5000)
    app.run(host="0.0.0.0", port=8080)
 
    #port = int(os.environ.get("PORT", 8080))  # Use Cloud Run's default port
    #app.run(debug=True, host="0.0.0.0", port=port)