import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from time import sleep
from zipfile import ZipFile

HEADERS = {
    "User-Agent": "Mozilla/5.0"
}

def clean_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).replace(" ", "_")

def download_image(url, path):
    try:
        r = requests.get(url, headers=HEADERS, stream=True, timeout=20)
        r.raise_for_status()
        with open(path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
    except Exception as e:
        print(f"❌ Erreur téléchargement image : {e}")

def get_metadata(soup, title, cover_url, folder_name):
    summary_block = soup.select_one("div.summary__content")
    summary = summary_block.text.strip() if summary_block else ""

    alt_name = ""
    for item in soup.select("div.post-content_item"):
        if "Alternative" in item.text:
            alt_block = item.select_one("div.summary-content")
            alt_name = alt_block.text.strip() if alt_block else ""

    authors = [a.text.strip() for a in soup.select("div.author-content a")]
    artists = [a.text.strip() for a in soup.select("div.artist-content a")]
    genres = [g.text.strip() for g in soup.select("div.genres-content a")]

    release_year = None
    for item in soup.select("div.post-content_item"):
        if "Date de sortie" in item.text:
            release_block = item.select_one("div.summary-content")
            if release_block and release_block.text.strip().isdigit():
                release_year = int(release_block.text.strip())

    status = "Inconnu"
    for item in soup.select("div.post-content_item"):
        if "Statut" in item.text:
            status_block = item.select_one("div.summary-content")
            status = status_block.text.strip() if status_block else "Inconnu"

    metadata = {
        "title": title,
        "alt_name": alt_name,
        "authors": authors,
        "artists": artists,
        "genres": genres,
        "release_year": release_year,
        "status": status,
        "summary": summary,
        "thumbnail_path": f"{folder_name}/cover.jpg"
    }

    with open(os.path.join(folder_name, "metadata.json"), "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

def get_chapter_links(soup):
    chap_links = []
    nav = soup.find("div", id="init-links")
    if not nav:
        return []

    first_btn = nav.find("a", id="btn-read-last")
    last_btn = nav.find("a", id="btn-read-first")

    if not first_btn or not last_btn:
        return []

    first_url = first_btn['href']
    last_url = last_btn['href']

    base_url = '/'.join(first_url.rstrip('/').split('/')[:-1])
    first_match = re.search(r'chapitre-(\d+)', first_url)
    last_match = re.search(r'chapitre-(\d+)', last_url)

    if not first_match or not last_match:
        return []

    first_num = int(first_match.group(1))
    last_num = int(last_match.group(1))

    for i in range(first_num, last_num + 1):
        chap_links.append(f"{base_url}/chapitre-{i}/")

    return chap_links[::-1]

def download_chapter(chap_url, folder_name, chap_index):
    try:
        r = requests.get(chap_url, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        img_tags = soup.select("div.page-break.no-gaps img")

        chap_dir = os.path.join(folder_name, f"Chapitre_{str(chap_index).zfill(3)}")
        os.makedirs(chap_dir, exist_ok=True)

        for idx, img in enumerate(img_tags, start=1):
            src = img.get("src")
            if not src:
                continue
            ext = os.path.splitext(src)[1].split("?")[0]
            img_path = os.path.join(chap_dir, f"{str(idx).zfill(3)}{ext}")
            download_image(src, img_path)

        return True
    except Exception as e:
        print(f"❌ Erreur téléchargement chapitre {chap_index} : {e}")
        return False

def zip_folder(folder_name):
    zip_name = f"{folder_name}.zip"
    with ZipFile(zip_name, "w") as zipf:
        for root, _, files in os.walk(folder_name):
            for file in files:
                full_path = os.path.join(root, file)
                arcname = os.path.relpath(full_path, folder_name)
                zipf.write(full_path, arcname)
    print(f"✅ ZIP créé : {zip_name}")

def process_url(url):
    print(f"🔍 Traitement : {url}")
    try:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
    except Exception as e:
        print(f"❌ Erreur HTTP : {e}")
        return

    title_tag = soup.select_one("div.post-title h1")
    if not title_tag:
        print("❌ Titre introuvable")
        return

    title = title_tag.text.strip()
    folder_name = clean_filename(title)
    os.makedirs(folder_name, exist_ok=True)

    cover_tag = soup.select_one("div.summary_image img")
    cover_url = cover_tag["src"] if cover_tag else None
    if cover_url:
        download_image(cover_url, os.path.join(folder_name, "cover.jpg"))

    print(f"✅ Metadata OK pour : {title}")
    get_metadata(soup, title, cover_url, folder_name)

    chapter_links = get_chapter_links(soup)
    print(f"🔗 {len(chapter_links)} chapitres trouvés")

    for i, chap_url in enumerate(chapter_links, start=1):
        print(f"📥 Téléchargement Chapitre {i}")
        ok = download_chapter(chap_url, folder_name, i)
        if not ok:
            break
        sleep(1)

    zip_folder(folder_name)

def main():
    if not os.path.exists("mangas.txt"):
        print("❌ Fichier mangas.txt manquant")
        return

    with open("mangas.txt", "r", encoding="utf-8") as f:
        urls = [line.strip() for line in f if line.strip()]

    for url in urls:
        process_url(url)

if __name__ == "__main__":
    main()
