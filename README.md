# Logbook Entry Generator

A configurable, self-contained HTML tool for generating shift log entries at
Jefferson Lab. Built initially for the PionCT experiment; adaptable to any
experiment via a single configuration file.

---

## What It Does

Shift workers open a single HTML file in any browser and fill in:

- A free-text shift summary and quick links
- Timestamped shift log entries
- Per-run data (spectrometer settings, beam parameters, DAQ config, etc.)

Clicking **Generate HTML** produces formatted HTML ready to paste directly
into the JLab logbook. Run data can optionally be sent to a shared Google
Sheet in real time.

No installation, no internet connection required for basic use, no external
files needed — everything is embedded in the single HTML output file.

---

## Repository Structure

```
├── build.py              # Build script — generates the HTML tool from config
├── config.json           # Experiment configuration — edit this for your experiment
├── logo.png              # Experiment logo (embedded at build time if present)
├── .schema_hash          # Auto-generated — tracks Google Sheets column schema
├── output/
│   ├── logbook_generator.html   # Generated — distribute this to shift workers
│   └── apps_script.gs           # Generated — paste into Google Apps Script
└── docs/
    ├── USER_GUIDE.md     # For shift workers
    ├── SETUP_GUIDE.md    # For experiment coordinators
    ├── DEVELOPER_GUIDE.md# For developers
    └── tex/              # LaTeX source for the above (pdflatex)
```

---

## Quick Start

### For shift workers

Open `output/logbook_generator.html` in Chrome, Firefox, or Edge. See the
[User Guide](docs/USER_GUIDE.md).

### For experiment coordinators (setting up for a new experiment)

1. Edit `config.json` — set your experiment name, logo, run fields, and
   optionally Google Sheets credentials.
2. Run the build script:
   ```bash
   python3 build.py
   ```
   Requires Python 3.6+, standard library only.
3. Distribute `output/logbook_generator.html` to your shift workers.
4. If using Google Sheets, follow the setup steps in the
   [Setup Guide](docs/SETUP_GUIDE.md).

### For developers

See the [Developer Guide](docs/DEVELOPER_GUIDE.md) for internals, extension
points, and known limitations.

---

## Configuring for Your Experiment

All experiment-specific content lives in `config.json`. Key things you can
change:

| Setting | What it controls |
|---|---|
| `experiment_name` | Page title, browser tab, localStorage namespace |
| `logo.path` | Logo image (embedded as base64 if file is present) |
| `quick_links` | The URL fields in the Summary section |
| `run_fields` | Every column in the run table and Google Sheet |
| `google_sheets.enabled` | Whether Sheets export UI appears at all |

Run `python3 build.py` after any change to regenerate the HTML.

### Changing run fields mid-experiment

You can add, remove, or reorder fields in `run_fields` at any time and
rebuild. If Google Sheets is enabled and the column schema changed, the build
script will print a warning reminding you to redeploy the Apps Script — the
column order in the sheet must stay in sync with the HTML tool.

If `.schema_hash` is missing (deleted or first run), the warning is skipped
and a new hash file is written automatically.

---

## Google Sheets Integration

When `google_sheets.enabled` is `true`, the build produces an
`output/apps_script.gs` file alongside the HTML. One-time setup:

1. Create a Google Sheet.
2. **Extensions → Apps Script** — paste `apps_script.gs`.
3. Set `SHARED_SECRET` in the script to match `config.json`.
4. **Deploy → New deployment → Web app** (Execute as: Me, Access: Anyone).
5. Copy the Web App URL into the logbook tool's Export Settings field.

Full instructions: [Setup Guide — Google Sheets section](docs/SETUP_GUIDE.md#setting-up-google-sheets-export).

---

## Documentation

| Document | Audience | Contents |
|---|---|---|
| [User Guide](docs/USER_GUIDE.md) | Shift workers | How to use the tool day-to-day |
| [Setup Guide](docs/SETUP_GUIDE.md) | Experiment coordinators | Config reference, build script, Google Sheets setup |
| [Developer Guide](docs/DEVELOPER_GUIDE.md) | Developers | Internals, architecture, extension points |

LaTeX source for all three documents is in `docs/tex/`. Compile with:
```bash
cd docs/tex
pdflatex user_guide.tex
pdflatex setup_guide.tex
pdflatex developer_guide.tex
```
Run `pdflatex` twice per document to resolve cross-references and the table
of contents.

---

## Requirements

| Component | Requirement |
|---|---|
| Build script | Python 3.6+, standard library only |
| Generated HTML | Any modern browser (Chrome, Firefox, Edge) |
| Google Sheets export | Internet access from the machine running the HTML |
| LaTeX docs | pdflatex with `tcolorbox`, `booktabs`, `tabularx`, `titlesec`, `fancyhdr` |

---

## Contact

Questions: [gayoso@jlab.org](mailto:gayoso@jlab.org)

Original logbook tool concept by Andrew Schick for the PRadII experiment.
