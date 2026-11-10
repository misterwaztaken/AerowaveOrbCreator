

from .common import *
from .intro import *
from .editor import *

def main():
    root = tk.Tk()
    root.withdraw()
    root.title(APP_NAME)
    try:
        ip = asset_path("image/orangeorb.png")
        if ip:
            ico = Image.open(ip).convert("RGBA")
            ico = ico.crop(ico.getchannel("A").getbbox()).resize((64, 64), Image.LANCZOS)
            root._icon = ImageTk.PhotoImage(ico)
            root.iconphoto(True, root._icon)
    except Exception:
        pass

    intro = AeroIntro(root)                  # black fullscreen cover appears instantly
    root.intro = intro
    try:
        root.attributes("-fullscreen", True)
    except tk.TclError:
        pass
    app = OrbCreator(root)                   # build the editor behind the intro
    root.deiconify()
    try:
        root.attributes("-fullscreen", True)
    except tk.TclError:
        pass
    root.update()
    root.app = app

    def intro_done():
        try:
            root.focus_force()
        except tk.TclError:
            pass

    intro.start(on_done=intro_done)
    root.mainloop()


if __name__ == "__main__":
    main()
