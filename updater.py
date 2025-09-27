import requests
import webbrowser
from PyQt6.QtWidgets import QMessageBox

VERSION_URL = "https://raw.githubusercontent.com/Jottaaa12/acaipdvsbt/refs/heads/main/versao.txt"
DOWNLOAD_URL = "https://github.com/Jottaaa12/acaipdvsbt/releases/latest/download/PDV.Moderno.exe"

def check_for_updates(current_version):
    try:
        response = requests.get(VERSION_URL)
        response.raise_for_status()  # Lança exceção para códigos de erro HTTP
        latest_version = response.text.strip()

        if latest_version > current_version:
            msg_box = QMessageBox()
            msg_box.setIcon(QMessageBox.Icon.Information)
            msg_box.setText(f"Uma nova versão ({latest_version}) está disponível!")
            msg_box.setInformativeText("Deseja ir para a página de download agora?")
            msg_box.setWindowTitle("Atualização Disponível")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            
            if msg_box.exec() == QMessageBox.StandardButton.Yes:
                webbrowser.open(DOWNLOAD_URL)
                return True
    except requests.RequestException as e:
        print(f"Erro ao verificar atualizações: {e}")
    return False
