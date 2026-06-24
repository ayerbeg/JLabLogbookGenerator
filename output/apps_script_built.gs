/**
 * PionCT Logbook -> Google Sheets bridge.
 * Schema hash: f7fb044dfc4af058
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

const SHARED_SECRET = 'CHANGE_ME_TO_SOMETHING_PRIVATE';

const HEADERS = [
  "Run Number",
  "Date",
  "Start Time",
  "End Time",
  "Total Time",
  "Target",
  "Beam Current (uA)",
  "HMS P [GeV]",
  "SHMS P [GeV]",
  "HMS angle [deg]",
  "SHMS angle [deg]",
  "Number of Events (M)",
  "Trigger Rate [Hz]",
  "Live Time [%]",
  "Plots OK?",
  "DAQ config",
  "Prescales Enabled",
  "Comments",
  "Full Replay Started?"
];

function doPost(e) {
  try {
    const body = JSON.parse(e.postData.contents);

    if (body.secret !== SHARED_SECRET) {
      return jsonResponse({ ok: false, error: 'Invalid secret.' });
    }

    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();

    if (sheet.getLastRow() === 0) {
      sheet.appendRow(HEADERS);
    }

    const run = body.run || {};
    const row = [
      run.number        || '',
      run.date        || '',
      run.start        || '',
      run.stop        || '',
      run.length        || '',
      run.target        || '',
      run.current        || '',
      run.hmsP        || '',
      run.shmsP        || '',
      run.hmsAngle        || '',
      run.shmsAngle        || '',
      run.events        || '',
      run.triggerRate        || '',
      run.livetime        || '',
      ''  // Plots OK? — filled manually in sheet,
      run.config        || '',
      ''  // Prescales Enabled — filled manually in sheet,
      run.comments        || '',
      ''  // Full Replay Started? — filled manually in sheet,
    ];

    sheet.appendRow(row);
    return jsonResponse({ ok: true, rowAppended: sheet.getLastRow() });

  } catch (err) {
    return jsonResponse({ ok: false, error: err.message });
  }
}

function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
