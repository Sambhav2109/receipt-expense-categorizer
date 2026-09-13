# Receipt Expense Categorizer

An MVP receipt ledger with a React/Vite frontend and a FastAPI/SQLite backend. It runs locally with no accounts, paid services, or secrets.

## Run it

### Backend (Python 3.10+)
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows (use source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
python -m app
```
The API is at `http://localhost:8000`; interactive docs are at `/docs`.

### Frontend (Node 18+)
```bash
cd frontend
npm install
npm run dev
```
Open the Vite URL (normally `http://localhost:5173`). Set `VITE_API_URL` if the API is elsewhere.

## Behavior

Upload accepts JPEG, PNG, WEBP, and PDF files up to 10 MB. Receipts are stored in `backend/data/receipts.db`. Text-based PDFs are parsed with `pypdf`; image receipts use optional `pytesseract`/Pillow OCR when installed. Extraction recognizes INR, `Rs`, and rupee-symbol amounts, stores line items when available, uses an explicit total when present, and falls back to the item sum. Categories are assigned using transparent keyword rules and can be changed in the UI.

API endpoints: `GET /api/health`, `POST /api/receipts`, `GET /api/receipts` (category/search/start_date/end_date filters), `GET/PATCH/DELETE /api/receipts/{id}`.

## Tests
```bash
cd backend
pytest
```
