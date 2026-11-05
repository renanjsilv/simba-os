# Upgrades must not delete the version a running process is executing from:
# mise up would prune the old install dir out from under a live session.
mise settings set upgrade.auto_prune false

simba-mise-install codex
simba-mise-install claude
simba-mise-install crush
simba-mise-install gh
simba-mise-install copilot
simba-mise-install opencode
simba-mise-install npm:playwright playwright
simba-mise-install pi
simba-mise-install github:can1357/oh-my-pi omp
simba-mise-install npm:@xai-official/grok grok
# Cursor's own installer links the same path, so a re-provision keeps it.
simba-cmd-missing cursor-agent && simba-mise-install cursor-agent
simba-mise-install npm:@kitlangton/ghui ghui
simba-mise-install aqua:modem-dev/hunk hunk
if simba-cmd-missing muse; then
  simba-mise-install "http:muse[url=https://api.meta.ai/muse-launcher.sh,bin=muse,version_list_url=https://api.meta.ai/muse-code/channels/muse-stable,version_json_path=.version]" muse
fi
