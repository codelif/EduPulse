import os
import time
import base64
import requests
import json
from urllib.parse import urlencode
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

class AgoraSeleniumVoiceClient:
    def __init__(self, app_id, channel, token, uid, agent_uid="1001", headless=False):
        self.app_id = app_id
        self.channel = channel
        self.token = token
        self.uid = uid
        self.agent_uid = agent_uid
        self.headless = headless
        self.driver = None
        
    def start(self):
        """Start the voice client in browser"""
        print("Starting Agora voice client...")
        
        # Validate App ID
        if not self.app_id or self.app_id == "your_app_id":
            raise ValueError("Invalid App ID. Please set a valid Agora App ID.")
        
        # Setup Chrome options
        chrome_options = Options()
        
        # CRITICAL: For real audio, we need different settings based on headless mode
        if self.headless:
            print("HEADLESS MODE: Audio may not work properly!")
            print("   Set headless=False for real audio input/output")
            chrome_options.add_argument('--headless=new')
            # Use fake devices in headless
            # chrome_options.add_argument('--use-fake-ui-for-media-stream')
            # chrome_options.add_argument('--use-fake-device-for-media-stream')
        else:
            print("VISIBLE MODE: Real audio enabled")
            # Auto-grant microphone permission
            # Don't use fake devices - use real microphone and speakers
        
        # Common settings
        chrome_options.add_argument('--enable-usermedia-screen-capturing')
        chrome_options.add_argument('--allow-file-access-from-files')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--autoplay-policy=no-user-gesture-required')
        
        # Grant permissions via preferences (more reliable)
        chrome_options.add_experimental_option('prefs', {
            'profile.default_content_setting_values.media_stream_mic': 1,
            'profile.default_content_setting_values.media_stream_camera': 1,
            'profile.default_content_setting_values.notifications': 1,
            'profile.content_settings.exceptions.automatic_downloads': {'*': {'setting': 1}}
        })
        
        # Initialize driver
        print("Initializing Chrome driver...")
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Grant microphone permissions (FIXED - removed audioPlayback)
        try:
            self.driver.execute_cdp_cmd('Browser.grantPermissions', {
                'permissions': ['audioCapture'],  # Only valid permission
                'origin': 'file://'
            })
        except Exception as e:
            print(f"Could not grant permissions via CDP: {e}")
            # This is okay - we already set it via prefs
        
        # Build URL with parameters
        html_file = os.path.abspath("agora_voice_client.html")
        params = {
            'appId': self.app_id,
            'channel': self.channel,
            'token': self.token,
            'uid': self.uid,
            'agentUid': self.agent_uid
        }
        url = f"file://{html_file}?{urlencode(params)}"
        
        print(f"Loading: {html_file}")
        print(f"Connecting to channel: {self.channel}")
        print(f"Your UID: {self.uid}")
        self.driver.get(url)
        
        # Wait for connection
        print("Waiting for connection...")
        time.sleep(3)
        
        # Check status
        self.print_status()
        
        # Check for errors in console
        self.print_console_logs()
        
    def print_console_logs(self):
        """Print browser console logs"""
        try:
            # Get browser console logs
            logs = self.driver.get_log('browser')
            if logs:
                print("\nBrowser Console Logs:")
                for log in logs[-5:]:  # Last 5 logs
                    print(f"   [{log['level']}] {log['message']}")
        except Exception as e:
            pass
    
    def print_status(self):
        """Print current status from the browser"""
        try:
            status = self.driver.execute_script("return window.getStatus();")
            print(f"\nStatus: {status}")
            
            # Check connection state
            is_connected = self.driver.execute_script("return window.isConnected();")
            if is_connected:
                print("Connected to channel")
            else:
                print("Not connected yet")
                
        except Exception as e:
            print(f"Could not get status: {e}")
    
    def get_audio_devices(self):
        """Check available audio devices"""
        try:
            devices = self.driver.execute_async_script("""
                var callback = arguments[arguments.length - 1];
                navigator.mediaDevices.enumerateDevices()
                    .then(devices => callback(devices.map(d => ({
                        kind: d.kind,
                        label: d.label || 'Unknown',
                        deviceId: d.deviceId
                    }))))
                    .catch(err => callback([]));
            """)
            return devices
        except:
            return []
    
    def test_audio(self):
        """Test if audio is working"""
        print("\n🔧 Testing audio setup...")
        
        # Check if we have microphone access
        result = self.driver.execute_async_script("""
            var callback = arguments[arguments.length - 1];
            navigator.mediaDevices.getUserMedia({audio: true})
                .then(() => callback({success: true, error: null}))
                .catch(err => callback({success: false, error: err.message}));
        """)
        
        if result['success']:
            print("Microphone access granted")
        else:
            print(f"No microphone access: {result['error']}")
        
        # Get devices
        devices = self.get_audio_devices()
        if devices:
            print(f"\nAvailable audio devices:")
            audio_inputs = [d for d in devices if d['kind'] == 'audioinput']
            audio_outputs = [d for d in devices if d['kind'] == 'audiooutput']
            
            print(f"   Microphones ({len(audio_inputs)}):")
            for device in audio_inputs:
                label = device['label'] or 'Default Microphone'
                print(f"      - {label}")
            
            print(f"   Speakers ({len(audio_outputs)}):")
            for device in audio_outputs:
                label = device['label'] or 'Default Speaker'
                print(f"      - {label}")
        else:
            print("Could not enumerate devices")
    
    def is_connected(self):
        """Check if connected to the channel"""
        try:
            return self.driver.execute_script("return window.isConnected();")
        except:
            return False
    
    def monitor(self, interval=5):
        """Monitor the connection"""
        print("\n" + "="*60)
        print("MONITORING (Ctrl+C to stop)")
        print("="*60)
        print("Speak into your microphone to talk to the AI agent")
        print("You should hear the AI agent's response through your speakers")
        print("="*60 + "\n")
        
        try:
            loop_count = 0
            while True:
                if loop_count % 3 == 0:  # Every 15 seconds
                    self.print_status()
                    self.print_console_logs()
                
                time.sleep(interval)
                loop_count += 1
                
        except KeyboardInterrupt:
            print("\nStopping monitor...")
    
    def stop(self):
        """Stop the voice client"""
        if self.driver:
            print("\nStopping voice client...")
            self.driver.quit()
            print("Stopped")


def load_config(config_file="agora_credentials.json"):
    """Load configuration from JSON file"""
    if not os.path.exists(config_file):
        print(f"Config file not found: {config_file}")
        print("\nPlease create agora_credentials.json with your credentials")
        exit(1)
    
    with open(config_file, 'r') as f:
        return json.load(f)


def get_basic_auth(customer_id, customer_secret):
    """Generate Basic Auth header"""
    credentials = f"{customer_id}:{customer_secret}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return f"Basic {encoded}"

# In the start_ai_agent function, add authorization parameter:

# Update the start_ai_agent function in agora2.py

def start_ai_agent(app_id, customer_id, customer_secret, channel, agent_token, 
                   agent_uid, user_uid, openai_key, azure_key, azure_region="eastus", authorization=""):
    """Start the AI agent via REST API"""
    print(f"\n=== Starting Agora Agent ===")
    print(f"App ID: {app_id}")
    print(f"Channel: {channel}")
    print(f"Agent UID: {agent_uid}")
    print(f"User UID: {user_uid}")
    
    url = f"https://api.agora.io/api/conversational-ai-agent/v2/projects/{app_id}/join"

    headers = {
        "Authorization": "Basic " + authorization,
        "Content-Type": "application/json"
    }

    data = {
        "name": f"agent_{int(time.time())}",  # Unique name each time
        "properties": {
            "channel": channel,
            "token": agent_token,
            "agent_rtc_uid": agent_uid,
            "remote_rtc_uids": [user_uid],
            "idle_timeout": 120,
            "advanced_features": {"enable_aivad": True},
            "llm": {
                "url": "https://api.openai.com/v1/chat/completions",
                "api_key": openai_key,
                "system_messages": [
                    {"role": "system", "content": "You are a helpful PA system assistant. Speak announcements clearly and concisely."}
                ],
                "max_history": 32,
                "greeting_message": "",  # No greeting for PA system
                "failure_message": "Please hold on a second.",
                "params": {"model": "gpt-4o-mini"},
            },
            "tts": {
                "vendor": "openai",
                "params": {
                    "api_key": openai_key,
                    "model": "tts-1",
                    "voice": "alloy",
                    "speed": 1.0,
                },
            },
            "asr": {"language": "en-US"},
        },
    }

    try:
        print(f"Sending request to: {url}")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")
        
        response.raise_for_status()
        result = response.json()
        
        return result
        
    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        print(f"Response: {e.response.text if e.response else 'No response'}")
        try:
            error_data = e.response.json()
            return error_data
        except:
            return {"code": -1, "message": str(e), "reason": e.response.text if e.response else ""}
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        return {"code": -1, "message": "Network error", "reason": str(e)}
    except Exception as e:
        print(f"Unexpected Error: {e}")
        import traceback
        traceback.print_exc()
        return {"code": -1, "message": "Unexpected error", "reason": str(e)}

def stop_ai_agent(app_id, agent_id, headers):
    url = f"https://api.agora.io/api/conversational-ai-agent/v2/projects/{app_id}/agents/{agent_id}/leave"
    requests.request("post", url, headers=headers)
