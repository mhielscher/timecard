Timecard
=======

Timecard is a script that monitors your computer usage (only while you're clocked in, of course). Every time you switch windows, the title and process of the new window is noted in a plaintext log. Optionally, a screenshot may be taken of the active window, active monitor, the monitor the cursor is in (whether the focused window is in it or not), or the entire desktop at regular intervals.

You can add notes to the log file as well - at clock-in, at clock-out, or at any time in between. This is useful for noting what you're working on, when the window names aren't self-explanatory.

Currently, the only reporting feature is a simple summarization. Timecard will print all of the timespans in which you worked, each followed by the length of the timespan, with a total at the end. You can specify, in a single command-line argument (enclosed in quotes if necessary) a time range to summarize. Timecard will accept most absolute date formats, plus "now" and relative negative times in weeks/days/hours format, e.g. 1w2d6h. A dash between times will indicate the range; if only one time is specified, a range up to and including "now" will be assumed. A special keyword, "lastpaid" indicates the time you last submitted your hours.

An analyze command is planned for the future. It will generate an HTML file showing spans in work in various formats, with screenshot thumbnails (if available), and an analysis of time spent in each window.

