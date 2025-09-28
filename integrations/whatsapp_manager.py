from PyQt6.QtCore import QObject, pyqtSignal, QThread
from PyQt6.QtGui import QPixmap, QImage
import base64
import io
from datetime import datetime
import whatsappy

class WhatsAppManager(QObject):
    """
    Gerenciador de WhatsApp usando whatsappy-py para notificações.
    Implementa o padrão Singleton para garantir uma única instância.
    """

    # Sinais para comunicação com a interface
    qr_code_updated = pyqtSignal(QPixmap)
    status_updated = pyqtSignal(str)

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
            self.client = None
            self.is_ready = False
            self.qr_code_data = None
            self._worker_thread = None

    def connect(self):
        """
        Inicia a conexão com o WhatsApp Web.
        Cria o cliente e registra os event handlers.
        """
        try:
            if self.client is not None:
                print(f"[{datetime.now()}] WhatsApp: Cliente já existe, desconectando primeiro...")
                self.disconnect()

            print(f"[{datetime.now()}] WhatsApp: Iniciando conexão...")
            self.status_updated.emit("Iniciando conexão...")

            # Criar cliente whatsappy com tratamento de erro
            try:
                self.client = whatsappy.Whatsapp()
                print(f"[{datetime.now()}] WhatsApp: Cliente criado com sucesso")
            except Exception as client_error:
                print(f"[{datetime.now()}] WhatsApp: Erro ao criar cliente - {str(client_error)}")
                self.status_updated.emit(f"Erro ao criar cliente: {str(client_error)}")
                return

            # Registrar event handlers com tratamento de erro
            try:
                self.client.event(self.on_qr)
                self.client.event(self.on_ready)
                self.client.event(self.on_disconnect)
                print(f"[{datetime.now()}] WhatsApp: Event handlers registrados")
            except Exception as event_error:
                print(f"[{datetime.now()}] WhatsApp: Erro ao registrar handlers - {str(event_error)}")
                self.status_updated.emit(f"Erro nos handlers: {str(event_error)}")
                return

            # Executar em thread separada para não bloquear a UI
            try:
                self._worker_thread = WhatsAppWorker(self.client)
                self._worker_thread.start()
                print(f"[{datetime.now()}] WhatsApp: Thread iniciada com sucesso")
            except Exception as thread_error:
                print(f"[{datetime.now()}] WhatsApp: Erro ao iniciar thread - {str(thread_error)}")
                self.status_updated.emit(f"Erro na thread: {str(thread_error)}")
                return

            print(f"[{datetime.now()}] WhatsApp: Cliente criado e thread iniciada")

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro geral ao conectar - {str(e)}")
            import traceback
            print(f"[{datetime.now()}] WhatsApp: Traceback - {traceback.format_exc()}")
            self.status_updated.emit(f"Erro ao conectar: {str(e)}")

    def on_qr(self, qr_code_base64):
        """
        Handler para quando o QR code é gerado.
        Converte o base64 para QPixmap e emite o sinal.
        """
        try:
            print(f"[{datetime.now()}] WhatsApp: QR Code recebido")

            # Decodificar base64
            qr_data = base64.b64decode(qr_code_base64)

            # Criar QImage a partir dos dados
            image = QImage.fromData(qr_data, "PNG")

            if not image.isNull():
                # Converter para QPixmap
                pixmap = QPixmap.fromImage(image)

                # Emitir sinal para a UI
                self.qr_code_updated.emit(pixmap)
                self.status_updated.emit("Aguardando QR Code")
                print(f"[{datetime.now()}] WhatsApp: QR Code processado e enviado para UI")
            else:
                print(f"[{datetime.now()}] WhatsApp: Erro ao processar QR Code - imagem nula")

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro ao processar QR Code - {str(e)}")
            self.status_updated.emit(f"Erro no QR Code: {str(e)}")

    def on_ready(self):
        """
        Handler para quando o WhatsApp está conectado e pronto.
        """
        try:
            print(f"[{datetime.now()}] WhatsApp: Conectado com sucesso!")
            self.is_ready = True
            self.status_updated.emit("Conectado")

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro no handler on_ready - {str(e)}")

    def on_disconnect(self):
        """
        Handler para quando o WhatsApp é desconectado.
        """
        try:
            print(f"[{datetime.now()}] WhatsApp: Desconectado")
            self.is_ready = False
            self.status_updated.emit("Desconectado")

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro no handler on_disconnect - {str(e)}")

    def send_message(self, phone_number, message):
        """
        Envia uma mensagem via WhatsApp.

        Args:
            phone_number (str): Número do telefone no formato internacional
            message (str): Mensagem a ser enviada

        Returns:
            bool: True se enviado com sucesso, False caso contrário
        """
        if not self.is_ready or self.client is None:
            print(f"[{datetime.now()}] WhatsApp: Cliente não está pronto para enviar mensagens")
            return False

        try:
            print(f"[{datetime.now()}] WhatsApp: Enviando mensagem para {phone_number}")

            # Abrir conversa
            self.client.open_chat(phone_number)

            # Enviar mensagem
            self.client.send_message(message)

            print(f"[{datetime.now()}] WhatsApp: Mensagem enviada com sucesso para {phone_number}")
            return True

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro ao enviar mensagem para {phone_number} - {str(e)}")
            return False

    def disconnect(self):
        """
        Desconecta do WhatsApp e limpa o estado.
        """
        try:
            print(f"[{datetime.now()}] WhatsApp: Desconectando...")

            if self.client:
                self.client.close()
                self.client = None

            if self._worker_thread and self._worker_thread.isRunning():
                self._worker_thread.stop()
                self._worker_thread = None

            self.is_ready = False
            self.status_updated.emit("Desconectado")

            print(f"[{datetime.now()}] WhatsApp: Desconectado com sucesso")

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp: Erro ao desconectar - {str(e)}")


class WhatsAppWorker(QThread):
    """
    Thread worker para executar o cliente WhatsApp sem bloquear a UI.
    """

    def __init__(self, client):
        super().__init__()
        self.client = client
        self._running = False

    def run(self):
        """
        Executa o loop principal do cliente WhatsApp.
        """
        try:
            self._running = True
            print(f"[{datetime.now()}] WhatsApp Worker: Iniciando loop do cliente...")

            if self.client is None:
                print(f"[{datetime.now()}] WhatsApp Worker: Cliente é None, saindo...")
                return

            # Executar o cliente (isso bloqueia até a desconexão)
            try:
                self.client.run()
            except Exception as client_error:
                print(f"[{datetime.now()}] WhatsApp Worker: Erro no client.run() - {str(client_error)}")
                import traceback
                print(f"[{datetime.now()}] WhatsApp Worker: Traceback - {traceback.format_exc()}")

        except Exception as e:
            print(f"[{datetime.now()}] WhatsApp Worker: Erro geral no loop - {str(e)}")
            import traceback
            print(f"[{datetime.now()}] WhatsApp Worker: Traceback - {traceback.format_exc()}")
        finally:
            self._running = False
            print(f"[{datetime.now()}] WhatsApp Worker: Loop finalizado")

    def stop(self):
        """
        Para o worker thread.
        """
        self._running = False
        if self.client:
            try:
                self.client.close()
            except:
                pass
