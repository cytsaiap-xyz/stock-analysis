from committee.markdown import split_thinking


def test_no_tags_returns_text_as_answer():
    assert split_thinking("just an answer") == ("just an answer", "")


def test_extracts_thought_block():
    a, t = split_thinking("<thought>reasoning here</thought>The answer.")
    assert a == "The answer."
    assert t == "reasoning here"


def test_extracts_think_block_case_insensitive():
    a, t = split_thinking("<THINK>r</THINK>ans")
    assert a == "ans" and t == "r"


def test_multiple_blocks_joined():
    a, t = split_thinking("<thought>one</thought>mid<thought>two</thought>end")
    assert a == "midend"
    assert t == "one\n\ntwo"


def test_unclosed_trailing_open_tag_is_thinking():
    a, t = split_thinking("answer text <thought>truncated reasoning")
    assert a == "answer text"
    assert t == "truncated reasoning"


def test_empty_input():
    assert split_thinking("") == ("", "")
    assert split_thinking(None) == ("", "")


from committee.markdown import render_markdown


def test_escapes_html():
    out = render_markdown("<script>alert(1)</script>")
    assert "<script>" not in out and "&lt;script&gt;" in out


def test_bold_italic_code():
    out = render_markdown("a **b** c *d* e `f`")
    assert "<strong>b</strong>" in out
    assert "<em>d</em>" in out
    assert "<code>f</code>" in out


def test_unordered_list():
    out = render_markdown("- one\n- two")
    assert out == "<ul><li>one</li><li>two</li></ul>"


def test_ordered_list():
    out = render_markdown("1. one\n2. two")
    assert out == "<ol><li>one</li><li>two</li></ol>"


def test_heading():
    assert render_markdown("# Title") == "<h3>Title</h3>"
    assert render_markdown("## Sub") == "<h4>Sub</h4>"


def test_paragraph_and_linebreak():
    assert render_markdown("a\nb") == "<p>a<br>b</p>"
    assert render_markdown("a\n\nb") == "<p>a</p><p>b</p>"


def test_fenced_code_block_keeps_content_literal():
    out = render_markdown("```\nx = **not bold**\n```")
    assert out == "<pre><code>x = **not bold**</code></pre>"


def test_http_link_rendered_other_schemes_literal():
    assert '<a href="https://x.com" target="_blank" rel="noopener">t</a>' in render_markdown("[t](https://x.com)")
    assert render_markdown("[t](javascript:alert(1))") == "<p>[t](javascript:alert(1))</p>"


def test_snake_case_not_italicized():
    assert render_markdown("get_monthly_revenue") == "<p>get_monthly_revenue</p>"


def test_render_inline_renders_bold_without_block_wrapper():
    from committee.markdown import render_inline
    assert render_inline("Recommendation: **BUY**") == "Recommendation: <strong>BUY</strong>"


def test_render_inline_escapes_html():
    from committee.markdown import render_inline
    assert render_inline("<b>x</b>") == "&lt;b&gt;x&lt;/b&gt;"
