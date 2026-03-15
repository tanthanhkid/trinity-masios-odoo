"""Unit tests for agent.py helper functions: _quick_reply, _trim_history, _extract_pdf, _pdf_summary, _mcp_tools_to_openai."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from agent import MasiAgent, _extract_pdf, _pdf_summary, _mcp_tools_to_openai


class TestQuickReply:
    def test_ok(self):
        assert MasiAgent._quick_reply("ok") is not None

    def test_ok_cam_on(self):
        assert MasiAgent._quick_reply("ok cảm ơn") is not None

    def test_thanks(self):
        assert MasiAgent._quick_reply("thanks") is not None

    def test_cam_on(self):
        assert MasiAgent._quick_reply("cảm ơn") is not None

    def test_duoc_roi(self):
        assert MasiAgent._quick_reply("được rồi") is not None

    def test_bye(self):
        assert MasiAgent._quick_reply("bye") is not None

    def test_good(self):
        assert MasiAgent._quick_reply("good") is not None

    def test_noted(self):
        assert MasiAgent._quick_reply("ghi nhận") is not None

    def test_xong(self):
        assert MasiAgent._quick_reply("xong") is not None

    def test_ok_xong(self):
        assert MasiAgent._quick_reply("ok xong") is not None

    def test_not_quick_normal_message(self):
        assert MasiAgent._quick_reply("cho tôi xem doanh số") is None

    def test_not_quick_command(self):
        assert MasiAgent._quick_reply("/kpi") is None

    def test_not_quick_number(self):
        assert MasiAgent._quick_reply("123") is None

    def test_case_insensitive(self):
        assert MasiAgent._quick_reply("OK") is not None

    def test_with_punctuation(self):
        assert MasiAgent._quick_reply("ok!") is not None

    def test_long_message_with_cam_on_still_matches(self):
        # "cảm ơn" pattern uses .* so longer messages still match
        assert MasiAgent._quick_reply("cảm ơn bạn rất nhiều vì đã giúp đỡ tôi hôm nay") is not None

    def test_long_unrelated_message_not_quick(self):
        assert MasiAgent._quick_reply("cho tôi xem báo cáo doanh thu tháng này đi") is None


class TestTrimHistory:
    def test_short_history_unchanged(self):
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(5)]
        result = MasiAgent._trim_history(msgs, keep=8)
        assert len(result) == 5

    def test_exact_boundary(self):
        msgs = [{"role": "user", "content": f"msg{i}"} for i in range(10)]
        result = MasiAgent._trim_history(msgs, keep=8)
        assert len(result) == 10  # 10 == 8+2, no trimming

    def test_long_history_trimmed(self):
        msgs = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"msg{i}"}
                for i in range(20)]
        result = MasiAgent._trim_history(msgs, keep=8)
        # Should have anchor (first 2) + last 8 = 10
        assert len(result) <= 10
        # First message preserved
        assert result[0]["content"] == "msg0"

    def test_starts_with_user(self):
        msgs = [
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "hello"},
        ] + [{"role": "user", "content": f"msg{i}"} for i in range(15)]
        result = MasiAgent._trim_history(msgs, keep=5)
        assert result[0]["role"] == "user"

    def test_empty_history(self):
        result = MasiAgent._trim_history([], keep=8)
        assert result == []


class TestExtractPdf:
    def test_direct_pdf(self):
        data = json.dumps({"pdf_base64": "abc123", "filename": "test.pdf"})
        result = _extract_pdf(data)
        assert result is not None
        assert result["pdf_base64"] == "abc123"

    def test_wrapped_pdf(self):
        inner = json.dumps({"pdf_base64": "abc123", "filename": "test.pdf"})
        data = json.dumps({"result": inner})
        result = _extract_pdf(data)
        assert result is not None
        assert result["pdf_base64"] == "abc123"

    def test_no_pdf(self):
        assert _extract_pdf('{"name": "test"}') is None

    def test_invalid_json(self):
        assert _extract_pdf("not json") is None

    def test_none_input(self):
        assert _extract_pdf(None) is None

    def test_dict_input(self):
        result = _extract_pdf({"pdf_base64": "xyz", "filename": "a.pdf"})
        assert result is not None
        assert result["pdf_base64"] == "xyz"


class TestPdfSummary:
    def test_basic(self):
        pdf = {"pdf_base64": "huge_data", "filename": "SO001.pdf",
               "size_bytes": 1024, "order_name": "S00001",
               "partner": "ABC", "amount_total": 5000000}
        result = _pdf_summary(pdf)
        parsed = json.loads(result)
        assert parsed["status"] == "pdf_generated"
        assert parsed["filename"] == "SO001.pdf"
        assert "pdf_base64" not in parsed  # Must NOT include base64

    def test_missing_keys(self):
        result = _pdf_summary({})
        parsed = json.loads(result)
        assert parsed["filename"] == "document.pdf"  # default


class TestMcpToolsToOpenai:
    def test_basic_conversion(self):
        mcp_tools = [{
            "name": "odoo_search_read",
            "description": "Search records",
            "input_schema": {
                "type": "object",
                "properties": {"model": {"type": "string"}},
                "required": ["model"],
            },
        }]
        result = _mcp_tools_to_openai(mcp_tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "odoo_search_read"
        assert result[0]["function"]["parameters"]["type"] == "object"

    def test_missing_schema(self):
        mcp_tools = [{"name": "test_tool", "description": "test"}]
        result = _mcp_tools_to_openai(mcp_tools)
        assert result[0]["function"]["parameters"]["type"] == "object"

    def test_empty_list(self):
        assert _mcp_tools_to_openai([]) == []

    def test_multiple_tools(self):
        tools = [
            {"name": f"tool_{i}", "description": f"desc {i}", "input_schema": {"type": "object", "properties": {}}}
            for i in range(5)
        ]
        result = _mcp_tools_to_openai(tools)
        assert len(result) == 5
        assert all(t["type"] == "function" for t in result)
