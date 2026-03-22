import wx

from eis.catalog_template import apply_pending_catalog_on_startup
from eis.ui import EISFrame


def main() -> None:
    apply_pending_catalog_on_startup()
    app = wx.App(False)
    frame = EISFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()

