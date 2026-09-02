#!/usr/bin/env python3
"""Build handbook PDFs and sync TOC page ranges to the real PDF pagination."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent.parent
PDF_DIR = ROOT / "pdf"
CSS = ROOT / "scripts" / "pdf-style.css"
CHAPTER_NAME_RE = re.compile(r"chapter-(\d+)", re.I)
CHAPTER_HEADING_RE = re.compile(r"^#\s+(Chapter\s+\d+:\s+.+)$", re.M)
PAGES_ITALIC_RE = re.compile(r"^\*.*Pages?\s+\d+.*\*\s*$", re.M)
ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


@dataclass
class Chapter:
    number: int
    path: Path
    title: str
    heading: str


def chapter_files(handbook_dir: Path) -> list[Chapter]:
    files = sorted(
        handbook_dir.rglob("chapter-*.md"),
        key=lambda p: int(CHAPTER_NAME_RE.search(p.name).group(1)),
    )
    chapters: list[Chapter] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        match = CHAPTER_HEADING_RE.search(text)
        heading = match.group(1).strip() if match else path.stem
        title = re.sub(r"^Chapter\s+\d+:\s*", "", heading)
        number = int(CHAPTER_NAME_RE.search(path.name).group(1))
        chapters.append(Chapter(number=number, path=path, title=title, heading=heading))
    return chapters


def stripped_chapter_markdown(path: Path) -> str:
    """Remove stale planned page ranges from chapter bodies before PDF conversion."""
    text = path.read_text(encoding="utf-8")
    text = PAGES_ITALIC_RE.sub("", text, count=1)
    return text.lstrip("\n")


def run(cmd: list[str], **kwargs) -> None:
    kwargs.setdefault("stdout", subprocess.DEVNULL)
    kwargs.setdefault("stderr", subprocess.DEVNULL)
    subprocess.run(cmd, check=True, **kwargs)


def markdown_to_pdf(md_files: list[Path], out_pdf: Path, title: str) -> None:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "pandoc",
        *[str(p) for p in md_files],
        "-o",
        str(out_pdf),
        "--pdf-engine=wkhtmltopdf",
        "--pdf-engine-opt=--enable-local-file-access",
        "-V",
        "margin-top=18mm",
        "-V",
        "margin-bottom=20mm",
        "-V",
        "margin-left=16mm",
        "-V",
        "margin-right=16mm",
        "--css",
        str(CSS),
        "--number-sections",
        "--metadata",
        f"title={title}",
    ]
    env = os.environ.copy()
    env.setdefault("XDG_RUNTIME_DIR", "/tmp/runtime-ubuntu")
    Path("/tmp/runtime-ubuntu").mkdir(exist_ok=True)
    run(cmd, env=env)


def stamp_page_numbers(pdf_path: Path) -> None:
    """Draw 1-based page numbers at the bottom center of every page."""
    from io import BytesIO

    from reportlab.pdfgen import canvas as rl_canvas

    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    for i, page in enumerate(reader.pages, start=1):
        box = page.mediabox
        width, height = float(box.width), float(box.height)
        packet = BytesIO()
        c = rl_canvas.Canvas(packet, pagesize=(width, height))
        c.setFont("Helvetica", 9)
        c.setFillGray(0.25)
        c.drawCentredString(width / 2.0, 16, str(i))
        c.save()
        packet.seek(0)
        overlay = PdfReader(packet)
        page.merge_page(overlay.pages[0])
        writer.add_page(page)
    with pdf_path.open("wb") as f:
        writer.write(f)


def build_body_pdf(
    chapters: list[Chapter], work: Path, title: str
) -> tuple[Path, dict[int, tuple[int, int]], int]:
    """Convert each chapter to its own PDF, then concatenate in order."""
    writer = PdfWriter()
    ranges: dict[int, tuple[int, int]] = {}
    cursor = 1
    for ch in chapters:
        md = work / f"chapter-{ch.number:02d}.md"
        md.write_text(stripped_chapter_markdown(ch.path), encoding="utf-8")
        pdf = work / f"chapter-{ch.number:02d}.pdf"
        markdown_to_pdf([md], pdf, f"{title} — Chapter {ch.number}")
        n = len(PdfReader(str(pdf)).pages)
        if n < 1:
            raise SystemExit(f"Chapter {ch.number} produced an empty PDF")
        ranges[ch.number] = (cursor, cursor + n - 1)
        for page in PdfReader(str(pdf)).pages:
            writer.add_page(page)
        cursor += n
    body_pdf = work / "body.pdf"
    with body_pdf.open("wb") as f:
        writer.write(f)
    return body_pdf, ranges, cursor - 1


def page_label(start: int, end: int) -> str:
    return f"{start}" if start == end else f"{start}–{end}"


DEVOPS_PARTS = [
    (1, "Introduction & Mindset", range(1, 5)),
    (2, "Linux & Shell Mastery", range(5, 9)),
    (3, "Git & Collaboration", range(9, 12)),
    (4, "Networking for DevOps", range(12, 16)),
    (5, "Scripting & Programming", range(16, 20)),
    (6, "Infrastructure as Code", range(20, 26)),
    (7, "Containers", range(26, 31)),
    (8, "Kubernetes", range(31, 37)),
    (9, "CI/CD", range(37, 43)),
    (10, "Observability & SRE", range(43, 49)),
    (11, "Security (DevSecOps)", range(49, 55)),
    (12, "Advanced Topics", range(55, 61)),
]

AWS_PARTS = [
    (1, "Cloud Foundations", range(1, 5)),
    (2, "Identity & Access Management", range(5, 9)),
    (3, "Networking", range(9, 15)),
    (4, "Compute", range(15, 20)),
    (5, "Storage", range(20, 24)),
    (6, "Databases", range(24, 28)),
    (7, "Application Integration", range(28, 31)),
    (8, "DevOps on AWS", range(31, 35)),
    (9, "Observability & Operations", range(35, 39)),
    (10, "Security & Compliance", range(39, 42)),
]


def render_toc_markdown(
    book_title: str,
    subtitle: str,
    chapters: list[Chapter],
    ranges: dict[int, tuple[int, int]],
    parts: list[tuple[int, str, range]],
    total_pages: int,
    companion: str | None = None,
) -> str:
    by_num = {c.number: c for c in chapters}
    lines = [
        f"# {book_title}",
        "",
        f"**This edition:** {total_pages} numbered PDF pages (matches the page numbers in this file).",
        "",
        f"{subtitle}",
        "",
    ]
    if companion:
        lines.extend([companion, ""])
    lines.extend(
        [
            "Page numbers in this index match the page number printed at the bottom of each PDF page.",
            "They are measured from this edition, not estimates.",
            "",
            f"**Total pages: {total_pages}**",
            "",
        ]
    )
    for roman, part_title, ch_range in parts:
        part_chapters = [n for n in ch_range if n in by_num]
        if not part_chapters:
            continue
        p0 = ranges[part_chapters[0]][0]
        p1 = ranges[part_chapters[-1]][1]
        roman_label = ROMAN[roman] if isinstance(roman, int) and roman < len(ROMAN) else str(roman)
        lines.append(f"## Part {roman_label} — {part_title} (Pages {page_label(p0, p1)})")
        lines.append("")
        lines.append("| Ch | Title | Pages |")
        lines.append("|----|-------|-------|")
        for n in part_chapters:
            start, end = ranges[n]
            lines.append(f"| {n} | {by_num[n].title} | {page_label(start, end)} |")
        lines.append("")
    lines.append(f"## Edition total")
    lines.append("")
    lines.append(f"This PDF contains **{len(chapters)} chapters** across **{total_pages} pages**.")
    lines.append("")
    return "\n".join(lines) + "\n"


def update_chapter_headers(chapters: list[Chapter], ranges: dict[int, tuple[int, int]], handbook_label: str) -> None:
    for ch in chapters:
        start, end = ranges[ch.number]
        text = ch.path.read_text(encoding="utf-8")
        new_italic = f"*{handbook_label} — Pages {page_label(start, end)} of this PDF edition*"
        if PAGES_ITALIC_RE.search(text):
            text = PAGES_ITALIC_RE.sub(new_italic, text, count=1)
        else:
            # Insert after first heading
            text = re.sub(
                r"(^# .+?\n)",
                r"\1\n" + new_italic + "\n",
                text,
                count=1,
                flags=re.M,
            )
        ch.path.write_text(text, encoding="utf-8")


def merge_pdfs(parts: list[Path], dest: Path) -> int:
    writer = PdfWriter()
    for part in parts:
        reader = PdfReader(str(part))
        for page in reader.pages:
            writer.add_page(page)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("wb") as f:
        writer.write(f)
    return len(writer.pages)


def two_pass_handbook(
    handbook_dir: Path,
    book_title: str,
    subtitle: str,
    parts: list[tuple[int, str, range]],
    handbook_label: str,
    out_name: str,
    toc_path: Path,
    companion: str | None,
) -> int:
    chapters = chapter_files(handbook_dir)
    work = Path(tempfile.mkdtemp(prefix="handbook-"))
    try:
        body_pdf, draft_ranges, body_pages = build_body_pdf(chapters, work, book_title)
        toc_md = work / "toc.md"
        cover_md = work / "cover.md"
        cover_md.write_text(
            f"# {book_title}\n\n"
            f"**Complete edition**\n\n"
            f"{subtitle}\n\n"
            f"Page numbers in the following index match the PDF footer.\n",
            encoding="utf-8",
        )

        def write_toc(offset: int) -> tuple[str, dict[int, tuple[int, int]], int]:
            shifted = {
                n: (s + offset, e + offset)
                for n, (s, e) in draft_ranges.items()
            }
            total = body_pages + offset
            return (
                render_toc_markdown(
                    book_title, subtitle, chapters, shifted, parts, total, companion
                ),
                shifted,
                total,
            )

        # Measure front matter with offset 0 first to get toc+cover page count
        toc_text, _, _ = write_toc(0)
        toc_md.write_text(toc_text, encoding="utf-8")
        front_pdf = work / "front.pdf"
        markdown_to_pdf([cover_md, toc_md], front_pdf, book_title)
        offset = len(PdfReader(str(front_pdf)).pages)

        # Rebuild TOC with correct offset (may change TOC length by 0–1 page)
        toc_text, shifted, total = write_toc(offset)
        toc_md.write_text(toc_text, encoding="utf-8")
        markdown_to_pdf([cover_md, toc_md], front_pdf, book_title)
        offset2 = len(PdfReader(str(front_pdf)).pages)
        if offset2 != offset:
            toc_text, shifted, total = write_toc(offset2)
            toc_md.write_text(toc_text, encoding="utf-8")
            markdown_to_pdf([cover_md, toc_md], front_pdf, book_title)
            offset = offset2

        toc_path.write_text(toc_text, encoding="utf-8")
        update_chapter_headers(chapters, shifted, handbook_label)

        dest = PDF_DIR / out_name
        merge_pdfs([front_pdf, body_pdf], dest)
        stamp_page_numbers(dest)
        actual = len(PdfReader(str(dest)).pages)
        print(f"Wrote {dest} ({actual} pages; index total {total})")
        if actual != total:
            print(f"WARNING: merged page count {actual} != index total {total}")
        # Verify chapter order in ranges
        prev_end = 0
        for n in [c.number for c in chapters]:
            s, e = shifted[n]
            if s <= prev_end:
                print(f"WARNING: chapter {n} starts at {s} overlapping previous end {prev_end}")
            prev_end = e
        return actual
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_simple_pdf(sources: list[Path], title: str, out_name: str) -> int:
    dest = PDF_DIR / out_name
    markdown_to_pdf(sources, dest, title)
    stamp_page_numbers(dest)
    pages = len(PdfReader(str(dest)).pages)
    print(f"Wrote {dest} ({pages} pages)")
    return pages


def main() -> None:
    PDF_DIR.mkdir(exist_ok=True)
    devops_pages = two_pass_handbook(
        handbook_dir=ROOT / "devops-handbook",
        book_title="DevOps Handbook — Complete Edition",
        subtitle="Beginner → Advanced. Every chapter is included.",
        parts=DEVOPS_PARTS,
        handbook_label="DevOps Handbook",
        out_name="devops-handbook.pdf",
        toc_path=ROOT / "devops-handbook" / "00-table-of-contents.md",
        companion="Companion: [AWS Handbook](../aws-handbook/00-table-of-contents.md)",
    )
    aws_pages = two_pass_handbook(
        handbook_dir=ROOT / "aws-handbook",
        book_title="AWS Cloud Handbook — Complete Edition",
        subtitle="Beginner → Advanced AWS. Every chapter is included.",
        parts=AWS_PARTS,
        handbook_label="AWS Handbook",
        out_name="aws-handbook.pdf",
        toc_path=ROOT / "aws-handbook" / "00-table-of-contents.md",
        companion="Companion: [DevOps Handbook](../devops-handbook/00-table-of-contents.md)",
    )
    curr_d = build_simple_pdf(
        [ROOT / "README.md", ROOT / "curriculum-devops.md"],
        "DevOps Curriculum — Tools & Concepts",
        "devops-curriculum.pdf",
    )
    curr_a = build_simple_pdf(
        [ROOT / "README.md", ROOT / "curriculum-aws.md"],
        "AWS Cloud Curriculum — Services & Tools",
        "aws-curriculum.pdf",
    )

    # Combined guide: own index with combined-PDF page numbers.
    work = Path(tempfile.mkdtemp(prefix="combined-"))
    try:
        sections = [
            ("DevOps Curriculum", curr_d),
            ("AWS Curriculum", curr_a),
            ("DevOps Handbook", devops_pages),
            ("AWS Cloud Handbook", aws_pages),
        ]
        # Measure a draft combined index, then apply offset.
        def combined_toc(offset: int) -> str:
            lines = [
                "# DevOps & AWS Complete Learning Guide",
                "",
                "Page numbers below match the footer of **this combined PDF**.",
                "",
                "| Section | Pages |",
                "|---------|-------|",
            ]
            cursor = offset + 1
            for name, length in sections:
                end = cursor + length - 1
                lines.append(f"| {name} | {cursor}–{end} |")
                cursor = end + 1
            total = cursor - 1
            lines.extend(["", f"**Total pages: {total}**", ""])
            return "\n".join(lines) + "\n", total

        toc_text, _ = combined_toc(0)
        toc_md = work / "combined-toc.md"
        toc_md.write_text(toc_text, encoding="utf-8")
        front = work / "combined-front.pdf"
        markdown_to_pdf([toc_md], front, "DevOps & AWS Complete Learning Guide")
        offset = len(PdfReader(str(front)).pages)
        toc_text, expected_total = combined_toc(offset)
        toc_md.write_text(toc_text, encoding="utf-8")
        markdown_to_pdf([toc_md], front, "DevOps & AWS Complete Learning Guide")
        offset2 = len(PdfReader(str(front)).pages)
        if offset2 != offset:
            toc_text, expected_total = combined_toc(offset2)
            toc_md.write_text(toc_text, encoding="utf-8")
            markdown_to_pdf([toc_md], front, "DevOps & AWS Complete Learning Guide")

        combined = PDF_DIR / "devops-aws-complete-guide.pdf"
        merge_pdfs(
            [
                front,
                PDF_DIR / "devops-curriculum.pdf",
                PDF_DIR / "aws-curriculum.pdf",
                PDF_DIR / "devops-handbook.pdf",
                PDF_DIR / "aws-handbook.pdf",
            ],
            combined,
        )
        stamp_page_numbers(combined)
        combined_pages = len(PdfReader(str(combined)).pages)
        print(f"Wrote {combined} ({combined_pages} pages; index total {expected_total})")
        (ROOT / "pdf" / "COMBINED-INDEX.md").write_text(toc_text, encoding="utf-8")
    finally:
        shutil.rmtree(work, ignore_errors=True)

    print(
        f"DONE devops={devops_pages} aws={aws_pages} combined={combined_pages}"
    )


if __name__ == "__main__":
    main()
