# Vocabulary Builder Agent

An academic Agentic AI project for learning vocabulary while reading. The planned
system will analyze a passage, select difficult words, generate contextual
definitions, validate the results, and export `Definitions.txt`.

**Phases 1 and 2 are implemented.** The app accepts text and identifies vocabulary
through OpenAI, with configurable difficulty and a maximum result count. Each
result includes the word, reader level, and original context. No API key is needed
to launch the UI; a key is required to analyze text. Definitions, LangGraph, and
file export are not implemented yet.

## Technologies

- Python 3.11+
- Streamlit for the interface and per-session input state
- Pydantic for validated vocabulary output contracts
- python-dotenv for optional local environment configuration
- pytest and Streamlit AppTest for automated checks
- LangGraph for future agent orchestration
- OpenAI Responses API with SDK Pydantic structured-output parsing
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
│   ├── prompts.py
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
│   ├── helpers.py
│   └── config.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_app.py
│   ├── test_identification.py
│   └── test_llm_service.py
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

`app.py` owns presentation and session state. `text_analyzer.py` validates input,
normalizes whitespace, and computes statistics. `word_identifier.py` coordinates
one structured request and deterministic validation through `validator.py`.
`prompts.py` contains selection criteria and instructions treating passage content
as untrusted data. `llm_service.py` owns SDK calls and sanitized error messages;
its `StructuredLLM` protocol allows replacement providers without UI changes.
`utils/config.py` loads environment settings and `helpers.py` counts words.

`models/vocabulary_model.py` preserves the complete Phase 1 vocabulary and analysis
models, with a shared difficulty enum accepting legacy lowercase values and
serializing title-case labels. Separate identification models omit definitions
and example sentences. `WordSelection` is the minimal LLM response;
`IdentificationResult` adds original text, selected difficulty, and locally
computed word count. An empty identified-words list is valid.

Definition generation, LangGraph workflow orchestration, and file export modules
remain placeholders for subsequent phases.

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

To enable analysis, copy `.env.example` to `.env` and replace the placeholder
locally. Do not overwrite an existing `.env` containing your settings. In PowerShell:

```powershell
Copy-Item .env.example .env
```

On macOS / Linux, use `cp .env.example .env`. Never commit real keys. `.env` is
ignored by Git, and existing process environment variables take precedence.

```dotenv
OPENAI_API_KEY=your_actual_api_key
OPENAI_MODEL=gpt-4o-mini
MAX_INPUT_CHARACTERS=5000
```

`OPENAI_MODEL` defaults to `gpt-4o-mini` when unset. A replacement OpenAI model
must support the Responses API and structured outputs. The configured key must
have model access and available API quota. The positive integer input limit
applies to the original submission, including whitespace, before normalization.
Configuration errors and missing credentials are shown only when analyzing.

The service uses the official SDK's `responses.parse(..., text_format=...)`
interface, described in the [OpenAI structured outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Each analysis makes one request, with a 30-second SDK timeout and automatic
retries disabled. Responses are requested with `store=False`. Input text is sent
to OpenAI only when you click Analyze for a new input/settings combination.

## Run

```bash
streamlit run app.py
```

Open the local URL printed by Streamlit. Paste text, then click outside the text
area to update the word count (Streamlit commits text edits on blur, rather than
every keystroke). A word is a whitespace-separated token; this is not linguistic
tokenization. Choose Beginner, Intermediate (default), or Advanced, and at most
5, 10 (default), 15, or 20 vocabulary words. The level changes the selection
criteria; the maximum never requires the model to fill a quota.

Analyze shows a loading spinner, then summary metrics and vocabulary cards with
context only. Results survive ordinary reruns; repeated Analyze clicks reuse the
current successful result. Editing the text or either setting invalidates results.
Clear Text clears the passage, results, and feedback while retaining selected
settings. State is per browser session and is not saved to disk. Errors permit a
manual retry and never produce fabricated vocabulary. Download remains disabled.

## Validation and limitations

The application rejects blank, non-word, and oversized input locally. Meaningful
English validation is a lightweight Latin-letter check, not language detection;
it cannot establish whether arbitrary prose is grammatical English.

The model selects words, but local code removes duplicates and absent word forms,
uses case-insensitive whole-token matching, restores the first occurrence's exact
spelling, sorts by passage order, and applies the maximum. Hyphenated and
apostrophe-containing words are treated as whole tokens; a singular form is not
accepted merely because a plural occurs. Model-provided context is replaced by a
span extracted from the original input. Basic punctuation/newline boundaries may
split abbreviations, so context can be a relevant span rather than a full sentence.

Difficulty is relative to the selected reader level. Selection quality and
educational relevance still depend on the model; deterministic checks guarantee
source grounding, not perfect pedagogical judgment. Prompt isolation reduces
instruction-injection risk but is not a guarantee of model behavior. There are
no tools for the model to execute. Refusals, incomplete responses, and malformed
structured output are errors; a valid empty list displays the no-vocabulary state.

## Tests

```bash
python -m pytest -q
```

Tests cover startup without credentials, input limits, levels, deduplication,
word boundaries and forms, source context, ordering, maximum counts, empty and
malformed output, SDK errors, and UI state. The real SDK structured parser runs
against `httpx.MockTransport`; all real HTTP transport is blocked by an autouse
fixture and local `.env` loading is disabled. Tests never consume API credits.
Vocabulary examples are test fixtures only.

For an optional live smoke test, configure a valid key and model, run the app,
paste a short passage, and click Analyze once. Verify source words/context and
summary metrics. This sends a billable API request and is separate from pytest.
Automated mock tests verify the configured-model request path but cannot verify
your account's credentials, quota, or model access.

## Planned development phases

Only Phases 1 and 2 are delivered here. The remaining breakdown is a proposed roadmap
to refine with each subsequent phase's requirements.

1. **Foundation and initial UI:** modular structure, environment setup, input
   handling, output models, and baseline tests.
2. **AI integration (complete):** provider adapter, structured identification,
   contextual validation, difficulty settings, and results UI.
3. **Agent workflow:** LangGraph orchestration, word selection, definition
   generation, and validation nodes.
4. **Results and export:** interactive vocabulary review and `Definitions.txt` download.
5. **Quality and completion:** failure handling, broader tests, usability polish,
   and final project documentation.

Phase 3 can wrap the existing preparation, identification, and validation functions
as LangGraph nodes, then add definition generation under its explicit requirements.
Phase 2 uses a direct service call and does not build that graph yet.
