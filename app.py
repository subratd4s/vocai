"""Premium Streamlit interface for the vocabulary learning workflow."""

import html
import os

import streamlit as st
from agents.text_analyzer import InputValidationError
from models.vocabulary_model import DifficultyLevel
from services.file_service import (
    DEFINITIONS_FILENAME, DEFINITIONS_MIME, FileGenerationError,
    generate_definitions_file, validate_workflow_result,
)
from services.llm_service import LLMServiceError
from ui.presentation import icon, orb_markup, shell
from utils.config import load_environment
from utils.helpers import count_words
from workflows.vocabulary_workflow import run_vocabulary_workflow

def reset_feedback() -> None:
    """Discard results when the passage or settings change."""
    st.session_state.validation_status = None
    st.session_state.analysis_result = None
    st.session_state.analysis_signature = None
    st.session_state.workflow_state = None
    st.session_state.download_content = None


def clear_text() -> None:
    """Reset application-owned state before Streamlit redraws the widgets."""
    st.session_state.passage = ""
    reset_feedback()


def select_analysis_setting(name: str, value: str | int) -> None:
    """Apply a click-only analysis option and discard results for old settings."""
    if st.session_state[name] != value:
        st.session_state[name] = value
        reset_feedback()


def render_entry_card(entry, index: int) -> None:
    """Render a validated vocabulary item with clear editorial hierarchy."""
    with st.container(border=True, key=f"vocabulary-entry-{index}"):
        st.markdown(
            f'<div class="word-title">{html.escape(entry.word)}<span class="difficulty-chip">'
            f'{html.escape(entry.difficulty_level.value)}</span></div>', unsafe_allow_html=True,
        )
        st.markdown('<div class="entry-label">Meaning in this passage</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="entry-copy">{html.escape(entry.definition)}</p>', unsafe_allow_html=True)
        st.markdown('<div class="entry-label">Original context</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="entry-copy"><em>“{html.escape(entry.original_context)}”</em></p>', unsafe_allow_html=True)
        st.markdown('<div class="entry-label">Example sentence</div>', unsafe_allow_html=True)
        st.markdown(f'<p class="entry-copy">{html.escape(entry.example_sentence)}</p>', unsafe_allow_html=True)


def main() -> None:
    """Render the interactive learning experience without implicit API requests."""
    load_environment()
    st.set_page_config(page_title="Vocabulary Builder", page_icon="📖", layout="wide")
    defaults = (
        ("passage", ""), ("validation_status", None), ("analysis_result", None),
        ("analysis_signature", None), ("workflow_state", None), ("download_content", None),
        ("input_signature", None), ("difficulty", "Intermediate"), ("max_words", 10),
    )
    for key, default in defaults:
        if key not in st.session_state:
            st.session_state[key] = default
    if st.session_state.difficulty not in [level.value for level in DifficultyLevel]:
        select_analysis_setting("difficulty", "Intermediate")
    if st.session_state.max_words not in (5, 10, 15, 20):
        select_analysis_setting("max_words", 10)

    configured = bool(os.getenv("GEMINI_API_KEY", "").strip()) and os.getenv("GEMINI_API_KEY") != "your_api_key_here"
    st.markdown(shell(configured), unsafe_allow_html=True)
    st.markdown(f'<section class="hero" id="home"><div class="hero-orb" aria-hidden="true">{orb_markup()}</div><h1>What would you like to learn today?</h1></section>', unsafe_allow_html=True)
    st.markdown('<div id="workspace"></div>', unsafe_allow_html=True)
    with st.container(key="composer"):
        st.text_area(
            "Paste a paragraph or passage", key="passage", height=150,
            placeholder="Paste your text here and let AI uncover new vocabulary...",
            label_visibility="collapsed", on_change=reset_feedback,
        )
        difficulty_column, maximum_column, spacer_column, clear_column, analyze_column = st.columns([1.9, 1.45, 4.6, .58, .7])
        with difficulty_column:
            with st.popover(st.session_state.difficulty, use_container_width=True):
                st.caption("Difficulty level")
                for level in DifficultyLevel:
                    st.button(
                        level.value, key=f"select_difficulty_{level.value}",
                        on_click=select_analysis_setting, args=("difficulty", level.value),
                        type="primary" if st.session_state.difficulty == level.value else "secondary",
                        use_container_width=True,
                    )
        with maximum_column:
            with st.popover(f"{st.session_state.max_words} words", use_container_width=True):
                st.caption("Maximum vocabulary words")
                for count in (5, 10, 15, 20):
                    st.button(
                        f"{count} words", key=f"select_max_words_{count}",
                        on_click=select_analysis_setting, args=("max_words", count),
                        type="primary" if st.session_state.max_words == count else "secondary",
                        use_container_width=True,
                    )
        with clear_column:
            st.button("×", key="clear", on_click=clear_text, help="Clear text and results")
        with analyze_column:
            analyze = st.button("↑", key="analyze", type="primary", help="Analyze vocabulary")
    with st.container(key="input_footer"):
        count_column, powered_column = st.columns(2)
        with count_column:
            st.caption(f"{count_words(st.session_state.passage)} words")
        with powered_column:
            st.caption("Powered by Agentic AI")

    signature = (st.session_state.passage, st.session_state.difficulty, st.session_state.max_words)
    if st.session_state.input_signature not in (None, signature):
        reset_feedback()
    st.session_state.input_signature = signature
    workflow = st.session_state.workflow_state
    if workflow is not None and (
        not isinstance(workflow, dict) or not isinstance(workflow.get("stage_status"), dict)
        or not all(key in workflow for key in ("retry_count", "validation_status", "validation_errors"))
        or workflow.get("original_text") != st.session_state.passage
    ):
        reset_feedback()
        st.session_state.validation_status = ("warning", "The saved workflow state was incomplete. Please analyze the passage again.")
    saved = st.session_state.analysis_result
    if saved is not None:
        try:
            if st.session_state.analysis_signature != signature or (
                saved["original_text"], DifficultyLevel(saved["selected_difficulty"]).value, saved["max_words"]
            ) != signature:
                raise ValueError
            validate_workflow_result(saved)
        except (FileGenerationError, KeyError, TypeError, ValueError):
            reset_feedback()
            st.session_state.validation_status = ("warning", "Your saved results no longer match this analysis. Please analyze the passage again.")
    elif st.session_state.analysis_signature is not None:
        reset_feedback()

    if analyze and st.session_state.analysis_signature != signature:
        reset_feedback()
        try:
            with st.spinner("Your AI agents are analyzing the passage and building your vocabulary..."):
                result = run_vocabulary_workflow(*signature)
            if result["validation_status"] == "valid":
                validate_workflow_result(result)
                st.session_state.analysis_result = result
                st.session_state.analysis_signature = signature
            else:
                kind = "warning" if result["error_kind"] == "input" else "error"
                st.session_state.validation_status = (kind, result["error_message"])
            st.session_state.workflow_state = result
        except FileGenerationError:
            st.session_state.validation_status = ("error", "The analysis returned inconsistent results. Please try again.")
        except InputValidationError as error:
            st.session_state.validation_status = ("warning", str(error))
        except LLMServiceError as error:
            st.session_state.validation_status = ("error", str(error))
        except Exception:
            st.session_state.validation_status = ("error", "An unexpected error occurred. Please try again later.")
    if st.session_state.analysis_result is None:
        st.session_state.download_content = None
    if st.session_state.validation_status:
        kind, message = st.session_state.validation_status
        with st.container(key="validation_notice"):
            (st.warning if kind == "warning" else st.error)(message)

    st.markdown('<div id="vocabulary"></div>', unsafe_allow_html=True)
    current_result = st.session_state.analysis_result
    current_workflow = st.session_state.workflow_state
    if current_result is not None or current_workflow is not None:
        with st.container(key="results"):
            heading = "Your Vocabulary, Uncovered." if current_result is not None else "Analysis could not finish."
            st.markdown(f'<h2>{heading}</h2>', unsafe_allow_html=True)
            if current_workflow is not None:
                st.markdown('<div class="section-kicker">Workflow status</div>', unsafe_allow_html=True)
                status_columns = st.columns(4)
                stage_names = ("Text Analysis", "Word Identification", "Definition Generation", "Validation")
                for column, stage in zip(status_columns, stage_names):
                    with column:
                        current_status = current_workflow["stage_status"].get(stage, "Pending")
                        label = "Passed" if stage == "Validation" and current_workflow["validation_status"] == "valid" else current_status
                        st.markdown(f'<div class="stage-chip"><span>{stage}</span><strong>{label}</strong></div>', unsafe_allow_html=True)
                if current_workflow["validation_status"] == "failed" and current_workflow["validation_errors"]:
                    with st.expander("Validation details"):
                        for message in current_workflow["validation_errors"]:
                            st.write(message)
            if current_result is not None:
                total, identified, level, validation = st.columns(4)
                total.metric("Words analyzed", current_result["total_words_analyzed"])
                identified.metric("Vocabulary discovered", len(current_result["identified_words"]))
                level.metric("Difficulty", DifficultyLevel(current_result["selected_difficulty"]).value)
                validation.metric("Validation", "Passed" if current_result["validation_status"] == "valid" else "Review")
                if not current_result["identified_words"]:
                    st.info("No challenging vocabulary words were identified for the selected difficulty level.")
                for index, entry in enumerate(validate_workflow_result(current_result), 1):
                    render_entry_card(entry, index)

    current_result = st.session_state.analysis_result
    if current_result is not None:
        with st.container(key="export"):
            if current_result["identified_words"]:
                try:
                    st.session_state.download_content = generate_definitions_file(current_result)
                except FileGenerationError as error:
                    st.error(str(error))
                except Exception:
                    st.error("Unable to prepare Definitions.txt. Your validated analysis is saved; try again without another AI request.")
                if st.session_state.download_content is not None:
                    export_icon, export_info, export_button = st.columns([.55, 4, 1.5])
                    with export_icon:
                        st.markdown(f'<div class="export-icon">{icon("file")}</div>', unsafe_allow_html=True)
                    with export_info:
                        st.markdown('<div class="export-name">Definitions.txt</div>', unsafe_allow_html=True)
                        st.markdown(f'<div class="export-meta">{len(current_result["identified_words"])} vocabulary entries · UTF-8 text</div>', unsafe_allow_html=True)
                    with export_button:
                        st.download_button("Download file", data=st.session_state.download_content, file_name=DEFINITIONS_FILENAME, mime=DEFINITIONS_MIME, on_click="ignore")
                    with st.expander("Preview Definitions.txt"):
                        st.code(st.session_state.download_content.decode("utf-8"), language=None)

if __name__ == "__main__":
    main()
