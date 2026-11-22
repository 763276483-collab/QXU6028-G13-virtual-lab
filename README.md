# G13 regular virtual lab analysis

The classroom group label is P13. Both the regular and classroom blind datasets use the code G13. The original ten files are in data/ and their hashes are checked at the start of each run.

With Python 3.11 or later and Git installed, install requirements.txt using python -m pip install -r requirements.txt. Then run python reproduce.py from this folder. This regenerates results.json, the supporting metrics, the plot data and four figure PDFs under generated/. The recorded calculation was run with NumPy 2.3.5 and ReportLab 4.4.9.

The PDF report is built from report_source.txt and the reproduced figures using python build_report.py. The report in report_source.txt distinguishes the reproduced regular analysis from the archived classroom run. Reproducing the regular analysis does not rerun the classroom test.

Files for submission and review:

- P13_report.pdf - the submitted report, six pages, including the classroom blind test section. Identical to generated/G13_report.pdf.
- results.json - the packaged machine-readable regular results. This is a copy of generated/results.json; run python reproduce.py to regenerate it under generated/.
- AI_USAGE_ADDENDUM.md - disclosure of the follow-up packaging and consistency review.
- PROCESS_RECORDS.md - AI usage log, AI error ledger and signed contribution statement. The signatures are collected in signatures/ and reproduced in SIGNED_CONTRIBUTION_STATEMENT.png.
- PROCESS_RECORDS_signed.pdf - the same process record typeset for reading, with the four handwritten signatures on the last page.
- P13_report_and_process_records.pdf - the report and the process record concatenated, nine pages, for reading in a single file.

For a clean checkout of the analysis history, run git clone P13_analysis.bundle G13_checkout from the unpacked project, then enter G13_checkout and run the same command. Publish the verified main branch to a group-owned GitHub or Gitee repository, grant marker access and use the repository URL on QMplus. The local bundle preserves the history for transfer to that repository.

If the class releases a blind folder with the specified schema, pass it via python reproduce.py --data PATH_TO_BLIND_GROUP --out blind_run. Use the frozen group-approved commit and the threshold announced for that session. The analysis writes blind_results.json when the input dataset is marked blind. Capture the actual terminal log and frozen commit hash as the separate files required by the class.

The L2 scalar uncertainty is half the 16th to 84th percentile width of selected gap values. The metric file preserves both endpoints and the median. The L3 pass Boolean compares the point estimate against the limit. The confidence string includes the prescribed noise envelope decision. L3 x increases with column and y increases with row, following the documented row-major pixel-centre convention. Random seeds are in reproduce.py.

The classroom_blind folder preserves the original blind JSON, UTF-16 run log, commit file, figures, archived source and original blind dataset. The archived manifest lists a blank blind_results.json template that is absent from the supplied archive. The completed classroom result is at classroom_blind/blind_results.json. The blind commit belongs to the group's classroom repository. The Git bundle in this package contains the later regular-analysis and report history.
