from abc import ABC, abstractmethod
from packages.code.models import Document


class BaseLoader(ABC):
    @abstractmethod
    def load(self, file_path: str, doc_id: str, title: str) -> list[Document]:
        ...
