from app.extract import fix_visual_hebrew, looks_reversed


def test_reversed_hebrew_line_is_fixed():
    logical = "כהן, ד. (2020). השפעת הלמידה מרחוק. Journal of X, 55(2)"
    # Simulate a visually-ordered extraction: whole line reversed, Latin/number runs kept readable.
    import re
    visual = re.sub(r"[\x00-\x7F]+", lambda m: m.group(0)[::-1], logical[::-1])
    assert looks_reversed(visual)
    assert fix_visual_hebrew(visual) == logical


def test_correct_hebrew_and_english_untouched():
    for line in ["כהן, ד. (2020). השפעת הלמידה מרחוק.", "Cohen, J. (1988). Power analysis."]:
        assert fix_visual_hebrew(line) == line
