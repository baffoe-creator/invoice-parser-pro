from abc import ABC, abstractmethod
from typing import List, Dict
import pandas as pd
from decimal import Decimal
from src.domain.models import InvoiceData, LineItem
import re

class BaseInvoiceParser(ABC):
    
    def __init__(self):
        self.patterns = {
            'invoice_number': r'(?:invoice|inv)\s*#?\s*:?\s*([A-Z0-9-]+)',
            'date': r'(?:date|dated)\s*:?\s*([A-Za-z]+\s+\d{1,2}\s+\d{4})',
            'total': r'(?:total|amount due|balance)\s*:?\s*\$?\s*([\d,]+\.?\d{0,2})',
            'vendor': r'^([A-Z][A-Za-z\s&.,]+(?:LLC|Inc|Ltd|Corp)?)',
        }
    
    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        pass
    
    @abstractmethod
    def extract_tables(self, file_path: str) -> List[pd.DataFrame]:
        pass
    
    def parse_metadata(self, text: str) -> Dict[str, str]:
        metadata = {}
        
        invoice_number_match = re.search(r'#\s*(\d+)', text)
        if invoice_number_match:
            metadata['invoice_number'] = invoice_number_match.group(1)
        
        date_match = re.search(r'Date:\s*([A-Za-z]+\s+\d{1,2}\s+\d{4})', text)
        if date_match:
            metadata['date'] = date_match.group(1)
        
        total_match = re.search(r'Total:\s*\$?([\d,]+\.\d{2})', text)
        if total_match:
            metadata['total'] = total_match.group(1).replace(',', '')
        
        balance_match = re.search(r'Balance Due:\s*\$?([\d,]+\.\d{2})', text)
        if balance_match:
            metadata['total'] = balance_match.group(1).replace(',', '')
        
        vendor_match = re.search(r'^([A-Z][a-zA-Z\s]+)', text)
        if vendor_match:
            metadata['vendor'] = vendor_match.group(1).strip()
        
        return metadata
    
    def clean_line_items(self, tables: List[pd.DataFrame]) -> List[LineItem]:
        if not tables:
            return []
        
        line_items = []
        
        for table in tables:
            if table.empty:
                continue
            
            df = table.copy()
            df.columns = [str(col).lower().strip() if col else '' for col in df.columns]
            
            for _, row in df.iterrows():
                try:
                    description = self._extract_field(row, ['description', 'item', 'product', 'service'])
                    quantity = self._extract_numeric_field(row, ['quantity', 'qty'])
                    unit_price = self._extract_numeric_field(row, ['unit price', 'price', 'rate', 'unit cost'])
                    amount = self._extract_numeric_field(row, ['amount', 'total', 'line total'])
                    
                    if description and any([quantity, unit_price, amount]):
                        line_item = LineItem(
                            description=str(description),
                            quantity=Decimal(str(quantity)) if quantity else Decimal('1'),
                            unit_price=Decimal(str(unit_price)) if unit_price else Decimal('0'),
                            amount=Decimal(str(amount)) if amount else Decimal('0')
                        )
                        line_items.append(line_item)
                except (ValueError, TypeError, Exception) as e:
                    continue
        
        return line_items
    
    def _extract_field(self, row, field_names):
        for field in field_names:
            if field in row and pd.notna(row[field]) and str(row[field]).strip():
                return str(row[field]).strip()
        return ""
    
    def _extract_numeric_field(self, row, field_names):
        for field in field_names:
            if field in row and pd.notna(row[field]):
                value = str(row[field]).replace('$', '').replace(',', '').strip()
                if value and re.match(r'^-?\d*\.?\d+$', value):
                    return float(value)
        return 0.0