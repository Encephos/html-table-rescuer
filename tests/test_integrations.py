"""Tests für die Framework-Integrationen (LangChain, LlamaIndex, Haystack).

Alle Frameworks sind optionale Extras — die Tests werden übersprungen,
wenn das jeweilige Paket nicht installiert ist.
"""
import json

import pytest

from html_table_rescuer.models import ParseConfig, RowspanStrategy

TWO_TABLES_HTML = """
<table>
    <tr><th>Name</th><th>Alter</th></tr>
    <tr><td>Max</td><td>25</td></tr>
</table>
<table>
    <tr><th>Stadt</th></tr>
    <tr><td>Berlin</td></tr>
</table>
"""

ROWSPAN_HTML = """
<table>
    <tr><th>Gruppe</th><th>Wert</th></tr>
    <tr><td rowspan="2">A</td><td>1</td></tr>
    <tr><td>2</td></tr>
</table>
"""


@pytest.fixture
def html_file(tmp_path):
    def _write(content=TWO_TABLES_HTML):
        f = tmp_path / "tables.html"
        f.write_text(content, encoding="utf-8")
        return f

    return _write


# --- LangChain ---------------------------------------------------------------


@pytest.fixture
def langchain_loader_cls():
    pytest.importorskip("langchain_core")
    pytest.importorskip("langchain_community")
    from html_table_rescuer.integrations.langchain import HTMLTableRescuerLoader

    return HTMLTableRescuerLoader


def test_langchain_one_document_per_table(langchain_loader_cls, html_file):
    docs = langchain_loader_cls(str(html_file())).load()
    assert len(docs) == 2
    assert "| Max | 25 |" in docs[0].page_content
    assert "| Berlin |" in docs[1].page_content


def test_langchain_metadata(langchain_loader_cls, html_file):
    f = html_file()
    docs = langchain_loader_cls(str(f)).load()
    assert docs[0].metadata == {
        "source": str(f),
        "table_index": 0,
        "parser": "html_table_rescuer",
    }
    assert docs[1].metadata["table_index"] == 1


def test_langchain_passes_config(langchain_loader_cls, html_file):
    config = ParseConfig(rowspan_strategy=RowspanStrategy.REPEAT_VALUE)
    docs = langchain_loader_cls(str(html_file(ROWSPAN_HTML)), config=config).load()
    assert docs[0].page_content.count("A") == 2
    assert "dito" not in docs[0].page_content


def test_langchain_missing_file_raises(langchain_loader_cls):
    with pytest.raises(RuntimeError):
        langchain_loader_cls("/nonexistent/file.html").load()


def test_langchain_no_tables(langchain_loader_cls, html_file):
    docs = langchain_loader_cls(str(html_file("<p>nix</p>"))).load()
    assert docs == []


# --- LlamaIndex --------------------------------------------------------------


@pytest.fixture
def llamaindex_reader_cls():
    pytest.importorskip("llama_index.core")
    from html_table_rescuer.integrations.llamaindex import HTMLTableRescuerReader

    return HTMLTableRescuerReader


def test_llamaindex_one_document_per_table(llamaindex_reader_cls, html_file):
    docs = llamaindex_reader_cls().load_data(html_file())
    assert len(docs) == 2
    assert "| Max | 25 |" in docs[0].text
    assert "| Berlin |" in docs[1].text


def test_llamaindex_metadata(llamaindex_reader_cls, html_file):
    f = html_file()
    docs = llamaindex_reader_cls().load_data(f)
    assert docs[0].metadata == {
        "source": str(f),
        "table_index": 0,
        "parser": "html_table_rescuer",
    }
    assert docs[1].metadata["table_index"] == 1


def test_llamaindex_extra_info_wins(llamaindex_reader_cls, html_file):
    """SimpleDirectoryReader reicht extra_info durch — das muss Vorrang haben."""
    docs = llamaindex_reader_cls().load_data(
        html_file(), extra_info={"file_name": "tables.html", "parser": "custom"}
    )
    assert docs[0].metadata["file_name"] == "tables.html"
    assert docs[0].metadata["parser"] == "custom"
    assert docs[0].metadata["table_index"] == 0


def test_llamaindex_accepts_str_path(llamaindex_reader_cls, html_file):
    docs = llamaindex_reader_cls().load_data(str(html_file()))
    assert len(docs) == 2


def test_llamaindex_passes_config(llamaindex_reader_cls, html_file):
    config = ParseConfig(rowspan_strategy=RowspanStrategy.REPEAT_VALUE)
    docs = llamaindex_reader_cls(config=config).load_data(html_file(ROWSPAN_HTML))
    assert docs[0].text.count("A") == 2
    assert "dito" not in docs[0].text


def test_llamaindex_lazy_load_is_lazy(llamaindex_reader_cls, html_file):
    gen = llamaindex_reader_cls().lazy_load_data(html_file())
    assert next(iter(gen)).metadata["table_index"] == 0


def test_llamaindex_missing_file_raises(llamaindex_reader_cls):
    with pytest.raises(RuntimeError):
        llamaindex_reader_cls().load_data("/nonexistent/file.html")


def test_llamaindex_no_tables(llamaindex_reader_cls, html_file):
    docs = llamaindex_reader_cls().load_data(html_file("<p>nix</p>"))
    assert docs == []


# --- Haystack ----------------------------------------------------------------


@pytest.fixture
def haystack_converter_cls():
    pytest.importorskip("haystack")
    from html_table_rescuer.integrations.haystack import HTMLTableRescuerConverter

    return HTMLTableRescuerConverter


def test_haystack_one_document_per_table(haystack_converter_cls, html_file):
    result = haystack_converter_cls().run(sources=[html_file()])
    docs = result["documents"]
    assert len(docs) == 2
    assert "| Max | 25 |" in docs[0].content
    assert "| Berlin |" in docs[1].content


def test_haystack_metadata(haystack_converter_cls, html_file):
    f = html_file()
    docs = haystack_converter_cls().run(sources=[f])["documents"]
    assert docs[0].meta["source"] == str(f)
    assert docs[0].meta["parser"] == "html_table_rescuer"
    assert docs[0].meta["table_index"] == 0
    assert docs[1].meta["table_index"] == 1


def test_haystack_meta_dict_applies_to_all(haystack_converter_cls, html_file):
    docs = haystack_converter_cls().run(
        sources=[html_file()], meta={"category": "report"}
    )["documents"]
    assert all(d.meta["category"] == "report" for d in docs)


def test_haystack_meta_list_per_source(haystack_converter_cls, html_file, tmp_path):
    a = tmp_path / "a.html"
    a.write_text("<table><tr><th>A</th></tr><tr><td>1</td></tr></table>", encoding="utf-8")
    b = tmp_path / "b.html"
    b.write_text("<table><tr><th>B</th></tr><tr><td>2</td></tr></table>", encoding="utf-8")

    docs = haystack_converter_cls().run(
        sources=[a, b], meta=[{"doc": "first"}, {"doc": "second"}]
    )["documents"]
    assert [d.meta["doc"] for d in docs] == ["first", "second"]


def test_haystack_user_meta_wins(haystack_converter_cls, html_file):
    docs = haystack_converter_cls().run(
        sources=[html_file()], meta={"parser": "custom"}
    )["documents"]
    assert docs[0].meta["parser"] == "custom"
    assert docs[0].meta["table_index"] == 0


def test_haystack_multiple_sources(haystack_converter_cls, html_file, tmp_path):
    a = tmp_path / "a.html"
    a.write_text("<table><tr><th>A</th></tr><tr><td>1</td></tr></table>", encoding="utf-8")
    docs = haystack_converter_cls().run(sources=[html_file(), a])["documents"]
    # 2 Tabellen aus der ersten Quelle + 1 aus der zweiten
    assert len(docs) == 3


def test_haystack_bytestream_source(haystack_converter_cls):
    from haystack.dataclasses import ByteStream

    stream = ByteStream(data=TWO_TABLES_HTML.encode("utf-8"))
    docs = haystack_converter_cls().run(sources=[stream])["documents"]
    assert len(docs) == 2
    assert docs[0].meta["table_index"] == 0


def test_haystack_bad_source_is_skipped(haystack_converter_cls, html_file, caplog):
    """Haystack-Konvention: defekte Quelle überspringen, Pipeline läuft weiter."""
    docs = haystack_converter_cls().run(
        sources=["/nonexistent/file.html", html_file()]
    )["documents"]
    assert len(docs) == 2
    assert "Skipping" in caplog.text


def test_haystack_passes_config(haystack_converter_cls, html_file):
    config = ParseConfig(rowspan_strategy=RowspanStrategy.REPEAT_VALUE)
    docs = haystack_converter_cls(config=config).run(sources=[html_file(ROWSPAN_HTML)])[
        "documents"
    ]
    assert docs[0].content.count("A") == 2
    assert "dito" not in docs[0].content


def test_haystack_no_tables(haystack_converter_cls, html_file):
    docs = haystack_converter_cls().run(sources=[html_file("<p>nix</p>")])["documents"]
    assert docs == []


def test_haystack_roundtrip_serialization(haystack_converter_cls):
    """Pipelines werden als YAML gespeichert — ParseConfig muss das überleben."""
    config = ParseConfig(rowspan_strategy=RowspanStrategy.EMPTY, dito_prefix="ebenso")
    data = haystack_converter_cls(config=config).to_dict()

    # Muss JSON-/YAML-serialisierbar sein (kein rohes Enum-Objekt)
    assert data["init_parameters"]["config"]["rowspan_strategy"] == "empty"
    json.dumps(data)

    restored = haystack_converter_cls.from_dict(data)
    assert restored.config == config


def test_haystack_roundtrip_without_config(haystack_converter_cls):
    data = haystack_converter_cls().to_dict()
    json.dumps(data)
    assert haystack_converter_cls.from_dict(data).config is None


def test_haystack_runs_in_pipeline(haystack_converter_cls, html_file):
    from haystack import Pipeline

    pipe = Pipeline()
    pipe.add_component("converter", haystack_converter_cls())
    result = pipe.run({"converter": {"sources": [html_file()]}})
    assert len(result["converter"]["documents"]) == 2


# --- Caption in den Metadaten aller Integrationen -----------------------------

CAPTION_HTML = (
    "<table><caption>Quarterly results</caption>"
    "<tr><th>Q</th><th>Revenue</th></tr><tr><td>Q1</td><td>100</td></tr></table>"
)


def test_langchain_exposes_caption(langchain_loader_cls, html_file):
    docs = langchain_loader_cls(str(html_file(CAPTION_HTML))).load()
    assert docs[0].metadata["caption"] == "Quarterly results"


def test_langchain_omits_caption_when_absent(langchain_loader_cls, html_file):
    docs = langchain_loader_cls(str(html_file())).load()
    assert "caption" not in docs[0].metadata


def test_llamaindex_exposes_caption(llamaindex_reader_cls, html_file):
    docs = llamaindex_reader_cls().load_data(html_file(CAPTION_HTML))
    assert docs[0].metadata["caption"] == "Quarterly results"


def test_haystack_exposes_caption(haystack_converter_cls, html_file):
    docs = haystack_converter_cls().run(sources=[html_file(CAPTION_HTML)])["documents"]
    assert docs[0].meta["caption"] == "Quarterly results"
