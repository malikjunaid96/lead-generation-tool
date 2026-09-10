/**
 * ============================================================================
 * JD TECH SOLUTIONS - LEAD GENERATION & EMAIL MANAGEMENT PIPELINE
 * Author: Junaid ur Rehman (JD Tech Solutions)
 * Description: Automated pipeline connecting Gemini AI, Gmail API, and Google Sheets.
 * ============================================================================
 */

// ============================================================================
// CONFIGURATION
// ============================================================================
const CONFIG = {
  // 1. Google Gemini API Key (set in Apps Script Project Settings -> Script Properties)
  GEMINI_API_KEY: PropertiesService.getScriptProperties().getProperty("GEMINI_API_KEY") || "YOUR_GEMINI_API_KEY_HERE",

  // 2. Personal Notification Email (Where hot lead alerts are sent)
  PERSONAL_EMAIL: "malikjunaid5074462@gmail.com",

  // 3. Your Google Sheet ID
  SPREADSHEET_ID: "18PSkLS8XIgFvJC6nYV6YxGp58X-vt-IPeRsICGtup1U",

  // 4. Tab names inside the Google Sheet
  SHEET_NAME_APPROVED: "Approved Leads",
  SHEET_NAME_SCRAPED: "All Scraped Leads",

  // 5. Agency / Personal Branding
  AGENCY_NAME: "JD Tech Solutions",
  SENDER_NAME: "Junaid ur Rehman",
  SENDER_ROLE: "Founder & Lead Developer",

  // 6. Gemini Model Selection (Gemini 2.5 Flash)
  GEMINI_MODEL: "gemini-2.5-flash",

  // 7. Processed label in Gmail to prevent duplicate reply checking
  PROCESSED_LABEL: "JD-Tech-Processed"
};


// ============================================================================
// 1. WEBHOOK / API RECEIVER (doPost)
// ============================================================================
function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);

    if (!e || !e.postData || !e.postData.contents) {
      return createJsonResponse({
        status: "error",
        message: "Empty or invalid POST body received."
      }, 400);
    }

    let payload;
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return createJsonResponse({
        status: "error",
        message: "Invalid JSON format: " + parseErr.message
      }, 400);
    }

    // Extract lead data including Phone Number, Niche, and Area
    const leadData = {
      businessName: payload.businessName || payload.business_name || "Valued Business",
      phoneNumber: payload.phoneNumber || payload.phone_number || payload.phone || "",
      niche: payload.niche || payload.industry || "Local Business",
      area: payload.area || payload.location || payload.city || "Target Area",
      email: (payload.email || payload.contact_email || "").trim(),
      onlinePresence: payload.onlinePresence || payload.online_presence || "No active website",
      address: payload.address || ""
    };

    // Process lead: create draft (if email exists) and log to sheet with Phone, Niche & Area
    const result = generateAndSaveDraft(leadData);

    return createJsonResponse({
      status: "success",
      message: result.message,
      lead: leadData.businessName,
      phone: leadData.phoneNumber,
      niche: leadData.niche,
      area: leadData.area,
      email: leadData.email,
      draftId: result.draftId || null,
      subject: result.subject || null
    }, 200);

  } catch (error) {
    console.error("Error in doPost:", error);
    return createJsonResponse({
      status: "error",
      message: error.toString()
    }, 500);
  } finally {
    lock.releaseLock();
  }
}


// ============================================================================
// 2. AI DRAFT GENERATOR & SHEET LOGGER (generateAndSaveDraft)
// ============================================================================
function generateAndSaveDraft(leadData) {
  try {
    let draftId = null;
    let subject = "";
    let draftCreated = false;

    // 1. Only generate AI email and Gmail draft IF the business actually has an email
    if (leadData.email && leadData.email !== "") {
      const prompt = `
You are writing a cold outreach email on behalf of ${CONFIG.SENDER_NAME}, ${CONFIG.SENDER_ROLE} at ${CONFIG.AGENCY_NAME}.
Our agency specializes in high-performance modern frontend web development using React and Tailwind CSS.

TARGET LEAD DETAILS:
- Business Name: ${leadData.businessName}
- Niche/Industry: ${leadData.niche}
- Location/Area: ${leadData.area}
- Current Online Presence: ${leadData.onlinePresence}

OBJECTIVE:
Write a short, engaging, and highly converting cold email to this business.
Key talking points:
1. Notice that their current online presence is missing a fast, modern website.
2. Propose a modern, lightning-fast, mobile-optimized website built with React and Tailwind CSS that turns visitors into paying customers.
3. Keep it professional, conversational, and under 150 words.
4. Call to Action: A brief, no-pressure 10-minute chat or a free custom mockup preview.
5. Sign off from:
${CONFIG.SENDER_NAME}
${CONFIG.AGENCY_NAME}

OUTPUT FORMAT:
Do NOT output code blocks, JSON formatting, or brackets.
Strictly format your response like this:
SUBJECT: [Catchy, professional subject line here]
BODY:
[Complete email body text here]
`;

      const aiResponseText = (callGeminiApi(prompt) || "").trim();

      // Cleanly extract Subject and Body
      subject = `Web development proposal for ${leadData.businessName}`;
      let body = aiResponseText;

      if (/SUBJECT:/i.test(aiResponseText) && /BODY:/i.test(aiResponseText)) {
        const parts = aiResponseText.split(/BODY:/i);
        const subjPart = parts[0].replace(/SUBJECT:/i, "").trim();
        const bodyPart = parts.slice(1).join("BODY:").trim();
        if (subjPart) subject = subjPart;
        if (bodyPart) body = bodyPart;
      } else {
        const subjMatch = aiResponseText.match(/"subject"\s*:\s*"([^"]+)"/i);
        const bodyMatch = aiResponseText.match(/"body"\s*:\s*"([\s\S]+?)"\s*\}?$/i);
        if (subjMatch) subject = subjMatch[1].trim();
        if (bodyMatch) body = bodyMatch[1].replace(/\\n/g, "\n").replace(/\\"/g, '"').trim();
      }

      const draft = GmailApp.createDraft(leadData.email, subject, body);
      draftId = draft.getId();
      draftCreated = true;
      console.log(`Draft created for ${leadData.businessName} (${leadData.email}). Subject: ${subject}`);
    } else {
      console.log(`No email for ${leadData.businessName}. Skipping Gmail Draft creation.`);
    }

    // 2. Log to Google Sheet under "All Scraped Leads" with Niche and Area
    try {
      const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
      let logSheet = ss.getSheetByName(CONFIG.SHEET_NAME_SCRAPED);

      const headers = [
        "Business Name",
        "Phone Number",
        "Contact Email",
        "Niche",
        "Area",
        "Online Presence",
        "Draft Status / Subject",
        "Date Created"
      ];

      if (!logSheet) {
        logSheet = ss.insertSheet(CONFIG.SHEET_NAME_SCRAPED);
        logSheet.appendRow(headers);
        logSheet.getRange(1, 1, 1, headers.length).setFontWeight("bold").setBackground("#e8f0fe");
      } else {
        // Ensure header has all 8 columns including Phone, Niche, and Area
        const col5 = logSheet.getRange(1, 5).getValue();
        if (col5 !== "Area") {
          logSheet.getRange(1, 1, 1, headers.length).setValues([headers]);
          logSheet.getRange(1, 1, 1, headers.length).setFontWeight("bold").setBackground("#e8f0fe");
        }
      }

      const now = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
      
      // If no email, leave email cell empty ("") - do NOT put any gmail
      const emailValue = leadData.email ? leadData.email : "";
      const statusValue = draftCreated ? subject : "No Email (Call via Phone)";

      // Format Phone Number with leading apostrophe so Google Sheets treats it as plain text and avoids #ERROR!
      let phoneValue = leadData.phoneNumber ? String(leadData.phoneNumber).trim() : "";
      if (phoneValue && !phoneValue.startsWith("'")) {
        phoneValue = "'" + phoneValue;
      }

      logSheet.appendRow([
        leadData.businessName,
        phoneValue,
        emailValue,
        leadData.niche,
        leadData.area,
        leadData.onlinePresence,
        statusValue,
        now
      ]);
      console.log(`Lead logged to Sheet: ${leadData.businessName} | Phone: "${phoneValue}" | Niche: "${leadData.niche}" | Area: "${leadData.area}"`);
    } catch (sheetErr) {
      console.warn("Could not log to All Scraped Leads tab:", sheetErr);
    }

    return {
      draftId: draftId,
      subject: subject,
      message: draftCreated 
        ? "Draft email created and lead logged to Google Sheet with Phone, Niche & Area."
        : "Lead logged to Google Sheet with Phone, Niche & Area (No email found - call outreach)."
    };

  } catch (err) {
    console.error(`Failed to process lead ${leadData.businessName}:`, err);
    throw new Error(`Pipeline processing failed: ${err.message}`);
  }
}


// ============================================================================
// 3. INBOX MONITOR (checkReplies)
// ============================================================================
function checkReplies() {
  console.log("Starting checkReplies inbox scan...");

  try {
    const processedLabel = getOrCreateLabel(CONFIG.PROCESSED_LABEL);
    const query = `is:unread -label:${CONFIG.PROCESSED_LABEL}`;
    const threads = GmailApp.search(query, 0, 20);

    if (threads.length === 0) {
      console.log("No unread candidate threads found.");
      return;
    }

    console.log(`Found ${threads.length} unread thread(s) to inspect.`);

    threads.forEach(thread => {
      const messages = thread.getMessages();
      if (messages.length < 2) {
        thread.addLabel(processedLabel);
        return;
      }

      const myEmail = Session.getActiveUser().getEmail().toLowerCase();
      const hasOutboundFromMe = messages.some(msg => {
        return (msg.getFrom() || "").toLowerCase().includes(myEmail);
      });

      if (!hasOutboundFromMe) {
        thread.addLabel(processedLabel);
        return;
      }

      const latestMessage = messages[messages.length - 1];
      const sender = latestMessage.getFrom();
      const senderEmail = extractEmailAddress(sender);

      if (senderEmail.toLowerCase() === myEmail) {
        return;
      }

      const replyText = latestMessage.getPlainBody();
      const subject = thread.getFirstMessageSubject();

      console.log(`Analyzing reply from: ${sender} | Subject: "${subject}"`);

      const sentiment = analyzeReply(replyText);
      console.log(`Sentiment classified as: [${sentiment}] for ${senderEmail}`);

      if (sentiment === "APPROVED") {
        const businessName = inferBusinessName(subject, sender);
        processApprovedLead({
          businessName: businessName,
          phoneNumber: "",
          niche: "",
          area: "",
          contactEmail: senderEmail,
          replyText: replyText,
          date: new Date()
        });
      }

      thread.markRead();
      thread.addLabel(processedLabel);
    });

    console.log("checkReplies completed successfully.");

  } catch (err) {
    console.error("Error in checkReplies:", err);
  }
}


// ============================================================================
// 4. AI SENTIMENT ANALYZER (analyzeReply)
// ============================================================================
function analyzeReply(replyText) {
  if (!replyText || replyText.trim() === "") {
    return "REJECTED";
  }

  const prompt = `
You are an expert sales assistant analyzing an email reply to a cold outreach proposal for web development services.

EMAIL REPLY CONTENT:
"""
${replyText}
"""

TASK:
Classify the sender's intent into EXACTLY one of these two labels:
1. "APPROVED" - If the prospect shows interest, curiosity, asks for pricing, requests a call/meeting, asks for portfolio/examples, or is receptive.
2. "REJECTED" - If the prospect declines, says no, asks to be removed/unsubscribed, is angry, or the message is an automated out-of-office / bounce-back notice.

OUTPUT REQUIREMENT:
Respond ONLY with the word "APPROVED" or "REJECTED". Do not include any explanation or other text.
`;

  try {
    const rawResult = callGeminiApi(prompt);
    const cleaned = rawResult.trim().toUpperCase();

    if (cleaned.includes("APPROVED")) {
      return "APPROVED";
    }
    return "REJECTED";
  } catch (err) {
    console.error("Error in analyzeReply:", err);
    return "REJECTED";
  }
}


// ============================================================================
// 5. DATABASE LOGGING & NOTIFICATION (processApprovedLead)
// ============================================================================
function processApprovedLead(leadInfo) {
  try {
    const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
    let sheet = ss.getSheetByName(CONFIG.SHEET_NAME_APPROVED);

    const headers = [
      "Business Name",
      "Phone Number",
      "Contact Email",
      "Niche",
      "Area",
      "Date",
      "Reply Snippet",
      "Status"
    ];

    if (!sheet) {
      sheet = ss.insertSheet(CONFIG.SHEET_NAME_APPROVED);
      sheet.appendRow(headers);
      sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold").setBackground("#d4edda");
    } else {
      const col5 = sheet.getRange(1, 5).getValue();
      if (col5 !== "Area") {
        sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
        sheet.getRange(1, 1, 1, headers.length).setFontWeight("bold").setBackground("#d4edda");
      }
    }

    const formattedDate = Utilities.formatDate(leadInfo.date, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
    const replySnippet = (leadInfo.replyText || "").substring(0, 500);

    let phoneValue = leadInfo.phoneNumber ? String(leadInfo.phoneNumber).trim() : "";
    if (phoneValue && !phoneValue.startsWith("'")) {
      phoneValue = "'" + phoneValue;
    }

    sheet.appendRow([
      leadInfo.businessName,
      phoneValue,
      leadInfo.contactEmail || "",
      leadInfo.niche || "",
      leadInfo.area || "",
      formattedDate,
      replySnippet,
      "HOT LEAD - REPLIED"
    ]);
    console.log(`Lead logged to Approved Leads sheet: ${leadInfo.businessName}`);

    // Alert Email
    if (CONFIG.PERSONAL_EMAIL) {
      const subject = `🔥 Hot Lead Alert: ${leadInfo.businessName} Replied!`;
      const sheetUrl = `https://docs.google.com/spreadsheets/d/${CONFIG.SPREADSHEET_ID}/edit`;

      const emailBody = `
Hi Junaid,

Exciting news! A prospect has replied with positive interest to your outreach from ${CONFIG.AGENCY_NAME}.

---------------------------------------------------------
LEAD DETAILS:
---------------------------------------------------------
• Business Name: ${leadInfo.businessName}
• Niche:         ${leadInfo.niche || "Not specified"}
• Area:          ${leadInfo.area || "Not specified"}
• Phone Number:  ${leadInfo.phoneNumber || "Not listed"}
• Contact Email: ${leadInfo.contactEmail}
• Date/Time:     ${Utilities.formatDate(leadInfo.date, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm")}
• Google Sheet:  ${sheetUrl}

---------------------------------------------------------
PROSPECT REPLY:
---------------------------------------------------------
${leadInfo.replyText}

---------------------------------------------------------
Action Item: Open Gmail or call their phone to follow up while the lead is hot!

Best regards,
JD Tech Solutions Automation Bot
      `.trim();

      GmailApp.sendEmail(CONFIG.PERSONAL_EMAIL, subject, emailBody);
      console.log(`Alert email sent to ${CONFIG.PERSONAL_EMAIL}`);
    }

  } catch (err) {
    console.error("Error in processApprovedLead:", err);
  }
}


// ============================================================================
// 6. GEMINI API HELPER (callGeminiApi)
// ============================================================================
function callGeminiApi(prompt) {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${CONFIG.GEMINI_MODEL}:generateContent?key=${CONFIG.GEMINI_API_KEY}`;

  const payload = {
    contents: [
      {
        parts: [
          { text: prompt }
        ]
      }
    ],
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 800
    }
  };

  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  const response = UrlFetchApp.fetch(endpoint, options);
  const responseCode = response.getResponseCode();
  const responseText = response.getContentText();

  if (responseCode !== 200) {
    throw new Error(`Gemini API error [HTTP ${responseCode}]: ${responseText}`);
  }

  const json = JSON.parse(responseText);
  if (!json.candidates || json.candidates.length === 0) {
    throw new Error("Gemini returned an empty candidate response.");
  }

  const candidate = json.candidates[0];
  if (!candidate.content || !candidate.content.parts || candidate.content.parts.length === 0) {
    throw new Error("Gemini response missing text parts.");
  }

  return candidate.content.parts[0].text;
}


// ============================================================================
// 7. UTILITY & HELPER FUNCTIONS
// ============================================================================
function createJsonResponse(data, statusCode) {
  return ContentService.createTextOutput(JSON.stringify(data))
    .setMimeType(ContentService.MimeType.JSON);
}

function extractEmailAddress(rawFrom) {
  if (!rawFrom) return "";
  const match = rawFrom.match(/<([^>]+)>/);
  if (match) {
    return match[1].trim();
  }
  return rawFrom.trim();
}

function inferBusinessName(subject, sender) {
  if (subject) {
    const cleanSubj = subject.replace(/^(re:|fwd:)\s*/i, "").trim();
    if (cleanSubj.includes("regarding ")) {
      return cleanSubj.split("regarding ")[1].replace("'s web presence", "").trim();
    }
  }
  if (sender.includes("<")) {
    return sender.split("<")[0].replace(/"/g, "").trim();
  }
  return sender;
}

function getOrCreateLabel(labelName) {
  let label = GmailApp.getUserLabelByName(labelName);
  if (!label) {
    label = GmailApp.createLabel(labelName);
  }
  return label;
}

/**
 * ONE-CLICK FIX FOR EXISTING #ERROR! CELLS IN GOOGLE SHEET
 * Run this function once in Apps Script to instantly fix all red #ERROR! cells
 * by formatting Column B as Plain Text.
 */
function fixExistingPhoneErrors() {
  const ss = SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME_SCRAPED);
  if (!sheet) return;
  const lastRow = sheet.getLastRow();
  if (lastRow < 2) return;
  
  // Format Column B (Phone Number) as Plain Text
  sheet.getRange(2, 2, lastRow - 1, 1).setNumberFormat("@");
  console.log("✅ Fixed! Column B formatted as Plain Text.");
}
