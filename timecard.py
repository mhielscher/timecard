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
from dateutil import parser as dateparser

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

def parse_timerange(timerange):
	timerange = timerange.split('-')
	if len(timerange) == 1:
		timerange.append('now')
	timestamp_range = []
	for item in timerange:
		if item == 'now':
			timestamp_range.append(datetime.datetime.now())
		elif re.match(r'(\d+[wdh])+', item):
			quanta = filter(len, re.split(r'(\d+[wdh])', item))
			quanta = {q[-1]: int(q[:-1]) for q in quanta}
			for k in ('w', 'd', 'h'):
				if k not in quanta:
					quanta[k] = 0
			quanta['d'] = quanta['w']*7 + quanta['d']
			quanta['s'] = quanta['h']*24*60*60
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
	#print timestamp_range
	return timestamp_range
		

def start_log():
    global args
    f = open(args.file, 'a')
    print >>f, "-- Starting log at %s --" % (get_current_timestamp())
    logger.debug("-- Starting log at %s --", get_current_timestamp())
    f.close()
    
def write_note(note):
    global args
    f = open(args.file, 'a')
    print >>f, "%s: [Note] %s" % (get_current_timestamp(), note)
    f.close()

def monitor():
    global args
    f = open(args.file, 'a')
    print >>f, "%s: %s" % (get_current_timestamp(), get_active_window())
    logger.debug("%s: %s", get_current_timestamp(), get_active_window())
    f.close()

def close_log():
    global args
    f = open(args.file, 'a')
    print >>f, "-- Closing log at %s --" % (get_current_timestamp())
    logger.debug("-- Closing log at %s --", get_current_timestamp())
    f.close()

def stop_monitoring(signum, frame):
    if signum in (signal.SIGTERM, signal.SIGINT) and args.verbose >= 2:
        logger.debug("Got %s." % ("SIGTERM" if signum==signal.SIGTERM else "SIGINT"))
    if signum in (signal.SIGTERM, signal.SIGINT):
        close_log()
        if release_lock(args.lockfile):
            sys.exit(0)
        else:
            print >>sys.stderr, "Failed to release lock."
            sys.exit(1)





if __name__ == "__main__":
    # If called from cron, find first display.
    if not 'DISPLAY' in os.environ:
	    os.environ['DISPLAY'] = find_display()

    commands = ["start", "stop", "note", "list", "analyze", "test"]

    argparser = argparse.ArgumentParser(description="Record or analyze time usage.")
    argparser.add_argument('-v', '--verbose', action='count', default=0, help="Display debug messages. -vv will disable forking.")
    argparser.add_argument('-f', '--file', metavar='file', default='timecard.log', help='Time log file.')
    argparser.add_argument('-l', '--lockfile', metavar='lockfile', default='timecard.lock', help='Lock file name.')
    argparser.add_argument('-s', '--screenshots', metavar='dir', nargs='?', default=None, const='screenshots', help='Take screenshots with every log entry. Optional: directory to store screenshots (default is screenshots/).')
    argparser.add_argument('-i', '--interval', metavar='interval', type=int, default=300, help='Seconds between monitor reports.')
    argparser.add_argument('command', choices=commands)
    argparser.add_argument('-n', '--note', metavar='note', help='Add a note to this action.')
    argparser.add_argument('timerange', nargs='?', help='Time range for list command.')
    argparser.add_argument('note_arg', nargs='?', help='Note to be recorded with note command.')
    args = argparser.parse_args()

    debuglevel = {
        0: logging.ERROR,
        1: logging.INFO,
        2: logging.DEBUG
    }

    logger = logging.getLogger(__name__)
    logger.setLevel(debuglevel[args.verbose])
    ch = logging.StreamHandler()
    ch.setLevel(debuglevel[args.verbose])
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    logger.debug(args)
    
    if args.screenshots:
        import screenshot
        screenshot.logger = logger

    if args.command == 'start':
        
        if get_lock(args.lockfile):
            logger.error("Timecard is already locked.")
            sys.exit(1)
        
        if args.verbose >= 2:
            if not lock_timecard(os.getpid(), args.lockfile):
                logger.error("Unable to create lock file.")
                sys.exit(1)
            print "Clocked in at %s." % (datetime.datetime.now().strftime("%H:%M:%S, %a %b %d, %Y"))
        else:
            pid = os.fork()
            if pid > 0:
                logger.debug("Parent reports child pid=%d", pid)
                if not lock_timecard(pid, args.lockfile):
                    os.kill(pid, signal.SIGTERM)
                    logger.error("Unable to create lock file.")
                    sys.exit(1)
                print "Clocked in at %s." % (datetime.datetime.now().strftime("%H:%M:%S, %a %b %d, %Y"))
                sys.exit(0)
        
        # Child process - this will do the monitoring
        # Give the parent a chance to do last checks and kill us if needed.
        logger.debug("Child started.")
        time.sleep(2)
        start_log()
        if args.note:
            write_note(args.note)
        time.sleep(5)
        signal.signal(signal.SIGTERM, stop_monitoring)
        if args.verbose >= 2:
            signal.signal(signal.SIGINT, stop_monitoring)
        while True:
            monitor()
            if args.screenshots:
                screenshot.take_screenshot(os.path.join(args.screenshots, get_current_timestamp(True)))
            logger.debug("Sleeping %d seconds.", args.interval)
            time.sleep(args.interval)

    elif args.command == 'note':
        write_note(args.timerange) # Because only one optional positional arg works
        print "Note saved at %s." % (get_current_timestamp())

    elif args.command == 'stop':
        pid = get_lock(args.lockfile)
        if not pid:
            logger.error("Could not get a valid PID from lock file.")
            sys.exit(1)
        if args.note:
        	write_note(args.note)
        logger.debug("Killing process %d.", pid)
        os.kill(pid, signal.SIGTERM)
        print "Clocked out at %s." % (datetime.datetime.now().strftime("%H:%M:%S, %a %b %d, %Y"))

    elif args.command == 'list':
        total_log = map(lambda l: l.strip(), open(args.file, 'r').readlines())
        spans = []
        closed = True
        for line in total_log:
            if closed and not line.startswith("-- Starting"):
                continue
            elif line.startswith("-- Starting"):
                timestamp = dateparser.parse(line[len("-- Starting log at "):-3])
                spans.append([(timestamp, line)])
                closed = False
            elif line.startswith("-- Closing"):
                timestamp = dateparser.parse(line[len("-- Closing log at "):-3])
                spans[-1].append((timestamp, line))
                closed = True
            else:
                timestamp = dateparser.parse(':'.join(line.split(':')[:3]))
                spans[-1].append((timestamp, ':'.join(line.split(':')[3:])))
        if args.timerange:
            start_time, end_time = parse_timerange(args.timerange)
            spans = filter(lambda s: s[0][0]>start_time, spans)
        total_hours = 0.0
        for span in spans:
            st_time = span[0][0]
            e_time = span[-1][0]
            delta = e_time - st_time
            hours = delta.total_seconds()/3600
            total_hours += hours
            print "Worked from %s to %s\n  -- Total %.3f hours." % (format_timestamp(st_time), format_timestamp(e_time), hours)
        if args.timerange:
            print "\nTotal time worked from %s to %s:\n    %.3f hours" % (format_timestamp(start_time, True), format_timestamp(end_time, True), total_hours)
        else:
            print "\nTotal time worked from %s to %s:\n    %.3f hours" % (format_timestamp(spans[0][0][0], True), format_timestamp(spans[-1][-1][0], True), total_hours)
                

    elif args.command == 'test':
        print args
        import screenshot
        take_screenshot("tests/test.png", target=screenshot.ENTIRE_DESKTOP)


