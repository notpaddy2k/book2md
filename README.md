# book2md

Convert EPUB and PDF books into clean Markdown chapters with frontmatter.

A thin Python wrapper around Pandoc that:

1. Converts the book to a single Markdown file (extracting media).
2. Splits at a configurable heading level into per-chapter notes.
3. Prepends YAML frontmatter from a template (with EPUB metadata auto-filled).
4. Rewrites image paths to Obsidian-style `![[name]]` embeds (configurable).
5. Adds a "next chapter" wikilink to each note, building the chain.
6. Filters book matter (Copyright, inside covers, etc.) you don't want as notes.

Designed to drop output cleanly into an Obsidian vault, but the markdown is generic.

## Status

- **v0.1** — File adapter (EPUB/PDF via Pandoc). Working.
- **v0.2** (planned) — Scan adapter (Meta Glasses page photos → OCR → Markdown).

## Install

```bash
git clone https://github.com/simphani2k/book2md.git
cd book2md
pip install -e .
```

You also need [Pandoc](https://pandoc.org/installing.html) on your PATH.

## Use

```bash
book2md convert path/to/book.epub --out ./output
```

Common options:

```
--heading-level N      Split at H1 (default), H2, etc.
--frontmatter PATH     YAML template (default: built-in Obsidian Book Template)
--exclude PATTERN      Drop notes whose title matches (repeatable)
--image-style STYLE    "wikilink" (default) or "markdown"
--attachments-dir PATH Where to put extracted images (default: <out>/attachments)
```

Run `book2md --help` for the full reference.

## Frontmatter template

Variables filled in from the EPUB metadata:

- `{{title}}` — book title
- `{{author}}` — author (single string or list)
- `{{language}}`
- `{{publisher}}`
- `{{date}}` — today's date

The default template matches an Obsidian "Book Template" with `categories: [[Books]]` and chapter-friendly tags.

## License

MIT
