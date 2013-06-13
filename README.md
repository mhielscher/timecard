Timecard
=======

Timecard is a script that monitors your computer usage (only while you're clocked in, of course). Every 5 minutes, or at an interval you specify, the time, date, and name of the active window are recorded in a plaintext log. Optionally, a screenshot may be taken of the active window, active monitor, the monitor the cursor is in (whether the focused window is in it or not), or the entire desktop.

You can add notes to the log file as well - at clockin, at clockout, or at any time in between. This is useful for noting what you're working on, when the window names aren't self-explanatory.

Currently, the only reporting feature is a simple summarization. Timecard will print all of the timespans in which you worked, each followed by the length of the timespan, with a total at the end. You can specify, in a single command-line argument (enclosed in quotes if necessary) a time range to summarize. Timecard will accept most absolute date formats, plus "now" and relative negative times in weeks/days/hours format, e.g. 1w2d6h. A dash between times will indicate the range; if only one time is specified, a range up to and including "now" will be assumed.

An analyze command is planned for the future. It will generate an HTML file showing spans in work in various formats, with screenshot thumbnails (if available).

