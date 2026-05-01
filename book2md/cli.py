"""
CLI entry point.

    book2md convert <book.epub> --out <dir> [options]
"""
from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from book2md import __version__
from book2md.adapters.file import convert_to_markdown, read_metadata
from book2md.core import (
    ConvertOptions,
    apply_excludes,
    append_next_links,
    render_frontmatter,
    rewrite_images,
    split_chapters,
    write_chapter_notes,
)


DEFAULT_TEMPLATE = Path(__file__).parent / "templates" / "book.yml"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="book2md", description="Convert EPUB/PDF books to Markdown chapters.")
    p.add_argument("--version", action="version", version=f"book2md {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    conv = sub.add_parser("convert", help="Convert a book file to Markdown chapters.")
    conv.add_argument("book", type=Path, help="Path to the EPUB or PDF.")
    conv.add_argument("--out", type=Path, required=True, help="Output directory for chapter notes.")
    conv.add_argument(
        "--attachments-dir",
        type=Path,
        default=None,
        help="Where to put extracted images. Default: <out>/attachments.",
    )
    conv.add_argument("--heading-level", type=int, default=1, help="Heading level to split on (default 1).")
    conv.add_argument(
        "--frontmatter",
        type=Path,
        default=DEFAULT_TEMPLATE,
        help="YAML frontmatter template file.",
    )
    conv.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Drop chapters whose title contains this string (case-insensitive). Repeatable.",
    )
    conv.add_argument(
        "--image-style",
        choices=["wikilink", "markdown"],
        default="wikilink",
        help="How to render image references in chapter notes.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "convert":
        return run_convert(args)
    return 1


def run_convert(args: argparse.Namespace) -> int:
    book: Path = args.book
    if not book.exists():
        print(f"error: {book} does not exist", file=sys.stderr)
        return 2

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    attachments_dir: Path = args.attachments_dir or (out_dir / "attachments")

    template_yaml = args.frontmatter.read_text(encoding="utf-8")

    print(f"[1/5] Pandoc: {book.name} -> Markdown")
    with tempfile.TemporaryDirectory() as tmp:
        work_dir = Path(tmp)
        md_path, media_dir = convert_to_markdown(book, work_dir)
        meta = read_metadata(book)
        if not meta.title:
            meta.title = book.stem.replace("_", " ")

        markdown = md_path.read_text(encoding="utf-8")

        print(f"[2/5] Splitting at H{args.heading_level}")
        chapters = split_chapters(markdown, args.heading_level)
        if not chapters:
            print(f"error: no headings of level {args.heading_level} found", file=sys.stderr)
            return 3

        if args.exclude:
            before = len(chapters)
            chapters = apply_excludes(chapters, args.exclude)
            print(f"[3/5] Dropped {before - len(chapters)} excluded chapter(s)")
        else:
            print("[3/5] No excludes")

        print("[4/5] Rewriting image paths")
        rewritten = []
        for c in chapters:
            new_body, _ = rewrite_images(c.body, args.image_style, media_dir, attachments_dir)
            rewritten.append(type(c)(title=c.title, body=new_body))
        chapters = rewritten

        chapters = append_next_links(chapters)

        frontmatter = render_frontmatter(template_yaml, meta)

        print(f"[5/5] Writing {len(chapters)} chapter note(s) to {out_dir}")
        written = write_chapter_notes(chapters, out_dir, frontmatter)

    print(f"\nDone. {len(written)} notes -> {out_dir}, attachments -> {attachments_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
