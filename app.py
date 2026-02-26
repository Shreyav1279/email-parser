import re
import json
from datetime import datetime
from typing import List, Dict
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


# ===============================
# Request Model
# ===============================

class EmailRequest(BaseModel):
    email_body: str
    email_received_date: str


# ===============================
# Your Existing Logic
# ===============================

def extract_branch(text: str):
    match = re.search(r'for\s+([A-Za-z\s]+?)\s+branch', text, re.IGNORECASE)
    return match.group(1).strip() if match else None


def extract_rashi_part_no(text: str):
    match = re.search(r'order to\s+([A-Z\-]+)', text, re.IGNORECASE)
    return match.group(1).upper() if match else None


def extract_order_date_from_text(text: str):
    match = re.search(r'\b\d{2}-\d{2}-\d{4}\b', text)
    if match:
        return datetime.strptime(match.group(), "%d-%m-%Y").date().isoformat()
    return None


pattern_format1 = r'(TL-[A-Z0-9\-]+|ER\d+)\s*[–-]\s*(\d+)\s*(nos|nps|ns|pcs)?\.?\s*@\s*([\d,]+)'
pattern_format2 = r'(\d+)\s*(nos|pcs|units)\s*of\s*(TL-[A-Z0-9\-]+|ER\d+)\s*at\s*([\d,]+)'
pattern_format3 = r'(TL-[A-Z0-9\-]+|ER\d+).*?(\d+).*?([\d,]{3,})'
PATTERNS = [pattern_format1, pattern_format2, pattern_format3]


def parse_unstructured_orders(text: str) -> List[Dict]:
    orders = []

    for pattern in PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)

        for match in matches:
            try:
                if pattern == pattern_format1:
                    material, qty, _, price = match
                elif pattern == pattern_format2:
                    qty, _, material, price = match
                else:
                    material, qty, price = match

                qty = int(qty)
                price = int(price.replace(",", ""))

                orders.append({
                    "VendorPartNo": material.strip(),
                    "Quantity": qty,
                    "UnitPrice": price,
                    "TotalAmount": qty * price
                })
            except:
                continue

    unique_orders = [dict(t) for t in {tuple(d.items()) for d in orders}]
    return unique_orders


# ===============================
# API Endpoint
# ===============================

@app.post("/process-email")
def process_email(request: EmailRequest):

    branch = extract_branch(request.email_body)
    rashi_part_no = extract_rashi_part_no(request.email_body)
    order_date = extract_order_date_from_text(request.email_body)

    if not order_date:
        try:
            # Handle ISO datetime from Power Automate
            order_date = datetime.fromisoformat(
                request.email_received_date.replace("Z", "")
            ).date().isoformat()
        except:
            # fallback if anything unexpected
            order_date = request.email_received_date.split("T")[0]

    orders = parse_unstructured_orders(request.email_body)

    final_orders = []

    for order in orders:
        final_orders.append({
            "OrderDate": order_date,
            "Branch": branch,
            "RashiPartNo": rashi_part_no,
            **order
        })

    confidence = 0.95 if final_orders else 0.2

    return {
        "detected_format": "UNSTRUCTURED_FORMAT",
        "orders": final_orders,
        "confidence": confidence
    }
