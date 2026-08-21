import logging
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from haystack import Document, component, default_from_dict, default_to_dict
from haystack.components.converters.utils import get_bytestream_from_source, normalize_metadata
from haystack.dataclasses import ByteStream

from html_table_rescuer.core import TableParser
from html_table_rescuer.models import ParseConfig, RowspanStrategy

logger = logging.getLogger(__name__)


@component
class HTMLTableRescuerConverter:
    """
    Haystack Converter der HTML-Quellen nach Tabellen durchsucht und jede Tabelle
    als eigenes Document ausgibt. Behebt typische Probleme mit colspan und rowspan.

    Im Gegensatz zu Haystacks HTMLToDocument erzeugt eine Quelle mehrere Documents
    (eines pro Tabelle), damit Retrieval eine Tabelle nie in der Mitte zerschneidet.

        from haystack import Pipeline

        pipe = Pipeline()
        pipe.add_component("converter", HTMLTableRescuerConverter())
        result = pipe.run({"converter": {"sources": ["page.html"]}})
    """

    def __init__(self, config: Optional[ParseConfig] = None):
        """
        Initialisiert den Converter.

        Args:
            config: Optionales html_table_rescuer ParseConfig Objekt.
        """
        self.config = config

    def to_dict(self) -> Dict[str, Any]:
        """Serialisiert die Komponente (für Pipeline-YAML)."""
        config = None
        if self.config is not None:
            config = asdict(self.config)
            # asdict lässt Enums unangetastet — für YAML/JSON den Wert nutzen
            config["rowspan_strategy"] = self.config.rowspan_strategy.value
        return default_to_dict(self, config=config)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HTMLTableRescuerConverter":
        """Deserialisiert die Komponente."""
        config = data.get("init_parameters", {}).get("config")
        if config is not None:
            config = dict(config)
            config["rowspan_strategy"] = RowspanStrategy(config["rowspan_strategy"])
            data["init_parameters"]["config"] = ParseConfig(**config)
        return default_from_dict(cls, data)

    @component.output_types(documents=List[Document])
    def run(
        self,
        sources: List[Union[str, Path, ByteStream]],
        meta: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    ) -> Dict[str, Any]:
        """
        Wandelt HTML-Quellen in Documents um — ein Document pro gefundener Tabelle.

        Args:
            sources: Liste von Dateipfaden oder ByteStream-Objekten.
            meta: Optionale Metadaten, entweder ein Dict für alle Quellen oder
                eine Liste mit einem Dict pro Quelle.

        Returns:
            Dict mit dem Schlüssel `documents`.
        """
        documents: List[Document] = []
        meta_list = normalize_metadata(meta=meta, sources_count=len(sources))

        for source, extra_meta in zip(sources, meta_list):
            try:
                bytestream = get_bytestream_from_source(source=source)
            except Exception as e:
                # Haystack-Konvention: fehlerhafte Quelle überspringen,
                # nicht die ganze Pipeline abbrechen
                logger.warning("Could not read %s. Skipping it. Error: %s", source, e)
                continue

            try:
                encoding = bytestream.meta.get("encoding", "utf-8")
                html_content = bytestream.data.decode(encoding)
                tables = TableParser(html_content, self.config).parse()
            except Exception as e:
                logger.warning("Failed to extract tables from %s. Skipping it. Error: %s", source, e)
                continue

            for idx, table in enumerate(tables):
                metadata = dict(bytestream.meta)
                metadata["table_index"] = idx
                metadata["parser"] = "html_table_rescuer"
                if "file_path" in bytestream.meta:
                    metadata["source"] = bytestream.meta["file_path"]
                # Der Tabellentitel ist für Retrieval oft die wertvollste Metadate
                if table.caption:
                    metadata["caption"] = table.caption
                # Nutzer-Metadaten haben Vorrang
                metadata.update(extra_meta)

                documents.append(Document(content=table.to_markdown(), meta=metadata))

        return {"documents": documents}
