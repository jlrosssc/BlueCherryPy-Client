import sys
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from bluecherrypy.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")          # cross-platform style; makes dropdowns/combos respect dark palette
    app.setApplicationName("BluecherryPy")
    app.setOrganizationName("BluecherryPy")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)

    # Dark palette so Fusion-styled widgets match the dark UI
    from PyQt6.QtGui import QPalette, QColor
    pal = QPalette()
    bg   = QColor("#1c1c1e")
    bg2  = QColor("#2c2c2e")
    txt  = QColor("#e0e0e0")
    sel  = QColor("#2c5282")
    hlt  = QColor("#4a9eff")
    pal.setColor(QPalette.ColorRole.Window,          bg)
    pal.setColor(QPalette.ColorRole.WindowText,      txt)
    pal.setColor(QPalette.ColorRole.Base,            bg2)
    pal.setColor(QPalette.ColorRole.AlternateBase,   bg)
    pal.setColor(QPalette.ColorRole.ToolTipBase,     bg2)
    pal.setColor(QPalette.ColorRole.ToolTipText,     txt)
    pal.setColor(QPalette.ColorRole.Text,            txt)
    pal.setColor(QPalette.ColorRole.Button,          bg2)
    pal.setColor(QPalette.ColorRole.ButtonText,      txt)
    pal.setColor(QPalette.ColorRole.BrightText,      QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Highlight,       sel)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    pal.setColor(QPalette.ColorRole.Link,            hlt)
    app.setPalette(pal)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
