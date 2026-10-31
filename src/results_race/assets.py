"""`results-race fetch-assets`: download the logos the result sheet can draw. They are not bundled with the project
(they are a government's and a board's marks, not ours to redistribute): each user fetches them onto their own machine."""
import urllib.request
from pathlib import Path

SAVE_AS = {"seal": "seal", "board-logo": "board-logo"}  # base file names; the extension follows the URL


def default_dir():
    import os
    base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local/share")
    return Path(base) / "results-race" / "assets"


def _download(url):
    req = urllib.request.Request(url, headers={"User-Agent": "results-race (+https://github.com/)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def fetch_assets(urls, folder, fetch=_download, say=print):
    """urls: {"seal": url, "board-logo": url}. Returns how many were saved; one failing never stops the rest."""
    folder = Path(folder)
    saved = 0
    for name, url in urls.items():
        if not url:
            continue
        ext = Path(url.split("?")[0]).suffix.lower() or ".png"
        try:
            data = fetch(url)
            folder.mkdir(parents=True, exist_ok=True)
            (folder / f"{name}{ext}").write_bytes(data)
            say(f"saved {folder / (name + ext)}  ({len(data):,} bytes)")
            saved += 1
        except Exception as e:  # noqa: BLE001 - any network/file problem is reported, not fatal
            say(f"could not fetch {name} from {url}: {e}")
    return saved
