# Set default XCompose that is triggered with CapsLock
tee ~/.XCompose >/dev/null <<EOF
# Run simba-restart-xcompose to apply changes

# Include fast emoji access
include "/usr/share/simba/default/xcompose"

# Identification
<Multi_key> <space> <n> : "$SIMBA_USER_NAME"
<Multi_key> <space> <e> : "$SIMBA_USER_EMAIL"
EOF
