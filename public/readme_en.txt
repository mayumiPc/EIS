Elevator Intelligence System (EIS) — User Guide
Version: 1.0.1

========================================
1. About this application
========================================
EIS analyzes images or videos to infer elevator manufacturers and helps you manage
installation catalog data.

About the AI model
- The app ships with a built-in image classification model (deep learning) used for
  manufacturer inference.
- Inference runs **on your PC**. Images and videos are **not** sent to external cloud
  services for inference (other features, such as update checks, may use the network).

The catalog is stored in an internal SQLite database. Microsoft Access (.accdb) files
are used only when you import or refresh catalog data.

========================================
2. Starting the app
========================================
- Run eis.exe in the distribution folder.
- If no internal catalog exists on first launch, choose
  File > Update catalog database… and select an Access file to import.

========================================
3. Inference (using the built-in AI model)
========================================
“Inference” means passing a selected image or video to the bundled AI model to obtain
elevator-manufacturer-style classes with confidence scores.

Typical workflow:
  1) Choose Image/video… to select a file
  2) Pick which model to use (see below)
  3) Run inference

Which model to use
- **Initial (base) model** — The default model included with the product. Ready to use.
- **User fine-tuned model** — Available after you create it with user training.
  If you have not trained one yet, use the base model.

For video files, the app samples frames and combines the results.

========================================
4. User training (adding your own model)
========================================
You can train an **additional model tailored to your images** inside the app to improve
results for your environment. The trained model is saved on disk and can be selected
as the “user fine-tuned model” for inference.

Typical workflow (training area on the main window):
  1) Choose how to supply data (single images vs. a zip archive)
  2) Select training data… to pick images (or a zip)
  3) When adding images one by one, also pick the label (class) that matches the manufacturer
  4) Create user fine-tuned model to start training
  5) After completion, restart the app when prompted so the new model is loaded

If you use a zip, organize images in **one folder per class (manufacturer)** inside the
archive. See the developer README for the exact folder naming rules.

========================================
5. Catalog update (Access import)
========================================
  1) File > Update catalog database…
  2) Select a .accdb file
  3) After import, the app restarts automatically

========================================
6. Updates
========================================
- Help > Check for updates… looks for a newer release.
- If updater.exe is missing, you will see a message such as:
  “The updater is not available right now.”

Notes when using the updater:
- An internet connection is required.
- The app may exit and restart during an update.
- Do not run updater.exe by itself; launch it from the main application.

========================================
7. Your data
========================================
- Do not delete the internal catalog or **files produced by user training**; the app
  needs them to run correctly.
- The original Access (.accdb) file is not required for day-to-day use, but keep a backup
  if you may re-import later.

========================================
8. Common notes
========================================
- Some menus are unavailable while a training job is running.
- If startup or import fails, make sure no other program has the same files open.
