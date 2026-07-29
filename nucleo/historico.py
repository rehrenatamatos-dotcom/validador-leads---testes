"""Histórico local de auditorias (arquivo JSON + pasta de resultados).
Guarda as últimas consultas de qualquer um dos três tipos de auditoria
("volume", "validador" ou "combinado") — simples e local, sem banco de
dados, mesma escolha do app original. Fica vazio de novo se o servidor
reiniciar (armazenamento local não é permanente em serviços como Streamlit
Cloud); aceitável para uso interno de hoje."""
import json
import os

ARQUIVO_HISTORICO = "historico.json"
PASTA_RESULTADOS = "resultados"
LIMITE_HISTORICO = 5  # guarda só as últimas consultas, para não acumular disco/memória


def carregar_historico() -> list:
    try:
        with open(ARQUIVO_HISTORICO, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def salvar_no_historico(registro: dict, arquivos: dict = None):
    """registro precisa ter "id" e "tipo" ("volume"/"validador"/"combinado").
    arquivos: dict {extensao_sem_ponto: bytes}, ex. {"xlsx": b"...", "html": b"..."}."""
    arquivos = arquivos or {}
    historico = carregar_historico()
    historico.insert(0, registro)
    mantidos = historico[:LIMITE_HISTORICO]
    removidos = historico[LIMITE_HISTORICO:]
    try:
        with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump(mantidos, f, ensure_ascii=False)
        os.makedirs(PASTA_RESULTADOS, exist_ok=True)
        rid = registro.get("id", "")
        if rid:
            for ext, conteudo in arquivos.items():
                if conteudo:
                    with open(os.path.join(PASTA_RESULTADOS, f"{rid}.{ext}"), "wb") as f:
                        f.write(conteudo)
        for antigo in removidos:
            rid_antigo = antigo.get("id", "")
            if not rid_antigo:
                continue
            for ext in ("csv", "xlsx", "html"):
                caminho = os.path.join(PASTA_RESULTADOS, f"{rid_antigo}.{ext}")
                if os.path.exists(caminho):
                    os.remove(caminho)
    except Exception:
        pass


def excluir_do_historico(rid: str):
    historico = [h for h in carregar_historico() if h.get("id") != rid]
    try:
        with open(ARQUIVO_HISTORICO, "w", encoding="utf-8") as f:
            json.dump(historico, f, ensure_ascii=False)
        for ext in ("csv", "xlsx", "html"):
            caminho = os.path.join(PASTA_RESULTADOS, f"{rid}.{ext}")
            if os.path.exists(caminho):
                os.remove(caminho)
    except Exception:
        pass


def ler_resultado_salvo(rid: str, ext: str):
    ext = ext.lstrip(".")
    try:
        with open(os.path.join(PASTA_RESULTADOS, f"{rid}.{ext}"), "rb") as f:
            return f.read()
    except Exception:
        return None
