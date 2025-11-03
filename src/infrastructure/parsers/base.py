from abc import ABC, abstractmethod
from typing import List, Dict
import pandas as pd
from decimal import Decimal
from src.domain.models import InvoiceData, LineItem
import re
class BaseInvoiceParser(ABC):
    """Abstract base class for invoice parsers"""
    
    def __init__(self):
        self.patterns = {
            'invoice_number': r'(?:invoice|inv)\s*#?\s*:?\s*([A-Z0-9-]+)',
            'date': r'(?:date|dated)\s*:?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
            'total': r'(?:total|amount due|balance)\s*:?\s*\$?\s*([\d,]+\.?\d{0,2})',
            'vendor': r'^([A-Z][A-Za-z\s&.,]+(?:LLC|Inc|Ltd|Corp)?)',
        }
    
    @abstractmethod
    def extract_text(self, file_path: str) -> str:
        """Extract text from file"""
        pass
    
    @abstractmethod
    def extract_tables(self, file_path: str) -> List[pd.DataFrame]:
        """Extract tables from file"""
        pass
    
    def parse_metadata(self, text: str) -> Dict[str, str]:
        """Extract metadata using regex patterns"""
        metadata = {}
        text_lower = text.lower()
        
        for key, pattern in self.patterns.items():
            match = re.search(pattern, text_lower, re.IGNORECASE | re.MULTILINE)
            if match:
                metadata[key] = match.group(1).strip()
        
        return metadata
    
    def clean_line_items(self, tables: List[pd.DataFrame]) -> List[LineItem]:
        """Clean and convert tables to line items"""
        if not tables:
            return []
        
        line_items = []
        combined_df = pd.concat(tables, ignore_index=True)
        
        # Standardize column names
        column_mapping = {
            'description': ['description', 'item', 'product', 'service'],
            'quantity': ['quantity', 'qty', 'count'],
            'unit_price': ['unit price', 'price', 'rate', 'unit cost'],
            'amount': ['amount', 'total', 'line total', 'subtotal']
        }
        
        for std_name, variations in column_mapping.items():
            for col in combined_df.columns:
                if col and any(variation in str(col).lower() for variation in variations):
                    combined_df.rename(columns={col: std_name}, inplace=True)
                    break
        
        # Remove empty rows and convert to line items
        combined_df = combined_df.dropna(how='all')
        
        for _, row in combined_df.iterrows():
            try:
                line_item = LineItem(
                    description=str(row.get('description', '')),
                    quantity=Decimal(str(row.get('quantity', 1))),
                    unit_price=Decimal(str(row.get('unit_price', 0))),
                    amount=Decimal(str(row.get('amount', 0)))
                )
                line_items.append(line_item)
            except (ValueError, TypeError):
                continue
        
        return line_items
