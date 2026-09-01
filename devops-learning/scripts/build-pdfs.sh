#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/pdf"
CSS="$ROOT/scripts/pdf-style.css"

mkdir -p "$OUT"

PANDOC_OPTS=(
  --pdf-engine=wkhtmltopdf
  --pdf-engine-opt=--enable-local-file-access
  -V margin-top=18mm
  -V margin-bottom=18mm
  -V margin-left=16mm
  -V margin-right=16mm
  --css="$CSS"
  --toc
  --toc-depth=2
  --number-sections
  -V documentclass=article
)

# Collect chapter files sorted numerically (chapter-01, chapter-02, ... chapter-60)
collect_chapters() {
  local handbook_dir="$1"
  find "$handbook_dir" -name 'chapter-*.md' -type f | sort -t'-' -k2 -n
}

build_pdf() {
  local name="$1"
  local title="$2"
  shift 2
  echo "Building $name ($(echo "$#" | tr -d ' ') files) ..."
  pandoc "$@" -o "$OUT/$name" "${PANDOC_OPTS[@]}" --metadata title="$title"
  local size
  size=$(du -h "$OUT/$name" | cut -f1)
  echo "  -> $OUT/$name ($size)"
}

DEVOPS_TOC="$ROOT/devops-handbook/00-table-of-contents.md"
AWS_TOC="$ROOT/aws-handbook/00-table-of-contents.md"

mapfile -t DEVOPS_CHAPTERS < <(collect_chapters "$ROOT/devops-handbook")
mapfile -t AWS_CHAPTERS < <(collect_chapters "$ROOT/aws-handbook")

echo "DevOps chapters found: ${#DEVOPS_CHAPTERS[@]}"
echo "AWS chapters found: ${#AWS_CHAPTERS[@]}"

# Curricula
build_pdf "devops-curriculum.pdf" "DevOps Curriculum — Tools & Concepts" \
  "$ROOT/README.md" "$ROOT/curriculum-devops.md"

build_pdf "aws-curriculum.pdf" "AWS Cloud Curriculum — Services & Tools" \
  "$ROOT/README.md" "$ROOT/curriculum-aws.md"

# Full handbooks
build_pdf "devops-handbook.pdf" "DevOps Handbook — Complete Edition" \
  "$DEVOPS_TOC" "${DEVOPS_CHAPTERS[@]}"

build_pdf "aws-handbook.pdf" "AWS Cloud Handbook — Complete Edition" \
  "$AWS_TOC" "${AWS_CHAPTERS[@]}"

# Combined mega-guide
build_pdf "devops-aws-complete-guide.pdf" "DevOps & AWS Complete Learning Guide" \
  "$ROOT/README.md" \
  "$ROOT/curriculum-devops.md" \
  "$ROOT/curriculum-aws.md" \
  "$DEVOPS_TOC" "${DEVOPS_CHAPTERS[@]}" \
  "$AWS_TOC" "${AWS_CHAPTERS[@]}"

echo ""
echo "PDF build complete. Files in: $OUT"
ls -lh "$OUT"/*.pdf
