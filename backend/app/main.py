from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

DATA_DIR = Path(os.getenv("RECEIPT_DATA_DIR", Path(__file__).resolve().parents[1] / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "receipts.db"
MAX_UPLOAD = 10 * 1024 * 1024
ALLOWED = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
CATEGORIES = (
    "Groceries", "Food", "Transport", "Travel", "Shopping", "Personal Care",
    "Office", "Utilities", "Healthcare", "Other",
)


@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS receipts (
            id TEXT PRIMARY KEY, filename TEXT NOT NULL, content_type TEXT NOT NULL,
            merchant TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL,
            receipt_date TEXT NOT NULL, category TEXT NOT NULL, notes TEXT,
            extracted_text TEXT, items TEXT NOT NULL DEFAULT '[]', created_at TEXT NOT NULL)""")
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(receipts)")}
        if "items" not in columns:
            conn.execute("ALTER TABLE receipts ADD COLUMN items TEXT NOT NULL DEFAULT '[]'")
        conn.execute("UPDATE receipts SET currency = 'INR' WHERE currency IS NULL OR currency = 'USD'")


init_db()
app = FastAPI(title="Receipt Expense Categorizer API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ReceiptUpdate(BaseModel):
    category: Optional[str] = None
    notes: Optional[str] = Field(default=None, max_length=500)


def classify(merchant: str, text: str) -> str:
    value = f"{merchant} {text}".lower()
    rules = {
        "Groceries": ("grocery", "groceries", "supermarket", "vegetable", "fruit", "milk"),
        "Food": ("restaurant", "cafe", "coffee", "food", "pizza", "bakery", "meal"),
        "Transport": ("uber", "lyft", "airline", "hotel", "taxi", "fuel", "petrol", "metro", "bus"),
        "Travel": ("travel",),
        "Personal Care": ("salon", "beauty", "cosmetic", "personal care"),
        "Office": ("office", "staples", "paper", "supplies"),
        "Utilities": ("electric", "water bill", "internet", "phone", "utility"),
        "Healthcare": ("pharmacy", "hospital", "clinic", "medical", "doctor"),
        "Shopping": ("amazon", "walmart", "store", "retail", "shopping"),
    }
    for category, words in rules.items():
        if any(word in value for word in words):
            return category
    return "Other"


AMOUNT_TOKEN = r"(?:₹|rs\.?|inr)?\s*\d[\d,]*(?:\.\d{1,2})?"


def parse_amount(value: str) -> float:
    matches = re.findall(r"\d[\d,]*(?:\.\d{1,2})?", value)
    if not matches:
        raise ValueError(f"Could not parse amount from {value!r}")
    return round(float(matches[-1].replace(",", "")), 2)


def item_category(name: str, explicit_category: str = "") -> str:
    if explicit_category in CATEGORIES and explicit_category != "Other":
        return explicit_category
    return classify(name, name)


def extract_items(text: str) -> list[dict]:
    items = []
    lines = [" ".join(line.split()).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    ignored = re.compile(r"(?i)\b(?:item|category|amount|subtotal|tax|gst|total|amount due|change|cash|card)\b")
    amount_line = re.compile(r"^[^\d]*\d[\d,]*(?:\.\d{1,2})?\s*$", re.I)

    index = 0
    while index < len(lines):
        line = lines[index]
        if ignored.search(line):
            index += 1
            continue

        same_line = re.search(rf"^(?P<name>.+?)\s+(?P<amount>{AMOUNT_TOKEN})$", line, re.I)
        if same_line:
            name = same_line.group("name").strip(" .:-")
            if name:
                items.append({
                    "name": name[:120],
                    "amount": parse_amount(same_line.group("amount")),
                    "category": item_category(name),
                })
            index += 1
            continue

        if (
            index + 2 < len(lines)
            and amount_line.fullmatch(lines[index + 2])
            and lines[index + 1] in CATEGORIES
        ):
            name = line.strip(" .:-")
            explicit_category = lines[index + 1]
            if name and not ignored.search(name):
                items.append({
                    "name": name[:120],
                    "amount": parse_amount(lines[index + 2]),
                    "category": item_category(name, explicit_category),
                })
                index += 3
                continue
        index += 1
    return items


def backfill_items() -> None:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, extracted_text FROM receipts WHERE (items IS NULL OR items = '[]') AND extracted_text IS NOT NULL AND extracted_text != ''"
        ).fetchall()
        for row in rows:
            items = extract_items(row["extracted_text"])
            if items:
                conn.execute("UPDATE receipts SET items = ? WHERE id = ?", (json.dumps(items), row["id"]))


def extract(content: bytes, content_type: str, filename: str) -> dict:
    """Extract receipt text locally using pypdf or Tesseract/Pillow when installed."""
    text = ""
    if content_type == "application/pdf":
        try:
            import pypdf  # type: ignore
            reader = pypdf.PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            text = ""
    elif content_type.startswith("image/"):
        try:
            import pytesseract  # type: ignore
            from PIL import Image  # type: ignore
            text = pytesseract.image_to_string(Image.open(io.BytesIO(content)))
        except Exception:
            text = ""
    amount_match = re.search(rf"(?i)\b(?:grand\s+)?total\b[^\d₹]*(?P<amount>{AMOUNT_TOKEN})", text)
    items = extract_items(text)
    amounts = re.findall(AMOUNT_TOKEN, text, re.I)
    amount = parse_amount(amount_match.group("amount")) if amount_match else (
        round(sum(item["amount"] for item in items), 2) if items else (
            parse_amount(amounts[-1]) if amounts else 0
        )
    )
    merchant = next((line.strip() for line in text.splitlines() if line.strip()), Path(filename).stem.replace("_", " ").title())
    date_match = re.search(r"\b(20\d{2}[-/]\d{1,2}[-/]\d{1,2})\b", text)
    receipt_date = date_match.group(1).replace("/", "-") if date_match else date.today().isoformat()
    return {"merchant": merchant[:120], "amount": amount, "currency": "INR",
            "receipt_date": receipt_date, "category": classify(merchant, text),
            "items": items, "extracted_text": text[:5000]}


backfill_items()


def serialize(row: sqlite3.Row) -> dict:
    result = dict(row)
    result["amount"] = round(result["amount"], 2)
    result["items"] = json.loads(result.get("items") or "[]")
    return result


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/receipts", status_code=201)
async def upload_receipt(file: UploadFile = File(...)) -> dict:
    if file.content_type not in ALLOWED:
        raise HTTPException(415, "Only JPEG, PNG, WEBP images and PDF files are supported")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty")
    if len(content) > MAX_UPLOAD:
        raise HTTPException(413, "File exceeds the 10 MB limit")
    fields = extract(content, file.content_type, file.filename or "receipt")
    item = {"id": str(uuid.uuid4()), "filename": file.filename or "receipt", "content_type": file.content_type,
            **fields, "notes": "", "created_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")}
    with db() as conn:
        item["items"] = json.dumps(item["items"])
        conn.execute("""INSERT INTO receipts
            (id, filename, content_type, merchant, amount, currency, receipt_date,
             category, notes, extracted_text, items, created_at)
            VALUES (:id,:filename,:content_type,:merchant,:amount,:currency,:receipt_date,
                    :category,:notes,:extracted_text,:items,:created_at)""", item)
    item["items"] = json.loads(item["items"])
    return item


@app.get("/api/receipts")
def list_receipts(category: Optional[str] = Query(None), search: Optional[str] = Query(None),
                  start_date: Optional[str] = Query(None), end_date: Optional[str] = Query(None)) -> dict:
    query, params = "SELECT * FROM receipts WHERE 1=1", []
    if category and category in CATEGORIES:
        query += " AND category = ?"; params.append(category)
    if search:
        query += " AND (merchant LIKE ? OR filename LIKE ?)"; params += [f"%{search}%", f"%{search}%"]
    if start_date:
        query += " AND receipt_date >= ?"; params.append(start_date)
    if end_date:
        query += " AND receipt_date <= ?"; params.append(end_date)
    query += " ORDER BY receipt_date DESC, created_at DESC"
    with db() as conn:
        items = [serialize(row) for row in conn.execute(query, params)]
    return {"items": items, "total": round(sum(item["amount"] for item in items), 2), "count": len(items)}


@app.get("/api/receipts/{receipt_id}")
def get_receipt(receipt_id: str) -> dict:
    with db() as conn:
        row = conn.execute("SELECT * FROM receipts WHERE id = ?", (receipt_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Receipt not found")
    return serialize(row)


@app.patch("/api/receipts/{receipt_id}")
def update_receipt(receipt_id: str, update: ReceiptUpdate) -> dict:
    changes = update.model_dump(exclude_unset=True)
    if "category" in changes and changes["category"] not in CATEGORIES:
        raise HTTPException(422, "Invalid category")
    if not changes:
        return get_receipt(receipt_id)
    assignments = ", ".join(f"{key} = ?" for key in changes)
    with db() as conn:
        result = conn.execute(f"UPDATE receipts SET {assignments} WHERE id = ?", [*changes.values(), receipt_id])
    if result.rowcount == 0:
        raise HTTPException(404, "Receipt not found")
    return get_receipt(receipt_id)


@app.delete("/api/receipts/{receipt_id}", status_code=204)
def delete_receipt(receipt_id: str) -> Response:
    with db() as conn:
        result = conn.execute("DELETE FROM receipts WHERE id = ?", (receipt_id,))
    if result.rowcount == 0:
        raise HTTPException(404, "Receipt not found")
    return Response(status_code=204)
