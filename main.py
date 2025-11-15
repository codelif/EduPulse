from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QFormLayout, QGroupBox,
    QScrollArea, QStackedWidget, QFrame, QCheckBox, QSpinBox,
    QListWidget, QListWidgetItem, QSpacerItem, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
import sys
import time
import requests
import json
from datetime import datetime
from agora2 import AgoraSeleniumVoiceClient, start_ai_agent

# Gmail imports
import imaplib
import email
from email.header import decode_header
import os

# Google Classroom imports
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle


# ============== SETTINGS MANAGER ==============

class SettingsManager:
    """Manages loading and saving settings to settings.json"""
    
    SETTINGS_FILE = "settings.json"
    
    DEFAULT_SETTINGS = {
        "email": {
            "imap_host": "imap.gmail.com",
            "username": "",
            "password": ""
        },
        "agora": {
            "app_id": "",
            "channel": "pa_channel",
            "token": "",
            "openai_key": "",
            "authorization": "",
            "headless": True
        },
        "polling": {
            "email_interval": 60,
            "classroom_interval": 60
        },
        "audio": {
            "default_language": "English",
            "auto_broadcast": False
        }
    }
    
    @classmethod
    def load_settings(cls):
        """Load settings from file or create default"""
        if os.path.exists(cls.SETTINGS_FILE):
            try:
                with open(cls.SETTINGS_FILE, 'r') as f:
                    loaded = json.load(f)
                    # Merge with defaults to handle new keys
                    settings = cls.DEFAULT_SETTINGS.copy()
                    cls._deep_update(settings, loaded)
                    return settings
            except Exception as e:
                print(f"Error loading settings: {e}")
                return cls.DEFAULT_SETTINGS.copy()
        else:
            # Create default settings file
            cls.save_settings(cls.DEFAULT_SETTINGS)
            return cls.DEFAULT_SETTINGS.copy()
    
    @classmethod
    def save_settings(cls, settings):
        """Save settings to file"""
        try:
            with open(cls.SETTINGS_FILE, 'w') as f:
                json.dump(settings, f, indent=4)
            return True
        except Exception as e:
            print(f"Error saving settings: {e}")
            return False
    
    @classmethod
    def _deep_update(cls, base_dict, update_dict):
        """Recursively update nested dictionaries"""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict:
                cls._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value


# ============== GMAIL POLLER ==============

class GmailPollerThread(QThread):
    new_email = pyqtSignal(dict)
    
    def __init__(self, settings, poll_interval=60):
        super().__init__()
        self.imap_host = settings['email']['imap_host']
        self.username = settings['email']['username']
        self.password = settings['email']['password']
        self.poll_interval = poll_interval
        self.running = True
        self.last_uid = self.load_last_uid()
        
    def load_last_uid(self):
        state_file = "last_uid.txt"
        if not os.path.exists(state_file):
            return None
        with open(state_file, "r") as f:
            value = f.read().strip()
            return int(value) if value else None
    
    def save_last_uid(self, uid):
        with open("last_uid.txt", "w") as f:
            f.write(str(uid))
    
    def parse_email(self, msg):
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding or "utf-8", errors="ignore")

        from_, enc = decode_header(msg.get("From"))[0]
        if isinstance(from_, bytes):
            from_ = from_.decode(enc or "utf-8", errors="ignore")

        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in disposition:
                    body = part.get_payload(decode=True).decode(errors="ignore")
                    break
                elif content_type == "text/html" and "attachment" not in disposition:
                    body = part.get_payload(decode=True).decode(errors="ignore")
        else:
            body = msg.get_payload(decode=True).decode(errors="ignore")

        return subject, from_, body
    
    def check_new_mail(self):
        if not self.username or not self.password:
            print("Gmail credentials not configured")
            return
            
        try:
            M = imaplib.IMAP4_SSL(self.imap_host)
            M.login(self.username, self.password)
            M.select("INBOX")

            if self.last_uid is None:
                typ, data = M.uid("search", None, "ALL")
                if typ == "OK" and data[0]:
                    uids = data[0].split()
                    max_uid = int(uids[-1])
                    self.save_last_uid(max_uid)
                    self.last_uid = max_uid
                M.close()
                M.logout()
                return

            search_criteria = f"(UID {self.last_uid + 1}:*)"
            typ, data = M.uid("search", None, search_criteria)

            if typ != "OK" or not data[0]:
                M.close()
                M.logout()
                return

            uids = data[0].split()
            max_uid_seen = self.last_uid

            for uid in uids:
                uid_int = int(uid)
                if uid_int <= self.last_uid:
                    continue

                typ, msg_data = M.uid("fetch", uid, "(RFC822)")
                if typ != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)
                subject, from_, body = self.parse_email(msg)

                self.new_email.emit({
                    'subject': subject,
                    'from': from_,
                    'body': body,
                    'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                })

                if uid_int > max_uid_seen:
                    max_uid_seen = uid_int

            self.save_last_uid(max_uid_seen)
            self.last_uid = max_uid_seen

            M.close()
            M.logout()
            
        except Exception as e:
            print(f"Gmail error: {e}")
    
    def run(self):
        while self.running:
            self.check_new_mail()
            time.sleep(self.poll_interval)
    
    def stop(self):
        self.running = False


# ============== GOOGLE CLASSROOM POLLER ==============

class ClassroomPollerThread(QThread):
    new_announcement = pyqtSignal(dict)
    
    def __init__(self, poll_interval=60):
        super().__init__()
        self.poll_interval = poll_interval
        self.running = True
        self.scopes = [
            'https://www.googleapis.com/auth/classroom.courses.readonly',
            'https://www.googleapis.com/auth/classroom.announcements.readonly'
        ]
        self.token_file = 'token.pickle'
        self.credentials_file = 'credentials.json'
        self.timestamp_file = 'last_timestamp.txt'
        self.service = None
        self.last_ts = self.load_last_timestamp()
        
    def load_last_timestamp(self):
        if not os.path.exists(self.timestamp_file):
            return None
        try:
            with open(self.timestamp_file, 'r') as f:
                return float(f.read().strip())
        except:
            return None
    
    def save_last_timestamp(self, ts):
        with open(self.timestamp_file, 'w') as f:
            f.write(str(ts))
    
    def iso_to_timestamp(self, iso_string):
        try:
            dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
            return dt.timestamp()
        except:
            return 0
    
    def authenticate(self):
        creds = None
        if os.path.exists(self.token_file):
            with open(self.token_file, 'rb') as token:
                creds = pickle.load(token)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes)
                creds = flow.run_local_server(port=0)
            with open(self.token_file, 'wb') as token:
                pickle.dump(creds, token)

        return build('classroom', 'v1', credentials=creds)
    
    def check_announcements(self, service, course_id, course_name, last_ts):
        try:
            results = service.courses().announcements().list(
                courseId=course_id,
                orderBy='updateTime desc',
                pageSize=10
            ).execute()

            announcements = results.get('announcements', [])
            latest_ts = last_ts if last_ts else 0

            for ann in announcements:
                ts = self.iso_to_timestamp(ann.get("updateTime", ""))
                latest_ts = max(latest_ts, ts)

                if last_ts and ts > last_ts:
                    self.new_announcement.emit({
                        'course_name': course_name,
                        'text': ann.get('text', ''),
                        'creation_time': ann.get('creationTime', '')
                    })

            return latest_ts

        except HttpError as e:
            print(f"Classroom error: {e}")
            return last_ts
    
    def check_classroom_updates(self):
        try:
            if not self.service:
                self.service = self.authenticate()
            
            first_run = self.last_ts is None
            
            results = self.service.courses().list(pageSize=100).execute()
            courses = results.get('courses', [])

            if not courses:
                return

            latest_timestamp_found = self.last_ts or 0

            for course in courses:
                course_id = course['id']
                course_name = course['name']

                course_latest_ts = self.check_announcements(
                    self.service, course_id, course_name, self.last_ts)

                latest_timestamp_found = max(latest_timestamp_found, course_latest_ts)

            self.save_last_timestamp(latest_timestamp_found)
            self.last_ts = latest_timestamp_found

        except Exception as e:
            print(f"Classroom update error: {e}")
    
    def run(self):
        while self.running:
            self.check_classroom_updates()
            time.sleep(self.poll_interval)
    
    def stop(self):
        self.running = False


# ============== AGORA INTEGRATION ==============

# Update only the relevant parts - keep everything else the same

# ============== AGORA INTEGRATION ==============

class AgoraInitThread(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    status_update = pyqtSignal(str)  # NEW: For progress updates
    
    def __init__(self, config):
        super().__init__()
        self.config = config
        
    def run(self):
        try:
            self.status_update.emit("Starting Agora agent...")
            
            # Validate required fields
            required_fields = ['APP_ID', 'CHANNEL', 'TOKEN', 'OPENAI_KEY', 'AUTHORIZATION']
            missing = [f for f in required_fields if not self.config.get(f)]
            
            if missing:
                self.error.emit(f"Missing required settings: {', '.join(missing)}")
                return
            
            # Start AI agent
            self.status_update.emit("Connecting to Agora API...")
            agent_response = start_ai_agent(
                self.config['APP_ID'],
                "",  # customer_id - not used
                "",  # customer_secret - not used
                self.config['CHANNEL'],
                self.config['TOKEN'],
                "1001",  # agent_uid - fixed
                "1002",  # user_uid - fixed
                self.config['OPENAI_KEY'],
                "",  # azure_key - not used
                "eastus",  # azure_region - not used
                self.config['AUTHORIZATION']
            )
            
            # Check for errors in response
            if not agent_response:
                self.error.emit("No response from Agora API")
                return
                
            if "code" in agent_response and agent_response["code"] != 0:
                error_msg = agent_response.get("message", "Unknown error")
                reason = agent_response.get("reason", "")
                full_error = f"{error_msg}" + (f": {reason}" if reason else "")
                self.error.emit(f"Agora API error - {full_error}")
                print(f"Full Agora response: {agent_response}")
                return
            
            status = agent_response.get("status")
            if status not in ["STARTING", "RUNNING"]:
                reason = agent_response.get("reason", "Unknown reason")
                self.error.emit(f"Agent failed to start. Status: {status}, Reason: {reason}")
                print(f"Full Agora response: {agent_response}")
                return
            
            agent_id = agent_response.get("agent_id")
            if not agent_id:
                self.error.emit("No agent_id in response")
                print(f"Full Agora response: {agent_response}")
                return
            
            self.status_update.emit(f"Agent started (ID: {agent_id}), initializing voice client...")
            time.sleep(5)
            
            # Start voice client
            self.status_update.emit("Starting voice client...")
            client = AgoraSeleniumVoiceClient(
                app_id=self.config['APP_ID'],
                channel=self.config['CHANNEL'],
                token=self.config['TOKEN'],
                uid="1002",
                agent_uid="1001",
                headless=self.config.get('HEADLESS', True)
            )
            client.start()
            
            agent_response['_client'] = client
            self.status_update.emit("Connected successfully!")
            self.finished.emit(agent_response)
            
        except requests.exceptions.RequestException as e:
            self.error.emit(f"Network error: {str(e)}")
            print(f"Network error details: {e}")
        except Exception as e:
            self.error.emit(f"Initialization error: {str(e)}")
            print(f"Error details: {e}")
            import traceback
            traceback.print_exc()


class AgoraManager:
    def __init__(self, config):
        self.config = config
        self.agent_id = None
        self.client = None
        self.is_initialized = False
        self.status_callback = None
        
    def initialize(self, on_success, on_error, on_status=None):
        self.status_callback = on_status
        self.init_thread = AgoraInitThread(self.config)
        self.init_thread.finished.connect(lambda resp: self._on_init_success(resp, on_success))
        self.init_thread.error.connect(on_error)
        if on_status:
            self.init_thread.status_update.connect(on_status)
        self.init_thread.start()
        
    def _on_init_success(self, agent_response, callback):
        self.agent_id = agent_response.get('agent_id')
        self.client = agent_response.get('_client')
        self.is_initialized = True
        callback(self.agent_id)
        
    def speak(self, text):
        if not self.is_initialized or not self.agent_id:
            raise Exception("Agora not initialized")
        
        words = text.split()
        if len(words) > 60:
            text = ' '.join(words[:60])
        
        url = f"https://api.agora.io/api/conversational-ai-agent/v2/projects/{self.config['APP_ID']}/agents/{self.agent_id}/speak"
        
        payload = {
            "text": text,
            "priority": "INTERRUPT",
            "interruptable": False
        }
        headers = {
            "Authorization": self.config['AUTHORIZATION']
        }
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Speak error: {e}")
            raise
        
    def cleanup(self):
        if not self.agent_id:
            return
            
        try:
            url = f"https://api.agora.io/api/conversational-ai-agent/v2/projects/{self.config['APP_ID']}/agents/{self.agent_id}/leave"
            
            headers = {
                "Authorization": self.config['AUTHORIZATION']
            }
            
            requests.post(url, headers=headers, timeout=10)
            
            if self.client:
                self.client.stop()
                
        except Exception as e:
            print(f"Error during cleanup: {e}")


# ... (keep all UI classes the same until MainWindow) ...


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multilingual PA System")
        self.resize(1200, 750)

        # Load settings
        self.settings = SettingsManager.load_settings()
        
        # Build simplified Agora config from settings
        self.agora_config = {
            'APP_ID': self.settings['agora']['app_id'],
            'CHANNEL': self.settings['agora']['channel'],
            'TOKEN': self.settings['agora']['token'],
            'OPENAI_KEY': self.settings['agora']['openai_key'],
            'AUTHORIZATION': self.settings['agora']['authorization'],
            'HEADLESS': self.settings['agora']['headless']
        }
        
        self.agora_manager = AgoraManager(self.agora_config)
        self.gmail_poller = None
        self.classroom_poller = None
        
        self._build_ui()
        self._apply_styles()
        self._initialize_agora()

    # ... (keep _build_ui and _switch_page the same) ...

    def _initialize_agora(self):
        # Validate configuration
        required = {
            'app_id': 'Agora App ID',
            'channel': 'Channel name',
            'token': 'RTC Token',
            'openai_key': 'OpenAI API Key',
            'authorization': 'Authorization header'
        }
        
        missing = [name for key, name in required.items() if not self.settings['agora'][key]]
        
        if missing:
            error_msg = f"Missing configuration:\n• " + "\n• ".join(missing)
            self.feed_page.update_status("Not configured")
            QMessageBox.warning(self, "Configuration Required", 
                              f"{error_msg}\n\nPlease configure these in Settings.")
            return
            
        def on_success(agent_id):
            self.feed_page.update_status(f"Connected • Agent ID: {agent_id}")
            self._start_pollers()
            
        def on_error(error_msg):
            self.feed_page.update_status(f"Error: {error_msg}")
            
            # Show detailed error dialog
            error_dialog = QMessageBox(self)
            error_dialog.setIcon(QMessageBox.Icon.Critical)
            error_dialog.setWindowTitle("Agora Initialization Failed")
            error_dialog.setText("Failed to initialize Agora voice system")
            error_dialog.setInformativeText(error_msg)
            
            # Add troubleshooting tips
            details = """
Common issues:

1. Invalid Authorization header
   • Check that it starts with "Basic "
   • Verify your credentials are correct

2. Invalid RTC Token
   • Token may have expired
   • Generate a new token from Agora console
   • Ensure token is for the correct channel

3. Invalid App ID
   • Check App ID matches your Agora project

4. OpenAI API Key issues
   • Verify the key is active
   • Check you have sufficient credits

5. Network issues
   • Check your internet connection
   • Verify firewall settings
"""
            error_dialog.setDetailedText(details)
            error_dialog.exec()
            
        def on_status(status_msg):
            self.feed_page.update_status(status_msg)
        
        self.agora_manager.initialize(on_success, on_error, on_status)

    # ... (keep rest of MainWindow methods the same) ...

class AgoraManager:
    def __init__(self, config):
        self.config = config
        self.agent_id = None
        self.client = None
        self.is_initialized = False
        
    def initialize(self, on_success, on_error):
        self.init_thread = AgoraInitThread(self.config)
        self.init_thread.finished.connect(lambda resp: self._on_init_success(resp, on_success))
        self.init_thread.error.connect(on_error)
        self.init_thread.start()
        
    def _on_init_success(self, agent_response, callback):
        self.agent_id = agent_response.get('agent_id')
        self.client = agent_response.get('_client')
        self.is_initialized = True
        callback(self.agent_id)
        
    def speak(self, text):
        if not self.is_initialized or not self.agent_id:
            raise Exception("Agora not initialized")
        
        words = text.split()
        if len(words) > 60:
            text = ' '.join(words[:60])
        
        url = f"https://api.agora.io/api/conversational-ai-agent/v2/projects/{self.config['APP_ID']}/agents/{self.agent_id}/speak"
        
        payload = {
            "text": text,
            "priority": "INTERRUPT",
            "interruptable": False
        }
        headers = {
            "Authorization": "Basic " + self.config['AUTHORIZATION']
        }
        
        response = requests.post(url, json=payload, headers=headers)
        return response.json()
        
    def cleanup(self):
        if not self.agent_id:
            return
            
        try:
            url = f"https://api.agora.io/api/conversational-ai-agent/v2/projects/{self.config['APP_ID']}/agents/{self.agent_id}/leave"
            
            headers = {
                "Authorization": "Basic " + self.config['AUTHORIZATION']
            }
            
            requests.post(url, headers=headers)
            
            if self.client:
                self.client.stop()
                
        except Exception as e:
            print(f"Error during cleanup: {e}")


# ============== UI COMPONENTS ==============

class AnnouncementCard(QWidget):
    def __init__(self, title: str, source: str, timestamp: str,
                 original_text: str, translated_text: str, 
                 agora_manager=None, auto_play=False, parent=None):
        super().__init__(parent)

        self.setObjectName("AnnouncementCard")
        self.agora_manager = agora_manager
        self.translated_text = translated_text
        self.is_playing = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        title_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        meta_label = QLabel(f"{source} • {timestamp}")
        meta_label.setObjectName("CardMeta")
        meta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(meta_label)

        original_label = QLabel("Original")
        original_label.setObjectName("CardSectionLabel")

        original_text_label = QLabel(original_text)
        original_text_label.setWordWrap(True)
        original_text_label.setObjectName("CardBody")

        translated_label = QLabel("Translated")
        translated_label.setObjectName("CardSectionLabel")

        translated_text_label = QLabel(translated_text)
        translated_text_label.setWordWrap(True)
        translated_text_label.setObjectName("CardBodyStrong")

        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        self.play_button = QPushButton("Play Audio")
        self.play_button.setObjectName("PrimaryButton")
        self.play_button.clicked.connect(self._on_play_audio)

        bottom_row.addWidget(self.play_button)
        bottom_row.addStretch()

        main_layout.addLayout(title_row)
        main_layout.addWidget(original_label)
        main_layout.addWidget(original_text_label)
        main_layout.addWidget(translated_label)
        main_layout.addWidget(translated_text_label)
        main_layout.addLayout(bottom_row)
        
        if auto_play:
            QTimer.singleShot(500, self.play_audio)

    def play_audio(self):
        if self.is_playing:
            return
            
        if not self.agora_manager or not self.agora_manager.is_initialized:
            print("Agora not ready for auto-play")
            return
        
        try:
            self.is_playing = True
            self.play_button.setEnabled(False)
            self.play_button.setText("Playing...")
            
            self.agora_manager.speak(self.translated_text)
            
            QTimer.singleShot(2000, self._reset_buttons)
            
        except Exception as e:
            print(f"Failed to play audio: {e}")
            self._reset_buttons()
    
    def _reset_buttons(self):
        self.is_playing = False
        self.play_button.setEnabled(True)
        self.play_button.setText("Play Audio")

    def _on_play_audio(self):
        if not self.agora_manager or not self.agora_manager.is_initialized:
            QMessageBox.warning(self, "Not Ready", 
                              "Agora audio system is still initializing. Please wait...")
            return
        
        sender = self.sender()
        
        if not isinstance(sender, QPushButton):
            self.play_audio()
            return
        
        try:
            if self.is_playing:
                return
                
            self.is_playing = True
            sender.setEnabled(False)
            sender.setText("Playing...")
            self.play_button.setEnabled(False)
            
            self.agora_manager.speak(self.translated_text)
            
            QApplication.processEvents()
            
            QTimer.singleShot(2000, self._reset_buttons)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to play audio: {str(e)}")
            self._reset_buttons()


class FeedPage(QWidget):
    def __init__(self, agora_manager=None, parent=None):
        super().__init__(parent)
        self.setObjectName("FeedPage")
        self.agora_manager = agora_manager
        self.auto_broadcast = False
        self.is_initial_load = True
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        header_row = QHBoxLayout()
        header_label = QLabel("Announcement Feed")
        header_label.setObjectName("PageTitle")

        language_label = QLabel("Output language")
        language_label.setObjectName("FieldLabel")

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Hindi", "Tamil", "Telugu", "Bengali"])
        self.language_combo.setObjectName("ComboBox")

        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("SecondaryButton")

        header_row.addWidget(header_label)
        header_row.addStretch()
        header_row.addWidget(language_label)
        header_row.addWidget(self.language_combo)
        header_row.addWidget(refresh_button)

        status_row = QHBoxLayout()
        self.status_label = QLabel("Status: Initializing...")
        self.status_label.setObjectName("StatusLabel")

        self.audio_toggle = QCheckBox("Enable auto broadcast")
        self.audio_toggle.setObjectName("CheckBox")
        self.audio_toggle.toggled.connect(self._on_auto_broadcast_toggle)

        status_row.addWidget(self.status_label)
        status_row.addStretch()
        status_row.addWidget(self.audio_toggle)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("FeedScrollArea")

        scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content)
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(16)

        self.spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.scroll_layout.addItem(self.spacer)

        scroll_area.setWidget(scroll_content)

        root_layout.addLayout(header_row)
        root_layout.addLayout(status_row)
        root_layout.addWidget(scroll_area)

    def _on_auto_broadcast_toggle(self, checked):
        self.auto_broadcast = checked

    def add_announcement(self, title, source, timestamp, original, translated, auto_play=False):
        should_auto_play = auto_play and not self.is_initial_load
        
        card = AnnouncementCard(
            title, source, timestamp, original, translated, 
            self.agora_manager, should_auto_play
        )
        self.scroll_layout.insertWidget(self.scroll_layout.count() - 1, card)
    
    def mark_initial_load_complete(self):
        self.is_initial_load = False

    def update_status(self, message):
        self.status_label.setText(f"Status: {message}")


class SettingsPage(QWidget):
    settings_saved = pyqtSignal(dict)
    
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self.settings = settings
        self._build_ui()
        self._load_settings()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        header_label = QLabel("Settings")
        header_label.setObjectName("PageTitle")

        root_layout.addWidget(header_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("SettingsScrollArea")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Email settings
        email_group = QGroupBox("Email Settings")
        email_group.setObjectName("SettingsGroup")
        email_layout = QFormLayout(email_group)

        self.email_username = QLineEdit()
        self.email_username.setPlaceholderText("your.email@gmail.com")
        self.email_password = QLineEdit()
        self.email_password.setEchoMode(QLineEdit.EchoMode.Password)
        self.email_password.setPlaceholderText("App password")
        self.email_imap = QLineEdit()
        self.email_imap.setPlaceholderText("imap.gmail.com")

        email_layout.addRow("Email", self.email_username)
        email_layout.addRow("Password", self.email_password)
        email_layout.addRow("IMAP Host", self.email_imap)

        # Agora settings (simplified)
        agora_group = QGroupBox("Agora Settings")
        agora_group.setObjectName("SettingsGroup")
        agora_layout = QFormLayout(agora_group)

        self.agora_app_id = QLineEdit()
        self.agora_app_id.setPlaceholderText("Agora App ID")
        self.agora_channel = QLineEdit()
        self.agora_channel.setPlaceholderText("pa_channel")
        self.agora_token = QLineEdit()
        self.agora_token.setPlaceholderText("RTC Token")
        self.agora_openai_key = QLineEdit()
        self.agora_openai_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.agora_openai_key.setPlaceholderText("OpenAI API Key")
        self.agora_authorization = QLineEdit()
        self.agora_authorization.setEchoMode(QLineEdit.EchoMode.Password)
        self.agora_authorization.setPlaceholderText("Basic xxxxxxxx...")
        self.agora_headless = QCheckBox("Run browser in headless mode")

        agora_layout.addRow("App ID", self.agora_app_id)
        agora_layout.addRow("Channel", self.agora_channel)
        agora_layout.addRow("RTC Token", self.agora_token)
        agora_layout.addRow("OpenAI Key", self.agora_openai_key)
        agora_layout.addRow("Authorization", self.agora_authorization)
        agora_layout.addRow("", self.agora_headless)

        # Polling settings
        polling_group = QGroupBox("Polling Settings")
        polling_group.setObjectName("SettingsGroup")
        polling_layout = QFormLayout(polling_group)

        self.email_interval = QSpinBox()
        self.email_interval.setRange(5, 3600)
        self.email_interval.setSuffix(" sec")

        self.classroom_interval = QSpinBox()
        self.classroom_interval.setRange(5, 3600)
        self.classroom_interval.setSuffix(" sec")

        polling_layout.addRow("Email polling", self.email_interval)
        polling_layout.addRow("Classroom polling", self.classroom_interval)

        # Audio settings
        audio_group = QGroupBox("Audio Settings")
        audio_group.setObjectName("SettingsGroup")
        audio_layout = QFormLayout(audio_group)

        self.default_language = QComboBox()
        self.default_language.addItems(["English", "Hindi", "Tamil", "Telugu", "Bengali"])
        self.default_language.setObjectName("ComboBox")

        audio_layout.addRow("Default language", self.default_language)

        # Action buttons
        actions_row = QHBoxLayout()
        save_button = QPushButton("Save Settings")
        save_button.setObjectName("PrimaryButton")
        save_button.clicked.connect(self._save_settings)
        reset_button = QPushButton("Reset to Defaults")
        reset_button.setObjectName("SecondaryButton")
        reset_button.clicked.connect(self._reset_settings)

        actions_row.addStretch()
        actions_row.addWidget(reset_button)
        actions_row.addWidget(save_button)

        scroll_layout.addWidget(email_group)
        scroll_layout.addWidget(agora_group)
        scroll_layout.addWidget(polling_group)
        scroll_layout.addWidget(audio_group)
        scroll_layout.addStretch()
        scroll_layout.addLayout(actions_row)

        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area)

    def _load_settings(self):
        """Load settings into UI fields"""
        # Email
        self.email_username.setText(self.settings['email']['username'])
        self.email_password.setText(self.settings['email']['password'])
        self.email_imap.setText(self.settings['email']['imap_host'])

        # Agora (simplified)
        self.agora_app_id.setText(self.settings['agora']['app_id'])
        self.agora_channel.setText(self.settings['agora']['channel'])
        self.agora_token.setText(self.settings['agora']['token'])
        self.agora_openai_key.setText(self.settings['agora']['openai_key'])
        self.agora_authorization.setText(self.settings['agora']['authorization'])
        self.agora_headless.setChecked(self.settings['agora']['headless'])

        # Polling
        self.email_interval.setValue(self.settings['polling']['email_interval'])
        self.classroom_interval.setValue(self.settings['polling']['classroom_interval'])

        # Audio
        lang = self.settings['audio']['default_language']
        index = self.default_language.findText(lang)
        if index >= 0:
            self.default_language.setCurrentIndex(index)

    def _save_settings(self):
        """Save settings from UI to file"""
        self.settings['email']['username'] = self.email_username.text()
        self.settings['email']['password'] = self.email_password.text()
        self.settings['email']['imap_host'] = self.email_imap.text()

        self.settings['agora']['app_id'] = self.agora_app_id.text()
        self.settings['agora']['channel'] = self.agora_channel.text()
        self.settings['agora']['token'] = self.agora_token.text()
        self.settings['agora']['openai_key'] = self.agora_openai_key.text()
        self.settings['agora']['authorization'] = self.agora_authorization.text()
        self.settings['agora']['headless'] = self.agora_headless.isChecked()

        self.settings['polling']['email_interval'] = self.email_interval.value()
        self.settings['polling']['classroom_interval'] = self.classroom_interval.value()

        self.settings['audio']['default_language'] = self.default_language.currentText()

        if SettingsManager.save_settings(self.settings):
            QMessageBox.information(self, "Success", "Settings saved successfully!\n\nRestart the application for changes to take effect.")
            self.settings_saved.emit(self.settings)
        else:
            QMessageBox.critical(self, "Error", "Failed to save settings.")

    def _reset_settings(self):
        """Reset to default settings"""
        reply = QMessageBox.question(self, "Reset Settings",
                                     "Are you sure you want to reset all settings to defaults?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.settings = SettingsManager.DEFAULT_SETTINGS.copy()
            self._load_settings()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multilingual PA System")
        self.resize(1200, 750)

        # Load settings
        self.settings = SettingsManager.load_settings()
        
        # Build simplified Agora config from settings
        self.agora_config = {
            'APP_ID': self.settings['agora']['app_id'],
            'CHANNEL': self.settings['agora']['channel'],
            'TOKEN': self.settings['agora']['token'],
            'OPENAI_KEY': self.settings['agora']['openai_key'],
            'AUTHORIZATION': self.settings['agora']['authorization'],
            'HEADLESS': self.settings['agora']['headless']
        }
        
        self.agora_manager = AgoraManager(self.agora_config)
        self.gmail_poller = None
        self.classroom_poller = None
        
        self._build_ui()
        self._apply_styles()
        self._initialize_agora()

    def _build_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("SideBar")
        sidebar.setFixedWidth(220)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(20, 24, 20, 24)
        sidebar_layout.setSpacing(16)

        app_label = QLabel("PA System")
        app_label.setObjectName("AppTitle")

        subtitle = QLabel("Festival & Crisis\nAnnouncements")
        subtitle.setObjectName("AppSubtitle")

        nav_feed = QPushButton("Feed")
        nav_feed.setCheckable(True)
        nav_feed.setObjectName("NavButton")
        nav_settings = QPushButton("Settings")
        nav_settings.setCheckable(True)
        nav_settings.setObjectName("NavButton")

        nav_feed.setChecked(True)

        sidebar_layout.addWidget(app_label)
        sidebar_layout.addWidget(subtitle)
        sidebar_layout.addSpacing(16)
        sidebar_layout.addWidget(nav_feed)
        sidebar_layout.addWidget(nav_settings)
        sidebar_layout.addStretch()

        footer_label = QLabel("Prototype build")
        footer_label.setObjectName("SidebarFooter")
        sidebar_layout.addWidget(footer_label)

        self.stack = QStackedWidget()
        self.feed_page = FeedPage(self.agora_manager)
        self.settings_page = SettingsPage(self.settings)
        self.stack.addWidget(self.feed_page)
        self.stack.addWidget(self.settings_page)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        self.setCentralWidget(central)

        nav_feed.clicked.connect(lambda: self._switch_page(0, nav_feed, nav_settings))
        nav_settings.clicked.connect(lambda: self._switch_page(1, nav_feed, nav_settings))

    def _switch_page(self, index: int, feed_btn: QPushButton, settings_btn: QPushButton):
        self.stack.setCurrentIndex(index)
        if index == 0:
            feed_btn.setChecked(True)
            settings_btn.setChecked(False)
        else:
            feed_btn.setChecked(False)
            settings_btn.setChecked(True)

    def _initialize_agora(self):
        if not self.settings['agora']['app_id']:
            self.feed_page.update_status("Not configured - Please configure Agora settings")
            QMessageBox.warning(self, "Configuration Required",
                              "Please configure Agora settings in the Settings page.")
            return
            
        def on_success(agent_id):
            self.feed_page.update_status(f"Connected • Agent ID: {agent_id}")
            self._start_pollers()
            
        def on_error(error_msg):
            self.feed_page.update_status(f"Error: {error_msg}")
            QMessageBox.warning(self, "Agora Error", 
                              f"Failed to initialize Agora: {error_msg}")
        
        self.agora_manager.initialize(on_success, on_error)

    def _start_pollers(self):
        self.feed_page.mark_initial_load_complete()
        
        if self.settings['email']['username'] and self.settings['email']['password']:
            self.gmail_poller = GmailPollerThread(
                self.settings,
                poll_interval=self.settings['polling']['email_interval']
            )
            self.gmail_poller.new_email.connect(self._on_new_email)
            self.gmail_poller.start()
        
        self.classroom_poller = ClassroomPollerThread(
            poll_interval=self.settings['polling']['classroom_interval']
        )
        self.classroom_poller.new_announcement.connect(self._on_new_announcement)
        self.classroom_poller.start()
        
        status = self.feed_page.status_label.text()
        self.feed_page.update_status(status + " • Polling Email & Classroom")

    def _on_new_email(self, email_data):
        title = email_data['subject']
        source = "Email"
        timestamp = email_data['timestamp']
        original = email_data['body'][:500]
        translated = email_data['body'][:500]
        
        auto_play = self.feed_page.auto_broadcast
        
        self.feed_page.add_announcement(
            title, source, timestamp, original, translated, auto_play
        )

    def _on_new_announcement(self, ann_data):
        title = f"Classroom: {ann_data['course_name']}"
        source = "Classroom"
        timestamp = ann_data['creation_time']
        original = ann_data['text'][:500]
        translated = ann_data['text'][:500]
        
        auto_play = self.feed_page.auto_broadcast
        
        self.feed_page.add_announcement(
            title, source, timestamp, original, translated, auto_play
        )

    def closeEvent(self, event):
        if self.gmail_poller:
            self.gmail_poller.stop()
            self.gmail_poller.wait()
        
        if self.classroom_poller:
            self.classroom_poller.stop()
            self.classroom_poller.wait()
        
        self.agora_manager.cleanup()
        event.accept()

    def _apply_styles(self):
        self.setStyleSheet("""
            QWidget {
                font-family: 'Segoe UI', 'Roboto', sans-serif;
                font-size: 10pt;
                background-color: #0f172a;
                color: #e5e7eb;
            }
            #SideBar {
                background-color: #020617;
                border-right: 1px solid #1f2937;
            }
            #AppTitle {
                font-size: 18pt;
                font-weight: 600;
                color: #e5e7eb;
            }
            #AppSubtitle {
                font-size: 9pt;
                color: #94a3b8;
            }
            #SidebarFooter {
                font-size: 8pt;
                color: #6b7280;
            }
            #PageTitle {
                font-size: 16pt;
                font-weight: 600;
                margin-bottom: 4px;
            }
            #StatusLabel {
                font-size: 9pt;
                color: #9ca3af;
            }
            #FieldLabel {
                font-size: 9pt;
                color: #9ca3af;
                margin-right: 8px;
            }
            #NavButton {
                text-align: left;
                padding: 8px 10px;
                border-radius: 8px;
                border: 1px solid transparent;
                background-color: transparent;
                color: #e5e7eb;
            }
            #NavButton:hover {
                background-color: #111827;
            }
            #NavButton:checked {
                background-color: #1f2937;
                border-color: #38bdf8;
                color: #f9fafb;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            QGroupBox#SettingsGroup {
                border: 1px solid #1f2937;
                border-radius: 12px;
                margin-top: 18px;
                padding: 12px 16px 16px 16px;
                background-color: #020617;
            }
            QGroupBox#SettingsGroup::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #9ca3af;
                font-size: 9pt;
            }
            QLabel {
                font-size: 10pt;
            }
            QLineEdit, QComboBox, QSpinBox {
                padding: 6px 8px;
                border-radius: 8px;
                border: 1px solid #1f2937;
                background-color: #020617;
                selection-background-color: #38bdf8;
                selection-color: #000000;
            }
            QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                border: 1px solid #38bdf8;
            }
            QCheckBox {
                spacing: 6px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                border-radius: 4px;
                border: 1px solid #4b5563;
                background-color: #020617;
            }
            QCheckBox::indicator:checked {
                border-radius: 4px;
                border: 1px solid #38bdf8;
                background-color: #38bdf8;
            }
            QPushButton {
                padding: 8px 14px;
                border-radius: 999px;
                border: 1px solid transparent;
                background-color: #111827;
                color: #e5e7eb;
            }
            QPushButton#PrimaryButton {
                background-color: #38bdf8;
                color: #020617;
                font-weight: 600;
            }
            QPushButton#PrimaryButton:hover {
                background-color: #0ea5e9;
            }
            QPushButton#PrimaryButton:disabled {
                background-color: #4b5563;
                color: #9ca3af;
            }
            QPushButton#SecondaryButton,
            QPushButton#SecondaryButtonLeft {
                background-color: #020617;
                border: 1px solid #1f2937;
                color: #e5e7eb;
            }
            QPushButton#SecondaryButton:hover,
            QPushButton#SecondaryButtonLeft:hover {
                border-color: #4b5563;
            }
            QPushButton#SecondaryButtonLeft {
                align-self: flex-start;
            }
            #AnnouncementCard {
                background-color: #020617;
                border-radius: 16px;
                border: 1px solid #1f2937;
            }
            #CardTitle {
                font-size: 12pt;
                font-weight: 600;
            }
            #CardMeta {
                font-size: 8pt;
                color: #9ca3af;
            }
            #CardSectionLabel {
                font-size: 8.5pt;
                color: #9ca3af;
                margin-top: 8px;
            }
            #CardBody {
                font-size: 10pt;
                color: #d1d5db;
            }
            #CardBodyStrong {
                font-size: 10pt;
                color: #f9fafb;
                font-weight: 500;
            }
            #FeedScrollArea, #SettingsScrollArea {
                background-color: transparent;
            }
        """)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
