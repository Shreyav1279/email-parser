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


pattern_format1 = r'(TL-[A-Z0-9\-]+|ER\d+)\s*[–-]\s*(\d+)\s*(nos|nps|ns|pcs)?\.?\s*@\s*([\d,]+)'
pattern_format2 = r'(\d+)\s*(nos|pcs|units)\s*of\s*(TL-[A-Z0-9\-]+|ER\d+)\s*at\s*([\d,]+)'
pattern_format3 = r'(TL-[A-Z0-9\-]+|ER\d+).*?(\d+).*?([\d,]{3,})'
PATTERNS = [pattern_format1, pattern_format2, pattern_format3]


def parse_unstructured_orders(text: str) -> List[Dict]:

    orders = []

    lines = text.splitlines()

    for line in lines:

        match = None
        used_pattern = None

        for pattern in PATTERNS:

            match = re.search(pattern, line, re.IGNORECASE)

            if match:
                used_pattern = pattern
                break

        if match:
            try:

                if used_pattern == pattern_format1:
                    material, qty, _, price = match.groups()

                elif used_pattern == pattern_format2:
                    qty, _, material, price = match.groups()

                else:
                    material, qty, price = match.groups()

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

    return orders


# ===============================
# API Endpoint
# ===============================

@app.post("/process-email")
def process_email(request: EmailRequest):

    branch = extract_branch(request.email_body)
    rashi_part_no = extract_rashi_part_no(request.email_body)

    orders = parse_unstructured_orders(request.email_body)

    final_orders = []

    for order in orders:
        final_orders.append({
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
