from __future__ import annotations

import logging
from pathlib import Path
import re
import subprocess
import threading

import wx

from .config import RecommendationWeights, USE_CASE_PRESETS
from .controller import EISController


class EISFrame(wx.Frame):
    def __init__(self) -> None:
        super().__init__(parent=None, title="EIS", size=(980, 820))
        self.controller = EISController()
        self.app_version = "1.0.0"
        self.language = "ja"
        self.log_level = "ERROR"
        self.logger = self._setup_logger()
        self.use_case_keys = ["hospital", "office", "residential", "hotel", "factory"]
        self.class_keys = ["mitsubishi", "hitachi", "otis", "toshiba", "thyssenkrupp", "westinghouse", "montgomery"]
        self.selected_path: str | None = None
        self.last_probabilities: dict[str, float] | None = None
        self.last_recommend_signature: tuple[str, float, str] | None = None
        self.output_history: list[dict] = []
        self.user_training_inputs: list[str] = []
        self.job_running = False
        self.trans = {
            "ja": {
                "title": "Elevator Intelligence System",
                "language": "言語",
                "model": "モデル",
                "model_base": "初回学習モデル",
                "model_user": "ユーザー追加学習モデル",
                "select_media": "画像/動画を選択",
                "infer": "推論のみ実行",
                "recommend": "用途推薦を実行",
                "use_case": "用途",
                "use_case_note": "用途の補足（自由入力）",
                "use_case_note_value": "用途補足",
                "use_case_note_hint": "例: 病院で夜間稼働が多い。騒音は抑えたい。保守しやすさ重視。",
                "weight_mode": "重み設定",
                "preset": "用途プリセット",
                "custom": "カスタム",
                "use_infer": "直前の推論結果を推薦に使う",
                "prob_unit": "確率単位",
                "decimal": "少数",
                "percent": "％",
                "refresh": "表示補正",
                "clear": "クリア",
                "no_file": "ファイル未選択",
                "invalid_file": "先に有効なファイルを選択してください。",
                "predicted": "推論メーカー",
                "probabilities": "推論確率",
                "recommended": "推奨メーカー",
                "score": "推奨スコア",
                "breakdown": "内訳(上位3)",
                "reason": "理由",
                "uses_inference": "推論反映",
                "yes": "あり",
                "no": "なし",
                "dup": "前回と同一条件のため、同じ推薦結果です。",
                "infer_title": "=== 推論結果 ===",
                "rec_title": "=== 用途推薦結果 ===",
                "train_title": "学習管理",
                "source_mode": "取り込み方式",
                "file_mode": "ファイル指定",
                "zip_mode": "zip一括指定",
                "class_label": "ラベル",
                "select_inputs": "学習用データを選択",
                "selected": "選択件数",
                "train_user": "ユーザー追加学習モデルを作成",
                "update_base": "初回学習モデルを更新(置換)",
                "job_running": "別のジョブが実行中です。",
                "no_inputs": "学習用入力が選択されていません。",
                "job_done": "ジョブ完了",
                "job_fail": "ジョブ失敗",
                "confirm_no_infer": "推論結果がありません。用途推薦のみ実行しますか？",
                "menu_settings": "設定",
                "menu_help": "ヘルプ",
                "menu_log_mode": "ログ出力モード",
                "menu_log_error": "ERROR",
                "menu_log_debug": "DEBUG",
                "menu_version": "バージョン情報",
                "version_title": "バージョン情報",
                "version_message": "Elevator Intelligence System\nVersion: {version}",
                "log_level_changed": "ログ出力モードを {level} に変更しました。",
                "safety": "安全性",
                "noise": "静音性",
                "speed": "速度",
                "maintenance": "保守性",
                "energy": "省エネ",
                "cost": "コスト",
                "use_case_hospital": "病院",
                "use_case_office": "オフィス",
                "use_case_residential": "住宅",
                "use_case_hotel": "ホテル",
                "use_case_factory": "工場",
            },
            "en": {
                "title": "Elevator Intelligence System",
                "language": "Language",
                "model": "Model",
                "model_base": "Base model",
                "model_user": "User-extended model",
                "select_media": "Select image/video",
                "infer": "Run inference only",
                "recommend": "Run recommendation",
                "use_case": "Use case",
                "use_case_note": "Use-case note (free text)",
                "use_case_note_value": "Use-case note",
                "use_case_note_hint": "Ex: Night operation in hospital. Prefer low noise and easy maintenance.",
                "weight_mode": "Weight mode",
                "preset": "Preset",
                "custom": "Custom",
                "use_infer": "Use latest inference for recommendation",
                "prob_unit": "Probability unit",
                "decimal": "Decimal",
                "percent": "Percent",
                "refresh": "Refresh display",
                "clear": "Clear",
                "no_file": "No file selected",
                "invalid_file": "Please select a valid file first.",
                "predicted": "Predicted manufacturer",
                "probabilities": "Inference probabilities",
                "recommended": "Recommended manufacturer",
                "score": "Recommendation score",
                "breakdown": "Top-3 breakdown",
                "reason": "Reason",
                "uses_inference": "Uses inference",
                "yes": "Yes",
                "no": "No",
                "dup": "Same conditions as previous run; result unchanged.",
                "infer_title": "=== Inference Result ===",
                "rec_title": "=== Recommendation Result ===",
                "train_title": "Training Management",
                "source_mode": "Import mode",
                "file_mode": "File",
                "zip_mode": "Zip",
                "class_label": "Label",
                "select_inputs": "Select training inputs",
                "selected": "Selected",
                "train_user": "Build user model",
                "update_base": "Update/replace base model",
                "job_running": "Another job is running.",
                "no_inputs": "No training inputs selected.",
                "job_done": "Job Completed",
                "job_fail": "Job Failed",
                "confirm_no_infer": "No inference result found. Run recommendation anyway?",
                "menu_settings": "Settings",
                "menu_help": "Help",
                "menu_log_mode": "Log output mode",
                "menu_log_error": "ERROR",
                "menu_log_debug": "DEBUG",
                "menu_version": "Version Info",
                "version_title": "Version Info",
                "version_message": "Elevator Intelligence System\nVersion: {version}",
                "log_level_changed": "Log output mode changed to {level}.",
                "safety": "Safety",
                "noise": "Noise",
                "speed": "Speed",
                "maintenance": "Maintenance",
                "energy": "Energy",
                "cost": "Cost",
                "use_case_hospital": "Hospital",
                "use_case_office": "Office",
                "use_case_residential": "Residential",
                "use_case_hotel": "Hotel",
                "use_case_factory": "Factory",
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
        self.model_lbl, self.model_choice = self._choice_row(panel, root, ["", ""])
        self.model_choice.SetSelection(0)
        self.usecase_lbl, self.usecase_choice = self._choice_row(panel, root, [""] * len(self.use_case_keys))
        self.usecase_choice.SetSelection(1)
        self.usecase_choice.Bind(wx.EVT_CHOICE, lambda e: self._on_change_use_case())
        self.weight_lbl, self.weight_choice = self._choice_row(panel, root, ["", ""])
        self.weight_choice.SetSelection(0)
        self.weight_choice.Bind(wx.EVT_CHOICE, lambda e: self._on_change_weight_mode())

        self.usecase_note_lbl = wx.StaticText(panel, label="")
        self.usecase_note_lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        root.Add(self.usecase_note_lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 6)
        self.usecase_note_txt = wx.TextCtrl(panel, style=wx.TE_MULTILINE, size=(-1, 80))
        self.usecase_note_txt.SetHint(self._t("use_case_note_hint"))
        self.usecase_note_txt.SetName("use_case_note_textbox")
        self.usecase_note_txt.SetToolTip("use_case_note_textbox")
        root.Add(self.usecase_note_txt, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.use_infer_chk = wx.CheckBox(panel, label="")
        self.use_infer_chk.SetValue(True)
        self.use_infer_chk.SetForegroundColour(wx.Colour(255, 255, 255))
        root.Add(self.use_infer_chk, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.path_lbl = wx.StaticText(panel, label="")
        self.path_lbl.SetForegroundColour(wx.Colour(255, 255, 0))
        root.Add(self.path_lbl, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.btn_select = wx.Button(panel, label="")
        self.btn_select.Bind(wx.EVT_BUTTON, self.on_select_media)
        root.Add(self.btn_select, 0, wx.ALL, 4)
        self.btn_infer = wx.Button(panel, label="")
        self.btn_infer.Bind(wx.EVT_BUTTON, self.on_infer)
        root.Add(self.btn_infer, 0, wx.ALL, 4)
        self.btn_recommend = wx.Button(panel, label="")
        self.btn_recommend.Bind(wx.EVT_BUTTON, self.on_recommend)
        root.Add(self.btn_recommend, 0, wx.ALL, 4)

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
        self.btn_update_base = wx.Button(panel, label="")
        self.btn_update_base.Bind(wx.EVT_BUTTON, self.on_update_base_model)
        root.Add(self.btn_update_base, 0, wx.ALL, 4)
        self.progress_lbl = wx.StaticText(panel, label="")
        self.progress_lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        root.Add(self.progress_lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        self.progress = wx.Gauge(panel, range=100, size=(-1, 18))
        root.Add(self.progress, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        disp_row = wx.BoxSizer(wx.HORIZONTAL)
        self.unit_lbl = wx.StaticText(panel, label="")
        self.unit_lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        disp_row.Add(self.unit_lbl, 0, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 8)
        self.unit_choice = wx.Choice(panel, choices=["", ""])
        self.unit_choice.SetSelection(1)
        disp_row.Add(self.unit_choice, 0, wx.RIGHT, 8)
        self.btn_refresh = wx.Button(panel, label="")
        self.btn_refresh.Bind(wx.EVT_BUTTON, self.on_refresh_display)
        disp_row.Add(self.btn_refresh, 0, wx.RIGHT, 8)
        self.btn_clear = wx.Button(panel, label="")
        self.btn_clear.Bind(wx.EVT_BUTTON, self.on_clear_output)
        disp_row.Add(self.btn_clear, 0)
        root.Add(disp_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        self.safety_lbl, self.safety_s = self._slider(panel, root)
        self.noise_lbl, self.noise_s = self._slider(panel, root)
        self.speed_lbl, self.speed_s = self._slider(panel, root)
        self.maint_lbl, self.maint_s = self._slider(panel, root)
        self.energy_lbl, self.energy_s = self._slider(panel, root)
        self.cost_lbl, self.cost_s = self._slider(panel, root)

        self.output = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY, size=(-1, 240))
        self.output.SetBackgroundColour(wx.Colour(0, 0, 0))
        self.output.SetForegroundColour(wx.Colour(0, 255, 0))
        root.Add(self.output, 1, wx.EXPAND | wx.ALL, 8)

        panel.SetSizer(root)
        self._build_menu()
        self._apply_language()
        self._apply_use_case_preset()
        self._update_slider_enable()
        self.Centre()

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger("eic")
        logger.handlers.clear()
        logger.setLevel(logging.ERROR)
        log_path = Path(__file__).resolve().parents[1] / "eic.log"
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

    def _slider(self, panel: wx.Panel, root: wx.BoxSizer):
        lbl = wx.StaticText(panel, label="")
        lbl.SetForegroundColour(wx.Colour(255, 255, 255))
        root.Add(lbl, 0, wx.LEFT | wx.RIGHT | wx.TOP, 4)
        s = wx.Slider(panel, value=20, minValue=0, maxValue=100)
        root.Add(s, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 6)
        return lbl, s

    def _apply_language(self) -> None:
        self.title_lbl.SetLabel(self._t("title"))
        self.lang_lbl.SetLabel(self._t("language"))
        self.model_lbl.SetLabel(self._t("model"))
        self.model_choice.SetItems([self._t("model_base"), self._t("model_user")])
        self.usecase_lbl.SetLabel(self._t("use_case"))
        self.usecase_choice.SetItems([self._t(f"use_case_{k}") for k in self.use_case_keys])
        self.weight_lbl.SetLabel(self._t("weight_mode"))
        self.weight_choice.SetItems([self._t("preset"), self._t("custom")])
        self.usecase_note_lbl.SetLabel(self._t("use_case_note"))
        self.usecase_note_txt.SetHint(self._t("use_case_note_hint"))
        self.use_infer_chk.SetLabel(self._t("use_infer"))
        self.path_lbl.SetLabel(self.selected_path or self._t("no_file"))
        self.btn_select.SetLabel(self._t("select_media"))
        self.btn_infer.SetLabel(self._t("infer"))
        self.btn_recommend.SetLabel(self._t("recommend"))
        self.train_title.SetLabel(self._t("train_title"))
        self.src_lbl.SetLabel(self._t("source_mode"))
        self.src_choice.SetItems([self._t("file_mode"), self._t("zip_mode")])
        self.class_lbl.SetLabel(self._t("class_label"))
        self.class_choice.SetItems(self.class_keys)
        self.btn_sel_inputs.SetLabel(self._t("select_inputs"))
        self.sel_count_lbl.SetLabel(f"{self._t('selected')}: {len(self.user_training_inputs)}")
        self.btn_train_user.SetLabel(self._t("train_user"))
        self.btn_update_base.SetLabel(self._t("update_base"))
        self.unit_lbl.SetLabel(self._t("prob_unit"))
        self.unit_choice.SetItems([self._t("decimal"), self._t("percent")])
        self.btn_refresh.SetLabel(self._t("refresh"))
        self.btn_clear.SetLabel(self._t("clear"))
        self.safety_lbl.SetLabel(self._t("safety"))
        self.noise_lbl.SetLabel(self._t("noise"))
        self.speed_lbl.SetLabel(self._t("speed"))
        self.maint_lbl.SetLabel(self._t("maintenance"))
        self.energy_lbl.SetLabel(self._t("energy"))
        self.cost_lbl.SetLabel(self._t("cost"))
        self._update_menu_labels()
        if not self.job_running and self.progress.GetValue() == 0:
            self.progress_lbl.SetLabel("")

    def _build_menu(self) -> None:
        self.menu_bar = wx.MenuBar()
        self.settings_menu = wx.Menu()
        self.help_menu = wx.Menu()

        self.log_mode_menu = wx.Menu()
        self.menu_log_error_item = self.log_mode_menu.AppendRadioItem(wx.ID_ANY, "ERROR")
        self.menu_log_debug_item = self.log_mode_menu.AppendRadioItem(wx.ID_ANY, "DEBUG")
        self.settings_menu.AppendSubMenu(self.log_mode_menu, "Log output mode")

        self.menu_version_item = self.help_menu.Append(wx.ID_ANY, "Version")
        self.menu_bar.Append(self.settings_menu, "Settings")
        self.menu_bar.Append(self.help_menu, "Help")
        self.SetMenuBar(self.menu_bar)

        self.Bind(wx.EVT_MENU, self.on_set_log_error, self.menu_log_error_item)
        self.Bind(wx.EVT_MENU, self.on_set_log_debug, self.menu_log_debug_item)
        self.Bind(wx.EVT_MENU, self.on_show_version, self.menu_version_item)
        self.menu_log_error_item.Check(True)

    def _update_menu_labels(self) -> None:
        self.menu_bar.SetMenuLabel(0, f"&{self._t('menu_settings')}")
        self.menu_bar.SetMenuLabel(1, f"&{self._t('menu_help')}")
        self.settings_menu.SetLabel(self.settings_menu.FindItemByPosition(0).GetId(), self._t("menu_log_mode"))
        self.menu_log_error_item.SetItemLabel(self._t("menu_log_error"))
        self.menu_log_debug_item.SetItemLabel(self._t("menu_log_debug"))
        self.menu_version_item.SetItemLabel(self._t("menu_version"))

    def _weights(self) -> RecommendationWeights:
        vals = [self.safety_s.GetValue(), self.noise_s.GetValue(), self.speed_s.GetValue(), self.maint_s.GetValue(), self.energy_s.GetValue(), self.cost_s.GetValue()]
        total = max(sum(vals), 1)
        return RecommendationWeights(*(v / total for v in vals))

    def _apply_use_case_preset(self) -> None:
        p = USE_CASE_PRESETS[self.use_case_keys[max(self.usecase_choice.GetSelection(), 0)]]
        self.safety_s.SetValue(int(p.safety * 100))
        self.noise_s.SetValue(int(p.noise * 100))
        self.speed_s.SetValue(int(p.speed * 100))
        self.maint_s.SetValue(int(p.maintenance * 100))
        self.energy_s.SetValue(int(p.energy * 100))
        self.cost_s.SetValue(int(p.cost * 100))

    def _update_slider_enable(self) -> None:
        custom = self.weight_choice.GetSelection() == 1
        for s in [self.safety_s, self.noise_s, self.speed_s, self.maint_s, self.energy_s, self.cost_s]:
            s.Enable(custom)

    def _set_training_controls(self, enabled: bool) -> None:
        for w in [self.btn_sel_inputs, self.btn_train_user, self.btn_update_base, self.src_choice, self.class_choice]:
            w.Enable(enabled)

    def _is_percent(self) -> bool:
        return self.unit_choice.GetSelection() == 1

    def _fmt(self, v: float) -> str:
        return f"{v * 100:.1f}%" if self._is_percent() else f"{v:.3f}"

    def _fmt_probs(self, probs: dict[str, float]) -> str:
        return ", ".join(f"{k}: {self._fmt(v)}" for k, v in sorted(probs.items(), key=lambda x: x[1], reverse=True))

    def _localized_reason(self, rec, uses_infer: bool) -> str:
        d = rec.score_breakdown.get(rec.manufacturer, {})
        contrib = {
            "safety": d.get("contrib_safety", 0.0),
            "noise": d.get("contrib_noise", 0.0),
            "speed": d.get("contrib_speed", 0.0),
            "maintenance": d.get("contrib_maintenance", 0.0),
            "energy": d.get("contrib_energy", 0.0),
            "cost": d.get("contrib_cost", 0.0),
        }
        top = [k for k, _ in sorted(contrib.items(), key=lambda x: x[1], reverse=True)[:2]]
        t1 = self._t(top[0]) if top else self._t("safety")
        t2 = self._t(top[1]) if len(top) > 1 else self._t("speed")
        uc = self._t(f"use_case_{rec.use_case}")
        ai = float(d.get("ai_confidence", 0.0))
        if self.language == "ja":
            if uses_infer:
                return f"{uc}用途では {t1} と {t2} を重視。{rec.manufacturer} は寄与が高く、推論信頼度 {ai:.1%} が加点。"
            return f"{uc}用途では {t1} と {t2} を重視。{rec.manufacturer} は用途寄与が最も高い。"
        if uses_infer:
            return f"For {uc}, {t1} and {t2} dominate. {rec.manufacturer} also gains inference boost ({ai:.1%})."
        return f"For {uc}, {t1} and {t2} dominate. {rec.manufacturer} has highest domain contribution."

    def _append(self, msg: str) -> None:
        self.output.AppendText(msg + "\n\n")
        self.logger.info(msg)

    def _append_error(self, msg: str) -> None:
        self.output.AppendText(msg + "\n\n")
        self.logger.error(msg)

    def _render_entry(self, e: dict) -> str:
        if e["type"] == "infer":
            return f"{self._t('infer_title')}\n{self._t('predicted')}: {e['predicted']}\n{self._t('probabilities')}: {self._fmt_probs(e['probabilities'])}"
        dup = f"\n{self._t('dup')}" if e.get("duplicate") else ""
        top3 = ", ".join(f"{k}: {self._fmt(v)}" for k, v in sorted(e["ranked_scores"].items(), key=lambda x: x[1], reverse=True)[:3])
        use_case_label = self._t(f"use_case_{e['use_case']}")
        return (
            f"{self._t('rec_title')}\n"
            f"{self._t('use_case')}: {use_case_label}\n"
            f"{self._t('use_case_note_value')}: {e['rec'].use_case_note if e['rec'].use_case_note else '-'}\n"
            f"{self._t('uses_inference')}: {self._t('yes') if e['uses_inference'] else self._t('no')}\n"
            f"{self._t('recommended')}: {e['manufacturer']}\n"
            f"{self._t('score')}: {self._fmt(e['score'])}\n"
            f"{self._t('breakdown')}: {top3}\n"
            f"{self._t('reason')}: {self._localized_reason(e['rec'], e['uses_inference'])}{dup}"
        )

    def _rerender_output(self) -> None:
        self.output.SetValue("")
        for e in self.output_history:
            self._append(self._render_entry(e))

    def _run_job(self, cmd: list[str], title: str, epochs: int = 10) -> None:
        if self.job_running:
            self._append(self._t("job_running"))
            return
        self.job_running = True
        self._set_training_controls(False)
        self.progress.SetValue(0)
        self.progress_lbl.SetLabel(title)
        self._append(f"[job-start] {title}")
        self.logger.debug(f"job-start {title} cmd={' '.join(cmd)}")

        def worker() -> None:
            code = 1
            try:
                pat = re.compile(r"\[epoch\s+(\d+)\]")
                p = subprocess.Popen(
                    cmd,
                    cwd=str(Path(__file__).resolve().parents[1]),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                assert p.stdout is not None
                for line in p.stdout:
                    s = line.rstrip()
                    wx.CallAfter(self._append, s)
                    self.logger.debug(s)
                    m = pat.search(s)
                    if m:
                        cur = int(m.group(1))
                        wx.CallAfter(self.progress.SetValue, int(min(100, (cur / max(epochs, 1)) * 100)))
                code = p.wait()
            except Exception as exc:
                wx.CallAfter(self._append_error, f"{self._t('job_fail')}: {exc}")
                self.logger.exception("job exception")
            finally:
                def done() -> None:
                    self.job_running = False
                    self._set_training_controls(True)
                    wx.MessageBox(title, self._t("job_done") if code == 0 else self._t("job_fail"), wx.OK | (wx.ICON_INFORMATION if code == 0 else wx.ICON_ERROR), self)
                wx.CallAfter(done)

        threading.Thread(target=worker, daemon=True).start()

    def _current_use_case(self) -> str:
        return self.use_case_keys[max(self.usecase_choice.GetSelection(), 0)]

    def _current_model(self) -> str:
        return "user" if self.model_choice.GetSelection() == 1 else "base"

    def _on_change_language(self) -> None:
        self.language = "ja" if self.lang_choice.GetSelection() == 0 else "en"
        self._apply_language()
        self._rerender_output()

    def _on_change_use_case(self) -> None:
        if self.weight_choice.GetSelection() == 0:
            self._apply_use_case_preset()

    def _on_change_weight_mode(self) -> None:
        if self.weight_choice.GetSelection() == 0:
            self._apply_use_case_preset()
        self._update_slider_enable()

    def _on_change_source_mode(self) -> None:
        self.class_choice.Enable(self.src_choice.GetSelection() == 0)

    def on_select_media(self, _event: wx.CommandEvent) -> None:
        wildcard = "Media files (*.jpg;*.jpeg;*.png;*.mp4;*.avi;*.mov)|*.jpg;*.jpeg;*.png;*.mp4;*.avi;*.mov"
        with wx.FileDialog(self, self._t("select_media"), wildcard=wildcard, style=wx.FD_OPEN) as d:
            if d.ShowModal() == wx.ID_CANCEL:
                return
            self.selected_path = d.GetPath()
            self.path_lbl.SetLabel(self.selected_path)

    def on_infer(self, _event: wx.CommandEvent) -> None:
        if not self.selected_path or not Path(self.selected_path).exists():
            self._append(self._t("invalid_file"))
            return
        try:
            p = self.controller.infer(self.selected_path, model_type=self._current_model())
            self.last_probabilities = p.probabilities
            self.last_recommend_signature = None
            entry = {"type": "infer", "predicted": p.manufacturer, "probabilities": dict(p.probabilities)}
            self.output_history.append(entry)
            self._append(self._render_entry(entry))
        except Exception as exc:
            self._append_error(f"{self._t('job_fail')}: {exc}")

    def on_recommend(self, _event: wx.CommandEvent) -> None:
        try:
            use_infer = bool(self.use_infer_chk.GetValue() and self.last_probabilities)
            if self.use_infer_chk.GetValue() and self.last_probabilities is None:
                if wx.MessageBox(self._t("confirm_no_infer"), self._t("use_case"), wx.YES_NO | wx.ICON_QUESTION, self) != wx.YES:
                    return
            weights = self._weights() if self.weight_choice.GetSelection() == 1 else None
            rec = self.controller.recommend(
                use_case=self._current_use_case(),
                weights=weights,
                probabilities=self.last_probabilities if self.use_infer_chk.GetValue() else None,
                use_case_note=self.usecase_note_txt.GetValue(),
            )
            sig = (rec.manufacturer, round(rec.score, 6), rec.use_case)
            entry = {
                "type": "recommend",
                "use_case": rec.use_case,
                "uses_inference": use_infer,
                "manufacturer": rec.manufacturer,
                "score": rec.score,
                "ranked_scores": dict(rec.ranked_scores),
                "rec": rec,
                "duplicate": self.last_recommend_signature == sig,
            }
            self.last_recommend_signature = sig
            self.output_history.append(entry)
            self._append(self._render_entry(entry))
        except Exception as exc:
            self._append_error(f"{self._t('job_fail')}: {exc}")

    def on_select_training_inputs(self, _event: wx.CommandEvent) -> None:
        zip_mode = self.src_choice.GetSelection() == 1
        wildcard = "Zip files (*.zip)|*.zip" if zip_mode else "Image files (*.jpg;*.jpeg;*.png;*.webp)|*.jpg;*.jpeg;*.png;*.webp"
        with wx.FileDialog(self, self._t("select_inputs"), wildcard=wildcard, style=wx.FD_OPEN | wx.FD_MULTIPLE) as d:
            if d.ShowModal() == wx.ID_CANCEL:
                return
            self.user_training_inputs = list(d.GetPaths())
            self.sel_count_lbl.SetLabel(f"{self._t('selected')}: {len(self.user_training_inputs)}")

    def on_train_user_model(self, _event: wx.CommandEvent) -> None:
        if not self.user_training_inputs:
            self._append_error(self._t("no_inputs"))
            return
        mode = "zip" if self.src_choice.GetSelection() == 1 else "file"
        cmd = ["py", "-3.11", "tools/train_user_model.py", "--source-mode", mode, "--inputs", *self.user_training_inputs]
        if mode == "file":
            cmd += ["--label", self.class_keys[self.class_choice.GetSelection()]]
        self._run_job(cmd, "train_user_model", epochs=10)

    def on_update_base_model(self, _event: wx.CommandEvent) -> None:
        self._run_job(["py", "-3.11", "tools/update_base_model.py"], "update_base_model", epochs=10)

    def on_refresh_display(self, _event: wx.CommandEvent) -> None:
        self._rerender_output()

    def on_clear_output(self, _event: wx.CommandEvent) -> None:
        self.output_history.clear()
        self.output.SetValue("")
        self.last_recommend_signature = None

    def on_set_log_error(self, _event: wx.CommandEvent) -> None:
        self._set_log_level("ERROR")
        self._append(self._t("log_level_changed").format(level=self.log_level))

    def on_set_log_debug(self, _event: wx.CommandEvent) -> None:
        self._set_log_level("DEBUG")
        self._append(self._t("log_level_changed").format(level=self.log_level))

    def on_show_version(self, _event: wx.CommandEvent) -> None:
        wx.MessageBox(
            self._t("version_message").format(version=self.app_version),
            self._t("version_title"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )

