# AI Text Humanizer

Standalone desktop tool that rewrites English text through three stages — DeepSeek paraphrase,
a translation round-trip, and an AI-pattern strip pass — then checks the output for lost factual
claims. Windows-first, packaged as a single `.exe`. No local ML models.

This tool rewrites text. It does not guarantee a particular detector score, and submitting
rewritten work as your own without attribution may breach your institution's academic policy.
Target detector: GPTZero Model 4.1o (English in, English out).

## Requirements

- Python 3.11+
- A DeepSeek API key (entered in the GUI; stored only on your machine)
- Internet access (DeepSeek + Google Translate via `deep-translator`)

## Setup

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Run

```bat
streamlit run app.py
```

Or use the backend directly, without the UI:

```python
from humanizer.pipeline import humanize_text

result = humanize_text(
    text="...at least 50 words of English...",
    api_key="sk-...",
    chain=["zh-CN", "ja", "ar", "ru"],
    temperature=1.3,
    run_verification=True,
)
print(result.final_text)
print(result.claim_loss)
```

Pipeline progress can be observed with a callback:

```python
def progress(stage_name, chunk_index, total_chunks):
    print(stage_name, chunk_index, total_chunks)

humanize_text(text, api_key, progress_cb=progress)
```

## API key storage

- The key is loaded from and saved to `%APPDATA%\AITextHumanizer\config.json` on Windows
  (`~/.config/AITextHumanizer/config.json` elsewhere), with `0600` permissions where supported.
- It is sent only to `https://api.deepseek.com/v1`. It is never logged and never included in
  returned results.

## Pipeline

For each chunk, in order:

1. **Paraphrase** — restructures sentences while preserving claims (`temperature` from the UI).
2. **Round-trip translation** — each selected language in order, then back to English.
3. **Strip patterns** — removes the AI-writing patterns defined in `humanizer/prompts.py`.
4. **Verify** (optional) — compares input and output and lists any claims that may be missing.

Chunks are split on blank-line paragraph boundaries (never mid-sentence); a paragraph longer
than 1,200 words is split on sentence boundaries. Chunks are reassembled with `\n\n`.

Failure behavior:

- A failed translation hop is skipped and reported as a warning; if every hop fails, that
  chunk falls back to its paraphrase output.
- A failed paraphrase falls back to the original chunk; a failed strip falls back to the
  translated text.
- A chunk failure never aborts the run. All warnings appear in the UI and in
  `HumanizeResult.warnings`.

Model IDs live in `humanizer/config.py`. If a configured model ID returns a 404/model-not-found,
the client retries with `DEEPSEEK_FALLBACK_MODEL` and logs a warning. The default
`DEEPSEEK_MODEL` is `deepseek-chat`, which is also the fallback.

## Tests

All tests are offline; DeepSeek and translation calls are mocked.

```bat
python -m unittest discover -s tests -v
```

Covers: paragraph/sentence-safe chunking and word order, coherence rejection, hop-skipping and
all-hop failure, one stage per step per chunk, paraphrase fallback, input validation, and API-key
non-leakage.

## Build (Windows)

```bat
build.bat
```

Output: `dist\AI Text Humanizer.exe` (one-file, ~83 MB; verified with
`streamlit-desktop-app 0.3.4` and PyInstaller 6.22.3). The one-file build works; a one-folder
build was not needed.

Build notes:

- The CLI flags were checked with `streamlit-desktop-app build --help`: `--name` and
  `--pyinstaller-options` are correct for 0.3.4.
- `build.bat` sets `PYTHONPATH` and passes `--collect-submodules humanizer`. Without these, the
  bundled EXE starts but cannot import the local `humanizer` package (PyInstaller's
  `collect_submodules` does not see the project root), and the build log shows
  `ERROR: Hidden import 'humanizer.config...' not found`. Those ERROR lines are produced by
  `streamlit-desktop-app`'s AST scanner treating imported attribute names as modules; they are
  harmless once the package is collected. The bundle was verified to contain `humanizer.*`,
  `openai.*`, and `deep_translator.*`.

## Manual acceptance

Not yet run (requires a DeepSeek key and GPTZero access). Checklist:

1. Build the EXE and run it on a machine without Python.
2. Paste a ~600-word policy essay paragraph. Confirm all four hops execute and the output is English.
3. Paste a 3,000-word essay. Confirm chunking runs, progress is visible, and the app does not hang.
4. Submit input and output to GPTZero separately and record both scores below.
5. Repeat with 10–15 paragraphs before changing any prompt — establish a baseline first.

## Results

| Input | Words / paragraphs | GPTZero score (input) | GPTZero score (output) | Notes |
|---|---|---|---|---|
| — | — | — | — | Baseline pending |

## Scope and do-nots

- No typos, deliberate grammar errors, filler insertion, synonym-swap loops, or extra
  "make it sound human" prompt layer.
- Citations, case names, statute numbers, and quotations must not be paraphrased or reordered.
- DeepSeek calls run sequentially, never concurrently.
- The key is stored only in the local config file.

## Layout

```
ai-humanizer/
├── app.py                  # Streamlit UI (calls humanize_text only)
├── humanizer/
│   ├── config.py           # constants, paths, config persistence
│   ├── prompts.py          # prompt strings
│   ├── llm.py              # DeepSeek calls
│   ├── translate.py        # round-trip chain
│   ├── chunking.py         # paragraph-safe splitting
│   └── pipeline.py         # humanize_text orchestrator
├── tests/test_pipeline.py
├── requirements.txt
├── build.bat
└── README.md
```
