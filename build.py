#!/usr/bin/env python3
"""
Logbook Generator Build Script
================================
Reads config.json and produces:
  - output/logbook_generator.html   (always)
  - output/apps_script.gs           (only when google_sheets.enabled is true)

Usage:
  python3 build.py                  # uses config.json in the same directory
  python3 build.py my_config.json   # uses a specific config file

Requirements: Python 3.6+, standard library only.

If the Sheets-relevant field schema has changed since the last build
(detected via a hash stored in config.json), a warning is printed
reminding you to redeploy the Apps Script.
"""

import base64
import hashlib
import json
import mimetypes
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Config loading and validation
# ---------------------------------------------------------------------------

REQUIRED_TOP_LEVEL = ["experiment_name", "page_title", "contact_email",
                      "quick_links", "run_fields"]
VALID_SOURCES = {"user", "auto", "sheet-only"}
VALID_TYPES   = {"text", "textarea"}

def load_config(config_path: Path) -> dict:
    with open(config_path, encoding="utf-8") as f:
        cfg = json.load(f)

    # Basic structure checks
    for key in REQUIRED_TOP_LEVEL:
        if key not in cfg:
            die(f"config.json is missing required key: '{key}'")

    for i, field in enumerate(cfg["run_fields"]):
        for k in ("key", "label", "type", "source", "sheet_column", "sheet_align"):
            if k not in field:
                die(f"run_fields[{i}] ('{field.get('key','?')}') is missing required key: '{k}'")
        if field["source"] not in VALID_SOURCES:
            die(f"run_fields[{i}]: source must be one of {VALID_SOURCES}, got '{field['source']}'")
        if field["type"] not in VALID_TYPES:
            die(f"run_fields[{i}]: type must be one of {VALID_TYPES}, got '{field['type']}'")

    sheets_cfg = cfg.get("google_sheets", {})
    if sheets_cfg.get("enabled") and not sheets_cfg.get("shared_secret"):
        die("google_sheets.enabled is true but shared_secret is missing or empty.")

    return cfg


def die(msg: str):
    print(f"\n  ERROR: {msg}\n", file=sys.stderr)
    sys.exit(1)


# ---------------------------------------------------------------------------
# Schema hash (for detecting Sheets-breaking changes)
# ---------------------------------------------------------------------------

def compute_schema_hash(cfg: dict) -> str:
    """Hash of the Sheets-visible field order and column names."""
    sheets_fields = [
        (f["key"], f["sheet_column"])
        for f in cfg["run_fields"]
    ]
    blob = json.dumps(sheets_fields, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Logo embedding
# ---------------------------------------------------------------------------

def embed_logo(logo_cfg: dict, config_dir: Path) -> str:
    """
    Returns an <img> tag. If the logo path exists next to the config,
    embeds it as base64 (self-contained). Otherwise falls back to the
    path as-is (works for hosted URLs or files at a known relative path).
    """
    path_str = logo_cfg.get("path", "")
    alt      = logo_cfg.get("alt", "Logo")

    if not path_str:
        return ""

    logo_path = config_dir / path_str
    if logo_path.exists():
        mime, _ = mimetypes.guess_type(str(logo_path))
        if not mime:
            mime = "image/png"
        data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        src = f"data:{mime};base64,{data}"
        print(f"  Logo: embedded '{logo_path.name}' as base64 ({len(data)//1024} KB)")
    else:
        src = path_str
        print(f"  Logo: using path/URL '{path_str}' (file not found locally — not embedded)")

    return f'<img src="{src}" alt="{alt}" />'


# ---------------------------------------------------------------------------
# JavaScript helpers derived from field config
# ---------------------------------------------------------------------------

def js_key(css_class: str) -> str:
    """Convert a CSS class like 'run-hms-p' to a JS variable name 'hmsP'."""
    # strip the 'run-' prefix if present
    s = css_class.removeprefix("run-")
    parts = s.split("-")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def build_add_run_entry_fields(user_fields: list, auto_fields: set) -> str:
    """Generate the innerHTML field divs for addRunEntry()."""
    lines = []
    for f in user_fields:
        key   = f["key"]
        label = f["label"]
        ph    = f.get("placeholder", "")
        ftype = f["type"]

        ph_attr     = f' placeholder="{ph}"' if ph else ""
        onchange    = ""
        readonly    = ""

        if key in auto_fields:
            # Total time: shown but calculated automatically
            readonly = " readonly style=\"background-color:#3a3f44; color:#aaaaaa;\""
        if key == "run-start" or key == "run-stop":
            onchange = ' onchange="updateRunLength(this)"'

        lines.append('                    <div class="form-group">')
        lines.append(f'                        <label>{label}:</label>')

        if ftype == "textarea":
            lines.append(f'                        <textarea class="{key}"></textarea>')
        else:
            lines.append(
                f'                        <input type="text" class="{key}"{ph_attr}{onchange}{readonly} value="">'
            )
        lines.append('                    </div>')

    return "\n".join(lines)


def build_extract_run_data(user_and_auto_form_fields: list) -> str:
    """Generate the extractRunData() function body."""
    lines = [
        "        function extractRunData(item) {",
        "            const now  = new Date();",
        "            const date = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;",
        "            return {",
    ]
    for f in user_and_auto_form_fields:
        key  = f["key"]
        jkey = js_key(key)
        if key == "date":
            lines.append(f"                {jkey}:    date,")
        elif key == "run-length":
            lines.append(f"                {jkey}:    item.querySelector('.run-length').value,")
        else:
            lines.append(f"                {jkey}:    item.querySelector('.{key}').value,")
    lines.append("            };")
    lines.append("        }")
    return "\n".join(lines)


def build_generate_html_run_table(all_html_fields: list) -> str:
    """Generate the run table header + data row loop inside generateHTML()."""
    n_cols = len(all_html_fields)
    lines = [
        "            // Run Summary",
        "            html += '<hr>\\n<h2>Run Summary</h2>\\n';",
        "            html += '<table style=\"border:2px solid black;\">\\n';",
        "            html += '  <colgroup>\\n';",
        f"            for (let i = 0; i < {n_cols}; i++) {{",
        "                html += '    <col style=\"border:1px solid black;\"/>\\n';",
        "            }",
        "            html += '  </colgroup> \\n';",
        "            html += '  <tr style=\"border:1px solid black; background-color: rgba(222,222,222,1.0);\">\\n';",
    ]
    for f in all_html_fields:
        align = f["sheet_align"]
        label = f["sheet_column"]
        lines.append(f'            html += \'    <th style="text-align:{align};">{label}</th>\\n\';')
    lines.append("            html += '  </tr>\\n\\n';")
    lines.append("")
    lines.append("            const runItems = document.querySelectorAll('#runEntries .entry-item');")
    lines.append("            runItems.forEach((item, index) => {")

    # Variable declarations for each field
    for f in all_html_fields:
        key  = f["key"]
        jkey = js_key(key)
        if key == "date":
            lines.append("                const now        = new Date();")
            lines.append(
                "                const date       = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;"
            )
        else:
            lines.append(f"                const {jkey:<14} = item.querySelector('.{key}').value;")

    lines.append("")
    lines.append("                const bgStyle   = index % 2 === 1 ? 'background-color: rgba(222,222,222,0.3);' : '';")
    lines.append("                const styleAttr = bgStyle ? ` style=\"border:1px solid black; ${bgStyle}\"` : ' style=\"border:1px solid black;\"';")
    lines.append("")
    lines.append("                html += `<tr${styleAttr}>\\n`;")
    for f in all_html_fields:
        jkey  = js_key(f["key"])
        align = f["sheet_align"]
        lines.append(f'                html += `    <td style="text-align:{align}">\\n${{{jkey}}}\\n    </td>\\n`;')
    lines.append("                html += `</tr>\\n\\n`;")
    lines.append("            });")
    lines.append("            html += '</table>\\n';")
    return "\n".join(lines)


def build_save_run_entries(form_fields: list) -> str:
    lines = [
        "            // Save run entries",
        "            document.querySelectorAll('#runEntries .entry-item').forEach(item => {",
        "                const runData = {",
    ]
    for f in form_fields:
        key  = f["key"]
        jkey = js_key(key)
        if key == "run-length":
            lines.append(f"                    {jkey}:   item.querySelector('.run-length').value,")
        else:
            lines.append(f"                    {jkey}:   item.querySelector('.{key}').value,")
    lines.append("                    sentToSheet: item.querySelector('.sheet-led')?.dataset.sent === 'true'")
    lines.append("                };")
    lines.append("                data.runEntries.push(runData);")
    lines.append("            });")
    return "\n".join(lines)


def build_load_run_entries(form_fields: list) -> str:
    lines = [
        "                // Restore run entries",
        "                data.runEntries?.forEach(run => {",
        "                    addRunEntry();",
        "                    const items    = document.querySelectorAll('#runEntries .entry-item');",
        "                    const lastItem = items[items.length - 1];",
    ]
    for f in form_fields:
        key  = f["key"]
        jkey = js_key(key)
        if key == "run-length":
            lines.append(f"                    lastItem.querySelector('.run-length').value = run.{jkey} || '';")
        else:
            lines.append(f"                    lastItem.querySelector('.{key}').value = run.{jkey} || '';")
    lines.append("                    if (run.sentToSheet) {")
    lines.append("                        const led = lastItem.querySelector('.sheet-led');")
    lines.append("                        led.style.backgroundColor = '#66bb6a';")
    lines.append("                        led.style.boxShadow = '0 0 4px rgba(102,187,106,0.6)';")
    lines.append("                        led.title = 'Sent to Google Sheet';")
    lines.append("                        led.dataset.sent = 'true';")
    lines.append("                    }")
    lines.append("                });")
    return "\n".join(lines)


def build_import_run_entries(html_fields: list) -> str:
    n = len(html_fields)
    lines = [
        "                // Process Run Summary table",
        "                if (runSummaryTable) {",
        "                    const rows = Array.from(runSummaryTable.querySelectorAll('tr')).slice(1);",
        "                    const validRows = rows.filter(row => {",
        "                        const cells = row.querySelectorAll('td');",
        f"                        if (cells.length < {n}) return false;",
        "                        return Array.from(cells).some(cell => cell.textContent.trim() !== '');",
        "                    });",
        "                    if (validRows.length > 0) addRunEntry();",
        "                    validRows.forEach((row, index) => {",
        "                        const cells = row.querySelectorAll('td');",
        "                        if (index > 0) addRunEntry();",
        "                        const entries = document.querySelectorAll('#runEntries .entry-item');",
        "                        const entry   = entries[index];",
        "                        if (entry) {",
    ]
    for col_idx, f in enumerate(html_fields):
        key = f["key"]
        if key == "date":
            lines.append(f"                            // cells[{col_idx}] is Date — auto-generated, not restored")
        else:
            lines.append(
                f"                            entry.querySelector('.{key}').value = cells[{col_idx}].textContent.trim();"
            )
    lines.append("                        }")
    lines.append("                    });")
    lines.append("                }")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Quick links HTML generation
# ---------------------------------------------------------------------------

def build_quick_links_form(quick_links: list) -> str:
    lines = ['        <h3>Quick Links</h3>']
    for i, link in enumerate(quick_links, 1):
        label = link["label"]
        lid   = link["id"]
        lines.append('        <div class="form-group">')
        lines.append(f'            <label>{i}. {label}:</label>')
        lines.append(f'            <input type="url" id="{lid}" value="">')
        lines.append('        </div>')
    return "\n".join(lines)


def build_quick_links_save(quick_links: list) -> str:
    return "\n".join(
        f'                {link["id"]}: document.getElementById(\'{link["id"]}\').value,'
        for link in quick_links
    )


def build_quick_links_load(quick_links: list) -> str:
    return "\n".join(
        f'                document.getElementById(\'{link["id"]}\').value = data.{link["id"]} || \'\';'
        for link in quick_links
    )


def build_quick_links_clear(quick_links: list) -> str:
    return "\n".join(
        f'                document.getElementById(\'{link["id"]}\').value = \'\';'
        for link in quick_links
    )


def build_quick_links_generate_html(quick_links: list) -> str:
    lines = ["            // Quick Links", "            html += '<h3>Quick Links</h3>\\n';"]
    for link in quick_links:
        lid   = link["id"]
        label = link["label"]
        lines.append(f'            const {lid} = document.getElementById(\'{lid}\').value;')
        lines.append(f'            if ({lid}) html += `<a href="${{{lid}}}">{label}</a>\\n<br>\\n`;')
    return "\n".join(lines)


def build_import_links(quick_links: list) -> str:
    """Generate the link-identification block inside importFromHTML."""
    lines = []
    for link in quick_links:
        label_lower = link["label"].lower()
        lid         = link["id"]
        # use the first significant word of the label as the keyword
        keyword = label_lower.split()[0]
        lines.append(
            f'                    if (text.toLowerCase().includes(\'{keyword}\')) {{'
        )
        lines.append(
            f'                        document.getElementById(\'{lid}\').value = href;'
        )
        lines.append("                    } else")
    # strip trailing ' else'
    if lines:
        lines[-1] = lines[-1].rstrip(" else")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Apps Script generation
# ---------------------------------------------------------------------------

def build_apps_script(cfg: dict, schema_hash: str) -> str:
    exp     = cfg["experiment_name"]
    secret  = cfg["google_sheets"]["shared_secret"]
    fields  = cfg["run_fields"]

    header_list  = ",\n  ".join(f'"{f["sheet_column"]}"' for f in fields)
    row_comments = {f["key"]: f.get("_comment", "") for f in fields}

    row_lines = []
    for f in fields:
        key  = f["key"]
        jkey = js_key(key)
        src  = f["source"]
        col  = f["sheet_column"]
        if src == "sheet-only":
            comment = f"  // {col} — filled manually in sheet"
            row_lines.append(f"      ''{comment},")
        elif key == "date":
            row_lines.append(f"      run.{jkey}        || '',")
        else:
            row_lines.append(f"      run.{jkey}        || '',")

    row_block = "\n".join(row_lines)

    return f"""/**
 * {exp} Logbook -> Google Sheets bridge.
 * Schema hash: {schema_hash}
 *   (If this hash changed since your last deployment, redeploy this script
 *    and update the Web App URL in the logbook tool's Export Settings.)
 *
 * SETUP:
 * 1. Open your target Google Sheet.
 * 2. Extensions -> Apps Script -> delete placeholder code -> paste this file.
 * 3. Change SHARED_SECRET below to match the value in the logbook tool.
 * 4. Deploy -> New deployment -> Web app.
 *      Execute as: Me
 *      Who has access: Anyone
 * 5. Authorize, then copy the Web App URL into the logbook tool's
 *    "Google Sheets Export Settings" field.
 *
 * WARNING: "Anyone" means anyone with this URL can POST rows.
 * The shared secret is the only guard — keep the URL and secret private.
 */

const SHARED_SECRET = '{secret}';

const HEADERS = [
  {header_list}
];

function doPost(e) {{
  try {{
    const body = JSON.parse(e.postData.contents);

    if (body.secret !== SHARED_SECRET) {{
      return jsonResponse({{ ok: false, error: 'Invalid secret.' }});
    }}

    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    if (sheet.getLastRow() === 0) {{
      sheet.appendRow(HEADERS);
    }}

    const run = body.run || {{}};
    const row = [
{row_block}
    ];

    sheet.appendRow(row);
    return jsonResponse({{ ok: true, rowAppended: sheet.getLastRow() }});

  }} catch (err) {{
    return jsonResponse({{ ok: false, error: err.message }});
  }}
}}

function jsonResponse(obj) {{
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}}
"""


# ---------------------------------------------------------------------------
# Main HTML generation
# ---------------------------------------------------------------------------

def build_html(cfg: dict, logo_tag: str, sheets_enabled: bool,
               schema_hash: str) -> str:

    exp_name   = cfg["experiment_name"]
    page_title = cfg["page_title"]
    contact    = cfg["contact_email"]
    credit     = cfg.get("credit_line", "")
    storage_key = exp_name.lower().replace(" ", "_") + "LogbookData"
    fields      = cfg["run_fields"]
    ql          = cfg["quick_links"]

    # Partition fields
    user_fields       = [f for f in fields if f["source"] == "user"]
    auto_form_fields  = [f for f in fields if f["source"] == "auto" and f["key"] != "date"]
    # Fields shown in the HTML form (user-entered + auto-calculated display, NOT sheet-only or date)
    form_fields       = [f for f in fields if f["source"] in ("user", "auto") and f["key"] != "date"]
    # Fields shown in the HTML run table (all non-sheet-only)
    html_table_fields = [f for f in fields if f["source"] != "sheet-only"]
    # Auto field keys that should be shown readonly in form
    auto_form_keys    = {f["key"] for f in auto_form_fields}

    # Build JS fragments
    run_entry_fields_html = build_add_run_entry_fields(form_fields, auto_form_keys)
    extract_run_data_js   = build_extract_run_data(
        [f for f in fields if f["source"] != "sheet-only"]
    )
    generate_run_table_js = build_generate_html_run_table(html_table_fields)
    save_run_js           = build_save_run_entries(form_fields)
    load_run_js           = build_load_run_entries(form_fields)
    import_run_js         = build_import_run_entries(html_table_fields)
    ql_form_html          = build_quick_links_form(ql)
    ql_save_js            = build_quick_links_save(ql)
    ql_load_js            = build_quick_links_load(ql)
    ql_clear_js           = build_quick_links_clear(ql)
    ql_generate_js        = build_quick_links_generate_html(ql)
    ql_import_js          = build_import_links(ql)

    sheets_warning = ""
    if sheets_enabled:
        sheets_warning = f"""
    <!-- ═══════════════════════════════════════════════════════════════════════
         GOOGLE SHEETS SCHEMA HASH: {schema_hash}
         If you change run_fields in config.json and rebuild, check whether
         this hash changed. If it did, you MUST redeploy the Apps Script and
         update the Web App URL in the Export Settings below, or the sheet
         columns will be misaligned.
         ═══════════════════════════════════════════════════════════════════════ -->"""

    sheets_settings_section = ""
    if sheets_enabled:
        sheets_settings_section = """
    <div class="container">
        <h2>Google Sheets Export Settings</h2>
        <p style="font-size:13px;">
            Paste the Apps Script Web App URL and shared secret here once (see setup instructions provided separately).
            These are saved locally in your browser and reused automatically.
        </p>
        <div class="form-group">
            <label>Web App URL:</label>
            <input type="url" id="sheetsWebAppUrl" placeholder="https://script.google.com/macros/s/XXXXXXX/exec" onchange="saveToLocalStorage()">
        </div>
        <div class="form-group">
            <label>Shared Secret:</label>
            <input type="text" id="sheetsSharedSecret" placeholder="must match SHARED_SECRET in the Apps Script" onchange="saveToLocalStorage()">
        </div>
        <button class="btn btn-info" onclick="exportAllRunsToSheet()">Export All Runs to Google Sheet</button>
        <div id="sheetsExportStatus" style="font-size:13px; margin-top:10px; color:#64b5f6;"></div>
    </div>
"""

    run_entry_header_buttons = ""
    if sheets_enabled:
        run_entry_header_buttons = """
                        <button class="btn btn-info" style="margin-right:10px;" onclick="sendRunToSheet(this)">Send to Google Sheet</button>"""

    led_html = ""
    if sheets_enabled:
        led_html = """
                        <span class="sheet-led" data-sent="false" title="Not yet sent to Google Sheet" style="display:inline-block; width:10px; height:10px; border-radius:50%; background-color:#f44336; margin-right:8px; box-shadow:0 0 4px rgba(244,67,54,0.6);"></span>"""

    sheets_status_div = ""
    if sheets_enabled:
        sheets_status_div = """
                <div class="run-sheet-status" style="font-size:12px; color:#64b5f6; margin-bottom:8px;"></div>"""

    sheets_save_js = ""
    if sheets_enabled:
        sheets_save_js = """
                sheetsWebAppUrl:    document.getElementById('sheetsWebAppUrl').value,
                sheetsSharedSecret: document.getElementById('sheetsSharedSecret').value,"""

    sheets_load_js = ""
    if sheets_enabled:
        sheets_load_js = """
                document.getElementById('sheetsWebAppUrl').value    = data.sheetsWebAppUrl    || '';
                document.getElementById('sheetsSharedSecret').value = data.sheetsSharedSecret || '';"""

    sheets_functions_js = ""
    if sheets_enabled:
        sheets_functions_js = """
        function extractRunData(item) {
            const now  = new Date();
            const date = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')}`;
            return {
EXTRACT_PLACEHOLDER
            };
        }

        async function postRunToSheet(runData) {
            const url    = document.getElementById('sheetsWebAppUrl').value.trim();
            const secret = document.getElementById('sheetsSharedSecret').value.trim();
            if (!url) throw new Error('No Web App URL configured. Fill in "Google Sheets Export Settings" first.');
            const response = await fetch(url, {
                method: 'POST',
                headers: { 'Content-Type': 'text/plain;charset=utf-8' },
                body: JSON.stringify({ secret, run: runData })
            });
            if (!response.ok) throw new Error(`Request failed with status ${response.status}`);
            const result = await response.json();
            if (!result.ok) throw new Error(result.error || 'Unknown error from Apps Script.');
            return result;
        }

        async function sendRunToSheet(button) {
            const item      = button.closest('.entry-item');
            const statusDiv = item.querySelector('.run-sheet-status');
            const led       = item.querySelector('.sheet-led');
            const runData   = extractRunData(item);
            statusDiv.textContent = 'Sending...';
            statusDiv.style.color = '#64b5f6';
            try {
                const result = await postRunToSheet(runData);
                statusDiv.textContent = `✓ Sent (row ${result.rowAppended}) at ${new Date().toLocaleTimeString()}`;
                statusDiv.style.color = '#66bb6a';
                led.style.backgroundColor = '#66bb6a';
                led.style.boxShadow = '0 0 4px rgba(102,187,106,0.6)';
                led.title = 'Sent to Google Sheet';
                led.dataset.sent = 'true';
                saveToLocalStorage();
            } catch (err) {
                statusDiv.textContent = `✗ Failed: ${err.message}`;
                statusDiv.style.color = '#f44336';
                led.style.backgroundColor = '#f44336';
                led.style.boxShadow = '0 0 4px rgba(244,67,54,0.6)';
                led.title = 'Not yet sent to Google Sheet';
                led.dataset.sent = 'false';
                console.error('Sheets export error:', err);
            }
        }

        async function exportAllRunsToSheet() {
            const statusDiv = document.getElementById('sheetsExportStatus');
            const items     = document.querySelectorAll('#runEntries .entry-item');
            if (items.length === 0) {
                statusDiv.textContent = 'No run entries to export.';
                statusDiv.style.color = '#f44336';
                return;
            }
            let successCount = 0, failCount = 0;
            for (let i = 0; i < items.length; i++) {
                statusDiv.textContent = `Sending run ${i + 1} of ${items.length}...`;
                statusDiv.style.color = '#64b5f6';
                try {
                    await postRunToSheet(extractRunData(items[i]));
                    successCount++;
                } catch (err) {
                    failCount++;
                    console.error(`Run ${i + 1} export error:`, err);
                }
            }
            if (failCount === 0) {
                statusDiv.textContent = `✓ Exported all ${successCount} run(s) successfully.`;
                statusDiv.style.color = '#66bb6a';
            } else {
                statusDiv.textContent = `Exported ${successCount}, failed ${failCount}. Check console for details.`;
                statusDiv.style.color = '#f44336';
            }
        }
"""
        # Inline extractRunData into the placeholder
        extract_lines = []
        for f in [x for x in fields if x["source"] != "sheet-only"]:
            key  = f["key"]
            jkey = js_key(key)
            if key == "date":
                extract_lines.append(f"                {jkey}:   date,")
            elif key == "run-length":
                extract_lines.append(f"                {jkey}:   item.querySelector('.run-length').value,")
            else:
                extract_lines.append(f"                {jkey}:   item.querySelector('.{key}').value,")
        sheets_functions_js = sheets_functions_js.replace(
            "EXTRACT_PLACEHOLDER", "\n".join(extract_lines)
        )

    credit_line_html = f'\n        <p style="margin-top: 5px; color: #ffffff; font-size: 13px;">{credit}</p>' if credit else ""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1400px;
            margin: 20px auto;
            padding: 20px;
            background: #e6e6e6;
            background-attachment: fixed;
            color: #2C3539;
            min-height: 100vh;
        }}
        .container {{
            background: linear-gradient(135deg, #6b7176 0%, #5a6066 100%);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.6), 0 0 20px rgba(255, 152, 0, 0.2);
            margin-bottom: 20px;
            border: 1px solid rgba(255, 152, 0, 0.3);
        }}
        h1 {{ color: #ff9800; text-shadow: 0 0 15px rgba(255,152,0,0.5), 0 0 30px rgba(255,152,0,0.3); }}
        h2 {{ color: #ffb74d; border-bottom: 2px solid #ff9800; padding-bottom: 10px; text-shadow: 0 0 8px rgba(255,152,0,0.3); }}
        h3 {{ color: #ffb74d; }}
        h4 {{ color: #ffb74d; }}
        .form-group {{ margin-bottom: 15px; }}
        label {{ display: block; font-weight: bold; margin-bottom: 5px; color: #ffffff; }}
        input[type="text"], input[type="url"], textarea, select {{
            width: 100%; padding: 8px; border: 1px solid #757575;
            border-radius: 4px; box-sizing: border-box;
            font-family: Arial, sans-serif;
            background-color: #464B50; color: #ffffff;
        }}
        input[type="text"]:focus, input[type="url"]:focus, textarea:focus, select:focus {{
            outline: none; border-color: #ff9800;
            box-shadow: 0 0 8px rgba(255,152,0,0.4);
        }}
        input::placeholder, textarea::placeholder {{ color: #5a6b7d; }}
        textarea {{ min-height: 60px; resize: vertical; }}
        .btn {{
            padding: 10px 20px; border: none; border-radius: 4px;
            cursor: pointer; font-size: 14px; margin-right: 10px;
            margin-top: 10px; font-weight: bold; transition: all 0.3s ease;
        }}
        .btn-primary   {{ background: linear-gradient(135deg, #ff9800, #ff9800); color: white; box-shadow: 0 2px 8px rgba(255,152,0,0.4); }}
        .btn-primary:hover {{ background: linear-gradient(135deg, #ffb74d, #ff9800); box-shadow: 0 4px 12px rgba(255,152,0,0.6); transform: translateY(-2px); }}
        .btn-secondary {{ background: linear-gradient(135deg, #757575, #616161); color: white; box-shadow: 0 2px 8px rgba(117,117,117,0.4); }}
        .btn-secondary:hover {{ background: linear-gradient(135deg, #9e9e9e, #757575); box-shadow: 0 4px 12px rgba(117,117,117,0.6); transform: translateY(-2px); }}
        .btn-danger    {{ background: linear-gradient(135deg, #f44336, #d32f2f); color: white; box-shadow: 0 2px 8px rgba(244,67,54,0.4); }}
        .btn-danger:hover {{ background: linear-gradient(135deg, #ef5350, #f44336); box-shadow: 0 4px 12px rgba(244,67,54,0.6); transform: translateY(-2px); }}
        .btn-success   {{ background: linear-gradient(135deg, #66bb6a, #43a047); color: white; box-shadow: 0 2px 8px rgba(76,175,80,0.4); }}
        .btn-success:hover {{ background: linear-gradient(135deg, #81c784, #66bb6a); box-shadow: 0 4px 12px rgba(76,175,80,0.6); transform: translateY(-2px); }}
        .btn-info      {{ background: linear-gradient(135deg, #42a5f5, #1e88e5); color: white; box-shadow: 0 2px 8px rgba(33,150,243,0.4); }}
        .btn-info:hover {{ background: linear-gradient(135deg, #64b5f6, #42a5f5); box-shadow: 0 4px 12px rgba(33,150,243,0.6); transform: translateY(-2px); }}
        .entry-item {{
            border: 1px solid rgba(255,152,0,0.3); padding: 15px;
            margin-bottom: 10px; border-radius: 4px;
            background-color: rgba(44,53,57,0.7);
        }}
        .entry-header {{
            display: flex; justify-content: space-between;
            align-items: center; margin-bottom: 10px;
        }}
        .entry-number {{ font-weight: bold; color: #ffb74d; text-shadow: 0 0 5px rgba(255,152,0,0.3); }}
        #output {{
            background-color: #464B50; border: 1px solid #757575;
            padding: 15px; border-radius: 4px;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap; word-wrap: break-word;
            max-height: 400px; overflow-y: auto; color: #ffffff;
        }}
        #preview {{
            border: 1px solid #ddd; padding: 15px;
            background: white; border-radius: 4px; color: #333;
        }}
        #preview h2 {{ color: #2c3e50; border-bottom: 2px solid #34495e; text-shadow: none; }}
        #preview h3 {{ color: #2c3e50; text-shadow: none; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }}
        .success-message {{
            background: linear-gradient(135deg, #ff9800, #ff9800);
            color: white; padding: 10px; border-radius: 4px;
            margin-top: 10px; display: none;
            box-shadow: 0 0 15px rgba(255,152,0,0.5);
        }}
        p {{ color: #ffffff; }}
        .logo-container {{ text-align: center; margin-bottom: 20px; }}
        .logo-container img {{ max-width: 400px; height: auto; filter: drop-shadow(0 0 20px rgba(255,152,0,0.4)); }}
    </style>
</head>
<body>
{sheets_warning}
    <div class="logo-container">
        {logo_tag}
    </div>
    <h1 style="text-align:center; color:#ff9800; text-shadow:0 0 15px rgba(255,152,0,0.5), 0 0 30px rgba(255,152,0,0.3);">{page_title}</h1>

    <div class="container" style="background:linear-gradient(135deg,#6b7176 0%,#5a6066 100%); border:1px solid rgba(255,152,0,0.3);">
        <h3 style="margin-top:0; color:#ffb74d;">Session Management</h3>
        <p style="margin:10px 0; color:#ffffff; font-size:14px;">
            <strong style="color:#ffb74d;">Auto-save:</strong> Your work is automatically saved in your browser. If you refresh or close this page, your data will be restored.
        </p>
        <button class="btn btn-secondary" onclick="showImportDialog()">Import from Previous HTML</button>
        <button class="btn btn-danger" onclick="clearAllData()">Clear All &amp; Start Fresh</button>
        <div id="autoSaveStatus" style="color:#64b5f6; font-size:11px; margin-top:10px;"></div>
        <p style="margin-top:15px; color:#ffffff; font-size:13px;">
            Contact: <a href="mailto:{contact}" style="color:#ffb74d;">{contact}</a>
        </p>{credit_line_html}
    </div>

    <!-- Import Dialog -->
    <div id="importDialog" style="display:none; position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); background:linear-gradient(135deg,#6b7176 0%,#5a6066 100%); padding:30px; border-radius:8px; box-shadow:0 4px 20px rgba(0,0,0,0.9), 0 0 30px rgba(255,152,0,0.3); z-index:1000; max-width:600px; width:90%; border:1px solid rgba(255,152,0,0.3); color:#ffffff;">
        <h3 style="color:#ffb74d; margin-top:0;">Import from Previous HTML</h3>
        <p style="color:#ffffff; font-size:14px;">Paste the HTML code from a previous logbook entry to continue editing:</p>
        <textarea id="importTextarea" style="width:100%; height:200px; font-family:monospace; font-size:12px; margin:10px 0; background-color:#464B50; color:#ffffff; border:1px solid #757575; padding:10px; border-radius:4px;"></textarea>
        <button class="btn btn-primary" onclick="importFromHTML()">Import</button>
        <button class="btn btn-secondary" onclick="hideImportDialog()">Cancel</button>
    </div>
    <div id="importOverlay" style="display:none; position:fixed; top:0; left:0; right:0; bottom:0; background:rgba(10,22,40,0.85); z-index:999;" onclick="hideImportDialog()"></div>

    <div class="container">
        <h2>Summary</h2>
        <div class="form-group">
            <label>Summary Text:</label>
            <textarea id="summaryText" placeholder="Example: We completed 2 production cycles of configs A and B."></textarea>
        </div>
{ql_form_html}
        <h4>Additional Links (optional)</h4>
        <div id="additionalLinks"></div>
        <button class="btn btn-secondary" onclick="addAdditionalLink()">+ Add Additional Link</button>
    </div>

    <div class="container">
        <h2>Shift Log Entries</h2>
        <div id="shiftEntries"></div>
        <button class="btn btn-success" onclick="addShiftEntry()">+ Add Shift Entry</button>
    </div>
{sheets_settings_section}
    <div class="container">
        <h2>Run Summary</h2>
        <div id="runEntries"></div>
        <button class="btn btn-success" onclick="addRunEntry()">+ Add Run Entry</button>
    </div>

    <div class="container">
        <h2>Generated HTML</h2>
        <ol style="font-size:13px; margin:0 0 15px 0; padding-left:20px; color:#ffffff;">
            <li>Click "Copy to Clipboard" below.</li>
            <li>In the logbook, open the summary entry you want to edit.</li>
            <li>Set the text format to <strong>HTML</strong>.</li>
            <li>Click inside the text area and select all the existing text (Ctrl+A).</li>
            <li>Paste the new text (Ctrl+V) to replace it.</li>
        </ol>
        <button class="btn btn-info" onclick="generateHTML()">Generate HTML</button>
        <button class="btn btn-success" onclick="copyToClipboard()">Copy to Clipboard</button>
        <div class="success-message" id="copySuccess">✓ Copied to clipboard!</div>
        <div id="output"></div>
    </div>

    <div class="container">
        <h2>Preview</h2>
        <div id="preview"></div>
    </div>

    <script>
        let shiftCounter = 0;
        let runCounter   = 0;

        function addAdditionalLink() {{
            const container = document.getElementById('additionalLinks');
            const div = document.createElement('div');
            div.className = 'entry-item';
            div.innerHTML = `
                <label>Link Text:</label>
                <input type="text" class="al-text" value="">
                <label>URL:</label>
                <input type="url" class="al-url" value="">
                <button class="btn btn-danger" onclick="removeAndSave(this)">Remove</button>
            `;
            container.appendChild(div);
            saveToLocalStorage();
        }}

        function addShiftEntry() {{
            shiftCounter++;
            const container = document.getElementById('shiftEntries');
            const div = document.createElement('div');
            div.className = 'entry-item';
            div.innerHTML = `
                <div class="entry-header">
                    <span class="entry-number">Shift Entry #${{shiftCounter}}</span>
                    <button class="btn btn-danger" onclick="removeAndSave(this)">Remove</button>
                </div>
                <div class="grid-2">
                    <div class="form-group">
                        <label>Time:</label>
                        <div style="display:flex; gap:8px;">
                            <input type="text" class="shift-time" placeholder="00:00" value="" style="flex:1;">
                            <button type="button" class="btn btn-secondary" style="margin:0; padding:8px 12px;" onclick="setNowTime(this)">Now</button>
                        </div>
                    </div>
                </div>
                <div class="form-group">
                    <label>Logbook Entry:</label>
                    <textarea class="shift-entry"></textarea>
                </div>
            `;
            container.appendChild(div);
            saveToLocalStorage();
        }}

        function addRunEntry() {{
            runCounter++;
            const container = document.getElementById('runEntries');
            const div = document.createElement('div');
            div.className = 'entry-item';
            div.innerHTML = `
                <div class="entry-header">
                    <span class="entry-number">{led_html}
                        Run Entry #${{runCounter}}
                    </span>
                    <div>{run_entry_header_buttons}
                        <button class="btn btn-danger" onclick="removeAndSave(this)">Remove</button>
                    </div>
                </div>{sheets_status_div}
                <div class="grid-2">
{run_entry_fields_html}
                </div>
            `;
            container.appendChild(div);
            saveToLocalStorage();
        }}

        function removeAndSave(button) {{
            button.closest('.entry-item').remove();
            saveToLocalStorage();
        }}

        function setNowTime(button) {{
            const input = button.previousElementSibling;
            const now = new Date();
            input.value = `${{String(now.getHours()).padStart(2,'0')}}:${{String(now.getMinutes()).padStart(2,'0')}}`;
            saveToLocalStorage();
        }}

        function parseHHMM(value) {{
            const match = /^(\\d{{1,2}}):(\\d{{2}})$/.exec(value.trim());
            if (!match) return null;
            const h = parseInt(match[1], 10), m = parseInt(match[2], 10);
            if (h > 23 || m > 59) return null;
            return h * 60 + m;
        }}

        function updateRunLength(inputEl) {{
            const item  = inputEl.closest('.entry-item');
            const sMin  = parseHHMM(item.querySelector('.run-start').value);
            const eMin  = parseHHMM(item.querySelector('.run-stop').value);
            if (sMin === null || eMin === null) {{ saveToLocalStorage(); return; }}
            let diff = eMin - sMin;
            if (diff < 0) diff += 24 * 60;
            item.querySelector('.run-length').value = diff;
            saveToLocalStorage();
        }}

        function generateHTML() {{
            let html = '<h2>Summary</h2>\\n';
            html += document.getElementById('summaryText').value + '\\n<br>\\n';

{ql_generate_js}

            // Additional links
            document.querySelectorAll('#additionalLinks .entry-item').forEach(item => {{
                const text = item.querySelector('.al-text').value;
                const url  = item.querySelector('.al-url').value;
                if (text && url) html += `<a href="${{url}}">${{text}}</a>\\n<br>\\n`;
            }});

            // Shift Log
            html += '\\n<hr>\\n<h2>Shift Log</h2>\\n';
            html += '<table style="border:2px solid black;"> \\n';
            html += '  <colgroup>\\n    <col style="border:1px solid black;"/>\\n    <col style="border:1px solid black;"/>\\n  </colgroup>\\n';
            html += '  <tr style="border:1px solid black; background-color: rgba(222,222,222,1.0);">\\n    <th>Time</th>\\n    <th>Logbook Entry</th>\\n  </tr>\\n\\n';
            document.querySelectorAll('#shiftEntries .entry-item').forEach((item, index) => {{
                const bgStyle   = index % 2 === 1 ? 'background-color: rgba(222,222,222,0.3);' : '';
                const styleAttr = bgStyle ? ` style="border:1px solid black; ${{bgStyle}}"` : ' style="border:1px solid black;"';
                html += `  <tr${{styleAttr}}>\\n    <td >\\n      ${{item.querySelector('.shift-time').value}}\\n    </td>\\n    <td>\\n     ${{item.querySelector('.shift-entry').value}}\\n    </td>\\n  </tr>\\n\\n`;
            }});
            html += '</table>\\n\\n';

{generate_run_table_js}

            document.getElementById('output').textContent = html;
            document.getElementById('preview').innerHTML  = html;
        }}

{sheets_functions_js}

        function copyToClipboard() {{
            navigator.clipboard.writeText(document.getElementById('output').textContent).then(() => {{
                const msg = document.getElementById('copySuccess');
                msg.style.display = 'block';
                setTimeout(() => msg.style.display = 'none', 2000);
            }});
        }}

        function saveToLocalStorage() {{
            const data = {{
                summaryText: document.getElementById('summaryText').value,
{ql_save_js}{sheets_save_js}
                additionalLinks: [],
                shiftEntries:    [],
                runEntries:      [],
                timestamp:       new Date().toISOString()
            }};

            document.querySelectorAll('#additionalLinks .entry-item').forEach(item => {{
                data.additionalLinks.push({{
                    text: item.querySelector('.al-text').value,
                    url:  item.querySelector('.al-url').value
                }});
            }});

            document.querySelectorAll('#shiftEntries .entry-item').forEach(item => {{
                data.shiftEntries.push({{
                    time:  item.querySelector('.shift-time').value,
                    entry: item.querySelector('.shift-entry').value
                }});
            }});

{save_run_js}

            localStorage.setItem('{storage_key}', JSON.stringify(data));
            document.getElementById('autoSaveStatus').textContent =
                'Last autosave at ' + new Date().toLocaleTimeString();
        }}

        function loadFromLocalStorage() {{
            const saved = localStorage.getItem('{storage_key}');
            if (!saved) return;
            try {{
                const data = JSON.parse(saved);
                document.getElementById('summaryText').value = data.summaryText || '';
{ql_load_js}{sheets_load_js}

                data.additionalLinks?.forEach(link => {{
                    addAdditionalLink();
                    const items = document.querySelectorAll('#additionalLinks .entry-item');
                    const last  = items[items.length - 1];
                    last.querySelector('.al-text').value = link.text;
                    last.querySelector('.al-url').value  = link.url;
                }});

                data.shiftEntries?.forEach(entry => {{
                    addShiftEntry();
                    const items = document.querySelectorAll('#shiftEntries .entry-item');
                    const last  = items[items.length - 1];
                    last.querySelector('.shift-time').value  = entry.time;
                    last.querySelector('.shift-entry').value = entry.entry;
                }});

{load_run_js}

                const status = document.getElementById('autoSaveStatus');
                status.textContent = '✓ Loaded session from ' + new Date(data.timestamp).toLocaleString();
                status.style.color = '#2196F3';
            }} catch(e) {{
                console.error('Error loading saved data:', e);
            }}
        }}

        function showImportDialog() {{
            document.getElementById('importDialog').style.display  = 'block';
            document.getElementById('importOverlay').style.display = 'block';
        }}

        function hideImportDialog() {{
            document.getElementById('importDialog').style.display  = 'none';
            document.getElementById('importOverlay').style.display = 'none';
            document.getElementById('importTextarea').value = '';
        }}

        function importFromHTML() {{
            const htmlText = document.getElementById('importTextarea').value;
            if (!htmlText.trim()) {{ alert('Please paste some HTML to import.'); return; }}
            try {{
                const doc = new DOMParser().parseFromString(htmlText, 'text/html');

                document.getElementById('summaryText').value = '';
{ql_clear_js}
                document.getElementById('shiftEntries').innerHTML = '';
                document.getElementById('runEntries').innerHTML   = '';

                const bodyHTML    = doc.body.innerHTML;
                const summaryMatch = bodyHTML.match(/<h2>Summary<\\/h2>([\\s\\S]*?)<h3>Quick Links<\\/h3>/i);
                if (summaryMatch) {{
                    const tmp = document.createElement('div');
                    tmp.innerHTML = summaryMatch[1].trim();
                    document.getElementById('summaryText').value = tmp.textContent.trim();
                }}

                doc.querySelectorAll('a').forEach(link => {{
                    const href = link.getAttribute('href') || '';
                    const text = link.textContent.trim();
{ql_import_js}
                }});

                const allTables = doc.querySelectorAll('table');
                let shiftLogTable = null, runSummaryTable = null;
                allTables.forEach(table => {{
                    const headers = Array.from(table.querySelectorAll('th')).map(th => th.textContent.trim());
                    if (headers.includes('Time') && headers.includes('Logbook Entry')) shiftLogTable = table;
                    else if (headers.includes('Run Number') && headers.includes('Start Time')) runSummaryTable = table;
                }});

                if (shiftLogTable) {{
                    const rows = Array.from(shiftLogTable.querySelectorAll('tr')).slice(1);
                    const valid = rows.filter(r => {{
                        const c = r.querySelectorAll('td');
                        return c.length >= 2 && (c[0].textContent.trim() || c[1].textContent.trim());
                    }});
                    if (valid.length > 0) addShiftEntry();
                    valid.forEach((row, i) => {{
                        const c = row.querySelectorAll('td');
                        if (i > 0) addShiftEntry();
                        const entries = document.querySelectorAll('#shiftEntries .entry-item');
                        const e = entries[i];
                        if (e) {{
                            e.querySelector('.shift-time').value  = c[0].textContent.trim();
                            e.querySelector('.shift-entry').value = c[1].textContent.trim();
                        }}
                    }});
                }}

{import_run_js}

                saveToLocalStorage();
                hideImportDialog();
                alert('HTML imported successfully!');
            }} catch(err) {{
                console.error('Import error:', err);
                alert('Error parsing HTML: ' + err.message);
            }}
        }}

        function clearAllData() {{
            if (confirm('Are you sure you want to clear all data and start fresh? This cannot be undone.')) {{
                localStorage.removeItem('{storage_key}');
                location.reload();
            }}
        }}

        window.addEventListener('DOMContentLoaded', () => {{ loadFromLocalStorage(); }});
        if (!localStorage.getItem('{storage_key}')) {{
            addShiftEntry();
            addRunEntry();
        }}
    </script>
</body>
</html>
"""
    return html


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("config.json")
    if not config_path.exists():
        die(f"Config file not found: {config_path}")

    config_dir = config_path.parent
    output_dir = config_dir / "output"
    output_dir.mkdir(exist_ok=True)

    print(f"\nBuilding from: {config_path}")

    cfg           = load_config(config_path)
    sheets_cfg    = cfg.get("google_sheets", {})
    sheets_enabled = sheets_cfg.get("enabled", False)
    schema_hash   = compute_schema_hash(cfg)

    # --- Schema change detection ---
    hash_file = config_dir / ".schema_hash"
    if hash_file.exists():
        old_hash = hash_file.read_text().strip()
        if old_hash != schema_hash and sheets_enabled:
            print()
            print("  ┌─────────────────────────────────────────────────────────────────┐")
            print("  │  ⚠  SHEETS SCHEMA CHANGED                                       │")
            print("  │  The run field schema has changed since the last build.          │")
            print("  │  You MUST redeploy the Apps Script and update the Web App URL    │")
            print("  │  in the logbook tool's Google Sheets Export Settings, or the     │")
            print("  │  column order in your sheet will be wrong.                       │")
            print("  └─────────────────────────────────────────────────────────────────┘")
            print()
    hash_file.write_text(schema_hash)

    # --- Logo ---
    logo_cfg = cfg.get("logo", {})
    logo_tag = embed_logo(logo_cfg, config_dir) if logo_cfg else ""

    # --- Generate HTML ---
    html = build_html(cfg, logo_tag, sheets_enabled, schema_hash)
    html_out = output_dir / "logbook_generator.html"
    html_out.write_text(html, encoding="utf-8")
    print(f"  HTML: written to {html_out}")

    # --- Generate Apps Script (only if Sheets enabled) ---
    if sheets_enabled:
        gs = build_apps_script(cfg, schema_hash)
        gs_out = output_dir / "apps_script.gs"
        gs_out.write_text(gs, encoding="utf-8")
        print(f"  Apps Script: written to {gs_out}")
    else:
        print("  Apps Script: skipped (google_sheets.enabled is false)")

    print(f"\nDone. Schema hash: {schema_hash}\n")


if __name__ == "__main__":
    main()
