"""
Lógica de chamada HTTP aos endpoints cadastrados.
"""

import json

import pandas as pd
import requests

from utils import extrair_valor, reconstruct_json


def build_payload(campos: list, auth_vars: dict, row: pd.Series, mapping: dict) -> dict:
    """
    Monta o payload JSON para um registro.

    campos    — lista de campos configurados do endpoint
    auth_vars — dict de variáveis do ambiente selecionado
    row       — linha do DataFrame
    mapping   — {campo_path: {"coluna": str, "extrair": str|None}}
                (apenas campos tipo "planilha")
    """
    flat: dict = {}

    for campo in campos:
        path = campo["path"]
        tipo = campo.get("tipo", "planilha")

        if tipo == "auth":
            auth_var = campo.get("auth_var", "")
            flat[path] = auth_vars.get(auth_var, "")

        elif tipo == "fixo":
            flat[path] = campo.get("valor_fixo", "")

        elif tipo == "planilha":
            cfg    = mapping.get(path) or {}
            coluna = cfg.get("coluna")
            if coluna:  # campo não mapeado → não inclui no payload
                flat[path] = extrair_valor(row[coluna], cfg.get("extrair"))

    return reconstruct_json(flat)


def chamar_endpoint(base_url: str, metodo: str, path: str, payload: dict) -> dict:
    """Executa a requisição HTTP e retorna o JSON de resposta."""
    url  = base_url.rstrip("/") + "/" + path.lstrip("/")
    resp = requests.request(metodo, url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()
