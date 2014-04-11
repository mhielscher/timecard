#!/usr/bin/python

"""timecard.py

Records time usage for e.g. billable time and proof of work.
"""

import sys
import os
import logging
import signal
import subprocess
import time
import argparse
import datetime
import re
import ctypes
import yaml
from dateutil import parser as dateparser
import screenshot
from gi.repository import Gtk, GLib, Wnck, Notify
from sh import ps

class XScreenSaverInfo( ctypes.Structure):
    """ typedef struct { ... } XScreenSaverInfo; """
    _fields_ = [('window',      ctypes.c_ulong), # screen saver window
                ('state',       ctypes.c_int),   # off,on,disabled
                ('kind',        ctypes.c_int),   # blanked,internal,external
                ('since',       ctypes.c_ulong), # milliseconds
                ('idle',        ctypes.c_ulong), # milliseconds
                ('event_mask',  ctypes.c_ulong)] # events

#########
# Config
#########

screenshot_types = {
    'all': screenshot.ENTIRE_DESKTOP,
    'active-window': screenshot.ACTIVE_WINDOW,
    'active-monitor': screenshot.ACTIVE_MONITOR,
    'cursor-monitor': screenshot.CURSOR_MONITOR
}

default_config = {
    'logfile': 'timecard.log',
    'screenshots': False,
    'idle-time': 480 # seconds
}

config = {}

def load_config(path=None):
    global logger, config, default_config
    if path:
        try:
            config = yaml.load(open(path, 'r'))
        except IOError:
            logger.error("Could not open config file %s", path)
            sys.exit(1)
    else:
        try:
            config = yaml.load(open(os.environ['HOME']+"/.config/timecard/timecard.conf", 'r'))
        except IOError:
            try:
                config = yaml.load(open("/etc/timecard/timecard.conf", 'r'))
            except IOError:
                config = default_config
    config = dict(default_config.items() + config.items())
    if config['screenshots'] and config['screenshots']['type'] and \
        config['screenshots']['type'] in screenshot_types:
            config['screenshots']['type'] = screenshot_types[config['screenshots']['types']]

def process_args(args):
    global config
    logger.debug(args)
    
    #if 'configfile' in args:
    #    load_config(args.configfile)
    
    args.cardname = os.path.splitext(os.path.split(config['logfile'])[1])[0]
    args.lockfile = os.path.join('/tmp', args.cardname+'.lock')
    
    config['logfile'] = config['logfile']
    config['cardname'] = os.path.splitext(os.path.split(config['logfile'])[1])[0]
    config['lockfile'] = os.path.join('/tmp', config['cardname']+'.lock')
    
    if 'screenshots' in args and args.screenshots != None:
        config['screenshots'] = {}
        config['screenshots']['directory'] = args.screenshots
        config['screenshots']['type'] = args.screenshot_type
        config['screenshots']['interval'] = args.screenshot_interval
        config['screenshots']['notify'] = args.notify
    
    if 'idletime' in args:
        config['idle-time'] = args.idletime
    
    logger.debug("Arguments:")
    for arg, val in vars(args).items():
        logger.debug("  %s = %s", arg, val)
    logger.debug("Config:")
    for key, val in config.items():
        logger.debug("  %s = %s", key, val)
    
    logger.debug(yaml.dump(config, default_flow_style=False))


registered_windows = set()

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
    return window_title

def window_name_changed(window):
    if Wnck.Screen.get_default().get_active_window() != window:
        return
    process_cmd = ps('-p', window.get_pid(), '-o', 'cmd', 'h').strip()
    monitor(process_cmd, window.get_name())

def application_closed(screen, application):
    global registered_windows
    logger.debug("pid %d closed:" % (application.get_pid()))
    logger.debug("  Deregistering windows: %s" % ([w.get_name() for w in application.get_windows()]))
    registered_windows -= frozenset(application.get_windows())

def focus_changed(screen, prev_window):
    global registered_windows
    window = screen.get_active_window()
    if not window:
        return
    process_cmd = ps('-p', window.get_pid(), '-o', 'cmd', 'h').strip()
    monitor(process_cmd, window.get_name())
    if window not in registered_windows:
    #and process_cmd.split()[0].split('/')[-1] == "google-chrome":
        window.connect("name-changed", window_name_changed)
        registered_windows.add(window)

def get_idle_time():
    xlib = ctypes.cdll.LoadLibrary( 'libX11.so')
    dpy = xlib.XOpenDisplay( os.environ['DISPLAY'])
    root = xlib.XDefaultRootWindow( dpy)
    xss = ctypes.cdll.LoadLibrary( 'libXss.so')
    xss.XScreenSaverAllocInfo.restype = ctypes.POINTER(XScreenSaverInfo)
    xss_info = xss.XScreenSaverAllocInfo()
    xss.XScreenSaverQueryInfo( dpy, root, xss_info)
    return xss_info.contents.idle/1000.

def check_idle():
    if get_idle_time() > config['idle-time']:
        logger.debug("Exceeded idle time.")
    return True

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

def parse_timerange(timerange, last_paid=None):
    timerange = timerange.split('-')
    if len(timerange) == 1:
        timerange.append('now')
    logger.debug(timerange)
    timestamp_range = []
    for item in timerange:
        if item.lower() == 'now':
            timestamp_range.append(datetime.datetime.now())
        elif item.lower() == 'today':
            timestamp_range.append(datetime.datetime.combine(datetime.date.today(), datetime.time.min))
        elif item.lower() in ('lastpaid', 'last paid', 'last_paid'):
            timestamp_range.append(last_paid)
        elif re.match(r'(\d+[wdhm])+', item):
            quanta = filter(len, re.split(r'(\d+[wdhm])', item))
            quanta = {q[-1]: int(q[:-1]) for q in quanta}
            for k in ('w', 'd', 'h', 'm'):
                if k not in quanta:
                    quanta[k] = 0
            logger.debug(quanta)
            quanta['d'] = quanta['w']*7 + quanta['d']
            quanta['s'] = quanta['h']*60*60 + quanta['m']*60
            logger.debug(quanta)
            delta = datetime.timedelta(days=quanta['d'], seconds=quanta['s'])
            timestamp_range.append(datetime.datetime.now() - delta)
        else:
            try:
                timestamp_range.append(datetime.datetime.fromtimestamp(int(item)))
                continue
            except ValueError:
                pass
            try:
                timestamp_range.append(dateparser.parse(item))
            except ValueError:
                raise ValueError, "unknown date format"
    timestamp_range.sort()
    logger.debug(timestamp_range)
    #print timestamp_range
    return timestamp_range
        

def notify(title, message):
    n = Notify.Notification.new(title, message)
    #n.set_timeout(Notify.EXPIRES_DEFAULT)
    n.show()
    time.sleep(delay)
    n.close()

def start_log():
    f = open(config['logfile'], 'a')
    print >>f, "-- Starting log at %s --" % (get_current_timestamp())
    logger.debug("-- Starting log at %s --", get_current_timestamp())
    f.close()
    
def write_note(note):
    f = open(config['logfile'], 'a')
    print >>f, "%s -- [Note] %s" % (get_current_timestamp(), note)
    f.close()

def write_manual_adjustment(td):
    f = open(config['logfile'], 'a')
    print >>f, "%s -- [Manual Adjustment] %d" % (get_current_timestamp(), td.seconds)
    f.close()

def monitor(command, window_name):
    f = open(config['logfile'], 'a')
    print >>f, "%s -- %s ::: %s" % (get_current_timestamp(), command, window_name)
    logger.debug("%s -- %s ::: %s" % (get_current_timestamp(), command, window_name))
    f.close()

def close_log():
    global args
    f = open(config['logfile'], 'a')
    print >>f, "-- Closing log at %s --" % (get_current_timestamp())
    logger.debug("-- Closing log at %s --", get_current_timestamp())
    f.close()

def stop_monitoring(signum, frame):
    if signum in (signal.SIGTERM, signal.SIGINT) and args.verbose >= 2:
        logger.debug("Got %s." % ("SIGTERM" if signum==signal.SIGTERM else "SIGINT"))
    if signum in (signal.SIGTERM, signal.SIGINT):
        close_log()
        if release_lock(config['lockfile']):
            sys.exit(0)
        else:
            print >>sys.stderr, "Failed to release lock."
            sys.exit(1)

#############
# Commands

def command_start(args):
    if get_lock(config['lockfile']):
        logger.error("Timecard is already locked.")
        sys.exit(1)
    
    if args.verbose >= 2:
        # Debug mode: -vv
        if not lock_timecard(os.getpid(), config['lockfile']):
            logger.error("Unable to create lock file.")
            sys.exit(1)
        print "Clocked in at %s." % (datetime.datetime.now().strftime("%H:%M:%S, %a %b %d, %Y"))
        # Don't fork a new process for the child.
        run_child(args)
    else:
        pid = os.fork()
        if pid > 0:
            logger.info("Parent reports child pid=%d", pid)
            if not lock_timecard(pid, config['lockfile']):
                os.kill(pid, signal.SIGTERM)
                logger.error("Unable to create lock file.")
                sys.exit(1)
            print "Clocked in at %s." % (get_current_timestamp())
            sys.exit(0)
        else:
            run_child(args)

def run_child(args):
    # Child process - this will do the monitoring
    # Give the parent a chance to do last checks and kill us if needed.
    global logger
    logger.debug("Child started.")
    time.sleep(2)
    start_log()
    
    if args.note:
        write_note(args.note)
    
    signal.signal(signal.SIGTERM, stop_monitoring)
    if args.verbose >= 2:
        signal.signal(signal.SIGINT, stop_monitoring)
    
    # Set up events
    screen = Wnck.Screen.get_default()
    screen.connect("active-window-changed", focus_changed)
    screen.connect("application-closed", application_closed)
    if config['screenshots']:
            GLib.timeout_add_seconds(config['screenshots']['interval'], screenshot.take_screenshot, os.path.join(config['screenshots']['directory'], get_current_timestamp(True)), target=config['screenshots']['type'])
    GLib.timeout_add_seconds(10, check_idle)
    
    logger.debug("Going into main loop.")
    Gtk.main()

def command_stop(args):
    pid = get_lock(config['lockfile'])
    if not pid:
        logger.error("Could not get a valid PID from lock file.")
        sys.exit(1)
    if args.note:
        write_note(args.note)
    logger.debug("Killing process %d.", pid)
    os.kill(pid, signal.SIGTERM)
    print "Clocked out at %s." % (datetime.datetime.now().strftime("%H:%M:%S, %a %b %d, %Y"))

def command_note(args):
    write_note(args.note)
    print "Note saved at %s." % (get_current_timestamp())

def get_spans(lines):
    spans = []
    adjustments = []
    closed = True
    last_paid = datetime.datetime(1900, 1, 1)
    for line in lines:
        logger.debug(line)
        #if " -- " not in line:
        #    logger.debug('" -- " not found in "%s"' % (line))
        #    continue
        timestamp = dateparser.parse(line[line.find(':')-2:line.find(" --")])
        if "[Note]" in line and "got paid" in line.lower() and timestamp > last_paid:
            last_paid = timestamp
        elif "[Manual Adjustment]" in line:
            seconds = int(line[line.find(']')+2:].strip())
            adjustments.append((timestamp, seconds))
            logger.debug("Added %d to adjustments." % seconds)
        if closed and not line.startswith("-- Starting"):
            continue
        elif line.startswith("-- Starting"):
            logger.debug("Starting at %s" % (timestamp))
            spans.append([(timestamp, line)])
            closed = False
        elif line.startswith("-- Closing"):
            spans[-1].append((timestamp, line))
            closed = True
        else:
            spans[-1].append((timestamp, line[line.find(" -- ")+4:line.find(" ::: ")], line[line.find(" ::: "):]))
    return (spans, adjustments, last_paid)

def command_summarize(args):
    total_log = map(lambda l: l.strip(), open(config['logfile'], 'r').readlines())
    logger.debug(len(total_log))
    spans, adjustments, last_paid = get_spans(total_log)
    logger.debug(len(spans))
    if args.timerange:
        start_time, end_time = parse_timerange(args.timerange, last_paid)
        logger.debug("start_time: '%s', end_time: '%s'", start_time, end_time)
        spans = filter(lambda s: s[0][0]>start_time, spans)
        adjustments = filter(lambda a: a[0]>start_time, adjustments)
    total_hours = 0.0
    for span in spans:
        st_time = span[0][0]
        e_time = span[-1][0]
        if args.timerange:
            if e_time < start_time or st_time > end_time:
                logger.debug("Skipping: %s, %s, %s, %s", start_time, st_time, end_time, e_time)
                continue
            elif start_time > st_time and end_time < e_time:
                # Span is completely within timerange
                delta = end_time - start_time
            elif st_time < start_time:
                logger.debug("%s, %s, %s, %s", start_time, st_time, end_time, e_time)
                delta = e_time - start_time
            elif e_time > end_time:
                logger.debug("%s, %s, %s, %s", start_time, st_time, end_time, e_time)
                delta = end_time - st_time
            else:
                delta = e_time - st_time
        else:
            delta = e_time - st_time
        hours = delta.total_seconds()/3600.
        total_hours += hours
        print "Worked from %s to %s\n  -- Total %.3f hours." % (format_timestamp(st_time), format_timestamp(e_time), hours)
    if adjustments:
        adj_hours = sum(a[1] for a in adjustments)/60./60.
        print "Manual adjustments totaling %.2f hours." % adj_hours
        total_hours += adj_hours
    if args.timerange:
        print "\nTotal time worked from %s to %s:\n    %.3f hours" % (format_timestamp(start_time, True), format_timestamp(end_time, True), total_hours)
    else:
        print "\nTotal time worked from %s to %s:\n    %.3f hours" % (format_timestamp(spans[0][0][0], True), format_timestamp(spans[-1][-1][0], True), total_hours)

def command_analyze(args):
    raw_log = map(lambda l: l.strip(), open(config['logfile'], 'r').readlines())
    raw_log = filter(lambda l: len(l)>0, raw_log)
    last_paid = datetime.datetime(datetime.MINYEAR, 1, 1)
    parsed_log = []
    for line in raw_log:
        if line.startswith("-- Starting log"):
            parsed_log.append([])
            segment = parsed_log[-1]
            continue
        elif line.startswith("-- Closing log"):
            segment.append((dateparser.parse(line[len("-- Closing log at "):-3]), "END", ""))
            continue
        
        timestamp, info = line.split(' -- ', 1)
        if info.startswith("[Note]"):
            if "got paid" in line.lower() and timestamp > last_paid:
                last_paid = timestamp
            continue
        command, window_name = info.split(' ::: ', 1)
        segment.append((dateparser.parse(timestamp), command, window_name))
    command_histogram = {}
    window_histogram = {}
    for segment in parsed_log:
        for i in xrange(len(segment)-1):
            entry = segment[i]
            next_entry = segment[i+1]
            if entry[1] == "END":
                break
            cmd_time_accumulated = command_histogram.get(entry[1], datetime.timedelta(0))
            cmd_time_accumulated += next_entry[0] - entry[0]
            command_histogram[entry[1]] = cmd_time_accumulated
            win_time_accumulated = window_histogram.get(entry[2], datetime.timedelta(0))
            win_time_accumulated += next_entry[0] - entry[0]
            window_histogram[entry[2]] = win_time_accumulated
    print "Time spent per command:"
    for command, time_len in sorted(command_histogram.items(), cmp=lambda e1, e2: cmp(e1[1], e2[1]), reverse=True):
        print "%s\t%s" % (time_len, command)
    print ""
    print "Time spent per window name:"
    for win_name, time_len in sorted(window_histogram.items(), cmp=lambda e1, e2: cmp(e1[1], e2[1]), reverse=True):
        print "%s\t%s" % (time_len, win_name)

def command_manual(args):
    timerange = parse_timerange(args.time)
    td = timerange[1]-timerange[0]
    write_manual_adjustment(td)

def command_test(args):
    global config
    print args
    print config
    screenshot.take_screenshot("tests/test.png", target=screenshot.ENTIRE_DESKTOP)



### Main script ###

if __name__ == "__main__":
    # If called from cron, find first display.
    if not 'DISPLAY' in os.environ:
        os.environ['DISPLAY'] = find_display()
    
    load_config()

    argparser = argparse.ArgumentParser(description="Record or analyze time usage.")
    argparser.add_argument('-v', '--verbose', action='count', default=0, help="Display debug messages. -vv will disable forking.")
    argparser.add_argument('-f', '--file', metavar='path', dest='logfile', default=config['logfile'], help='Time log file.')
    #argparser.add_argument('-c', '--config-file', default=None, metavar='path', dest='configfile', help="Use the specified config file location.")
    #argparser.add_argument('--config', nargs=2, action='append', metavar=('key', 'value'), help="Set config file options directly and persistently.")
    argparser.add_argument('--save-config', action='store_true', help="Save arguments to this invocation as options in the config file.")
    argparser.add_argument('-V', '--version', action='version', version='0.1a')
    subparsers = argparser.add_subparsers(help="Help for commands.")
    
    parser_start = subparsers.add_parser('start', help='Clock in - begin recording into the timecard.')
    parser_start.add_argument('-s', '--screenshots', metavar='dir', nargs='?', default=None if config['screenshots'] == False or config['screenshots']['interval'] == 0 else config['screenshots']['directory'], const=config['screenshots'] and config['screenshots']['directory'], help='Take screenshots with every log entry. Optional: directory to store screenshots.')
    parser_start.add_argument('--screenshot-type', choices=screenshot_types.keys(), default='active-monitor' if not config['screenshots'] else config['screenshots']['type'], help='Area to restrict screenshots to.')
    parser_start.add_argument('--screenshot-interval', metavar='interval', type=int, default=300 if not config['screenshots'] else config['screenshots']['interval'], help='Seconds between screenshots.')
    parser_start.add_argument('-N', '--notify', metavar='warning', nargs='?', type=int, default=config['screenshots'] and config['screenshots']['notify'], const=default_config['screenshots'] and default_config['screenshots']['notify'], help='Notify [N] seconds before a screenshot.')
    parser_start.add_argument('-i', '--idle-time', metavar='seconds', dest='idletime', type=int, default=config['idle-time'], help='Time in seconds before user becomes idle.')
    parser_start.add_argument('-n', '--note', metavar='note', help='Add a note to this action.')
    parser_start.set_defaults(func=command_start)
    
    parser_stop = subparsers.add_parser('stop', help='Clock out - stop recording and close the timecard.')
    parser_stop.add_argument('-n', '--note', metavar='note', help='Add a note to this action.')
    parser_stop.set_defaults(func=command_stop)
    
    parser_note = subparsers.add_parser('note', help='Add a note to an active timecard.')
    parser_note.add_argument('note', nargs='?', help='Note to be recorded.')
    parser_note.set_defaults(func=command_note)
    
    parser_summarize = subparsers.add_parser('summarize', help='Summarize the time usage in a timecard, optionally over a time range.')
    parser_summarize.add_argument('timerange', nargs='?', help='Time range to summarize. Accepts absolute dates, relative dates in *w*d*h (weeks/days/hours) format, and ranges of either or both.')
    parser_summarize.set_defaults(func=command_summarize)
    
    parser_analyze = subparsers.add_parser('analyze', help='More detailed analysis of time use.')
    parser_analyze.add_argument('timerange', nargs='?', help='Time range to analyze. Accepts absolute dates, relative dates in 1w2d3h (weeks/days/hours) format, and ranges of either or both.')
    parser_analyze.set_defaults(func=command_analyze)
    
    parser_manual = subparsers.add_parser('manual', help='Add or subtract time manually.')
    parser_manual.add_argument('time', nargs='?', help='Amount of time to add, in 1w1d1h1m format.')
    parser_manual.set_defaults(func=command_manual)
    
    parser_test = subparsers.add_parser('test', help='Internal test.')
    parser_test.set_defaults(func=command_test)
    
    args = argparser.parse_args()
    
    debuglevel = {
        0: logging.ERROR,
        1: logging.INFO,
        2: logging.DEBUG
    }
    args.verbose = min(args.verbose, max(debuglevel.keys()))
    
    logger = logging.getLogger(__name__)
    logger.setLevel(debuglevel[args.verbose])
    ch = logging.StreamHandler()
    ch.setLevel(debuglevel[args.verbose])
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    if 'screenshots' in args:
        screenshot.logger = logger
    
    process_args(args)
    
    args.func(args)
    
