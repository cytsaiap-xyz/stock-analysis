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
