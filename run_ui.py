import wx

from eis.ui import EISFrame


def main() -> None:
    app = wx.App(False)
    frame = EISFrame()
    frame.Show()
    app.MainLoop()


if __name__ == "__main__":
    main()

