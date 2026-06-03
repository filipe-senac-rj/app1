"""
Entrada principal — MXM Integrador.

Perfis:
  admin    → acesso a tudo (Ambientes, Endpoints, Usuários, Envio, Histórico)
  operador → apenas Envio e Histórico
"""

import streamlit as st

import db
from views import ambientes, endpoints, envio, historico, login, usuarios

# ─── Páginas por perfil ────────────────────────────────────────────────────────

PAGES_ADMIN = {
    "🌐  Ambientes": ambientes.show,
    "📌  Endpoints": endpoints.show,
    "👥  Usuários":  usuarios.show,
    "📤  Envio":     envio.show,
    "📊  Histórico": historico.show,
}

PAGES_OPERADOR = {
    "📤  Envio":     envio.show,
    "📊  Histórico": historico.show,
}


def _get_pages() -> dict:
    perfil = st.session_state.get("_user", {}).get("perfil", "operador")
    return PAGES_ADMIN if perfil == "admin" else PAGES_OPERADOR


# ─── Sidebar ───────────────────────────────────────────────────────────────────

def render_sidebar() -> str:
    pages = _get_pages()
    user  = st.session_state.get("_user", {})

    with st.sidebar:
        st.markdown("## 🏢 MXM Integrador - deploy automático 123")
        st.markdown("---")

        # Garante que a página atual é válida para o perfil
        if st.session_state.get("_page") not in pages:
            st.session_state["_page"] = list(pages.keys())[0]

        for label in pages:
            active = st.session_state["_page"] == label
            if st.button(label, use_container_width=True,
                         type="primary" if active else "secondary",
                         key=f"nav_{label}"):
                st.session_state["_page"] = label
                st.rerun()

        st.markdown("---")

        # Info do usuário logado
        perfil_icon = "🔑" if user.get("perfil") == "admin" else "👤"
        st.caption(f"{perfil_icon} **{user.get('nome', '')}**")
        st.caption(f"{user.get('email', '')} · {user.get('perfil', '').capitalize()}")

        if st.button("🚪 Sair", use_container_width=True):
            st.session_state.pop("_user", None)
            st.session_state.pop("_page", None)
            st.rerun()

        st.markdown("---")
        st.caption("v2.0 · SQLite local")

    return st.session_state["_page"]


# ─── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    st.set_page_config(
        page_title="MXM Integrador",
        page_icon="🏢",
        layout="wide",
    )

    db.init_db()

    # Autenticação
    if not st.session_state.get("_user"):
        login.show()
        return

    page_sel = render_sidebar()
    _get_pages()[page_sel]()


if __name__ == "__main__":
    main()

