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
        try:
            # Verifica se o objeto C++ subjacente ainda existe
            # Isso evita crash quando o logging tenta flushar após o término do QApplication
            import sip
            if sip.isdeleted(self):
                return
        except ImportError:
            # Se sip não estiver disponível (PyQt6 as vezes usa outra forma), 
            # tentamos acessar um atributo segura
            try:
                self.objectName()
            except RuntimeError:
                return

        try:
            # 'format' transforma o objeto de log 'record' na string final.
            msg = self.format(record)
            # Emite o sinal com a mensagem para qualquer slot conectado.
            self.log_updated.emit(msg)
        except (RuntimeError, Exception):
            # Ignora erros de emissão durante o shutdown
            pass

    def close(self):
        """
        Remove o handler e desconecta sinais para fechamento limpo.
        """
        self.log_updated.disconnect()
        super().close()
