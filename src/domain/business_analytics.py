from typing import List, Dict
from decimal import Decimal


class InvoiceAnalytics:
    @staticmethod
    def calculate_roi(parsed_invoices: List[Dict]) -> Dict:
        total_invoices = len(parsed_invoices)
        manual_time_per_invoice = Decimal("3.5")
        automated_time_per_invoice = Decimal("0.5")

        time_saved_minutes = (
            manual_time_per_invoice - automated_time_per_invoice
        ) * total_invoices
        time_saved_hours = time_saved_minutes / Decimal("60")
        cost_savings = time_saved_hours * Decimal("30")

        return {
            "total_invoices_processed": total_invoices,
            "time_saved_hours": float(time_saved_hours),
            "cost_savings": float(cost_savings),
            "efficiency_gain": float(
                (manual_time_per_invoice / automated_time_per_invoice) * 100
            ),
        }

    @staticmethod
    def generate_spend_analytics(parsed_invoices: List[Dict]) -> Dict:
        analytics = {
            "total_spend": Decimal("0"),
            "spend_by_vendor": {},
            "average_discount_rate": Decimal("0"),
            "shipping_costs": Decimal("0"),
        }

        total_discounts = Decimal("0")
        invoices_with_discounts = 0

        for invoice in parsed_invoices:
            total = invoice.get("total_amount", Decimal("0"))
            vendor = invoice.get("vendor", "Unknown")
            discount = invoice.get("discount_amount", Decimal("0"))
            shipping = invoice.get("shipping_amount", Decimal("0"))

            analytics["total_spend"] += total
            analytics["spend_by_vendor"][vendor] = (
                analytics["spend_by_vendor"].get(vendor, Decimal("0")) + total
            )
            analytics["shipping_costs"] += shipping

            if discount > 0:
                total_discounts += discount
                invoices_with_discounts += 1

        if invoices_with_discounts > 0:
            analytics["average_discount_rate"] = (
                total_discounts / analytics["total_spend"]
            ) * Decimal("100")

        return analytics
