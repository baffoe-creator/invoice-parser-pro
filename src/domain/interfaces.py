from abc import ABC, abstractmethod
from typing import Dict, Any


class InvoiceParser(ABC):
    @abstractmethod
    def parse(self, file_path: str) -> Dict[str, Any]:
        pass


class InvoiceRepository(ABC):
    @abstractmethod
    def save(self, invoice_data: Dict[str, Any], user_id: str, filename: str) -> str:
        pass

    @abstractmethod
    def get_by_user(self, user_id: str) -> list:
        pass
