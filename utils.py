"""
Utilitários compartilhados entre os módulos.

Estrutura de um campo de endpoint (armazenada em endpoints.campos como JSON list):

  {
    "path":        "Data.EstruturaFuncional.Codigo",  # notação ponto (readonly)
    "tipo":        "planilha" | "auth" | "fixo",
    # se tipo == "auth":
    "auth_var":    "Username",   # nome da variável no ambiente
    # se tipo == "fixo":
    "valor_fixo":  "19",
    # se tipo == "planilha":
    "label":       "Código",     # label exibido na tela de envio
    "obrigatorio": True,
  }
"""

import json

import pandas as pd


# ─── JSON flatten / reconstruct ────────────────────────────────────────────────

def flatten_json(obj: dict, prefix: str = "") -> dict:
    """Transforma JSON aninhado em dict com notação ponto.

    Ex.: {"Data": {"Codigo": ""}} → {"Data.Codigo": ""}
    Arrays são ignorados (não achatados).
    """
    result = {}
    for key, value in obj.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(flatten_json(value, full_key))
        else:
            result[full_key] = value
    return result


def reconstruct_json(flat: dict) -> dict:
    """Reconstrói JSON aninhado a partir de dict com notação ponto."""
    result: dict = {}
    for path, value in flat.items():
        parts = path.split(".")
        node = result
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
    return result


# ─── Extração de valor de célula ───────────────────────────────────────────────

def extrair_valor(val, extrair: str | None = None) -> str:
    """
    extrair=None        → retorna o valor como está
    extrair="codigo"    → retorna o trecho ANTES do primeiro "-"
    extrair="descricao" → retorna o trecho APÓS o primeiro "-"
    """
    if pd.isna(val):
        return ""
    s = str(val).strip()
    if extrair == "codigo" and "-" in s:
        return s.split("-")[0].strip()
    if extrair == "descricao" and "-" in s:
        return s.split("-", 1)[1].strip()
    return s


# ─── Parsing de campos de endpoint ────────────────────────────────────────────

def parse_campos_json(json_str: str) -> list[dict] | None:
    """
    Recebe a string JSON colada pelo usuário e retorna a lista de campos
    com configuração padrão (tipo='planilha').
    Retorna None se o JSON for inválido.
    """
    try:
        obj = json.loads(json_str)
    except (json.JSONDecodeError, ValueError):
        return None

    flat = flatten_json(obj)
    campos = []
    for path in flat:
        campos.append({
            "path":        path,
            "tipo":        "planilha",
            "auth_var":    "",
            "valor_fixo":  "",
            "label":       path.split(".")[-1],
            "obrigatorio": False,
        })
    return campos


def merge_campos(novos: list[dict], existentes: list[dict]) -> list[dict]:
    """
    Ao recarregar o JSON de um endpoint já configurado,
    preserva as configurações dos campos que ainda existem.
    """
    existentes_map = {c["path"]: c for c in existentes}
    for campo in novos:
        if campo["path"] in existentes_map:
            campo.update(existentes_map[campo["path"]])
    return novos
