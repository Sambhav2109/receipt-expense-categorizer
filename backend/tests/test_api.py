import io
import json
import sqlite3
import pytest
from fastapi.testclient import TestClient

from app.main import app, DB_PATH

client = TestClient(app)


def sample_pdf() -> bytes:
    stream = b"BT /F1 12 Tf 72 720 Td (Fresh Mart Grocery) Tj 0 -20 Td (Rice 120.00) Tj 0 -20 Td (Milk 85.50) Tj 0 -20 Td (Total: INR 205.50) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    pdf.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


def sample_indian_receipt_pdf() -> bytes:
    lines = [
        "GREEN MART", "123 Park Street, Kolkata, West Bengal",
        "GSTIN: 19ABCDE1234F1Z5", "Receipt No: GM-2026-0913-1042",
        "Date: 13/09/2026", "Item", "Category", "Amount",
        "Milk 1L", "Groceries", "₹60.00", "Bread", "Groceries", "₹40.00",
        "Shampoo", "Personal Care", "₹250.00", "Bus Pass", "Transport", "₹120.00",
        "Coffee", "Food", "₹90.00", "Notebook", "Office", "₹75.00",
        "Total", "₹635.00",
    ]
    commands = [b"BT /F1 12 Tf 72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append(b"0 -20 Td")
        commands.append(f"({line}) Tj".encode())
    stream = b" ".join(commands) + b" ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    pdf.extend(b"".join(f"{offset:010d} 00000 n \n".encode() for offset in offsets[1:]))
    pdf.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return bytes(pdf)


@pytest.fixture(autouse=True)
def clean_db():
    DB_PATH.unlink(missing_ok=True)
    from app.main import init_db
    init_db()


def test_upload_list_and_filter():
    response = client.post("/api/receipts", files={"file": ("cafe.txt", io.BytesIO(b"receipt"), "text/plain")})
    assert response.status_code == 415
    response = client.post("/api/receipts", files={"file": ("cafe.png", io.BytesIO(b"not-an-image"), "image/png")})
    assert response.status_code == 201
    assert response.json()["category"] == "Food"
    listed = client.get("/api/receipts", params={"category": "Food"})
    assert listed.json()["count"] == 1
    assert client.get("/api/receipts").json()["count"] == 1


def test_text_pdf_extracts_total_items_and_category():
    response = client.post("/api/receipts", files={"file": ("fresh-mart.pdf", sample_pdf(), "application/pdf")})
    assert response.status_code == 201
    receipt = response.json()
    assert receipt["merchant"] == "Fresh Mart Grocery"
    assert receipt["amount"] == 205.50
    assert receipt["currency"] == "INR"
    assert receipt["category"] == "Groceries"
    assert receipt["items"] == [
        {"name": "Rice", "amount": 120.0, "category": "Other"},
        {"name": "Milk", "amount": 85.5, "category": "Groceries"},
    ]


def test_sample_indian_pdf_extracts_all_six_line_items():
    response = client.post(
        "/api/receipts",
        files={"file": ("sample_indian_receipt.pdf", sample_indian_receipt_pdf(), "application/pdf")},
    )
    assert response.status_code == 201
    receipt = response.json()
    assert receipt["merchant"] == "GREEN MART"
    assert receipt["amount"] == 635.0
    assert [(item["name"], item["amount"]) for item in receipt["items"]] == [
        ("Milk 1L", 60.0),
        ("Bread", 40.0),
        ("Shampoo", 250.0),
        ("Bus Pass", 120.0),
        ("Coffee", 90.0),
        ("Notebook", 75.0),
    ]
    assert sum(item["amount"] for item in receipt["items"]) == 635.0
    connection = sqlite3.connect(DB_PATH)
    try:
        stored = connection.execute(
            "SELECT items FROM receipts WHERE id = ?", (receipt["id"],)
        ).fetchone()[0]
    finally:
        connection.close()
    assert json.loads(stored) == receipt["items"]
    details = client.get(f"/api/receipts/{receipt['id']}")
    assert details.status_code == 200
    assert details.json()["items"] == receipt["items"]


def test_update_and_missing():
    created = client.post("/api/receipts", files={"file": ("x.pdf", io.BytesIO(b"x"), "application/pdf")}).json()
    updated = client.patch(f"/api/receipts/{created['id']}", json={"category": "Office", "notes": "review"})
    assert updated.status_code == 200 and updated.json()["category"] == "Office"
    assert client.patch(f"/api/receipts/{created['id']}", json={"category": "Nope"}).status_code == 422
    assert client.get("/api/receipts/missing").status_code == 404
