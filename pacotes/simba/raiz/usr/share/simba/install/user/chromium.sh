# Chromium ships in the base packages, so it never goes through
# simba-install-browser, and fresh installs mark every migration as already
# applied. Without this, the bundled extensions load but have no native
# messaging host to talk to.
simba-install-chromium-copy-url
simba-install-chromium-ytdlp
