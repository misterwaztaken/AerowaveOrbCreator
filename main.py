"""
Aerowave Orb Creator
====================
This script is the main script's extension; extending src/main.py
You can run this script in your terminal or use it for what PyInstaller uses

Listed below, the assets that are depended on (please keep them where they are):

    in assets/image/ 
        - aerowave.png, orbcreator.png, orangeorb.png    - the three logo components
        - darkbutton.png                                 - UI selector orbs
          ecobutton.png
          aquabutton.png
          dorficbutton.png                               
        - exittext.png                                   - exit animation
        
    in assets/sfx/
        - orbcreatorjingle.wav                           - intro jingle
        - saved.wav                                      - "orb saved" sound
        - exitjingle.wav                                 - exit jingle
        
The chosen UI theme, the last folder you saved to and your 10 most recent colours are
remembered in config.aero (which is created in the same place this script is in).

Requires: Pillow, numpy   ->   pip install pillow numpy

For any additional information, please read the README (which may not be up-to-date, bear with me)
Split Python files have brief info about them in the top, like this massive comment.
"""

from src.main import main

if __name__ == "__main__":
    main()
