"""Streamlit UI. Pipeline logic lives in humanizer/."""

import streamlit as st

from humanizer.config import (
    APP_NAME,
    CONFIG_FILE,
    DEFAULT_CHAIN,
    DEFAULT_TEMPERATURE,
    TRANSLATE_LANGUAGES,
    load_config,
    save_config,
)
from humanizer.pipeline import humanize_text

st.set_page_config(page_title=APP_NAME, page_icon="📝", layout="wide")

if "api_key" not in st.session_state:
    st.session_state["api_key"] = load_config().get("api_key", "")


def _persist_key() -> None:
    save_config({"api_key": st.session_state.get("api_key", "")})


with st.sidebar:
    st.header(APP_NAME)
    st.text_input(
        "DeepSeek API key",
        type="password",
        key="api_key",
        on_change=_persist_key,
        placeholder="sk-...",
    )
    if st.session_state.get("api_key"):
        st.caption(f"Key saved locally in {CONFIG_FILE}")

    chain = st.multiselect(
        "Translation chain",
        options=TRANSLATE_LANGUAGES,
        default=DEFAULT_CHAIN,
        key="chain",
        help="Hops run in the order selected, then back to English.",
    )
    if len(chain) < 2:
        st.info("Select at least two languages.")

    temperature = st.slider(
        "Temperature",
        min_value=1.0,
        max_value=1.5,
        value=DEFAULT_TEMPERATURE,
        step=0.05,
        key="temperature",
    )
    run_verification = st.toggle(
        "Run claim-preservation check",
        value=True,
        key="run_verification",
    )

st.title(APP_NAME)

text = st.text_area(
    "Text to humanize",
    height=360,
    placeholder="Paste English text (at least 50 words)…",
)
word_count = len(text.split())
st.caption(f"{word_count} words")

api_key = st.session_state.get("api_key", "")
disabled = not text.strip() or not api_key.strip() or len(chain) < 2

if st.button("Humanize", type="primary", disabled=disabled):
    with st.status("Running pipeline...", expanded=True) as status:

        def progress(stage: str, chunk_index: int, total_chunks: int) -> None:
            status.write(stage)

        try:
            st.session_state["result"] = humanize_text(
                text,
                api_key,
                chain=chain,
                temperature=temperature,
                run_verification=run_verification,
                progress_cb=progress,
            )
            status.update(label="Run complete", state="complete", expanded=False)
        except Exception as exc:
            st.session_state.pop("result", None)
            status.update(label="Run failed", state="error", expanded=False)
            st.error(str(exc))

result = st.session_state.get("result")
if result is not None:
    st.subheader("Output")
    st.text_area(
        "Humanized text",
        value=result.final_text,
        height=360,
        disabled=True,
        label_visibility="collapsed",
    )
    st.download_button(
        "Download .txt",
        data=result.final_text,
        file_name="humanized.txt",
        mime="text/plain",
    )

    if result.claim_loss:
        st.warning(
            "The claim-preservation check flagged possible loss. Review the original "
            "before using this output:\n\n"
            + "\n".join(f"- {item}" for item in result.claim_loss)
        )

    for stage in result.stages:
        with st.expander(f"Stage details — {stage.name}"):
            st.write(f"Name: {stage.name}")
            st.write(f"Seconds: {stage.seconds:.2f}")
            if stage.warnings:
                for warning in stage.warnings:
                    st.warning(warning)
            else:
                st.caption("No warnings")
            if stage.output:
                st.code(stage.output)

    if result.warnings and not any(s.warnings for s in result.stages):
        for warning in result.warnings:
            st.warning(warning)

st.divider()
st.markdown(
    "<small>This tool rewrites text. Submitting rewritten work as your own without "
    "attribution may breach your institution's academic policy.</small>",
    unsafe_allow_html=True,
)
