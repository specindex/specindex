# Connect SpecIndex Demo Form to a Google Sheet & `hello@specindex.ai`

This setup automatically appends all website demo requests to a **Google Sheet** and sends an instant email notification to **`hello@specindex.ai`**.

---

## 1. Create Your Google Sheet

1. Open [sheets.google.com](https://sheets.google.com/) (logged in as `asif@specindex.ai`).
2. Create a new spreadsheet named **SpecIndex Demo Requests**.
3. In Row 1, add these headers:
   - Column A: `Timestamp`
   - Column B: `First Name`
   - Column C: `Last Name`
   - Column D: `Work Email`
   - Column E: `Company`
   - Column F: `Product Categories`

---

## 2. Add Google Apps Script

1. In your Google Sheet, click **Extensions > Apps Script**.
2. Replace all existing code with this snippet:

```javascript
function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = JSON.parse(e.postData.contents);

    // 1. Append row to Google Sheet
    sheet.appendRow([
      data.timestamp || new Date(),
      data.firstName,
      data.lastName,
      data.email,
      data.company,
      data.categories,
    ]);

    // 2. Send email notification to hello@specindex.ai
    var subject = "New SpecIndex Demo Request: " + data.company;
    var body =
      "A new demo request was submitted on specindex.ai:\n\n" +
      "Name: " +
      data.firstName +
      " " +
      data.lastName +
      "\n" +
      "Email: " +
      data.email +
      "\n" +
      "Company: " +
      data.company +
      "\n" +
      "Categories: " +
      (data.categories || "None") +
      "\n" +
      "Time: " +
      data.timestamp +
      "\n\n" +
      "View in Google Sheet: " +
      SpreadsheetApp.getActiveSpreadsheet().getUrl();

    MailApp.sendEmail("hello@specindex.ai", subject, body);

    return ContentService.createTextOutput(
      JSON.stringify({ result: "success" })
    ).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(
      JSON.stringify({ result: "error", error: err.toString() })
    ).setMimeType(ContentService.MimeType.JSON);
  }
}
```

3. Click **Save** (disk icon).

---

## 3. Deploy as Web App

1. Click **Deploy > New deployment**.
2. Click the gear icon ⚙️ next to *Select type* and choose **Web app**.
3. Configure settings:
   - **Description:** `SpecIndex Lead Webhook`
   - **Execute as:** `Me`
   - **Who has access:** `Anyone` *(required so client-side web forms can post to it)*
4. Click **Deploy**, authorize permissions when prompted, and copy the generated **Web App URL**.

---

## 4. Add Web App URL to Next.js Project

Add the Web App URL to your `.env.local` file (or Next.js environment):

```env
NEXT_PUBLIC_SHEET_WEBHOOK_URL="https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec"
```

Rebuild/deploy Next.js with `npm run deploy`.
