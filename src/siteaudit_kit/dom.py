"""A bounded source tree, not a browser DOM or an accessibility implementation."""

from dataclasses import dataclass, field
from html.parser import HTMLParser
from html import escape

VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
INERT = frozenset({"template", "script", "style", "noscript"})


@dataclass(eq=False)
class Node:
    tag: str
    attrs: dict[str, str]
    line: int
    parent: "Node | None" = None
    children: list["Node | str"] = field(default_factory=list)

    def walk(self, *, active_only: bool = True):
        stack = [self]
        while stack:
            node = stack.pop()
            if active_only and node.tag in {"template", "noscript"}:
                continue
            yield node
            stack.extend(reversed([c for c in node.children if isinstance(c, Node)]))

    def text(self, *, include_hidden: bool = False) -> str:
        parts = []
        stack = [self]
        while stack:
            child = stack.pop()
            if isinstance(child, str):
                parts.append(child)
                continue
            if child.tag in INERT:
                continue
            if not include_hidden and (
                "hidden" in child.attrs or child.attrs.get("aria-hidden", "").lower() == "true"
            ):
                continue
            if child.tag == "img":
                parts.append(child.attrs.get("alt", ""))
            stack.extend(reversed(child.children))
        return " ".join(" ".join(parts).split())

    def has_ancestor(self, tag: str) -> bool:
        node = self.parent
        while node:
            if node.tag == tag:
                return True
            node = node.parent
        return False

    def is_hidden(self) -> bool:
        node = self
        while node:
            if "hidden" in node.attrs or node.attrs.get("aria-hidden", "").lower() == "true":
                return True
            node = node.parent
        return False

    def evidence(self) -> str:
        attributes = " ".join(f'{k}="{escape(v, quote=True)}"' for k, v in sorted(self.attrs.items()))
        return (f"<{self.tag}{' ' if attributes else ''}{attributes}>" + self.text()[:80])[:240]


class Document(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=True)
        self.root = Node("#document", {}, 1)
        self.stack = [self.root]
        self.count = 0
        self.feed(source)
        self.close()
        self.nodes = list(self.root.walk())[1:]
        self.ids = {}
        self.labels = set()
        for node in self.nodes:
            if node.attrs.get("id"):
                self.ids.setdefault(node.attrs["id"], node)
            if node.tag == "label" and node.attrs.get("for") and node.text():
                self.labels.add(node.attrs["for"])

    def handle_starttag(self, tag, attrs):
        self.count += 1
        if self.count > 100_000 or len(self.stack) > 512:
            raise ValueError("HTML exceeds parser node or nesting limit")
        # Basic optional-end-tag recovery for common generated/static documents.
        if tag in {"li", "p", "dt", "dd", "option"} and self.stack[-1].tag == tag:
            self.stack.pop()
        node = Node(tag, {k: v or "" for k, v in attrs}, self.getpos()[0], self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)

    def named(self, node: Node) -> str:
        references = node.attrs.get("aria-labelledby", "").split()
        if references:
            name = " ".join(self.ids[r].text(include_hidden=True) for r in references if r in self.ids)
            if name.strip():
                return name.strip()
        if node.attrs.get("aria-label", "").strip():
            return node.attrs["aria-label"].strip()
        if node.tag == "input":
            kind = node.attrs.get("type", "text").lower()
            if kind == "image":
                return node.attrs.get("alt", "").strip()
            if kind in {"submit", "reset"}:
                return node.attrs.get("value", "Submit" if kind == "submit" else "Reset").strip()
            if kind == "button":
                return node.attrs.get("value", "").strip()
        name = node.text() if node.tag in {"button", "a"} else ""
        return name or node.attrs.get("title", "").strip()

    def labelled_control(self, node: Node) -> bool:
        if self.named(node):
            return True
        ident = node.attrs.get("id")
        if ident and ident in self.labels:
            return True
        parent = node.parent
        while parent:
            if parent.tag == "label" and parent.text():
                return True
            parent = parent.parent
        return False
