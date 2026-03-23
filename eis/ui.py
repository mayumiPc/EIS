from __future__ import annotations

import gc
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import threading

import wx

from constants import APP_FULL_NAME, APP_NAME, APP_VERSION, UPDATE_REPO

from .access_catalog import (
    COL_CAPACITY,
    COL_CITY,
    COL_ID,
    COL_KIND,
    COL_LOAD,
    COL_MEDIA,
    COL_MAKER,
    COL_NAME,
    COL_PREF,
    COL_USE,
    AccessCatalogError,
    catalog_sqlite_is_valid,
    manufacturer_to_training_class,
)
from .catalog_import_access import import_access_to_sqlite
from .catalog_sqlite import InstallationCatalog
from .catalog_template import CatalogImportError, has_stuck_pending_catalog
from .infer_register_dialog import show_infer_register_dialog
from .controller import EISController
from .paths import install_root
from .user_training_reset import reset_user_training_artifacts


class EISFrame(wx.Frame):
    """Access カタログを主画面とし、推論・学習は周辺機能として配置する。"""

    def __init__(self) -> None:
        super().__init__(parent=None, title="EIS", size=(1000, 780))
        self.controller = EISController()
        self.app_version = APP_VERSION
        self.language = "ja"
        self.log_level = "ERROR"
        self.logger = self._setup_logger()
        self.class_keys = ["mitsubishi", "hitachi", "otis", "toshiba", "thyssenkrupp", "westinghouse", "montgomery"]
        self.selected_path: str | None = None
        self.last_probabilities: dict[str, float] | None = None
        self.user_training_inputs: list[str] = []
        self.job_running = False
        self._active_job_id: str | None = None  # train_user_model など（状態表示用）
        self._job_lock = threading.Lock()
        self._job_process: subprocess.Popen[str] | None = None
        self._job_user_cancelled = False
        self._ts_job_val = "—"
        self._ts_state_val = ""
        self._ts_prog_val = "—"
        self._catalog: InstallationCatalog | None = None
        self._catalog_rows: list[dict] = []
        self.trans = {
            "ja": {
                "title": APP_FULL_NAME,
                "language": "言語",
                "model": "モデル",
                "model_base": "初回学習モデル",
                "model_user": "ユーザー追加学習モデル",
                "select_media": "画像/動画を選択",
                "infer": "推論を実行",
                "no_file": "ファイル未選択",
                "invalid_file": "先に有効なファイルを選択してください。",
                "predicted": "推論メーカー",
                "probabilities": "推論確率",
                "infer_title": "推論結果",
                "infer_register_title": "推論結果とカタログ登録",
                "reg_no_catalog": "内部カタログがありません。先に Access から取り込み・再起動のうえ、ここから登録できます。",
                "reg_field_maker": "メーカー（必須）",
                "reg_maker_infer_hint": "推論クラス: {cls} ／ 日本語候補: {ja}",
                "reg_field_kind": "種類",
                "reg_field_pref": "都道府県",
                "reg_field_city": "市区町村",
                "reg_field_site": "設置場所の名称（必須）",
                "reg_field_media": "動画・画像・音声（パス）",
                "reg_field_use": "用途",
                "reg_field_load": "積載",
                "reg_field_capacity": "定員",
                "reg_required_hint": "※ メーカーと設置場所の名称は必須です。プルダウンは既存カタログの値候補です（自由入力可）。",
                "reg_save": "カタログに登録",
                "reg_close": "閉じる",
                "reg_saved_ok": "カタログに登録しました（ID: {id}）。",
                "train_title": "学習管理",
                "source_mode": "取り込み方式",
                "file_mode": "ファイル指定",
                "zip_mode": "zip一括指定",
                "class_label": "ラベル",
                "select_inputs": "学習用データを選択",
                "selected": "選択件数",
                "train_user": "ユーザー追加学習モデルを作成",
                "job_running": "別のジョブが実行中です。",
                "no_inputs": "学習用入力が選択されていません。",
                "job_done": "ジョブ完了",
                "job_fail": "ジョブ失敗",
                "menu_settings": "設定",
                "menu_help": "ヘルプ",
                "menu_log_mode": "ログ出力モード",
                "menu_log_error": "ERROR",
                "menu_log_debug": "DEBUG",
                "menu_version": "バージョン情報",
                "menu_check_update": "アップデートを確認…",
                "updater_missing_title": "アップデータ",
                "updater_missing_msg": "現在、アップデータを利用することができません。",
                "version_title": "バージョン情報",
                "version_message": f"{APP_FULL_NAME}\nVersion: {{version}}",
                "log_level_changed": "ログ出力モードを {level} に変更しました。",
                "menu_file": "ファイル",
                "menu_update_catalog_db": "カタログDBの更新…",
                "db_update_intro_first": (
                    "内部カタログ（アプリ用の設置データ）がありません。\n"
                    "Microsoft Access の .accdb を選び、テンプレートに沿って取り込みます。\n"
                    "（既存の .accdb ファイルそのものは変更しません。）\n\n"
                    "取り込み完了後、**アプリケーションは自動的に再起動**し、一覧に反映されます。\n\n続行しますか？"
                ),
                "db_update_intro_update": (
                    "Access の .accdb を選び、内部カタログを再取り込みします。\n\n"
                    "取り込み完了後、**アプリケーションは自動的に再起動**し、本体に反映されます。\n\n続行しますか？"
                ),
                "db_update_pick_title": "取り込む Access データベース (.accdb) を選択",
                "db_compile_done_restart": (
                    "データベースのコンパイルが完了しました。アプリケーションは自動的に再起動されます。\n\n"
                    "（{n} 件を取り込みました）"
                ),
                "db_restart_failed": (
                    "新しいプロセスの起動に失敗しました。手動でアプリを起動し直してください。\n\n{err}"
                ),
                "db_update_fail": "取り込みに失敗しました",
                "db_pending_stuck_restart": (
                    "有効な取り込み仮ファイル（eis_installation_catalog.sqlite.next）がありますが、"
                    "本体（.sqlite）へ反映できませんでした。\n\n"
                    "他アプリが data フォルダ内の SQLite を開いていないか確認し、**アプリを終了してから再度起動**してください。"
                ),
                "cat_internal_missing": (
                    "内部カタログがありません。「ファイル」→「カタログDBの更新」で .accdb から取り込んでください。"
                ),
                "catalog_box": "設置カタログ",
                "catalog_hint": "条件を変えると一覧が更新されます。「動画・画像・音声」はファイルパスでない場合があります。",
                "cat_maker": "メーカー",
                "cat_kind": "種類",
                "cat_pref": "都道府県",
                "cat_city": "市区町村",
                "cat_use": "用途(DB)",
                "cat_load": "積載",
                "cat_cap": "定員",
                "cat_all": "(すべて)",
                "cat_apply": "選択行を作業に反映",
                "cat_col_id": "ID",
                "cat_col_site": "設置名称",
                "cat_err_load": "カタログ読込エラー",
                "cat_none": "該当データがありません。",
                "cat_pick_row": "一覧で行を選択してください。",
                "cat_applied": "学習ラベルをカタログ行に合わせて更新しました。",
                "cat_applied_partial": "メーカーを学習ラベルに自動対応できません。ラベルを手で選んでください。",
                "infer_section": "推論（メディア）",
                "label_unmapped": "選択中のラベルは学習用クラス名（英語7種）に変換できません。\n英語のクラス名、または対応するメーカー表記を選んでください。",
                "state_idle": "【状態】待機中 — 操作できます（学習ジョブは実行されていません）。",
                "state_idle_train_ready": "【状態】待機中 — 学習用に {n} 件選択済み。「ユーザー追加学習モデルを作成」で開始できます。",
                "state_idle_infer_ready": "【状態】待機中 — 推論用メディアを選択済み。「推論を実行」できます。",
                "state_running_user": "【実行中】ユーザー追加学習モデルを作成中です。下のボタンは無効です。完了までお待ちください。",
                "state_running_generic": "【実行中】バックグラウンド処理中: {name}（操作はブロックされています）",
                "train_log_heading": "学習ステータス（各項目は固定行。値のみ更新されます）",
                "train_log_sr_help": "学習ジョブ名・実行状態・プログレスの3行です。Tabでフォーカスし、行を移動して確認できます。",
                "train_status_row_job": "学習ジョブ",
                "train_status_row_state": "実行状態",
                "train_status_row_progress": "プログレス",
                "train_status_cell_idle": "待機中（学習ジョブは実行されていません）",
                "train_status_cell_running": "実行しています",
                "train_status_cell_error_process": "エラーが発生しています（プロセスの異常終了など）",
                "train_status_cell_error_start": "エラーが発生しています（開始時のエラー）",
                "train_status_cell_error_other": "エラーが発生しています（その他）",
                "train_status_cell_cancelled": "キャンセルされました",
                "train_status_cell_cancel_pending": "キャンセル処理中です",
                "train_status_cell_success": "正常に完了しました",
                "train_status_prog_waiting": "—",
                "train_status_prog_started": "プロセス起動済み。標準出力を受信中…",
                "train_status_prog_done_ok": "正常終了",
                "train_status_prog_done_fail": "異常終了",
                "job_cancel": "学習をキャンセル",
                "job_cancel_confirm": "実行中の学習プロセスを終了します。よろしいですか？",
                "job_cancelled": "学習をキャンセルしました。",
                "job_cancel_requested": "キャンセル要求を送信しました。プロセスを終了しています…",
                "menu_init": "初期化",
                "menu_reset_user_training_danger": "ユーザー学習データのリセット(危険)",
                "reset_blocked_job": "学習ジョブ実行中はリセットできません。完了してから実行してください。",
                "reset_confirm1_title": "危険な操作 (1/3)",
                "reset_confirm1_text": "ユーザー追加学習で作成したモデルファイルと、取り込んだ学習用データのコピーを削除します。\n\n削除後は元に戻せません。このまま進みますか？",
                "reset_confirm2_title": "データ範囲の確認 (2/3)",
                "reset_confirm2_text": "次のみ削除します:\n・models/eis_classifier_user.pt\n・dataset_user/ フォルダ全体\n・dataset_combined_user/ フォルダ全体\n\n初回学習モデル(base)、dataset/、dataset_legacy/、内部カタログ・元の.accdb、ログ等は削除しません。スクリプトは上記以外のパスには一切触れません。学習ジョブが実行中でないことも確認してください。続行しますか？",
                "reset_confirm3_title": "最終確認 (3/3)",
                "reset_confirm3_text": "本当に実行しますか？\n「はい」を選ぶと直ちに削除が始まります。",
                "reset_done_title": "リセット完了",
                "reset_done_ok": "削除した項目:\n{deleted}\n\n見つからずスキップ:\n{skipped}\n\n推論モデルは「初回学習モデル」のみの状態に戻りました。",
                "reset_done_errors": "一部エラーがありました:\n{errors}",
                "reset_nothing": "削除対象はありませんでした（すでにクリーンな状態です）。",
                "reset_list_empty": "（なし）",
            },
            "en": {
                "title": APP_FULL_NAME,
                "language": "Language",
                "model": "Model",
                "model_base": "Base model",
                "model_user": "User-extended model",
                "select_media": "Select image/video",
                "infer": "Run inference",
                "no_file": "No file selected",
                "invalid_file": "Please select a valid file first.",
                "predicted": "Predicted manufacturer",
                "probabilities": "Inference probabilities",
                "infer_title": "Inference result",
                "infer_register_title": "Inference & register to catalog",
                "reg_no_catalog": "No internal catalog yet. Import from Access and restart the app before registering here.",
                "reg_field_maker": "Manufacturer (required)",
                "reg_maker_infer_hint": "Inference class: {cls} / Suggested (JA): {ja}",
                "reg_field_kind": "Type",
                "reg_field_pref": "Prefecture",
                "reg_field_city": "City",
                "reg_field_site": "Site name (required)",
                "reg_field_media": "Media path",
                "reg_field_use": "Use (DB)",
                "reg_field_load": "Load",
                "reg_field_capacity": "Capacity",
                "reg_required_hint": "Manufacturer and site name are required. Dropdowns suggest values from the catalog (you can type freely).",
                "reg_save": "Save to catalog",
                "reg_close": "Close",
                "reg_saved_ok": "Saved to catalog (ID: {id}).",
                "train_title": "Training Management",
                "source_mode": "Import mode",
                "file_mode": "File",
                "zip_mode": "Zip",
                "class_label": "Label",
                "select_inputs": "Select training inputs",
                "selected": "Selected",
                "train_user": "Build user model",
                "job_running": "Another job is running.",
                "no_inputs": "No training inputs selected.",
                "job_done": "Job Completed",
                "job_fail": "Job Failed",
                "menu_settings": "Settings",
                "menu_help": "Help",
                "menu_log_mode": "Log output mode",
                "menu_log_error": "ERROR",
                "menu_log_debug": "DEBUG",
                "menu_version": "Version Info",
                "menu_check_update": "Check for updates…",
                "updater_missing_title": "Updater",
                "updater_missing_msg": "The updater is not available right now.",
                "version_title": "Version Info",
                "version_message": f"{APP_FULL_NAME}\nVersion: {{version}}",
                "log_level_changed": "Log output mode changed to {level}.",
                "menu_file": "File",
                "menu_update_catalog_db": "Update catalog database…",
                "db_update_intro_first": (
                    "No internal installation catalog yet.\n"
                    "Choose a Microsoft Access .accdb to import using the app template.\n"
                    "(Your original .accdb file will not be modified.)\n\n"
                    "When import finishes, the application **restarts automatically** and the catalog becomes available.\n\nContinue?"
                ),
                "db_update_intro_update": (
                    "Choose an Access .accdb to re-import the internal catalog.\n\n"
                    "When import finishes, the application **restarts automatically** to apply changes.\n\nContinue?"
                ),
                "db_update_pick_title": "Select Access database (.accdb) to import",
                "db_compile_done_restart": (
                    "Database compilation finished. The application will restart automatically.\n\n"
                    "({n} row(s) imported.)"
                ),
                "db_restart_failed": (
                    "Could not start a new process. Please launch the app again manually.\n\n{err}"
                ),
                "db_update_fail": "Import failed",
                "db_pending_stuck_restart": (
                    "A valid staging file (eis_installation_catalog.sqlite.next) exists, but it could not be merged into the main catalog (.sqlite).\n\n"
                    "Close any program using files under data\\, then **exit and restart** this app."
                ),
                "cat_internal_missing": (
                    "No internal catalog. Use File → Update catalog database to import from a .accdb."
                ),
                "catalog_box": "Installation catalog",
                "catalog_hint": "The list updates when you change filters. The media column may not be a file path.",
                "cat_maker": "Manufacturer",
                "cat_kind": "Type",
                "cat_pref": "Prefecture",
                "cat_city": "City",
                "cat_use": "Use (DB)",
                "cat_load": "Load",
                "cat_cap": "Capacity",
                "cat_all": "(All)",
                "cat_apply": "Apply selected row",
                "cat_col_id": "ID",
                "cat_col_site": "Site name",
                "cat_err_load": "Catalog load error",
                "cat_none": "No matching rows.",
                "cat_pick_row": "Select a row in the list.",
                "cat_applied": "Training label updated from the catalog row.",
                "cat_applied_partial": "Manufacturer could not be mapped to a training label. Pick manually.",
                "infer_section": "Inference (media)",
                "label_unmapped": "The selected label cannot be mapped to a training class name (7 English classes).\nChoose an English class or a manufacturer name that maps to one.",
                "state_idle": "[Status] Idle — you can use the UI (no training job running).",
                "state_idle_train_ready": "[Status] Idle — {n} training path(s) selected. Press “Build user model” to start.",
                "state_idle_infer_ready": "[Status] Idle — media selected. Press “Run inference”.",
                "state_running_user": "[Running] Building user model. Training controls are disabled until finished.",
                "state_running_generic": "[Running] Background job: {name} (UI blocked for this section)",
                "train_log_heading": "Training status (fixed rows; values update in place)",
                "train_log_sr_help": "Three rows: job name, run state, and progress. Tab into the list and use arrow keys.",
                "train_status_row_job": "Training job",
                "train_status_row_state": "Run state",
                "train_status_row_progress": "Progress",
                "train_status_cell_idle": "Idle (no training job)",
                "train_status_cell_running": "Running",
                "train_status_cell_error_process": "Error (process exited abnormally)",
                "train_status_cell_error_start": "Error (failed to start)",
                "train_status_cell_error_other": "Error (other)",
                "train_status_cell_cancelled": "Cancelled",
                "train_status_cell_cancel_pending": "Cancelling…",
                "train_status_cell_success": "Completed successfully",
                "train_status_prog_waiting": "—",
                "train_status_prog_started": "Process started; reading stdout…",
                "train_status_prog_done_ok": "Finished OK",
                "train_status_prog_done_fail": "Finished with error",
                "job_cancel": "Cancel training",
                "job_cancel_confirm": "Stop the running training process?",
                "job_cancelled": "Training was cancelled.",
                "job_cancel_requested": "Cancel requested; terminating process…",
                "menu_init": "Initialize",
                "menu_reset_user_training_danger": "Reset user training data (dangerous)",
                "reset_blocked_job": "Cannot reset while a training job is running. Wait until it finishes.",
                "reset_confirm1_title": "Dangerous action (1/3)",
                "reset_confirm1_text": "This will delete the user-trained model file and copied training import data.\n\nYou cannot undo this. Continue?",
                "reset_confirm2_title": "Scope check (2/3)",
                "reset_confirm2_text": "Only these will be removed:\n· models/eis_classifier_user.pt\n· dataset_user/ (entire folder)\n· dataset_combined_user/ (entire folder)\n\nThe base model, dataset/, dataset_legacy/, internal catalog, source .accdb, logs, etc. are NOT deleted. Continue?",
                "reset_confirm3_title": "Final confirmation (3/3)",
                "reset_confirm3_text": "Really proceed?\nChoosing Yes will delete immediately.",
                "reset_done_title": "Reset complete",
                "reset_done_ok": "Removed:\n{deleted}\n\nSkipped (missing):\n{skipped}\n\nInference is back to the base model only.",
                "reset_done_errors": "Some errors occurred:\n{errors}",
                "reset_nothing": "Nothing to remove (already clean).",
                "reset_list_empty": "(none)",
            },
        }

        panel = wx.Panel(self)
        panel.SetBackgroundColour(wx.Colour(20, 20, 20))
        panel.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        root = wx.BoxSizer(wx.VERTICAL)

        self.title_lbl = wx.StaticText(panel, label="")
        self.title_lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        self.title_lbl.SetFont(wx.Font(17, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        root.Add(self.title_lbl, 0, wx.ALL, 8)

        self.lang_lbl, self.lang_choice = self._choice_row(panel, root, ["日本語", "English"])
        self.lang_choice.SetSelection(0)
        self.lang_choice.Bind(wx.EVT_CHOICE, lambda e: self._on_change_language())

        self.catalog_box = wx.StaticBox(panel, label="")
        cat_outer = wx.StaticBoxSizer(self.catalog_box, wx.VERTICAL)
        self.catalog_hint_lbl = wx.StaticText(panel, label="")
        self.catalog_hint_lbl.SetForegroundColour(wx.Colour(200, 200, 200))
        cat_outer.Add(self.catalog_hint_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.catalog_err_lbl = wx.StaticText(panel, label="")
        self.catalog_err_lbl.SetForegroundColour(wx.Colour(255, 120, 120))
        cat_outer.Add(self.catalog_err_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)

        cat_inner = wx.BoxSizer(wx.VERTICAL)
        self.cat_maker_lbl = wx.StaticText(panel, label="")
        self.cat_maker = wx.Choice(panel, choices=[self._t("cat_all")])
        cat_inner.Add(self._h_row(panel, self.cat_maker_lbl, self.cat_maker), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        self.cat_kind_lbl = wx.StaticText(panel, label="")
        self.cat_kind = wx.Choice(panel, choices=[self._t("cat_all")])
        cat_inner.Add(self._h_row(panel, self.cat_kind_lbl, self.cat_kind), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        self.cat_pref_lbl = wx.StaticText(panel, label="")
        self.cat_pref = wx.Choice(panel, choices=[self._t("cat_all")])
        cat_inner.Add(self._h_row(panel, self.cat_pref_lbl, self.cat_pref), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        self.cat_city_lbl = wx.StaticText(panel, label="")
        self.cat_city = wx.Choice(panel, choices=[self._t("cat_all")])
        cat_inner.Add(self._h_row(panel, self.cat_city_lbl, self.cat_city), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        self.cat_use_lbl = wx.StaticText(panel, label="")
        self.cat_use = wx.Choice(panel, choices=[self._t("cat_all")])
        cat_inner.Add(self._h_row(panel, self.cat_use_lbl, self.cat_use), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        self.cat_load_lbl = wx.StaticText(panel, label="")
        self.cat_load = wx.Choice(panel, choices=[self._t("cat_all")])
        cat_inner.Add(self._h_row(panel, self.cat_load_lbl, self.cat_load), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        self.cat_cap_lbl = wx.StaticText(panel, label="")
        self.cat_cap = wx.Choice(panel, choices=[self._t("cat_all")])
        cat_inner.Add(self._h_row(panel, self.cat_cap_lbl, self.cat_cap), 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 4)
        cat_outer.Add(cat_inner, 0, wx.EXPAND)

        self.btn_cat_apply = wx.Button(panel, label="")
        self.btn_cat_apply.Bind(wx.EVT_BUTTON, self.on_catalog_apply_row)
        cat_outer.Add(self.btn_cat_apply, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.catalog_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL, size=(-1, 260))
        self.catalog_list.SetBackgroundColour(wx.Colour(30, 30, 30))
        self.catalog_list.SetForegroundColour(wx.Colour(220, 255, 220))
        cat_outer.Add(self.catalog_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        root.Add(cat_outer, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)

        self.cat_pref.Bind(wx.EVT_CHOICE, self._on_catalog_prefecture)
        for ch in (
            self.cat_maker,
            self.cat_kind,
            self.cat_city,
            self.cat_use,
            self.cat_load,
            self.cat_cap,
        ):
            ch.Bind(wx.EVT_CHOICE, self._on_catalog_filter_changed)

        self.infer_section_lbl = wx.StaticText(panel, label="")
        self.infer_section_lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        self.infer_section_lbl.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        root.Add(self.infer_section_lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)

        self.model_lbl, self.model_choice = self._choice_row(panel, root, ["", ""])
        self.model_choice.SetSelection(0)

        self.path_lbl = wx.StaticText(panel, label="")
        self.path_lbl.SetForegroundColour(wx.Colour(255, 255, 0))
        root.Add(self.path_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.btn_select = wx.Button(panel, label="")
        self.btn_select.Bind(wx.EVT_BUTTON, self.on_select_media)
        root.Add(self.btn_select, 0, wx.ALL, 4)
        self.btn_infer = wx.Button(panel, label="")
        self.btn_infer.Bind(wx.EVT_BUTTON, self.on_infer)
        root.Add(self.btn_infer, 0, wx.ALL, 4)

        self.train_title = wx.StaticText(panel, label="")
        self.train_title.SetForegroundColour(wx.Colour(255, 255, 255))
        self.train_title.SetFont(wx.Font(13, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        root.Add(self.train_title, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
        self.src_lbl, self.src_choice = self._choice_row(panel, root, ["", ""])
        self.src_choice.SetSelection(0)
        self.src_choice.Bind(wx.EVT_CHOICE, lambda e: self._on_change_source_mode())
        self.class_lbl, self.class_choice = self._choice_row(panel, root, self.class_keys)
        self.class_choice.SetSelection(0)
        self.btn_sel_inputs = wx.Button(panel, label="")
        self.btn_sel_inputs.Bind(wx.EVT_BUTTON, self.on_select_training_inputs)
        root.Add(self.btn_sel_inputs, 0, wx.ALL, 4)
        self.sel_count_lbl = wx.StaticText(panel, label="")
        self.sel_count_lbl.SetForegroundColour(wx.Colour(200, 255, 200))
        root.Add(self.sel_count_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)
        self.btn_train_user = wx.Button(panel, label="")
        self.btn_train_user.Bind(wx.EVT_BUTTON, self.on_train_user_model)
        root.Add(self.btn_train_user, 0, wx.ALL, 4)
        self.app_state_lbl = wx.StaticText(panel, label="")
        self.app_state_lbl.SetForegroundColour(wx.Colour(180, 255, 200))
        self.app_state_lbl.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        root.Add(self.app_state_lbl, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.train_log_heading_lbl = wx.StaticText(panel, label="")
        self.train_log_heading_lbl.SetForegroundColour(wx.Colour(220, 220, 255))
        root.Add(self.train_log_heading_lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        self.training_status_list = wx.ListCtrl(
            panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER,
            size=(-1, 110),
            name="EIS_TrainingStatusLog",
        )
        self.training_status_list.SetBackgroundColour(wx.Colour(25, 25, 28))
        self.training_status_list.SetForegroundColour(wx.Colour(230, 230, 230))
        self.training_status_list.InsertColumn(0, "k", width=160)
        self.training_status_list.InsertColumn(1, "v", width=720)
        self.training_status_list.SetMinSize((-1, 100))
        root.Add(self.training_status_list, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 4)
        self._training_status_init_rows()
        self._training_status_set("-", self._t("train_status_cell_idle"), self._t("train_status_prog_waiting"))
        prog_row = wx.BoxSizer(wx.HORIZONTAL)
        self.progress = wx.Gauge(panel, range=100, size=(-1, 18))
        prog_row.Add(self.progress, 1, wx.EXPAND | wx.RIGHT, 8)
        self.btn_cancel_job = wx.Button(panel, label="", name="EIS_CancelTrainingJob")
        self.btn_cancel_job.Enable(False)
        self.btn_cancel_job.Bind(wx.EVT_BUTTON, self.on_cancel_training_job)
        prog_row.Add(self.btn_cancel_job, 0, wx.ALIGN_CENTER_VERTICAL)
        root.Add(prog_row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        panel.SetSizer(root)
        self._build_menu()
        self._apply_language()
        self._on_change_source_mode()
        self.Centre()
        wx.CallAfter(self._startup_catalog_flow)

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("eic")
        logger.handlers.clear()
        logger.setLevel(logging.ERROR)
        log_path = install_root() / "EIS.log"
        handler = logging.FileHandler(log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
        return logger

    def _set_log_level(self, level_name: str) -> None:
        self.log_level = level_name
        level = logging.DEBUG if level_name == "DEBUG" else logging.ERROR
        self.logger.setLevel(level)

    def _t(self, key: str) -> str:
        return self.trans[self.language].get(key, key)

    def _choice_row(self, panel: wx.Panel, root: wx.BoxSizer, items: list[str]):
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl = wx.StaticText(panel, label="")
        lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        row.Add(lbl, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        c = wx.Choice(panel, choices=items)
        row.Add(c, 0)
        root.Add(row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        return lbl, c

    def _h_row(self, panel: wx.Panel, lbl: wx.StaticText, ctrl: wx.Window) -> wx.BoxSizer:
        row = wx.BoxSizer(wx.HORIZONTAL)
        lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        row.Add(lbl, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        row.Add(ctrl, 0)
        return row

    def _apply_language(self) -> None:
        self.title_lbl.SetLabel(self._t("title"))
        self.lang_lbl.SetLabel(self._t("language"))
        self.infer_section_lbl.SetLabel(self._t("infer_section"))
        self.model_lbl.SetLabel(self._t("model"))
        msel = self.model_choice.GetSelection()
        self.model_choice.SetItems([self._t("model_base"), self._t("model_user")])
        self.model_choice.SetSelection(0 if msel < 0 else min(msel, 1))
        self.path_lbl.SetLabel(self.selected_path or self._t("no_file"))
        self.btn_select.SetLabel(self._t("select_media"))
        self.btn_infer.SetLabel(self._t("infer"))
        self.train_title.SetLabel(self._t("train_title"))
        self.src_lbl.SetLabel(self._t("source_mode"))
        ssel = self.src_choice.GetSelection()
        self.src_choice.SetItems([self._t("file_mode"), self._t("zip_mode")])
        self.src_choice.SetSelection(0 if ssel < 0 else min(ssel, 1))
        self.class_lbl.SetLabel(self._t("class_label"))
        self._sync_class_choice_items()
        if not self.job_running:
            self._on_change_source_mode()
        self.btn_sel_inputs.SetLabel(self._t("select_inputs"))
        self.sel_count_lbl.SetLabel(f"{self._t('selected')}: {len(self.user_training_inputs)}")
        self.btn_train_user.SetLabel(self._t("train_user"))
        self.train_log_heading_lbl.SetLabel(self._t("train_log_heading"))
        self.training_status_list.SetHelpText(self._t("train_log_sr_help"))
        self._training_status_update_row_labels_i18n()
        self.btn_cancel_job.SetLabel(self._t("job_cancel"))
        self.catalog_box.SetLabel(self._t("catalog_box"))
        self.catalog_hint_lbl.SetLabel(self._t("catalog_hint"))
        self.btn_cat_apply.SetLabel(self._t("cat_apply"))
        self.cat_maker_lbl.SetLabel(self._t("cat_maker"))
        self.cat_kind_lbl.SetLabel(self._t("cat_kind"))
        self.cat_pref_lbl.SetLabel(self._t("cat_pref"))
        self.cat_city_lbl.SetLabel(self._t("cat_city"))
        self.cat_use_lbl.SetLabel(self._t("cat_use"))
        self.cat_load_lbl.SetLabel(self._t("cat_load"))
        self.cat_cap_lbl.SetLabel(self._t("cat_cap"))
        self._setup_catalog_list_headers()
        self._patch_catalog_all_labels()
        self._update_menu_labels()
        self._apply_app_state_ui()

    def _build_menu(self) -> None:
        self.menu_bar = wx.MenuBar()
        self.file_menu = wx.Menu()
        self.settings_menu = wx.Menu()
        self.init_menu = wx.Menu()
        self.help_menu = wx.Menu()

        self.menu_update_catalog_db = self.file_menu.Append(wx.ID_ANY, "Update catalog database")

        self.log_mode_menu = wx.Menu()
        self.menu_log_error_item = self.log_mode_menu.AppendRadioItem(wx.ID_ANY, "ERROR")
        self.menu_log_debug_item = self.log_mode_menu.AppendRadioItem(wx.ID_ANY, "DEBUG")
        self.settings_menu.AppendSubMenu(self.log_mode_menu, "Log output mode")

        self.menu_reset_user_training = self.init_menu.Append(wx.ID_ANY, "Reset user training")
        self.menu_check_update_item = self.help_menu.Append(wx.ID_ANY, "Check for updates")
        self.menu_version_item = self.help_menu.Append(wx.ID_ANY, "Version")
        self.menu_bar.Append(self.file_menu, "File")
        self.menu_bar.Append(self.settings_menu, "Settings")
        self.menu_bar.Append(self.init_menu, "Init")
        self.menu_bar.Append(self.help_menu, "Help")
        self.SetMenuBar(self.menu_bar)

        self.Bind(wx.EVT_MENU, self.on_menu_update_catalog_db, self.menu_update_catalog_db)
        self.Bind(wx.EVT_MENU, self.on_set_log_error, self.menu_log_error_item)
        self.Bind(wx.EVT_MENU, self.on_set_log_debug, self.menu_log_debug_item)
        self.Bind(wx.EVT_MENU, self.on_menu_reset_user_training, self.menu_reset_user_training)
        self.Bind(wx.EVT_MENU, self.on_menu_check_update, self.menu_check_update_item)
        self.Bind(wx.EVT_MENU, self.on_show_version, self.menu_version_item)
        self.menu_log_error_item.Check(True)

    def _update_menu_labels(self) -> None:
        self.menu_bar.SetMenuLabel(0, f"&{self._t('menu_file')}")
        self.menu_bar.SetMenuLabel(1, f"&{self._t('menu_settings')}")
        self.menu_bar.SetMenuLabel(2, f"&{self._t('menu_init')}")
        self.menu_bar.SetMenuLabel(3, f"&{self._t('menu_help')}")
        self.menu_update_catalog_db.SetItemLabel(self._t("menu_update_catalog_db"))
        self.settings_menu.SetLabel(self.settings_menu.FindItemByPosition(0).GetId(), self._t("menu_log_mode"))
        self.menu_log_error_item.SetItemLabel(self._t("menu_log_error"))
        self.menu_log_debug_item.SetItemLabel(self._t("menu_log_debug"))
        self.menu_reset_user_training.SetItemLabel(self._t("menu_reset_user_training_danger"))
        self.menu_check_update_item.SetItemLabel(self._t("menu_check_update"))
        self.menu_version_item.SetItemLabel(self._t("menu_version"))

    def _set_training_controls(self, enabled: bool) -> None:
        """学習まわりの有効/無効。有効化時は zip モードならラベル(Choice)だけ無効のままにする。"""
        train_btns = (self.btn_sel_inputs, self.btn_train_user)
        if enabled:
            for w in train_btns:
                w.Enable(True)
            self.src_choice.Enable(True)
            self.class_choice.Enable(self.src_choice.GetSelection() == 0)
        else:
            for w in (*train_btns, self.src_choice, self.class_choice):
                w.Enable(False)

    def _apply_app_state_ui(self) -> None:
        """いま待機中か・どのジョブが走っているか・ファイル選択後に何ができるかを明示する。"""
        if self.job_running:
            jid = self._active_job_id or ""
            if jid == "train_user_model":
                self.app_state_lbl.SetLabel(self._t("state_running_user"))
                self.app_state_lbl.SetForegroundColour(wx.Colour(255, 210, 120))
            else:
                self.app_state_lbl.SetLabel(self._t("state_running_generic").format(name=jid or "?"))
                self.app_state_lbl.SetForegroundColour(wx.Colour(255, 210, 120))
            return
        n = len(self.user_training_inputs)
        if n > 0:
            self.app_state_lbl.SetLabel(self._t("state_idle_train_ready").format(n=n))
        elif self.selected_path:
            self.app_state_lbl.SetLabel(self._t("state_idle_infer_ready"))
        else:
            self.app_state_lbl.SetLabel(self._t("state_idle"))
        self.app_state_lbl.SetForegroundColour(wx.Colour(180, 255, 200))

    def _training_status_init_rows(self) -> None:
        lc = self.training_status_list
        lc.DeleteAllItems()
        for key in ("train_status_row_job", "train_status_row_state", "train_status_row_progress"):
            i = lc.GetItemCount()
            lc.InsertItem(i, self._t(key))
            lc.SetItem(i, 1, "—")

    def _training_status_update_row_labels_i18n(self) -> None:
        lc = self.training_status_list
        if lc.GetItemCount() < 3:
            return
        lc.SetItem(0, 0, self._t("train_status_row_job"))
        lc.SetItem(1, 0, self._t("train_status_row_state"))
        lc.SetItem(2, 0, self._t("train_status_row_progress"))
        self._training_status_sync_values_to_list()

    def _training_status_sync_values_to_list(self) -> None:
        lc = self.training_status_list
        if lc.GetItemCount() < 3:
            return
        lc.SetItem(0, 1, self._ts_job_val)
        lc.SetItem(1, 1, self._ts_state_val)
        lc.SetItem(2, 1, self._ts_prog_val)

    def _training_status_set(
        self,
        job: str | None = None,
        state: str | None = None,
        progress: str | None = None,
    ) -> None:
        if job is not None:
            self._ts_job_val = job
        if state is not None:
            self._ts_state_val = state
        if progress is not None:
            self._ts_prog_val = progress
        self._training_status_sync_values_to_list()

    def _on_job_stdout_line(self, line: str) -> None:
        self.logger.info(line)
        s = line.rstrip()
        if len(s) > 500:
            s = s[:497] + "..."
        self._training_status_set(progress=s)

    def _run_job(self, cmd: list[str], title: str, epochs: int = 10, *, job_id: str | None = None) -> None:
        if self.job_running:
            wx.MessageBox(self._t("job_running"), self._t("train_title"), wx.OK | wx.ICON_INFORMATION, self)
            return
        self.job_running = True
        self._job_user_cancelled = False
        self._active_job_id = job_id or title
        self._set_training_controls(False)
        self.progress.SetValue(0)
        wx.CallAfter(self.btn_cancel_job.Enable, True)
        wx.CallAfter(
            lambda t=title: self._training_status_set(
                t,
                self._t("train_status_cell_running"),
                self._t("train_status_prog_started"),
            )
        )
        self._apply_app_state_ui()
        self.logger.info(f"[job-start] {title} cmd={' '.join(cmd)}")

        def worker() -> None:
            code = 1
            p: subprocess.Popen[str] | None = None
            worker_exc: Exception | None = None
            try:
                pat = re.compile(r"\[epoch\s+(\d+)\]")
                p = subprocess.Popen(
                    cmd,
                    cwd=str(install_root()),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                with self._job_lock:
                    self._job_process = p
                assert p.stdout is not None
                for line in p.stdout:
                    s = line.rstrip()
                    wx.CallAfter(self._on_job_stdout_line, s)
                    self.logger.debug(s)
                    m = pat.search(s)
                    if m:
                        cur = int(m.group(1))
                        wx.CallAfter(self.progress.SetValue, int(min(100, (cur / max(epochs, 1)) * 100)))
                code = p.wait()
            except Exception as exc:
                worker_exc = exc
                self.logger.exception("job exception")
                code = -1
            finally:
                with self._job_lock:
                    self._job_process = None
                user_cancelled = self._job_user_cancelled

                def done() -> None:
                    self.job_running = False
                    self._active_job_id = None
                    self._job_user_cancelled = False
                    self.btn_cancel_job.Enable(False)
                    self._set_training_controls(True)
                    self.progress.SetValue(0)
                    if worker_exc is not None:
                        if p is None:
                            st = self._t("train_status_cell_error_start")
                        else:
                            st = self._t("train_status_cell_error_other")
                        self._training_status_set(
                            state=st,
                            progress=str(worker_exc)[:400],
                        )
                        wx.MessageBox(
                            f"{self._t('job_fail')}: {worker_exc}",
                            title,
                            wx.OK | wx.ICON_ERROR,
                            self,
                        )
                        self._apply_app_state_ui()
                        return
                    if user_cancelled:
                        self._training_status_set(
                            state=self._t("train_status_cell_cancelled"),
                            progress=self._t("job_cancel_requested"),
                        )
                    elif code == 0:
                        self._training_status_set(
                            state=self._t("train_status_cell_success"),
                            progress=self._t("train_status_prog_done_ok"),
                        )
                    else:
                        self._training_status_set(
                            state=self._t("train_status_cell_error_process"),
                            progress=f"{self._t('train_status_prog_done_fail')} (exit={code})",
                        )
                    self._apply_app_state_ui()
                    if user_cancelled:
                        wx.MessageBox(
                            self._t("job_cancelled"),
                            self._t("train_title"),
                            wx.OK | wx.ICON_INFORMATION,
                            self,
                        )
                    elif code == 0:
                        wx.MessageBox(
                            title,
                            self._t("job_done"),
                            wx.OK | wx.ICON_INFORMATION,
                            self,
                        )
                    else:
                        wx.MessageBox(
                            title,
                            self._t("job_fail"),
                            wx.OK | wx.ICON_ERROR,
                            self,
                        )

                wx.CallAfter(done)

        threading.Thread(target=worker, daemon=True).start()

    def on_cancel_training_job(self, _event: wx.CommandEvent) -> None:
        if not self.job_running:
            return
        if (
            wx.MessageBox(
                self._t("job_cancel_confirm"),
                self._t("job_cancel"),
                wx.YES_NO | wx.ICON_QUESTION,
                self,
            )
            != wx.YES
        ):
            return
        self._job_user_cancelled = True
        with self._job_lock:
            proc = self._job_process
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                self.logger.exception("terminate training process")
                try:
                    proc.kill()
                except Exception:
                    self.logger.exception("kill training process")
        wx.CallAfter(
            lambda: self._training_status_set(
                state=self._t("train_status_cell_cancel_pending"),
                progress=self._t("job_cancel_requested"),
            )
        )

    def _current_model(self) -> str:
        return "user" if self.model_choice.GetSelection() == 1 else "base"

    def _on_change_language(self) -> None:
        self.language = "ja" if self.lang_choice.GetSelection() == 0 else "en"
        self._apply_language()
        if self._catalog:
            self._run_catalog_query()

    def _on_change_source_mode(self, _event: wx.CommandEvent | None = None) -> None:
        if self.job_running:
            return
        self.class_choice.Enable(self.src_choice.GetSelection() == 0)

    def _after_modal_file_dialog(self) -> None:
        """ネイティブ FileDialog 後にフレーム/ボタンが無効のまま残る環境への対策。"""
        self.Enable(True)
        if not self.job_running:
            self._set_training_controls(True)
            self._apply_app_state_ui()

    def on_select_media(self, _event: wx.CommandEvent) -> None:
        wildcard = "Media files (*.jpg;*.jpeg;*.png;*.mp4;*.avi;*.mov)|*.jpg;*.jpeg;*.png;*.mp4;*.avi;*.mov"
        with wx.FileDialog(self, self._t("select_media"), wildcard=wildcard, style=wx.FD_OPEN) as d:
            if d.ShowModal() == wx.ID_CANCEL:
                wx.CallAfter(self._after_modal_file_dialog)
                return
            self.selected_path = d.GetPath()
            self.path_lbl.SetLabel(self.selected_path)
        wx.CallAfter(self._after_modal_file_dialog)

    def _distinct_values_for_register(self, column: str) -> list[str]:
        if not self._catalog:
            return []
        try:
            return self._catalog.distinct_values(column)
        except Exception:
            self.logger.exception("distinct for register %s", column)
            return []

    def _after_catalog_registration(self) -> None:
        if self._catalog:
            try:
                self._refresh_catalog_filter_choices()
            except Exception:
                self.logger.exception("refresh catalog after registration")
            self._run_catalog_query()

    def on_infer(self, _event: wx.CommandEvent) -> None:
        if not self.selected_path or not Path(self.selected_path).exists():
            wx.MessageBox(self._t("invalid_file"), self._t("infer"), wx.OK | wx.ICON_WARNING, self)
            return
        try:
            p = self.controller.infer(self.selected_path, model_type=self._current_model())
            self.last_probabilities = dict(p.probabilities)
            self.logger.info("infer %s -> %s", self.selected_path, p.manufacturer)
            catalog_ready = self._catalog is not None and catalog_sqlite_is_valid()
            show_infer_register_dialog(
                self,
                manufacturer=p.manufacturer,
                probabilities=p.probabilities,
                media_path=self.selected_path,
                class_keys=self.class_keys,
                translate=self._t,
                catalog_ready=catalog_ready,
                get_distinct_values=self._distinct_values_for_register,
                on_registered=self._after_catalog_registration,
            )
        except Exception as exc:
            self.logger.exception("infer")
            wx.MessageBox(f"{self._t('job_fail')}: {exc}", self._t("infer"), wx.OK | wx.ICON_ERROR, self)

    def on_select_training_inputs(self, _event: wx.CommandEvent) -> None:
        zip_mode = self.src_choice.GetSelection() == 1
        wildcard = "Zip files (*.zip)|*.zip" if zip_mode else "Image files (*.jpg;*.jpeg;*.png;*.webp)|*.jpg;*.jpeg;*.png;*.webp"
        with wx.FileDialog(self, self._t("select_inputs"), wildcard=wildcard, style=wx.FD_OPEN | wx.FD_MULTIPLE) as d:
            if d.ShowModal() == wx.ID_CANCEL:
                wx.CallAfter(self._after_modal_file_dialog)
                return
            self.user_training_inputs = list(d.GetPaths())
            self.sel_count_lbl.SetLabel(f"{self._t('selected')}: {len(self.user_training_inputs)}")
        wx.CallAfter(self._after_modal_file_dialog)

    def on_train_user_model(self, _event: wx.CommandEvent) -> None:
        if not self.user_training_inputs:
            wx.MessageBox(self._t("no_inputs"), self._t("train_title"), wx.OK | wx.ICON_WARNING, self)
            return
        mode = "zip" if self.src_choice.GetSelection() == 1 else "file"
        cmd = ["py", "-3.11", "tools/train_user_model.py", "--source-mode", mode, "--inputs", *self.user_training_inputs]
        if mode == "file":
            label_arg = self._resolve_training_label_for_cmd()
            if not label_arg:
                wx.MessageBox(self._t("label_unmapped"), self._t("train_title"), wx.OK | wx.ICON_WARNING, self)
                return
            cmd += ["--label", label_arg]
        self._run_job(cmd, "train_user_model", epochs=10, job_id="train_user_model")

    def on_set_log_error(self, _event: wx.CommandEvent) -> None:
        self._set_log_level("ERROR")
        wx.MessageBox(
            self._t("log_level_changed").format(level=self.log_level),
            self._t("menu_settings"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def on_set_log_debug(self, _event: wx.CommandEvent) -> None:
        self._set_log_level("DEBUG")
        wx.MessageBox(
            self._t("log_level_changed").format(level=self.log_level),
            self._t("menu_settings"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def on_show_version(self, _event: wx.CommandEvent) -> None:
        wx.MessageBox(
            self._t("version_message").format(version=self.app_version),
            self._t("version_title"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

    def on_menu_check_update(self, _event: wx.CommandEvent) -> None:
        root = install_root()
        candidates = (
            root / "updater" / "updater.exe",
            root / "public" / "updater" / "updater.exe",
        )
        updater_exe = next((p for p in candidates if p.is_file()), None)
        if updater_exe is None:
            wx.MessageBox(
                self._t("updater_missing_msg"),
                self._t("updater_missing_title"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            return

        # updater 側に対象ディレクトリと現在バージョンを渡す（updater.exe 単体実行は想定しない）。
        cmd = [
            str(updater_exe),
            "--target-dir",
            str(root),
            "--current-version",
            str(self.app_version),
            "--parent-pid",
            str(os.getpid()),
            "--app-name",
            APP_NAME,
            "--repo",
            UPDATE_REPO,
        ]
        subprocess.Popen(cmd, cwd=str(root))

    def on_menu_reset_user_training(self, _event: wx.CommandEvent) -> None:
        if self.job_running:
            wx.MessageBox(
                self._t("reset_blocked_job"),
                self._t("menu_init"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
            return
        confirmations = (
            ("reset_confirm1_title", "reset_confirm1_text"),
            ("reset_confirm2_title", "reset_confirm2_text"),
            ("reset_confirm3_title", "reset_confirm3_text"),
        )
        for title_key, msg_key in confirmations:
            if (
                wx.MessageBox(
                    self._t(msg_key),
                    self._t(title_key),
                    wx.YES_NO | wx.ICON_WARNING,
                    self,
                )
                != wx.YES
            ):
                return
        root = install_root()
        result = reset_user_training_artifacts(root)
        self.controller.discard_user_engine_cache()
        self.user_training_inputs = []
        self.sel_count_lbl.SetLabel(f"{self._t('selected')}: 0")
        if self.model_choice.GetCount() > 0:
            self.model_choice.SetSelection(0)
        self._apply_app_state_ui()
        self.logger.info(
            "user training reset: deleted=%s skipped=%s errors=%s",
            result.deleted,
            result.skipped_missing,
            result.errors,
        )
        empty = self._t("reset_list_empty")
        deleted_txt = "\n".join(result.deleted) if result.deleted else empty
        skipped_txt = "\n".join(result.skipped_missing) if result.skipped_missing else empty
        if result.errors:
            err_txt = "\n".join(result.errors)
            wx.MessageBox(
                self._t("reset_done_errors").format(errors=err_txt)
                + "\n\n"
                + self._t("reset_done_ok").format(deleted=deleted_txt, skipped=skipped_txt),
                self._t("reset_done_title"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
        elif not result.deleted:
            wx.MessageBox(
                self._t("reset_nothing"),
                self._t("reset_done_title"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )
        else:
            wx.MessageBox(
                self._t("reset_done_ok").format(deleted=deleted_txt, skipped=skipped_txt),
                self._t("reset_done_title"),
                wx.OK | wx.ICON_INFORMATION,
                self,
            )

    def _catalog_widget_list(self) -> list[wx.Window]:
        return [
            self.cat_maker,
            self.cat_kind,
            self.cat_pref,
            self.cat_city,
            self.cat_use,
            self.cat_load,
            self.cat_cap,
            self.btn_cat_apply,
            self.catalog_list,
        ]

    def _set_catalog_enabled(self, enabled: bool) -> None:
        for w in self._catalog_widget_list():
            w.Enable(enabled)

    def _setup_catalog_list_headers(self) -> None:
        self.catalog_list.ClearAll()
        cols: list[tuple[str, int]] = [
            (self._t("cat_col_id"), 48),
            (self._t("cat_maker"), 88),
            (self._t("cat_kind"), 72),
            (self._t("cat_pref"), 68),
            (self._t("cat_col_site"), 200),
            (self._t("cat_use"), 64),
            (self._t("cat_load"), 72),
            (self._t("cat_cap"), 56),
        ]
        for i, (name, w) in enumerate(cols):
            self.catalog_list.InsertColumn(i, name, width=w)

    def _patch_catalog_all_labels(self) -> None:
        all_l = self._t("cat_all")
        for ch in (
            self.cat_maker,
            self.cat_kind,
            self.cat_pref,
            self.cat_city,
            self.cat_use,
            self.cat_load,
            self.cat_cap,
        ):
            items = ch.GetStrings()
            if not items:
                ch.SetItems([all_l])
                ch.SetSelection(0)
                continue
            prev = ch.GetString(ch.GetSelection()) if ch.GetSelection() != wx.NOT_FOUND else all_l
            items[0] = all_l
            ch.SetItems(items)
            found = False
            for i, s in enumerate(ch.GetStrings()):
                if s == prev:
                    ch.SetSelection(i)
                    found = True
                    break
            if not found:
                ch.SetSelection(0)

    def _startup_catalog_flow(self) -> None:
        """起動時: 未反映の .next が残っている／本体が無ければ案内する。"""
        if has_stuck_pending_catalog():
            wx.MessageBox(
                self._t("db_pending_stuck_restart"),
                self._t("menu_update_catalog_db"),
                wx.OK | wx.ICON_WARNING,
                self,
            )
            self._init_catalog_after_skip()
            return
        if catalog_sqlite_is_valid():
            self._init_catalog()
        else:
            self._offer_catalog_import(is_update=False)

    def on_menu_update_catalog_db(self, _event: wx.CommandEvent) -> None:
        """ファイル → カタログDBの更新（初回と同じ取り込みフロー）。"""
        self._offer_catalog_import(is_update=True)

    def _spawn_restart_process(self) -> None:
        """同じインタプリタ・引数で EIS を起動し直す（run_ui.py 想定）。"""
        project_root = install_root()
        if getattr(sys, "frozen", False):
            executable = str(Path(sys.executable).resolve())
            args = [executable, *sys.argv[1:]]
        else:
            executable = sys.executable
            script = Path(sys.argv[0]).resolve()
            args = [executable, str(script), *sys.argv[1:]]
        popen_kw: dict = {"cwd": str(project_root)}
        if os.name == "nt":
            popen_kw["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(args, **popen_kw)

    def _restart_after_catalog_import(self) -> None:
        """取り込み完了後: 子プロセス起動 → 自プロセス終了（起動時に .next→本体 が反映される）。"""
        try:
            self._spawn_restart_process()
        except OSError as exc:
            self.logger.exception("catalog import restart spawn failed")
            wx.MessageBox(
                self._t("db_restart_failed").format(err=exc),
                self._t("menu_update_catalog_db"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
        try:
            self.Destroy()
        finally:
            app = wx.GetApp()
            if app:
                app.ExitMainLoop()

    def _init_catalog_after_skip(self) -> None:
        self._catalog = None
        self._catalog_rows = []
        self.catalog_list.DeleteAllItems()
        self.catalog_err_lbl.SetLabel(self._t("cat_internal_missing"))
        self._set_catalog_enabled(False)
        self._sync_class_choice_items()
        if not self.job_running:
            self._on_change_source_mode()

    def _offer_catalog_import(self, is_update: bool) -> None:
        intro = self._t("db_update_intro_update") if is_update else self._t("db_update_intro_first")
        if (
            wx.MessageBox(intro, self._t("menu_update_catalog_db"), wx.OK | wx.CANCEL | wx.ICON_QUESTION, self)
            != wx.OK
        ):
            if not catalog_sqlite_is_valid():
                self._init_catalog_after_skip()
            return
        wildcard = "Access (*.accdb;*.mdb)|*.accdb;*.mdb|All files (*.*)|*.*"
        with wx.FileDialog(
            self,
            self._t("db_update_pick_title"),
            wildcard=wildcard,
            style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
        ) as d:
            if d.ShowModal() != wx.ID_OK:
                if not catalog_sqlite_is_valid():
                    self._init_catalog_after_skip()
                return
            accdb_path = Path(d.GetPath())
        try:
            n = import_access_to_sqlite(accdb_path)
        except CatalogImportError as exc:
            wx.MessageBox(
                f"{self._t('db_update_fail')}: {exc}",
                self._t("db_update_fail"),
                wx.OK | wx.ICON_ERROR,
                self,
            )
            if not catalog_sqlite_is_valid():
                self._init_catalog_after_skip()
            return
        wx.MessageBox(
            self._t("db_compile_done_restart").format(n=n),
            self._t("menu_update_catalog_db"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )
        self._restart_after_catalog_import()

    def _init_catalog(self) -> None:
        self.catalog_err_lbl.SetLabel("")
        try:
            self._catalog = InstallationCatalog()
            self._refresh_catalog_filter_choices()
        except (AccessCatalogError, OSError, FileNotFoundError) as exc:
            self._catalog = None
            self.catalog_err_lbl.SetLabel(f"{self._t('cat_err_load')}: {exc}")
            self._set_catalog_enabled(False)
            self._sync_class_choice_items()
            if not self.job_running:
                self._on_change_source_mode()
            return
        self._set_catalog_enabled(True)
        self._run_catalog_query()

    def _refresh_catalog_filter_choices(self) -> None:
        if not self._catalog:
            return
        all_l = self._t("cat_all")

        def refill(ch: wx.Choice, col: str) -> None:
            vals = self._catalog.distinct_values(col)
            ch.SetItems([all_l] + vals)
            ch.SetSelection(0)

        refill(self.cat_maker, COL_MAKER)
        refill(self.cat_kind, COL_KIND)
        refill(self.cat_pref, COL_PREF)
        self._refill_catalog_cities()
        refill(self.cat_use, COL_USE)
        refill(self.cat_load, COL_LOAD)
        refill(self.cat_cap, COL_CAPACITY)
        self._sync_class_choice_items()
        if not self.job_running:
            self._on_change_source_mode()

    def _build_label_choice_items(self) -> list[str]:
        """学習ラベル: 英語クラス名 + カタログのメーカー一覧（重複文字列は除外）。"""
        items: list[str] = list(self.class_keys)
        if not self._catalog:
            return items
        try:
            for m in self._catalog.distinct_values(COL_MAKER):
                if m is None:
                    continue
                ms = str(m).strip()
                if not ms or ms in items:
                    continue
                items.append(ms)
        except Exception:
            self.logger.exception("label list from catalog makers")
        return items

    def _sync_class_choice_items(self) -> None:
        prev = ""
        sel = self.class_choice.GetSelection()
        if sel != wx.NOT_FOUND and 0 <= sel < self.class_choice.GetCount():
            prev = self.class_choice.GetString(sel)
        items = self._build_label_choice_items()
        self.class_choice.SetItems(items)
        if prev:
            for i, x in enumerate(items):
                if x == prev:
                    self.class_choice.SetSelection(i)
                    return
            canon_prev = prev if prev in self.class_keys else manufacturer_to_training_class(prev)
            if canon_prev:
                for i, x in enumerate(items):
                    if x == canon_prev:
                        self.class_choice.SetSelection(i)
                        return
                    c = manufacturer_to_training_class(x)
                    if c and c == canon_prev:
                        self.class_choice.SetSelection(i)
                        return
        self.class_choice.SetSelection(0)

    def _resolve_training_label_for_cmd(self) -> str | None:
        """train_user_model に渡す英語クラス名。未対応の表示ラベルは None。"""
        sel = self.class_choice.GetSelection()
        if sel == wx.NOT_FOUND or sel >= self.class_choice.GetCount():
            return None
        s = self.class_choice.GetString(sel)
        if s in self.class_keys:
            return s
        mapped = manufacturer_to_training_class(s)
        return mapped if mapped in self.class_keys else None

    def _select_class_choice_for_catalog_maker(self, maker_raw: object, canonical: str | None) -> None:
        if maker_raw is not None:
            s = str(maker_raw).strip()
            for i in range(self.class_choice.GetCount()):
                if self.class_choice.GetString(i) == s:
                    self.class_choice.SetSelection(i)
                    return
        if canonical and canonical in self.class_keys:
            for i in range(self.class_choice.GetCount()):
                lab = self.class_choice.GetString(i)
                if lab == canonical:
                    self.class_choice.SetSelection(i)
                    return
            for i in range(self.class_choice.GetCount()):
                if manufacturer_to_training_class(self.class_choice.GetString(i)) == canonical:
                    self.class_choice.SetSelection(i)
                    return

    def _refill_catalog_cities(self) -> None:
        if not self._catalog:
            return
        all_l = self._t("cat_all")
        pref = self._catalog_choice_value(self.cat_pref)
        cities = self._catalog.distinct_cities(pref)
        self.cat_city.SetItems([all_l] + cities)
        self.cat_city.SetSelection(0)

    def _catalog_choice_value(self, ch: wx.Choice) -> str | None:
        if ch.GetSelection() <= 0:
            return None
        return ch.GetString(ch.GetSelection())

    def _on_catalog_prefecture(self, _event: wx.CommandEvent) -> None:
        if not self._catalog:
            return
        self._refill_catalog_cities()
        self._run_catalog_query()

    def _on_catalog_filter_changed(self, _event: wx.CommandEvent) -> None:
        if not self._catalog:
            return
        self._run_catalog_query()

    def _run_catalog_query(self) -> None:
        if not self._catalog:
            return
        try:
            self._catalog_rows = self._catalog.search(
                maker=self._catalog_choice_value(self.cat_maker),
                kind=self._catalog_choice_value(self.cat_kind),
                prefecture=self._catalog_choice_value(self.cat_pref),
                city=self._catalog_choice_value(self.cat_city),
                use_=self._catalog_choice_value(self.cat_use),
                load=self._catalog_choice_value(self.cat_load),
                capacity=self._catalog_choice_value(self.cat_cap),
            )
            self.catalog_err_lbl.SetLabel("")
        except Exception as exc:
            self.logger.exception("catalog query")
            self.catalog_err_lbl.SetLabel(f"{self._t('cat_err_load')}: {exc}")
            self._catalog_rows = []
        self._fill_catalog_list()

    def _fill_catalog_list(self) -> None:
        self.catalog_list.DeleteAllItems()
        for i, r in enumerate(self._catalog_rows):
            idx = self.catalog_list.InsertItem(i, str(r.get(COL_ID, "")))

            def cell(col: str, cidx: int) -> None:
                v = r.get(col, "")
                if v is None:
                    v = ""
                s = str(v).replace("\n", " ")
                if len(s) > 120:
                    s = s[:117] + "..."
                self.catalog_list.SetItem(idx, cidx, s)

            cell(COL_MAKER, 1)
            cell(COL_KIND, 2)
            cell(COL_PREF, 3)
            cell(COL_NAME, 4)
            cell(COL_USE, 5)
            cell(COL_LOAD, 6)
            cell(COL_CAPACITY, 7)

    def _try_apply_media_path_from_row(self, row: dict) -> None:
        raw = row.get(COL_MEDIA)
        if not raw or not isinstance(raw, str):
            return
        s = raw.strip()
        if "#" in s:
            s = s.split("#")[0].strip()
        if not s:
            return
        norm = s.replace("\\", "/")
        root = install_root()
        for p in (Path(s), Path(norm)):
            if p.is_absolute() and p.exists() and p.is_file():
                self.selected_path = str(p.resolve())
                self.path_lbl.SetLabel(self.selected_path)
                return
        for base in (root, root / "dataset", root / "dataset_legacy"):
            cand = base / norm
            if cand.exists() and cand.is_file():
                self.selected_path = str(cand.resolve())
                self.path_lbl.SetLabel(self.selected_path)
                return

    def on_catalog_apply_row(self, _event: wx.CommandEvent) -> None:
        if not self._catalog_rows:
            wx.MessageBox(self._t("cat_none"), self._t("catalog_box"), wx.OK | wx.ICON_INFORMATION, self)
            return
        idx = self.catalog_list.GetFirstSelected()
        if idx < 0 or idx >= len(self._catalog_rows):
            wx.MessageBox(self._t("cat_pick_row"), self._t("catalog_box"), wx.OK | wx.ICON_INFORMATION, self)
            return
        row = self._catalog_rows[idx]
        maker_raw = row.get(COL_MAKER)
        cls = manufacturer_to_training_class(str(maker_raw) if maker_raw is not None else None)
        mapped = bool(cls and cls in self.class_keys)
        if mapped or maker_raw is not None:
            self._select_class_choice_for_catalog_maker(maker_raw, cls if mapped else None)
        self._try_apply_media_path_from_row(row)
        self.logger.info(
            "catalog apply id=%s maker=%s class=%s",
            row.get(COL_ID),
            maker_raw,
            cls,
        )
        msg = self._t("cat_applied") if mapped else self._t("cat_applied_partial")
        if not self.job_running:
            self._apply_app_state_ui()
        wx.MessageBox(msg, self._t("catalog_box"), wx.OK | wx.ICON_INFORMATION, self)
