# LaTeX thesis report

This directory contains the reproducible source for the FPT MSE-formatted
system report.

## Before submission

Review `metadata.tex` and confirm:

- the official thesis title;
- the Group 1 roster and name spelling;
- the supervisor name;
- the convocation year.

The acknowledgments section contains the single official team roster and
repository role mapping table.

## Build

From this directory, when Perl is available:

```powershell
latexmk -xelatex -interaction=nonstopmode -halt-on-error report.tex
```

`latexmk` invokes BibTeX when citations change. The result is `report.pdf`.

MiKTeX installations without Perl can use the direct sequence:

```powershell
xelatex -interaction=nonstopmode -halt-on-error report.tex
bibtex report
xelatex -interaction=nonstopmode -halt-on-error report.tex
xelatex -interaction=nonstopmode -halt-on-error report.tex
```

To remove auxiliary build files while retaining the PDF:

```powershell
latexmk -c report.tex
```

The document prefers Times New Roman. If the system font is unavailable,
XeLaTeX falls back to TeX Gyre Termes, a metrically compatible serif face.

## Structure

- `metadata.tex` — replaceable submission metadata;
- `frontmatter/` — abstract and acknowledgments;
- `chapters/` — thesis body;
- `figures/` — reproducible TikZ/PGFPlots figures;
- `appendices/` — API, feature, runbook, and test reference;
- `references.bib` — academic and software sources.

The Markdown architecture report and official-run artifacts were synchronized
into the LaTeX source on 31 July 2026. The checked-in PDF remains an older
evidence snapshot and has intentionally not been rebuilt yet. Review the
updated split counts, official V2 CatBoost metrics, calibration/promotion
status, and policy-ownership caveat before building a new PDF.
