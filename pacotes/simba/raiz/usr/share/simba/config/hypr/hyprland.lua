-- Learn how to configure Hyprland: https://wiki.hypr.land/Configuring/Start/

-- Simba's bootstrap keeps path setup out of this user config.
dofile((os.getenv("SIMBA_PATH") or "/usr/share/simba") .. "/default/hypr/bootstrap.lua")

-- Disable all Simba default bindings. Add your own in hypr/bindings.lua.
-- simba_default_bindings = false
--
-- Or disable only bindings for Simba's preinstalled apps/web apps while
-- keeping core window-manager bindings:
-- simba_preinstalled_bindings = false

-- Load Simba defaults.
require("default.hypr.simba")

-- Put your personal overrides in these files. They're loaded after Simba's
-- defaults so package updates can improve the defaults without rewriting your
-- ~/.config/hypr files.
require("hypr.monitors")
require("hypr.input")
require("hypr.bindings")
require("hypr.looknfeel")
require("hypr.autostart")

-- Toggle config flags dynamically.
require("default.hypr.toggles")

-- Add any other personal Hyprland configuration below.
-- o.window("qemu", { workspace = "5" })
