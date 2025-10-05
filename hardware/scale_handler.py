import time
import random
import serial
import re
from PyQt6.QtCore import QThread, pyqtSignal, QObject, QTimer
import logging

class AbstractScaleWorker(QObject):
    """Classe base abstrata para os workers da balança."""
    weight_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)
    is_running = True

    def stop(self):
        self.is_running = False

class SimulatedScaleWorker(AbstractScaleWorker):
    """Worker que simula a leitura de peso em uma thread separada."""
    def run(self):
        logging.info("Simulador de Balança: Iniciando thread de simulação.")
        while self.is_running:
            try:
                weight = round(random.uniform(0.100, 5.000), 3)
                self.weight_updated.emit(weight)
                logging.debug(f"Simulador de Balança: Peso simulado emitido - {weight:.3f} kg")

                # Dividir o sleep em intervalos menores para verificar is_running mais frequentemente
                for _ in range(20):  # 20 * 0.1s = 2 segundos
                    if not self.is_running:
                        break
                    time.sleep(0.1)

            except Exception as e:
                error_message = f"Erro na simulação da balança: {e}"
                self.error_occurred.emit(error_message)
                logging.error(error_message, exc_info=True)
                break
        logging.info("Simulador de Balança: Thread de simulação finalizada.")


class RealScaleWorker(AbstractScaleWorker):
    """Worker que lê o peso de uma balança serial real em uma thread."""
    def __init__(self, port, baudrate, bytesize, parity, stopbits):
        super().__init__()
        self.port = port
        self.baudrate = baudrate
        self.bytesize = bytesize
        self.parity = parity
        self.stopbits = stopbits
        self.serial_connection = None
        self.buffer = "" # Buffer para dados fragmentados

    def run(self):
        logging.info(f"Balança Real: Iniciando thread de leitura na porta {self.port}.")

        while self.is_running:
            try:
                # Etapa 1: Garantir que a conexão esteja aberta
                if self.serial_connection is None or not self.serial_connection.isOpen():
                    if self.serial_connection:
                        self.serial_connection.close() # Garante que a conexão anterior seja fechada

                    self.serial_connection = serial.Serial(
                        port=self.port,
                        baudrate=self.baudrate,
                        bytesize=self.bytesize,
                        parity=self.parity,
                        stopbits=self.stopbits,
                        timeout=0.1  # Timeout reduzido para 100ms
                    )
                    logging.info("Balança Real: Conexão serial estabelecida.")

                # Etapa 2: Ler e processar dados
                data_received = self.serial_connection.read_all().decode('ascii', errors='ignore')
                if data_received:
                    self.buffer += data_received

                matches = list(re.finditer(r'\d+\.\d{3}', self.buffer))
                if matches:
                    last_match = matches[-1]
                    weight_str = last_match.group(0)

                    weight_kg = float(weight_str)
                    self.weight_updated.emit(weight_kg)

                    self.buffer = self.buffer[last_match.end():]

                # Pequena pausa para não sobrecarregar a CPU
                time.sleep(0.05)

            except serial.SerialException as e:
                # Etapa 3: Lidar com erros de comunicação e tentar reconectar
                if self.serial_connection and self.serial_connection.isOpen():
                    self.serial_connection.close()

                error_message = f"Balança Real: Erro de comunicação serial: {e}"
                self.error_occurred.emit(error_message)
                logging.warning(f"{error_message}. Tentando reconectar em 5 segundos...")

                # Aguarda 5 segundos antes de tentar reconectar, mas verifica is_running
                for _ in range(50):  # 50 * 0.1s = 5 segundos
                    if not self.is_running:
                        break
                    time.sleep(0.1)
                continue

            except ValueError:
                self.buffer = "" # Limpa o buffer em caso de dado malformado
                pass

            except Exception as e:
                error_message = f"Balança Real: Erro inesperado na leitura: {e}"
                self.error_occurred.emit(error_message)
                logging.error(error_message, exc_info=True)

                # Espera antes de tentar novamente, mas verifica is_running
                for _ in range(20):  # 20 * 0.1s = 2 segundos
                    if not self.is_running:
                        break
                    time.sleep(0.1)

        # Etapa 4: Limpeza ao finalizar a thread
        if self.serial_connection and self.serial_connection.isOpen():
            self.serial_connection.close()
        logging.info("Balança Real: Thread de leitura finalizada.")


class ScaleHandler(QObject):
    """
    Gerencia a comunicação com a balança (real ou simulada) e emite sinais
    para a interface principal.
    """
    weight_updated = pyqtSignal(float)
    error_occurred = pyqtSignal(str)

    def __init__(self, mode='test', **kwargs):
        super().__init__()
        self.mode = mode
        self.config = kwargs
        self.worker = None
        self.thread = None
        self.stop_timer = None
        # A thread não será mais iniciada automaticamente na construção.
        # self.start()

    def start(self):
        self.stop() # Garante que qualquer thread anterior seja parada

        self.thread = QThread()

        if self.mode == 'production':
            logging.info("ScaleHandler: Iniciando em Modo de Produção.")
            self.worker = RealScaleWorker(
                port=self.config.get('port', 'COM3'),
                baudrate=self.config.get('baudrate', 9600),
                bytesize=self.config.get('bytesize', 8),
                parity=self.config.get('parity', 'N'),
                stopbits=self.config.get('stopbits', 1)
            )
        else:
            logging.info("ScaleHandler: Iniciando em Modo de Teste (Simulado).")
            self.worker = SimulatedScaleWorker()

        self.worker.moveToThread(self.thread)

        # Conectar sinais do worker aos sinais do handler
        self.worker.weight_updated.connect(self.weight_updated)
        self.worker.error_occurred.connect(self.error_occurred)

        # Iniciar a thread
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def stop(self):
        """Para a thread da balança de forma síncrona e segura."""
        if self.thread and self.thread.isRunning():
            logging.info("ScaleHandler: Parando thread existente.")
            if self.worker:
                self.worker.stop()  # Sinaliza para o loop do worker parar

            self.thread.quit()  # Pede para a thread sair do loop de eventos

            # Espera até 3 segundos pela finalização da thread
            if not self.thread.wait(3000):
                logging.warning("ScaleHandler: Thread não respondeu ao quit/wait, será terminada.")
                self.thread.terminate() # Força o término como último recurso
            else:
                logging.info("ScaleHandler: Thread finalizada com sucesso.")
        
        self._cleanup_references()

    def _cleanup_references(self):
        """Limpa as referências da thread e worker."""
        self.thread = None
        self.worker = None
        logging.info("ScaleHandler: Thread parada e referências limpas.")

    def reconfigure(self, mode, **kwargs):
        logging.info(f"ScaleHandler: Reconfigurando para modo '{mode}'.")
        self.mode = mode
        self.config = kwargs
        self.start() # Reinicia o worker com a nova configuração

    def get_current_weight(self):
        # Este método pode ser removido ou adaptado, já que o peso agora é emitido por sinal.
        # Para um request síncrono, seria mais complexo e contra o padrão de QThread.
        logging.info("ScaleHandler: A leitura de peso agora é assíncrona via sinal 'weight_updated'.")
        return 0.0
