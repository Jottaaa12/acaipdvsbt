import logging
from PyQt6.QtCore import QObject, pyqtSignal

class QtLogHandler(logging.Handler, QObject):
    """
    Um handler de log customizado que emite sinais Qt com as mensagens de log.
    Esta abordagem desacopla a lógica de logging da interface do usuário.
    """
    # Sinal que emitirá cada mensagem de log formatada como uma string.
    log_updated = pyqtSignal(str)

    def __init__(self, parent=None):
        """
        Inicializador da classe. É crucial chamar os construtores de ambas as classes-pai.
        """
        super().__init__()
        QObject.__init__(self, parent)

    def emit(self, record):
        """
        Este método é chamado automaticamente pelo sistema de logging sempre que uma
        mensagem precisa ser processada pelo handler.
        """
        # 'format' transforma o objeto de log 'record' na string final.
        msg = self.format(record)
        # Emite o sinal com a mensagem para qualquer slot conectado.
        self.log_updated.emit(msg)
