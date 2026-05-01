"""
File adapter: convert an EPUB or PDF into a single Markdown file plus a
media directory using Pandoc, then extract metadata.
"""
from __future__ import annotations

import shutil
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from book2md.core import BookMetadata


PANDOC = shutil.which("pandoc")


def require_pandoc() -> None:
    if PANDOC is None:
        raise RuntimeError(
            "pandoc is not on PATH. Install it (https://pandoc.org/installing.html)."
        )


def convert_to_markdown(book_path: Path, work_dir: Path) -> tuple[Path, Path]:
    """Run Pandoc to produce a single Markdown file + media directory.

    Returns (markdown_path, media_dir).
    """
    require_pandoc()
    work_dir.mkdir(parents=True, exist_ok=True)
    media_dir = work_dir / "media"
    md_path = work_dir / "full.md"

    cmd = [
        PANDOC,
        "-t", "gfm-raw_html",
        "--wrap=none",
        f"--extract-media={media_dir}",
        "-s", str(book_path),
        "-o", str(md_path),
    ]
    subprocess.run(cmd, check=True)
    return md_path, media_dir


def read_epub_metadata(epub_path: Path) -> BookMetadata:
    """Parse OPF metadata from an EPUB without external deps."""
    meta = BookMetadata()
    try:
        with zipfile.ZipFile(epub_path) as z:
            opf_path = _find_opf(z)
            if not opf_path:
                return meta
            opf_xml = z.read(opf_path).decode("utf-8", errors="replace")
        root = ET.fromstring(opf_xml)
        ns = {
            "opf": "http://www.idpf.org/2007/opf",
            "dc": "http://purl.org/dc/elements/1.1/",
        }
        title = root.find(".//dc:title", ns)
        if title is not None and title.text:
            meta.title = title.text.strip()
        for creator in root.findall(".//dc:creator", ns):
            if creator.text:
                meta.authors.append(creator.text.strip())
        publisher = root.find(".//dc:publisher", ns)
        if publisher is not None and publisher.text:
            meta.publisher = publisher.text.strip()
        language = root.find(".//dc:language", ns)
        if language is not None and language.text:
            meta.language = language.text.strip()
    except (zipfile.BadZipFile, ET.ParseError, OSError):
        pass
    return meta


def _find_opf(z: zipfile.ZipFile) -> str | None:
    """Locate the OPF file inside an EPUB via META-INF/container.xml."""
    try:
        container_xml = z.read("META-INF/container.xml").decode("utf-8", errors="replace")
    except KeyError:
        return None
    root = ET.fromstring(container_xml)
    ns = {"c": "urn:oasis:names:tc:opendocument:xmlns:container"}
    rootfile = root.find(".//c:rootfile", ns)
    if rootfile is None:
        return None
    return rootfile.get("full-path")


def read_metadata(book_path: Path) -> BookMetadata:
    """Dispatch by extension. PDFs return mostly-empty metadata for now."""
    suffix = book_path.suffix.lower()
    if suffix == ".epub":
        return read_epub_metadata(book_path)
    # PDF metadata via pikepdf or pdfminer would go here in v0.2+
    return BookMetadata(title=book_path.stem.replace("_", " "))
