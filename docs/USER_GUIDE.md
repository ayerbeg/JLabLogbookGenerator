# Logbook Entry Generator — User Guide

This guide is for shift workers using the logbook tool during an experiment.
No installation, no accounts, no configuration needed on your part — just open
the HTML file in a browser and start logging.

---

## Opening the Tool

Open `logbook_generator.html` in any modern browser (Chrome, Firefox, Edge).
No internet connection is required to use the form itself. Internet is only
needed if you want to send run data to Google Sheets.

---

## Your Work is Saved Automatically

Every field you fill in is saved to your browser's local storage automatically
as you type. If you close the tab, refresh the page, or the browser crashes,
your data will be restored when you reopen the file **in the same browser on
the same machine**.

> ⚠ Data is saved per-browser, per-machine. If you switch to a different
> browser or computer, your saved session will not be there. Use
> **Import from Previous HTML** (see below) to move a session between machines.

The autosave timestamp is shown at the top of the page under Session Management.

---

## Session Management

At the top of the page you have two session controls:

- **Import from Previous HTML** — paste the HTML output from a previous entry
  to continue editing it. Useful for carrying over run data to the next shift.
- **Clear All & Start Fresh** — wipes everything and reloads a blank form.
  This cannot be undone.

---

## Filling in the Form

### Summary

Free-text description of the shift. Write whatever is relevant: what was
accomplished, any issues, beam status, etc.

### Quick Links

Paste URLs for the standard shift documents (run plan, checklist, beamline
screenshots, etc.). Links left blank are simply omitted from the generated
output.

### Additional Links (optional)

Click **+ Add Additional Link** to add any extra URLs with custom labels.
Click **Remove** on an entry to delete it.

### Shift Log Entries

Click **+ Add Shift Entry** to add a timestamped log line.

- **Time** — enter the time manually in `HH:MM` (24-hour) format, or click
  **Now** to fill it from the system clock.
- **Logbook Entry** — free text describing what happened at that time.

Click **Remove** on an entry to delete it. The numbering (Shift Entry #1, #2…)
is assigned at creation and does not change if you delete other entries.

### Run Summary

Click **+ Add Run Entry** for each run taken during the shift.

Fields filled by you:

| Field | Notes |
|---|---|
| Run Number | The DAQ run number |
| Start Time | `HH:MM` format, 24-hour, set by hand from the DAQ |
| Stop Time | `HH:MM` format, 24-hour, set by hand from the DAQ |
| Target | Free text |
| Beam Current (uA) | |
| HMS P [GeV] | |
| SHMS P [GeV] | |
| HMS Angle [deg] | |
| SHMS Angle [deg] | |
| Number of Events (M) | |
| Trigger Rate [Hz] | |
| Live Time [%] | |
| DAQ Config | |
| Comments | |

Fields filled automatically:

| Field | How |
|---|---|
| Total Time (min) | Calculated from Stop − Start as soon as both are filled. Handles midnight crossings correctly. If either time is missing or malformed, it is left unchanged. |
| Date | Filled at the moment you click Generate HTML or Send to Google Sheet (local date, `YYYY-MM-DD`). |

---

## Google Sheets Export (if configured)

If your experiment coordinator has set up Google Sheets integration, you will
see a **Google Sheets Export Settings** section. Paste the Web App URL and
shared secret there once — they are remembered by the browser.

Each run entry has:

- A **coloured dot** (LED) next to its label:
  - 🔴 Red — not yet sent to the sheet
  - 🟢 Green — successfully sent (persists across page reloads)
- A **Send to Google Sheet** button — sends that specific run's data.
- An **Export All Runs to Google Sheet** button (in the settings section) —
  sends every run in sequence.

The dot state is saved alongside your form data, so reopening the page will
still show which runs have been exported.

> ⚠ The dot reflects whether *this tool* successfully sent the data. It does
> not check whether the row actually landed in the sheet. If you have doubts,
> verify directly in the spreadsheet.

---

## Generating the Logbook Entry

1. Click **Generate HTML**.
2. The raw HTML appears in the output box and a preview renders below it.
3. Click **Copy to Clipboard**.
4. In the JLab logbook, open the summary entry you want to update.
5. Set the text format to **HTML**.
6. Select all existing text (Ctrl+A) and paste (Ctrl+V).

---

## Importing a Previous Entry

To continue editing a previous shift's entry:

1. Open the logbook entry in a browser and view its HTML source (or copy it
   from the logbook's HTML editor).
2. Click **Import from Previous HTML** in the tool.
3. Paste the HTML into the text box and click **Import**.

The tool will restore the summary, links, shift log, and run table from that
entry. The Google Sheets sent/not-sent dot state is **not** restored on import
(the tool has no way to know what was previously sent), so all imported runs
will show red dots.

---

## Tips

- Total Time auto-fills only when both Start and Stop are valid `HH:MM` values.
  If you type a non-standard format (e.g. `930` instead of `09:30`) it will be
  left as-is.
- You can manually override Total Time by typing directly into that field. It
  will recalculate if you later change Start or Stop.
- The run entry number (Run Entry #N) is permanent — it does not renumber if
  you delete other entries. This is intentional so numbers stay stable during
  a shift.
