"""Streamlit entry point for the Phase 1 Vocabulary Builder Agent."""

from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from utils.helpers import count_words


def reset_feedback() -> None:
    """Discard feedback and future results when the passage changes."""
    st.session_state.validation_status = None
    st.session_state.analysis_result = None


def clear_text() -> None:
    """Reset application-owned state before Streamlit redraws the widgets."""
    st.session_state.passage = ""
    reset_feedback()


def main() -> None:
    """Render the foundation UI without invoking any AI or export service."""
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
    st.set_page_config(
        page_title="Vocabulary Builder Agent", page_icon="📖", layout="wide"
    )
    for key, default in (
        ("passage", ""),
        ("validation_status", None),
        ("analysis_result", None),
    ):
        if key not in st.session_state:
            st.session_state[key] = default

    st.markdown(
        """<style>
        .block-container { max-width: 1100px; padding-top: 2.5rem; }
        h1 { letter-spacing: -0.035em; }
        textarea { line-height: 1.65 !important; }
        </style>""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.title("Vocabulary Builder Agent")
        st.write(
            "An academic Agentic AI project designed to help you learn "
            "new words in the context of your reading."
        )
        st.divider()
        st.subheader("How It Works")
        st.write("Input Text → Identify Words → Generate Definitions → Export Results")
        st.divider()
        st.success("Status: Phase 1 · Input interface ready")
        st.caption("AI analysis and file export are planned for later phases.")

    st.title("Vocabulary Builder Agent")
    st.write("Transform your reading into a smarter vocabulary learning experience.")
    st.divider()
    st.subheader("Start with your reading")
    st.text_area(
        "Paste a paragraph or passage",
        key="passage",
        height=260,
        placeholder=(
            "The inquisitive student explored the intricate connections between "
            "language and culture. Through persistent reading, she developed "
            "a nuanced understanding of unfamiliar expressions and their context."
        ),
        on_change=reset_feedback,
    )
    st.caption(f"Word count: {count_words(st.session_state.passage)}")
    st.caption("The count updates when you finish editing and click outside the text box.")
    analyze_column, clear_column = st.columns(2)
    with analyze_column:
        analyze = st.button("Analyze Vocabulary", type="primary", use_container_width=True)
    with clear_column:
        st.button("Clear Text", on_click=clear_text, use_container_width=True)

    if analyze:
        st.session_state.validation_status = (
            "valid" if st.session_state.passage.strip() else "empty"
        )
    if st.session_state.validation_status == "empty":
        st.warning("Please enter a paragraph or passage before analyzing your vocabulary.")
    elif st.session_state.validation_status == "valid":
        st.success(
            "Input validated successfully. AI vocabulary analysis will be implemented in Phase 2."
        )

    st.divider()
    st.subheader("Your Vocabulary Insights")
    st.info("Your identified vocabulary words and definitions will appear here after analysis.")
    st.subheader("Download")
    st.button("Download Definitions.txt", disabled=True)
    st.caption("File export will be available in a later phase.")


if __name__ == "__main__":
    main()
