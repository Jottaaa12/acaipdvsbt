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
    # Fallback simples se utilitário não estiver disponível
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

    # Novos sinais
    qr_code_ready = pyqtSignal(str)      # caminho do arquivo PNG do QR
    status_updated = pyqtSignal(str)     # mensagens de status
    error_occurred = pyqtSignal(str)     # mensagens de erro

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhatsAppManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            super().__init__()
            self._initialized = True

            # Compatibilidade com código legado (não é usado aqui)
            self.client = None

            self.is_ready = False
            self._worker_thread: WhatsAppWorker | None = None

    def connect(self):
        """
        Inicia/reativa a conexão com o WhatsApp via bridge Node (sem navegador).
        Não bloqueia a UI.
        """
        try:
            # Se já está rodando, evita múltiplas instâncias
            if self._worker_thread and self._worker_thread.isRunning():
                self.status_updated.emit("🔄 Já conectando/conectado")
                return

            self.status_updated.emit("Iniciando conexão...")
            self._worker_thread = WhatsAppWorker(self)
            self._worker_thread.start()
        except Exception as e:
            self.error_occurred.emit(f"Falha ao iniciar conexão: {e}")

    def send_message(self, phone_number: str, message: str) -> bool:
        """
        Enfileira o envio de mensagem para execução no worker.
        Nunca bloqueia a UI.
        """
        if not self._worker_thread or not self._worker_thread.isRunning():
            print(f"[{datetime.now()}] WhatsApp: Worker não está em execução")
            return False
        try:
            self._worker_thread.enqueue_send(phone_number, message)
            return True
        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro ao enfileirar envio - {e}")
            return False

    def disconnect(self):
        """
        Encerra a bridge e limpa o estado local.
        """
        try:
            if self._worker_thread:
                self._worker_thread.stop()
                self._worker_thread.wait(5000)
                self._worker_thread = None
            self.is_ready = False
            self.status_updated.emit("Desconectado")
        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro ao desconectar - {e}")


class WhatsAppWorker(QThread):
    """
    Executa a bridge Node.js (Baileys) em um processo separado e comunica via STDIN/STDOUT (NDJSON).
    Garante que a UI continue responsiva e reporta eventos por sinais.
    """

    def __init__(self, manager: WhatsAppManager):
        super().__init__()
        self.manager = manager
        self._running = threading.Event()
        self._running.set()
        self._send_queue: "queue.Queue[dict]" = queue.Queue()
        self.process: subprocess.Popen | None = None

        # Caminhos persistentes
        self.session_path = get_data_path("whatsapp_session.json")
        self.qr_image_path = get_data_path("qr.png")
        self.bridge_path = get_data_path("wa_bridge.js")

    def run(self):
        try:
            os.makedirs(os.path.dirname(self.session_path), exist_ok=True)
            self._write_bridge_script()

            node_cmd = self._find_node_command()
            if node_cmd is None:
                raise RuntimeError("Node.js não encontrado no sistema. Instale o Node e execute novamente.")

            args = [node_cmd, self.bridge_path, self.session_path]
            self.manager.status_updated.emit("🔌 Iniciando bridge WhatsApp...")
            self.process = subprocess.Popen(
                args,
                cwd=os.path.dirname(self.bridge_path) or None,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                creationflags=(subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0),
            )

            # Threads auxiliares
            threading.Thread(target=self._read_stdout, daemon=True).start()
            threading.Thread(target=self._read_stderr, daemon=True).start()
            threading.Thread(target=self._sender_loop, daemon=True).start()

            # Tentativa de reconexão com sessão salva
            if os.path.exists(self.session_path):
                self.manager.status_updated.emit("🔎 Tentando reconectar usando sessão salva...")

            # Loop de vida
            while self._running.is_set():
                if self.process.poll() is not None:
                    break
                time.sleep(0.2)

            # Encerramento gracioso
            if self.process and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=3)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass

        except Exception as e:
            tb = traceback.format_exc()
            print(f"[{datetime.now()}] WhatsApp Worker: Exceção - {e}\n{tb}")
            self.manager.error_occurred.emit(str(e))
        finally:
            self.manager.is_ready = False

    def stop(self):
        self._running.clear()
        # Solicita desligamento ao bridge
        try:
            self._write_stdin_json({"action": "shutdown"})
        except Exception:
            pass

    def enqueue_send(self, phone: str, message: str):
        self._send_queue.put({"action": "send", "phone": phone, "message": message})

    def _sender_loop(self):
        while self._running.is_set():
            try:
                payload = self._send_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                self._write_stdin_json(payload)
            except Exception as e:
                print(f"[{datetime.now()}] WhatsApp Worker: erro ao enviar para bridge - {e}")

    def _write_stdin_json(self, obj: dict):
        if not self.process or not self.process.stdin:
            raise RuntimeError("Bridge não está ativa")
        line = json.dumps(obj, ensure_ascii=False)
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def _read_stdout(self):
        try:
            if not self.process or not self.process.stdout:
                return
            for raw in self.process.stdout:
                line = raw.strip()
                if not line:
                    continue
                # A bridge envia linhas JSON. Logs não-JSON são ignorados.
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    print(f"[WA-BRIDGE] {line}")
                    continue
                self._handle_bridge_message(msg)
        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp Worker: erro lendo stdout - {e}")

    def _read_stderr(self):
        try:
            if not self.process or not self.process.stderr:
                return
            for raw in self.process.stderr:
                text = raw.strip()
                if text:
                    print(f"[WA-BRIDGE:ERR] {text}")
        except Exception:
            pass

    def _handle_bridge_message(self, msg: dict):
        t = msg.get("type")
        if t == "status":
            status = msg.get("data", "")
            if status == "connected":
                self.manager.is_ready = True
                self.manager.status_updated.emit("✅ Conectado usando sessão salva" if os.path.exists(self.session_path) else "✅ Conectado com sucesso!")
            elif status == "connecting":
                self.manager.status_updated.emit("🔄 Conectando...")
            elif status == "session_invalid":
                # Sessão inválida: remove arquivo e solicita novo login
                try:
                    if os.path.exists(self.session_path):
                        os.remove(self.session_path)
                except Exception:
                    pass
                self.manager.status_updated.emit("⚠️ Sessão inválida, gere um novo QR Code")
            elif status == "disconnected":
                self.manager.is_ready = False
                self.manager.status_updated.emit("🔌 Desconectado")
            elif status == "session_saved":
                self.manager.status_updated.emit("💾 Sessão salva")
            else:
                self.manager.status_updated.emit(status)

        elif t == "qr":
            qr_text = msg.get("data", "")
            try:
                if qrcode is None:
                    raise RuntimeError("Dependência 'qrcode' não instalada. Adicione 'qrcode[pil]' ao requirements.txt")
                img = qrcode.make(qr_text)
                img.save(self.qr_image_path)
                self.manager.qr_code_ready.emit(self.qr_image_path)
                self.manager.status_updated.emit("ℹ️ Por favor, escaneie o QR Code")
            except Exception as e:
                self.manager.error_occurred.emit(f"Falha ao gerar imagem do QR: {e}")

        elif t == "error":
            err = msg.get("data", "Erro desconhecido")
            self.manager.error_occurred.emit(str(err))

        elif t == "log":
            print(f"[WA-BRIDGE] {msg.get('data')}")

        else:
            print(f"[WA-BRIDGE:UNKNOWN] {msg}")

    def _find_node_command(self):
        # Procura por 'node' no PATH
        candidates = ["node"]
        if os.name == "nt":
            candidates.append("node.exe")

        print(f"[DEBUG] Procurando node entre candidatos: {candidates}")

        for c in candidates:
            path = shutil.which(c)
            if path:
                print(f"[DEBUG] Encontrado: {c} -> {path}")
                return path

        # Verificar caminhos comuns do Node.js
        common_paths = [
            "C:\\Program Files\\nodejs\\node.exe",
            "C:\\Program Files (x86)\\nodejs\\node.exe",
            "%LOCALAPPDATA%\\fnm_multishells\\nodejs\\node.exe",
            "%LOCALAPPDATA%\\nvm\\node.exe",
            "%PROGRAMFILES%\\nodejs\\node.exe",
            "%PROGRAMFILES(X86)%\\nodejs\\node.exe"
        ]

        print("[DEBUG] Verificando caminhos comuns...")
        for path in common_paths:
            expanded = os.path.expandvars(path)
            if os.path.exists(expanded):
                print(f"[DEBUG] Encontrado no caminho comum: {expanded}")
                return expanded

        print("[DEBUG] Node.js não encontrado")
        return None

    def _write_bridge_script(self):
        """
        Escreve a bridge Node (Baileys) em arquivo JS no diretório de dados.
        Isso evita dependência de arquivo externo e simplifica a distribuição.
        """
        try:
            with open(self.bridge_path, "w", encoding="utf-8") as f:
                f.write(BAILEYS_BRIDGE_JS)
        except Exception as e:
            raise RuntimeError(f"Não foi possível escrever o script da bridge: {e}")


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
      const phone = (msg.phone || '').replace(/[^\d]/g, '');
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
