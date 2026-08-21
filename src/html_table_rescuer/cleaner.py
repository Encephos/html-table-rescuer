import re

from bs4 import Comment, NavigableString, Tag

from .models import ParseConfig

# Tags whose text content is code, not cell content. Wikipedia and most CMS
# exports inline <style> blocks inside tables; their CSS must not become text.
NON_CONTENT_TAGS = frozenset({"style", "script", "template", "noscript"})


def clean_cell_content(cell: Tag, config: ParseConfig) -> str:
    """
    Wandelt HTML-Inhalt einer Zelle rekursiv in einen Markdown-String um,
    sodass Formatierungen auch in verschachtelten Tags (z.B. div > span > b) erhalten bleiben.
    """
    if not cell:
        return ""

    def _parse_element(element) -> str:
        # HTML-Kommentare sind NavigableString-Subklassen und dürfen nicht als Text durchrutschen
        if isinstance(element, Comment):
            return ""

        # --- 1. Base Case: Wir sind beim reinen Text angekommen ---
        if isinstance(element, NavigableString):
            text = str(element).replace("\n", " ").strip()
            # Pipes müssen für MD-Tabellen escaped werden
            text = text.replace("|", "\\|")
            return text

        # --- 2. Rekursiver Case: Wir sind bei einem HTML-Tag ---
        if isinstance(element, Tag):
            # Sonderfall <br>
            if element.name == 'br':
                return "<br>"

            # <style>/<script> enthalten Code, keinen Zellinhalt
            if element.name in NON_CONTENT_TAGS:
                return ""

            # Wir sammeln zuerst den verarbeiteten Text ALLER Kinder dieses Tags
            child_texts = []
            for child in element.contents:
                parsed_child = _parse_element(child)
                if parsed_child:
                    child_texts.append(parsed_child)
            
            # Text der Kinder zusammenfügen
            inner_text = " ".join(child_texts).strip()

            if not inner_text:
                return ""

            # --- 3. Formatierung von "innen nach außen" anwenden ---
            if element.name == 'a' and element.get('href') and config.keep_links:
                href = element.get('href')
                return f"[{inner_text}]({href})"
            
            elif element.name in ['b', 'strong'] and config.keep_bold:
                return f"**{inner_text}**"
            
            elif element.name in ['i', 'em'] and config.keep_italic:
                return f"_{inner_text}_"
            
            else:
                # div, span, p, td etc. -> Tag ignorieren, aber seinen (bereits formatierten) Inhalt durchreichen!
                return inner_text
        
        return ""

    # Zelle an die rekursive Funktion übergeben
    raw_result = _parse_element(cell)
    
    # Kosmetik: Durch das rekursive Zusammenfügen können doppelte Leerzeichen entstehen.
    # Wir machen aus mehreren Leerzeichen ein einzelnes.
    final_result = re.sub(r'\s+', ' ', raw_result)
    
    return final_result.strip()
