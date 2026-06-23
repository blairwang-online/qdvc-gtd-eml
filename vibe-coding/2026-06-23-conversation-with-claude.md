# 2026-06-23 Conversation with Claude

Opus 4.8 High

## 1. User request

I would like to implement a version of GTD (Getting Things Done) based on EML email files, using Python. Consider the following folder structure:

01-input  
02-triage  
03-actionable  
04-reference  
05-archive  

I will manually place EML files in 01-input.

It will be the Python script's responsibility to rename new files in the EML according to the following naming convention: yyyy-mm-dd-brief-description.eml. For example 2026-06-12-meeting-minutes-project-pudding.eml. The brief description should be derived from the email subject line in the EML file. The Python script should ensure that no other EML files across all 5 folders already have that filename, if so then a different name should be chosen (e.g., 2026-06-12-meeting-minutes-project-pudding-23.eml). Each filename is to contain digits, dashes, and lowercase alphabetical characters only. No spacebars, no special symbols. I should be able to set the maximum number of characters in the filename using a constant at the top of the Python script.

After the automatic renaming, the EML file is placed into 02-triage.

As the human user, I will inspect the files in 02-triage and move to either 03-actionable or 04-reference or 05-archive.

The Python script should report on:

* Any files in 02-triage that have yet to be moved to one of the other folders
* Any files in 03-actionable
* Any files in 04-reference
* The last N files in 05-archive (e.g., N=10). I should be able to set N using a constant at the top of the Python script.

When reporting on these files, the first part of each line should be the date of the file (based on email headers) and how many days have elapsed since that date. For example:

```
2026-06-03 (20d)   Meeting Meetings Project Pudding
2026-06-13 (10d)   Update on Pudding
2026-06-20  (3d)   Pudding good news!
```


There should be a metadata.csv file at the root directory (not in any of the 5 folders). Headers:

* eml_filename
* general_notes
* project


Please ensure that the Python file is well-modularised (sensible functions). Each function should have a comment with example input and outputs.

## 2. LLM response

Let me verify it works with a quick test.Works as specified — ingestion, MIME-decoded subjects, collision-safe naming, reporting with elapsed days, and idempotent metadata sync.Done. Tested output:

```
2026-06-03  (20d)   Meeting Minutes - Project Pudding!
2026-06-13  (10d)   Update on Pudding
```

Notes on the implementation:

- **Constants at top:** `MAX_FILENAME_CHARS` (caps total filename length including `.eml`, truncating the slug on a dash boundary) and `ARCHIVE_REPORT_N` (last-N archive files). `BASE_DIR` defaults to the script's own directory.
- **Naming:** subject is MIME-decoded then slugified to `[a-z0-9-]` only; collisions across all 5 folders get `-2`, `-3`, … appended while staying within the char limit.
- **Idempotent:** rerunning skips an empty input and preserves existing `general_notes`/`project` values in `metadata.csv`, adding rows for new files and dropping rows for files that no longer exist anywhere.
- **Dates** come from the email `Date` header (falls back to now if missing/unparseable). Elapsed days are right-aligned so single- and double-digit counts line up.

Run it with `python3 gtd.py` from wherever the 5 folders should live (or place the script in that root). Each function carries an example-input/output comment as requested.

One thing to flag: subjects in the report show the original (with punctuation/casing), while filenames use the slug — that matched your example. If you'd rather the report show the slug-style description instead, that's a one-line change.

Attached: gtd.py _(as of this commit)_
