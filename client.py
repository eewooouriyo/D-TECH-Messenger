
import sys
import os
import json
import socket
import base64
import threading
import html
from datetime import datetime

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QFontDatabase, QTextCursor
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QDialog, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget,
    QListWidgetItem, QTextEdit, QMessageBox, QFileDialog,
    QInputDialog, QSplitter, QMenu
)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000
MAX_FILE_SIZE = 10 * 1024 * 1024

BLUE = "#1769aa"
DARK_BLUE = "#07528e"
LIGHT_BLUE = "#dceefa"
GREEN = "#38a34a"
BG = "#f1f6fb"
TEXT = "#263746"

EMOJIS = [
    "😀", "😃", "😄", "😁", "😆", "😅", "🤣", "😂",
    "🙂", "🙃", "😉", "😊", "😇", "🥰", "😍", "🤩",
    "😘", "😋", "😛", "😜", "🤪", "😎", "🤓", "🧐",
    "🤔", "🫡", "🤨", "😐", "😶", "🙄", "😏", "😴",
    "🥳", "😭", "🥹", "😢", "😡", "🤬", "🤯", "😱",
    "🤗", "🤫", "🫠", "💀", "👻", "🤖", "👽", "🎃",
    "❤️", "🧡", "💛", "💚", "💙", "💜", "🖤", "🤍",
    "💔", "💕", "💖", "💗", "💯", "💢", "💬", "💤",
    "👍", "👎", "👏", "🙌", "🤝", "🙏", "💪", "👀",
    "👋", "✌️", "🤞", "🫶", "🗿", "🔥", "✨", "⭐",
    "🌟", "⚡", "☀️", "🌈", "🌙", "☁️", "❄️", "☂️",
    "🍕", "🍔", "🍟", "🌮", "🍿", "🍩", "🍪", "🎂",
    "🍉", "🍓", "🍎", "🍌", "☕", "🥤", "🧋", "🍜",
    "🐱", "🐶", "🐸", "🐼", "🐵", "🦊", "🐔", "🦆",
    "🦖", "🐉", "🐝", "🕷️", "🦋", "🌻", "🌹", "🌳",
    "🎮", "🎯", "🎲", "🎵", "🎶", "🎧", "🎤", "🎉",
    "🏆", "🚀", "💻", "📱", "📎", "📁", "💡", "✅",
    "❌", "⚠️", "❓", "❗", "💸", "🤑", "🗣️", "🫂"
]

def emoji_font():
    families = QFontDatabase.families()
    for name in ("Segoe UI Emoji", "Segoe UI Symbol", "Segoe UI"):
        if name in families:
            return name
    return QApplication.font().family()

EMOJI_FONT = "Segoe UI Emoji"

STYLE = f"""
QWidget {{
    font-family: "Segoe UI";
    font-size: 10pt;
    color: {TEXT};
}}
QMainWindow, QDialog {{ background: {BG}; }}
QLineEdit, QTextEdit {{
    background: white;
    border: 1px solid #b6cfe1;
    border-radius: 5px;
    padding: 7px;
}}
QPushButton {{
    background: #e7f2fb;
    border: 1px solid #b3d0e7;
    border-radius: 5px;
    padding: 7px 10px;
}}
QPushButton:hover {{ background: #cfe8fb; }}
QListWidget {{
    background: white;
    border: 1px solid #c1d7e8;
    border-radius: 5px;
    outline: 0;
}}
QListWidget::item {{ padding: 8px; border-bottom: 1px solid #edf2f7; }}
QListWidget::item:selected {{ background: #c9e6fb; color: #173e60; }}
"""

def send_json(sock, packet, lock):
    raw = json.dumps(packet, ensure_ascii=False).encode("utf-8") + b"\n"
    with lock:
        sock.sendall(raw)

class EmojiPicker(QMenu):
    def __init__(self, parent, callback):
        super().__init__(parent)
        self.callback = callback
        self.setStyleSheet("""
            QMenu { background: white; border: 1px solid #b6cfe1; }
            QMenu::item { padding: 5px; }
            QMenu::item:selected { background: #c9e6fb; }
        """)
        for start in range(0, len(EMOJIS), 8):
            row = EMOJIS[start:start + 8]
            for emoji in row:
                action = self.addAction(emoji)
                action.triggered.connect(
                    lambda checked=False, e=emoji: self.callback(e)
                )
            if start + 8 < len(EMOJIS):
                self.addSeparator()

class LoginDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.sock = None
        self.user = None
        self.host_address = SERVER_HOST
        self.mode = "login"
        self.drag_offset = None

        self.setWindowTitle("D-TECH Messenger")
        self.setFixedSize(400, 455)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint
        )
        self.setStyleSheet(STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 16)
        root.setSpacing(10)

        bar = QWidget()
        bar.setFixedHeight(34)
        bar.setStyleSheet(f"background:{DARK_BLUE};")
        br = QHBoxLayout(bar)
        br.setContentsMargins(10, 0, 4, 0)
        title = QLabel("✉  D-TECH Messenger")
        title.setStyleSheet("color:white;font-weight:bold;")
        close = QPushButton("✕")
        close.setFixedSize(32, 26)
        close.setStyleSheet(
            "QPushButton{background:transparent;color:white;border:0;}"
            "QPushButton:hover{background:#d9534f;}"
        )
        close.clicked.connect(self.reject)
        br.addWidget(title)
        br.addStretch()
        br.addWidget(close)
        root.addWidget(bar)

        banner = QWidget()
        banner.setFixedHeight(100)
        banner.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            f"stop:0 {DARK_BLUE},stop:1 #51a9e6);"
        )
        bl = QVBoxLayout(banner)
        heading = QLabel("¡Bienvenido! 👋")
        heading.setStyleSheet("color:white;font-size:24pt;font-weight:bold;")
        subtitle = QLabel("Conéctate con tus contactos 💬")
        subtitle.setStyleSheet("color:#eaf7ff;")
        bl.addWidget(heading)
        bl.addWidget(subtitle)
        root.addWidget(banner)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Nombre (solo al registrarte)")
        self.email = QLineEdit()
        self.email.setPlaceholderText("Correo electrónico")
        self.password = QLineEdit()
        self.password.setPlaceholderText("Contraseña")
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.host = QLineEdit(SERVER_HOST)
        self.host.setPlaceholderText("IP del servidor")

        for widget in (self.name, self.email, self.password, self.host):
            root.addWidget(widget)
            widget.setContentsMargins(18, 0, 18, 0)

        self.action = QPushButton("Iniciar sesión")
        self.action.setStyleSheet(
            f"background:{BLUE};color:white;font-weight:bold;padding:10px;"
        )
        self.action.clicked.connect(self.authenticate)
        root.addWidget(self.action)

        self.switch = QPushButton("Crear una cuenta nueva ✨")
        self.switch.setFlat(True)
        self.switch.clicked.connect(self.toggle_mode)
        root.addWidget(self.switch)

        self.note = QLabel("Servidor: puerto 5000")
        self.note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.note.setStyleSheet("color:#71879a;")
        root.addWidget(self.note)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = (
                event.globalPosition().toPoint()
                - self.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self.drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_offset)

    def toggle_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self.name.setVisible(self.mode == "register")
        self.action.setText(
            "Crear cuenta ✨" if self.mode == "register"
            else "Iniciar sesión"
        )
        self.switch.setText(
            "Ya tengo una cuenta" if self.mode == "register"
            else "Crear una cuenta nueva ✨"
        )

    def authenticate(self):
        email = self.email.text().strip().lower()
        password = self.password.text()
        host = self.host.text().strip()

        if not email or not password or not host:
            QMessageBox.warning(self, "Faltan datos", "Completa todos los campos.")
            return
        if self.mode == "register" and len(password) < 8:
            QMessageBox.warning(self, "Contraseña", "Usa al menos 8 caracteres.")
            return

        sock = None
        reader = None
        try:
            sock = socket.create_connection((host, SERVER_PORT), timeout=8)
            send_json(sock, {
                "type": self.mode,
                "email": email,
                "password": password,
                "name": self.name.text().strip()
            }, threading.Lock())

            reader = sock.makefile("r", encoding="utf-8")
            line = reader.readline()
            if not line:
                raise ConnectionError("El servidor cerró la conexión.")

            result = json.loads(line)
            if not result.get("ok"):
                reader.close()
                sock.close()
                QMessageBox.warning(
                    self, "Inicio de sesión",
                    result.get("error", "No se pudo iniciar sesión.")
                )
                return

            sock.settimeout(None)
            self.sock = sock
            self.user = result["user"]
            self.host_address = host
            self.accept()
        except (OSError, ValueError, json.JSONDecodeError) as error:
            if reader:
                try:
                    reader.close()
                except OSError:
                    pass
            if sock:
                sock.close()
            QMessageBox.critical(self, "Error de conexión", str(error))

class NetworkThread(QThread):
    packet_received = pyqtSignal(dict)
    disconnected = pyqtSignal(str)

    def __init__(self, sock):
        super().__init__()
        self.sock = sock
        self.lock = threading.Lock()
        self.active = True
        self.reader = None

    def send(self, packet):
        try:
            send_json(self.sock, packet, self.lock)
        except OSError as error:
            self.disconnected.emit(str(error))

    def run(self):
        try:
            self.reader = self.sock.makefile("r", encoding="utf-8")
            for line in self.reader:
                if not self.active:
                    break
                try:
                    self.packet_received.emit(json.loads(line))
                except json.JSONDecodeError:
                    continue
            if self.active:
                self.disconnected.emit("El servidor cerró la conexión.")
        except (OSError, ValueError) as error:
            if self.active:
                self.disconnected.emit(str(error))
        finally:
            if self.reader:
                try:
                    self.reader.close()
                except OSError:
                    pass

    def stop(self):
        self.active = False
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass
        if self.isRunning():
            self.wait(1200)

class TitleBar(QWidget):
    def __init__(self, window, title):
        super().__init__()
        self.window = window
        self.drag_offset = None
        self.setFixedHeight(36)
        self.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {DARK_BLUE},stop:1 #55afe8);"
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 4, 0)
        logo = QLabel("✉")
        logo.setFont(QFont(EMOJI_FONT, 15))
        logo.setStyleSheet("color:white;")
        label = QLabel(title)
        label.setStyleSheet("color:white;font-weight:bold;")
        row.addWidget(logo)
        row.addWidget(label)
        row.addStretch()

        for symbol, callback in (
            ("—", window.showMinimized),
            ("□", self.toggle_max),
            ("✕", window.close)
        ):
            button = QPushButton(symbol)
            button.setFixedSize(38, 28)
            button.setStyleSheet(
                "QPushButton{background:transparent;color:white;border:0;font-size:12pt;}"
                "QPushButton:hover{background:#ffffff45;}"
            )
            button.clicked.connect(callback)
            row.addWidget(button)

    def toggle_max(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = (
                event.globalPosition().toPoint()
                - self.window.frameGeometry().topLeft()
            )

    def mouseMoveEvent(self, event):
        if self.drag_offset and event.buttons() & Qt.MouseButton.LeftButton:
            if not self.window.isMaximized():
                self.window.move(
                    event.globalPosition().toPoint() - self.drag_offset
                )

    def mouseReleaseEvent(self, event):
        self.drag_offset = None

class ChatWindow(QMainWindow):
    def __init__(self, sock, user, server_host):
        super().__init__()
        self.user = user
        self.server_host = server_host
        self.network = NetworkThread(sock)
        self.network.packet_received.connect(self.on_packet)
        self.network.disconnected.connect(self.on_disconnect)
        self.contacts = {}
        self.groups = {}
        self.histories = {}
        self.selected_id = None
        self.selected_kind = None

        self.setWindowTitle("D-TECH Messenger")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        )
        self.resize(870, 600)
        self.setMinimumSize(680, 450)
        self.setStyleSheet(STYLE)

        central = QWidget()
        main = QVBoxLayout(central)
        main.setContentsMargins(1, 1, 1, 1)
        main.setSpacing(0)

        self.titlebar = TitleBar(self, "D-TECH Messenger")
        main.addWidget(self.titlebar)

        header = QWidget()
        header.setStyleSheet(f"background:{LIGHT_BLUE};")
        header.setFixedHeight(92)
        h = QHBoxLayout(header)

        avatar = QLabel("🙂")
        avatar.setFont(QFont(EMOJI_FONT, 29))
        avatar.setFixedSize(60, 60)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            "background:white;border:2px solid #8abce0;border-radius:8px;"
        )
        h.addWidget(avatar)

        userbox = QVBoxLayout()
        self.name_label = QLabel(user.get("name", user.get("email", "Usuario")))
        self.name_label.setStyleSheet(
            f"font-size:16pt;font-weight:bold;color:{DARK_BLUE};"
        )
        self.status_label = QLabel("🟢 Conectado")
        self.status_label.setFont(QFont(EMOJI_FONT, 10))
        self.status_label.setStyleSheet(f"color:{GREEN};")
        userbox.addWidget(self.name_label)
        userbox.addWidget(self.status_label)
        h.addLayout(userbox)
        h.addStretch()

        add_btn = QPushButton("＋ Agregar contacto")
        add_btn.clicked.connect(self.add_contact)
        group_btn = QPushButton("👥 Crear grupo")
        group_btn.clicked.connect(self.create_group)
        group_btn.setFont(QFont(EMOJI_FONT, 10))
        h.addWidget(add_btn)
        h.addWidget(group_btn)
        main.addWidget(header)

        split = QSplitter(Qt.Orientation.Horizontal)
        split.setChildrenCollapsible(False)

        left = QWidget()
        left.setMinimumWidth(210)
        left.setMaximumWidth(320)
        ll = QVBoxLayout(left)
        ll.setContentsMargins(8, 8, 8, 8)
        ll.addWidget(QLabel("CONTACTOS"))

        self.search = QLineEdit()
        self.search.setPlaceholderText("🔎 Buscar contacto...")
        self.search.textChanged.connect(self.filter_contacts)
        ll.addWidget(self.search)

        self.list = QListWidget()
        self.list.itemClicked.connect(self.select_contact)
        self.list.setFont(QFont(emoji_font(), 10))
        ll.addWidget(self.list)
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(8, 8, 8, 8)

        self.chat_header = QLabel("Selecciona un contacto para conversar 💬")
        self.chat_header.setStyleSheet(
            f"background:{LIGHT_BLUE};color:{DARK_BLUE};font-weight:bold;padding:12px;"
        )
        rl.addWidget(self.chat_header)

        self.chat = QTextEdit()
        self.chat.setReadOnly(True)
        self.chat.setFont(QFont(emoji_font(), 10))
        self.chat.setStyleSheet(
            'QTextEdit { background:white; border:1px solid #c1d7e8;'
            'font-family:"Segoe UI Emoji","Segoe UI Symbol","Segoe UI"; }'
        )
        rl.addWidget(self.chat, 1)

        self.input = QTextEdit()
        self.input.setFont(QFont(emoji_font(), 11))
        self.input.setPlaceholderText(
            "Escribe un mensaje... (Enter envía, Shift+Enter hace salto)"
        )
        self.input.setFixedHeight(75)
        self.input.installEventFilter(self)
        rl.addWidget(self.input)

        controls = QHBoxLayout()
        emoji_btn = QPushButton("😀 Emojis")
        emoji_btn.setFont(QFont(emoji_font(), 10))
        emoji_btn.clicked.connect(self.show_emoji_picker)
        file_btn = QPushButton("📎 Enviar archivo")
        file_btn.setFont(QFont(emoji_font(), 10))
        file_btn.clicked.connect(self.send_file)
        send_btn = QPushButton("Enviar ➤")
        send_btn.setStyleSheet(
            f"background:{BLUE};color:white;font-weight:bold;"
        )
        send_btn.clicked.connect(self.send_message)
        controls.addWidget(emoji_btn)
        controls.addWidget(file_btn)
        controls.addStretch()
        controls.addWidget(send_btn)
        rl.addLayout(controls)

        split.addWidget(right)
        split.setSizes([255, 600])
        main.addWidget(split, 1)

        footer = QLabel("  D-TECH Messenger  •  Conectado al servidor 💙")
        footer.setStyleSheet(
            "background:#e5eef6;color:#6d8497;padding:5px;font-size:9pt;"
        )
        main.addWidget(footer)
        self.setCentralWidget(central)
        self.network.start()

    def show_emoji_picker(self):
        menu = EmojiPicker(self, self.insert_emoji)
        menu.exec(self.mapToGlobal(self.rect().center()))

    def insert_emoji(self, emoji):
        cursor = self.input.textCursor()
        cursor.insertText(emoji)
        self.input.setTextCursor(cursor)
        self.input.setFocus()

    def eventFilter(self, obj, event):
        if obj is self.input and event.type().name == "KeyPress":
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                    self.send_message()
                    return True
        return super().eventFilter(obj, event)

    def add_contact(self):
        email, ok = QInputDialog.getText(
            self, "Agregar contacto", "Correo de la cuenta:"
        )
        if ok and email.strip():
            self.network.send({
                "type": "add_contact",
                "email": email.strip()
            })

    def create_group(self):
        name, ok = QInputDialog.getText(
            self, "Nuevo grupo", "Nombre del grupo:"
        )
        if ok and name.strip():
            self.network.send({
                "type": "create_group",
                "name": name.strip()
            })

    def filter_contacts(self, text):
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def refresh_list(self):
        current = (self.selected_kind, self.selected_id)
        self.list.clear()

        for email, user in sorted(self.contacts.items()):
            status = "🟢" if user.get("status") == "online" else "⚪"
            item = QListWidgetItem(
                f"{status}  {user.get('name', email)}\n      {email}"
            )
            item.setData(Qt.ItemDataRole.UserRole, ("contact", email))
            self.list.addItem(item)

        for gid, group in sorted(
            self.groups.items(),
            key=lambda pair: pair[1].get("name", "")
        ):
            item = QListWidgetItem(
                f"👥  {group.get('name', 'Grupo')}\n      Grupo"
            )
            item.setData(Qt.ItemDataRole.UserRole, ("group", gid))
            self.list.addItem(item)

        self.list.setFont(QFont(emoji_font(), 10))
        for i in range(self.list.count()):
            if self.list.item(i).data(Qt.ItemDataRole.UserRole) == current:
                self.list.setCurrentRow(i)
                break

    def on_packet(self, packet):
        kind = packet.get("type")

        if kind == "contact_list":
            self.contacts = {
                u["email"]: u for u in packet.get("contacts", [])
            }
            self.groups = {
                g["id"]: g for g in packet.get("groups", [])
            }
            self.refresh_list()

        elif kind in ("message", "file"):
            sender = packet.get("from", "")
            target = packet.get("to", "")
            key = target if target in self.groups else sender
            self.append_history(key, packet, incoming=True)

        elif kind == "error":
            QMessageBox.warning(
                self, "D-TECH Messenger",
                packet.get("message", "Error")
            )

    def on_disconnect(self, reason):
        self.status_label.setText("🔴 Desconectado")
        self.status_label.setStyleSheet("color:#c0392b;")
        self.chat_header.setText("Se perdió la conexión con el servidor")

    def select_contact(self, item):
        self.selected_kind, self.selected_id = item.data(
            Qt.ItemDataRole.UserRole
        )
        if self.selected_kind == "contact":
            user = self.contacts.get(self.selected_id, {})
            self.chat_header.setText(
                f"Conversación con {user.get('name', self.selected_id)} 💬"
            )
        else:
            group = self.groups.get(self.selected_id, {})
            self.chat_header.setText(
                f"👥 Grupo: {group.get('name', 'Grupo')}"
            )
        self.render_history()

    def append_history(self, key, packet, incoming=False):
        self.histories.setdefault(key, []).append((packet, incoming))
        if self.selected_id == key:
            self.render_history()

    def render_history(self):
        self.chat.clear()
        if self.selected_id is None:
            return

        for packet, incoming in self.histories.get(self.selected_id, []):
            sender = packet.get("from", self.user.get("email", "Yo"))
            name = self.contacts.get(sender, {}).get("name", sender)
            if not incoming:
                name = "Tú"

            time = packet.get(
                "time", datetime.now().strftime("%H:%M")
            )
            if packet.get("type") == "file":
                file_info = packet.get("file") or {}
                text = f"📎 Archivo: {file_info.get('name', 'archivo')}"
            else:
                text = str(packet.get("text", ""))

            color = "#2875b8" if incoming else "#279348"
            safe_name = html.escape(str(name))
            safe_text = html.escape(text).replace("\n", "<br>")
            safe_time = html.escape(str(time))

            self.chat.append(
                f'<span style="color:{color};font-weight:bold">{safe_name}</span> '
                f'<span style="color:#8899aa;font-size:9pt">{safe_time}</span>'
                f'<br><span style="font-family:\'{EMOJI_FONT}\',\'Segoe UI Symbol\',sans-serif;">'
                f'{safe_text}</span><br><br>'
            )

        bar = self.chat.verticalScrollBar()
        bar.setValue(bar.maximum())

    def send_message(self):
        if not self.selected_id:
            QMessageBox.information(
                self, "Mensaje",
                "Selecciona primero un contacto o grupo."
            )
            return

        text = self.input.toPlainText().strip()
        if not text:
            return

        self.network.send({
            "type": "message",
            "to": self.selected_id,
            "text": text
        })
        packet = {
            "type": "message",
            "from": self.user["email"],
            "to": self.selected_id,
            "text": text,
            "time": datetime.now().strftime("%H:%M")
        }
        self.append_history(self.selected_id, packet, incoming=False)
        self.input.clear()

    def send_file(self):
        if not self.selected_id:
            QMessageBox.information(
                self, "Archivo",
                "Selecciona primero un contacto o grupo."
            )
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar archivo"
        )
        if not path:
            return

        try:
            size = os.path.getsize(path)
            if size > MAX_FILE_SIZE:
                QMessageBox.warning(
                    self, "Archivo", "El límite es 10 MB."
                )
                return

            with open(path, "rb") as file:
                data = base64.b64encode(file.read()).decode("ascii")

            name = os.path.basename(path)
            self.network.send({
                "type": "file",
                "to": self.selected_id,
                "name": name,
                "data": data
            })
            packet = {
                "type": "file",
                "from": self.user["email"],
                "to": self.selected_id,
                "file": {"name": name, "data": data},
                "time": datetime.now().strftime("%H:%M")
            }
            self.append_history(
                self.selected_id, packet, incoming=False
            )

        except OSError as error:
            QMessageBox.critical(self, "Archivo", str(error))

    def closeEvent(self, event):
        self.network.stop()
        event.accept()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName("D-TECH Messenger")
    app.setStyle("Fusion")
    app.setFont(QFont(emoji_font(), 10))
    app.setStyleSheet(STYLE)

    login = LoginDialog()
    if login.exec() != QDialog.DialogCode.Accepted:
        sys.exit(0)

    window = ChatWindow(
        login.sock, login.user, login.host_address
    )
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
