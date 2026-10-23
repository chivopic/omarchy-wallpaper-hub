# Release readiness evidence

`test-results.png` is a rendered excerpt of the actual test and lint output in
the adjacent `before-*.txt` and `after-*.txt` files. It is test evidence, not a
product screenshot or a screenshot of the running desktop UI.

The baseline files were captured from `main` in an isolated temporary archive;
the after files were captured from `fix/release-readiness`. Reproduce the Python
suite with:

```bash
python3 -m unittest discover -s tests -v
```

For QML lint, point a temporary `qs` import link at the installed Omarchy shell
and run:

```bash
mkdir -p /tmp/omarchy-wallpaper-hub-qmlimports
ln -sfn /usr/share/omarchy/shell /tmp/omarchy-wallpaper-hub-qmlimports/qs
/usr/lib/qt6/bin/qmllint -I /tmp/omarchy-wallpaper-hub-qmlimports WallpaperPanel.qml
```

The baseline QML output reports the missing `openAdjustModal` member at both
call sites. The updated output has no such warning; unrelated dynamic theme
singleton warnings remain.

The deletion regression was reproduced in the baseline suite: both deletion
tests passed after taking the `FILE_NOT_FOUND` branch. The updated tests use
valid catalog images, assert the specific active/native protection error, and
assert that `gio trash` is never called.

`regression-on-main.txt` records the new concurrent-writer test run against the
original `main` backend; it fails because parallel stale snapshots discard
favorites. The same test passes against the updated backend.
