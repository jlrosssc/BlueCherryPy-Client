# Third-Party Licenses

BlueCherryPy Client is licensed under GPL-3.0-or-later. It depends on
third-party packages and external tools that remain under their own
licenses.

| Component | License | Project |
|---|---|---|
| PyQt6 | GPL-3.0 or commercial license | https://www.riverbankcomputing.com/software/pyqt/ |
| Qt 6 | LGPL-3.0, GPL-3.0, or commercial license, depending on modules and distribution | https://www.qt.io/ |
| requests | Apache-2.0 | https://github.com/psf/requests |
| urllib3 | MIT | https://github.com/urllib3/urllib3 |
| keyring | MIT | https://github.com/jaraco/keyring |
| Pillow | MIT-CMU | https://github.com/python-pillow/Pillow |
| lxml | BSD-3-Clause | https://github.com/lxml/lxml |
| FFmpeg | LGPL/GPL depending on build configuration | https://ffmpeg.org/ |

## Notes

PyQt6 is available under GPL-3.0 or a commercial license. Because this
application uses PyQt6, the project license is GPL-3.0-or-later rather
than GPL-2.0-only.

FFmpeg is not bundled in this repository. The install instructions ask
Linux users to install FFmpeg from their operating system package
manager so PyQt6 multimedia playback can use the system multimedia
backend.
