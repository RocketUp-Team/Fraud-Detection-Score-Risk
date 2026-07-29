# LaTeX thesis report

This directory contains the reproducible source for the FPT MSE-formatted
system report.

## Before submission

Review `metadata.tex` and confirm:

- the official thesis title;
- the Group 1 roster and name spelling;
- the supervisor name;
- the convocation year.

The appendix distinguishes repository-recorded subsystem roles from team
members whose detailed contribution statement still requires confirmation.

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

The generated PDF is an evidence snapshot of the repository as inspected on
30 July 2026. It distinguishes current verification from saved artifact claims.
