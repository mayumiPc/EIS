"""
推論結果を表示し、テンプレートに沿った設置カタログ行を内部 SQLite に登録するダイアログ。

wx.ComboBox は必ず (parent, id, value, pos, size, choices, style) の形で生成する。
parent と style だけの生成は環境によってネイティブ側の表示が列とずれることがある。
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path

import wx

from .catalog_register import CatalogRegisterError, insert_row_jp, training_class_to_suggested_maker_ja
from .catalog_template import (
    COL_CAPACITY,
    COL_CITY,
    COL_KIND,
    COL_LOAD,
    COL_MEDIA,
    COL_MAKER,
    COL_NAME,
    COL_PREF,
    COL_USE,
)


def _dedupe_preserve(items: list[str]) -> list[str]:
    return list(dict.fromkeys([str(x).strip() for x in items if str(x).strip()]))


def _combo_standard(
    parent: wx.Window,
    *,
    choices: list[str],
    initial: str,
    width: int = 400,
) -> wx.ComboBox:
    """
    Phoenix 推奨: choices をリストで渡し、初期表示文字列を value に指定。
    Append だけの ComboBox は別ウィンドウ扱いになることがあるため使わない。
    """
    init = (initial or "").strip()
    ordered = _dedupe_preserve(choices)
    if init and init not in ordered:
        ordered.insert(0, init)
    if not ordered:
        ordered = [init] if init else [""]
    return wx.ComboBox(
        parent,
        wx.ID_ANY,
        init if init else ordered[0],
        wx.DefaultPosition,
        wx.Size(width, -1),
        ordered,
        wx.CB_DROPDOWN,
    )


class InferRegisterDialog(wx.Dialog):
    def __init__(
        self,
        parent: wx.Window,
        *,
        manufacturer: str,
        probabilities: Mapping[str, float],
        media_path: str,
        class_keys: list[str],
        translate: Callable[[str], str],
        catalog_ready: bool,
        get_distinct_values: Callable[[str], list[str]],
        on_registered: Callable[[], None],
    ) -> None:
        title = translate("infer_register_title")
        super().__init__(parent, title=title, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, size=(600, 720))
        self._t = translate
        self._catalog_ready = catalog_ready
        self._on_registered = on_registered
        self._media_path = media_path
        self._infer_class = (manufacturer or "").strip()
        self._training_class_keys = tuple(class_keys)  # 呼び出し互換（将来メーカー候補拡張用）

        root = wx.BoxSizer(wx.VERTICAL)

        # 上部は「確率一覧」のみ（推論クラスはメーカー行に一本化して重複表示しない）
        prob_block = f"{self._t('probabilities')}:\n{self._fmt_prob(probabilities)}"
        st_prob = wx.StaticText(self, label=prob_block)
        st_prob.SetForegroundColour(wx.Colour(40, 40, 40))
        root.Add(st_prob, 0, wx.ALL | wx.EXPAND, 10)

        if not catalog_ready:
            warn = wx.StaticText(self, label=self._t("reg_no_catalog"))
            warn.SetForegroundColour(wx.Colour(180, 60, 60))
            root.Add(warn, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        # ScrolledPanel は子のネイティブコントロールと相性が悪いことがあるため通常 Panel
        panel = wx.Panel(self, name="EIS_InferRegisterForm")
        form = wx.BoxSizer(wx.VERTICAL)

        suggested_ja = training_class_to_suggested_maker_ja(manufacturer)
        # メーカー欄の候補は「DB のメーカー列」のみ（英語 class_keys は混ぜない＝種類名が紛れ込むのを防ぐ）
        makers_from_db = _dedupe_preserve(get_distinct_values(COL_MAKER))
        initial_maker = suggested_ja if suggested_ja else self._infer_class
        if not initial_maker and makers_from_db:
            initial_maker = makers_from_db[0]
        maker_choice_list = _dedupe_preserve([initial_maker, *makers_from_db])

        def add_field(
            label_main: str,
            ctrl: wx.Control,
            *,
            sublabel: str | None = None,
        ) -> None:
            col = wx.BoxSizer(wx.VERTICAL)
            lab1 = wx.StaticText(panel, label=label_main)
            lab1.SetFont(lab1.GetFont().Bold())
            col.Add(lab1, 0, wx.BOTTOM, 2)
            if sublabel:
                lab2 = wx.StaticText(panel, label=sublabel)
                lab2.SetForegroundColour(wx.Colour(90, 90, 90))
                col.Add(lab2, 0, wx.BOTTOM, 4)
            row = wx.BoxSizer(wx.HORIZONTAL)
            row.Add(col, 0, wx.RIGHT, 12)
            row.Add(ctrl, 1, wx.EXPAND)
            form.Add(row, 0, wx.EXPAND | wx.BOTTOM, 12)

        maker_sublabel = self._t("reg_maker_infer_hint").format(cls=self._infer_class, ja=suggested_ja or "—")
        self._cb_maker = _combo_standard(panel, choices=maker_choice_list, initial=initial_maker)
        add_field(self._t("reg_field_maker"), self._cb_maker, sublabel=maker_sublabel)

        self._cb_kind = _combo_standard(panel, choices=get_distinct_values(COL_KIND), initial="")
        add_field(self._t("reg_field_kind"), self._cb_kind)

        self._cb_pref = _combo_standard(panel, choices=get_distinct_values(COL_PREF), initial="")
        add_field(self._t("reg_field_pref"), self._cb_pref)

        self._cb_city = _combo_standard(panel, choices=get_distinct_values(COL_CITY), initial="")
        add_field(self._t("reg_field_city"), self._cb_city)

        default_site = Path(media_path).stem if media_path else ""
        self._tc_site = wx.TextCtrl(panel, value=default_site, size=(400, -1))
        add_field(self._t("reg_field_site"), self._tc_site)

        self._tc_media = wx.TextCtrl(panel, value=media_path, size=(400, -1))
        add_field(self._t("reg_field_media"), self._tc_media)

        self._cb_use = _combo_standard(panel, choices=get_distinct_values(COL_USE), initial="")
        add_field(self._t("reg_field_use"), self._cb_use)

        self._cb_load = _combo_standard(panel, choices=get_distinct_values(COL_LOAD), initial="")
        add_field(self._t("reg_field_load"), self._cb_load)

        self._cb_cap = _combo_standard(panel, choices=get_distinct_values(COL_CAPACITY), initial="")
        add_field(self._t("reg_field_capacity"), self._cb_cap)

        hint = wx.StaticText(panel, label=self._t("reg_required_hint"))
        hint.SetForegroundColour(wx.Colour(100, 100, 100))
        form.Add(hint, 0, wx.TOP | wx.EXPAND, 4)

        panel.SetSizer(form)
        root.Add(panel, 1, wx.LEFT | wx.RIGHT | wx.EXPAND, 14)

        btn_row = wx.BoxSizer(wx.HORIZONTAL)
        self._btn_save = wx.Button(self, label=self._t("reg_save"))
        self._btn_save.Bind(wx.EVT_BUTTON, self._on_save)
        self._btn_save.Enable(catalog_ready)
        btn_close = wx.Button(self, wx.ID_CANCEL, label=self._t("reg_close"))
        btn_row.AddStretchSpacer(1)
        btn_row.Add(self._btn_save, 0, wx.RIGHT, 8)
        btn_row.Add(btn_close, 0)
        root.Add(btn_row, 0, wx.ALL | wx.EXPAND, 10)

        self.SetSizer(root)
        self.CenterOnParent()

    @staticmethod
    def _fmt_prob(probs: Mapping[str, float]) -> str:
        lines = [f"  {k}: {v * 100:.1f}%" for k, v in sorted(probs.items(), key=lambda x: -x[1])]
        return "\n".join(lines) if lines else "—"

    def _on_save(self, _evt: wx.CommandEvent) -> None:
        row = {
            COL_MAKER: self._cb_maker.GetValue(),
            COL_KIND: self._cb_kind.GetValue(),
            COL_PREF: self._cb_pref.GetValue(),
            COL_CITY: self._cb_city.GetValue(),
            COL_NAME: self._tc_site.GetValue(),
            COL_MEDIA: self._tc_media.GetValue(),
            COL_USE: self._cb_use.GetValue(),
            COL_LOAD: self._cb_load.GetValue(),
            COL_CAPACITY: self._cb_cap.GetValue(),
        }
        try:
            new_id = insert_row_jp(row, auto_id=True)
        except CatalogRegisterError as e:
            wx.MessageBox(str(e), self._t("reg_save"), wx.OK | wx.ICON_ERROR, self)
            return
        wx.MessageBox(
            self._t("reg_saved_ok").format(id=new_id),
            self._t("reg_save"),
            wx.OK | wx.ICON_INFORMATION,
            self,
        )
        self._on_registered()
        self.EndModal(wx.ID_OK)


def show_infer_register_dialog(
    parent: wx.Window,
    *,
    manufacturer: str,
    probabilities: Mapping[str, float],
    media_path: str,
    class_keys: list[str],
    translate: Callable[[str], str],
    catalog_ready: bool,
    get_distinct_values: Callable[[str], list[str]],
    on_registered: Callable[[], None],
) -> None:
    dlg = InferRegisterDialog(
        parent,
        manufacturer=manufacturer,
        probabilities=probabilities,
        media_path=media_path,
        class_keys=class_keys,
        translate=translate,
        catalog_ready=catalog_ready,
        get_distinct_values=get_distinct_values,
        on_registered=on_registered,
    )
    dlg.ShowModal()
    dlg.Destroy()
