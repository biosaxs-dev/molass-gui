"""Runtime feature flags, set once at startup by launcher.main() from CLI args.

Dropbox support (see Copilot/DESIGN_dropbox_integration.md) defaults to off
until it's been through more real-world testing -- start the GUI with
`--dropbox-support` to opt in.
"""
DROPBOX_SUPPORT_ENABLED = False

# Immature features (SDM (lognormal) model, rank "Suggest" button) are hidden
# by default -- start the GUI with `--develop` to opt in.
DEVELOP_MODE_ENABLED = False
