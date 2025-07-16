# Auto-README Backend (FastAPI)

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run the server

```bash
uvicorn main:app --reload
```

## API Endpoint
- `POST /generate-readme/` with JSON `{ "repo_url": "<github_repo_url>" }`
- Returns: `{ "readme": "..." }` 