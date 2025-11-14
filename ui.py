from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QFormLayout, QGroupBox,
    QScrollArea, QStackedWidget, QFrame, QCheckBox, QSpinBox,
    QListWidget, QListWidgetItem, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
import sys


class AnnouncementCard(QWidget):
    """A single announcement card widget for the feed view."""

    def __init__(self, title: str, source: str, timestamp: str,
                 original_text: str, translated_text: str, parent=None):
        super().__init__(parent)

        self.setObjectName("AnnouncementCard")

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(8)

        # Title row
        title_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")

        meta_label = QLabel(f"{source} • {timestamp}")
        meta_label.setObjectName("CardMeta")
        meta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        title_row.addWidget(title_label)
        title_row.addStretch()
        title_row.addWidget(meta_label)

        # Original text
        original_label = QLabel("Original")
        original_label.setObjectName("CardSectionLabel")

        original_text_label = QLabel(original_text)
        original_text_label.setWordWrap(True)
        original_text_label.setObjectName("CardBody")

        # Translated text
        translated_label = QLabel("Translated")
        translated_label.setObjectName("CardSectionLabel")

        translated_text_label = QLabel(translated_text)
        translated_text_label.setWordWrap(True)
        translated_text_label.setObjectName("CardBodyStrong")

        # Bottom row: controls
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(8)

        play_button = QPushButton("Play Audio")
        play_button.setObjectName("PrimaryButton")
        replay_button = QPushButton("Re-broadcast")
        replay_button.setObjectName("SecondaryButton")

        bottom_row.addWidget(play_button)
        bottom_row.addWidget(replay_button)
        bottom_row.addStretch()

        main_layout.addLayout(title_row)
        main_layout.addWidget(original_label)
        main_layout.addWidget(original_text_label)
        main_layout.addWidget(translated_label)
        main_layout.addWidget(translated_text_label)
        main_layout.addLayout(bottom_row)


class FeedPage(QWidget):
    """Front view: announcement feed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FeedPage")
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        # Header
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

        # Sub header: status row
        status_row = QHBoxLayout()
        status_label = QLabel("Status: Connected • Polling Email (5 min) • Polling Classroom")
        status_label.setObjectName("StatusLabel")

        audio_toggle = QCheckBox("Enable auto broadcast")
        audio_toggle.setObjectName("CheckBox")

        status_row.addWidget(status_label)
        status_row.addStretch()
        status_row.addWidget(audio_toggle)

        # Scroll area for feed
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("FeedScrollArea")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Add a few sample announcement cards as placeholders
        demo_cards = [
            (
                "Safety Drill at 5 PM",
                "Email",
                "Today • 15:32",
                "There will be an evacuation drill at 5 PM. Please follow the instructions from the coordinators.",
                "Hindi: आज शाम 5 बजे निकासी अभ्यास होगा। कृपया समन्वयकों के निर्देशों का पालन करें।",
            ),
            (
                "Festival Parking Instructions",
                "Classroom",
                "Today • 14:05",
                "Parking near Block A will be closed during the festival. Use the north parking lot instead.",
                "Tamil: திருவிழா நேரத்தில் பிளாக் A அருகில் வண்டி நிறுத்தம் மூடப்படும். வடக்கு நிறுத்துமிடத்தைப் பயன்படுத்தவும்.",
            ),
            (
                "Emergency Weather Update",
                "Email",
                "Today • 12:40",
                "Due to heavy rain, outdoor events are moved indoors. Check your department notice board for room changes.",
                "Telugu: భారీ వర్షం కారణంగా బహిరంగ కార్యక్రమాలు గదులలోకి మార్చబడ్డాయి. గది మార్పుల కోసం శాఖ నోటీసు బోర్డును చూడండి.",
            ),
        ]

        for title, source, ts, orig, trans in demo_cards:
            card = AnnouncementCard(title, source, ts, orig, trans)
            scroll_layout.addWidget(card)

        # Spacer at bottom
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        scroll_layout.addItem(spacer)

        scroll_area.setWidget(scroll_content)

        root_layout.addLayout(header_row)
        root_layout.addLayout(status_row)
        root_layout.addWidget(scroll_area)


class SettingsPage(QWidget):
    """Settings view: configuration for emails, Classroom, polling, audio, etc."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("SettingsPage")
        self._build_ui()

    def _build_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setSpacing(16)

        header_label = QLabel("Settings")
        header_label.setObjectName("PageTitle")

        root_layout.addWidget(header_label)

        # Use scroll area to keep settings usable on smaller screens
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setObjectName("SettingsScrollArea")

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(16)

        # Email accounts group
        email_group = QGroupBox("Email Accounts")
        email_group.setObjectName("SettingsGroup")
        email_layout = QVBoxLayout(email_group)
        email_layout.setSpacing(12)

        email_form = QFormLayout()
        email_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        email_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)

        email_address = QLineEdit()
        email_address.setPlaceholderText("your.email@college.edu")
        email_password = QLineEdit()
        email_password.setEchoMode(QLineEdit.EchoMode.Password)
        email_password.setPlaceholderText("Password / App password")
        imap_server = QLineEdit()
        imap_server.setPlaceholderText("imap.yourcollege.edu")

        email_form.addRow("Primary email", email_address)
        email_form.addRow("Password", email_password)
        email_form.addRow("IMAP server", imap_server)

        add_email_button = QPushButton("Add another email")
        add_email_button.setObjectName("SecondaryButtonLeft")

        email_layout.addLayout(email_form)
        email_layout.addWidget(add_email_button)

        # Classroom group
        classroom_group = QGroupBox("Classroom Accounts")
        classroom_group.setObjectName("SettingsGroup")
        classroom_layout = QVBoxLayout(classroom_group)

        classroom_form = QFormLayout()
        classroom_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        classroom_form.setFormAlignment(Qt.AlignmentFlag.AlignTop)

        classroom_email = QLineEdit()
        classroom_email.setPlaceholderText("your.classroom@college.edu")
        api_key = QLineEdit()
        api_key.setPlaceholderText("Google API key / credentials reference")

        classroom_form.addRow("Account email", classroom_email)
        classroom_form.addRow("API credentials", api_key)

        add_classroom_button = QPushButton("Add another Classroom account")
        add_classroom_button.setObjectName("SecondaryButtonLeft")

        classroom_layout.addLayout(classroom_form)
        classroom_layout.addWidget(add_classroom_button)

        # Polling settings group
        polling_group = QGroupBox("Polling & Realtime Settings")
        polling_group.setObjectName("SettingsGroup")
        polling_layout = QFormLayout(polling_group)
        polling_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
        polling_layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)

        email_interval_spin = QSpinBox()
        email_interval_spin.setRange(1, 60)
        email_interval_spin.setValue(5)
        email_interval_spin.setSuffix(" min")

        classroom_interval_spin = QSpinBox()
        classroom_interval_spin.setRange(5, 300)
        classroom_interval_spin.setValue(30)
        classroom_interval_spin.setSuffix(" sec")

        polling_layout.addRow("Email polling interval", email_interval_spin)
        polling_layout.addRow("Classroom polling interval", classroom_interval_spin)

        # Audio settings group
        audio_group = QGroupBox("Audio & Language Settings")
        audio_group.setObjectName("SettingsGroup")
        audio_layout = QFormLayout(audio_group)

        auto_broadcast_checkbox = QCheckBox("Enable automatic broadcast for critical messages")
        default_lang_combo = QComboBox()
        default_lang_combo.addItems(["English", "Hindi", "Tamil", "Telugu", "Bengali"])
        default_lang_combo.setObjectName("ComboBox")

        audio_layout.addRow("Default output language", default_lang_combo)
        audio_layout.addRow("", auto_broadcast_checkbox)

        # Agora group
        agora_group = QGroupBox("Agora Conversational API")
        agora_group.setObjectName("SettingsGroup")
        agora_layout = QFormLayout(agora_group)

        agora_key = QLineEdit()
        agora_key.setPlaceholderText("Agora API key")

        agora_endpoint = QLineEdit()
        agora_endpoint.setPlaceholderText("https://api.agora.io/...")

        agora_layout.addRow("API key", agora_key)
        agora_layout.addRow("Endpoint", agora_endpoint)

        # Action buttons row
        actions_row = QHBoxLayout()
        save_button = QPushButton("Save Settings")
        save_button.setObjectName("PrimaryButton")
        reset_button = QPushButton("Reset to Defaults")
        reset_button.setObjectName("SecondaryButton")

        actions_row.addStretch()
        actions_row.addWidget(reset_button)
        actions_row.addWidget(save_button)

        # Add groups to scroll layout
        scroll_layout.addWidget(email_group)
        scroll_layout.addWidget(classroom_group)
        scroll_layout.addWidget(polling_group)
        scroll_layout.addWidget(audio_group)
        scroll_layout.addWidget(agora_group)
        scroll_layout.addStretch()
        scroll_layout.addLayout(actions_row)

        scroll_area.setWidget(scroll_content)
        root_layout.addWidget(scroll_area)


class MainWindow(QMainWindow):
    """Main application window with sidebar navigation and stacked views."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multilingual PA System")
        self.resize(1200, 750)
        self._build_ui()
        self._apply_styles()

    def _build_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar
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

        # Make Feed the default selected
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

        # Stacked pages
        self.stack = QStackedWidget()
        self.feed_page = FeedPage()
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.feed_page)
        self.stack.addWidget(self.settings_page)

        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.stack)

        self.setCentralWidget(central)

        # Navigation behavior
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

    def _apply_styles(self):
        # A minimal modern dark-ish theme with accent color
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
