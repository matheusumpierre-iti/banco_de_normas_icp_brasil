#!/usr/bin/env python3
"""
Converte todos os arquivos .doc de uma pasta para .docx.
Os arquivos convertidos são salvos na subpasta "Convertidos".

O pandoc NÃO lê o formato .doc (binário antigo do Word), então este script usa:
    1. LibreOffice em modo headless (Windows, Linux e macOS)  -> preferencial
    2. Microsoft Word via pywin32 (somente Windows)           -> alternativa

Uso:
    python converter_doc_para_docx.py /caminho/da/pasta
    python converter_doc_para_docx.py            # usa a pasta atual

Requisitos (pelo menos um):
    - LibreOffice instalado (https://www.libreoffice.org/download/)
    - Microsoft Word + `pip install pywin32` (apenas Windows)
"""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

NOME_SUBPASTA = "Convertidos"

# Locais comuns do executável do LibreOffice quando não está no PATH
CAMINHOS_LIBREOFFICE = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/local/bin/soffice",
    "/opt/libreoffice/program/soffice",
]


# --------------------------------------------------------------------------- #
# Conversor 1: LibreOffice
# --------------------------------------------------------------------------- #
def localizar_libreoffice():
    """Retorna o caminho do executável do LibreOffice, ou None se não achar."""
    for nome in ("soffice", "libreoffice"):
        caminho = shutil.which(nome)
        if caminho:
            return caminho
    for caminho in CAMINHOS_LIBREOFFICE:
        if os.path.isfile(caminho):
            return caminho
    return None


class ConversorLibreOffice:
    nome = "LibreOffice"

    def __init__(self, executavel: str):
        self.executavel = executavel
        # Perfil temporário evita conflito caso o LibreOffice esteja aberto
        self._perfil = tempfile.TemporaryDirectory(prefix="lo_perfil_")

    def converter(self, origem: Path, destino: Path) -> None:
        pasta_saida = destino.parent
        perfil_uri = Path(self._perfil.name).as_uri()
        comando = [
            self.executavel,
            f"-env:UserInstallation={perfil_uri}",
            "--headless",
            "--convert-to", "docx:MS Word 2007 XML",
            "--outdir", str(pasta_saida),
            str(origem),
        ]
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=180)

        # O LibreOffice grava como <nome_original>.docx na pasta de saída
        gerado = pasta_saida / f"{origem.stem}.docx"
        if resultado.returncode != 0 or not gerado.exists():
            raise RuntimeError(resultado.stderr.strip() or resultado.stdout.strip() or "falha desconhecida")

    def fechar(self) -> None:
        self._perfil.cleanup()


# --------------------------------------------------------------------------- #
# Conversor 2: Microsoft Word (Windows)
# --------------------------------------------------------------------------- #
class ConversorWord:
    nome = "Microsoft Word"
    WD_FORMAT_DOCX = 16  # wdFormatXMLDocument

    def __init__(self):
        import win32com.client  # type: ignore

        self.word = win32com.client.DispatchEx("Word.Application")
        self.word.Visible = False
        self.word.DisplayAlerts = 0

    def converter(self, origem: Path, destino: Path) -> None:
        doc = self.word.Documents.Open(str(origem), ReadOnly=True, AddToRecentFiles=False)
        try:
            doc.SaveAs2(str(destino), FileFormat=self.WD_FORMAT_DOCX)
        finally:
            doc.Close(False)

    def fechar(self) -> None:
        try:
            self.word.Quit()
        except Exception:
            pass


# --------------------------------------------------------------------------- #
# Escolha do conversor
# --------------------------------------------------------------------------- #
def escolher_conversor():
    exe = localizar_libreoffice()
    if exe:
        return ConversorLibreOffice(exe)

    if sys.platform.startswith("win"):
        try:
            return ConversorWord()
        except Exception:
            pass

    return None


# --------------------------------------------------------------------------- #
# Programa principal
# --------------------------------------------------------------------------- #
def main() -> int:
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    pasta = pasta.expanduser().resolve()

    if not pasta.is_dir():
        print(f"Erro: '{pasta}' não é uma pasta válida.")
        return 1

    # Lista os .doc (exclui .docx, que tem outra extensão, e arquivos temporários)
    arquivos = sorted(
        f for f in pasta.iterdir()
        if f.is_file()
        and f.suffix.lower() == ".doc"
        and not f.name.startswith(("~$", ".~lock"))
    )

    if not arquivos:
        print(f"Nenhum arquivo .doc encontrado em '{pasta}'.")
        return 0

    conversor = escolher_conversor()
    if conversor is None:
        print(
            "Erro: nenhum conversor disponível.\n"
            "Instale o LibreOffice (https://www.libreoffice.org/download/) ou, no Windows,\n"
            "tenha o Microsoft Word instalado e rode: pip install pywin32"
        )
        return 1

    saida = pasta / NOME_SUBPASTA
    saida.mkdir(exist_ok=True)

    print(f"Usando: {conversor.nome}")
    print(f"Convertendo {len(arquivos)} arquivo(s) de '{pasta}'...\n")

    sucessos = 0
    try:
        for arquivo in arquivos:
            destino = saida / f"{arquivo.stem}.docx"
            print(f"- {arquivo.name} -> {NOME_SUBPASTA}/{destino.name}")
            try:
                conversor.converter(arquivo, destino)
                sucessos += 1
            except Exception as erro:
                print(f"  [ERRO] {arquivo.name}: {erro}")
    finally:
        conversor.fechar()

    falhas = len(arquivos) - sucessos
    print(f"\nConcluído: {sucessos} convertido(s), {falhas} falha(s).")
    print(f"Resultado em: {saida}")
    return 0 if falhas == 0 else 2


if __name__ == "__main__":
    sys.exit(main())