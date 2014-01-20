from gi.repository import Gtk, Wnck
from sh import ps

chrome_registered = False

def chrome_tab_changed(window):
    if Wnck.Screen.get_default().get_active_window() != window:
        return
    print window.get_name()

def focus_changed(screen, prev_window):
    win = screen.get_active_window()
    if not win:
        return
    global chrome_registered
    process_cmd = ps('-p', win.get_pid(), '-o', 'cmd', 'h').strip()
    print win.get_name()
    if not chrome_registered and process_cmd.split()[0].split('/')[-1] == "google-chrome":
        win.connect("name-changed", chrome_tab_changed)
        chrome_registered = True

s = Wnck.Screen.get_default()
s.connect("active-window-changed", focus_changed)

Gtk.main()
