# Contributing

## Local setup

1. Install Python dependencies into the shared vendor directory:

```bash
python3 -m pip install --target /Users/jongcye/Documents/Codex/.vendor -r requirements.txt
```

2. Install frontend dependencies:

```bash
PATH=/Users/jongcye/Documents/Codex/.local/node-v22.14.0-darwin-arm64/bin:$PATH npm install
```

3. Create local environment variables:

```bash
cp .env.example .env
```

## Run

Backend:

```bash
PYTHONPATH=/Users/jongcye/Documents/Codex/.vendor python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Frontend:

```bash
PATH=/Users/jongcye/Documents/Codex/.local/node-v22.14.0-darwin-arm64/bin:$PATH npm run dev:webapp
```

## Before opening a PR

Run the frontend typecheck:

```bash
PATH=/Users/jongcye/Documents/Codex/.local/node-v22.14.0-darwin-arm64/bin:$PATH ./webapp/node_modules/.bin/tsc --noEmit -p webapp/tsconfig.json
```

Run a lightweight Python syntax check:

```bash
PYTHONPATH=/Users/jongcye/Documents/Codex/.vendor PYTHONPYCACHEPREFIX=/tmp python3 -m py_compile app/main.py app/models.py app/services/*.py
```

## Project notes

- The UI is a 3-column `Sources / Chat / Studio` workspace.
- Studio-derived summaries are forwarded into Chat through `studio_context`.
- ROH is computed with `bcftools roh` through `pysam` bindings when available.
- Keep secrets out of the repository. Use `.env` only for local development.
