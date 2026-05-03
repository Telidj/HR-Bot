from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class ComposerAction:
    kind: str = "none"
    prompt: str = ""


def _queue_manual_submit() -> None:
    prompt = str(st.session_state.get("composer_draft", "")).strip()
    if not prompt:
        return

    # Update the request state before the next rerun begins rendering so the
    # idle composer is not painted one extra time during submit.
    st.session_state.queued_prompt = prompt
    st.session_state.drawer_open = False
    st.session_state.request_in_flight = True


def render_composer_styles() -> None:
    st.markdown(
        """
        <style>
        .st-key-composer_shell {
            margin-top: 0.9rem;
        }

        .st-key-composer_bar {
            border: 1px solid #343c4c;
            background: rgba(38, 39, 46, 0.96);
            border-radius: 28px;
            padding: 0.35rem 0.45rem;
            box-shadow: 0 18px 34px rgba(8, 12, 20, 0.16);
        }

        .st-key-composer_bar [data-testid="stHorizontalBlock"] {
            align-items: center;
            gap: 0.55rem;
            flex-wrap: nowrap;
        }

        .st-key-composer_bar [data-testid="stTextInput"],
        .st-key-composer_bar [data-testid="stButton"] {
            margin-bottom: 0;
        }

        .st-key-composer_bar [data-testid="stTextInput"] {
            flex: 1 1 auto;
            min-width: 0;
        }

        .st-key-composer_bar [data-testid="stButton"] {
            flex: 0 0 auto;
        }

        .st-key-composer_bar [data-testid="stForm"] {
            width: 100%;
        }

        .st-key-composer_bar form {
            width: 100%;
        }

        .st-key-composer_bar [data-testid="stTextInputRootElement"] {
            background: transparent !important;
        }

        .st-key-composer_bar [data-testid="stTextInputRootElement"] > div {
            border: none !important;
            background: transparent !important;
            box-shadow: none !important;
            min-height: 3.2rem;
        }

        .st-key-composer_bar input {
            color: #f2f5fb !important;
            background: transparent !important;
            min-height: 3.2rem !important;
            font-size: 1rem !important;
            line-height: 1.45 !important;
        }

        .st-key-composer_bar input:disabled {
            color: #f2f5fb !important;
            -webkit-text-fill-color: #f2f5fb !important;
            opacity: 1 !important;
        }

        .st-key-composer_bar input::placeholder {
            color: #b7bdc8 !important;
        }

        .st-key-composer_bar button {
            width: 3rem;
            min-width: 3rem;
            min-height: 3rem;
            border-radius: 999px !important;
            border: 1px solid #495062 !important;
            background: rgba(18, 24, 34, 0.18) !important;
            color: #f4f7fb !important;
            box-shadow: none !important;
            font-weight: 600 !important;
            padding: 0 !important;
        }

        .st-key-composer_bar button:hover {
            border-color: #6d7fa0 !important;
            background: rgba(52, 63, 81, 0.58) !important;
        }

        .st-key-composer_bar button:disabled {
            opacity: 1 !important;
            cursor: default !important;
        }

        .st-key-composer_bar [data-testid="column"]:last-child button {
            background: linear-gradient(135deg, #1d4ed8, #2563eb 58%, #3b82f6) !important;
            border-color: #78a8ff !important;
        }

        .st-key-composer_bar [data-testid="column"]:last-child button:hover {
            background: linear-gradient(135deg, #2157ec, #3170ff 58%, #4c8bff) !important;
        }

        .st-key-composer_bar [data-testid="column"]:first-child button {
            font-size: 1.45rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_composer(*, disabled: bool) -> ComposerAction:
    with st.container(key="composer_shell"):
        with st.container(key="composer_bar", horizontal=True, vertical_alignment="center", gap="small"):
            toggle_col, form_col = st.columns([1, 12], gap="small", vertical_alignment="center")

            with toggle_col:
                toggle_clicked = st.button(
                    "＋",
                    key="composer_toggle",
                    help="Open demo prompts",
                    width="content",
                    disabled=disabled,
                )

            with form_col:
                with st.form("composer_form", clear_on_submit=False, enter_to_submit=not disabled, border=False):
                    input_col, send_col = st.columns([12, 1], gap="small", vertical_alignment="center")
                    with input_col:
                        st.text_input(
                            "Ask an HR or IT question",
                            key="composer_draft",
                            placeholder="Ask an HR or IT question",
                            label_visibility="collapsed",
                            disabled=disabled,
                        )
                    with send_col:
                        st.form_submit_button(
                            "↑",
                            key="composer_send",
                            help="Send message",
                            width="content",
                            disabled=disabled,
                            on_click=_queue_manual_submit,
                        )

    if toggle_clicked:
        return ComposerAction(kind="toggle_drawer")

    return ComposerAction()
