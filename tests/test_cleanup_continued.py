"""Test output cleanup for continued generation."""

from lorebook.workflow.text import _clean_continued_output


def test_clean_continued_removes_continued_markers() -> None:
    """Verify (Continued) markers are removed."""
    text = "Some content\n\n## Section 1 (Continued)\n\nMore content"
    result = _clean_continued_output(text)
    assert "(Continued)" not in result
    assert "Some content" in result
    assert "## Section 1" in result


def test_clean_continued_fixes_mashed_headers() -> None:
    """Verify headers mashed together with text are separated."""
    text = "A sailor may attempt to bond## World Rules\n\n### Subsection"
    result = _clean_continued_output(text)
    # Should have newlines before the header
    assert "bond\n" in result
    assert "## World Rules" in result


def test_clean_continued_removes_duplicate_headers() -> None:
    """Verify duplicate headers are removed."""
    text = "## World Rules\n\nContent about world\n\n## World Rules\n\nMore content"
    result = _clean_continued_output(text)
    # Count occurrences of the header
    count = result.count("## World Rules")
    assert count == 1
    assert "Content about world" in result


def test_clean_continued_with_realistic_example() -> None:
    """Test with realistic continued output pattern."""
    text = """## World Rules

### 1. The Bond of Light and Salt
Each lighthouse is a living entity that forms an unbreakable symbiotic bond with exactly one sailor.

A sailor may attempt to bond## World Rules (Continued)

#### 1. The Bond of Light and Salt (Continued)

A sailor may attempt to bond with a new lighthouse only if their current lighthouse"""
    
    result = _clean_continued_output(text)
    
    # Should not have (Continued) markers
    assert "(Continued)" not in result
    
    # Should not have duplicate main headers
    assert result.count("## World Rules") == 1
    
    # Should have cleaned text
    assert "Each lighthouse is a living entity" in result
    assert "A sailor may attempt to bond" in result


def test_clean_continued_preserves_legitimate_duplicates() -> None:
    """Verify we only remove exact duplicate headers, not similar ones."""
    text = "## Background\n\nText\n\n## Background Story\n\nMore text"
    result = _clean_continued_output(text)
    
    # Both should remain since they're different
    assert "## Background" in result
    assert "## Background Story" in result


def test_clean_continued_handles_empty_input() -> None:
    """Verify empty/None input is handled gracefully."""
    assert _clean_continued_output("") == ""
    assert _clean_continued_output(None) == ""


def test_clean_continued_normalizes_excessive_newlines() -> None:
    """Verify excessive blank lines are reduced."""
    text = "Line 1\n\n\n\n\n\nLine 2"
    result = _clean_continued_output(text)
    
    # Should have max 3 newlines (2 blank lines between content)
    assert "\n\n\n\n" not in result
    assert "Line 1" in result
    assert "Line 2" in result
