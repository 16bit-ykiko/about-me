class Node:
    def __str__(self) -> str:
        raise NotImplementedError


class Paragraph(Node):
    """Represents a paragraph in a markdown document."""

    def __init__(self, children: list[Node]):
        assert isinstance(children, list), "Children must be a list"

        self.children = children

    def __str__(self) -> str:
        return "".join(str(child) for child in self.children)


class Text(Node):
    """Represents a text node in a markdown document."""

    def __init__(self, text: str):
        assert isinstance(text, str), "Text must be a string"

        self.text = text

    def __str__(self) -> str:
        return self.text


class Emphasis(Node):
    """Represents an emphasis in a markdown document. Syntax: *text*."""

    def __init__(self, text: str):
        assert isinstance(text, str), "Child must be a Node"

        self.text = text

    def __str__(self) -> str:
        return f"*{self.text}* "


class Strong(Node):
    """Represents a strong emphasis in a markdown document. Syntax: **text**."""

    def __init__(self, text: str):
        assert isinstance(text, str), "Text must be a string"

        self.text = text

    def __str__(self) -> str:
        return f"**{self.text}**"


class Link(Node):
    """Represents a hyperlink in a markdown document. Syntax: [label](url)."""

    def __init__(self, label: str, url: str):
        assert isinstance(label, str), "Label must be a string"
        assert isinstance(url, str), "URL must be a string"

        self.label = label
        self.url = url

    def __str__(self) -> str:
        return f"[{self.label}]({self.url})"


class Image(Node):
    """Represents an image in a markdown document. Syntax: ![label](url)."""

    def __init__(self, label: str, url: str):
        assert isinstance(label, str), "Label must be a string"
        assert isinstance(url, str), "URL must be a string"

        self.label = label
        self.url = url

    def __str__(self) -> str:
        return f"![{self.label}]({self.url})"


class InlineCode(Node):
    """Represents inline code in a markdown document. Syntax: `code`."""

    def __init__(self, code: str):
        assert isinstance(code, str), "Code must be a string"

        self.code = code

    def __str__(self) -> str:
        return f"`{self.code}`"


class BlockCode(Node):
    """Represents a block of code in a markdown document. Syntax: ```language code```."""

    def __init__(self, code: str, language: str):
        assert isinstance(code, str), "Code must be a string"
        assert isinstance(language, str), "Language must be a string"

        self.code = code
        self.language = language

    def __str__(self) -> str:
        return f"```{self.language}\n{self.code}\n```"


class Header(Node):
    """Represents a header in a markdown document. Syntax: # text."""

    def __init__(self, level: int, text: str):
        assert isinstance(level, int), "Level must be an integer"
        assert isinstance(text, str), "Text must be a string"

        self.level = level
        self.text = text

    def __str__(self) -> str:
        return f"{'#' * self.level} {self.text} "


class List(Node):
    """Represents a list in a markdown document. Syntax: \n - item1 \n - item2."""

    def __init__(self, ordered: bool, items: list[Node]):
        assert items, "List must have at least one item"
        assert isinstance(ordered, bool), "Ordered must be a boolean"
        assert isinstance(items, list), "Items must be a list"

        self.ordered = ordered
        self.items = items

    def __str__(self, depth=0) -> str:
        result = ""
        indent = "  " * depth
        for index, item in enumerate(self.items):
            prefix = f"{index + 1}. " if self.ordered else "- "
            text = item.__str__(
                depth + 1) if isinstance(item, List) else str(item)
            result += f"{indent}{prefix}{text}\n"
        return result


class BlockQuote(Node):
    """Represents a block quote in a markdown document. Syntax: > text."""

    def __init__(self, children: Paragraph):
        assert isinstance(children, Paragraph), "Children must be a Paragraph"

        self.children = children

    def __str__(self) -> str:
        return f"> {self.children} "


class HorizontalRule(Node):
    """Represents a horizontal rule in a markdown document. Syntax: ---."""

    def __init__(self):
        pass

    def __str__(self) -> str:
        return "---"


class NewLine(Node):
    """Represents a new line in a markdown document. Syntax: <br>."""

    def __init__(self):
        pass

    def __str__(self) -> str:
        return "<br>"


# markdown extension, see that https://blowfish.page/zh-cn/docs/shortcodes/#article
class LinkCard(Node):
    """Represents a link card in a markdown document. Syntax: [label](url)"""

    def __init__(self, label: str, url: str):
        assert isinstance(label, str), "Label must be a string"
        assert isinstance(url, str), "URL must be a string"

        self.label = label
        self.url = url

    def __str__(self) -> str:
        return '{{< article link="' + self.url + '" >}}'


class Document:
    """Represents a markdown document."""

    def __init__(self, children: list[Node]):
        assert isinstance(children, list), "Children must be a list"

        self.children = children

    def format(self):
        pass

    def dump(self):
        return '\n\n'.join(str(child) for child in self.children)
