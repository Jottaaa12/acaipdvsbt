
import random
import time

class ScaleHandler:
    """
    Classe simulada para interagir com uma balança eletrônica.
    Em um cenário real, esta classe conteria a lógica para comunicação
    via porta serial (usando a biblioteca pyserial).
    """
    def __init__(self, port="COM3", baudrate=9600):
        self.port = port
        self.baudrate = baudrate
        self.is_connected = False
        # A conexão agora é feita sob demanda

    def reconfigure(self, port, baudrate, **kwargs):
        self.port = port
        self.baudrate = baudrate
        self.is_connected = False
        print(f"Simulador de Balança: Reconfigurado para a porta {self.port} a {self.baudrate} bps.")

    def connect(self):
        """Simula a conexão com a balança. Retorna (status, mensagem)."""
        print(f"Simulador de Balança: Tentando conectar na porta {self.port}...")
        time.sleep(0.5)  # Simula o tempo de conexão
        
        # Simula uma falha aleatória de conexão
        if random.random() < 0.2: # 20% de chance de falha
            self.is_connected = False
            error_message = f"Falha ao conectar na balança (porta {self.port}). Verifique a conexão e as configurações."
            print(f"Simulador de Balança: {error_message}")
            return False, error_message

        self.is_connected = True
        success_message = f"Simulador de Balança: Conectada com sucesso na porta {self.port}."
        print(success_message)
        return True, success_message

    def get_weight(self):
        """
        Simula a leitura de peso da balança.
        Retorna uma tupla (status, peso_ou_mensagem_de_erro).
        """
        if not self.is_connected:
            success, message = self.connect()
            if not success:
                return False, message
        
        try:
            # Simula a instabilidade do peso antes de estabilizar
            print("Simulador de Balança: Lendo peso...")
            time.sleep(0.3)
            
            # Gera um peso aleatório "estável"
            stable_weight = round(random.uniform(0.100, 5.000), 3)
            print(f"Simulador de Balança: Peso estabilizado em {stable_weight:.3f} kg.")
            
            return True, stable_weight
        except Exception as e:
            error_message = f"Erro ao ler o peso da balança: {e}"
            print(f"Simulador de Balança: {error_message}")
            return False, error_message

    def check_status(self):
        """Verifica o status da conexão com a balança."""
        # Em um cenário real, isso poderia envolver um comando "ping" para o dispositivo.
        # Para o simulador, vamos apenas retornar o estado de `is_connected`.
        # E para tornar mais dinâmico, vamos simular uma chance de desconexão.
        if self.is_connected and random.random() < 0.05: # 5% de chance de desconectar
            print("Simulador de Balança: Conexão perdida.")
            self.is_connected = False
        return self.is_connected
if __name__ == '__main__':
    # Exemplo de uso
    scale = ScaleHandler()
    weight = scale.get_weight()
    print(f"Peso final capturado: {weight} kg")
