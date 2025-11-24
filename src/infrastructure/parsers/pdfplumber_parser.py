import pdfplumber
import pandas as pd
import re
from typing import List, Dict
from decimal import Decimal
from src.infrastructure.parsers.base import BaseInvoiceParser
from src.domain.interfaces import InvoiceParser
from src.domain.models import InvoiceData, LineItem
from src.domain.exceptions import ParsingFailedError


class PdfPlumberParser(BaseInvoiceParser, InvoiceParser):

    def extract_text(self, file_path: str) -> str:
        try:
            text = ""
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
            return text
        except Exception as e:
            raise ParsingFailedError(f"Failed to extract text from PDF: {str(e)}")

    def extract_tables(self, file_path: str) -> List[pd.DataFrame]:
        try:
            tables = []
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    extracted_tables = page.extract_tables(
                        {"vertical_strategy": "lines", "horizontal_strategy": "text"}
                    )
                    for table in extracted_tables or []:
                        if table and len(table) > 1:
                            df = pd.DataFrame(table[1:], columns=table[0])
                            tables.append(df)
            return tables
        except Exception as e:
            raise ParsingFailedError(f"Failed to extract tables from PDF: {str(e)}")

    def parse(self, file_path: str) -> InvoiceData:
        try:
            text = self.extract_text(file_path)
            tables = self.extract_tables(file_path)

            financials = self.extract_financials_with_validation(text)
            metadata = self.extract_metadata_with_fallbacks(text)
            line_items = self.extract_structured_line_items(tables, text)

            self.validate_business_logic(financials, line_items, text)

            return InvoiceData(
                vendor=metadata.get("vendor", "Unknown Vendor"),
                invoice_number=metadata.get("invoice_number", "N/A"),
                invoice_date=metadata.get("date", "N/A"),
                total_amount=financials["final_total"],
                currency="USD",
                line_items=line_items,
                raw_text=text[:1000],
                subtotal=financials["subtotal"],
                discount_amount=financials["discount"],
                discount_percentage=financials["discount_percentage"],
                shipping_amount=financials["shipping"],
                tax_amount=financials["tax"],
            )
        except Exception as e:
            raise ParsingFailedError(f"Invoice parsing failed: {str(e)}")

    def extract_financials_with_validation(self, text: str) -> Dict[str, Decimal]:
        financials = {
            "subtotal": Decimal("0"),
            "discount": Decimal("0"),
            "discount_percentage": Decimal("0"),
            "shipping": Decimal("0"),
            "tax": Decimal("0"),
            "final_total": Decimal("0"),
        }

        print(f"🔍 RAW TEXT FOR DEBUGGING:\n{text[:2000]}")

        balance_due_match = re.search(
            r"Balance Due:\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE
        )
        total_match = re.search(r"Total:\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        amount_due_match = re.search(
            r"Amount Due:\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE
        )

        if balance_due_match:
            financials["final_total"] = Decimal(
                balance_due_match.group(1).replace(",", "")
            )
        elif total_match:
            financials["final_total"] = Decimal(total_match.group(1).replace(",", ""))
        elif amount_due_match:
            financials["final_total"] = Decimal(
                amount_due_match.group(1).replace(",", "")
            )

        subtotal_match = re.search(
            r"Subtotal:\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE
        )
        if subtotal_match:
            financials["subtotal"] = Decimal(subtotal_match.group(1).replace(",", ""))

        discount_patterns = [
            r"Discount\s*[^:\n]*:\s*\$?\s*([\d,]+\.\d{2})",
            r"\$?([\d,]+\.\d{2})\s*\(?(\d+\.?\d*)%?\)?\s*[Dd]iscount",
            r"Discount\s*Amount\s*:\s*\$?\s*([\d,]+\.\d{2})",
            r"Savings\s*:\s*\$?\s*([\d,]+\.\d{2})",
            r"Deduction\s*:\s*\$?\s*([\d,]+\.\d{2})",
            r"Less\s*:\s*\$?\s*([\d,]+\.\d{2})",
        ]

        discount_percent_patterns = [
            r"Discount\s*\(?(\d+\.?\d*)%?\)?",
            r"(\d+\.?\d*)%\s*[Dd]iscount",
            r"Discount\s*Rate\s*:\s*(\d+\.?\d*)%",
        ]

        for pattern in discount_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    amount_str = match.group(1).replace(",", "")
                    try:
                        financials["discount"] = Decimal(amount_str)
                        print(f"💰 FOUND DISCOUNT AMOUNT: ${financials['discount']}")
                        break
                    except:
                        continue

        for pattern in discount_percent_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                percent_str = match.group(1)
                try:
                    financials["discount_percentage"] = Decimal(percent_str)
                    print(
                        f"💰 FOUND DISCOUNT PERCENTAGE: {financials['discount_percentage']}%"
                    )
                    break
                except:
                    continue

        shipping_match = re.search(
            r"Shipping:\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE
        )
        if shipping_match:
            financials["shipping"] = Decimal(shipping_match.group(1).replace(",", ""))

        tax_match = re.search(r"Tax:\s*\$?\s*([\d,]+\.\d{2})", text, re.IGNORECASE)
        if tax_match:
            financials["tax"] = Decimal(tax_match.group(1).replace(",", ""))

        if financials["discount"] == Decimal("0") and financials[
            "discount_percentage"
        ] > Decimal("0"):
            if financials["subtotal"] > Decimal("0"):
                financials["discount"] = (
                    financials["subtotal"]
                    * financials["discount_percentage"]
                    / Decimal("100")
                ).quantize(Decimal("0.01"))
                print(
                    f"💰 CALCULATED DISCOUNT FROM PERCENTAGE: ${financials['discount']}"
                )

        if financials["discount_percentage"] == Decimal("0") and financials[
            "discount"
        ] > Decimal("0"):
            if financials["subtotal"] > Decimal("0"):
                financials["discount_percentage"] = (
                    (financials["discount"] / financials["subtotal"]) * Decimal("100")
                ).quantize(Decimal("0.01"))
                print(
                    f"💰 CALCULATED DISCOUNT PERCENTAGE FROM AMOUNT: {financials['discount_percentage']}%"
                )

        calculated_total_before_discount = (
            financials["subtotal"] + financials["shipping"] + financials["tax"]
        )

        if (
            financials["final_total"] > Decimal("0")
            and financials["discount"] == Decimal("0")
            and calculated_total_before_discount > financials["final_total"]
        ):

            potential_discount = (
                calculated_total_before_discount - financials["final_total"]
            )
            if potential_discount > Decimal("0.01"):
                financials["discount"] = potential_discount.quantize(Decimal("0.01"))
                if financials["subtotal"] > Decimal("0"):
                    financials["discount_percentage"] = (
                        (financials["discount"] / financials["subtotal"])
                        * Decimal("100")
                    ).quantize(Decimal("0.01"))
                print(
                    f"💰 INFERRED DISCOUNT FROM TOTALS: ${financials['discount']} ({financials['discount_percentage']}%)"
                )

        print(
            f"💰 FINAL FINANCIALS: Subtotal=${financials['subtotal']}, Discount=${financials['discount']}, Discount%={financials['discount_percentage']}, Shipping=${financials['shipping']}, Tax=${financials['tax']}, Total=${financials['final_total']}"
        )
        print(
            f"💰 CALCULATION CHECK: (Subtotal ${financials['subtotal']} + Shipping ${financials['shipping']} + Tax ${financials['tax']}) - Discount ${financials['discount']} = ${(financials['subtotal'] + financials['shipping'] + financials['tax'] - financials['discount']).quantize(Decimal('0.01'))} vs Total ${financials['final_total']}"
        )

        return financials

    def extract_metadata_with_fallbacks(self, text: str) -> Dict[str, str]:
        metadata = {}

        vendor_patterns = [
            r"^([A-Z][A-Za-z\s&]+(?:Inc|LLC|Ltd|Corp|Company|Store)?)",
            r"From:\s*([^\n]+)",
            r"Vendor:\s*([^\n]+)",
            r"Bill From:\s*([^\n]+)",
        ]

        for pattern in vendor_patterns:
            match = re.search(pattern, text)
            if match:
                vendor_name = match.group(1).strip()
                if "invoice" in vendor_name.lower():
                    vendor_name = vendor_name.replace("invoice", "").strip()
                if "INVOICE" in vendor_name:
                    vendor_name = vendor_name.replace("INVOICE", "").strip()
                metadata["vendor"] = vendor_name
                break

        if "vendor" not in metadata:
            first_line = text.split("\n")[0].strip()
            if first_line and len(first_line) > 3:
                metadata["vendor"] = first_line

        date_patterns = [
            r"Date:\s*([A-Za-z]+\s+\d{1,2}\s+\d{4})",
            r"Invoice Date:\s*([A-Za-z]+\s+\d{1,2}\s+\d{4})",
            r"(\w{3}\s+\d{1,2}\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{4})",
            r"Order Date\s*[:\-]\s*([^,\n]+)",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["date"] = match.group(1).strip()
                break

        invoice_patterns = [
            r"#\s*(\d+)",
            r"Invoice\s*#?\s*:?\s*(\d+)",
            r"INVOICE\s*#?\s*:?\s*(\d+)",
            r"Invoice Number:\s*(\d+)",
        ]

        for pattern in invoice_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata["invoice_number"] = match.group(1)
                break

        return metadata

    def extract_structured_line_items(
        self, tables: List[pd.DataFrame], text: str
    ) -> List[LineItem]:
        line_items = []

        if tables:
            for table in tables:
                items = self.parse_table_to_line_items(table)
                line_items.extend(items)

        if not line_items:
            text_items = self.extract_line_items_from_text_patterns(text)
            line_items.extend(text_items)

        return line_items

    def parse_table_to_line_items(self, table: pd.DataFrame) -> List[LineItem]:
        line_items = []

        if table.empty:
            return line_items

        column_mapping = {
            "description": ["description", "item", "product", "service", "name"],
            "quantity": ["quantity", "qty", "count"],
            "unit_price": ["unit price", "price", "rate", "unit cost", "cost"],
            "amount": ["amount", "total", "line total", "subtotal"],
        }

        df = table.copy()
        df.columns = [str(col).lower().strip() if col else "" for col in df.columns]

        for std_name, variations in column_mapping.items():
            for col in df.columns:
                if any(variation in col for variation in variations):
                    df.rename(columns={col: std_name}, inplace=True)
                    break

        for _, row in df.iterrows():
            try:
                if self._is_header_row(row):
                    continue

                description = str(row.get("description", "")).strip()
                quantity = self._safe_decimal(row.get("quantity", 1))
                unit_price = self._safe_decimal(row.get("unit_price", 0))
                amount = self._safe_decimal(row.get("amount", 0))

                if description and (quantity > 0 or unit_price > 0 or amount > 0):
                    line_item = LineItem(
                        description=description,
                        quantity=quantity,
                        unit_price=unit_price,
                        amount=amount,
                    )
                    line_items.append(line_item)
            except (ValueError, TypeError) as e:
                continue

        return line_items

    def extract_line_items_from_text_patterns(self, text: str) -> List[LineItem]:
        line_items = []

        item_patterns = [
            r"([A-Za-z][^$\n]{10,}?)\s+(\d+)\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})",
            r"([A-Za-z][^$\n]{10,}?)\s+(\d+)\s+([\d,]+\.\d{2})\s+([\d,]+\.\d{2})",
        ]

        for pattern in item_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                try:
                    description, quantity, unit_price, amount = match
                    line_item = LineItem(
                        description=description.strip(),
                        quantity=Decimal(quantity),
                        unit_price=Decimal(unit_price.replace(",", "")),
                        amount=Decimal(amount.replace(",", "")),
                    )
                    line_items.append(line_item)
                except (ValueError, TypeError):
                    continue

        return line_items

    def validate_business_logic(
        self, financials: Dict[str, Decimal], line_items: List[LineItem], text: str
    ):
        calculated_total = (
            financials["subtotal"]
            - financials["discount"]
            + financials["shipping"]
            + financials["tax"]
        )

        if financials["final_total"] > Decimal("0") and abs(
            calculated_total - financials["final_total"]
        ) > Decimal("0.10"):
            print(
                f"⚠️  Invoice validation: Calculated ${calculated_total} vs Parsed ${financials['final_total']}"
            )

        line_items_total = sum(item.amount for item in line_items)
        if financials["subtotal"] > Decimal("0") and abs(
            line_items_total - financials["subtotal"]
        ) > Decimal("0.10"):
            print(
                f"⚠️  Line items validation: Items sum to ${line_items_total} vs Subtotal ${financials['subtotal']}"
            )

        if financials["discount"] > financials["subtotal"]:
            print("⚠️  Business validation: Discount exceeds subtotal")

        if financials["final_total"] <= Decimal("0") and financials[
            "subtotal"
        ] > Decimal("0"):
            print("⚠️  Business validation: Invalid total amount")

    def _is_header_row(self, row) -> bool:
        if row.empty:
            return True

        row_text = " ".join(str(x) for x in row.values if x).lower()
        header_indicators = [
            "item",
            "description",
            "quantity",
            "price",
            "amount",
            "total",
        ]

        return any(indicator in row_text for indicator in header_indicators)

    def _safe_decimal(self, value, default=Decimal("0")) -> Decimal:
        try:
            if pd.isna(value) or value == "":
                return default
            clean_value = str(value).replace("$", "").replace(",", "").strip()
            return Decimal(clean_value)
        except (ValueError, TypeError):
            return default
