# EIS Quick Notes

- Run UI: `py -3.11 run_ui.py`
- Update/replace base model: `py -3.11 tools/update_base_model.py`
- Train user model:
  - file: `py -3.11 tools/train_user_model.py --source-mode file --inputs "C:\path\img.jpg" --label toshiba`
  - zip: `py -3.11 tools/train_user_model.py --source-mode zip --inputs "C:\path\data.zip"`

The main view is the **Installation catalog** (internal SQLite, imported from an Access `.accdb`). Changing filters refreshes the list (no search button). Recommendation UI, read-only log panel, and free-text use-case input were removed; inference shows a dialog; details go to `EIS.log`.

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
