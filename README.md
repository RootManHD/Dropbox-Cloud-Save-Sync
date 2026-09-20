# 🎮 Cloud Save Sync - Dropbox

A lightweight Python utility to synchronize PC game saves with **Dropbox**, functioning as a private, custom Cloud Save system across multiple PCs.

---

## ✨ Features

- **Bi-directional Sync**:
  - ⬆️ **Upload / Backup**: Compresses local game saves into a zip archive and uploads them to Dropbox (with chunked streaming support for large save files).
  - ⬇️ **Download / Restore**: Fetches and extracts cloud saves directly into your game's local save directory.
- **🛡️ Safety First**: Automatically creates a local safety backup in `_local_backups` before extracting any downloaded files over existing saves.
- **🔑 Persistent Auth (OAuth2 Refresh Token)**: Authenticate once. The script uses refresh tokens so credentials don't expire every 4 hours.
- **💻 Windows Environment Variable Expansion**: Supports paths using `%LOCALAPPDATA%`, `%APPDATA%`, `%USERPROFILE%`, `%DOCUMENTS%`.
- **➕ Easy Management**: Add and remove games via `games.json` or interactively from the console menu.

---

## 🚀 Requirements

- **Python 3.8+** (make sure to select *"Add Python to PATH"* during installation on Windows).
- Windows, macOS, or Linux.

---

## 📦 Installation

1. Clone or download this repository.
2. Open a terminal in the project folder and install requirements:
   ```bash
   pip install -r requirements.txt
   ```

---

## ⚙️ Initial Dropbox Setup

This tool uses the official **Dropbox API** with an offline **Refresh Token** so you only need to authenticate once without your access token expiring every 4 hours. Initial setup takes about 2 minutes.

### 1. Create a Dropbox App
1. Go to the Dropbox Developer App Console:
   👉 **[https://www.dropbox.com/developers/apps](https://www.dropbox.com/developers/apps)**
   *(Log in to your Dropbox account if prompted)*.
2. Click the blue button in the top right: **Create app**.
3. Select the following settings:
   - **1. Choose an API**: select **Scoped access**.
   - **2. Choose the type of access**:
     - Select **App folder** *(Recommended: the script will only have access to its dedicated `/Apps/<AppName>` folder, keeping your other Dropbox files isolated)*.
     - *Or select **Full Dropbox** if you prefer having folders in your Dropbox root.*
   - **3. Name your app**: choose a unique name (e.g., `GameSaveCloudSync-YourName`).
4. Click **Create app**.

### 2. Configure Required Permissions (IMPORTANT)
1. On your newly created app page, click the **Permissions** tab.
2. Under the **Files and folders** section, check both:
   - ✅ `files.content.write` (allows uploading save files)
   - ✅ `files.content.read` (allows downloading save files)
3. Scroll to the bottom of the page and click **Submit** to save changes.

### 3. Retrieve App Key and App Secret
1. Go back to the **Settings** tab of your app.
2. Locate:
   - **App key** (e.g., `ab12cd34ef56gh7`)
   - **App secret**: click *Show* to reveal it (e.g., `jk89lm01no23pq4`)

### 4. Authenticate via Script
When you launch `python sync.py` (or `run_sync.bat`) for the first time:
1. Paste your **App Key** and **App Secret**.
2. The script will automatically open your browser. Click **Allow** / **Authorize**.
3. Copy the authorization code shown in your browser and paste it into the console.

The script will automatically generate and save your persistent Refresh Token in `dropbox_config.json`. You will not need to authenticate again!

---

## 🎮 Game Configuration (`games.json`)

Configure your games in `games.json`:

```json
[
  {
    "id": 1,
    "name": "Example Game",
    "save_path": "%LOCALAPPDATA%\\DeveloperName\\GameName\\Saved\\SaveGames"
  }
]
```

*Note: You can also add and remove games interactively inside the script.*

---

## ▶️ Usage

Double-click **`run_sync.bat`** (on Windows) or run in terminal:

```bash
python sync.py
```

Select your game by typing its number:
- `1` ⬇️ Download from Cloud (Restore)
- `2` ⬆️ Upload to Cloud (Backup)
- `3` ❌ Remove from list

You can also use option `A` to add a new game or option `R` to remove an existing game directly from the main menu.

---

## 🔒 Security

- Your `dropbox_config.json` and any backups in `_local_backups/` are automatically excluded by `.gitignore` to prevent leaking private credentials.
