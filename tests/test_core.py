from datetime import date

import pytest

from book2md.core import (
    BookMetadata,
    Chapter,
    apply_excludes,
    append_next_links,
    render_frontmatter,
    split_chapters,
)


def test_split_chapters_at_h1():
    md = "# One\n\nfirst\n\n# Two\n\nsecond\n\n## Two-A\n\nstill two\n"
    chapters = split_chapters(md, heading_level=1)
    assert [c.title for c in chapters] == ["One", "Two"]
    assert "still two" in chapters[1].body


def test_split_chapters_at_h2():
    md = "# Book\n\n## Chapter 1\n\na\n\n## Chapter 2\n\nb\n"
    chapters = split_chapters(md, heading_level=2)
    assert [c.title for c in chapters] == ["Chapter 1", "Chapter 2"]


def test_split_chapters_no_headings():
    assert split_chapters("just text", 1) == []


def test_apply_excludes_case_insensitive():
    chapters = [Chapter("Copyright", ""), Chapter("Chapter 1", "")]
    kept = apply_excludes(chapters, ["copyright"])
    assert [c.title for c in kept] == ["Chapter 1"]


def test_apply_excludes_no_patterns():
    chapters = [Chapter("Anything", "")]
    assert apply_excludes(chapters, []) == chapters


def test_append_next_links_chains_in_order():
    chapters = [Chapter("A", "# A\n"), Chapter("B", "# B\n"), Chapter("C", "# C\n")]
    chained = append_next_links(chapters)
    assert "[[B]]" in chained[0].body
    assert "[[C]]" in chained[1].body
    assert "Next chapter" not in chained[2].body  # last chapter has no next


def test_render_frontmatter_promotes_author_to_list():
    template = 'book: "{{title}}"\nauthor: "{{author}}"\n'
    meta = BookMetadata(title="The Book", authors=["Jane", "John"])
    rendered = render_frontmatter(template, meta)
    assert "book: The Book" in rendered
    # Author should be a YAML list, not a string
    assert "- Jane" in rendered
    assert "- John" in rendered


def test_render_frontmatter_fills_date():
    template = 'created: "{{date}}"\n'
    meta = BookMetadata()
    rendered = render_frontmatter(template, meta)
    assert date.today().isoformat() in rendered
