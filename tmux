
#> cat ~/.tmux.conf
# ══════════════════════════════════════════════════════════
#  CHEAT SHEET                          prefix = C-a
#  (`prefix ?` lists every live binding — this is the tour)
# ══════════════════════════════════════════════════════════
#
#  ── SCROLLBACK / COPY ────────────────────────────────────
#  C-a C-p    whole scrollback -> macOS clipboard
#  C-a P      whole scrollback -> file (prompts, prefilled path)
#  C-a /      copy mode + search-up prompt (the common case)
#  C-a [      enter copy mode        C-a ]   paste buffer
#  C-a =      list/choose paste buffers
#  drag       mouse-select copies, stays in copy mode
#
#  in copy mode (vi keys):
#    g / G          top of history / bottom
#    C-u / C-d      half page up / down
#    ?  <text>      search UP into history  <- what you want;
#                   copy mode opens at the BOTTOM, so `/`
#                   (search down) usually finds nothing
#    /  <text>      search down toward the bottom
#    n / N          next match / previous match
#    * / #          search fwd/back for word under cursor
#    v              start selection    C-v  block select
#    y              yank -> pbcopy, exit
#    q or Escape    leave copy mode
#  select all: C-a [  then  g v G $ y
#
#  Beyond a quick eyeball, grep it instead:  tgrep 'pattern'
#  (shell fn in ~/.zshrc; `tgrep -a` sweeps every pane)
#
#  ── PANES ────────────────────────────────────────────────
#  C-a |      split vertical   (inherits cwd)
#  C-a -      split horizontal (inherits cwd)
#  C-a h/j/k/l  move left/down/up/right   (repeatable)
#    NOTE: this rebinds default `C-a l` (last-window). Use
#          `C-a w` or `C-a n`/`C-a p` to jump windows instead.
#  C-a z      zoom / unzoom pane    C-a x   kill pane
#  C-a {  }   swap pane back / forward
#  C-a !      break pane into its own window
#  C-a q      show pane numbers (type one to jump)
#  C-a Space  cycle layouts
#
#  ── WINDOWS / SESSIONS ───────────────────────────────────
#  C-a c      new window (inherits cwd)   C-a &  kill window
#  C-a 1..9   select window (1-based, renumbered on close)
#  C-a n / p  next / previous window
#  C-a w      window picker   C-a s  session picker
#  C-a ,      rename window   C-a $  rename session
#  C-a d      detach          `tmux a`  reattach
#
#  ── MISC ─────────────────────────────────────────────────
#  C-a r      reload this file
#  C-a :      tmux command prompt
#  C-a C-a    send a literal C-a through to the shell
#  C-a I      install plugins (tpm)      C-a U  update them
#
#  ── GOTCHAS ──────────────────────────────────────────────
#  * history-limit is 50000 (below) — "whole scrollback" means
#    the last 50k lines; older output is already discarded.
#  * Sessions auto-save/restore via continuum+resurrect.
# ══════════════════════════════════════════════════════════

# ─── General ──────────────────────────────────────────────
set -g mouse on
setw -g mode-keys vi
set -g status-keys vi

set -sg escape-time 10           # 500ms default = ESC lag in vim
set -g history-limit 50000       # 2000 default truncates build output
set -g focus-events on           # vim autoread, terminal theme sync
set -g set-clipboard on          # OSC 52: copy works over SSH too

# 1-based windows, renumber on close
set -g base-index 1
setw -g pane-base-index 1
set -g renumber-windows on

# True color (infocmp tmux-256color verified present)
set -g default-terminal "tmux-256color"
set -ga terminal-overrides ",*256col*:Tc,xterm-256color:RGB"

# ─── Prefix: C-a ──────────────────────────────────────────
unbind C-b
set -g prefix C-a
bind C-a send-prefix

# ─── Bindings ─────────────────────────────────────────────
# -N attaches a note. Without it a binding is INVISIBLE to
# `prefix ?` (list-keys -N), which only lists noted keys.
bind -N "Reload tmux.conf" \
  r source-file ~/.tmux.conf \; display "tmux.conf reloaded"

# Splits and new windows inherit the current directory
bind -N "Split vertically (keep cwd)"   | split-window -h -c "#{pane_current_path}"
bind -N "Split horizontally (keep cwd)" - split-window -v -c "#{pane_current_path}"
bind -N "New window (keep cwd)"         c new-window -c "#{pane_current_path}"
unbind '"'
unbind %

# Vim-style pane movement (-r = repeatable without re-pressing prefix)
bind -r -N "Select pane left"  h select-pane -L
bind -r -N "Select pane down"  j select-pane -D
bind -r -N "Select pane up"    k select-pane -U
bind -r -N "Select pane right" l select-pane -R

# ─── Copy mode (macOS: pbcopy, not xclip) ─────────────────
# prefix / : jump straight into copy mode with a search prompt.
# search-BACKWARD is deliberate — copy mode opens at the bottom,
# so searching up into history is the only useful direction.
# (Plain `/` inside copy mode is tmux's default search-forward.)
# Overrides default `prefix /` = describe-key (press a key, get
# its binding). That still exists as `prefix ?` -> full key list.
bind -N "Search scrollback (upward)" \
  / copy-mode \; command-prompt -T search -p "(search up)" \
  { send -X search-backward "%%" }

bind -T copy-mode-vi v send -X begin-selection
bind -T copy-mode-vi C-v send -X rectangle-toggle
bind -T copy-mode-vi y send -X copy-pipe-and-cancel "pbcopy"

# ─── Dump scrollback ──────────────────────────────────────
# capture-pane flags worth knowing when doing this by hand:
#   -p   print to stdout instead of a tmux buffer
#   -S - start at the oldest line still in history
#   -J   join wrapped lines. Not cosmetic: tmux stores a wrapped
#        line as two rows, so without -J a grep for a long token
#        can silently miss it. Also implies -T.
#   e.g.  tmux capture-pane -pJ -S - | pbcopy
#   NB: -E defaults to the bottom of the visible pane, which is
#       what you want. `-E -` means the same thing, not "end of
#       history" — there is no flag for that, and none is needed.
#
# prefix P : whole scrollback -> file (prompts for path)
# Routed through run-shell, not save-buffer: tmux does NOT expand ~ itself and
# would create a literal directory named "~". /bin/sh expands it correctly.
bind -N "Save whole scrollback to a file" \
  P command-prompt -p 'save history to:' -I '~/tmux-#{session_name}-#{window_index}.txt' \
  'run-shell "tmux capture-pane -p -S - -t \"#{pane_id}\" > %1 && tmux display \"saved to %1\""'

# prefix C-p : whole scrollback -> macOS clipboard
bind -N "Copy whole scrollback to clipboard" \
  C-p run-shell 'tmux capture-pane -p -S - -t "#{pane_id}" | pbcopy' \; display "scrollback copied"

# prefix K : wipe screen AND scrollback (shifted on purpose —
# this is irreversible; capture-pane/tgrep find nothing after).
#
# The sleep is load-bearing, not superstition. send-keys is
# ASYNC: tmux queues C-l and returns immediately, so a plain
# `send-keys C-l \; clear-history` clears history FIRST, then
# the shell redraws and pushes the still-visible screen back
# into history — measured 27 lines surviving. Letting the shell
# act first gives history_size 0.
#   `send-keys -R \; clear-history` also measures 0, but leaves
#   the pane blank with NO prompt until you hit Enter. C-l lets
#   the shell redraw its prompt properly.
# run-shell -b so the 0.3s wait doesn't freeze the whole server.
bind -N "Clear screen and scrollback" K send-keys C-l \; \
  run-shell -b 'sleep 0.3; tmux clear-history -t "#{pane_id}"; tmux display "scrollback cleared"'

# ─── Plugins (prefix + I to install) ──────────────────────
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-sensible'
set -g @plugin 'tmux-plugins/tmux-yank'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'tmux-plugins/tmux-continuum'
set -g @continuum-restore 'on'

run '~/.tmux/plugins/tpm/tpm'

# Must come AFTER tpm: tmux-yank binds MouseDragEnd1Pane to
# copy-pipe-and-cancel, which drops you out of copy mode on every
# drag-select. -no-clear keeps the selection and the mode.
bind -T copy-mode-vi MouseDragEnd1Pane send -X copy-pipe-no-clear "pbcopy"


