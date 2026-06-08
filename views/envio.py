"""
Página: Envio
Upload de planilha → mapeamento de colunas → envio à API.

Somente campos "planilha" aparecem no mapeamento.
Campos "auth" e "fixo" são preenchidos automaticamente.
Campos "planilha" sem mapeamento são omitidos do payload.
"""

import io
import json

import pandas as pd
import streamlit as st

import db

from api import build_payload, chamar_endpoint

from utils import extrair_valor, flatten_json, reconstruct_json

NAO_MAPEAR      = "-- Não mapear --"
PAGE_SIZE_OPTS  = [10, 20, 50, 100]
DEFAULT_PS_IDX  = 1   # 20 registros


def show() -> None:
    st.title("📤 Envio")

    endpoints = db.listar_endpoints()
    ambientes = db.listar_ambientes()

    if not endpoints:
        st.warning("Nenhum endpoint cadastrado. Vá até **📌 Endpoints** para criar um.")
        return
    if not ambientes:
        st.warning("Nenhum ambiente cadastrado. Vá até **🌐 Ambientes** para criar um.")
        return

    # ── Seleção de endpoint e ambiente ────────────────────────────────────────
    col_ep, col_amb = st.columns(2)
    with col_ep:
        ep_opcoes = {ep["nome"]: ep for ep in endpoints}
        ep_nome   = st.selectbox("Endpoint *", list(ep_opcoes.keys()))
        endpoint  = ep_opcoes[ep_nome]
    with col_amb:
        amb_opcoes = {amb["nome"]: amb for amb in ambientes}
        amb_nome   = st.selectbox("Ambiente *", list(amb_opcoes.keys()))
        ambiente   = amb_opcoes[amb_nome]

    campos_ep   = json.loads(endpoint["campos"] or "[]")
    campos_plan = [c for c in campos_ep if c.get("tipo") == "planilha"]
    auth_vars   = json.loads(ambiente["auth_vars"] or "{}")

    st.caption(
        f"URL: `{ambiente['base_url']}{endpoint['path']}` · "
        f"Método: `{endpoint['metodo']}` · "
        f"{len(campos_plan)} campo(s) para mapear"
    )
    st.markdown("---")

    # ── Upload ────────────────────────────────────────────────────────────────
    st.markdown("### 1️⃣ Upload do arquivo")
    arquivo = st.file_uploader("Selecione o arquivo Excel (.xlsx)", type=["xlsx"])

    if not arquivo:
        st.stop()

    try:
        df_raw = pd.read_excel(arquivo)
    except Exception as e:
        st.error(f"❌ Não foi possível ler o arquivo: {e}")
        st.stop()

    if df_raw.empty or len(df_raw.columns) == 0:
        st.error("❌ O arquivo está vazio ou sem colunas.")
        st.stop()

    df_raw  = df_raw.reset_index(drop=True)
    colunas = list(df_raw.columns)

    state_key  = f"_env_{endpoint['id']}_{arquivo.name}"
    editor_key = f"{state_key}_editor"
    sel_key    = f"{state_key}_sel"
    pg_key     = f"{state_key}_page"
    ps_key     = f"{state_key}_page_size"
    bk_key     = f"{state_key}_prev_busca"

    _ensure_state(state_key, len(df_raw))

    st.success(f"✅ **{arquivo.name}** — {len(df_raw)} registros · {len(colunas)} colunas")

    with st.expander("🔍 Pré-visualização (10 primeiras linhas)", expanded=True):
        st.dataframe(df_raw.head(10), use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── Mapeamento ────────────────────────────────────────────────────────────
    if not st.session_state.get(f"{state_key}_map_ok"):
        _step_mapeamento(campos_plan, colunas, state_key)
        st.stop()

    mapping = st.session_state[f"{state_key}_mapping"]

    with st.expander("✅ Mapeamento confirmado — clique para ver / refazer", expanded=False):
        _resumo_mapeamento(campos_plan, mapping)
        if st.button("🔁 Refazer mapeamento"):
            st.session_state[f"{state_key}_map_ok"] = False
            st.rerun()

    st.markdown("---")

    # ── Validação de auth ─────────────────────────────────────────────────────
    erros_cfg = _validar_auth(campos_ep, auth_vars)
    if erros_cfg:
        st.error(
            "❌ **Configuração incompleta no endpoint:**\n\n"
            + "\n".join(f"- {e}" for e in erros_cfg)
        )
        st.info("💡 Vá até **📌 Endpoints**, edite e verifique os campos de autenticação.")
        st.stop()

    # ── Preview do payload ────────────────────────────────────────────────────
    with st.expander("🔬 Inspecionar payload (primeira linha)", expanded=False):
        try:
            payload_raw  = build_payload(campos_ep, auth_vars, df_raw.iloc[0], mapping)
            payload_safe = _mascarar_senhas(payload_raw, campos_ep)
            st.json(payload_safe)
        except Exception as e:
            st.warning(f"Não foi possível gerar preview: {e}")

    st.markdown("### 3️⃣ Selecione os registros para envio")

    # ── Controles: busca + tamanho de página ─────────────────────────────────
    col_busca, col_ps = st.columns([4, 1])
    with col_busca:
        busca = st.text_input("🔍 Buscar em qualquer coluna...", key=f"{state_key}_busca")
    with col_ps:
        page_size = st.selectbox(
            "Por página",
            PAGE_SIZE_OPTS,
            index=st.session_state.get(ps_key, DEFAULT_PS_IDX),
            key=f"{state_key}_ps_sel",
        )
        new_ps_idx = PAGE_SIZE_OPTS.index(page_size)
        if new_ps_idx != st.session_state.get(ps_key, DEFAULT_PS_IDX):
            st.session_state[ps_key]  = new_ps_idx
            st.session_state[pg_key]  = 0
            _clear_editor(editor_key)

    # ── Filtragem ─────────────────────────────────────────────────────────────
    if busca:
        mask = df_raw.apply(
            lambda col: col.astype(str).str.contains(busca, case=False, na=False)
        ).any(axis=1)
        df_filtrado = df_raw[mask].copy()
    else:
        df_filtrado = df_raw.copy()

    idx_filtrados = list(df_filtrado.index)

    # Detecta mudança no filtro de busca
    if busca != st.session_state.get(bk_key, ""):
        st.session_state[bk_key]  = busca
        st.session_state[pg_key]  = 0
        _clear_editor(editor_key)

    # ── Paginação ─────────────────────────────────────────────────────────────
    total   = len(df_filtrado)
    n_pages = max(1, (total + page_size - 1) // page_size)

    if st.session_state[pg_key] >= n_pages:
        st.session_state[pg_key] = 0

    start    = st.session_state[pg_key] * page_size
    df_page  = df_filtrado.iloc[start : start + page_size].copy()
    idx_page = list(df_page.index)

    n_sel_total = sum(1 for i in idx_filtrados if st.session_state[sel_key].get(i))
    n_sel_page  = sum(1 for i in idx_page      if st.session_state[sel_key].get(i))

    # ── Botões de seleção ─────────────────────────────────────────────────────
    col_todos, col_pag, col_nenhum, col_info = st.columns([1, 1, 1, 4])

    with col_todos:
        if st.button("☑ Todos", use_container_width=True, help="Seleciona todos os registros filtrados"):
            for i in idx_filtrados:
                st.session_state[sel_key][i] = True
            _clear_editor(editor_key)

    with col_pag:
        if st.button("☑ Página", use_container_width=True, help="Seleciona apenas os registros desta página"):
            for i in idx_page:
                st.session_state[sel_key][i] = True
            _clear_editor(editor_key)

    with col_nenhum:
        if st.button("☐ Nenhum", use_container_width=True, help="Desmarca todos"):
            for i in idx_filtrados:
                st.session_state[sel_key][i] = False
            _clear_editor(editor_key)

    with col_info:
        st.caption(
            f"{total} registro(s) filtrado(s) · "
            f"**{n_sel_total}** selecionado(s) no total · "
            f"{n_sel_page} nesta página"
        )

    # ── Controles de página ───────────────────────────────────────────────────
    col_prev, col_pg_info, col_next = st.columns([1, 4, 1])
    with col_prev:
        if st.button("◀", disabled=(st.session_state[pg_key] == 0), use_container_width=True):
            st.session_state[pg_key] -= 1
            _clear_editor(editor_key)
            st.rerun()
    with col_pg_info:
        st.caption(f"Página **{st.session_state[pg_key] + 1}** de **{n_pages}**")
    with col_next:
        if st.button("▶", disabled=(st.session_state[pg_key] >= n_pages - 1), use_container_width=True):
            st.session_state[pg_key] += 1
            _clear_editor(editor_key)
            st.rerun()

    # ── Tabela editável ───────────────────────────────────────────────────────
    # Recalcula df_page (pode ter mudado após st.rerun não ter sido chamado ainda)
    start   = st.session_state[pg_key] * page_size
    df_page = df_filtrado.iloc[start : start + page_size].copy()
    idx_page = list(df_page.index)

    df_page.insert(0, "✔", [st.session_state[sel_key].get(i, False) for i in df_page.index])

    df_editado = st.data_editor(
        df_page,
        use_container_width=True,
        hide_index=True,
        column_config={"✔": st.column_config.CheckboxColumn("Enviar", default=False, width="small")},
        disabled=list(df_raw.columns),
        key=editor_key,
    )

    # Persiste seleção da página atual no state
    for idx, row in df_editado.iterrows():
        st.session_state[sel_key][idx] = bool(row["✔"])

    # ── Botão de envio ────────────────────────────────────────────────────────
    idx_sel   = [i for i in df_raw.index if st.session_state[sel_key].get(i)]
    df_enviar = df_raw.loc[idx_sel]

    st.markdown("---")
    col_txt, col_btn = st.columns([5, 1])
    with col_txt:
        st.markdown(f"**{len(df_enviar)}** registro(s) selecionado(s) para envio")
    with col_btn:
        btn_enviar = st.button(
            "🚀 Enviar", type="primary",
            disabled=(len(df_enviar) == 0),
            use_container_width=True,
        )

    if btn_enviar:
        campo_id   = next((c for c in campos_plan if c.get("obrigatorio")), campos_plan[0] if campos_plan else None)
        col_id_cfg = mapping.get(campo_id["path"]) if campo_id else {}

        resultados   = []
        progress_bar = st.progress(0, text="Iniciando...")
        status_txt   = st.empty()
        total_env    = len(df_enviar)

        for i, (_, row) in enumerate(df_enviar.iterrows()):
            identificador = (
                extrair_valor(row[col_id_cfg["coluna"]], col_id_cfg.get("extrair"))
                if col_id_cfg and col_id_cfg.get("coluna") else f"linha_{i+1}"
            )
            status_txt.caption(f"Enviando [{i+1}/{total_env}]: `{identificador}`")

            try:
                payload  = build_payload(campos_ep, auth_vars, row, mapping)
                resp     = chamar_endpoint(ambiente["base_url"], endpoint["metodo"], endpoint["path"], payload)
                sucesso  = resp.get("Success", False)
                msgs     = resp.get("Messages") or []
                mensagem = msgs[0].get("Message", "") if msgs else ""
            except Exception as e:
                sucesso  = False
                mensagem = str(e)

            resultados.append({"identificador": identificador, "sucesso": sucesso, "mensagem": mensagem})
            progress_bar.progress((i + 1) / total_env)

        progress_bar.empty()
        status_txt.empty()

        usuario_id = st.session_state.get("_user", {}).get("id")
        lote_id = db.salvar_lote(endpoint["id"], ambiente["id"], arquivo.name, resultados, usuario_id)
        n_ok    = sum(1 for r in resultados if r["sucesso"])
        n_err   = len(resultados) - n_ok

        if n_err == 0:
            st.success(f"✅ Lote **#{lote_id}** concluído — {n_ok} registro(s) com sucesso")
        else:
            st.warning(f"⚠️ Lote **#{lote_id}** — {n_ok} sucesso(s) / {n_err} erro(s)")

        df_res = pd.DataFrame(resultados)
        df_res["Status"] = df_res["sucesso"].map({True: "✅ Sucesso", False: "❌ Erro"})
        st.dataframe(
            df_res[["identificador", "Status", "mensagem"]].rename(columns={
                "identificador": "Identificador", "mensagem": "Mensagem"
            }),
            use_container_width=True, hide_index=True,
        )

        buf = io.BytesIO()
        df_res.to_excel(buf, index=False)
        buf.seek(0)
        st.download_button(
            "📥 Baixar resultado",
            data=buf,
            file_name=f"resultado_lote_{lote_id}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


# ─── Mapeamento ────────────────────────────────────────────────────────────────

def _step_mapeamento(campos_plan: list, colunas: list, state_key: str) -> None:
    st.markdown("### 2️⃣ Mapeamento de colunas")
    st.caption("Associe cada campo da API a uma coluna da planilha. Campos ✳️ são obrigatórios.")

    mapping_atual    = st.session_state.get(f"{state_key}_mapping", {})
    novo_mapping     = {}
    opcoes_opcionais = [NAO_MAPEAR] + colunas

    h1, h2, h3, h4 = st.columns([3, 3, 1, 1])
    h1.markdown("**Campo da API**")
    h2.markdown("**Coluna da planilha**")
    h3.markdown("**Extrair código**")
    h4.markdown("**Extrair descrição**")
    st.markdown("---")

    for campo in campos_plan:
        path    = campo["path"]
        label   = campo.get("label", path.split(".")[-1])
        obrig   = campo.get("obrigatorio", False)
        opcoes  = colunas if obrig else opcoes_opcionais

        cfg_atual = mapping_atual.get(path) or {}
        col_atual = cfg_atual.get("coluna")
        ext_atual = cfg_atual.get("extrair")
        sugestao  = col_atual if col_atual in opcoes else opcoes[0]

        c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
        with c1:
            st.markdown(f"{'✳️ ' if obrig else ''}**{label}**")
            st.caption(f"`{path}`")
        with c2:
            escolha = st.selectbox(
                label=label, options=opcoes,
                index=opcoes.index(sugestao),
                key=f"_map_{state_key}_{path}_col",
                label_visibility="collapsed",
            )
        with c3:
            ext_cod = st.checkbox(
                "código", value=(ext_atual == "codigo"),
                key=f"_map_{state_key}_{path}_cod",
                label_visibility="collapsed",
            )
        with c4:
            ext_desc = st.checkbox(
                "descrição", value=(ext_atual == "descricao"),
                key=f"_map_{state_key}_{path}_desc",
                label_visibility="collapsed",
            )

        extrair = "descricao" if ext_desc else ("codigo" if ext_cod else None)
        novo_mapping[path] = {
            "coluna":  None if escolha == NAO_MAPEAR else escolha,
            "extrair": extrair,
        }

    st.markdown("---")
    if st.button("✅ Confirmar mapeamento", type="primary"):
        faltando = [
            campo.get("label", campo["path"].split(".")[-1])
            for campo in campos_plan
            if campo.get("obrigatorio") and not novo_mapping[campo["path"]]["coluna"]
        ]
        if faltando:
            st.error("❌ Mapeie os campos obrigatórios:\n\n"
                     + "\n".join(f"- **{l}**" for l in faltando))
        else:
            st.session_state[f"{state_key}_mapping"] = novo_mapping
            st.session_state[f"{state_key}_map_ok"]  = True
            st.rerun()


def _resumo_mapeamento(campos_plan: list, mapping: dict) -> None:
    rows = []
    for campo in campos_plan:
        path = campo["path"]
        cfg  = mapping.get(path) or {}
        ext  = cfg.get("extrair")
        rows.append({
            "Campo API":          campo.get("label", path.split(".")[-1]),
            "Coluna da planilha": cfg.get("coluna") or "— não mapeado —",
            "Extração":           {"codigo": "✂️ código", "descricao": "✂️ descrição"}.get(ext, "como está")
                                  if cfg.get("coluna") else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ─── Utilitários ───────────────────────────────────────────────────────────────

def _clear_editor(editor_key: str) -> None:
    """Remove o estado interno do data_editor para forçar render limpo."""
    st.session_state.pop(editor_key, None)


def _mascarar_senhas(payload: dict, campos_ep: list) -> dict:
    flat = flatten_json(payload)
    for campo in campos_ep:
        if campo.get("tipo") == "auth":
            if any(s in campo.get("auth_var", "").lower() for s in ("password", "senha")):
                if campo["path"] in flat:
                    flat[campo["path"]] = "***"
    return reconstruct_json(flat)


def _validar_auth(campos_ep: list, auth_vars: dict) -> list[str]:
    erros = []
    for campo in campos_ep:
        if campo.get("tipo") != "auth":
            continue
        auth_var = campo.get("auth_var", "").strip()
        if not auth_var:
            erros.append(f"Campo `{campo['path']}` sem variável de auth definida.")
        elif auth_var not in auth_vars:
            disponiveis = ", ".join(f"`{k}`" for k in auth_vars) or "nenhuma"
            erros.append(f"Campo `{campo['path']}`: variável `{auth_var}` não existe no ambiente (disponíveis: {disponiveis}).")
    return erros


def _ensure_state(state_key: str, n: int) -> None:
    sel_key = f"{state_key}_sel"
    st.session_state.setdefault(sel_key,              {i: False for i in range(n)})
    st.session_state.setdefault(f"{state_key}_page",  0)
    st.session_state.setdefault(f"{state_key}_map_ok", False)
    st.session_state.setdefault(f"{state_key}_mapping", {})
    st.session_state.setdefault(f"{state_key}_page_size", DEFAULT_PS_IDX)
    st.session_state.setdefault(f"{state_key}_prev_busca", "")
