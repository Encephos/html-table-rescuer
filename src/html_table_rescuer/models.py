import csv
import io
import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class RowspanStrategy(Enum):
    """Strategie für vertikal verbundene Zellen (rowspan)."""
    FILL_WITH_DITO = "fill_dito"   # Schreibt 'dito (Wert)' in die unteren Zellen
    REPEAT_VALUE = "repeat"        # Wiederholt den Wert 1:1
    EMPTY = "empty"                # Lässt die unteren Zellen leer

@dataclass
class ParseConfig:
    """Konfiguration für den Parsing-Prozess."""
    rowspan_strategy: RowspanStrategy = RowspanStrategy.FILL_WITH_DITO
    dito_prefix: str = "dito"  # Nur relevant für FILL_WITH_DITO
    
    # Formatierungs-Optionen
    keep_links: bool = True    # <a href="..."> behalten
    keep_bold: bool = True     # <b> / <strong> behalten
    keep_italic: bool = True   # <i> / <em> behalten
    
    # Verbindet die Ebenen eines gestapelten Headers, z.B. "Peak positions - US"
    header_separator: str = " - "

    # Technisches
    parser_library: str = "lxml" # oder 'html.parser'

@dataclass
class ParsedTable:
    """Das Ergebnis einer Konvertierung (zuvor MarkdownTable)."""
    headers: list[str]
    rows: list[list[str]]
    caption: Optional[str] = None

    def to_markdown(self, include_caption: bool = True) -> str:
        """
        Rendert die Tabelle zu einem Markdown-String.

        Die <caption> wird als fette Zeile vorangestellt — für ein LLM ist der
        Tabellentitel oft die wichtigste Information am Chunk.
        """
        if not self.headers and not self.rows:
            return ""
            
        lines = []
        
        # Grid Dimension bestimmen
        cols = len(self.headers)
        if cols == 0 and self.rows:
            cols = len(self.rows[0])
            # Leere Header generieren, falls keine <th> da waren
            header_line = f"| {' | '.join([''] * cols)} |"
        else:
            header_line = f"| {' | '.join(self.headers)} |"
            
        lines.append(header_line)
        lines.append(f"| {' | '.join(['---'] * cols)} |")
        
        for row in self.rows:
            # Padding: Zeile auffüllen falls zu kurz
            current_row = row + [""] * (cols - len(row))
            # Abschneiden falls zu lang
            current_row = current_row[:cols]
            lines.append(f"| {' | '.join(current_row)} |")

        table = "\n".join(lines)
        if include_caption and self.caption:
            return f"**{self.caption}**\n\n{table}"
        return table

    # Abwärtskompatibilität: Falls jemand schon to_string() nutzt
    def to_string(self) -> str:
        return self.to_markdown()

    def _repr_markdown_(self) -> str:
        """Jupyter/Colab-Integration: Tabellen rendern automatisch als Markdown."""
        return self.to_markdown()

    def to_json(self, indent: int = 2) -> str:
        """Rendert die Tabelle zu einem JSON-String (Liste von Dictionaries)."""
        if not self.headers and not self.rows:
            return "[]"
        
        result = []
        # Fallback falls Headers fehlen
        effective_headers = self.headers if self.headers else [f"Column {i+1}" for i in range(len(self.rows[0])) if self.rows]
        
        for row in self.rows:
            # Stelle sicher, dass row und headers gleich lang sind
            padded_row = row + [""] * (len(effective_headers) - len(row))
            padded_row = padded_row[:len(effective_headers)]
            
            row_dict = dict(zip(effective_headers, padded_row))
            result.append(row_dict)
            
        return json.dumps(result, indent=indent, ensure_ascii=False)

    def to_csv(self, delimiter: str = ',') -> str:
        """Rendert die Tabelle zu einem CSV-String."""
        if not self.headers and not self.rows:
            return ""
            
        output = io.StringIO()
        writer = csv.writer(output, delimiter=delimiter)
        
        if self.headers:
            writer.writerow(self.headers)
            
        for row in self.rows:
            # Padding: Zeile auffüllen falls zu kurz (orientiert an headern)
            cols = len(self.headers) if self.headers else len(row)
            current_row = row + [""] * (cols - len(row))
            current_row = current_row[:cols]
            writer.writerow(current_row)
            
        return output.getvalue()
