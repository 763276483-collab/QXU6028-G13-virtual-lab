# G13 regular virtual lab analysis

The classroom group label is P13. Both the regular and classroom blind datasets use the code G13. The original ten files are in `data/` and their SHA-256 hashes are checked at the start of each run.

With Python 3.10 or later installed, install dependencies using `python -m pip install -r requirements.txt` (requires `numpy>=2.0` and `reportlab>=4.0`). Then run `python reproduce.py` from this folder. This regenerates `results.json`, the supporting metrics, the plot data and four figure PDFs under `generated/`.

The PDF report is built from `report_source.txt` and the reproduced figures using `python build_report.py`. The report in `report_source.txt` distinguishes the reproduced regular analysis from the archived classroom run. Reproducing the regular analysis does not rerun the classroom test.

Files for submission and review:

- `P13_report.pdf` - the submitted report, six pages, including the classroom blind test section. Identical to `generated/G13_report.pdf`.
- `results.json` - the packaged machine-readable regular results. This is a copy of `generated/results.json`; run `python reproduce.py` to regenerate it under `generated/`.
- `AI_USAGE_ADDENDUM.md` - summary of follow-up packaging and pre-submission review assistance (also integrated into `PROCESS_RECORDS.md`).
- `PROCESS_RECORDS.md` - AI usage log, AI error ledger and signed contribution statement. The signatures are collected in `signatures/` and reproduced in `SIGNED_CONTRIBUTION_STATEMENT.png`.
- `PROCESS_RECORDS_signed.pdf` - the same process record typeset for reading, with the four handwritten signatures on the last page.
- `P13_report_and_process_records.pdf` - the report and the process record concatenated, nine pages, for reading in a single file.

To test a clean checkout from the bundle, run `git clone P13_analysis.bundle G13_checkout`, enter `G13_checkout`, install `requirements.txt`, and run `python reproduce.py`. Before QMplus submission, push the verified `main` branch to the group's GitHub or Gitee repository and provide the accessible repository URL on QMplus.

If running on a blind dataset folder with the specified schema, pass it via `python reproduce.py --data PATH_TO_BLIND_GROUP --out blind_run`. The analysis writes `blind_results.json` when the input dataset is marked `blind`.

The L2 scalar uncertainty is half the 16th to 84th percentile width of selected gap values. The metric file preserves both endpoints and the median. The L3 `pass` Boolean compares the point estimate against the limit. The `confidence` string includes the prescribed noise envelope decision. L3 `x` increases with column and `y` increases with row, following the documented row-major pixel-centre convention. Random seeds are in `reproduce.py`.

The `classroom_blind` folder preserves the original blind JSON, UTF-16 run log, commit file, figures, archived source and original blind dataset. The archived manifest lists a blank `blind_results.json` template that is absent from the supplied archive. The completed classroom result is at `classroom_blind/blind_results.json`. The blind commit belongs to the group's classroom repository. The Git bundle in this package contains the regular-analysis and report history.
