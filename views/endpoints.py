"""
Página: Endpoints
Cadastro de endpoints: URL, método, JSON de exemplo e configuração de campos.

Tipos de campo:
  auth     → preenchido com variável do ambiente selecionado no envio
  fixo     → valor constante definido aqui
  planilha → mapeado pelo usuário na tela de envio

FUTURE (login): restringir a perfil "admin".
"""

import json

import streamlit as st

import db
from utils import parse_campos_json, merge_campos

METODOS = ["POST", "PATCH", "PUT", "GET", "DELETE"]
TIPOS   = ["planilha", "auth", "fixo"]
TIPO_LABELS = {"planilha": "📋 Planilha", "auth": "🔐 Auth", "fixo": "🔒 Fixo"}


def show() -> None:
    st.title("📌 Endpoints")
    st.caption("Cadastre os endpoints da API e configure como cada campo do JSON será preenchido.")

    view = st.session_state.get("_ep_view", "list")

    if view == "list":
        _lista()
    else:
        _formulario()


# ─── Lista ─────────────────────────────────────────────────────────────────────

def _lista() -> None:
    endpoints = db.listar_endpoints()

    col_titulo, col_btn = st.columns([5, 1])
    with col_titulo:
        st.subheader("Endpoints cadastrados")
    with col_btn:
        if st.button("➕ Novo", use_container_width=True, type="primary"):
            _ir_form(None)

    if not endpoints:
        st.info("Nenhum endpoint cadastrado ainda. Clique em **➕ Novo** para começar.")
        return

    for ep in endpoints:
        campos = json.loads(ep["campos"] or "[]")
        n_plan = sum(1 for c in campos if c.get("tipo") == "planilha")
        n_auth = sum(1 for c in campos if c.get("tipo") == "auth")
        n_fixo = sum(1 for c in campos if c.get("tipo") == "fixo")

        with st.expander(f"**{ep['nome']}** — `{ep['metodo']} {ep['path']}`"):
            st.caption(
                f"Campos: 📋 {n_plan} planilha · 🔐 {n_auth} auth · 🔒 {n_fixo} fixo"
            )
            col_ed, col_del = st.columns([1, 1])
            with col_ed:
                if st.button("✏️ Editar", key=f"ed_ep_{ep['id']}", use_container_width=True):
                    _ir_form(ep["id"])
            with col_del:
                if st.button("🗑️ Excluir", key=f"del_ep_{ep['id']}", use_container_width=True):
                    db.excluir_endpoint(ep["id"])
                    st.success("Endpoint excluído.")
                    st.rerun()


# ─── Formulário ────────────────────────────────────────────────────────────────

def _formulario() -> None:
    edit_id = st.session_state.get("_ep_edit_id")
    titulo  = "Editar endpoint" if edit_id else "Novo endpoint"
    st.subheader(titulo)

    ep = db.buscar_endpoint(edit_id) if edit_id else None

    # ── Dados básicos ─────────────────────────────────────────────────────────
    col1, col2 = st.columns([3, 1])
    with col1:
        nome = st.text_input("Nome *", value=ep["nome"] if ep else "")
    with col2:
        metodo_idx = METODOS.index(ep["metodo"]) if ep and ep["metodo"] in METODOS else 0
        metodo = st.selectbox("Método *", METODOS, index=metodo_idx)

    path = st.text_input(
        "Path *",
        value=ep["path"] if ep else "",
        placeholder="/webmanager/api/MeuModulo/MinhaEntidade/Gravar",
        help="Caminho relativo à base URL do ambiente. A URL final = base_url + path.",
    )

    st.markdown("---")

    # ── JSON de exemplo ───────────────────────────────────────────────────────
    st.markdown("**JSON de exemplo**")
    st.caption(
        "Cole o JSON completo que a API espera receber. "
        "Campos aninhados serão listados em notação ponto (ex.: `Data.Entidade.Campo`)."
    )

    json_exemplo_salvo = ""
    if ep:
        campos_db = json.loads(ep["campos"] or "[]")
        # Reconstrói o JSON de exemplo a partir dos paths salvos para exibição
        json_exemplo_salvo = json.dumps(
            {c["path"]: "..." for c in campos_db}, indent=2
        )

    json_raw = st.text_area(
        "JSON de exemplo",
        value=st.session_state.get("_ep_json_raw", json_exemplo_salvo),
        height=200,
        label_visibility="collapsed",
        key="_ep_json_textarea",
        placeholder='{\n  "AuthToken": {"Username": "", "Password": ""},\n  "Data": {"Entidade": {"Campo": ""}}\n}',
    )
    st.session_state["_ep_json_raw"] = json_raw

    if st.button("🔍 Carregar campos do JSON"):
        novos = parse_campos_json(json_raw)
        if novos is None:
            st.error("❌ JSON inválido. Verifique a sintaxe e tente novamente.")
        else:
            existentes = st.session_state.get("_ep_campos", [])
            st.session_state["_ep_campos"] = merge_campos(novos, existentes)
            # Reinicia os widgets de configuração de campo
            _limpar_widgets_campo()
            # Pré-carrega valores salvos no banco (edição)
            if ep:
                _init_widgets_campo(json.loads(ep["campos"] or "[]"))
            st.rerun()

    # ── Configuração dos campos ───────────────────────────────────────────────
    campos = st.session_state.get("_ep_campos", [])

    # Ao entrar em modo de edição sem ter clicado em "Carregar campos" ainda:
    if not campos and ep:
        campos = json.loads(ep["campos"] or "[]")
        st.session_state["_ep_campos"] = campos
        _init_widgets_campo(campos)

    if campos:
        st.markdown("---")
        st.markdown("**Configuração dos campos**")
        st.caption(
            "Para cada campo do JSON, defina o tipo: "
            "**📋 Planilha** (mapeado pelo usuário), "
            "**🔐 Auth** (preenchido pelo ambiente), "
            "**🔒 Fixo** (valor constante)."
        )

        _render_campos(campos)

    st.markdown("---")
    col_salvar, col_cancelar = st.columns([1, 1])

    with col_salvar:
        if st.button("💾 Salvar endpoint", type="primary", use_container_width=True):
            if not nome.strip() or not path.strip():
                st.error("❌ Nome e Path são obrigatórios.")
            elif not campos:
                st.error("❌ Carregue o JSON e configure ao menos um campo.")
            else:
                campos_salvos = _coletar_campos(campos)
                db.salvar_endpoint(nome.strip(), metodo, path.strip(), campos_salvos, edit_id)
                st.success("✅ Endpoint salvo!")
                _ir_lista()

    with col_cancelar:
        if st.button("Cancelar", use_container_width=True):
            _ir_lista()


# ─── Renderização dos campos ───────────────────────────────────────────────────

def _render_campos(campos: list) -> None:
    # Cabeçalho
    h1, h2, h3 = st.columns([4, 2, 4])
    h1.markdown("**Path do campo**")
    h2.markdown("**Tipo**")
    h3.markdown("**Configuração**")
    st.markdown("---")

    for i, campo in enumerate(campos):
        c1, c2, c3 = st.columns([4, 2, 4])

        with c1:
            st.code(campo["path"], language=None)

        with c2:
            tipo_atual = st.selectbox(
                "tipo",
                options=TIPOS,
                format_func=lambda t: TIPO_LABELS[t],
                index=TIPOS.index(st.session_state.get(f"_ep_c_{i}_tipo", campo.get("tipo", "planilha"))),
                key=f"_ep_c_{i}_tipo",
                label_visibility="collapsed",
            )

        with c3:
            if tipo_atual == "auth":
                auth_vars_disponiveis = _auth_vars_cadastradas()
                valor_atual = st.session_state.get(f"_ep_c_{i}_authvar", campo.get("auth_var", ""))
                if auth_vars_disponiveis:
                    # Garante que o valor atual aparece na lista mesmo se vier de outro ambiente
                    opcoes = sorted(set(auth_vars_disponiveis) | ({valor_atual} if valor_atual else set()))
                    idx = opcoes.index(valor_atual) if valor_atual in opcoes else 0
                    st.selectbox(
                        "Variável de auth",
                        options=opcoes,
                        index=idx,
                        key=f"_ep_c_{i}_authvar",
                        label_visibility="collapsed",
                        help="Variáveis disponíveis nos ambientes cadastrados.",
                    )
                else:
                    st.text_input(
                        "Nome da variável de auth",
                        value=valor_atual,
                        key=f"_ep_c_{i}_authvar",
                        placeholder="ex.: Username",
                        label_visibility="collapsed",
                        help="Cadastre um ambiente primeiro para ver as variáveis disponíveis.",
                    )

            elif tipo_atual == "fixo":
                st.text_input(
                    "Valor fixo",
                    value=st.session_state.get(f"_ep_c_{i}_fixo", campo.get("valor_fixo", "")),
                    key=f"_ep_c_{i}_fixo",
                    placeholder="ex.: 19",
                    label_visibility="collapsed",
                )

            else:  # planilha
                col_label, col_obrig = st.columns([3, 1])
                with col_label:
                    st.text_input(
                        "Label",
                        value=st.session_state.get(
                            f"_ep_c_{i}_label",
                            campo.get("label", campo["path"].split(".")[-1])
                        ),
                        key=f"_ep_c_{i}_label",
                        label_visibility="collapsed",
                        placeholder="Label para o usuário",
                    )
                with col_obrig:
                    st.checkbox(
                        "Obrig.",
                        value=st.session_state.get(f"_ep_c_{i}_obrig", campo.get("obrigatorio", False)),
                        key=f"_ep_c_{i}_obrig",
                    )


def _coletar_campos(campos: list) -> list:
    """Lê os valores dos widgets e monta a lista de campos para salvar."""
    resultado = []
    for i, campo in enumerate(campos):
        tipo = st.session_state.get(f"_ep_c_{i}_tipo", "planilha")
        c: dict = {"path": campo["path"], "tipo": tipo}

        if tipo == "auth":
            c["auth_var"] = st.session_state.get(f"_ep_c_{i}_authvar", "").strip()
        elif tipo == "fixo":
            c["valor_fixo"] = st.session_state.get(f"_ep_c_{i}_fixo", "").strip()
        else:
            c["label"]       = st.session_state.get(f"_ep_c_{i}_label", campo["path"].split(".")[-1]).strip()
            c["obrigatorio"] = st.session_state.get(f"_ep_c_{i}_obrig", False)

        resultado.append(c)
    return resultado


# ─── Helpers de estado ─────────────────────────────────────────────────────────

def _init_widgets_campo(campos: list) -> None:
    """Pré-carrega os valores dos campos no session state (modo edição)."""
    for i, campo in enumerate(campos):
        tipo = campo.get("tipo", "planilha")
        st.session_state[f"_ep_c_{i}_tipo"] = tipo
        if tipo == "auth":
            st.session_state[f"_ep_c_{i}_authvar"] = campo.get("auth_var", "")
        elif tipo == "fixo":
            st.session_state[f"_ep_c_{i}_fixo"] = campo.get("valor_fixo", "")
        else:
            st.session_state[f"_ep_c_{i}_label"] = campo.get("label", campo["path"].split(".")[-1])
            st.session_state[f"_ep_c_{i}_obrig"] = campo.get("obrigatorio", False)


def _limpar_widgets_campo() -> None:
    for key in list(st.session_state.keys()):
        if key.startswith("_ep_c_"):
            del st.session_state[key]


def _auth_vars_cadastradas() -> list[str]:
    """Retorna a lista única de nomes de variáveis de auth de todos os ambientes."""
    import json as _json
    ambientes = db.listar_ambientes()
    nomes: set[str] = set()
    for amb in ambientes:
        nomes.update(_json.loads(amb["auth_vars"] or "{}").keys())
    return sorted(nomes)


def _ir_form(id_: int | None) -> None:
    st.session_state["_ep_view"]    = "form"
    st.session_state["_ep_edit_id"] = id_
    st.session_state["_ep_campos"]  = []
    st.session_state.pop("_ep_json_raw", None)
    _limpar_widgets_campo()
    st.rerun()


def _ir_lista() -> None:
    st.session_state["_ep_view"]    = "list"
    st.session_state["_ep_edit_id"] = None
    st.session_state["_ep_campos"]  = []
    st.session_state.pop("_ep_json_raw", None)
    _limpar_widgets_campo()
    st.rerun()
