# Report originality and AI-assistance check

Date checked: 2 August 2026

The revised report was reviewed after the prose rewrite and before submission. The review covered the LaTeX source under `docs/latex/`, including the abstract, chapters, conclusion, and acknowledgement disclosure.

The local structural check found no remaining `itemize`, `enumerate`, `description`, or `\\item` environments in the LaTeX report. The prose was rewritten around the project's own dataset counts, model metrics, validation artifacts, architecture decisions, and limitations. Technical claims were kept tied to the existing tables, figures, repository evidence, and cited references; no new performance result was invented during the rewrite.

Three distinctive sentences from the revised prose were searched as exact phrases on the public web. No exact matching report or source passage was found in the returned results. This is only a spot check, not an institutional similarity report, because services such as Turnitin and iThenticate use proprietary indexes that are not available in this workspace.

AI authorship detection cannot be established reliably from text alone. The report therefore includes an explicit AI-assistance disclosure in `frontmatter/acknowledgments.tex`. The team remains responsible for verifying the wording, citations, data, code, and interpretation against the original project evidence. Before final submission, the authors should run the PDF through the university's approved similarity checker and manually inspect every highlighted match, especially standard technical terminology and dataset names.
