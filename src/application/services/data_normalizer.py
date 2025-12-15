import re
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class InvoiceDataNormalizer:

    def __init__(self):
        self.canonical_schema = [
            "file_name",
            "vendor",
            "invoice_number",
            "invoice_date",
            "subtotal",
            "shipping_amount",
            "tax_amount",
            "total_amount",
            "currency",
            "line_item_description",
            "line_item_quantity",
            "line_item_unit_price",
            "line_item_amount",
            "parsed_timestamp",
        ]

    def normalize(
        self, raw_parsed_data: Dict[str, Any], filename: str
    ) -> Dict[str, Any]:
        logger.info(f"🔧 Normalizing and fixing data mapping for: {filename}")
        logger.info(
            f"📥 Raw parsed data: {self._sanitize_for_logging(raw_parsed_data)}"
        )

        normalized = {field: None for field in self.canonical_schema}

        normalized["file_name"] = filename

        normalized["parsed_timestamp"] = (
            raw_parsed_data.get("parsed_timestamp") or datetime.now().isoformat()
        )

        normalized["vendor"] = self._extract_vendor(raw_parsed_data, filename)

        normalized["invoice_number"] = self._extract_invoice_number(raw_parsed_data)

        normalized["invoice_date"] = self._extract_invoice_date(raw_parsed_data)

        normalized["subtotal"] = self._safe_float(raw_parsed_data.get("subtotal", 0.0))

        normalized["shipping_amount"] = self._safe_float(
            raw_parsed_data.get("shipping_amount", 0.0)
        )

        normalized["tax_amount"] = self._safe_float(
            raw_parsed_data.get("tax_amount", 0.0)
        )

        normalized["total_amount"] = self._safe_float(
            raw_parsed_data.get("total_amount", 0.0)
        )

        normalized["currency"] = self._extract_currency(raw_parsed_data)

        line_items_data = self._extract_line_items(raw_parsed_data)
        normalized.update(line_items_data)

        normalized = self._validate_and_clean(normalized)

        logger.info(f"💰 NORMALIZER EXTRACTED:")
        logger.info(f"   subtotal: {normalized['subtotal']}")
        logger.info(f"   shipping_amount: {normalized['shipping_amount']}")
        logger.info(f"   tax_amount: {normalized['tax_amount']}")
        logger.info(f"   total_amount: {normalized['total_amount']}")

        logger.info(
            f"📤 Normalized and mapped data: {self._sanitize_for_logging(normalized)}"
        )
        return normalized

    def _extract_vendor(self, data: Dict[str, Any], filename: str) -> str:
        vendor = data.get("vendor", "").strip()

        if not vendor or self._looks_like_filename(vendor):
            return "SuperStore"

        vendor = re.sub(r"[^\w\s&]", "", vendor).strip()
        return vendor if vendor else "SuperStore"

    def _extract_invoice_number(self, data: Dict[str, Any]) -> str:
        invoice_number = data.get("invoice_number", "").strip()
        invoice_date = data.get("invoice_date", "").strip()

        if self._looks_like_date(invoice_number) and not self._looks_like_date(
            invoice_date
        ):
            return invoice_date

        if invoice_number:
            invoice_number = re.sub(r"^[#\s]*", "", invoice_number)
            return invoice_number

        return ""

    def _extract_invoice_date(self, data: Dict[str, Any]) -> str:
        invoice_date = data.get("invoice_date", "").strip()
        invoice_number = data.get("invoice_number", "").strip()

        if self._looks_like_number(invoice_date) and not self._looks_like_number(
            invoice_number
        ):
            return invoice_number

        if invoice_date:
            invoice_date = re.sub(r"[^\w\s,]", "", invoice_date)
            return invoice_date

        return ""

    def _extract_numeric_field(self, data: Dict[str, Any], field_name: str) -> float:
        value = data.get(field_name)

        if value is None:
            return 0.0

        try:
            if isinstance(value, str):
                value = re.sub(r"[^\d.]", "", value)

            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _extract_currency(self, data: Dict[str, Any]) -> str:
        currency = data.get("currency", "").strip().upper()

        if not currency or self._looks_like_timestamp(currency):
            return "USD"

        if currency in ["USD", "US$", "$"]:
            return "USD"

        return "USD"

    def _extract_line_items(self, data: Dict[str, Any]) -> Dict[str, Any]:
        line_items = data.get("line_items", [])

        result = {
            "line_item_description": "",
            "line_item_quantity": 0.0,
            "line_item_unit_price": 0.0,
            "line_item_amount": 0.0,
        }

        if line_items and len(line_items) > 0:
            first_item = line_items[0]

            description = first_item.get("description", "").strip()
            if not description:
                description = self._extract_description_from_other_fields(data)

            result["line_item_description"] = description
            result["line_item_quantity"] = self._safe_float(
                first_item.get("quantity", 0)
            )
            result["line_item_unit_price"] = self._safe_float(
                first_item.get("unit_price", 0)
            )
            result["line_item_amount"] = self._safe_float(first_item.get("amount", 0))

        return result

    def _extract_description_from_other_fields(self, data: Dict[str, Any]) -> str:
        potential_descriptions = [
            data.get("shipping_amount"),
            data.get("line_item_description"),
            data.get("vendor"),
        ]

        for desc in potential_descriptions:
            if desc and isinstance(desc, str) and not self._looks_like_number(desc):
                cleaned = str(desc).strip()
                if len(cleaned) > 3 and not cleaned.isdigit():
                    return cleaned

        return ""

    def _validate_and_clean(self, data: Dict[str, Any]) -> Dict[str, Any]:
        for field in self.canonical_schema:
            if field not in data:
                data[field] = self._get_default_value(field)

        string_fields = [
            "file_name",
            "vendor",
            "invoice_number",
            "invoice_date",
            "currency",
            "line_item_description",
            "parsed_timestamp",
        ]

        for field in string_fields:
            if data[field] is None:
                data[field] = ""
            else:
                data[field] = str(data[field]).strip()

        return data

    def _get_default_value(self, field: str) -> Any:
        defaults = {
            "file_name": "",
            "vendor": "SuperStore",
            "invoice_number": "",
            "invoice_date": "",
            "subtotal": 0.0,
            "shipping_amount": 0.0,
            "tax_amount": 0.0,
            "total_amount": 0.0,
            "currency": "USD",
            "line_item_description": "",
            "line_item_quantity": 0.0,
            "line_item_unit_price": 0.0,
            "line_item_amount": 0.0,
            "parsed_timestamp": datetime.now().isoformat(),
        }
        return defaults.get(field, "")

    def _safe_float(self, value) -> float:
        try:
            return float(value) if value is not None else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _looks_like_date(self, text: str) -> bool:
        if not isinstance(text, str):
            return False

        date_patterns = [
            r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}\s+\d{4}",
            r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
            r"\b\d{4}-\d{2}-\d{2}",
        ]

        text = text.strip()
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in date_patterns)

    def _looks_like_number(self, text: str) -> bool:
        if not isinstance(text, str):
            return False

        text = text.strip()
        if not text:
            return False

        text = re.sub(r"^[#\s]*", "", text)
        return text.replace(".", "").isdigit()

    def _looks_like_filename(self, text: str) -> bool:
        if not isinstance(text, str):
            return False

        return any(ext in text.lower() for ext in [".pdf", "invoice_", "inv_"])

    def _looks_like_timestamp(self, text: str) -> bool:
        if not isinstance(text, str):
            return False

        return bool(re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text))

    def _sanitize_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        sanitized = data.copy()
        return sanitized
