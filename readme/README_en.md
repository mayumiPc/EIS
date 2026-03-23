# EIS Quick Notes

- Run UI: `py -3.11 run_ui.py` or `py -3.11 -m eis` (same entry)
- **Frozen exe**: from repo root run `py -3.11 tools/build.py` → `dist/eis/eis.exe` (see “Distribution build” below)
- Update/replace base model: `py -3.11 tools/update_base_model.py`
- Train user model:
  - file: `py -3.11 tools/train_user_model.py --source-mode file --inputs "C:\path\img.jpg" --label toshiba`
  - zip: `py -3.11 tools/train_user_model.py --source-mode zip --inputs "C:\path\data.zip"` (see folder layout below)

## User training: file mode vs zip (how labels work)

The UI **import mode** is either **File** or **Zip**. Labeling rules differ:

| Mode | How the class (manufacturer-like training label) is chosen | UI “Label” dropdown |
|------|--------------------------------------------------------------|---------------------|
| **File** | Every selected image shares **one** class. The combo maps to `--label` (English class or catalog-backed label). | **Enabled** (required) |
| **Zip** | After extraction, **folder names inside the archive** define classes. Each top-level folder under the zip should match one of the **seven English class names**: `mitsubishi`, `hitachi`, `otis`, `toshiba`, `thyssenkrupp`, `westinghouse`, `montgomery`. If none match, behavior depends on CLI `--label` fallback; the **UI does not pass `--label` in zip mode**. | **Disabled** by design (labels come from zip directory layout) |

- For **zip bulk import**, structure archives like `data.zip` → `toshiba/image001.jpg` under a **class-named folder**. A flat zip of images only may import nothing or fail class assignment from the UI path—use **folder-per-class** or **file mode + label**.
- From the **command line** only, you can add `--label` with zip mode as a fallback when the archive has no class folders (see `import_zip_mode` in `tools/train_user_model.py`).

## Distribution build (PyInstaller → `eis.exe`)

- Output **executable** is **`eis.exe`** (onedir under `dist/eis/`). **Do not add root `eis.py`** (shadows the `eis` package).
- **Canonical entry**: `eis/__main__.py`. PyInstaller bootstrap: **`tools/eis_bundle_entry.py`** (`ENTRY_SCRIPT` in `tools/build_constants.py`).
- **Flow** (modeled after **`samplebuild.py`**, implemented in **`sample_build.py`**):
  1. **Remove `dist/` and `build/`** entirely (clean previous output).
  2. Run **PyInstaller with a small CLI**: `--log-level=ERROR`, `--workpath build/pyi_work`, `--specpath build/spec_staging`, then **delete the generated `.spec`**.
  3. **Copy into `dist/eis/`** after the build: paths in **`PACKAGE_CONTAIN_ITEMS`** in `tools/build_constants.py` (default: `tools`, `models`, `train.py`).
  4. **ZIP** under `build/artifacts/` (`eis_<TAG>_<timestamp>.zip`; `TAG` from env `TAG_NAME`, default `snapshot`).
- **Commands**: from repo root, **`py -3.11 sample_build.py`** or **`py -3.11 tools/build.py`** (same behavior).
- **Smoke tests**: **only on GitHub Actions** by default; **`EIS_FORCE_BUILD_SMOKE=1`** forces them locally. Lite vs full: `EIS_SMOKE_FULL` as before.
- **CI Python**: prefer **`EIS_PY_LAUNCH=python`** after `setup-python` (see `.github/workflows/build-eis.yml`).
- **Runtime paths**: `install_root()` is the folder with `eis.exe`; `tools/`, `models/`, `train.py` come from **post-build copy**.
- **Console**: `PYINSTALLER_CONSOLE` or **`EIS_PYI_CONSOLE=0|1`**.
- Training from the UI expects **`py -3.11 tools/...`** on the machine; **no Python on the target** may break training buttons.

The main view is the **Installation catalog** (internal SQLite, imported from an Access `.accdb`). Changing filters refreshes the list (no search button). After **Run inference**, a dialog shows the result and lets you **fill template fields (manufacturer, type, location, site name, media path, etc.) and save a row** into the internal catalog (manufacturer and site name required). Save is disabled until a valid internal catalog exists. Recommendation UI and similar were removed; details go to `EIS.log`.

## Initialize menu (reset user training)

**Initialize → Reset user training data (dangerous)** asks for **three separate confirmations**, then deletes only `models/eis_classifier_user.pt`, `dataset_user/`, and `dataset_combined_user/`. Base model, `dataset/`, `dataset_legacy/`, internal catalog, `.accdb`, etc. are untouched. Disabled while a training job is running.

## Installation catalog (internal DB + Access import)

- **Startup**: `run_ui.py` **first** promotes `data/eis_installation_catalog.sqlite.next` (staging) to `eis_installation_catalog.sqlite` when present, before the UI opens the catalog (nothing should hold the main file yet).
- **First launch / catalog update**: After you pick an Access `.accdb`, only **`.sqlite.next`** is written, then the app **restarts itself** with the same command line. On startup, `.next` is merged into the main `.sqlite` (no in-process replace, avoiding self-lock issues on Windows).
- **File → Update catalog database…** uses the same flow.
- Filters: manufacturer, type, prefecture, city, DB use, load, capacity. At runtime the UI reads **only** the internal SQLite file, not `.accdb` directly.
- **Apply selected row** sets the training label; media path is set only when the DB value resolves to a real file.
- **Import only** needs `pyodbc` and ACE on Windows. Schema/mapping: see `eis/catalog_template.py`.
- **What the template import “guarantees”**: At runtime only the internal SQLite is read (`eis/catalog_sqlite.py`). Access is opened via `pyodbc` **only during import** (`eis/catalog_import_access.py`). Import checks the **「設置場所」** table and **required columns** (`ACCESS_COLUMNS_REQUIRED` in `catalog_template.py`) and copies rows into the template schema. It does **not** guarantee a full reproduction of every Access feature/object type or business correctness (bad or exotic values may error or be coerced to text).
- **Deleting the source “設置場所” `.accdb` from the project**: If **`data/eis_installation_catalog.sqlite` is valid and already applied**, normal UI use **does not** need the original `.accdb` on disk. For **File → Update catalog database**, you still need **some** `.accdb` (e.g. a backup copy elsewhere). If you delete your only master, you cannot re-import without obtaining the file again.
- Base training and image download scripts under `tools/` and `pixabay-downloader` remain available.
