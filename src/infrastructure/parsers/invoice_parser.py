import os
import tempfile
import PyPDF2
import re
from typing import Dict, Any
from src.domain.interfaces import InvoiceParser


class InvoiceParser(InvoiceParser):
    def parse(self, file_path: str) -> Dict[str, Any]:
        try:
            print(f"🔍 REAL PARSER: Parsing actual file: {file_path}")

            with open(file_path, "rb") as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for page in pdf_reader.pages:
                    text += page.extract_text()

            print(f"📄 Extracted {len(text)} characters from PDF")

            self._debug_text_extraction(text, os.path.basename(file_path))

            parsed_data = self._parse_invoice_text(text, file_path)

            print(f"💰 PARSER EXTRACTED:")
            print(f"   subtotal: {parsed_data.get('subtotal')}")
            print(f"   shipping_amount: {parsed_data.get('shipping_amount')}")
            print(f"   tax_amount: {parsed_data.get('tax_amount')}")
            print(f"   total_amount: {parsed_data.get('total_amount')}")

            class ParsedInvoice:
                def __init__(self, data):
                    self.data = data

                def to_dict(self):
                    return self.data

            return ParsedInvoice(parsed_data)

        except Exception as e:
            print(f"❌ PARSER ERROR: {str(e)}")
            import traceback

            print(traceback.format_exc())
            return self._get_fallback_data()

    def _debug_text_extraction(self, text: str, filename: str):
        print(f"\n🔍 DEBUG TEXT EXTRACTION FOR: {filename}")
        print("=" * 50)
        lines = text.split("\n")
        for i, line in enumerate(lines):
            if any(
                keyword in line.lower()
                for keyword in [
                    "total",
                    "subtotal",
                    "shipping",
                    "tax",
                    "amount",
                    "$",
                    "balance",
                    "discount",
                ]
            ):
                print(f"Line {i}: {line}")
        print("=" * 50)

    def _parse_invoice_text(self, text: str, file_path: str) -> Dict[str, Any]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        # Extract all financial data using the new improved method
        financial_data = self._extract_all_financial_data(lines)

        invoice_data = {
            "vendor": "SuperStore",
            "invoice_number": self._extract_invoice_number(lines, file_path),
            "invoice_date": self._extract_date(lines),
            "subtotal": financial_data.get("subtotal", 0.0),
            "shipping_amount": financial_data.get("shipping", 0.0),
            "tax_amount": financial_data.get("tax", 0.0),
            "total_amount": financial_data.get("total", 0.0),
            "currency": "USD",
            "line_items": self._extract_superstore_line_items(lines),
        }

        return invoice_data

    def _extract_invoice_number(self, lines: list, file_path: str) -> str:
        # First try to get from filename
        try:
            filename = os.path.basename(file_path)
            parts = filename.replace(".pdf", "").split("_")
            if len(parts) >= 3 and parts[-1].isdigit():
                invoice_num = parts[-1]
                print(f"📝 Found invoice number from filename: {invoice_num}")
                return invoice_num
        except:
            pass

        # Look for invoice number in content - pattern like "# 36258"
        for line in lines:
            match = re.search(r"#\s*(\d+)", line)
            if match:
                invoice_num = match.group(1)
                print(f"📝 Found invoice number in content: {invoice_num}")
                return invoice_num

        return "UNKNOWN"

    def _extract_date(self, lines: list) -> str:
        # Look for "Date: Mar 06 2012" pattern
        for line in lines:
            match = re.search(
                r"Date:\s*([A-Za-z]+\s+\d{1,2}\s+\d{4})", line, re.IGNORECASE
            )
            if match:
                date = match.group(1)
                print(f"📅 Found date: {date}")
                return date

        # Fallback to general date patterns
        for line in lines:
            date_patterns = [
                r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},?\s+\d{4}\b",
                r"\b\d{1,2}/\d{1,2}/\d{4}\b",
            ]
            for pattern in date_patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    date = match.group(0)
                    print(f"📅 Found date (fallback): {date}")
                    return date
        return ""

    def _extract_all_financial_data(self, lines: list) -> Dict[str, float]:
        """Extract all financial data from the structured invoice format"""
        financials = {"subtotal": 0.0, "shipping": 0.0, "tax": 0.0, "total": 0.0}

        # Look for the financial section structure
        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Look for "Balance Due" pattern - this is usually the final total
            if "balance due" in line_lower:
                # Check previous line for amount (based on your debug output)
                if i > 0:
                    amount = self._extract_currency_value(lines[i - 1])
                    if amount > 0:
                        financials["total"] = amount
                        print(f"💵 Found total (Balance Due prev line): {amount}")
                        continue

                # Check same line
                amount = self._extract_currency_value(line)
                if amount > 0:
                    financials["total"] = amount
                    print(f"💵 Found total (Balance Due same line): {amount}")
                    continue

                # Check next line
                if i + 1 < len(lines):
                    amount = self._extract_currency_value(lines[i + 1])
                    if amount > 0:
                        financials["total"] = amount
                        print(f"💵 Found total (Balance Due next line): {amount}")
                        continue

            # Look for "Subtotal" pattern
            elif line_lower.strip() == "subtotal" and i > 0:
                amount = self._extract_currency_value(lines[i - 1])
                if amount > 0:
                    financials["subtotal"] = amount
                    print(f"📊 Found subtotal (prev line): {amount}")
                    continue

            # Look for "Shipping" pattern - FIXED: Check multiple lines
            elif line_lower.strip() == "shipping":
                # Check previous line first
                if i > 0:
                    amount = self._extract_currency_value(lines[i - 1])
                    if amount > 0:
                        financials["shipping"] = amount
                        print(f"📮 Found shipping (prev line): {amount}")
                        continue

                # Check same line
                amount = self._extract_currency_value(line)
                if amount > 0:
                    financials["shipping"] = amount
                    print(f"📮 Found shipping (same line): {amount}")
                    continue

                # Check next line
                if i + 1 < len(lines):
                    amount = self._extract_currency_value(lines[i + 1])
                    if amount > 0:
                        financials["shipping"] = amount
                        print(f"📮 Found shipping (next line): {amount}")
                        continue

            # Look for "Tax" pattern - FIXED: Check multiple lines
            elif line_lower.strip() == "tax":
                # Check previous line first
                if i > 0:
                    amount = self._extract_currency_value(lines[i - 1])
                    if amount > 0:
                        financials["tax"] = amount
                        print(f"💰 Found tax (prev line): {amount}")
                        continue

                # Check same line
                amount = self._extract_currency_value(line)
                if amount > 0:
                    financials["tax"] = amount
                    print(f"💰 Found tax (same line): {amount}")
                    continue

                # Check next line
                if i + 1 < len(lines):
                    amount = self._extract_currency_value(lines[i + 1])
                    if amount > 0:
                        financials["tax"] = amount
                        print(f"💰 Found tax (next line): {amount}")
                        continue

        # FIXED: Smart calculation for missing shipping and tax
        if financials["total"] > 0 and financials["subtotal"] > 0:
            # Calculate the difference between total and subtotal
            difference = financials["total"] - financials["subtotal"]

            # If we have shipping but not tax
            if financials["shipping"] > 0 and financials["tax"] == 0:
                calculated_tax = difference - financials["shipping"]
                if calculated_tax >= 0:
                    financials["tax"] = calculated_tax
                    print(f"🧮 Calculated tax from difference: {calculated_tax}")

            # If we have tax but not shipping
            elif financials["tax"] > 0 and financials["shipping"] == 0:
                calculated_shipping = difference - financials["tax"]
                if calculated_shipping >= 0:
                    financials["shipping"] = calculated_shipping
                    print(
                        f"🧮 Calculated shipping from difference: {calculated_shipping}"
                    )

            # If we have neither shipping nor tax, but there's a difference
            elif (
                financials["shipping"] == 0
                and financials["tax"] == 0
                and difference > 0
            ):
                # Look for shipping and tax amounts in nearby lines based on debug patterns
                shipping_candidates = []
                tax_candidates = []

                # Search for amounts that could be shipping/tax
                for j, search_line in enumerate(
                    lines[max(0, i - 10) : min(len(lines), i + 10)]
                ):
                    amount = self._extract_currency_value(search_line)
                    if 0 < amount < financials["subtotal"]:  # Reasonable amounts
                        if "ship" in search_line.lower():
                            shipping_candidates.append(amount)
                        elif "tax" in search_line.lower():
                            tax_candidates.append(amount)

                # Use found amounts or estimate
                if shipping_candidates:
                    financials["shipping"] = max(shipping_candidates)
                    print(f"📮 Found shipping candidate: {financials['shipping']}")
                if tax_candidates:
                    financials["tax"] = max(tax_candidates)
                    print(f"💰 Found tax candidate: {financials['tax']}")

        return financials

    def _extract_superstore_line_items(self, lines: list) -> list:
        items = []

        # Look for line item amounts in the structure
        amount_lines = []

        for i, line in enumerate(lines):
            amount = self._extract_currency_value(line)
            if amount > 0:
                # Skip amounts that are likely financial totals
                if amount < 1000:  # Filter out totals
                    amount_lines.append((i, line, amount))

        # Sort by line number to maintain order
        amount_lines.sort(key=lambda x: x[0])

        # Take the first few amounts as line items
        for i, (line_num, line_text, amount) in enumerate(amount_lines[:3]):
            # Look backwards for description
            description = ""
            for j in range(line_num - 1, max(0, line_num - 5), -1):
                desc_line = lines[j]
                if (
                    len(desc_line) > 10
                    and not self._extract_currency_value(desc_line)
                    and not any(
                        keyword in desc_line.lower()
                        for keyword in [
                            "subtotal",
                            "shipping",
                            "tax",
                            "total",
                            "balance",
                            "amount",
                            "discount",
                        ]
                    )
                ):
                    description = desc_line
                    break

            if not description:
                description = f"Product {i+1}"

            items.append(
                {
                    "description": description,
                    "quantity": 1.0,
                    "unit_price": amount,
                    "amount": amount,
                }
            )
            print(f"📦 Found line item: {description[:40]}... Amount: {amount}")

        if not items:
            print("⚠️  No line items found, using fallback")
            items = [
                {
                    "description": "Product/Service",
                    "quantity": 1.0,
                    "unit_price": 0.0,
                    "amount": 0.0,
                }
            ]

        return items

    def _extract_currency_value(self, text: str) -> float:
        """Extract currency value from text - improved to handle various formats"""
        # Look for patterns like $50.10, $11.13, $9.74, etc.
        patterns = [
            r"\$?\s*(\d{1,3}(?:,\d{3})*\.\d{2})",  # $1,234.56
            r"\$?\s*(\d+\.\d{2})",  # $123.45
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                try:
                    # Return the first amount found
                    amount = float(matches[0].replace(",", ""))
                    return amount
                except (ValueError, IndexError):
                    continue

        return 0.0

    def _get_fallback_data(self):
        fallback_data = {
            "vendor": "SuperStore",
            "invoice_number": "ERROR-PARSING",
            "invoice_date": "",
            "subtotal": 0.0,
            "shipping_amount": 0.0,
            "tax_amount": 0.0,
            "total_amount": 0.0,
            "currency": "USD",
            "line_items": [],
        }

        class FallbackInvoice:
            def to_dict(self):
                return fallback_data

        return FallbackInvoice()


class SimpleInvoiceParser(InvoiceParser):
    def parse(self, file_path: str) -> Dict[str, Any]:
        print(f"🔍 SIMPLE PARSER: Processing {file_path}")

        data = {
            "vendor": "Vendor Corp",
            "invoice_number": "INV-SIMPLE-001",
            "invoice_date": "2024-01-01",
            "subtotal": 900.00,
            "shipping_amount": 50.00,
            "tax_amount": 50.00,
            "total_amount": 1000.00,
            "currency": "USD",
            "line_items": [
                {
                    "description": "Service Fee",
                    "quantity": 1,
                    "unit_price": 1000.00,
                    "amount": 1000.00,
                }
            ],
        }

        class SimpleInvoice:
            def to_dict(self):
                return data

        return SimpleInvoice()
