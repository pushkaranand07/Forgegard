import argparse
import subprocess
import sys
import zipfile
from pathlib import Path


MIRRORS = {
    "kaggle": {
        "url": "https://www.kaggle.com/datasets/aryan063/genimage/download",
        "note": "Requires Kaggle API. Run: kaggle datasets download aryan063/genimage",
    },
    "huggingface_small": {
        "url": "https://huggingface.co/datasets/MMInstruction/GenImage/resolve/main/GenImage.zip?download=1",
        "note": "Smaller subset (~10GB) - use --small flag",
    },
    "google_drive_alt": {
        "url": "https://drive.usercontent.google.com/download?id=1jGt10bwTbhEZuGXLyvrCuxOI0cBqQ1FS&confirm=t",
        "note": "Alternative Google Drive link (may have quota)",
    },
    "direct_fallback": {
        "url": "https://data.vision.ee.ethz.ch/cvl/GenImage/GenImage.zip",
        "note": "ETH Zurich mirror (often working)",
    },
}


def download_with_resume(url: str, output_path: Path) -> bool:
    """Download using curl/wget with resume support."""
    print(f"Downloading from {url}")
    if sys.platform == "win32":
        cmd = ["curl", "-L", "-o", str(output_path), "--continue-at", "-", url]
    else:
        cmd = ["wget", "-c", "-O", str(output_path), url]
    try:
        subprocess.run(cmd, check=True)
        return output_path.exists() and output_path.stat().st_size > 0
    except subprocess.CalledProcessError:
        return False


def try_mirror(mirror_name: str, mirror_info: dict, output_path: Path) -> bool:
    print(f"\nTrying mirror: {mirror_name}")
    print(f"  Note: {mirror_info['note']}")
    if mirror_name == "kaggle":
        print("  Kaggle requires API setup; skipping automatic download.")
        return False
    return download_with_resume(mirror_info["url"], output_path)


def extract_zip(zip_path: Path, extract_to: Path) -> None:
    print(f"Extracting {zip_path} to {extract_to}...")
    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(extract_to)
    print("Extraction complete.")


def is_valid_zip_file(zip_path: Path) -> bool:
    """Return True only if file is a real readable zip archive."""
    if not zip_path.exists() or zip_path.stat().st_size == 0:
        return False
    if not zipfile.is_zipfile(zip_path):
        return False
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            bad = zf.testzip()
            return bad is None
    except Exception:
        return False


def download_small_alternative(output_dir: Path) -> bool:
    """Offer a tiny fallback dataset for quick testing."""
    print("\nAll large dataset mirrors failed or are unavailable.")
    choice = input("Download small dataset (~50MB) instead? [y/N]: ").strip().lower()
    if choice != "y":
        return False

    small_url = "https://huggingface.co/datasets/NickyFot/Real_vs_AI/resolve/main/small_ai_real_dataset.zip"
    zip_path = output_dir / "small_dataset.zip"
    if not download_with_resume(small_url, zip_path):
        return False
    extract_zip(zip_path, output_dir)
    print(f"Small dataset ready at {output_dir / 'data'}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Download GenImage or an alternative dataset.")
    parser.add_argument("--destination", type=str, default="./GenImage_download", help="Destination folder")
    parser.add_argument("--extract", action="store_true", help="Extract zip after download")
    parser.add_argument("--small", action="store_true", help="Download small subset only")
    return parser.parse_args()


def main():
    args = parse_args()
    destination = Path(args.destination)
    destination.mkdir(parents=True, exist_ok=True)
    zip_file = destination / "GenImage.zip"

    if args.small:
        print("Downloading small GenImage subset from HuggingFace...")
        if download_with_resume(MIRRORS["huggingface_small"]["url"], zip_file):
            if not is_valid_zip_file(zip_file):
                print("Downloaded file is not a valid zip archive.")
                sys.exit(1)
            if args.extract:
                extract_zip(zip_file, destination)
        else:
            print("Small subset download failed.")
            sys.exit(1)
        return

    success = False
    for mirror_name, mirror_info in MIRRORS.items():
        if mirror_name == "huggingface_small":
            continue
        if try_mirror(mirror_name, mirror_info, zip_file):
            if is_valid_zip_file(zip_file):
                success = True
                break
            print("Downloaded file is not a valid zip. Trying next mirror...")
            try:
                zip_file.unlink(missing_ok=True)
            except Exception:
                pass

    if not success:
        print("\nAll automatic mirrors failed.")
        if download_small_alternative(destination):
            return
        print("\nManual alternatives:")
        print("1. kaggle datasets download aryan063/genimage")
        print("2. https://huggingface.co/datasets/MMInstruction/GenImage")
        print("3. Generate your own AI images with Stable Diffusion")
        sys.exit(1)

    if args.extract and zip_file.exists():
        extract_zip(zip_file, destination)
        print(f"\nDataset ready at {destination}")


if __name__ == "__main__":
    main()
