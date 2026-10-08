"""Keep the translated docs' executable examples and local links intact."""

from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


ROOT = Path(__file__).resolve().parents[1]


class DocsPage(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.language = None
        self.ids = set()
        self.sections = []
        self.code = []
        self.examples = []
        self.table_structure = []
        self.local_links = []
        self._code = None
        self._in_pre = False
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "html":
            self.language = attrs.get("lang")
        if "id" in attrs:
            self.ids.add(attrs["id"])
        if tag == "section":
            self.sections.append(attrs.get("id"))
        if tag in {"table", "tr", "td", "th"}:
            self.table_structure.append((tag, attrs.get("scope")))
        if tag == "code":
            self._code = ""
        if tag == "pre":
            self._in_pre = True
        for name in ("src", "href"):
            if name in attrs:
                link = urlsplit(attrs[name])
                if not link.scheme and not link.netloc:
                    self.local_links.append(link)

    def handle_data(self, data):
        if self._code is not None:
            self._code += data

    def handle_endtag(self, tag):
        if tag == "code":
            self.code.append(self._code)
            if self._in_pre:
                self.examples.append(self._code)
            self._code = None
        if tag == "pre":
            self._in_pre = False


def test_chinese_docs_preserve_examples_sections_and_reference_tables():
    english = DocsPage(ROOT / "docs/index.html")
    chinese = DocsPage(ROOT / "docs/zh/index.html")
    assert english.language == "en"
    assert chinese.language == "zh-CN"
    assert chinese.sections == english.sections
    # Inline technical terms can move with Chinese sentence order.
    assert Counter(chinese.code) == Counter(english.code)
    assert chinese.examples == english.examples
    assert chinese.table_structure == english.table_structure


def test_both_docs_have_valid_local_assets_and_navigation_targets():
    for relative in ("docs/index.html", "docs/zh/index.html"):
        page = DocsPage(ROOT / relative)
        for link in page.local_links:
            if not link.path:
                assert not link.fragment or link.fragment in page.ids
                continue
            target = (page.path.parent / unquote(link.path)).resolve()
            if target.is_dir():
                target /= "index.html"
            assert target.is_file(), f"{relative}: missing {link.geturl()}"
            if link.fragment and target.suffix == ".html":
                assert link.fragment in DocsPage(target).ids
