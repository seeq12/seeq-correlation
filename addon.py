import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BIN = ROOT / "bin"
MANIFEST = ROOT / "addon.json"
FUNCTIONS = ROOT / "python-plotter-functions"


def build_wheel() -> Path:
    shutil.rmtree(ROOT / "build", ignore_errors=True)
    if DIST.exists():
        shutil.rmtree(DIST)
    subprocess.run(
        [sys.executable, "-m", "build", "--wheel", "--outdir", str(DIST)],
        cwd=ROOT,
        check=True,
    )
    wheels = list(DIST.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected one wheel in {DIST}, found {len(wheels)}")
    return wheels[0]


def package_wheel_with_functions(wheel: Path) -> Path:
    for stale_wheel in FUNCTIONS.glob("*.whl"):
        stale_wheel.unlink()
    packaged_wheel = FUNCTIONS / wheel.name
    shutil.copy2(wheel, packaged_wheel)
    (FUNCTIONS / "requirements.txt").write_text(f"./{packaged_wheel.name}\n", encoding="utf-8")
    return packaged_wheel


def write_manifest(archive: zipfile.ZipFile, manifest: dict) -> None:
    archive.writestr("addon.json", json.dumps(manifest, indent=2))


def build() -> tuple[Path, Path]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    wheel = build_wheel()
    packaged_wheel = package_wheel_with_functions(wheel)
    wheel_version = wheel.name.split("-")[1]
    if manifest["version"] != wheel_version:
        raise RuntimeError(
            f"addon.json version {manifest['version']} does not match wheel version {wheel_version}"
        )

    BIN.mkdir(exist_ok=True)
    artifact_base = f"{manifest['identifier']}-{manifest['version']}"
    addon = BIN / f"{artifact_base}.addon"
    addonmeta = BIN / f"{artifact_base}.addonmeta"

    with zipfile.ZipFile(addon, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        write_manifest(archive, manifest)
        for source in FUNCTIONS.iterdir():
            if source.is_file():
                archive.write(source, f"python-plotter-functions/{source.name}")
        for preview in manifest.get("previews", []):
            archive.write(ROOT / preview, preview)

    with zipfile.ZipFile(addonmeta, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        write_manifest(archive, manifest)
        for preview in manifest.get("previews", []):
            archive.write(ROOT / preview, preview)

    print(addon)
    print(addonmeta)
    print(packaged_wheel)
    print(FUNCTIONS / "requirements.txt")
    return addon, addonmeta


if __name__ == "__main__":
    build()