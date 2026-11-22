# G13 regular virtual lab analysis

The source pack labels this dataset G13. The user's classroom label was P13. Confirm the official mapping before submission. The original ten files are in data/ and their hashes are checked at the start of each run.

With Python 3.10 or later and Git installed, install requirements.txt using python -m pip install -r requirements.txt. Then run python reproduce.py from this folder. This regenerates results.json, the supporting metrics, the plot data and four figure PDFs under generated/. The recorded calculation was run with NumPy 2.3.5 and ReportLab 4.4.9. For Python 3.10 specifically, use NumPy 2.2.6 if the pinned version cannot be installed.

The PDF report is built from report_source.txt and the reproduced figures using python build_report.py. Its narrative describes G13 regular data specifically. The supplied report is an editable draft via report_source.txt. Fill in student names and IDs, confirm the group mapping, verify the Chapter 3 reference against the original lecture, and have the group check the interpretation and complete the process records.

For a clean checkout of the analysis history, run git clone G13_analysis.bundle G13_checkout from the unpacked project, then enter G13_checkout and run the same command. Publish the verified project to a group-owned GitHub or Gitee repository, grant marker access and use the repository URL on QMplus.

If the class releases a blind folder with the specified schema, pass it via python reproduce.py --data PATH_TO_BLIND_GROUP --out blind_run. Use the frozen group-approved commit and the threshold announced for that session. The analysis writes blind_results.json when the input dataset is marked blind. Capture the actual terminal log and frozen commit hash as the separate files required by the class.

The L2 scalar uncertainty is half the 16th to 84th percentile width of selected gap values. The metric file preserves both endpoints and the median. The L3 pass Boolean compares the point estimate against the limit. The confidence string includes the prescribed noise envelope decision. L3 x increases with column and y increases with row, following the documented row-major pixel-centre convention. Random seeds are in reproduce.py.
