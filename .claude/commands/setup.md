# /setup - Automatic Installation

Run this command to install GM Claude dependencies. This runs automatically on first launch.

## Steps

1. **Check Python version**
   ```bash
   python3 --version
   ```
   Verify Python 3.11+ is installed. If not, inform the user:
   "Python 3.11+ is required. Install from: https://www.python.org/downloads/"

2. **Create virtual environment if missing**
   ```bash
   [ -d ".venv" ] || python3 -m venv .venv
   ```

3. **Install dependencies (including semantic recall and the book search)**

   Try uv first (faster), fall back to pip:
   ```bash
   if command -v uv &> /dev/null; then
       uv sync --extra recall
   else
       source .venv/bin/activate && pip install --upgrade pip && pip install -e '.[recall]'
   fi
   bash tools/gm-recall.sh setup
   ```

   Note: this installs numpy, onnxruntime and tokenizers (about 150 MB) and downloads the model (217 MB, checked) into `models/`. No PyTorch.

4. **Create .env if missing**
   ```bash
   if [ ! -f ".env" ]; then
       cat > .env << 'EOF'
   # GM Claude Configuration
   DEFAULT_CAMPAIGN_NAME="My Campaign"
   DEFAULT_STARTING_LOCATION="Thornwick"
   EOF
   fi
   ```

5. **Set script permissions**
   ```bash
   chmod +x tools/*.sh tools/*.py lib/*.py
   ```

6. **Verify installation**
   ```bash
   uv run python lib/dice.py "1d20"
   ```

   If the dice roll works, installation is complete.

---

## Setup Complete → Hand Off to /gm

Installation is the only job of this command. `/gm` is the single front door for
everything that follows — do NOT re-implement a campaign/import/new-game menu here.
`/gm` already lists saved campaigns and offers **New Adventure** (a world made together, from one sentence, or from a
book: `/new-game` or `/import`).

After install succeeds, display:

```
================================================================
  ✅ GM CLAUDE IS READY
================================================================

  Run /gm to begin.

  • Pick up a saved campaign, or
  • Start a New Adventure: build a world together, from one
    sentence, or from a book.
================================================================
```

Then route into `/gm` (its STEP 0 handles campaign selection, new-vs-import, and
returning players in one place).
