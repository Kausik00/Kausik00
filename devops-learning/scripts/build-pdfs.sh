#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$ROOT/pdf"
CSS="$ROOT/scripts/pdf-style.css"

mkdir -p "$OUT"

PANDOC_OPTS=(
  --pdf-engine=wkhtmltopdf
  --pdf-engine-opt=--enable-local-file-access
  -V margin-top=20mm
  -V margin-bottom=20mm
  -V margin-left=18mm
  -V margin-right=18mm
  --css="$CSS"
  --toc
  --toc-depth=3
  --number-sections
  -V documentclass=article
)

build_pdf() {
  local name="$1"
  local title="$2"
  shift 2
  echo "Building $name ..."
  pandoc "$@" -o "$OUT/$name" "${PANDOC_OPTS[@]}" --metadata title="$title"
  echo "  -> $OUT/$name"
}

# Curricula (standalone reference guides)
build_pdf "devops-curriculum.pdf" "DevOps Curriculum — Tools & Concepts" \
  "$ROOT/README.md" \
  "$ROOT/curriculum-devops.md"

build_pdf "aws-curriculum.pdf" "AWS Cloud Curriculum — Services & Tools" \
  "$ROOT/README.md" \
  "$ROOT/curriculum-aws.md"

# DevOps Handbook (TOC + written chapters)
build_pdf "devops-handbook.pdf" "DevOps Handbook" \
  "$ROOT/devops-handbook/00-table-of-contents.md" \
  "$ROOT/devops-handbook/part-01-introduction/chapter-01-what-is-devops.md" \
  "$ROOT/devops-handbook/part-01-introduction/chapter-02-calms-three-ways.md" \
  "$ROOT/devops-handbook/part-02-linux/chapter-05-linux-fundamentals.md"

# AWS Handbook (TOC + written chapters)
build_pdf "aws-handbook.pdf" "AWS Cloud Handbook" \
  "$ROOT/aws-handbook/00-table-of-contents.md" \
  "$ROOT/aws-handbook/part-01-foundations/chapter-01-introduction-aws.md" \
  "$ROOT/aws-handbook/part-01-foundations/chapter-02-global-infrastructure.md" \
  "$ROOT/aws-handbook/part-02-iam/chapter-05-iam-fundamentals.md"

# Combined edition
build_pdf "devops-aws-complete-guide.pdf" "DevOps & AWS Complete Learning Guide" \
  "$ROOT/README.md" \
  "$ROOT/curriculum-devops.md" \
  "$ROOT/curriculum-aws.md" \
  "$ROOT/devops-handbook/00-table-of-contents.md" \
  "$ROOT/devops-handbook/part-01-introduction/chapter-01-what-is-devops.md" \
  "$ROOT/devops-handbook/part-01-introduction/chapter-02-calms-three-ways.md" \
  "$ROOT/devops-handbook/part-02-linux/chapter-05-linux-fundamentals.md" \
  "$ROOT/aws-handbook/00-table-of-contents.md" \
  "$ROOT/aws-handbook/part-01-foundations/chapter-01-introduction-aws.md" \
  "$ROOT/aws-handbook/part-01-foundations/chapter-02-global-infrastructure.md" \
  "$ROOT/aws-handbook/part-02-iam/chapter-05-iam-fundamentals.md"

echo ""
echo "PDF build complete. Files in: $OUT"
ls -lh "$OUT"/*.pdf
