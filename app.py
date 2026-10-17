"""Streamlit interface for vocabulary analysis, preview, and TXT download."""

import streamlit as st
from agents.text_analyzer import InputValidationError
from models.vocabulary_model import DifficultyLevel
from services.file_service import (
    DEFINITIONS_FILENAME, DEFINITIONS_MIME, FileGenerationError,
    generate_definitions_file, validate_workflow_result,
)
from services.llm_service import LLMServiceError
from utils.config import load_environment
from utils.helpers import count_words
from workflows.vocabulary_workflow import run_vocabulary_workflow


def reset_feedback() -> None:
    """Discard feedback and results when the passage or settings change."""
    st.session_state.validation_status = None
    st.session_state.analysis_result = None
    st.session_state.analysis_signature = None
    st.session_state.workflow_state = None
    st.session_state.download_content = None


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
        ("workflow_state", None),
        ("download_content", None),
        ("input_signature", None),
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
        st.success("Status: Vocabulary analysis and TXT export ready")
        st.caption("Analysis requires an OpenAI API key. Preview and download use your validated results.")

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
    if st.session_state.input_signature not in (None, signature):
        reset_feedback()
    st.session_state.input_signature = signature
    workflow = st.session_state.workflow_state
    if workflow is not None and (
        not isinstance(workflow, dict)
        or not isinstance(workflow.get("stage_status"), dict)
        or not all(key in workflow for key in ("retry_count", "validation_status", "validation_errors"))
        or workflow.get("original_text") != st.session_state.passage
    ):
        reset_feedback()
        st.session_state.validation_status = ("warning", "The saved workflow state was incomplete. Please analyze the passage again.")
    # Recover safely from missing/legacy/corrupted saved state before rendering.
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
            st.session_state.validation_status = ("warning", "Your saved results no longer match this analysis. Please click Analyze Vocabulary again.")
    elif st.session_state.analysis_signature is not None:
        reset_feedback()
    if st.session_state.analysis_result is None:
        st.session_state.download_content = None
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
    if st.session_state.validation_status:
        kind, message = st.session_state.validation_status
        (st.warning if kind == "warning" else st.error)(message)

    st.divider()
    workflow = st.session_state.workflow_state
    if workflow is not None:
        st.subheader("Workflow Status")
        for stage, status in workflow["stage_status"].items():
            st.caption(f"{stage}: {status}")
        st.caption(f"Definition correction attempts: {workflow['retry_count']} / 1")
        if workflow["validation_status"] == "failed" and workflow["validation_errors"]:
            with st.expander("Validation details"):
                for message in workflow["validation_errors"]:
                    st.text(message)
    st.subheader("Your Vocabulary Insights")
    result = st.session_state.analysis_result
    if result is None:
        st.info("Your vocabulary words, definitions, and examples will appear here after successful analysis.")
    else:
        total, identified, difficulty = st.columns(3)
        total.metric("Total words in passage", result["total_words_analyzed"])
        identified.metric("Vocabulary words identified", len(result["identified_words"]))
        difficulty.metric("Selected difficulty level", DifficultyLevel(result["selected_difficulty"]).value)
        if not result["identified_words"]:
            st.info("No challenging vocabulary words were identified for the selected difficulty level.")
        for entry in validate_workflow_result(result):
            with st.container(border=True):
                st.subheader(entry.word)
                st.caption(f"Difficulty: {entry.difficulty_level.value}")
                st.markdown("**Definition**")
                st.text(entry.definition)
                st.markdown("**Original context**")
                st.text(entry.original_context)
                st.markdown("**Example sentence**")
                st.text(entry.example_sentence)
    st.subheader("Download")
    st.session_state.download_content = None
    if result is not None and result["identified_words"]:
        try:
            st.session_state.download_content = generate_definitions_file(result)
        except FileGenerationError as error:
            st.error(str(error))
        except Exception:
            st.error("Unable to prepare Definitions.txt. Your analysis is saved; click Analyze Vocabulary to retry file preparation without another AI request.")
        if st.session_state.download_content is not None:
            st.subheader("Definitions.txt Preview")
            st.code(st.session_state.download_content.decode("utf-8"), language=None)
            st.download_button(
                "Download Definitions.txt", data=st.session_state.download_content,
                file_name=DEFINITIONS_FILENAME, mime=DEFINITIONS_MIME, on_click="ignore",
            )
    else:
        st.caption("A download will be available after vocabulary results pass validation.")


if __name__ == "__main__":
    main()
