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

        line = line.strip()

        if not line:
            continue

        match = re.search(pattern_format1, line, re.IGNORECASE)

        if not match:
            match = re.search(pattern_format2, line, re.IGNORECASE)

        if not match:
            match = re.search(pattern_format3, line, re.IGNORECASE)

        if match:
            try:

                if len(match.groups()) == 4:
                    material, qty, _, price = match.groups()

                elif pattern_format2 in match.re.pattern:
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
# NEW → Structured email detection
# ===============================

def is_structured_email(text: str):

    if "Material value" in text:
        return True

    return False


# ===============================
# NEW → Structured parser
# ===============================

def parse_structured_orders(text: str):

    orders = []

    lines = [l.strip() for l in text.splitlines() if l.strip()]

    i = 0

    while i < len(lines):

        try:

            line = lines[i]

            # detect date line
            if re.search(r"\d{2}-\d{2}-\d{4}", line):

                branch = lines[i + 1]
                rashi = lines[i + 2]
                vendor = lines[i + 3]
                qty = lines[i + 4]
                price = lines[i + 5]
                material = lines[i + 6]

                # skip header blocks
                if branch.lower() == "branch":
                    i += 1
                    continue

                # skip if not number
                if not qty.isdigit():
                    i += 1
                    continue

                qty = int(qty)
                price = int(price.replace(",", ""))
                material = int(material.replace(",", ""))

                total = qty * price

                orders.append({
                    "Branch": branch,
                    "RashiPartNo": rashi,
                    "VendorPartNo": vendor,
                    "Quantity": qty,
                    "UnitPrice": price,
                    "TotalAmount": total,
                    "MaterialValue": material
                })

                i += 7
                continue

        except:
            pass

        i += 1

    return orders

# ===============================
# API Endpoint
# ===============================

@app.post("/process-email")
def process_email(request: EmailRequest):

    branch = extract_branch(request.email_body)
    rashi_part_no = extract_rashi_part_no(request.email_body)

    # NEW LOGIC → structured / unstructured

    if is_structured_email(request.email_body):

        orders = parse_structured_orders(request.email_body)
        detected_format = "STRUCTURED_FORMAT"

    else:

        orders = parse_unstructured_orders(request.email_body)
        detected_format = "UNSTRUCTURED_FORMAT"

    final_orders = []

    for order in orders:
        final_orders.append({
            "Branch": branch,
            "RashiPartNo": rashi_part_no,
            **order,
            "MaterialValue": order.get("MaterialValue", "")
        })

    confidence = 0.95 if final_orders else 0.2

    return {
        "detected_format": detected_format,
        "orders": final_orders,
        "confidence": confidence
    }
