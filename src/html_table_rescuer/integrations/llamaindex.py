from pathlib import Path
from typing import Iterable, Optional, Union

from llama_index.core.readers.base import BaseReader
from llama_index.core.schema import Document

from html_table_rescuer.core import TableParser
from html_table_rescuer.models import ParseConfig


class HTMLTableRescuerReader(BaseReader):
    """
    LlamaIndex Reader der HTML-Dateien nach Tabellen durchsucht und diese als
    Markdown-Dokumente extrahiert. Behebt typische Probleme mit colspan und rowspan.

    Nutzbar direkt oder als `file_extractor` in einem SimpleDirectoryReader:

        from llama_index.core import SimpleDirectoryReader

        reader = SimpleDirectoryReader(
            "./docs",
            file_extractor={".html": HTMLTableRescuerReader()},
        )
    """

    def __init__(self, config: Optional[ParseConfig] = None):
        """
        Initialisiert den Reader.

        Args:
            config: Optionales html_table_rescuer ParseConfig Objekt.
        """
        self.config = config

    def lazy_load_data(
        self,
        file: Union[str, Path],
        extra_info: Optional[dict] = None,
    ) -> Iterable[Document]:
        """Lädt die HTML-Datei und yieldet jede Tabelle als eigenes LlamaIndex Document."""
        file_path = Path(file)
        try:
            html_content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            raise RuntimeError(f"Error reading file {file_path}: {e}")

        parser = TableParser(html_content, self.config)

        for idx, table in enumerate(parser.parse()):
            metadata = {
                "source": str(file_path),
                "table_index": idx,
                "parser": "html_table_rescuer",
            }
            # Der Tabellentitel ist für Retrieval oft die wertvollste Metadate
            if table.caption:
                metadata["caption"] = table.caption
            # extra_info von SimpleDirectoryReader hat Vorrang
            if extra_info:
                metadata.update(extra_info)

            yield Document(text=table.to_markdown(), metadata=metadata)
