"""
cute_voice_assistant_gui.py
A cute Tkinter GUI voice assistant using VOSK (offline STT) and pyttsx3 (offline TTS).

Features:
- Pastel, rounded-button aesthetic "cute" GUI
- Start/Stop listening button
- Live transcript area
- Assistant speaks replies using pyttsx3 (offline)
- Simple command handling: add task, list tasks, screenshot, open chrome, tell time, exit
- Runs VOSK in a background thread with sounddevice

Setup:
1) Create a folder and place this script inside it.
2) Download and unzip a VOSK model (small English):
   https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip
   Rename the extracted folder to `model` and put it next to this script.
3) Install dependencies:
   pip install vosk sounddevice pyttsx3 Pillow pyautogui

Run:
   python cute_voice_assistant_gui.py

Notes:
- Designed for Windows; should also work on macOS/Linux with small changes (winsound removed).
- If sounddevice installation fails, try using wheels or using the earlier file-based fallback.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import time
import json
import webbrowser
import datetime
import os
import pyautogui

# STT/TTS imports
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import pyttsx3

# ---------- Configuration ----------
MODEL_PATH = "model"  # folder name of vosk model
SAMPLE_RATE = 16000

# ---------- Voice (TTS) ----------
engine = pyttsx3.init()
engine.setProperty('rate', 160)
engine.setProperty('volume', 1.0)

def speak(text: str):
    """Speak text asynchronously to avoid blocking the GUI."""
    def _s():
        engine.say(text)
        engine.runAndWait()
    threading.Thread(target=_s, daemon=True).start()

# ---------- Vosk STT (background thread) ----------
audio_q = queue.Queue()
text_q = queue.Queue()
listening_flag = threading.Event()

try:
    vosk_model = Model(MODEL_PATH)
except Exception as e:
    vosk_model = None

recognizer = None
if vosk_model:
    recognizer = KaldiRecognizer(vosk_model, SAMPLE_RATE)


def sd_callback(indata, frames, time_info, status):
    if status:
        print("SoundDevice status:", status)
    audio_q.put(bytes(indata))


def stt_worker():
    """Background worker: consumes audio bytes and pushes recognized text to text_q."""
    global recognizer
    try:
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16', channels=1, callback=sd_callback):
            while True:
                listening_flag.wait()  # blocks until listening_flag is set
                try:
                    data = audio_q.get()
                except Exception:
                    continue
                if recognizer.AcceptWaveform(data):
                    res = json.loads(recognizer.Result())
                    txt = res.get('text', '').strip()
                    if txt:
                        text_q.put(txt)
                # else: partial results ignored to avoid spam
    except Exception as e:
        print('STT worker error:', e)

# Start STT worker thread
stt_thread = threading.Thread(target=stt_worker, daemon=True)
stt_thread.start()

# ---------- Simple command handling ----------
tasks = []


def handle_command(cmd: str, gui_append_fn):
    """Process recognized command and produce responses."""
    cmd = cmd.lower()
    gui_append_fn(f"You: {cmd}\n")

    if 'add task' in cmd or cmd.startswith('add'):
        speak('What is the task?')
        gui_append_fn('Assistant: What is the task?\n')
        # Next recognized phrase will be taken as task by the main loop
        return ('awaiting_task', None)

    if 'list tasks' in cmd or 'show tasks' in cmd:
        if tasks:
            for t in tasks:
                gui_append_fn(f"Assistant: {t}\n")
                speak(t)
        else:
            gui_append_fn('Assistant: You have no tasks.\n')
            speak('You have no tasks.')
        return ('done', None)

    if 'screenshot' in cmd or 'take a screenshot' in cmd:
        path = os.path.join(os.getcwd(), f'screenshot_{int(time.time())}.png')
        pyautogui.screenshot(path)
        gui_append_fn(f'Assistant: Screenshot saved to {path}\n')
        speak('Screenshot taken for you.')
        return ('done', None)

    if 'open chrome' in cmd or 'open browser' in cmd:
        gui_append_fn('Assistant: Opening browser.\n')
        speak('Opening browser')
        webbrowser.open('https://www.google.com')
        return ('done', None)

    if 'time' in cmd or "what's the time" in cmd or 'current time' in cmd:
        now = datetime.datetime.now().strftime('%I:%M %p')
        gui_append_fn(f'Assistant: The time is {now}\n')
        speak(f'The time is {now}')
        return ('done', None)

    if 'exit' in cmd or 'quit' in cmd or 'goodbye' in cmd:
        gui_append_fn('Assistant: Goodbye!\n')
        speak('Goodbye')
        return ('exit', None)

    # If we reach here, not understood
    gui_append_fn("Assistant: I didn't understand that. Try again.\n")
    speak("I didn't understand that. Try again.")
    return ('done', None)

# ---------- Cute GUI (Tkinter) ----------
class CuteAssistantGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('✨ Cutie Assistant ✨')
        self.configure(bg='#FFF8F0')
        self.geometry('520x600')
        self.resizable(False, False)

        # Styling
        style = ttk.Style(self)
        style.configure('TButton', font=('Helvetica', 11, 'bold'))

        # Header
        header = tk.Label(self, text='Cutie Assistant', font=('Comic Sans MS', 20, 'bold'), bg='#FFF8F0', fg='#7B3F00')
        header.pack(pady=(12,6))

        subtitle = tk.Label(self, text='Your friendly offline voice buddy 💖', font=('Helvetica', 10), bg='#FFF8F0')
        subtitle.pack()

        # Frame for buttons
        btn_frame = tk.Frame(self, bg='#FFF8F0')
        btn_frame.pack(pady=12)

        self.listen_btn = tk.Button(btn_frame, text='Start Listening', command=self.toggle_listen, bd=0, bg='#FFDFE4', fg='#7B2D2D', padx=14, pady=8)
        self.listen_btn.grid(row=0, column=0, padx=8)

        self.stop_btn = tk.Button(btn_frame, text='Stop', command=self.stop_listen, bd=0, bg='#E6F7FF', fg='#0A4A6B', padx=14, pady=8)
        self.stop_btn.grid(row=0, column=1, padx=8)

        save_btn = tk.Button(btn_frame, text='Save Tasks', command=self.save_tasks, bd=0, bg='#FFF2BF', fg='#6B4A00', padx=10, pady=8)
        save_btn.grid(row=0, column=2, padx=8)

        # Transcript box
        self.transcript = scrolledtext.ScrolledText(self, wrap=tk.WORD, width=58, height=18, font=('Helvetica', 10))
        self.transcript.pack(padx=12, pady=(8,16))
        self.transcript.insert(tk.END, 'Assistant: Ready. Click Start Listening to begin.\n')
        self.transcript.configure(state='disabled')

        tips = tk.Label(
            self,
            text="Try: add task, list tasks, screenshot, open chrome, what's the time",
            bg='#FFF8F0',
            font=('Helvetica', 9),
            fg='#444'
        )
        tips.pack(pady=(0,12))


        self.awaiting_task = False
        self.after(200, self.check_text_queue)

        # Closing behavior
        self.protocol('WM_DELETE_WINDOW', self.on_close)

    def append_transcript(self, text: str):
        self.transcript.configure(state='normal')
        self.transcript.insert(tk.END, text)
        self.transcript.see(tk.END)
        self.transcript.configure(state='disabled')

    def toggle_listen(self):
        if not vosk_model:
            messagebox.showerror('Model missing', 'VOSK model not found. Put model folder next to script.')
            return
        if listening_flag.is_set():
            self.stop_listen()
        else:
            listening_flag.set()
            self.listen_btn.config(text='Listening...', bg='#DFF7E0')
            self.append_transcript('Assistant: Listening...\n')

    def stop_listen(self):
        listening_flag.clear()
        self.listen_btn.config(text='Start Listening', bg='#FFDFE4')
        self.append_transcript('Assistant: Stopped listening.\n')

    def save_tasks(self):
        try:
            with open('tasks.txt', 'w', encoding='utf-8') as f:
                for t in tasks:
                    f.write(t + '\n')
            messagebox.showinfo('Saved', 'Tasks saved to tasks.txt')
        except Exception as e:
            messagebox.showerror('Error', str(e))

    def check_text_queue(self):
        """Poll text_q for new recognized text and handle it."""
        try:
            while not text_q.empty():
                txt = text_q.get_nowait()
                if self.awaiting_task:
                    tasks.append(txt)
                    self.append_transcript(f'Assistant: Added task: {txt}\n')
                    speak('Task added')
                    self.awaiting_task = False
                else:
                    result_state, _ = handle_command(txt, self.append_transcript)
                    if result_state == 'awaiting_task':
                        self.awaiting_task = True
                    elif result_state == 'exit':
                        self.on_close()
        except Exception as e:
            print('Queue check error:', e)
        finally:
            self.after(200, self.check_text_queue)

    def on_close(self):
        if messagebox.askokcancel('Quit', 'Do you want to quit?'):
            listening_flag.clear()
            self.destroy()


if __name__ == '__main__':
    app = CuteAssistantGUI()
    app.mainloop()
