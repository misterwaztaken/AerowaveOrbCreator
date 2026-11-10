"""
Aerowave Orb Creator
====================
Keep these files next to this script (or inside an "assets" folder beside it):

    aerowave.png, orbcreator.png, Orangeorb.png      - the three logo components
    orbcreatorjingle.wav                              - intro jingle
    saved.wav                                         - "orb saved" sound
    darkbutton.png, ecobutton.png, aquabutton.png,
    dorficbutton.png                                  - UI selector orbs
    exittext.png, exitjingle.wav                      - exit animation

The chosen UI theme, the last folder you saved to and your 10 most recent colours are
remembered in config.aero
(created next to this script).
Requires: Pillow, numpy   ->   pip install pillow numpy
"""
from src.main import main


if __name__ == "__main__":
    main()
