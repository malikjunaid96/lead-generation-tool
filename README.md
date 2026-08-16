# Lead Generation Tool

A Streamlit app that searches Google Maps for a business type + area, pulls each
business's name/phone/website, scans each website for a public contact email, and
lets you export everything to CSV or Excel.

## How it works

1. You enter a business type ("Roofers") and an area ("Austin, TX").
2. The app queries the **Places API (New)** — Google's current, ToS-compliant way
   to search Maps data programmatically — for matching businesses.
3. For every business that has a website, the app fetches the homepage (and a
   contact/about page, if the homepage has no visible email) and pulls out any
   email address it finds, filtering out things like `logo@2x.png` or
   `email@example.com`.
4. Results land in a table you can download as `.csv` or `.xlsx`.

### A note on the scraping approach

You gave me the choice between the official Places API and a headless-browser
(Selenium/Playwright) scraper to avoid needing an API key at all. I went with
the API, for a few reasons worth knowing:

- Scraping Google Maps' website directly breaks Google's Terms of Service, and
  Google actively fingerprints and blocks that kind of automated traffic, so a
  scraper like that needs frequent maintenance as they change their page/bot
  detection.
- The Places API's free monthly quota (see **Costs** below) comfortably covers
  normal lead-gen use, so you likely won't pay anything — which was presumably
  the point of avoiding a "paid API" in the first place.

The website/email-scraping half of this app (`email_scraper.py`) is
independent of this choice and works the same either way.

## 1. Get a Google Maps API key

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) and sign in.
2. Create a new project (top bar → **Select a project** → **New Project**), or pick an existing one.
3. **Enable billing** for the project (left menu → **Billing** → link a payment
   method). Google requires a card on file to issue a key at all, even though
   there's a real free monthly quota — see **Costs** below.
4. Go to **APIs & Services → Library**, search for **"Places API (New)"**, and click **Enable**.
5. Go to **APIs & Services → Credentials → Create Credentials → API key**. Copy the key.
6. *(Recommended)* Click into the new key and, under **API restrictions**,
   limit it to **Places API (New)** only — so the key is harmless if it ever
   leaks or gets committed to a repo by accident.

## 2. Install

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 3. Add your API key and set a password

### API Key
Either:

- Copy `.env.example` to `.env` and paste your key in, **or**
- Just paste it into the "Google Maps API Key" box in the app's sidebar each time you run it.

### Password Protection (Optional)
The app includes built-in password protection. By default, the password is `password123`. 

To set a custom password:

1. Create or edit your `.env` file
2. Add the line: `APP_PASSWORD=your_secure_password_here`
3. Replace `your_secure_password_here` with your desired password
4. Restart the app

The password will be required each time you or anyone else opens the app. Users can log out using the logout button in the sidebar.

## 4. Run it

```bash
streamlit run app.py
```

This opens the app at `http://localhost:8501`. Enter a business type and area,
click **Start Lead Generation**, and download the results once it finishes.

## 5. Deploy to Streamlit Cloud (Access from Anywhere!)

Want to access your app from any device, anywhere? Deploy it to **Streamlit Cloud** for free!

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete step-by-step instructions.

**Key benefits:**
- ✅ Access from any device, anywhere
- ✅ No need to keep your computer running
- ✅ Share the link with your team
- ✅ Free hosting tier available
- ✅ Automatic updates when you push to GitHub

## Costs

Since March 2025, Google prices Places API (New) per field, not as one flat
product — each group of fields ("SKU") carries its own free monthly quota
instead of sharing one $200/month credit. Phone numbers and websites are
**Enterprise**-tier fields, which get **1,000 free calls/month**; since each
call in this app returns up to 20 businesses at once, that's roughly **20,000
businesses/month before anything is billed**. Past that, Google's list price
is roughly in the $30–$40-per-1,000-calls range at the Enterprise tier — check
the [current Places API pricing page](https://mapsplatform.google.com/pricing/)
for exact numbers, since Google updates these periodically. You can also set a
budget alert (or a hard cap) for the project in Cloud Console → Billing if you
want a safety net.

## Good to know

- **robots.txt**: the email scraper checks each site's `robots.txt` before
  visiting a page and skips anything disallowed. It also waits between
  requests (adjustable in the sidebar) to avoid hammering any one site.
- **Using the emails you collect**: this app only *finds* public contact
  emails — it doesn't send anything. If you go on to email these leads,
  commercial-email rules (like CAN-SPAM in the US, or GDPR/PECR if you're
  contacting people in the EU/UK) will apply to that outreach, so it's worth a
  quick check of what's required in your case (e.g. a working unsubscribe
  link, accurate sender info). This isn't legal advice, just a heads-up.
- **Missing data is expected, not a bug**: many small-business sites only have
  a contact form, or load their content with JavaScript this scraper can't
  execute — when no email is found, or a business has no listed website, that
  cell is simply left blank and the run continues.

## Project files

| File                     | Purpose                                                          |
|--------------------------|-------------------------------------------------------------------|
| `app.py`                 | Streamlit UI — inputs, orchestration, results table, downloads   |
| `google_maps_client.py`  | Talks to the Places API (New) `searchText` endpoint              |
| `email_scraper.py`       | Fetches a website + contact page, extracts emails                |
| `requirements.txt`       | Python dependencies                                              |
| `.env.example`           | Template for storing your API key locally                        |

## Troubleshooting

- **"Google Places API error (403)"** — usually means the API isn't enabled
  for your project, or billing isn't linked yet. Re-check steps 3–4 above.
- **"Google Places API error (400)"** — usually an invalid, missing, or
  over-restricted API key (e.g. restricted to the wrong API).
- **No emails found for most businesses** — normal. Many sites only offer a
  contact form, or hide addresses behind JavaScript this scraper doesn't
  execute; that's a real ceiling on any regex-based scraper, not a bug here.
- **The run feels slow** — most of the time goes to visiting each business's
  website one at a time with a polite delay in between. Lower "Max businesses
  to fetch" in the sidebar for a quicker run.
