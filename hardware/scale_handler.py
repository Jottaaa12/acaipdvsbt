import time
import random
import serial
import re
from PyQt6.QtCore import QThread, pyqtSignal, QObject

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
        print("Simulador de Balança: Iniciando thread de simulação.")
        while self.is_running:
            try:
                weight = round(random.uniform(0.100, 5.000), 3)
                self.weight_updated.emit(weight)
                print(f"Simulador de Balança: Peso simulado emitido - {weight:.3f} kg")
                time.sleep(2)  # Emite um novo peso a cada 2 segundos
            except Exception as e:
                error_message = f"Erro na simulação da balança: {e}"
                self.error_occurred.emit(error_message)
                print(error_message)
                break
        print("Simulador de Balança: Thread de simulação finalizada.")


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
        print(f"Balança Real: Iniciando thread de leitura na porta {self.port}.")
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=self.bytesize,
                parity=self.parity,
                stopbits=self.stopbits,
                timeout=1
            )
            print("Balança Real: Conexão serial estabelecida.")
        except serial.SerialException as e:
            error_message = f"Balança Real: Erro ao abrir a porta serial {self.port}: {e}"
            self.error_occurred.emit(error_message)
            print(error_message)
            return

        while self.is_running and self.serial_connection.isOpen():
            try:
                # Lê o que estiver disponível e adiciona ao buffer
                data_received = self.serial_connection.read_all().decode('ascii', errors='ignore')
                if data_received:
                    self.buffer += data_received

                # Tenta encontrar o último número válido no buffer
                # A expressão regular busca por padrões como 0.123, 1.234, 12.345, etc.
                matches = list(re.finditer(r'\d+\.\d{3}', self.buffer))
                if matches:
                    last_match = matches[-1]
                    weight_str = last_match.group(0)
                    
                    # Converte e emite o peso
                    weight_kg = float(weight_str)
                    self.weight_updated.emit(weight_kg)

                    # Limpa o buffer, mantendo apenas o que veio depois do último peso lido
                    self.buffer = self.buffer[last_match.end():]

            except serial.SerialException as e:
                error_message = f"Balança Real: Erro de comunicação serial: {e}"
                self.error_occurred.emit(error_message)
                print(error_message)
                self.is_running = False # Para a thread em caso de erro grave
            except ValueError:
                # Se a conversão falhar, limpa o buffer para evitar loops de erro
                self.buffer = ""
                pass
            except Exception as e:
                error_message = f"Balança Real: Erro inesperado na leitura: {e}"
                self.error_occurred.emit(error_message)
                print(error_message)
                time.sleep(2) # Espera antes de tentar novamente

        if self.serial_connection and self.serial_connection.isOpen():
            self.serial_connection.close()
        print("Balança Real: Thread de leitura finalizada.")


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
        self.start()

    def start(self):
        self.stop() # Garante que qualquer thread anterior seja parada

        self.thread = QThread()
        
        if self.mode == 'production':
            print("ScaleHandler: Iniciando em Modo de Produção.")
            self.worker = RealScaleWorker(
                port=self.config.get('port', 'COM3'),
                baudrate=self.config.get('baudrate', 9600),
                bytesize=self.config.get('bytesize', 8),
                parity=self.config.get('parity', 'N'),
                stopbits=self.config.get('stopbits', 1)
            )
        else:
            print("ScaleHandler: Iniciando em Modo de Teste (Simulado).")
            self.worker = SimulatedScaleWorker()

        self.worker.moveToThread(self.thread)
        
        # Conectar sinais do worker aos sinais do handler
        self.worker.weight_updated.connect(self.weight_updated)
        self.worker.error_occurred.connect(self.error_occurred)
        
        # Iniciar a thread
        self.thread.started.connect(self.worker.run)
        self.thread.start()

    def stop(self):
        if self.thread and self.thread.isRunning():
            print("ScaleHandler: Parando thread existente.")
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()
            print("ScaleHandler: Thread parada com sucesso.")
        self.thread = None
        self.worker = None

    def reconfigure(self, mode, **kwargs):
        print(f"ScaleHandler: Reconfigurando para modo '{mode}'.")
        self.mode = mode
        self.config = kwargs
        self.start() # Reinicia o worker com a nova configuração

    def get_current_weight(self):
        # Este método pode ser removido ou adaptado, já que o peso agora é emitido por sinal.
        # Para um request síncrono, seria mais complexo e contra o padrão de QThread.
        print("ScaleHandler: A leitura de peso agora é assíncrona via sinal 'weight_updated'.")
        return 0.0