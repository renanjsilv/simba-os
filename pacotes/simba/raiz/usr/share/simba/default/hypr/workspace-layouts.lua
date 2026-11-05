-- Restore workspace layouts saved by simba-hyprland-workspace-layout-toggle.

local paths = require("default.hypr.paths")
local require_all = require("default.hypr.require_all")

local layouts_dir = paths.state_home .. "/simba/workspace-layouts"

require_all.files(layouts_dir, "simba.workspace-layouts", { reload = true })
