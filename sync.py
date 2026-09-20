import os
import sys
import json
import tempfile
import zipfile
import webbrowser
from datetime import datetime
from pathlib import Path

try:
    import dropbox
    from dropbox.exceptions import AuthError, ApiError
    from dropbox.files import WriteMode
except ImportError:
    print("Error: The 'dropbox' package is not installed.")
    print("Run: pip install -r requirements.txt")
    sys.exit(1)

SCRIPT_DIR = Path(__file__).resolve().parent
GAMES_FILE = SCRIPT_DIR / "games.json"
DROPBOX_CONFIG_FILE = SCRIPT_DIR / "dropbox_config.json"
BACKUPS_DIR = SCRIPT_DIR / "_local_backups"
CHUNK_SIZE = 4 * 1024 * 1024


def load_games():
    if not GAMES_FILE.exists():
        default_games = [
            {
                "id": 1,
                "name": "Example Game",
                "save_path": "%LOCALAPPDATA%\\DeveloperName\\GameName\\Saved\\SaveGames"
            }
        ]
        with open(GAMES_FILE, "w", encoding="utf-8") as f:
            json.dump(default_games, f, indent=2, ensure_ascii=False)
        return default_games

    try:
        with open(GAMES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {GAMES_FILE.name}: {e}")
        return []


def save_games(games):
    with open(GAMES_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2, ensure_ascii=False)


def resolve_path(path_str):
    return Path(os.path.expandvars(os.path.expanduser(path_str)))


def setup_dropbox():
    print("\n" + "=" * 60)
    print(" DROPBOX API SETUP")
    print("=" * 60)
    print("Please provide your App Key and App Secret from the Dropbox Developer Console.\n")

    app_key = input("Enter App Key: ").strip()
    app_secret = input("Enter App Secret: ").strip()

    if not app_key or not app_secret:
        print("Invalid App Key or App Secret. Setup aborted.")
        return {}

    try:
        auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(
            app_key,
            app_secret,
            token_access_type="offline"
        )
        authorize_url = auth_flow.start()

        print("\n" + "-" * 60)
        print("Opening browser for authorization...")
        print(f"If it doesn't open automatically, visit:\n{authorize_url}")
        print("-" * 60)

        try:
            webbrowser.open(authorize_url)
        except Exception:
            pass

        auth_code = input("\nEnter the authorization code: ").strip()
        if not auth_code:
            print("No authorization code entered. Setup aborted.")
            return {}

        oauth_result = auth_flow.finish(auth_code)

        config = {
            "app_key": app_key,
            "app_secret": app_secret,
            "refresh_token": oauth_result.refresh_token
        }

        with open(DROPBOX_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        print("\nSetup completed successfully!")
        print(f"Credentials saved to {DROPBOX_CONFIG_FILE.name}\n")
        return config

    except Exception as e:
        print(f"\nOAuth authorization error: {e}")
        return {}


def check_dropbox_permissions(dbx):
    try:
        test_path = "/.perm_check"
        dbx.files_upload(b"1", test_path, mode=WriteMode.overwrite)
        try:
            dbx.files_delete_v2(test_path)
        except Exception:
            pass
        return True
    except Exception as e:
        err_msg = str(e)
        if "files.content.write" in err_msg or "EOF" in err_msg or "SSLError" in err_msg:
            print("\n" + "!" * 65)
            print(" WARNING: MISSING DROPBOX WRITE PERMISSIONS")
            print("!" * 65)
            print("Your Dropbox App lacks the required write permission.")
            print("To fix this:")
            print("1. Visit https://www.dropbox.com/developers/apps")
            print("2. Open your App and go to the 'Permissions' tab")
            print("3. Check the following scopes:")
            print("   - [x] files.content.write")
            print("   - [x] files.content.read")
            print("4. Click the 'Submit' button at the bottom.")
            print("5. Reconnect to generate a new token (Option C in the menu).")
            print("!" * 65 + "\n")
            return False
        return True


def get_dropbox_client():
    if not DROPBOX_CONFIG_FILE.exists():
        print("Dropbox configuration file not found. Starting setup...")
        config = setup_dropbox()
        if not config:
            return None
    else:
        try:
            with open(DROPBOX_CONFIG_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception as e:
            print(f"Error reading {DROPBOX_CONFIG_FILE.name}: {e}")
            return None

    app_key = config.get("app_key")
    app_secret = config.get("app_secret")
    refresh_token = config.get("refresh_token")

    if not (app_key and app_secret and refresh_token):
        print("Incomplete credentials in configuration file. Reconfiguration required.")
        config = setup_dropbox()
        if not config:
            return None
        app_key = config.get("app_key")
        app_secret = config.get("app_secret")
        refresh_token = config.get("refresh_token")

    try:
        dbx = dropbox.Dropbox(
            app_key=app_key,
            app_secret=app_secret,
            oauth2_refresh_token=refresh_token
        )
        account = dbx.users_get_current_account()
        print(f"Connected to Dropbox as: {account.name.display_name} ({account.email})")

        if not check_dropbox_permissions(dbx):
            print("Would you like to re-authorize now to update permissions? (y/n)")
            if input("> ").strip().lower() == "y":
                new_config = setup_dropbox()
                if new_config:
                    return get_dropbox_client()

        return dbx
    except AuthError as e:
        print(f"Dropbox authentication error: {e}")
        print("Would you like to re-enter your credentials? (y/n)")
        if input("> ").strip().lower() == "y":
            new_config = setup_dropbox()
            if new_config:
                return get_dropbox_client()
        return None
    except Exception as e:
        print(f"Failed to connect to Dropbox: {e}")
        return None


def zip_path(source_path, zip_file_path):
    with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        if source_path.is_file():
            zipf.write(source_path, arcname=source_path.name)
        elif source_path.is_dir():
            for root, _, files in os.walk(source_path):
                for file in files:
                    file_path = Path(root) / file
                    zipf.write(file_path, arcname=file_path.relative_to(source_path))


def extract_zip(zip_file_path, destination_path):
    destination_path.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_file_path, "r") as zipf:
        zipf.extractall(destination_path)


def create_local_backup(local_path, game_id):
    if not local_path.exists() or (local_path.is_dir() and not any(local_path.iterdir())):
        return None

    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUPS_DIR / f"game_{game_id}_backup_{timestamp}.zip"

    try:
        zip_path(local_path, backup_file)
        print(f"Local safety backup created: {backup_file.name}")
        return backup_file
    except Exception as e:
        print(f"Warning: Could not create local safety backup: {e}")
        return None


def upload_file(dbx, local_file_path, dropbox_path):
    file_size = local_file_path.stat().st_size
    print(f"Uploading to Dropbox: {dropbox_path} ({file_size / (1024 * 1024):.2f} MB)...")

    try:
        with open(local_file_path, "rb") as f:
            if file_size <= CHUNK_SIZE:
                dbx.files_upload(f.read(), dropbox_path, mode=WriteMode.overwrite)
            else:
                upload_session = dbx.files_upload_session_start(f.read(CHUNK_SIZE))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session.session_id,
                    offset=f.tell()
                )
                commit = dropbox.files.CommitInfo(path=dropbox_path, mode=WriteMode.overwrite)

                while f.tell() < file_size:
                    if (file_size - f.tell()) <= CHUNK_SIZE:
                        dbx.files_upload_session_finish(f.read(CHUNK_SIZE), cursor, commit)
                    else:
                        dbx.files_upload_session_append_v2(f.read(CHUNK_SIZE), cursor)
                        cursor.offset = f.tell()
                        percent = (cursor.offset / file_size) * 100
                        print(f"  -> Upload progress: {percent:.1f}%", end="\r")

                print("  -> Upload progress: 100.0%    ")

        print("Upload completed successfully!")
        return True

    except Exception as e:
        err_msg = str(e)
        print(f"\nUpload failed: {e}")
        if "files.content.write" in err_msg or "EOF" in err_msg or "SSLError" in err_msg:
            print("Reason: Your Dropbox App does not have 'files.content.write' permission enabled,")
            print("or the token was generated before enabling permissions.")
            print("Please check your App settings on Dropbox and run option 'C' to reconnect.")
        return False


def download_file(dbx, dropbox_path, local_save_path):
    print(f"Downloading from Dropbox: {dropbox_path}...")
    try:
        metadata, response = dbx.files_download(dropbox_path)
        with open(local_save_path, "wb") as f:
            f.write(response.content)
        print(f"Download completed ({metadata.size / (1024 * 1024):.2f} MB)")
        return True
    except ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            print(f"No cloud save found on Dropbox at: {dropbox_path}")
        else:
            print(f"API error during download: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error during download: {e}")
        return False


def handle_upload(dbx, game):
    local_path = resolve_path(game["save_path"])
    print(f"\n--- UPLOAD SAVE: {game['name']} ---")
    print(f"Local path: {local_path}")

    if not local_path.exists():
        print(f"Error: Local path does not exist:\n  {local_path}")
        print("Make sure the game has saved files or check the path in games.json.")
        return

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip = Path(temp_dir) / "save.zip"
        print("Compressing save files...")
        zip_path(local_path, temp_zip)
        upload_file(dbx, temp_zip, f"/{game['id']}/save.zip")


def handle_download(dbx, game):
    local_path = resolve_path(game["save_path"])
    print(f"\n--- DOWNLOAD SAVE: {game['name']} ---")
    print(f"Destination: {local_path}")

    dropbox_path = f"/{game['id']}/save.zip"

    try:
        metadata = dbx.files_get_metadata(dropbox_path)
        print(f"Found on Dropbox: {metadata.name} (Modified: {metadata.server_modified})")
    except ApiError as e:
        if e.error.is_path() and e.error.get_path().is_not_found():
            print(f"No cloud save found on Dropbox for ID {game['id']} ({dropbox_path}).")
            return
        else:
            print(f"Error checking cloud file: {e}")
            return

    create_local_backup(local_path, game["id"])

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_zip = Path(temp_dir) / "save.zip"
        if not download_file(dbx, dropbox_path, temp_zip):
            return

        print(f"Extracting files to: {local_path}")
        try:
            extract_zip(temp_zip, local_path)
            print("Save files restored successfully!")
        except Exception as e:
            print(f"Extraction error: {e}")


def add_game(games):
    print("\n" + "=" * 50)
    print(" ADD NEW GAME")
    print("=" * 50)

    name = input("Game name: ").strip()
    if not name:
        print("Invalid game name.")
        return

    print("\nTip: You can use environment variables like %LOCALAPPDATA%, %APPDATA%, %USERPROFILE%")
    print("Example: %LOCALAPPDATA%\\DeveloperName\\GameName\\Saved\\SaveGames")
    save_path = input("Local save path: ").strip()
    if not save_path:
        print("Invalid save path.")
        return

    existing_ids = [g.get("id", 0) for g in games if isinstance(g.get("id"), int)]
    next_id = max(existing_ids, default=0) + 1

    custom_id_str = input(f"Numeric ID for this game (Press Enter for {next_id}): ").strip()
    if custom_id_str:
        try:
            assigned_id = int(custom_id_str)
        except ValueError:
            print("Invalid number. Using default ID.")
            assigned_id = next_id
    else:
        assigned_id = next_id

    for g in games:
        if g.get("id") == assigned_id:
            print(f"ID {assigned_id} was already assigned to '{g.get('name')}'. Updating entry.")
            g["name"] = name
            g["save_path"] = save_path
            save_games(games)
            print("Game updated!")
            return

    games.append({
        "id": assigned_id,
        "name": name,
        "save_path": save_path
    })
    save_games(games)
    print(f"Game '{name}' added with ID {assigned_id}!")


def remove_game(games, target_id=None):
    if not games:
        print("No games in the list to remove.")
        return

    if target_id is None:
        print("\n" + "=" * 50)
        print(" REMOVE A GAME")
        print("=" * 50)
        for g in games:
            print(f"  {g.get('id')}) {g.get('name')}")
        choice = input("\nEnter the ID of the game to remove (0 to cancel): ").strip()
        try:
            target_id = int(choice)
        except ValueError:
            print("Invalid ID.")
            return

        if target_id == 0:
            return

    game_to_remove = None
    for g in games:
        if g.get("id") == target_id:
            game_to_remove = g
            break

    if not game_to_remove:
        print(f"No game found with ID {target_id}.")
        return

    confirm = input(f"Are you sure you want to remove '{game_to_remove['name']}'? (y/n): ").strip().lower()
    if confirm == "y":
        games.remove(game_to_remove)
        save_games(games)
        print(f"Game '{game_to_remove['name']}' removed successfully!")
    else:
        print("Removal cancelled.")


def main():
    
    dbx = get_dropbox_client()
    if not dbx:
        print("\nCannot proceed without Dropbox authentication.")
        print("Refer to README.md for setup instructions.")
        input("\nPress Enter to exit...")
        return

    while True:
        games = load_games()
        games.sort(key=lambda x: x.get("id", 9999))

        print("\n" + "-" * 55)
        print("Which game do you want to sync?")
        for g in games:
            print(f"  {g.get('id')}) {g.get('name')}")
        print("\nOptions:")
        print("  A) Add a new game")
        print("  R) Remove a game")
        print("  C) Reconfigure Dropbox account")
        print("  0) Exit")
        print("-" * 55)

        choice = input("Enter choice: ").strip()

        if choice == "0":
            print("\nGoodbye!")
            break
        elif choice.upper() == "A":
            add_game(games)
            continue
        elif choice.upper() == "R":
            remove_game(games)
            continue
        elif choice.upper() == "C":
            setup_dropbox()
            dbx = get_dropbox_client()
            continue

        selected_game = None
        try:
            chosen_id = int(choice)
            for g in games:
                if g.get("id") == chosen_id:
                    selected_game = g
                    break
        except ValueError:
            selected_game = None

        if not selected_game:
            print("Invalid choice. Please try again.")
            continue

        print(f"\n[ Selected Game: {selected_game['name']} (ID: {selected_game['id']}) ]")
        print("What would you like to do?")
        print("  1) Download from Cloud (Restore)")
        print("  2) Upload to Cloud (Backup)")
        print("  3) Remove from list")
        print("  0) Back to main menu")

        action = input("Choice (1/2/3/0): ").strip()
        if action == "1":
            handle_download(dbx, selected_game)
        elif action == "2":
            handle_upload(dbx, selected_game)
        elif action == "3":
            remove_game(games, selected_game["id"])
        elif action == "0":
            continue
        else:
            print("Invalid action.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nExiting.")
