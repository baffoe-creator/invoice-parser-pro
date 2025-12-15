from typing import Dict, Any
from src.domain.interfaces import InvoiceParser, InvoiceRepository
from src.infrastructure.file_handlers.secure_file_handler import SecureFileHandler
from src.domain.exceptions import InvoiceParsingError


class ParseInvoiceUseCase:
    def __init__(
        self,
        parser: InvoiceParser,
        repository: InvoiceRepository,
        file_handler: SecureFileHandler,
    ):
        self.parser = parser
        self.repository = repository
        self.file_handler = file_handler

    async def execute(
        self, file_content: bytes, filename: str, user_id: str
    ) -> Dict[str, Any]:
        try:
            print(f"🔍 USE CASE: Starting execution for {filename}")

            await self.file_handler.validate_file(file_content, filename)

            temp_path = self.file_handler.create_secure_temp_file(file_content)

            try:
                print("🔍 USE CASE: Calling parser...")
                invoice_data = self.parser.parse(temp_path)

                # DIAGNOSTIC: Check what parser returned
                print(f"\n{'='*60}")
                print(f"💰 RAW PARSER OUTPUT FOR: {filename}")
                print(f"{'='*60}")
                print(f"Type: {type(invoice_data)}")

                if hasattr(invoice_data, "to_dict"):
                    parsed_dict = invoice_data.to_dict()
                    print("Converted object to dict using to_dict()")
                else:
                    parsed_dict = invoice_data
                    print("Using raw parser output (already a dict)")

                print(f"\n📋 ALL FIELDS IN PARSED DATA:")
                for key, value in parsed_dict.items():
                    print(f"   {key}: {value} (type: {type(value).__name__})")

                # DIAGNOSTIC: Check financial fields specifically
                print(f"\n💰 FINANCIAL FIELDS CHECK:")
                financial_fields = [
                    "subtotal",
                    "shipping_amount",
                    "tax_amount",
                    "total_amount",
                ]
                for field in financial_fields:
                    value = parsed_dict.get(field)
                    if value is None:
                        print(f"   ❌ {field}: MISSING (None)")
                    elif value == 0 or value == 0.0:
                        print(
                            f"   ⚠️  {field}: {value} (ZERO - might be extraction issue)"
                        )
                    else:
                        print(f"   ✅ {field}: {value}")

                print(f"{'='*60}\n")

                if not isinstance(parsed_dict, dict):
                    raise ValueError("Parser did not return a dictionary")

                parsed_dict = self._clean_parsed_data(parsed_dict)

                # DIAGNOSTIC: Check after cleaning
                print(f"\n🧹 AFTER CLEANING:")
                for field in financial_fields:
                    print(f"   {field}: {parsed_dict.get(field)}")

                print("🔍 USE CASE: Saving to repository...")
                invoice_id = self.repository.save(parsed_dict, user_id, filename)

                return {
                    "success": True,
                    "invoice_id": invoice_id,
                    "parsed_data": parsed_dict,
                    "message": "Invoice parsed successfully",
                }

            except Exception as parse_error:
                print(f"❌ USE CASE: Parser error: {str(parse_error)}")
                import traceback

                print(f"❌ Full traceback:\n{traceback.format_exc()}")
                return {
                    "success": False,
                    "error": f"Parsing failed: {str(parse_error)}",
                    "message": "Failed to parse invoice content",
                }

            finally:
                self.file_handler.cleanup_temp_file(temp_path)

        except InvoiceParsingError as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Failed to parse invoice",
            }
        except Exception as e:
            print(f"❌ USE CASE: General error: {str(e)}")
            import traceback

            print(f"❌ Full traceback:\n{traceback.format_exc()}")
            return {
                "success": False,
                "error": f"Processing failed: {str(e)}",
                "message": "Failed to process invoice file",
            }

    def _clean_parsed_data(self, parsed_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and order parsed data - now parser returns correct field names"""

        # Preferred field order for output
        preferred_order = [
            "vendor",
            "invoice_number",
            "invoice_date",
            "subtotal",
            "shipping_amount",
            "tax_amount",
            "total_amount",
            "currency",
            "discount_amount",
            "discount_percentage",
            "line_items",
            "raw_text",
        ]

        # Build ordered dict preserving all fields
        ordered_dict = {}
        for field in preferred_order:
            if field in parsed_dict:
                ordered_dict[field] = parsed_dict[field]

        # Add any remaining fields not in preferred order
        for field, value in parsed_dict.items():
            if field not in ordered_dict:
                ordered_dict[field] = value

        return ordered_dict
