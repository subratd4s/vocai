# Vocabulary Builder Agent

An academic Agentic AI project for learning vocabulary while reading. The planned
system will analyze a passage, select difficult words, generate contextual
definitions, validate the results, and export `Definitions.txt`.

**Phase 1 is implemented.** The app accepts text, counts words, validates input,
and clears session state. It does not call an LLM, run an agent workflow, generate
definitions, or export files. No API key is needed to launch it.

## Technologies

- Python 3.11+
- Streamlit for the interface and per-session input state
- Pydantic for validated vocabulary output contracts
- python-dotenv for optional local environment configuration
- pytest and Streamlit AppTest for automated checks
- LangGraph for future agent orchestration
- OpenAI API for future LLM integration, isolated behind a service boundary
- UTF-8 TXT for future export; no database required

## Folder structure

The repository root is the `VocabularyBuilderAgent/` project directory (the local
checkout folder may have a different name).

```text
VocabularyBuilderAgent/
├── app.py
├── agents/
│   ├── __init__.py
│   ├── text_analyzer.py
│   ├── word_identifier.py
│   ├── definition_generator.py
│   └── validator.py
├── workflows/
│   ├── __init__.py
│   └── vocabulary_workflow.py
├── services/
│   ├── __init__.py
│   ├── llm_service.py
│   └── file_service.py
├── models/
│   ├── __init__.py
│   └── vocabulary_model.py
├── utils/
│   ├── __init__.py
│   └── helpers.py
├── tests/
│   ├── __init__.py
│   └── test_app.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

`app.py` owns presentation and session state. `utils/helpers.py` counts
whitespace-separated words. `models/vocabulary_model.py` defines a vocabulary
entry (word, definition, original context, example sentence, and a beginner,
intermediate, or advanced difficulty level) and an analysis result containing
the original text and a list of entries. An empty list is a valid result.

The `agents/`, `workflows/`, and `services/` modules contain only documented
placeholders. Future agents will use `llm_service.py` rather than importing a
provider directly. The workflow will coordinate agents, while `file_service.py`
will format validated results for export. These boundaries allow a later provider
change without rewriting the interface.

## Installation

Install Python 3.11 or newer and open a terminal in the project root.

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Or on macOS / Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

An environment file is optional in Phase 1. For future API integration, copy
`.env.example` to `.env` and replace the placeholder locally. In PowerShell:

```powershell
Copy-Item .env.example .env
```

On macOS / Linux, use `cp .env.example .env`. Never commit real keys. `.env` is
ignored by Git, and existing process environment variables take precedence.

## Run

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit. Paste text, then click outside the text
area to update the word count (Streamlit commits text edits on blur, rather than
every keystroke). A word is a whitespace-separated token; this is not linguistic
tokenization. Analyze validates nonblank input and displays the Phase 2 notice.
Clear Text resets the passage, validation feedback, and reserved result state.
Editing a passage also clears stale feedback. State is per browser session and
is not saved to disk. The download control is intentionally disabled.

## Tests

```bash
python -m pytest -q
```

Tests cover startup without an API key, blank input, word counts, successful
validation, editing and clearing state, and Pydantic validation. Vocabulary
examples in tests are fixtures only; the application never displays fabricated
analysis results.

## Planned development phases

Only Phase 1 is delivered here. The remaining breakdown is a proposed roadmap
to refine with each subsequent phase's requirements.

1. **Foundation and initial UI:** modular structure, environment setup, input
   handling, output models, and baseline tests.
2. **AI integration:** provider adapter and initial contextual vocabulary analysis.
3. **Agent workflow:** LangGraph orchestration, word selection, definition
   generation, and validation nodes.
4. **Results and export:** interactive vocabulary review and `Definitions.txt` download.
5. **Quality and completion:** failure handling, broader tests, usability polish,
   and final project documentation.

The planned agentic behavior will involve autonomous word selection, contextual
reasoning, and structured workflow execution. Phase 1 establishes the boundaries
for that work; it does not yet demonstrate autonomous AI execution.
