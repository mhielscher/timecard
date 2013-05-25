import os
import datetime
import Xlib.display, Xlib.error
import subprocess
import pynotify

def find_display(max_n=9):
    display_name = ""
    test_count = 0
    while display_name == "":
        test_name = ":%d.0" % (test_count)
        try:
            display_name = Xlib.display.Display(test_name).display.display_name
        except Xlib.error.DisplayConnectionError:
            if test_count > max_n:
                return None
            test_count += 1
            continue
    return display_name

def get_active_window():
    window_id = subprocess.check_output(['xprop', '-root', '-f', '_NET_ACTIVE_WINDOW', '0x', r' $0\n', '_NET_ACTIVE_WINDOW']).split()[1]
    window_title = ' '.join(subprocess.check_output(['xprop', '-id', str(window_id), '-f', '_NET_WM_NAME', '0s', r' $0\n', '_NET_WM_NAME']).split()[1:]).strip('"')
    return window_title

def get_current_timestamp(compact=False):
    return format_timestamp(datetime.datetime.now(), compact=compact)

def write_note(filename, note):
    f = open(filename, 'a')
    print >>f, "%s: [Note] %s" % (get_current_timestamp(), note)
    f.close()


keywords = ['THERMS', 'cPanel', 'Parallels', '.php', 'phpmyadmin', 'WebHost', 'PHP:']
base_dir = '/home/restorer/Documents/devel/timecard'

if __name__ == '__main__':
    # If called from cron, find first display.
    if not 'DISPLAY' in os.environ:
        os.environ['DISPLAY'] = find_display()
    
    title = get_active_window()
    working = False
    for w in keywords:
        if w.lower() in title.lower():
            working = True
    
    os.chdir(base_dir)
    
    logname = None
    for filename in os.listdir('.'):
        if filename.endswith('.lock'):
            logname = filename.split('.')[0]
    
    if working and (not logname or not os.path.isfile(logname+".lock")):
        
        
        if not pynotify.init("Timecard"):
	        sys.exit(1)

        n = pynotify.Notification("Timecard", "You look like you're working - should start recording this stuff.")
        n.set_timeout(pynotify.EXPIRES_DEFAULT)
        n.show()
        
        subprocess.call('beep -f 1350 -r 3 -d 25'.split())

