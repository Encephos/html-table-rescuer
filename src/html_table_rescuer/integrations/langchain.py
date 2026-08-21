from collections.abc import Iterator
from typing import Optional

from langchain_community.document_loaders.base import BaseLoader
from langchain_core.documents import Document

from html_table_rescuer.core import TableParser
from html_table_rescuer.models import ParseConfig


class HTMLTableRescuerLoader(BaseLoader):
    """
    LangChain Document Loader der HTML-Dateien nach Tabellen durchsucht 
    und diese als Markdown-Dokumente extrahiert. Behebt typische Probleme 
    mit colspan und rowspan.
    """

    def __init__(self, file_path: str, config: Optional[ParseConfig] = None):
        """
        Initialisiert den Loader.

        Args:
            file_path: Pfad zur HTML-Datei.
            config: Optionales html_table_rescuer ParseConfig Objekt.
        """
        self.file_path = file_path
        self.config = config

    def lazy_load(self) -> Iterator[Document]:
        """Lädt die HTML-Datei und yieldet jede Tabelle als eigenes LangChain Document."""
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                html_content = f.read()
        except Exception as e:
            raise RuntimeError(f"Error reading file {self.file_path}: {e}")

        parser = TableParser(html_content, self.config)
        tables = parser.parse()

        for idx, table in enumerate(tables):
            # Nutzt jetzt die sauber umbenannte to_markdown() Methode
            md_content = table.to_markdown()
            
            metadata = {
                "source": self.file_path,
                "table_index": idx,
                "parser": "html_table_rescuer"
            }
            # Der Tabellentitel ist für Retrieval oft die wertvollste Metadate
            if table.caption:
                metadata["caption"] = table.caption

            yield Document(page_content=md_content, metadata=metadata)
