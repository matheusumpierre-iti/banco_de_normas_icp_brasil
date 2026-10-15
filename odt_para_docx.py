"""
Converte todos os arquivos .odt de uma pasta para .docx usando o pandoc.
Os arquivos convertidos são salvos na subpasta "Convertidos".
 
Uso:
    python converter_odt_para_docx.py /caminho/da/pasta
    python converter_odt_para_docx.py            # usa a pasta atual
 
Requisitos:
    - Python 3.6+
    - pandoc instalado e disponível no PATH (https://pandoc.org/installing.html)
"""
 
import shutil
import subprocess
import sys
from pathlib import Path
 
NOME_SUBPASTA = "Convertidos"
 
 
def converter_arquivo(origem: Path, destino: Path) -> bool:
    """Converte um único arquivo .odt para .docx. Retorna True em caso de sucesso."""
    comando = ["pandoc", str(origem), "-f", "odt", "-t", "docx", "-o", str(destino)]
    try:
        subprocess.run(comando, check=True, capture_output=True, text=True)
        return True
    except subprocess.CalledProcessError as erro:
        mensagem = erro.stderr.strip() or "erro desconhecido"
        print(f"  [ERRO] {origem.name}: {mensagem}")
        return False
 
 
def main() -> int:
    # Verifica se o pandoc está instalado
    if shutil.which("pandoc") is None:
        print("Erro: pandoc não encontrado. Instale-o em https://pandoc.org/installing.html")
        return 1
 
    # Define a pasta de trabalho
    pasta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    pasta = pasta.expanduser().resolve()
 
    if not pasta.is_dir():
        print(f"Erro: '{pasta}' não é uma pasta válida.")
        return 1
 
    # Lista os .odt (ignora maiúsculas/minúsculas e arquivos temporários de bloqueio)
    arquivos = sorted(
        f for f in pasta.iterdir()
        if f.is_file() and f.suffix.lower() == ".odt" and not f.name.startswith(".~lock")
    )
 
    if not arquivos:
        print(f"Nenhum arquivo .odt encontrado em '{pasta}'.")
        return 0
 
    # Cria a subpasta de saída
    saida = pasta / NOME_SUBPASTA
    saida.mkdir(exist_ok=True)
 
    print(f"Convertendo {len(arquivos)} arquivo(s) de '{pasta}'...\n")
 
    sucessos = 0
    for arquivo in arquivos:
        destino = saida / f"{arquivo.stem}.docx"
        print(f"- {arquivo.name} -> {NOME_SUBPASTA}/{destino.name}")
        if converter_arquivo(arquivo, destino):
            sucessos += 1
 
    falhas = len(arquivos) - sucessos
    print(f"\nConcluído: {sucessos} convertido(s), {falhas} falha(s).")
    print(f"Resultado em: {saida}")
    return 0 if falhas == 0 else 2
 
 
if __name__ == "__main__":
    sys.exit(main())