# Reporting a confirmed bug

Simba OS has no public issue tracker. When a crash is confirmed to be a bug in a
Simba OS component (anything under /usr/share/simba, /usr/bin/simba-* or the
user's ~/.config/simba), write a short report for the user instead:

- program and version (`simba-version`, `pacman -Q <package>`)
- the symbolized backtrace and the signal
- the exact steps that reproduce it

Save it as `~/simba-falha-<programa>-<data>.md` and tell the user where it is.
Bugs in upstream Arch packages go to the package's own tracker (see `pacman -Qi`).
