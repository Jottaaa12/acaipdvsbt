import subprocess
import os
import sys
import shutil
import logging
from pathlib import Path
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMessageBox
import database as db
from typing import Tuple, Optional, List

class PDVBuilder:
    """
    Sistema de construção e distribuição do PDV.
    Gerencia criação de executáveis, instaladores e testes automatizados.
    """

    def __init__(self):
        self.project_root = Path(__file__).parent
        self.dist_dir = self.project_root / "dist"
        self.build_dir = self.project_root / "build"
        self.output_dir = self.project_root / "Output"

        # Configurações de build
        self.pyinstaller_config = {
            'main_script': 'main.py',
            'name': 'PDV.Moderno',
            'version': self.get_current_version(),
            'icon': 'icone.ico',
            # Usar a análise automática de dependências do PyInstaller sempre que possível.
            # Adicionar apenas o que for estritamente necessário e não for detectado.
            'hidden_imports': [
                'PyQt6.QtSql',  # Exemplo de import que pode ser necessário
                'schedule',
                'requests',
            ],
            'add_data': [
                ('ui/*.py', 'ui'),
                ('hardware/*.py', 'hardware'),
                ('integrations/*.py', 'integrations'),
                ('*.ico', '.'),
                ('versao.txt', '.'),
            ],
            'excludes': [
                'tkinter',
                'unittest',
                'test',
                'tests',
                'pytest',
                'pip',
                'setuptools',
            ],
            'optimize': 2,
        }

        # Configurações do instalador
        self.innosetup_config = {
            'script_template': 'pdv_setup.iss',
            'output_name': f'setup-pdv-moderno-v{self.get_current_version()}',
        }

    def get_current_version(self) -> str:
        """Obtém versão atual do projeto."""
        try:
            version_file = self.project_root / "versao.txt"
            if version_file.exists():
                return version_file.read_text().strip()
            return "1.0.0"
        except Exception:
            return "1.0.0"

    def run_tests(self) -> Tuple[bool, str]:
        """
        Executa testes antes do build.

        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        try:
            logging.info("Executando testes...")

            # Verificar se banco de dados está acessível
            try:
                db.get_db_connection().close()
                logging.info("✓ Banco de dados acessível")
            except Exception as e:
                return False, f"Erro no banco de dados: {e}"

            # Verificar arquivos essenciais
            essential_files = [
                'main.py',
                'database.py',
                'ui/modern_main_window.py',
                'ui/modern_login.py',
                'requirements.txt'
            ]

            for file in essential_files:
                if not (self.project_root / file).exists():
                    return False, f"Arquivo essencial não encontrado: {file}"

            logging.info("✓ Todos os arquivos essenciais encontrados")

            # Verificar dependências
            try:
                import PyQt6
                import sqlite3
                logging.info("✓ Dependências principais OK")
            except ImportError as e:
                return False, f"Dependência não instalada: {e}"

            return True, "Testes executados com sucesso"

        except Exception as e:
            return False, f"Erro ao executar testes: {e}"

    def build_executable(self) -> Tuple[bool, str]:
        """
        Constrói executável com PyInstaller otimizado.

        Returns:
            Tuple[bool, str]: (sucesso, mensagem/caminho)
        """
        try:
            logging.info("Iniciando build do executável...")

            # Preparar ambiente
            self._prepare_build_environment()

            # Executar testes primeiro
            test_success, test_message = self.run_tests()
            if not test_success:
                return False, f"Testes falharam: {test_message}"

            # Construir comando PyInstaller
            cmd = self._build_pyinstaller_command()

            logging.info(f"Executando: {' '.join(cmd)}")

            # Executar PyInstaller
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300  # 5 minutos timeout
            )

            if result.returncode == 0:
                # Verificar se executável foi criado
                exe_path = self._get_executable_path()
                if exe_path and exe_path.exists():
                    logging.info(f"✓ Executável criado: {exe_path}")

                    # Copiar arquivos adicionais necessários
                    self._copy_additional_files()

                    return True, str(exe_path)
                else:
                    return False, "Executável não foi criado"
            else:
                error_msg = f"PyInstaller falhou:\n{result.stderr}"
                logging.error(error_msg)
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Build timeout - operação cancelada"
        except Exception as e:
            return False, f"Erro no build: {e}"
        finally:
            # Limpar arquivos temporários
            self._cleanup_build_files()

    def _prepare_build_environment(self):
        """Prepara ambiente para build."""
        # Criar diretórios necessários
        self.dist_dir.mkdir(exist_ok=True)
        self.build_dir.mkdir(exist_ok=True)

        # Limpar builds anteriores
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
            self.dist_dir.mkdir()

        logging.info("Ambiente preparado para build")

    def _build_pyinstaller_command(self) -> List[str]:
        """Constrói comando PyInstaller."""
        config = self.pyinstaller_config

        # Criar um arquivo de versão para o PyInstaller usar
        version_file_path = self.project_root / 'file_version_info.txt'
        self._create_version_file(version_file_path, config['version'])

        cmd = [
            'pyinstaller',
            '--name', config['name'],
            f'--version-file={version_file_path}',
            '--onefile',  # Single executable file
            '--windowed',  # No console window
            '--optimize', str(config['optimize']),
            '--clean',
            '--noconfirm',
        ]

        # Adicionar ícone se existir
        if config['icon'] and (self.project_root / config['icon']).exists():
            cmd.extend(['--icon', config['icon']])

        # Adicionar script principal
        cmd.append(config['main_script'])

        # Adicionar hidden imports
        for import_name in config['hidden_imports']:
            cmd.extend(['--hidden-import', import_name])

        # Adicionar arquivos de dados
        for source, destination in config.get('add_data', []):
            cmd.extend(['--add-data', f'{source}{os.pathsep}{destination}'])

        # Adicionar excludes
        for exclude in config['excludes']:
            cmd.extend(['--exclude-module', exclude])

        # Configurações específicas para Windows
        if sys.platform == 'win32':
            cmd.extend([
                '--upx-dir', 'C:\\upx\\' if os.path.exists('C:\\upx\\') else '--noupx',
            ])

        return cmd

    def _get_executable_path(self) -> Optional[Path]:
        """Obtém caminho do executável gerado."""
        exe_name = f"{self.pyinstaller_config['name']}.exe"
        return self.dist_dir / exe_name

    def _create_version_file(self, path: Path, version: str):
        """Cria o arquivo de informações de versão para o PyInstaller."""
        # Formato: Key=Value
        # Exemplo: FileVersion=1.0.0.0
        # O PyInstaller espera 4 dígitos, então completamos com .0 se necessário
        version_parts = version.split('.')
        while len(version_parts) < 4:
            version_parts.append('0')
        full_version = '.'.join(version_parts)

        content = f"""
# UTF-8
#
# For more details about fixed file info 'ffi' see:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx
VSVersionInfo(
  ffi=VS_FIXEDFILEINFO(
    # filevers and prodvers should be always a tuple with four items: (1, 0, 0, 0)
    # Set not needed items to zero 0.
    filevers=({', '.join(version_parts)}),
    prodvers=({', '.join(version_parts)}),
    # Contains a bitmask that specifies the valid bits 'flags'r
    mask=0x3f,
    # Contains a bitmask that specifies the Boolean attributes of the file.
    flags=0x0,
    # The operating system for which this file was designed.
    # 0x4 - NT and there is no need to change it.
    OS=0x40004,
    # The general type of file.
    # 0x1 - application
    fileType=0x1,
    # The function of the file.
    # 0x0 - unknown
    subtype=0x0,
    # Creation date and time stamp.
    date=(0, 0)
    ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'{self.innosetup_config.get("publisher", "Sua Empresa")}'),
        StringStruct(u'FileDescription', u'PDV Moderno'),
        StringStruct(u'FileVersion', u'{full_version}'),
        StringStruct(u'InternalName', u'PDV.Moderno'),
        StringStruct(u'LegalCopyright', u'© {datetime.now().year} {self.innosetup_config.get("publisher", "Sua Empresa")}. Todos os direitos reservados.'),
        StringStruct(u'OriginalFilename', u'PDV.Moderno.exe'),
        StringStruct(u'ProductName', u'PDV Moderno'),
        StringStruct(u'ProductVersion', u'{full_version}')])
      ]), 
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""
        path.write_text(content.strip(), encoding='utf-8')
        logging.info(f"Arquivo de versão criado em: {path}")

    def _copy_additional_files(self):
        """
        Esta função não é mais necessária, pois os arquivos de dados
        são incluídos diretamente no .exe pelo PyInstaller.
        """
        pass

    def _cleanup_build_files(self):
        """Limpa arquivos temporários de build."""
        try:
            # Remover diretório build se existir
            if self.build_dir.exists():
                shutil.rmtree(self.build_dir)
                logging.info("Arquivos temporários removidos")
        except Exception as e:
            logging.warning(f"Erro ao limpar arquivos temporários: {e}")

    def create_installer(self) -> Tuple[bool, str]:
        """
        Cria instalador com Inno Setup.

        Returns:
            Tuple[bool, str]: (sucesso, mensagem/caminho)
        """
        try:
            logging.info("Criando instalador...")

            # Verificar se executável existe
            exe_path = self._get_executable_path()
            if not exe_path or not exe_path.exists():
                return False, "Executável não encontrado. Execute o build primeiro."

            # Verificar Inno Setup
            inno_compiler = self._find_inno_compiler()
            if not inno_compiler:
                return False, "Inno Setup Compiler não encontrado"

            # Compilar instalador
            script_path = self.project_root / self.innosetup_config['script_template']

            cmd = [
                inno_compiler,
                '/cc', script_path
            ]

            logging.info(f"Executando: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=120  # 2 minutos timeout
            )

            if result.returncode == 0:
                # Procurar arquivo de instalador gerado
                output_files = list(self.project_root.glob("*.exe"))
                installer_files = [f for f in output_files if 'setup' in f.name.lower()]

                if installer_files:
                    installer_path = installer_files[0]
                    logging.info(f"✓ Instalador criado: {installer_path}")
                    return True, str(installer_path)
                else:
                    return False, "Instalador não foi gerado"
            else:
                error_msg = f"Inno Setup falhou:\n{result.stderr}"
                logging.error(error_msg)
                return False, error_msg

        except subprocess.TimeoutExpired:
            return False, "Criação do instalador timeout"
        except Exception as e:
            return False, f"Erro na criação do instalador: {e}"

    def _find_inno_compiler(self) -> Optional[str]:
        """Localiza o compilador Inno Setup."""
        possible_paths = [
            r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
            r"C:\Program Files\Inno Setup 6\ISCC.exe",
            r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
            r"C:\Program Files\Inno Setup 5\ISCC.exe",
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return None

    def verify_installation(self) -> Tuple[bool, str]:
        """
        Verifica se instalação foi criada corretamente.

        Returns:
            Tuple[bool, str]: (sucesso, mensagem)
        """
        try:
            exe_path = self._get_executable_path()
            if not exe_path or not exe_path.exists():
                return False, "Executável não encontrado"

            # Verificar tamanho do arquivo (não pode ser muito pequeno)
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            if size_mb < 10:  # Menos de 10MB pode indicar problema
                return False, f"Executável muito pequeno ({size_mb:.1f}MB)"

            # Tentar executar verificação básica
            try:
                # Apenas testar se arquivo é executável válido
                with open(exe_path, 'rb') as f:
                    header = f.read(4)
                    if header != b'MZ':  # Assinatura PE
                        return False, "Arquivo executável inválido"
            except Exception:
                return False, "Erro ao verificar executável"

            return True, f"Instalação verificada ({size_mb:.1f}MB)"

        except Exception as e:
            return False, f"Erro na verificação: {e}"

    def clean_build(self):
        """Limpa todos os arquivos de build."""
        try:
            dirs_to_clean = [self.dist_dir, self.build_dir]

            for dir_path in dirs_to_clean:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                    logging.info(f"Diretório limpo: {dir_path}")

            # Remover arquivos temporários
            temp_patterns = ['*.spec', '*.log', 'build.log']
            for pattern in temp_patterns:
                for file in self.project_root.glob(pattern):
                    try:
                        file.unlink()
                        logging.info(f"Arquivo temporário removido: {file}")
                    except Exception as e:
                        logging.warning(f"Erro ao remover {file}: {e}")

            logging.info("Limpeza concluída")

        except Exception as e:
            logging.error(f"Erro na limpeza: {e}")

    def get_build_info(self) -> dict:
        """Retorna informações sobre o build."""
        exe_path = self._get_executable_path()

        info = {
            'version': self.get_current_version(),
            'project_root': str(self.project_root),
            'dist_dir': str(self.dist_dir),
            'executable_exists': exe_path.exists() if exe_path else False,
            'executable_path': str(exe_path) if exe_path else None,
            'executable_size': 0,
        }

        if exe_path and exe_path.exists():
            info['executable_size'] = exe_path.stat().st_size / (1024 * 1024)  # MB

        return info

# Funções de conveniência
def build_executable() -> Tuple[bool, str]:
    """Constrói executável."""
    builder = PDVBuilder()
    return builder.build_executable()

def create_installer() -> Tuple[bool, str]:
    """Cria instalador."""
    builder = PDVBuilder()
    return builder.create_installer()

def run_tests() -> Tuple[bool, str]:
    """Executa testes."""
    builder = PDVBuilder()
    return builder.run_tests()

def clean_build():
    """Limpa arquivos de build."""
    builder = PDVBuilder()
    builder.clean_build()

def get_build_info() -> dict:
    """Obtém informações de build."""
    builder = PDVBuilder()
    return builder.get_build_info()

def verify_installation() -> Tuple[bool, str]:
    """Verifica instalação."""
    builder = PDVBuilder()
    return builder.verify_installation()
