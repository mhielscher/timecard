import os
import logging
from gi.repository import Gdk, GdkPixbuf

ARBITRARY_AREA = 0 # Specified area
ACTIVE_WINDOW = 1 # Focused/top window only
ACTIVE_MONITOR = 2 # Monitor containing the active window
CURSOR_MONITOR = 3 # Monitor containing the cursor
ENTIRE_DESKTOP = 4 # Everything

logger = logging.getLogger(__name__)

def get_active_window(root=None):
    """Returns the active (focused, top) window, or None."""
    root = root or Gdk.Screen.get_default()
    active = root.get_active_window()
    if not active:
        return None
    return active

def get_active_monitor(root=None):
    """Returns the index of the active monitor, or -1 if undetermined."""
    root = root or Gdk.Screen.get_default()
    num_monitors = root.get_n_monitors()
    if (num_monitors == 1):
        return 0
    active = get_active_window()
    if active != None:
        return root.get_monitor_at_window(active)
    else:
        return -1

def take_screenshot(filepath, target=ACTIVE_MONITOR, fmt="png", scale=1.0, area=(0,0,0,0), fmt_options={}):
    """Take a screenshot of the desired target area."""
    logger.debug("Taking screenshot (target=%d)." % target)
    root = Gdk.Screen.get_default()
    root_win = root.get_root_window()
    active = get_active_window(root)
    if active == None and target in (ACTIVE_WINDOW, ACTIVE_MONITOR):
        # Fallback to everything
        target = ENTIRE_DESKTOP
    
    if target == ARBITRARY_AREA:
        x, y, w, h = area
    elif target == ACTIVE_WINDOW:
        rx, ry, w, h = active.get_geometry()
        w = w + rx*2
        h = h + rx+ry
        x, y = active.get_root_origin()
    elif target == ACTIVE_MONITOR:
        monitor = root.get_monitor_at_window(active)
        x, y, w, h = (root.get_monitor_geometry(monitor).x, root.get_monitor_geometry(monitor).y, root.get_monitor_geometry(monitor).width, root.get_monitor_geometry(monitor).height)
    elif target == CURSOR_MONITOR:
        cursor = root_win.get_pointer()
        monitor = root.get_monitor_at_point(*cursor[1:3])
        x, y, w, h = (root.get_monitor_geometry(monitor).x, root.get_monitor_geometry(monitor).y, root.get_monitor_geometry(monitor).width, root.get_monitor_geometry(monitor).height)
    elif target == ENTIRE_DESKTOP:
        x, y, w, h = root_win.get_geometry()
    
    logger.debug("Area = (x=%d, y=%d, w=%d, h=%d)" % (x, y, w, h))
    #pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h)
    pb = Gdk.pixbuf_get_from_window(root_win, x, y, w, h)
    pb = pb.scale_simple(int(w*scale), int(h*scale), GdkPixbuf.InterpType.BILINEAR)
    
    if fmt == "jpg":
        # "jpeg" required for pb.save format string
        if not (filepath.endswith('.jpg') or filepath.endswith('.jpeg')):
            filepath += '.jpg'
        fmt = "jpeg"
    else:
        if not filepath.endswith('.'+fmt):
            filepath += '.'+fmt
    if (pb != None):
        logger.debug("Saving screenshot to %s." % filepath)
        try:
            pb.savev(filepath, fmt, fmt_options.keys(), fmt_options.values())
        except Exception as e:
            logger.error("Failed to save screenshot to %s: %s." % (filepath, e))
            return False
        return True
    else:
        logger.error("Failed to save screenshot to %s." % filepath)
        return False


if __name__ == "__main__":
    # Tests
    from time import sleep
    
    logger.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    take_screenshot("tests/window", target=ACTIVE_WINDOW)
    take_screenshot("tests/all.9.png", target=ENTIRE_DESKTOP, fmt="png", fmt_options={"compression": "9"})
    take_screenshot("tests/all.1.png", target=ENTIRE_DESKTOP, fmt="png", fmt_options={"compression": "1"})
    take_screenshot("tests/monitor.hi", target=ACTIVE_MONITOR, fmt="jpg", fmt_options={"quality": "95"})
    take_screenshot("tests/monitor.lo.jpg", target=ACTIVE_MONITOR, fmt="jpeg", fmt_options={"quality": "60"})
    take_screenshot("tests/cursor", target=CURSOR_MONITOR, scale=0.75, fmt_options={"compression": "9"})
    take_screenshot("tests/cursor.jpg", target=CURSOR_MONITOR, scale=0.75, fmt="jpg", fmt_options={"quality": "90"})
    take_screenshot("tests/arbitrary.png", target=ARBITRARY_AREA, fmt="gif", area=(10,10,1280,1024))
    take_screenshot("tests/window.fail", target=ACTIVE_WINDOW, fmt="svg")
    logger.debug("Focus new window, move cursor to other monitor now please.")
    sleep(5)
    take_screenshot("tests/all.fail", target=ENTIRE_DESKTOP, fmt="raw")
    take_screenshot("tests/monitor.2.png", target=ACTIVE_MONITOR)
    take_screenshot("tests/cursor.2", target=CURSOR_MONITOR, fmt="jpg")
    
