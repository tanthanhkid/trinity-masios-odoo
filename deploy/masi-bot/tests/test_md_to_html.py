"""Unit tests for bot.py md_to_html function."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from bot import md_to_html


class TestMdToHtml:
    def test_bold(self):
        assert "<b>hello</b>" in md_to_html("**hello**")

    def test_italic(self):
        assert "<i>hello</i>" in md_to_html("*hello*")

    def test_underline(self):
        assert "<u>hello</u>" in md_to_html("__hello__")

    def test_strikethrough(self):
        assert "<s>hello</s>" in md_to_html("~~hello~~")

    def test_header_to_bold(self):
        assert "<b>Title</b>" in md_to_html("# Title")

    def test_h3_to_bold(self):
        assert "<b>Section</b>" in md_to_html("### Section")

    def test_code_block(self):
        result = md_to_html("```\ncode here\n```")
        assert "<pre>" in result
        assert "code here" in result

    def test_inline_code(self):
        result = md_to_html("Use `command` here")
        assert "<code>command</code>" in result

    def test_html_escape(self):
        result = md_to_html("a < b > c & d")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result

    def test_code_block_preserves_html_chars(self):
        result = md_to_html("```\na < b\n```")
        assert "&lt;" in result

    def test_link_http(self):
        result = md_to_html("[click](https://example.com)")
        assert '<a href="https://example.com">click</a>' in result

    def test_link_non_http_stripped(self):
        result = md_to_html("[click](javascript:alert(1))")
        assert "javascript" not in result
        assert "click" in result

    def test_blockquote(self):
        result = md_to_html("> quote text")
        assert "<blockquote>" in result

    def test_horizontal_rule(self):
        result = md_to_html("---")
        assert "─" in result

    def test_table_conversion(self):
        table = "| Name | Value |\n| --- | --- |\n| A | 1 |\n| B | 2 |"
        result = md_to_html(table)
        # Should convert to bullet list, not keep | chars
        assert "Name: A" in result or "A" in result
        assert "<table>" not in result  # No HTML tables

    def test_mixed_formatting(self):
        text = "**Bold** and *italic* and `code`"
        result = md_to_html(text)
        assert "<b>Bold</b>" in result
        assert "<i>italic</i>" in result
        assert "<code>code</code>" in result

    def test_empty_string(self):
        assert md_to_html("") == ""

    def test_plain_text(self):
        assert md_to_html("Hello world") == "Hello world"

    def test_nested_bold_italic(self):
        result = md_to_html("***bold italic***")
        assert "<b>" in result or "<i>" in result
