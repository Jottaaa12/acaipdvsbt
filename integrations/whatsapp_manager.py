
import sys
from PyQt6.QtCore import QObject, pyqtSignal, QThread
from datetime import datetime
import os
import json
import subprocess
import threading
import queue
import time
import shutil
import traceback

# Utilitário para caminho de dados persistentes
try:
    from utils import get_data_path
except Exception:
    def get_data_path(name: str) -> str:
        return os.path.join(os.getcwd(), name)

# Renderização de QR via Python (sem browser)
try:
    import qrcode
except Exception:
    qrcode = None

class WhatsAppManager(QObject):
    """
    Integração WhatsApp sem navegador usando uma bridge Node.js (Baileys).
    Mantém robustez via QThread e sinais Qt.
    """
    qr_code_ready = pyqtSignal(str)
    status_updated = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        super().__init__()
        self.client = None
        self.is_ready = False
        self._worker_thread: WhatsAppWorker | None = None

    def connect(self):
        if self._worker_thread and self._worker_thread.isRunning():
            self.status_updated.emit("Conexão já em andamento.")
            return
        
        self.status_updated.emit("Iniciando conexão com WhatsApp...")
        self._worker_thread = WhatsAppWorker(self)
        self._worker_thread.start()

    def send_message(self, phone_number: str, message: str) -> bool:
        if not self._worker_thread or not self._worker_thread.isRunning():
            print(f"[{datetime.now()}] WhatsApp: Worker não está em execução para enviar mensagem.")
            return False
        self._worker_thread.enqueue_send(phone_number, message)
        return True

    def disconnect(self):
        if self._worker_thread:
            self._worker_thread.stop()
            self._worker_thread.wait(5000)
            self._worker_thread = None
        self.is_ready = False
        self.status_updated.emit("Desconectado")

class WhatsAppWorker(QThread):
    def __init__(self, manager: WhatsAppManager):
        super().__init__()
        self.manager = manager
        self._running = threading.Event()
        self._running.set()
        self._send_queue: "queue.Queue[dict]" = queue.Queue()
        self.process: subprocess.Popen | None = None
        self.session_path = get_data_path("whatsapp_session.json")
        self.qr_image_path = get_data_path("qr.png")
        self.bridge_path = get_data_path("wa_bridge.js")

    def run(self):
        try:
            self._write_bridge_script()

            node_cmd = self._find_node_command()
            if node_cmd is None:
                self.manager.error_occurred.emit("Node.js não foi encontrado. Por favor, instale-o.")
                return

            args = [node_cmd, self.bridge_path, self.session_path]
            
            # Força o CWD para a raiz do projeto, onde node_modules está.
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

            self.process = subprocess.Popen(
                args,
                cwd=project_root,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1, encoding='utf-8',
                creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0),
            )

            threading.Thread(target=self._read_stdout, daemon=True).start()
            threading.Thread(target=self._read_stderr, daemon=True).start()
            threading.Thread(target=self._sender_loop, daemon=True).start()

            while self._running.is_set():
                if self.process.poll() is not None:
                    break
                time.sleep(0.2)

        except Exception as e:
            tb = traceback.format_exc()
            print(f"--- ERRO FATAL NO WHATSAPP WORKER ---\n{e}\n{tb}", file=sys.stderr, flush=True)
            self.manager.error_occurred.emit(f"Erro fatal na conexão: {e}")
        finally:
            self.manager.is_ready = False

    def stop(self):
        self._running.clear()
        try:
            if self.process and self.process.stdin:
                self._write_stdin_json({"action": "shutdown"})
        except Exception:
            pass

    def enqueue_send(self, phone: str, message: str):
        self._send_queue.put({"action": "send", "phone": phone, "message": message})

    def _sender_loop(self):
        while self._running.is_set():
            try:
                payload = self._send_queue.get(timeout=0.5)
                self._write_stdin_json(payload)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Erro no loop de envio do WhatsApp: {e}", file=sys.stderr, flush=True)

    def _write_stdin_json(self, obj: dict):
        if self.process and self.process.stdin:
            line = json.dumps(obj, ensure_ascii=False)
            self.process.stdin.write(line + "\n")
            self.process.stdin.flush()

    def _read_stdout(self):
        try:
            if not self.process or not self.process.stdout: return
            for raw in self.process.stdout:
                line = raw.strip()
                if not line: continue
                try:
                    msg = json.loads(line)
                    self._handle_bridge_message(msg)
                except json.JSONDecodeError:
                    print(f"[WA-BRIDGE] {line}", file=sys.stderr, flush=True)
        except Exception:
            pass

    def _read_stderr(self):
        try:
            if not self.process or not self.process.stderr: return
            for raw in self.process.stderr:
                print(f"[WA-BRIDGE:ERR] {raw.strip()}", file=sys.stderr, flush=True)
        except Exception:
            pass

    def _handle_bridge_message(self, msg: dict):
        t = msg.get("type")
        if t == "status":
            status = msg.get("data", "")
            if status == "connected":
                self.manager.is_ready = True
                self.manager.status_updated.emit("✅ Conectado com sucesso!")
            else:
                self.manager.status_updated.emit(status)
        elif t == "qr":
            qr_text = msg.get("data", "")
            try:
                if qrcode is None:
                    raise RuntimeError("Dependência 'qrcode' não instalada.")
                img = qrcode.make(qr_text)
                img.save(self.qr_image_path)
                self.manager.qr_code_ready.emit(self.qr_image_path)
                self.manager.status_updated.emit("ℹ️ Por favor, escaneie o QR Code")
            except Exception as e:
                self.manager.error_occurred.emit(f"Falha ao gerar imagem do QR: {e}")
        elif t == "error":
            self.manager.error_occurred.emit(str(msg.get("data", "Erro desconhecido")))

    def _find_node_command(self):
        path = shutil.which("node") or shutil.which("node.exe")
        if path: return path
        
        common_paths = [
            "C:\\Program Files\\nodejs\\node.exe",
            "C:\\Program Files (x86)\\nodejs\\node.exe",
            os.path.expandvars("%LOCALAPPDATA%\\nvm\\current\\node.exe"),
        ]
        for p in common_paths:
            if os.path.exists(p):
                return p
        return None

    def _write_bridge_script(self):
        with open(self.bridge_path, "w", encoding="utf-8") as f:
            f.write(BAILEYS_BRIDGE_JS)

# Conteúdo do bridge utilizando @whiskeysockets/baileys
BAILEYS_BRIDGE_JS = r"""
const fs = require('fs');
const path = require('path');

function safeLog(obj) {
  try {
    process.stdout.write(JSON.stringify(obj) + '\n');
  } catch (e) {
    // ignore
  }
}

(async () => {
  let baileys;
  let pino;
  try {
    baileys = require('@whiskeysockets/baileys');
    pino = require('pino');
  } catch (e) {
    safeLog({ type: 'error', data: "Dependências Node ausentes. Instale com: npm i @whiskeysockets/baileys pino" });
    process.exit(1);
    return;
  }

  const { default: makeWASocket, useSingleFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = baileys;
  const args = process.argv.slice(2);
  const sessionPath = args[0] || path.join(process.cwd(), 'whatsapp_session.json');

  const { state, saveState } = useSingleFileAuthState(sessionPath);
  const { version } = await fetchLatestBaileysVersion();
  let sock;

  function startSock() {
    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: false,
      browser: ['PDV-Desktop', 'Chrome', '1.0.0'],
      logger: pino({ level: 'silent' }),
      markOnlineOnConnect: false,
      syncFullHistory: false,
    });

    sock.ev.on('creds.update', saveState);

    sock.ev.on('connection.update', (update) => {
      const { connection, lastDisconnect, qr } = update;
      if (qr) {
        safeLog({ type: 'qr', data: qr });
      }
      if (connection === 'connecting') {
        safeLog({ type: 'status', data: 'connecting' });
      } else if (connection === 'open') {
        safeLog({ type: 'status', data: 'connected' });
        safeLog({ type: 'status', data: 'session_saved' });
      } else if (connection === 'close') {
        const reason = lastDisconnect?.error?.output?.statusCode || lastDisconnect?.error?.status || lastDisconnect?.error?.code;
        if (reason === DisconnectReason.loggedOut || reason === 401 || reason === 'ERR_BAD_SESSION') {
          try { fs.unlinkSync(sessionPath); } catch (e) {}
          safeLog({ type: 'status', data: 'session_invalid' });
        } else {
          safeLog({ type: 'status', data: 'disconnected' });
        }
        process.exit(0);
      }
    });
  }

  startSock();

  // Leitura de comandos via STDIN (NDJSON)
  const readline = require('readline');
  const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });

  rl.on('line', async (line) => {
    let msg;
    try { msg = JSON.parse(line); } catch { return; }
    if (!msg || typeof msg !== 'object') return;

    if (msg.action === 'shutdown') {
      try { await sock?.end?.(); } catch {}
      process.exit(0);
      return;
    }

    if (msg.action === 'send') {
      const phone = (msg.phone || '').replace(/[\d]/g, '');
      const text = msg.message || '';
      if (!phone || !text) return;
      try {
        const jid = phone.endsWith('@s.whatsapp.net') ? phone : phone + '@s.whatsapp.net';
        await sock.sendMessage(jid, { text });
        safeLog({ type: 'log', data: 'Mensagem enviada' });
      } catch (e) {
        safeLog({ type: 'error', data: 'Falha ao enviar mensagem: ' + (e?.message || e) });
      }
      return;
    }
  });

  rl.on('close', () => {
    process.exit(0);
  });
})();
"""
