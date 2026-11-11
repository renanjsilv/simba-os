# Real newlines, not a literal \n: the card renders the body as it arrives, and
# elides past three lines.
simba-notification-send -u normal -t 20000 -g  "Learn Keybindings" \
  $'Super + K for cheatsheet.\nSuper + Space for the Start menu.' \
  --exec simba-menu-keybindings
