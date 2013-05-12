#!/usr/bin/python

"""timecard.py

Records time usage for e.g. billable time and proof of work.
"""

import sys
import os
import signal
import subprocess
import time
import argparse
import datetime
from dateutil import parser as dateparser
import gtk.gdk

def find_display(max_n=9):
    import Xlib.display, Xlib.error
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
    return int(window_id, 16), window_title

def get_lock(lockfilename):
    if not os.path.isfile(lockfilename):
        return None
    try:
        pid = int(open(lockfilename, 'r').read().strip())
    except ValueError:
        return None
    return pid

def lock_timecard(pid, lockfilename):
    if not get_lock(lockfilename):
        open(lockfilename, 'w').write(str(pid))
        return True
    else:
        return False

def release_lock(lockfilename):
    if get_lock(lockfilename) == os.getpid():
        os.remove(lockfilename)
        return True
    else:
        return False

def format_timestamp(dt, compact=False):
    if compact:
        return dt.strftime("%Y-%m-%d_%H:%M:%S")
    else:
        return dt.strftime("%H:%M:%S, %a %b %d, %Y")

def get_current_timestamp(compact=False):
    return format_timestamp(datetime.datetime.now(), compact=compact)

def start_log():
    global args
    f = open(args.file, 'a')
    print >>f, "-- Starting log at %s --" % (get_current_timestamp())
    f.close()

def monitor():
    global args
    f = open(args.file, 'a')
    print >>f, "%s: %s" % (get_current_timestamp(), get_active_window())
    f.close()

def close_log():
    global args
    f = open(args.file, 'a')
    print >>f, "-- Closing log at %s --" % (get_current_timestamp())
    f.close()

def stop_monitoring(signum, frame):
    if signum == signal.SIGTERM:
        close_log()
        if release_lock(args.lockfile):
            sys.exit(0)
        else:
            print >>sys.stderr, "Failed to release lock."
            sys.exit(1)

def take_screenshot():
    w = gtk.gdk.get_default_root_window()
    sz = w.get_size()
    pb = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB,False,8,sz[0],sz[1])
    pb = pb.get_from_drawable(w,w.get_colormap(),0,0,0,0,sz[0],sz[1])
    if (pb != None):
        pb.save(os.path.join(args.screenshots, "%s.png" % (get_current_timestamp(compact=True))), "png", 9)
        return True
    else:
        return False


# If called from cron, find first display.
if not 'DISPLAY' in os.environ:
	os.environ['DISPLAY'] = find_display()

commands = ["start", "stop", "list", "analyze", "test"]

argparser = argparse.ArgumentParser(description="Record or analyze time usage.")
argparser.add_argument('-v', '--verbose', action='count')
argparser.add_argument('-f', '--file', metavar='file', default='timecard.log', help='Time log file.')
argparser.add_argument('-l', '--lockfile', metavar='lockfile', default='timecard.lock', help='Lock file name.')
argparser.add_argument('-s', '--screenshots', metavar='dir', nargs='?', default=None, const='screenshots', help='Take screenshots with every log entry. Optional: directory to store screenshots (default is screenshots/).')
argparser.add_argument('-i', '--interval', metavar='interval', type=int, default=300, help='Seconds between monitor reports.')
argparser.add_argument('command', choices=commands)
argparser.add_argument('timerange', nargs='?', help='Time range for list command.')
args = argparser.parse_args()

if args.command == 'start':
    if get_lock(args.lockfile):
        print >>sys.stderr, "Timecard is already locked."
        sys.exit(1)
    
    pid = os.fork()
    if pid > 0:
        #print "Parent reports child pid=%d" % pid
        if not lock_timecard(pid, args.lockfile):
            os.kill(pid, signal.SIGTERM)
            print >>sys.stderr, "Unable to create lock file."
            sys.exit(1)
        print "Clocked in at %s." % (datetime.datetime.now().strftime("%H:%M:%S, %a %b %d, %Y"))
        sys.exit(0)
    
    # Child process - this will do the monitoring
    # Give the parent a chance to do last checks and kill us if needed.
    time.sleep(2)
    start_log()
    time.sleep(5)
    signal.signal(signal.SIGTERM, stop_monitoring)
    while True:
        monitor()
        if args.screenshots:
            take_screenshot()
        time.sleep(args.interval)

elif args.command == 'stop':
    pid = get_lock(args.lockfile)
    if not pid:
        print >>syd.stderr, "Could not get a valid PID from lock file."
        sys.exit(1)
    os.kill(pid, signal.SIGTERM)
    print "Clocked out at %s." % (datetime.datetime.now().strftime("%H:%M:%S, %a %b %d, %Y"))

elif args.command == 'list':
    total_log = map(lambda l: l.strip(), open(args.file, 'r').readlines())
    spans = []
    for line in total_log:
        if len(spans)==0 and not line.startswith("-- Starting"):
            continue
        elif line.startswith("-- Starting"):
            timestamp = dateparser.parse(line[len("-- Starting log at "):-3])
            spans.append([(timestamp, line)])
        elif line.startswith("-- Closing"):
            timestamp = dateparser.parse(line[len("-- Closing log at "):-3])
            spans[-1].append((timestamp, line))
        else:
            timestamp = dateparser.parse(':'.join(line.split(':')[:3]))
            spans[-1].append((timestamp, ':'.join(line.split(':')[3:])))
    total_hours = 0.0
    for span in spans:
        start_time = span[0][0]
        end_time = span[-1][0]
        delta = end_time - start_time
        hours = delta.total_seconds()/3600
        total_hours += hours
        print "Worked from %s to %s\n  -- Total %.3f hours." % (format_timestamp(start_time), format_timestamp(end_time), hours)
    print "\nTotal hours worked in this timespan: %.3f" % (total_hours)
            

elif args.command == 'test':
    print args
    wid, wname = get_active_window()
    print wid
    w = gtk.gdk.window_lookup(wid)
    print w


