# Discordify tests

Unit tests for the Discordify Synapse module.

## Running tests

From the repo root, create a virtual environment and install dependencies:

```bash
cd discordify
python3 -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -e ".[test]"
pip install -r requirements-test.txt
pytest
```

Or with system Python if synapse and pytest are available:

```bash
cd discordify
pip install -e .  # installs matrix-synapse
pip install pytest pytest-asyncio
pytest
```

## Tests

- **test_parse_config.py**: Config parsing (valid/invalid channels, roles, defaults).
- **test_check_event_allowed.py**: Timeout logic (allow when no timeout or expired, reject when timed out; space parent resolution).
