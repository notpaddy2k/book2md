"""
Core conversion pipeline. Format-agnostic — takes a single Markdown file
plus a media directory and emits chapter notes with frontmatter, image
embeds rewritten for the target vault, and a chapter chain of next-links.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import yaml


@dataclass
class BookMetadata:
    title: str = ""
    authors: list[str] = field(default_factory=list)
    publisher: str = ""
    language: str = ""

    @property
    def author_str(self) -> str:
        return ", ".join(self.authors) if self.authors else ""


@dataclass
class ConvertOptions:
    heading_level: int = 1
    image_style: str = "wikilink"  # or "markdown"
    exclude_patterns: list[str] = field(default_factory=list)
    frontmatter_template_path: Path | None = None


# ----- frontmatter -----

def render_frontmatter(template_yaml: str, meta: BookMetadata) -> str:
    """Substitute placeholders, then re-emit clean YAML.

    `{{author}}` is special-cased to a YAML list regardless of count.
    """
    today = date.today().isoformat()
    substituted = (
        template_yaml
        .replace("{{title}}", _yaml_escape(meta.title))
        .replace("{{author}}", _yaml_escape(meta.author_str))
        .replace("{{publisher}}", _yaml_escape(meta.publisher))
        .replace("{{language}}", _yaml_escape(meta.language))
        .replace("{{date}}", today)
    )
    parsed = yaml.safe_load(substituted) or {}
    if "author" in parsed and isinstance(parsed["author"], str):
        parsed["author"] = meta.authors  # promote to YAML list
    return yaml.safe_dump(parsed, sort_keys=False, allow_unicode=True).strip()


def _yaml_escape(s: str) -> str:
    return s.replace('"', '\\"')


# ----- splitting -----

@dataclass
class Chapter:
    title: str
    body: str  # full markdown including the heading line


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")


def split_chapters(markdown: str, heading_level: int) -> list[Chapter]:
    """Split a single markdown blob at the requested heading level."""
    lines = markdown.splitlines()
    marker = "#" * heading_level + " "
    indices = [i for i, ln in enumerate(lines) if ln.startswith(marker)]
    if not indices:
        return []

    chapters: list[Chapter] = []
    for i, start in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(lines)
        body = "\n".join(lines[start:end]).rstrip() + "\n"
        title = lines[start][heading_level:].lstrip(" #").strip()
        chapters.append(Chapter(title=title, body=body))
    return chapters


def split_chapters_by_pattern(markdown: str, pattern: re.Pattern[str]) -> list[Chapter]:
    """Split a markdown blob at any line matching the regex.

    Useful for messy PDFs where heading levels are unreliable but chapter
    titles share a recognisable shape (e.g. all-caps headings, or numbered
    chapters like 'Chapter 4 ...').

    The matched line is treated as the chapter title; markdown heading
    markers (`#`) are stripped from the extracted title.
    """
    lines = markdown.splitlines()
    indices = [i for i, ln in enumerate(lines) if pattern.match(ln)]
    if not indices:
        return []

    chapters: list[Chapter] = []
    for i, start in enumerate(indices):
        end = indices[i + 1] if i + 1 < len(indices) else len(lines)
        body = "\n".join(lines[start:end]).rstrip() + "\n"
        title = lines[start].lstrip("#").strip()
        chapters.append(Chapter(title=title, body=body))
    return chapters


# Common preset patterns for `--chapter-pattern` shorthand.
CHAPTER_PATTERNS: dict[str, str] = {
    # All-caps heading at any heading level (e.g. ## LIVING A PURPOSEFUL LIFE)
    "caps": r"^#+\s+[A-Z][A-Z0-9\s\-,'’.!?&]+\s*$",
    # "Chapter N ..." or "Chapter N: ..." regardless of heading level
    "numbered": r"^#+\s+(?:Chapter|CHAPTER|Part|PART)\s+\d+",
}


# ----- filtering -----

def apply_excludes(chapters: list[Chapter], patterns: list[str]) -> list[Chapter]:
    """Drop chapters whose title matches any pattern (case-insensitive substring)."""
    if not patterns:
        return chapters
    lowered = [p.lower() for p in patterns]
    kept = []
    for c in chapters:
        if any(p in c.title.lower() for p in lowered):
            continue
        kept.append(c)
    return kept


# ----- image rewriting -----

# Pandoc emits ![](path/to/image.ext) — possibly with absolute paths
PANDOC_IMG_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<path>[^)]+)\)")


def rewrite_images(
    markdown: str,
    image_style: str,
    media_src: Path,
    media_dst: Path,
) -> tuple[str, list[Path]]:
    """Move images from media_src into media_dst (flat) and rewrite references.

    Returns (new_markdown, list of copied filenames).
    """
    media_dst.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []

    def replace(match: re.Match) -> str:
        alt = match.group("alt")
        raw_path = match.group("path")
        # Pandoc paths are relative to the media dir or absolute.
        src = (media_src / raw_path) if not Path(raw_path).is_absolute() else Path(raw_path)
        if not src.exists():
            # Try a flatter resolution: the filename only
            candidate = media_src.rglob(Path(raw_path).name)
            for c in candidate:
                src = c
                break
        if not src.exists():
            return match.group(0)  # leave as-is

        dst = media_dst / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
            copied.append(dst)
        if image_style == "wikilink":
            return f"![[{src.name}]]"
        return f"![{alt}]({dst.name})"

    new_md = PANDOC_IMG_RE.sub(replace, markdown)
    return new_md, copied


# ----- chapter chain -----

def append_next_links(chapters: list[Chapter]) -> list[Chapter]:
    """Append a 'Next chapter' wikilink to each chapter except the last."""
    if not chapters:
        return chapters
    out: list[Chapter] = []
    for i, c in enumerate(chapters):
        if i + 1 < len(chapters):
            next_title = chapters[i + 1].title
            footer = f"\n---\n\n> [!info] Next chapter\n> [[{_safe_filename(next_title)}]]\n"
            new_body = c.body.rstrip() + footer
        else:
            new_body = c.body
        out.append(Chapter(title=c.title, body=new_body))
    return out


# ----- writing -----

ILLEGAL_FN_CHARS = re.compile(r'[\\/*?:"<>|]')


def _safe_filename(title: str) -> str:
    return ILLEGAL_FN_CHARS.sub("", title).strip()


def write_chapter_notes(
    chapters: list[Chapter],
    out_dir: Path,
    frontmatter: str,
) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for c in chapters:
        path = out_dir / f"{_safe_filename(c.title)}.md"
        content = f"---\n{frontmatter}\n---\n\n{c.body}"
        path.write_text(content, encoding="utf-8")
        written.append(path)
    return written
