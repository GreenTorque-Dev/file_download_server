# Email Capture Plugin

Collect emails from any website and automatically send time-limited download links for specific files.

---

## How It Works

1. Drop your files into `/files/` folder on the server
2. Paste one `<script>` tag on any webpage with `data-file` pointing to the file you want to send
3. User enters email → gets a private download link via email
4. Link expires after N hours (default: 24)

---

## Project Structure

```
email-plugin/
├── main.py           ← FastAPI backend
├── plugin.js         ← Embeddable JS plugin (served by backend)
├── demo.html         ← Demo page
├── requirements.txt
├── install.sh        ← Auto-installer for Ubuntu
├── .env.example      ← Copy to .env and fill in your values
├── plugin.db         ← SQLite DB (auto-created on first run)
└── files/            ← Put all downloadable files here
    ├── ebook.pdf
    ├── guide.pdf
    ├── template.zip
    └── ...           ← any file type works
```

---

## Setup (Manual)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env with your SMTP and server settings
```

### 3. Add your files
Place any files you want to distribute in the `files/` folder:
```bash
files/ebook.pdf
files/guide.pdf
files/template.zip
# Any file type — pdf, zip, docx, mp4, etc.
```

### 4. Run the server
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

---

## Setup (Auto — Ubuntu)

```bash
chmod +x install.sh
sudo ./install.sh
```

The installer will ask for your config, install everything, set up cron for auto-start, and launch the server.

---

## Embedding on Any Website

Paste ONE script tag on any page. Set `data-file` to the filename you want that page to send.

### Inline form
```html
<script src="https://yourserver.com/plugin.js"
        data-website="mysite"
        data-file="ebook.pdf"
        data-title="Download our free eBook"
        data-btn="Send me the eBook"
        data-theme="light"
        data-position="inline">
</script>
```

### Floating button (bottom-right)
```html
<script src="https://yourserver.com/plugin.js"
        data-website="mysite"
        data-file="guide.pdf"
        data-theme="dark"
        data-position="bottom-right">
</script>
```

### Center popup (auto-opens after 2s)
```html
<script src="https://yourserver.com/plugin.js"
        data-website="mysite"
        data-file="template.zip"
        data-position="center-popup">
</script>
```

### Multiple files on same website — just use different pages
```html
<!-- homepage sends ebook.pdf -->
<script src="https://yourserver.com/plugin.js"
        data-website="mysite"
        data-file="ebook.pdf">
</script>

<!-- blog page sends guide.pdf -->
<script src="https://yourserver.com/plugin.js"
        data-website="mysite"
        data-file="guide.pdf">
</script>
```

### Multiple websites — same server, just change data-website
```html
<!-- Website X -->
<script src="https://yourserver.com/plugin.js"
        data-website="website-x"
        data-file="report.pdf">
</script>

<!-- Website Y -->
<script src="https://yourserver.com/plugin.js"
        data-website="website-y"
        data-file="cheatsheet.pdf">
</script>
```

---

## Plugin Attributes

| Attribute       | Required | Description                                                  | Default               |
|-----------------|----------|--------------------------------------------------------------|-----------------------|
| `data-website`  | ✅        | Website name/key — saved in DB for tracking                  | `"default"`           |
| `data-file`     | ✅        | Exact filename in server's `/files/` folder                  | —                     |
| `data-theme`    | ❌        | `light` or `dark`                                           | `light`               |
| `data-title`    | ❌        | Heading text on the form                                     | `"Get your free file"`|
| `data-subtitle` | ❌        | Subheading text                                              | default text          |
| `data-btn`      | ❌        | Button label                                                 | `"Send me the link"`  |
| `data-position` | ❌        | `inline` / `bottom-right` / `bottom-left` / `center-popup`  | `inline`              |

---

## API Endpoints

| Endpoint                           | Method | Description                                  |
|------------------------------------|--------|----------------------------------------------|
| `/api/subscribe`                   | POST   | Capture email, create token, send email       |
| `/api/files`                       | GET    | List all available files in `/files/` folder  |
| `/download/{token}`                | GET    | Validate token, serve file                    |
| `/admin/subscribers?secret=...`    | GET    | View all subscribers and download links       |
| `/plugin.js`                       | GET    | Serves the embeddable plugin                  |
| `/demo`                            | GET    | Demo page                                     |

---

## Database

### `subscribers`
| Column     | Description                          |
|------------|--------------------------------------|
| email      | subscriber's email                   |
| website    | which website they came from         |
| file_name  | which file was requested             |
| ip         | their IP address                     |
| user_agent | their browser info                   |
| created_at | timestamp                            |

### `download_links`
| Column         | Description                        |
|----------------|------------------------------------|
| token          | unique UUID token                  |
| email          | subscriber email                   |
| website        | source website                     |
| file_name      | file that was sent                 |
| expires_at     | link expiry time                   |
| downloaded     | 1 if ever downloaded               |
| download_count | total times downloaded             |

---

## Adding a New File

Just copy the file to the `files/` folder — no config or restart needed:
```bash
cp myfile.pdf /opt/email-plugin/files/
```
Then use `data-file="myfile.pdf"` in your script tag.

---

## Gmail App Password Setup
1. Google Account → Security → 2-Step Verification → App Passwords
2. Create a new App Password
3. Use it as `SMTP_PASSWORD` in `.env`

---

## Manage Server (after install.sh)

```bash
/opt/email-plugin/start.sh    # start
/opt/email-plugin/stop.sh     # stop
/opt/email-plugin/status.sh   # check status
```