# integrations/commands/monitor_command.py
import logging
import os
import time
import uuid
import threading
from typing import List, Dict, Any

# Novas importações para captura
try:
    import mss
    import mss.tools
except ImportError:
    mss = None

try:
    import cv2  # OpenCV
except ImportError:
    cv2 = None

from .base_command import ManagerCommand
from utils import get_data_path  # Usar o utilitário de caminho
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from integrations.whatsapp_manager import WhatsAppManager

class MonitorCommand(ManagerCommand):
    """
    Executa uma verificação remota, capturando a tela e a webcam.
    Uso restrito a Gerentes: /verificar_pdv
    """

    # Define um local temporário para salvar as imagens
    TEMP_PATH = get_data_path('temp_captures')

    # Gerenciamento de arquivos temporários pendentes
    _pending_files: Dict[str, Dict[str, Any]] = {}
    _pending_lock = threading.Lock()

    def __init__(self, args: List[str], user_id: str, chat_id: str, manager: 'WhatsAppManager'):
        super().__init__(args, user_id, chat_id, manager)
        # Garante que a pasta temporária existe
        os.makedirs(self.TEMP_PATH, exist_ok=True)
        self.logger = logging.getLogger(__name__)

        # Registrar callback para limpeza de arquivos após envio
        # O callback será registrado quando os arquivos forem enviados

        # Iniciar limpeza periódica de arquivos antigos (fallback)
        self._cleanup_timer = threading.Timer(300.0, self._cleanup_old_files)  # 5 minutos
        self._cleanup_timer.daemon = True
        self._cleanup_timer.start()

    def execute(self) -> str:
        """
        Executa a sequência de captura e envio.
        Retorna uma string vazia se o envio de mídia for iniciado,
        ou uma mensagem de erro se algo falhar.
        """
        self.logger.info(f"Comando /verificar_pdv recebido de {self.user_id}.")

        # 1. Enviar confirmação inicial
        try:
            self.manager.send_message(self.chat_id, "ℹ️ Verificação remota iniciada... Processando capturas.")
        except Exception as e:
            self.logger.warning(f"Falha ao enviar mensagem de 'iniciado': {e}")
            # Não interrompe o processo por isso

        screenshot_path = None
        webcam_path = None

        # --- 2. Captura de Tela (Screenshot) ---
        if mss:
            try:
                screenshot_path = os.path.join(self.TEMP_PATH, f"ss_{uuid.uuid4()}.png")
                with mss.mss() as sct:
                    # Captura o monitor principal (monitor 1)
                    monitor = sct.monitors[1]
                    sct_img = sct.grab(monitor)
                    # Salva a imagem
                    mss.tools.to_png(sct_img.rgb, sct_img.size, output=screenshot_path)
                self.logger.info(f"Screenshot salvo em: {screenshot_path}")
            except Exception as e:
                self.logger.error(f"Falha ao capturar screenshot: {e}", exc_info=True)
                self.manager.send_message(self.chat_id, f"❌ Falha ao capturar screenshot: {e}")
        else:
            self.manager.send_message(self.chat_id, "❌ Erro: Biblioteca 'mss' não instalada para screenshots.")

        # --- 3. Captura da Webcam ---
        if cv2:
            cam = None
            try:
                webcam_path = os.path.join(self.TEMP_PATH, f"cam_{uuid.uuid4()}.jpg")
                cam = cv2.VideoCapture(0) # Tenta abrir a câmera 0 (padrão)

                if not cam.isOpened():
                    raise RuntimeError("Não foi possível acessar a câmera 0. Verifique as permissões ou se está em uso.")

                # Câmeras precisam de um momento para ajustar o foco/exposição
                time.sleep(1.0)

                ret, frame = cam.read()
                if not ret or frame is None:
                    raise RuntimeError("Falha ao ler o frame da câmera.")

                # Salva o frame capturado
                cv2.imwrite(webcam_path, frame)
                self.logger.info(f"Foto da webcam salva em: {webcam_path}")

            except Exception as e:
                self.logger.error(f"Falha ao capturar webcam: {e}", exc_info=True)
                self.manager.send_message(self.chat_id, f"❌ Falha ao capturar webcam: {e}")
            finally:
                if cam:
                    cam.release() # ESSENCIAL: Libera a câmera
        else:
            self.manager.send_message(self.chat_id, "❌ Erro: Biblioteca 'opencv-python' não instalada para webcam.")

        # --- 4. Envio dos Arquivos (Usando o Passo 0) ---
        try:
            if screenshot_path:
                message_id = self._send_media_and_track(screenshot_path, "1/2 - Screenshot da Tela PDV")
                self.logger.info(f"Comando de envio de mídia (screenshot) para {self.chat_id} enfileirado. Message ID: {message_id}")

            if webcam_path:
                # Pequeno delay para garantir que as mensagens cheguem em ordem
                time.sleep(2.0)
                message_id = self._send_media_and_track(webcam_path, "2/2 - Foto da Webcam PDV")
                self.logger.info(f"Comando de envio de mídia (webcam) para {self.chat_id} enfileirado. Message ID: {message_id}")

        except Exception as e:
            self.logger.error(f"Falha ao enfileirar mídias para envio: {e}", exc_info=True)
            return "❌ Erro interno ao tentar enfileirar as imagens para envio."

        # Se tudo correu bem, não precisamos enviar texto,
        # apenas as imagens que já foram enfileiradas.
        return "" # Retorna string vazia para o handler não enviar nada

    def _send_media_and_track(self, file_path: str, caption: str) -> str:
        """
        Envia mídia e rastreia o arquivo para limpeza posterior.
        Retorna o message_id gerado.
        """
        # Gerar message_id único para rastreamento
        message_id = str(uuid.uuid4())

        # Enfileirar envio
        result = self.manager.send_media(self.chat_id, file_path, caption)

        if result['success']:
            # Registrar callback para limpeza do arquivo após envio
            self.manager.register_media_callback(result['message_id'], self._on_media_result_received)

            # Rastrear arquivo pendente
            with self._pending_lock:
                self._pending_files[result['message_id']] = {
                    'file_path': file_path,
                    'timestamp': time.time(),
                    'chat_id': self.chat_id,
                    'caption': caption
                }
            self.logger.info(f"Arquivo {file_path} rastreado com message_id {result['message_id']}")
        else:
            self.logger.error(f"Falha ao enfileirar mídia {file_path}: {result.get('error', 'Erro desconhecido')}")
            # Remover arquivo imediatamente se falhou no enfileiramento
            try:
                os.remove(file_path)
                self.logger.info(f"Arquivo {file_path} removido após falha no enfileiramento")
            except Exception as e:
                self.logger.warning(f"Falha ao remover arquivo {file_path} após erro: {e}")

        return message_id

    def _on_media_result_received(self, message_id: str, success: bool, error: str):
        """
        Callback chamado quando o resultado do envio de mídia é recebido.
        Remove o arquivo se foi enviado com sucesso.
        """
        with self._pending_lock:
            if message_id in self._pending_files:
                file_info = self._pending_files[message_id]
                file_path = file_info['file_path']

                if success:
                    # Remover arquivo após envio bem-sucedido
                    try:
                        os.remove(file_path)
                        self.logger.info(f"Arquivo {file_path} removido após envio bem-sucedido (message_id: {message_id})")
                    except Exception as e:
                        self.logger.error(f"Falha ao remover arquivo {file_path}: {e}")
                else:
                    # Manter arquivo por mais tempo em caso de falha (pode ser retry)
                    self.logger.warning(f"Envio falhou para {file_path} (message_id: {message_id}): {error}")
                    # Arquivo será removido pela limpeza periódica se necessário

                # Remover da lista de pendentes
                del self._pending_files[message_id]
            else:
                self.logger.debug(f"Message ID {message_id} não encontrado na lista de pendentes")

    def _cleanup_old_files(self):
        """
        Remove arquivos temporários antigos que não foram processados.
        Executado periodicamente como fallback.
        """
        try:
            with self._pending_lock:
                current_time = time.time()
                to_remove = []

                for message_id, file_info in self._pending_files.items():
                    # Remover arquivos com mais de 10 minutos
                    if current_time - file_info['timestamp'] > 600:  # 10 minutos
                        file_path = file_info['file_path']
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                                self.logger.info(f"Arquivo antigo {file_path} removido pela limpeza periódica")
                        except Exception as e:
                            self.logger.error(f"Falha ao remover arquivo antigo {file_path}: {e}")

                        to_remove.append(message_id)

                # Remover das listas de pendentes
                for message_id in to_remove:
                    del self._pending_files[message_id]

                # Reiniciar timer se ainda há arquivos pendentes
                if self._pending_files:
                    self._cleanup_timer = threading.Timer(300.0, self._cleanup_old_files)
                    self._cleanup_timer.daemon = True
                    self._cleanup_timer.start()

        except Exception as e:
            self.logger.error(f"Erro na limpeza periódica de arquivos: {e}")
