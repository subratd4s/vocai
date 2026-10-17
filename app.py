"""Streamlit interface for vocabulary identification (Phase 2)."""

import streamlit as st
from agents.text_analyzer import InputValidationError
from agents.word_identifier import identify_words
from models.vocabulary_model import DifficultyLevel
from services.llm_service import LLMServiceError
from utils.config import load_environment
from utils.helpers import count_words


def reset_feedback() -> None:
    """Discard feedback and results when the passage or settings change."""
    st.session_state.validation_status = None
    st.session_state.analysis_result = None
    st.session_state.analysis_signature = None


def clear_text() -> None:
    """Reset application-owned state before Streamlit redraws the widgets."""
    st.session_state.passage = ""
    reset_feedback()


def main() -> None:
    """Render persisted results; make API calls only on explicit analysis clicks."""
    load_environment()
    st.set_page_config(
        page_title="Vocabulary Builder Agent", page_icon="📖", layout="wide"
    )
    for key, default in (
        ("passage", ""),
        ("validation_status", None),
        ("analysis_result", None),
        ("analysis_signature", None),
        ("difficulty", "Intermediate"),
        ("max_words", 10),
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
        st.success("Status: Phase 2 · Vocabulary identification ready")
        st.caption("Analysis requires an OpenAI API key. Definitions and export are planned for later phases.")

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
    difficulty_column, maximum_column = st.columns(2)
    with difficulty_column:
        st.selectbox("Difficulty level", [level.value for level in DifficultyLevel], key="difficulty", on_change=reset_feedback)
    with maximum_column:
        st.selectbox("Maximum vocabulary words", [5, 10, 15, 20], key="max_words", format_func=lambda value: f"{value} words", on_change=reset_feedback)
    signature = (st.session_state.passage, st.session_state.difficulty, st.session_state.max_words)
    if st.session_state.analysis_signature not in (None, signature):
        reset_feedback()
    analyze_column, clear_column = st.columns(2)
    with analyze_column:
        analyze = st.button("Analyze Vocabulary", type="primary", use_container_width=True)
    with clear_column:
        st.button("Clear Text", on_click=clear_text, use_container_width=True)

    if analyze:
        # Reuse the current successful result even if Analyze is clicked again.
        if st.session_state.analysis_signature != signature:
            reset_feedback()
            try:
                with st.spinner("Analyzing your text and identifying vocabulary..."):
                    result = identify_words(*signature)
                st.session_state.analysis_result = result
                st.session_state.analysis_signature = signature
            except InputValidationError as error:
                st.session_state.validation_status = ("warning", str(error))
            except LLMServiceError as error:
                st.session_state.validation_status = ("error", str(error))
            except Exception:
                st.session_state.validation_status = ("error", "An unexpected error occurred. Please try again later.")
    if st.session_state.validation_status:
        kind, message = st.session_state.validation_status
        (st.warning if kind == "warning" else st.error)(message)

    st.divider()
    st.subheader("Your Vocabulary Insights")
    result = st.session_state.analysis_result
    if result is None:
        st.info("Your identified vocabulary words and their context will appear here after analysis.")
    else:
        total, identified, difficulty = st.columns(3)
        total.metric("Total words in passage", result.total_words_analyzed)
        identified.metric("Vocabulary words identified", len(result.identified_words))
        difficulty.metric("Selected difficulty level", result.selected_difficulty.value)
        if not result.identified_words:
            st.info("No challenging vocabulary words were identified for the selected difficulty level.")
        for entry in result.identified_words:
            with st.container(border=True):
                st.subheader(entry.word)
                st.caption(f"Difficulty: {entry.difficulty_level.value}")
                st.text(entry.original_context)
    st.subheader("Download")
    st.button("Download Definitions.txt", disabled=True)
    st.caption("File export will be available in a later phase.")


if __name__ == "__main__":
    main()
