#!/usr/bin/env python3
# sparkTerminal - a separate terminal program; it never changes GNOME Terminal or ~/.bashrc
# Steps 121-124: per-tab settings (prompt, theme, text colour, font size) with live preview,
# program defaults for new tabs (gear button), saved only in sparkTerminal's own config file,
# close button on every tab (asks first when a program is still running in it), window icon,
# copy and paste (Ctrl+Shift+C / Ctrl+Shift+V and a right-click menu inside the terminal)
# directories shown bold and italic by ls and other LS_COLORS tools (only inside sparkTerminal)
# MIT License, copyright Shrinivas Kodati (see LICENSE in the repo root)

import configparser  # read and write the program's own settings file
import getpass  # user name for the live preview
import os  # folders, file permissions and the user's environment
import shlex  # quote a requested command safely for bash
import shutil  # delete the program's private temporary folder at the end
import signal  # SIGHUP: the signal a terminal sends to its shell when the tab is closed
import socket  # host name for the live preview
import sys  # exit with a status code at the end
import time  # current date and time for the live preview

import gi  # GObject introspection: lets Python use the GTK and VTE libraries

gi.require_version("Gdk", "3.0")  # pin Gdk to 3.0 (matches GTK 3); without this PyGObject loads Gdk 4.0 first and GTK 3 fails
gi.require_version("Gtk", "3.0")  # use GTK 3 (same toolkit as the ports widget)
gi.require_version("Pango", "1.0")  # font descriptions (family and size)
gi.require_version("Vte", "2.91")  # use VTE 2.91 (the terminal engine inside GNOME Terminal, 0.76 here)

from gi.repository import Gdk, Gio, GLib, Gtk, Pango, Vte  # Gio reads GNOME settings (it writes only the default terminal, when you press the button); the rest as named above

APP_TITLE = "sparkTerminal"  # window title shown in the title bar and the task bar
SHELL = "/bin/bash"  # the shell started in each tab (bash, as agreed)
CONFIG_FILE = os.path.join(GLib.get_user_config_dir(), "sparkTerminal", "settings.conf")  # ~/.config/sparkTerminal/settings.conf, only written on Apply
RUNTIME_DIR = os.path.join(GLib.get_user_runtime_dir(), f"sparkTerminal-{os.getpid()}")  # private temporary folder for this run, deleted at the end

PROMPT_STYLES = [  # (stored value, text shown in the settings box)
    ("dir", "Working directory only"),  # ~/sparkToolset$
    ("timestamp", "Date + time + directory"),  # [2026-11-10 19:57] ~/sparkToolset$
    ("datedaytime", "Date + day + time + directory"),  # [2026-11-10 Tue 19:57] ~/sparkToolset$
    ("date", "Date + directory"),  # [2026-11-10] ~/sparkToolset$
    ("dateday", "Date + day + directory"),  # [2026-11-10 Tue] ~/sparkToolset$
    ("time", "Time + directory"),  # [19:57] ~/sparkToolset$
    ("bare", "Prompt only ($)"),  # $
]  # end of the list above
PROMPT_TIME_FORMATS = {  # date/time part per style ("Tue" = short day)
    "timestamp": "%Y-%m-%d %H:%M",  # 2026-11-10 19:57
    "datedaytime": "%Y-%m-%d %a %H:%M",  # 2026-11-10 Tue 19:57
    "date": "%Y-%m-%d",  # 2026-11-10
    "dateday": "%Y-%m-%d %a",  # 2026-11-10 Tue
    "time": "%H:%M",  # 19:57
}  # end of the table above

THEMES = [("dark", "Dark"), ("light", "Light"), ("auto", "Auto (follows the GNOME light/dark setting)")]  # theme choices
BACKGROUNDS = {"dark": "#000000", "light": "#f6f5f4"}  # background colour per theme (soft off-white on the light theme)
TEXT_COLOURS = [("green", "Green"), ("white", "White (black on the light theme)"), ("amber", "Amber"), ("cyan", "Cyan")]  # text colour choices
TEXT_RGB = {  # text colour per theme; darker shades on the light theme so the text stays readable on white
    "dark": {"green": "#33cc33", "white": "#e6e6e6", "amber": "#ffb000", "cyan": "#00c8c8"},  # bright shades on black
    "light": {"green": "#1a7f1a", "white": "#202020", "amber": "#9a5b00", "cyan": "#007a7a"},  # dark shades on white
}  # end of the table above
PROMPT_COLOURS = [("auto", "Automatic (recommended)"), ("cyan", "Cyan"), ("yellow", "Yellow"), ("green", "Green"), ("magenta", "Magenta"), ("blue", "Blue"), ("white", "White (black on the light theme)")]  # prompt colour choices
PROMPT_RGB = {  # prompt colour per theme; contrast measured: 8.8:1 or better on black, 6.8:1 or better on the soft light background
    "dark": {"cyan": "#00e5ff", "yellow": "#ffe14d", "green": "#66ff66", "magenta": "#ff77ff", "blue": "#66aaff", "white": "#ffffff"},  # bright shades on black
    "light": {"cyan": "#005f6b", "yellow": "#6b5000", "green": "#0f5f0f", "magenta": "#a0189a", "blue": "#1556c4", "white": "#000000"},  # livelier magenta and blue (6.1:1 or better) on the soft light background
}  # end of the table above
AUTO_PROMPT = {  # what Automatic picks per text colour: a different colour family than the text, so prompt and output are easy to tell apart
    "dark": {"white": "cyan", "green": "yellow", "amber": "cyan", "cyan": "yellow"},  # on the dark theme
    "light": {"white": "blue", "green": "magenta", "amber": "blue", "cyan": "magenta"},  # on the light theme
}  # end of the table above
PALETTES = {  # the 16 standard terminal colours per theme (black, red, green, yellow, blue, magenta, cyan, white, then the bright versions); contrast measured: 4.6:1 or better on black, 4.7:1 or better on the soft light background
    "dark": ["#767676", "#ff6b6b", "#4ee04e", "#e6c200", "#6aa7ff", "#d87bff", "#34d6d6", "#d3d7cf", "#9a9a9a", "#ff8a8a", "#8ae234", "#fce94f", "#8fbcff", "#e6a0ff", "#6ae8e8", "#ffffff"],  # light shades on black (the default dark blue was only 2.2:1)
    "light": ["#000000", "#b3001b", "#1a7f1a", "#7a5800", "#0033cc", "#8b008b", "#006b7a", "#555555", "#444444", "#cc0000", "#237a00", "#8a5a00", "#0044ff", "#a000a0", "#007a85", "#1a1a1a"],  # dark shades on white
}  # end of the table above
SCROLLBACK_LINES = 100000  # lines of history per tab (also the most output rows one command can keep for copying)
MAX_COPY_BYTES = 1000000  # a command's result larger than this (1 MB) is cut at a line end when copied to the clipboard
FONT_SIZES = ["medium", "large"]  # only two sizes, as agreed (large = medium x 1.25)

BUILT_IN_DEFAULTS = {  # defaults agreed with the user; used when no settings file exists or Reset is pressed
    "prompt_style": "timestamp",  # date + time + directory (like the current GNOME Terminal prompt)
    "system_name": "yes",  # always prefix with user@system
    "theme": "dark",  # dark theme
    "text_colour": "green",  # green text
    "prompt_colour": "auto",  # automatic: bold colour chosen from the theme and the text colour
    "font_size": "medium",  # system monospace size
    "copy_result": "no",  # do not copy command results to the clipboard unless switched on
    "copy_start_time": "no",  # no "Started:" line before a copied result unless switched on
    "copy_end_time": "no",  # no "Finished:" line after a copied result unless switched on
    "half_screen": "no",  # open the window at its normal size unless switched on
    "half_side": "left",  # which half of the screen is used when the half-screen switch is on
    "run_commands": "no",  # do not run commands that other programs ask for, unless switched on
}  # end of the table above


def system_font():  # the GNOME monospace font, read only (e.g. "Monospace 12")
    try:  # GNOME settings may be missing on other desktops
        name = Gio.Settings.new("org.gnome.desktop.interface").get_string("monospace-font-name")  # read the system monospace font
    except Exception:  # schema not installed
        name = "Monospace 12"  # safe fallback
    desc = Pango.FontDescription.from_string(name)  # turn the text into a font description
    if desc.get_size() == 0:  # no size given in the setting
        desc.set_size(12 * Pango.SCALE)  # use 12 points
    return desc  # family and size of the system font


def font_points(size_name):  # size in points for "medium" or "large"
    medium = system_font().get_size() / Pango.SCALE  # system size in points (12 here)
    return medium * 1.25 if size_name == "large" else medium  # large is 25% bigger (15 here)


def gnome_prefers_dark():  # read (never change) the GNOME light/dark setting for the Auto theme
    try:  # the key does not exist on older or other desktops
        return Gio.Settings.new("org.gnome.desktop.interface").get_string("color-scheme") == "prefer-dark"  # True when GNOME is dark
    except Exception:  # setting not available
        return True  # treat as dark (the agreed default theme)


def effective_theme(settings):  # "dark" or "light" after resolving Auto
    if settings["theme"] == "auto":  # Auto follows GNOME at the moment it is applied
        return "dark" if gnome_prefers_dark() else "light"  # pick from the GNOME setting
    return settings["theme"]  # Dark or Light as chosen


def prompt_colour_name(settings):  # name of the prompt colour after resolving Automatic
    name = settings["prompt_colour"]  # chosen colour or "auto"
    if name == "auto":  # Automatic depends on the theme and the text colour
        return AUTO_PROMPT[effective_theme(settings)][settings["text_colour"]]  # contrasting colour family
    return name  # colour chosen by the user


def prompt_rgb(settings):  # the prompt colour as "r;g;b" numbers for a terminal colour code
    hexcolour = PROMPT_RGB[effective_theme(settings)][prompt_colour_name(settings)]  # e.g. "#00e5ff"
    return ";".join(str(int(hexcolour[i:i + 2], 16)) for i in (1, 3, 5))  # e.g. "0;229;255"


def build_ps1(settings):  # bash prompt text (PS1) for the chosen style
    style = settings["prompt_style"]  # chosen prompt style
    ps1 = ""  # start empty
    if style in PROMPT_TIME_FORMATS:  # styles that show a date or time
        ps1 += "[\\D{" + PROMPT_TIME_FORMATS[style] + "}] "  # bash's \D{format} shows the time when the prompt is drawn
    if settings["system_name"] == "yes":  # system-name switch on
        ps1 += "\\u@\\h"  # user@host, e.g. alice@myhost
    if style != "bare":  # every style except "prompt only" shows the folder
        ps1 += (":" if settings["system_name"] == "yes" else "") + "\\w"  # current folder, ~ for home
    start = "\\[\\e[1;38;2;" + prompt_rgb(settings) + "m\\]"  # bold plus exact colour; \[ and \] tell bash these characters take no room on the line
    end = "\\[\\e[0m\\]"  # back to the normal text colour for what you type
    return start + ps1 + "\\$" + end + " "  # coloured prompt ($ for a normal user, # for root), colour reset, then a space


def sample_prompt(settings):  # the same prompt as plain text, for the live preview
    style = settings["prompt_style"]  # chosen prompt style
    text = ""  # start empty
    if style in PROMPT_TIME_FORMATS:  # styles that show a date or time
        text += "[" + time.strftime(PROMPT_TIME_FORMATS[style]) + "] "  # real current date or time
    if settings["system_name"] == "yes":  # system-name switch on
        text += getpass.getuser() + "@" + socket.gethostname().split(".")[0]  # real user and short host name (like \u@\h)
    if style != "bare":  # every style except "prompt only" shows the folder
        text += (":" if settings["system_name"] == "yes" else "") + "~/sparkToolset"  # example folder
    return "\x1b[1;38;2;" + prompt_rgb(settings) + "m" + text + "$\x1b[0m ls"  # bold coloured prompt, colour reset, then the example command in the text colour


TIME_STAMP_FORMAT = "%Y-%m-%d %H:%M:%S"  # local date and time with seconds, e.g. 2026-11-14 18:21:05


def copy_text_with_times(text, started, finished, add_start, add_end):  # the copied result with an optional "Started:" first line and "Finished:" last line
    parts = []  # the lines of the final text, joined at the end
    if add_start and started is not None:  # start time wanted and known
        parts.append("Started: " + time.strftime(TIME_STAMP_FORMAT, time.localtime(started)))  # first line
    parts.append(text)  # the command's result itself
    if add_end and finished is not None:  # end time wanted and known
        parts.append("Finished: " + time.strftime(TIME_STAMP_FORMAT, time.localtime(finished)))  # last line
    return "\n".join(parts)  # one line break between the parts


def load_defaults():  # program defaults from the settings file, checked against the allowed values
    values = dict(BUILT_IN_DEFAULTS)  # start from the agreed defaults
    parser = configparser.ConfigParser()  # reader for the simple key = value file
    parser.read(CONFIG_FILE)  # a missing file is simply ignored
    if parser.has_section("defaults"):  # the file has our section
        allowed = {  # values that are accepted per key
            "prompt_style": [v for v, _ in PROMPT_STYLES],  # the six styles
            "system_name": ["yes", "no"],  # on or off
            "theme": [v for v, _ in THEMES],  # dark, light, auto
            "text_colour": [v for v, _ in TEXT_COLOURS],  # four colours
            "prompt_colour": [v for v, _ in PROMPT_COLOURS],  # automatic or one of six colours
            "font_size": FONT_SIZES,  # medium, large
            "copy_result": ["yes", "no"],  # on or off
            "copy_start_time": ["yes", "no"],  # on or off
            "copy_end_time": ["yes", "no"],  # on or off
            "half_screen": ["yes", "no"],  # on or off
            "half_side": ["left", "right"],  # left or right half of the screen
            "run_commands": ["yes", "no"],  # on or off
        }  # end of the table above
        for key, options in allowed.items():  # check every key
            value = parser.get("defaults", key, fallback=values[key])  # value from the file, or the default
            if value in options:  # only accept known values
                values[key] = value  # use the value from the file
    return values  # complete, valid settings


def save_defaults(values):  # write the program defaults to sparkTerminal's own file (nothing else is touched)
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)  # create ~/.config/sparkTerminal if needed
    parser = configparser.ConfigParser()  # writer for the key = value file
    parser["defaults"] = values  # one section with all settings
    with open(CONFIG_FILE, "w", encoding="utf-8") as handle:  # overwrite the file
        parser.write(handle)  # save it


TERMINAL_SCHEMA = "org.gnome.desktop.default-applications.terminal"  # GNOME setting (per user) that names the default terminal command
TERMINAL_KEY = "exec"  # the key inside that setting
PREVIOUS_FILE = os.path.join(GLib.get_user_config_dir(), "sparkTerminal", "previousDefaultTerminal.conf")  # sparkTerminal's own note of the value that was there before


def terminal_setting():  # the GNOME setting object, or None when this desktop does not have it
    source = Gio.SettingsSchemaSource.get_default()  # list of the installed settings schemas
    if source is None or source.lookup(TERMINAL_SCHEMA, True) is None:  # look first: opening a missing schema would crash the program
        return None  # not available here
    return Gio.Settings.new(TERMINAL_SCHEMA)  # the setting itself


def own_command():  # full path of this program: the value that makes it the default terminal
    return os.path.realpath(__file__)  # absolute path, symbolic links resolved


def command_problem(command):  # empty text when the command can be used as default terminal, otherwise the reason
    if any(ch.isspace() or ch in "'\"\\$" for ch in command):  # spaces and quote characters would break the command line GNOME builds
        return "the program path contains spaces or special characters"  # reason shown to the user
    if not os.access(command, os.X_OK):  # GNOME starts the file directly, so it must be executable
        return "the program file is not executable"  # reason shown to the user
    return ""  # usable


def previous_terminal():  # the value saved before "Set sparkTerminal as default", or None when nothing is saved
    parser = configparser.ConfigParser(interpolation=None)  # reader for sparkTerminal's own note (no % handling)
    parser.read(PREVIOUS_FILE)  # a missing file is simply ignored
    return parser.get("previous", "exec", fallback=None)  # the saved command, or None


def make_default_terminal():  # makes sparkTerminal the user's default terminal; returns a short message for the user
    setting = terminal_setting()  # the GNOME setting
    if setting is None:  # no such setting on this desktop
        return "This desktop has no default terminal setting."  # nothing is changed
    ours = own_command()  # this program
    problem = command_problem(ours)  # can it be used?
    if problem:  # not usable
        return "Not changed: " + problem + "."  # nothing is changed
    current = setting.get_string(TERMINAL_KEY)  # the value that is set now
    if current == ours:  # nothing to do
        return "sparkTerminal is already the default terminal."  # nothing is changed
    os.makedirs(os.path.dirname(PREVIOUS_FILE), exist_ok=True)  # create ~/.config/sparkTerminal if needed
    parser = configparser.ConfigParser(interpolation=None)  # writer for sparkTerminal's own note
    parser["previous"] = {"exec": current}  # remember the value that is replaced
    with open(PREVIOUS_FILE, "w", encoding="utf-8") as handle:  # save the note BEFORE changing anything
        parser.write(handle)  # write it
    if previous_terminal() != current:  # the note must be readable, otherwise Restore could not work
        return "Not changed: the previous value could not be saved."  # nothing is changed
    setting.set_string(TERMINAL_KEY, ours)  # the one and only change to the desktop: our command becomes the default
    Gio.Settings.sync()  # write it out at once
    if setting.get_string(TERMINAL_KEY) != ours:  # check that GNOME took it
        return "Not changed: the desktop did not accept the setting."  # the saved note stays, it is harmless
    return "Done. sparkTerminal is now the default terminal."  # success


def restore_default_terminal():  # puts the saved previous value back; returns a short message for the user
    setting = terminal_setting()  # the GNOME setting
    if setting is None:  # no such setting on this desktop
        return "This desktop has no default terminal setting."  # nothing is changed
    previous = previous_terminal()  # the value saved by "Set sparkTerminal as default"
    if previous is None:  # nothing saved
        return "Nothing to restore: no previous value is saved."  # nothing is changed
    if setting.get_string(TERMINAL_KEY) != own_command():  # something else changed the default since then
        return "Not changed: the default is not sparkTerminal any more."  # do not overwrite someone else's choice
    setting.set_string(TERMINAL_KEY, previous)  # put the old value back
    Gio.Settings.sync()  # write it out at once
    if setting.get_string(TERMINAL_KEY) != previous:  # check that GNOME took it
        return "Not restored: the desktop did not accept the setting."  # the saved note stays
    try:  # the note is no longer needed
        os.remove(PREVIOUS_FILE)  # delete sparkTerminal's own note (nothing else)
    except OSError:  # ignore a problem here
        pass  # harmless
    return "Done. The previous default terminal is back."  # success


def parse_launch_arguments(args):  # what another program asked for on the command line: a command to run and a folder to start in
    command = None  # the command and its arguments, if one was asked for
    folder = None  # the folder to start in, if one was asked for
    index = 0  # position in the argument list
    while index < len(args):  # look at the arguments one by one
        arg = args[index]  # the argument looked at now
        if arg in ("-e", "-x", "--"):  # everything after this word is the command and its arguments
            rest = args[index + 1:]  # the command part
            if len(rest) == 1 and any(ch.isspace() for ch in rest[0]) and not os.path.exists(rest[0]):  # one single text with spaces (gnome-terminal style): split it the way a shell would
                try:  # a text with an open quote cannot be split
                    rest = shlex.split(rest[0])  # split into command and arguments
                except ValueError:  # broken quoting
                    rest = [rest[0]]  # use it as it is
            command = rest or None  # no words after the marker means no command
            break  # the rest was the command, so there is nothing more to read
        if arg.startswith("--working-directory="):  # folder written as --working-directory=FOLDER
            folder = arg.split("=", 1)[1]  # the part after the equals sign
        elif arg == "--working-directory" and index + 1 < len(args):  # folder written as --working-directory FOLDER
            folder = args[index + 1]  # the next argument
            index += 1  # it has been used
        index += 1  # next argument (other options are ignored, as before)
    return {"command": command, "folder": folder}  # what was asked (None for anything not asked)


def launch_rc_lines(command):  # bash lines that run a requested command once, say what runs, and leave the shell open afterwards
    joined = shlex.join(command)  # the command as one safely quoted line
    return [  # one bash line per item
        "printf '%s\\n' " + shlex.quote("sparkTerminal: running the command another program asked for: " + joined),  # tell the user what is running
        "command " + joined,  # run it (the word "command" skips aliases and shell functions)
        "__sparkStatus=$?",  # remember how it ended
        "printf '%s\\n' \"sparkTerminal: the command ended with status $__sparkStatus; this tab stays open\"",  # tell the user it ended
        "unset __sparkStatus",  # tidy up
    ]  # end of the lines


TAB_CSS = """
notebook > header.top > tabs > tab {
    background-image: none;
    background-color: shade(@theme_bg_color, 0.82);
    border: 1px solid alpha(currentColor, 0.35);
    border-radius: 6px 6px 0 0;
    box-shadow: none;
    margin: 4px 2px 0 2px;
    padding: 3px 8px;
    min-height: 0;
}
notebook > header.top > tabs > tab:hover {
    background-color: shade(@theme_bg_color, 0.95);
}
notebook > header.top > tabs > tab:checked {
    background-color: shade(@theme_bg_color, 1.12);
    border-top: 3px solid #76b900;
    box-shadow: none;
}
notebook.spark-light > header {
    background-color: #dcd9d5;
    background-image: none;
}
notebook.spark-light > header.top > tabs > tab {
    background-color: #cfccc7;
    color: #202020;
}
notebook.spark-light > header.top > tabs > tab label {
    color: #202020;
}
notebook.spark-light > header.top > tabs > tab:hover {
    background-color: #e2dfdb;
}
notebook.spark-light > header.top > tabs > tab:checked {
    background-color: #f6f5f4;
}
notebook.spark-light > header.top button {
    color: #202020;
}
"""  # style of the tab row (the spark-light rules apply while the tab in front uses the light theme): every tab is a box, the active tab is lighter with a green line on top (colours follow the desktop theme)


def apply_tab_style():  # gives the tabs their box look; used only inside this program
    try:  # a theme or GTK problem must never stop the program
        provider = Gtk.CssProvider()  # holds the style text
        provider.load_from_data(TAB_CSS.encode("utf-8"))  # read the style
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)  # apply it to this program only
    except Exception:  # style not applied: the tabs keep the theme look
        pass  # nothing else to do


def half_screen_rectangle(side):  # (x, y, width, height) of the left or right half of the usable area of the monitor under the mouse pointer
    display = Gdk.Display.get_default()  # connection to the screen
    pointer = display.get_default_seat().get_pointer()  # the mouse of the user
    _screen, pointer_x, pointer_y = pointer.get_position()  # where the pointer is, in screen coordinates
    monitor = display.get_monitor_at_point(pointer_x, pointer_y)  # the monitor under the pointer
    area = monitor.get_workarea()  # usable area of that monitor (without the top bar and the dock)
    half = area.width // 2  # half of the usable width
    left = area.x if side == "left" else area.x + area.width - half  # left edge of the chosen half
    return left, area.y, half, area.height  # position and size of the half


def apply_look(terminal, settings):  # colours and font of one terminal widget (tab or preview)
    theme = effective_theme(settings)  # dark or light
    foreground = Gdk.RGBA()  # text colour object
    foreground.parse(TEXT_RGB[theme][settings["text_colour"]])  # chosen text colour for this theme
    background = Gdk.RGBA()  # background colour object
    background.parse(BACKGROUNDS[theme])  # black or white
    palette = []  # the 16 standard colours for this theme
    for hexcolour in PALETTES[theme]:  # one entry per colour
        colour = Gdk.RGBA()  # colour object
        colour.parse(hexcolour)  # e.g. "#6aa7ff"
        palette.append(colour)  # add it to the list
    terminal.set_colors(foreground, background, palette)  # text colour, background and the 16 standard colours (ls directories, errors) in one call
    desc = system_font()  # start from the system monospace font
    desc.set_size(int(font_points(settings["font_size"]) * Pango.SCALE))  # medium or large size
    terminal.set_font(desc)  # set the font of this terminal only


class SparkTerminalWindow(Gtk.Window):  # the main window of the program
    def __init__(self, launch=None):  # build the window when the program starts (launch = what another program asked for, or None)
        super().__init__(title=APP_TITLE)  # create a normal window with the program name as title
        self.set_default_size(1000, 600)  # start at 1000 x 600 pixels (resizable)
        icon_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "sparkTerminalIcon.svg")  # icon file next to the program
        if os.path.isfile(icon_path):  # only when the icon was installed with the program
            self.set_icon_from_file(icon_path)  # show it in the title bar and the task bar
        self.tab_counter = 0  # counts tabs ever opened, used for default names and file names
        self.tabs = {}  # per tab (keyed by its scroll area): terminal widget, settings, prompt file
        self.defaults = load_defaults()  # program defaults for new tabs

        os.makedirs(RUNTIME_DIR, mode=0o700, exist_ok=True)  # private folder (only this user can read it) for the per-tab startup files

        self.notebook = Gtk.Notebook()  # tab container
        self.notebook.set_scrollable(True)  # let many tabs scroll instead of squeezing
        apply_tab_style()  # boxed tab look
        self.notebook.connect_after("switch-page", self.on_page_switched)  # the tab row follows the theme of the tab that comes to the front
        self.add(self.notebook)  # place the tab container inside the window

        plus_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)  # holder for the "+" button (left end of the tab row)
        gear_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)  # holder for the gear button (right end of the tab row)
        plus_button = Gtk.Button.new_from_icon_name("list-add-symbolic", Gtk.IconSize.MENU)  # the "+" button with the standard add icon
        plus_button.set_relief(Gtk.ReliefStyle.NONE)  # flat look, like a tab bar button
        plus_button.set_tooltip_text("New tab: choose its name and settings (Ctrl+Shift+T)")  # plain-language hint on hover
        plus_button.connect("clicked", self.on_new_tab_clicked)  # clicking it opens the new-tab box
        gear_button = Gtk.Button.new_from_icon_name("emblem-system-symbolic", Gtk.IconSize.MENU)  # gear button for program defaults
        gear_button.set_relief(Gtk.ReliefStyle.NONE)  # flat look
        gear_button.set_tooltip_text("Default settings for new tabs (open tabs keep their own settings)")  # hint on hover
        gear_button.connect("clicked", self.on_defaults_clicked)  # clicking it opens the defaults box
        plus_box.pack_start(plus_button, False, False, 0)  # the "+" goes into its own holder
        gear_box.pack_start(gear_button, False, False, 0)  # the gear goes into its own holder
        plus_box.show_all()  # action widgets must be shown explicitly
        gear_box.show_all()  # action widgets must be shown explicitly
        self.notebook.set_action_widget(plus_box, Gtk.PackType.START)  # the "+" sits at the left end of the tab row, inside the tab bar
        self.notebook.set_action_widget(gear_box, Gtk.PackType.END)  # the gear stays at the right end

        self.connect("key-press-event", self.on_key_press)  # listen for the keyboard shortcuts
        self.connect("destroy", Gtk.main_quit)  # closing the window ends the program

        self.tab_counter += 1  # count the first tab
        command, folder, notice = None, None, ""  # what the first tab runs, where it starts, and a message when a request is not followed
        if launch and (launch["command"] or launch["folder"]):  # another program asked for a command or a folder
            if self.defaults.get("run_commands") == "yes":  # the user allowed this in the gear dialog
                command = launch["command"]  # the command to run
                if launch["folder"] and os.path.isdir(launch["folder"]):  # the folder exists
                    folder = launch["folder"]  # start there
                elif launch["folder"]:  # the folder does not exist
                    notice = "folder not found, started in the home folder"  # tell the user
            else:  # not allowed: behave as always, but say so
                notice = "another program asked for a command or folder; 'Run commands from other programs' is off (see the gear dialog)"  # tell the user
        self.add_tab(os.path.basename(command[0]) or "Shell" if command else "Shell", dict(self.defaults), command, folder)  # open the first tab (named after the command when there is one)
        if notice:  # something to tell the user
            GLib.idle_add(self.show_copy_notice, notice, 8)  # show it in the title bar for 8 seconds once the window is up

    # ---------- settings box (used for new tabs, tab settings and program defaults) ----------

    def settings_dialog(self, title, settings, reset_to, ok_label, name=None):  # returns (name, settings) or None on Cancel
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)  # box on top of the main window
        dialog.add_buttons("Reset", 1, "Cancel", Gtk.ResponseType.CANCEL, ok_label, Gtk.ResponseType.OK)  # Reset, Cancel, Apply/Open tab
        dialog.set_default_response(Gtk.ResponseType.OK)  # Enter key means OK
        grid = Gtk.Grid(column_spacing=12, row_spacing=8, border_width=12)  # two-column layout: label, control
        dialog.get_content_area().add(grid)  # put the layout in the box
        row = 0  # current row in the layout

        name_entry = None  # name field only for tabs, not for program defaults
        if name is not None:  # a tab is being created or changed
            name_entry = Gtk.Entry(text=name, width_chars=30, activates_default=True)  # tab name field, Enter presses OK
            grid.attach(Gtk.Label(label="Tab name", xalign=0), 0, row, 1, 1)  # label
            grid.attach(name_entry, 1, row, 1, 1)  # field
            row += 1  # next row

        def combo(label_text, options, active):  # helper: a labelled drop-down list
            nonlocal row  # use the row counter of the outer function
            box = Gtk.ComboBoxText()  # drop-down list
            for value, text in options:  # add every choice
                box.append(value, text)  # stored value and visible text
            box.set_active_id(active)  # select the current value
            grid.attach(Gtk.Label(label=label_text, xalign=0), 0, row, 1, 1)  # label
            grid.attach(box, 1, row, 1, 1)  # list
            row += 1  # next row
            return box  # caller reads the choice from it

        prompt_box = combo("Prompt", sorted(PROMPT_STYLES, key=lambda item: item[1].lower()), settings["prompt_style"])  # prompt style list, sorted A to Z by the text shown
        system_check = Gtk.CheckButton(label="Always prefix with the system name (user@system)")  # system-name switch
        system_check.set_active(settings["system_name"] == "yes")  # current state
        grid.attach(system_check, 1, row, 1, 1)  # under the prompt list
        row += 1  # next row
        prompt_colour_box = combo("Prompt colour", PROMPT_COLOURS, settings["prompt_colour"])  # prompt colour list, directly under the prompt settings
        theme_box = combo("Theme", THEMES, settings["theme"])  # theme list
        colour_box = combo("Text colour", TEXT_COLOURS, settings["text_colour"])  # text colour list
        sizes = [(s, f"{s.capitalize()} ({font_points(s):g} pt)") for s in FONT_SIZES]  # "Medium (12 pt)", "Large (15 pt)"
        size_box = combo("Font size", sizes, settings["font_size"])  # font size list
        copy_check = None  # the copy switch exists only in the program defaults dialog (gear button), not for single tabs
        start_check = None  # "Add start time" option (defaults dialog only)
        end_check = None  # "Add end time" option (defaults dialog only)
        saved_times = {"start": settings["copy_start_time"] == "yes", "end": settings["copy_end_time"] == "yes"}  # the user's time-option choices, kept while the main copy switch is off
        if name is None:  # only the gear dialog has no tab name field
            copy_check = Gtk.CheckButton(label="Copy command results (all tabs)")  # copy switch for the whole application
            copy_check.set_active(settings["copy_result"] == "yes")  # current state
            grid.attach(copy_check, 1, row, 1, 1)  # under the font size list
            row += 1  # next row
            start_check = Gtk.CheckButton(label="Add start time (first line)")  # puts "Started: <time>" before the copied result
            start_check.set_active(settings["copy_start_time"] == "yes")  # current state
            start_check.set_margin_start(24)  # indented: belongs to the copy switch above
            grid.attach(start_check, 1, row, 1, 1)  # under the copy switch
            row += 1  # next row
            end_check = Gtk.CheckButton(label="Add end time (last line)")  # puts "Finished: <time>" after the copied result
            end_check.set_active(settings["copy_end_time"] == "yes")  # current state
            end_check.set_margin_start(24)  # indented like the start option
            grid.attach(end_check, 1, row, 1, 1)  # under the start option
            row += 1  # next row
            syncing = [False]  # True while the program itself changes the two options (so that this is not taken for a user choice)

            def remember_time_options(_button):  # the user ticked or unticked a time option: keep the choice
                if not syncing[0] and copy_check.get_active():  # only real clicks while copying is on
                    saved_times["start"] = start_check.get_active()  # start option as chosen
                    saved_times["end"] = end_check.get_active()  # end option as chosen

            def sync_time_options(*_args):  # copying on: show the user's choices; copying off: show both options unticked and greyed out
                syncing[0] = True  # these changes come from the program, not from the user
                on = copy_check.get_active()  # state of the main switch
                start_check.set_active(saved_times["start"] if on else False)  # shown as chosen, or unticked
                end_check.set_active(saved_times["end"] if on else False)  # same for the end option
                start_check.set_sensitive(on)  # greyed out while copying is off
                end_check.set_sensitive(on)  # same for the end option
                syncing[0] = False  # back to normal

            start_check.connect("toggled", remember_time_options)  # watch the start option
            end_check.connect("toggled", remember_time_options)  # watch the end option
            copy_check.connect("toggled", sync_time_options)  # follow the main switch
            sync_time_options()  # first display
        half_check = None  # the half-screen choice exists only in the program defaults dialog (gear button), not for single tabs
        left_radio = None  # "Left half" choice (defaults dialog only)
        right_radio = None  # "Right half" choice (defaults dialog only)
        if name is None:  # only the gear dialog has no tab name field
            half_check = Gtk.CheckButton(label="Open the window on half of the screen")  # half-screen switch for the whole application
            half_check.set_active(settings["half_screen"] == "yes")  # current state
            grid.attach(half_check, 1, row, 1, 1)  # under the copy switch
            row += 1  # next row
            side_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)  # holder for the two side choices
            left_radio = Gtk.RadioButton.new_with_label_from_widget(None, "Left half")  # first choice starts the radio group
            right_radio = Gtk.RadioButton.new_with_label_from_widget(left_radio, "Right half")  # second choice joins the group
            if settings["half_side"] == "right":  # current side
                right_radio.set_active(True)  # right half selected
            side_box.pack_start(left_radio, False, False, 0)  # left choice first
            side_box.pack_start(right_radio, False, False, 0)  # then the right choice
            side_box.set_sensitive(half_check.get_active())  # the side can only be chosen while the switch is on
            half_check.connect("toggled", lambda button: side_box.set_sensitive(button.get_active()))  # enable or disable the side choice
            grid.attach(side_box, 1, row, 1, 1)  # under the half-screen switch
            row += 1  # next row

        run_state = {"on": settings["run_commands"] == "yes", "os": False}  # the real choice, and whether the box only shows what the OS terminal does
        run_check = None  # "Run commands from other programs" exists only in the program defaults dialog (gear button)
        if name is None:  # only the gear dialog has no tab name field
            run_check = Gtk.CheckButton(label="Run commands from other programs")  # switch for the whole application
            run_check.set_active(settings["run_commands"] == "yes")  # current state
            run_note_base = ("When a program asks for a terminal to run a command (for example to start htop) or to open in a folder, "
                             "sparkTerminal does it in a tab that stays open when the command ends.")  # plain explanation with an example
            run_note = Gtk.Label(label=run_note_base, xalign=0)  # the label under the switch
            run_note.set_line_wrap(True)  # long text wraps
            run_note.set_max_width_chars(50)  # keeps the box narrow
            run_note.set_margin_start(24)  # indented: belongs to the switch above
            run_note.get_style_context().add_class("dim-label")  # smaller, greyed text
        if name is None:  # only the gear dialog has the default-terminal buttons
            default_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)  # holder: status text, buttons, note
            default_status = Gtk.Label(xalign=0)  # says what the default terminal is now
            default_status.set_line_wrap(True)  # long text wraps
            default_status.set_max_width_chars(50)  # keeps the box narrow
            button_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)  # the two buttons side by side
            make_button = Gtk.Button(label="Set sparkTerminal as default")  # sets sparkTerminal as default (asks first)
            restore_button = Gtk.Button(label="Restore OS default")  # puts the saved value back
            button_row.pack_start(make_button, False, False, 0)  # first button
            button_row.pack_start(restore_button, False, False, 0)  # second button
            default_note = Gtk.Label(label="Takes effect at once; not part of Apply or Cancel. GNOME Terminal is not changed.", xalign=0)  # note
            default_note.set_line_wrap(True)  # long text wraps
            default_note.set_max_width_chars(50)  # keeps the box narrow
            default_note.get_style_context().add_class("dim-label")  # smaller, greyed text
            default_box.pack_start(default_status, False, False, 0)  # status first
            default_box.pack_start(button_row, False, False, 0)  # then the buttons
            default_warning = Gtk.Label(xalign=0)  # warning line, not greyed out so that it stands out
            default_warning.set_markup("<span foreground='#e01b24' weight='bold' size='large'>\u26a0</span> Some programs that ask for a terminal to run a command will open an empty window. Tick 'Run commands from other programs' below to fix this.")  # red bold warning symbol
            default_warning.set_line_wrap(True)  # long text wraps
            default_warning.set_max_width_chars(50)  # keeps the box narrow
            default_box.pack_start(default_note, False, False, 0)  # then the note
            default_box.pack_start(default_warning, False, False, 0)  # then the warning line
            default_box.pack_start(run_check, False, False, 0)  # then the switch, below the warning it answers
            default_box.pack_start(run_note, False, False, 0)  # and its explanation
            default_warning.set_no_show_all(True)  # show_all() must not override the visibility chosen below

            def update_warning(*_args):  # the warning is only needed while commands from other programs are not allowed
                default_warning.set_visible(not run_check.get_active())  # hidden while the switch is ticked

            def on_run_toggled(*_args):  # the box changed
                if not run_state["os"]:  # a click by the user, not the indicator shown while the OS terminal is in use
                    run_state["on"] = run_check.get_active()  # remember the real choice

            def show_run_state(os_in_use):  # show the box for the current default terminal
                run_state["os"] = os_in_use  # set first, so that the change below is not taken for a click
                if os_in_use:  # the OS terminal runs commands from other programs
                    run_check.set_active(True)  # indicator only: the real choice stays in run_state
                else:  # sparkTerminal is the default
                    run_check.set_active(run_state["on"])  # the real choice
                run_check.set_sensitive(not os_in_use)  # can be changed only while sparkTerminal is the default
                update_warning()  # the red warning follows the box

            run_check.connect("toggled", on_run_toggled)  # remember clicks
            run_check.connect("toggled", update_warning)  # follow the switch
            update_warning()  # first display
            grid.attach(Gtk.Label(label="Default terminal", xalign=0, yalign=0), 0, row, 1, 1)  # label
            grid.attach(default_box, 1, row, 1, 1)  # the holder
            row += 1  # next row

            def refresh_default_status(message=""):  # show the current state and enable only the buttons that make sense
                setting = terminal_setting()  # the GNOME setting, or None
                can_make = False  # "Set sparkTerminal as default" enabled?
                can_restore = False  # "Restore OS default" enabled?
                ours = False  # is sparkTerminal the default terminal now?
                if setting is None:  # not available on this desktop
                    text = "Not available on this desktop."  # status text
                else:  # available
                    current = setting.get_string(TERMINAL_KEY)  # the command set now
                    ours = current == own_command()  # is it this program?
                    problem = command_problem(own_command())  # can this program be used as default?
                    can_restore = ours and previous_terminal() is not None  # only when we set it and know the old value
                    can_make = (not ours) and not problem  # only when it is not set yet and usable
                    if ours:  # already the default
                        text = "sparkTerminal is the default terminal."  # status text
                    elif problem:  # cannot be used
                        text = "Cannot be set: " + problem + "."  # status text
                    else:  # something else is the default
                        text = "Current default: " + current  # status text
                if message:  # result of the last click
                    text = message + "\n" + text  # shown above the status
                default_status.set_text(text)  # update the label
                make_button.set_sensitive(can_make)  # update the buttons
                restore_button.set_sensitive(can_restore)  # update the buttons
                show_run_state(not ours)  # ticked and greyed out while the OS terminal is in use, the real choice otherwise

            def on_make_default(_button):  # click on "Set sparkTerminal as default"
                already = False  # the switch always starts off when sparkTerminal becomes the default: the user must choose it
                ask = Gtk.MessageDialog(transient_for=dialog, modal=True, message_type=Gtk.MessageType.QUESTION,
                                        buttons=Gtk.ButtonsType.OK_CANCEL, text="Set sparkTerminal as your default terminal?")  # confirmation first, OK or Cancel
                text = ("This changes one setting of your user account: which terminal programs open by default. "
                        "GNOME Terminal is not changed and still opens from its own icon. "
                        "You can undo this at any time with \"Restore OS default\".\n\n")  # plain explanation
                if already:  # commands from other programs are allowed
                    text += "Programs that ask the terminal to run a command will work: sparkTerminal opens a tab for the command and keeps it open."  # good news
                else:  # not allowed yet: warn and offer the fix
                    text += ("<span foreground='#e01b24' weight='bold' size='large'>\u26a0</span> <b>Warning:</b> some programs ask the terminal to run a command for you. "
                             "For example, a program that wants to start htop in a terminal will open an empty "
                             "sparkTerminal window, and htop will not start. Tick the box below to let sparkTerminal run such commands.")  # warning with a real example
                ask.format_secondary_markup(text)  # show the text
                run_in_question = None  # the extra tick box exists only while the switch is off
                if not already:  # offer the choice here too
                    run_in_question = Gtk.CheckButton(label="Also run commands from other programs (the warning goes away)")  # unticked: the user must choose it
                    ask.get_message_area().pack_start(run_in_question, False, False, 0)  # under the text
                    run_in_question.show()  # make it visible
                answer = ask.run()  # wait for OK or Cancel
                with_commands = run_in_question is not None and run_in_question.get_active()  # did the user also tick the box?
                ask.destroy()  # close the question
                if answer == Gtk.ResponseType.OK:  # the user agreed
                    message = make_default_terminal()  # do it
                    if message.startswith("Done"):  # the default was set
                        run_state["on"] = with_commands  # off unless the user ticked it in the question
                        self.defaults["run_commands"] = "yes" if with_commands else "no"  # in the running program
                        save_defaults(self.defaults)  # and save it at once (other pending changes in this box still need Apply)
                        message += "\nRun commands from other programs is " + ("on (saved)." if with_commands else "off (saved). Tick it below to allow it.")  # tell the user
                    refresh_default_status(message)  # show the result

            def on_restore_default(_button):  # click on "Restore OS default"
                message = restore_default_terminal()  # undo the default terminal
                if message.startswith("Done"):  # the OS default is back
                    run_state["on"] = False  # sparkTerminal's own switch goes back to off; the box now only shows what the OS terminal does
                    self.defaults["run_commands"] = "no"  # switch it off in the running program
                    save_defaults(self.defaults)  # and save it at once (other pending changes in this box still need Apply)
                    message += "\nsparkTerminal's own switch for running commands is reset to off (saved)."  # tell the user
                refresh_default_status(message)  # show the result

            make_button.connect("clicked", on_make_default)  # connect the buttons
            restore_button.connect("clicked", on_restore_default)  # connect the buttons
            refresh_default_status()  # first display

        grid.attach(Gtk.Label(label="Preview (before Apply)", xalign=0), 0, row, 2, 1)  # preview heading
        row += 1  # next row
        preview = Vte.Terminal()  # a real terminal widget used only to show the sample; no shell runs in it
        preview.set_size_request(560, 70)  # room for the sample line
        preview.set_can_focus(False)  # it cannot be typed into
        grid.attach(preview, 0, row, 2, 1)  # full width under the controls

        def chosen_time(which, check):  # a time option as the user chose it (while copying is off the box is shown unticked, the choice is in saved_times)
            if check is None:  # a tab dialog has no such option
                return settings["copy_" + which + "_time"]  # keep the stored value unchanged
            on = check.get_active() if copy_check.get_active() else saved_times[which]  # visible state, or the kept choice
            return "yes" if on else "no"  # stored form

        def current():  # the settings currently chosen in the box
            return {  # one value per setting
                "prompt_style": prompt_box.get_active_id(),  # chosen style
                "system_name": "yes" if system_check.get_active() else "no",  # switch state
                "theme": theme_box.get_active_id(),  # chosen theme
                "text_colour": colour_box.get_active_id(),  # chosen colour
                "prompt_colour": prompt_colour_box.get_active_id(),  # chosen prompt colour
                "font_size": size_box.get_active_id(),  # chosen size
                "half_screen": ("yes" if half_check.get_active() else "no") if half_check is not None else settings["half_screen"],  # half-screen switch state (a tab dialog keeps the value unchanged)
                "half_side": ("right" if right_radio.get_active() else "left") if right_radio is not None else settings["half_side"],  # chosen half (a tab dialog keeps the value unchanged)
                "copy_result": ("yes" if copy_check.get_active() else "no") if copy_check is not None else settings["copy_result"],  # copy switch state (a tab dialog keeps the value unchanged)
                "copy_start_time": chosen_time("start", start_check),  # start-time option (a tab dialog keeps the value unchanged)
                "copy_end_time": chosen_time("end", end_check),  # end-time option (a tab dialog keeps the value unchanged)
                "run_commands": ("yes" if run_state["on"] else "no") if run_check is not None else settings["run_commands"],  # run-commands switch (a tab dialog keeps the value unchanged)
            }  # end of the table above

        def refresh(*_args):  # redraw the preview after any change
            chosen = current()  # read the controls
            apply_look(preview, chosen)  # same colour and font code as the real tabs
            preview.feed(b"\x1b[2J\x1b[H")  # clear the preview and move to the top left
            preview.feed(("\r\n " + sample_prompt(chosen)).encode("utf-8"))  # show the sample prompt line

        def set_controls(values):  # put a set of values into the controls (used by Reset)
            prompt_box.set_active_id(values["prompt_style"])  # style
            system_check.set_active(values["system_name"] == "yes")  # switch
            theme_box.set_active_id(values["theme"])  # theme
            colour_box.set_active_id(values["text_colour"])  # colour
            prompt_colour_box.set_active_id(values["prompt_colour"])  # prompt colour
            size_box.set_active_id(values["font_size"])  # size
            if half_check is not None:  # only the defaults dialog has the half-screen choice
                half_check.set_active(values["half_screen"] == "yes")  # half-screen switch
                (right_radio if values["half_side"] == "right" else left_radio).set_active(True)  # chosen half
            if copy_check is not None:  # only the defaults dialog has the switch
                copy_check.set_active(values["copy_result"] == "yes")  # copy switch
                saved_times["start"] = values["copy_start_time"] == "yes"  # start-time choice from the reset values
                saved_times["end"] = values["copy_end_time"] == "yes"  # end-time choice from the reset values
                sync_time_options()  # show them (unticked and greyed out while copying is off)
            if run_check is not None:  # only the defaults dialog has the run-commands switch
                run_state["on"] = values["run_commands"] == "yes"  # the real choice from the reset values
                show_run_state(run_state["os"])  # show it (ticked and greyed out while the OS terminal is in use)

        for widget in (prompt_box, theme_box, colour_box, prompt_colour_box, size_box):  # every drop-down list
            widget.connect("changed", refresh)  # refresh the preview on change
        system_check.connect("toggled", refresh)  # refresh the preview when the switch changes

        dialog.show_all()  # show the box
        refresh()  # first preview
        if name_entry is not None:  # tab box
            name_entry.select_region(0, -1)  # select the name so typing replaces it
        result = None  # stays None on Cancel
        while True:  # Reset keeps the box open
            response = dialog.run()  # wait for a button
            if response == 1:  # Reset
                set_controls(reset_to)  # fill in the reset values (still needs Apply)
                continue  # keep the box open
            if response == Gtk.ResponseType.OK:  # Apply / Open tab
                new_name = name_entry.get_text().strip() if name_entry is not None else None  # typed name, if any
                result = (new_name, current())  # name and chosen settings
            break  # OK, Cancel or window closed
        dialog.destroy()  # close the box
        return result  # None means Cancel

    # ---------- tabs ----------

    def write_prompt_file(self, record):  # (re)write the tab's prompt file; the shell reads it before each prompt
        with open(record["prompt_file"], "w", encoding="utf-8") as handle:  # overwrite the file
            handle.write("PS1='" + build_ps1(record["settings"]) + "'\n")  # one line setting the prompt (contains no single quotes)

    def add_tab(self, name, settings, command=None, folder=None):  # create one tab with its own bash shell and its own settings (optionally running a requested command in a folder)
        tab_id = self.tab_counter  # number used in the file names of this tab
        prompt_file = os.path.join(RUNTIME_DIR, f"tab{tab_id}.prompt")  # file with this tab's prompt
        rc_file = os.path.join(RUNTIME_DIR, f"tab{tab_id}.rc")  # startup file for this tab's shell
        with open(rc_file, "w", encoding="utf-8") as handle:  # write the startup file (private folder, not your home files)
            handle.write('[ -f "$HOME/.bashrc" ] && . "$HOME/.bashrc"\n')  # first load your normal ~/.bashrc unchanged (read only)
            handle.write('[ -n "$LS_COLORS" ] || eval "$(dircolors -b 2>/dev/null)"\n')  # make sure ls colours exist (system defaults if ~/.bashrc set none)
            handle.write('for __sparkKey in di ow tw st; do\n')  # directory types: normal, other-writable, sticky+other-writable, sticky
            handle.write('  case ":$LS_COLORS:" in\n')  # does this directory type already have a colour?
            handle.write('    *":$__sparkKey="*) LS_COLORS=$(printf "%s" "$LS_COLORS" | sed -E "s/(^|:)($__sparkKey)=([^:]*)/\\1\\2=\\3;01;03/") ;;\n')  # yes: add bold (01) and italic (03) to its existing colour
            handle.write('    *) [ "$__sparkKey" = di ] && LS_COLORS="di=01;03;34:$LS_COLORS" ;;\n')  # no colour for normal directories: bold italic blue
            handle.write('  esac\n')  # end of the check
            handle.write('done; unset __sparkKey; export LS_COLORS\n')  # only this tab's shell gets the changed colours
            handle.write(f'__sparkPrompt() {{ [ -r "{prompt_file}" ] && . "{prompt_file}"; }}\n')  # function that loads this tab's prompt
            handle.write('__sparkN=0\n')  # counter, so the end mark changes the terminal title every time
            handle.write(r"""__sparkMark() { local p=${PS1@P}; while [[ $p == *$'\e['*m* ]]; do p=${p%%$'\e['*}${p#*$'\e['*m}; done; __sparkN=$((__sparkN+1)); printf '\033]0;sparkTerminal:%s:%s\007' "$__sparkN" "${#p}"; }""" + "\n")  # prints the end mark "sparkTerminal:<counter>:<visible prompt width>" (colour codes are not counted)
            handle.write('PROMPT_COMMAND="__sparkPrompt${PROMPT_COMMAND:+; $PROMPT_COMMAND}; __sparkMark"\n')  # run it before every prompt, keeping any existing PROMPT_COMMAND; the mark comes last, right before the prompt is drawn

        if command:  # another program asked for a command and the user allowed it
            with open(rc_file, "a", encoding="utf-8") as handle:  # add to this tab's own startup file (private folder)
                handle.write("\n".join(launch_rc_lines(command)) + "\n")  # runs after everything else is set up, so the prompt returns afterwards

        terminal = Vte.Terminal()  # a new terminal widget for this tab
        terminal.set_scrollback_lines(SCROLLBACK_LINES)  # keep 100000 lines of history to scroll back and to copy results from
        scroller = Gtk.ScrolledWindow()  # adds a scroll bar next to the terminal
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)  # vertical scroll bar only, when needed
        scroller.add(terminal)  # put the terminal inside the scroll area

        record = {"terminal": terminal, "settings": settings, "prompt_file": prompt_file, "rc_file": rc_file, "pid": None, "copy_start": None, "ready": False}  # everything about this tab (pid filled in when bash starts; copy_start = row where the running command's output starts; ready = first prompt seen)
        self.tabs[scroller] = record  # remember it
        self.write_prompt_file(record)  # write the tab's prompt before the shell starts
        apply_look(terminal, settings)  # colours and font of this tab

        self.notebook.append_page(scroller, self.make_tab_label(name, scroller, record))  # add the tab with its clickable title and close button
        self.notebook.set_tab_reorderable(scroller, True)  # tabs can be dragged into another order

        terminal.spawn_async(  # start bash inside this terminal, without blocking the window
            Vte.PtyFlags.DEFAULT,  # normal pseudo-terminal settings
            folder or os.environ.get("HOME", "/"),  # start in the folder another program asked for, otherwise in the home folder
            [SHELL, "--rcfile", rc_file],  # bash with this tab's startup file (which loads ~/.bashrc first)
            None,  # keep the user's own environment variables
            GLib.SpawnFlags.DEFAULT,  # normal start flags
            None,  # no setup function before the shell starts
            None,  # no data for that setup function
            -1,  # no time limit for starting
            None,  # no way to cancel the start
            self.on_shell_started,  # called when bash has started, to remember its process number
            record,  # this tab's information, passed to that function
        )  # end of the start command

        terminal.connect("commit", self.on_commit, record)  # a key press is about to be sent to bash (used to find where a command's output starts)
        terminal.connect("window-title-changed", self.on_title_mark, record)  # the shell's end-of-output mark arrives as a title change
        terminal.connect("child-exited", self.on_shell_exited, scroller)  # when bash ends (e.g. "exit"), close its tab
        terminal.connect("button-press-event", self.on_terminal_clicked)  # right-click inside the terminal opens Copy/Paste/Select all
        self.show_all()  # make the new tab and its widgets visible
        self.notebook.set_current_page(self.notebook.page_num(scroller))  # switch to the new tab
        self.set_tab_bar_theme(settings)  # the tab row follows this tab's theme (also for the very first tab)
        terminal.grab_focus()  # put the keyboard cursor in the terminal so you can type at once

    def on_commit(self, terminal, text, _size, record):  # a key press is about to go to bash
        if text == "\r" and record["ready"] and record["copy_start"] is None:  # one Enter press while the shell waits at its prompt (not a paste, not a key typed into a running program)
            _col, row = terminal.get_cursor_position()  # the cursor is on the command line (row is absolute)
            record["copy_start"] = row + 1  # the output of the command starts on the next row
            record["copy_time"] = time.time()  # moment the command was started (for the optional "Started:" line)

    def on_title_mark(self, terminal, record):  # the shell printed its end-of-output mark (title "sparkTerminal:<counter>:<prompt width>")
        try:  # a problem here must never disturb the terminal
            parts = (terminal.get_window_title() or "").split(":")  # ["sparkTerminal", counter, width]
            if len(parts) != 3 or parts[0] != "sparkTerminal" or not parts[2].isdigit():  # not our mark
                return  # ignore other titles
            record["ready"] = True  # the shell has shown its first prompt
            start = record["copy_start"]  # row where the finished command's output started (None at the first prompt)
            record["copy_start"] = None  # the shell is at its prompt again
            started = record.get("copy_time")  # moment the finished command was started
            finished = time.time()  # moment the command ended (the prompt is back)
            if start is None or self.defaults.get("copy_result") != "yes":  # nothing to copy, or the application-wide switch is off
                return  # leave the clipboard alone
            col, row = terminal.get_cursor_position()  # the cursor is behind the new prompt
            end_col = max(col - int(parts[2]), 0)  # cut the prompt off: the output ends where the prompt starts
            if row < start or (row == start and end_col == 0):  # no output rows at all (empty Enter, command without output)
                return  # leave the clipboard alone
            result = terminal.get_text_range_format(Vte.Format.TEXT, start, 0, row, end_col)  # plain text (no colour codes) of the output rows
            text = result[0] if isinstance(result, tuple) else result  # keep only the text
            text = (text or "").rstrip("\n")  # no trailing empty lines
            if not text.strip():  # empty result (for example a full-screen program)
                return  # leave the clipboard alone
            note = ""  # extra words for the window title
            if len(text.encode("utf-8")) > MAX_COPY_BYTES:  # too big: keep the beginning, cut at a line end
                kept = text.encode("utf-8")[:MAX_COPY_BYTES].decode("utf-8", errors="ignore")  # first 1 MB (a half character at the end is dropped)
                kept = kept[:kept.rfind("\n")] if "\n" in kept else kept  # end at a whole line
                note += f", {text.count(chr(10)) - kept.count(chr(10))} lines left out (limit {MAX_COPY_BYTES // 1000000} MB)"  # how many lines did not fit
                text = kept  # copy only the kept part
            if row - start >= SCROLLBACK_LINES:  # more rows than the history holds
                note += ", the beginning scrolled out of the history"  # tell the user
            count = text.count("\n") + 1  # number of result lines (the optional time lines are not counted)
            text = copy_text_with_times(text, started, finished, self.defaults.get("copy_start_time") == "yes", self.defaults.get("copy_end_time") == "yes")  # add the optional time lines
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).set_text(text, -1)  # replace the clipboard with this command's result
            self.show_copy_notice(f"copied {count} line{'' if count == 1 else 's'}{note}")  # short notice in the title bar
        except Exception:  # never let the copy feature break the terminal
            pass  # ignore the problem

    def show_copy_notice(self, message, seconds=3):  # show a short notice in the window title (3 seconds unless told otherwise), then restore the normal title
        self.set_title(APP_TITLE + " - " + message)  # notice in the title bar
        self.copy_notice_id = getattr(self, "copy_notice_id", 0) + 1  # a newer notice replaces an older one
        notice_id = self.copy_notice_id  # remember which notice this is

        def restore():  # runs once after 3 seconds
            if notice_id == self.copy_notice_id:  # only if no newer notice has appeared
                self.set_title(APP_TITLE)  # back to the normal title
            return False  # do not repeat
        GLib.timeout_add_seconds(seconds, restore)  # schedule it

    def on_shell_started(self, _terminal, pid, _error, record):  # bash has started (or failed to start)
        if pid and pid > 0:  # a real process number
            record["pid"] = pid  # remember it, used to check for running programs and to close the tab

    def make_tab_label(self, name, scroller, record):  # tab title with click handling and a close button
        label = Gtk.Label(label=name)  # the visible tab text
        record["label"] = label  # remember the label so it can be renamed later
        event_box = Gtk.EventBox()  # a plain label cannot receive clicks, an EventBox around it can
        event_box.set_visible_window(False)  # keep the tab's normal look
        event_box.add(label)  # put the text inside the click area
        event_box.set_tooltip_text("Double-click to rename; right-click for rename, tab settings or close")  # hint on hover
        event_box.connect("button-press-event", self.on_tab_label_clicked, scroller)  # handle the mouse clicks
        close_button = Gtk.Button.new_from_icon_name("window-close-symbolic", Gtk.IconSize.MENU)  # small x button
        close_button.set_relief(Gtk.ReliefStyle.NONE)  # flat look, like other tab close buttons
        close_button.set_focus_on_click(False)  # clicking it does not take the keyboard away from the terminal
        close_button.set_tooltip_text("Close this tab (Ctrl+Shift+W)")  # hint on hover
        close_button.connect("clicked", lambda _b: self.close_tab(scroller))  # clicking it closes this tab
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)  # name and x side by side
        box.pack_start(event_box, True, True, 0)  # name on the left
        box.pack_start(close_button, False, False, 0)  # x on the right
        box.show_all()  # make both visible
        return box  # used as the tab's title widget

    def set_tab_bar_theme(self, settings):  # light tab row for a light tab, normal (desktop) look otherwise
        try:  # a style problem must never stop the program
            context = self.notebook.get_style_context()  # style information of the tab container
            if settings is not None and effective_theme(settings) == "light":  # the tab in front uses the light theme
                context.add_class("spark-light")  # switch on the light tab row style
            else:  # dark theme (or no tab)
                context.remove_class("spark-light")  # back to the normal tab row style
        except Exception:  # not possible: keep the current look
            pass  # nothing else to do

    def on_page_switched(self, _notebook, page, _number):  # another tab came to the front
        record = self.tabs.get(page)  # that tab's information (None while a tab is being built)
        self.set_tab_bar_theme(record["settings"] if record else None)  # light or normal tab row

    def tab_label(self, scroller):  # the Gtk.Label of a tab
        return self.tabs[scroller]["label"]  # label remembered when the tab was made

    def current_scroller(self):  # the tab in front, or None
        page = self.notebook.get_current_page()  # index of the tab in front (-1 if none)
        return self.notebook.get_nth_page(page) if page >= 0 else None  # its scroll area

    def on_tab_label_clicked(self, _widget, event, scroller):  # mouse click on a tab title
        if event.type == Gdk.EventType._2BUTTON_PRESS and event.button == 1:  # left double-click
            self.rename_tab(scroller)  # open the rename box
            return True  # click handled
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:  # right-click
            menu = Gtk.Menu()  # small pop-up menu
            rename_item = Gtk.MenuItem(label="Rename tab…")  # first entry
            rename_item.connect("activate", lambda _i: self.rename_tab(scroller))  # opens the rename box
            settings_item = Gtk.MenuItem(label="Tab settings…")  # second entry
            settings_item.connect("activate", lambda _i: self.tab_settings(scroller))  # opens the tab settings box
            menu.append(rename_item)  # add the first entry
            menu.append(settings_item)  # add the second entry
            close_item = Gtk.MenuItem(label="Close tab")  # third entry
            close_item.connect("activate", lambda _i: self.close_tab(scroller))  # closes this tab
            menu.append(close_item)  # add the third entry
            menu.show_all()  # make the entries visible
            menu.popup_at_pointer(event)  # show the menu where the mouse is
            return True  # click handled
        return False  # other clicks: normal behaviour (a single click switches tab)

    def rename_tab(self, scroller=None):  # quick rename (name only)
        scroller = scroller or self.current_scroller()  # the given tab, or the one in front
        if scroller is None:  # no tab at all
            return  # nothing to rename
        dialog = Gtk.Dialog(title="Rename tab", transient_for=self, modal=True)  # small box on top of the window
        dialog.add_buttons("Cancel", Gtk.ResponseType.CANCEL, "OK", Gtk.ResponseType.OK)  # Cancel and OK buttons
        dialog.set_default_response(Gtk.ResponseType.OK)  # Enter key means OK
        entry = Gtk.Entry(text=self.tab_label(scroller).get_text(), width_chars=30, activates_default=True)  # current name, Enter presses OK
        box = dialog.get_content_area()  # area above the buttons
        box.set_border_width(10)  # margin
        box.add(entry)  # the name field
        dialog.show_all()  # show the box
        entry.select_region(0, -1)  # select the name so typing replaces it
        response = dialog.run()  # wait for a button
        name = entry.get_text().strip()  # typed name without spaces at the ends
        dialog.destroy()  # close the box
        if response == Gtk.ResponseType.OK and name:  # OK with a non-empty name (Cancel or empty keeps the old name)
            self.tab_label(scroller).set_text(name)  # show the new name

    def tab_settings(self, scroller=None):  # change the name and settings of one tab only
        scroller = scroller or self.current_scroller()  # the given tab, or the one in front
        if scroller is None:  # no tab at all
            return  # nothing to change
        record = self.tabs[scroller]  # this tab's information
        result = self.settings_dialog("Tab settings", record["settings"], self.defaults, "Apply", self.tab_label(scroller).get_text())  # Reset = program defaults
        if result is None:  # Cancel
            return  # nothing changes
        name, settings = result  # chosen name and settings
        if name:  # empty name keeps the old one
            self.tab_label(scroller).set_text(name)  # new tab name
        record["settings"] = settings  # remember the new settings for this tab
        apply_look(record["terminal"], settings)  # colours and font change at once
        self.set_tab_bar_theme(settings)  # the tab row follows the new theme
        self.write_prompt_file(record)  # the prompt changes at the next prompt (press Enter)

    def on_new_tab_clicked(self, _button=None):  # "+" button or Ctrl+Shift+T
        suggested = f"Shell {self.tab_counter + 1}"  # suggested name
        result = self.settings_dialog("New tab", self.defaults, self.defaults, "Open tab", suggested)  # name + settings, starting from the defaults
        if result is None:  # Cancel
            return  # no tab is created
        name, settings = result  # chosen name and settings
        self.tab_counter += 1  # count the new tab
        self.add_tab(name or suggested, settings)  # empty name falls back to the suggestion

    def place_on_half(self):  # put the window on the chosen half of the screen; does nothing when the switch is off
        if self.defaults.get("half_screen") != "yes":  # switch is off
            return  # leave the window as it is
        try:  # pointer or monitor information may be missing on unusual setups
            left, top, width, height = half_screen_rectangle(self.defaults["half_side"])  # the chosen half of the monitor under the pointer
        except Exception:  # keep the normal window
            return  # nothing to do
        if self.is_maximized():  # a maximized window ignores size and position
            self.unmaximize()  # make it a normal window first
        self.resize(width, height)  # width of half the screen, full usable height
        self.move(left, top)  # left or right edge
        from gi.repository import GLib  # timer, imported here so the top of the program stays unchanged
        GLib.timeout_add(200, self.fit_frame, left, top, width, height)  # later, when the title bar exists, make the whole frame fit

    def fit_frame(self, left, top, width, height):  # shrink the window by the size of its title bar and borders so the frame fits the half exactly
        try:  # never let a placement detail stop the program
            gdk_window = self.get_window()  # the real window on screen (None before it is shown)
            if gdk_window is not None:  # only when it exists
                frame = gdk_window.get_frame_extents()  # size of the window including title bar and borders
                extra_width = max(0, frame.width - width)  # how much wider than the half the frame is
                extra_height = max(0, frame.height - height)  # how much taller than the usable height the frame is
                if extra_width or extra_height:  # the frame is too big
                    self.resize(width - extra_width, height - extra_height)  # make the inside smaller by that amount
                    self.move(left, top)  # keep the top left corner in place
        except Exception:  # ignore any problem
            pass  # the window simply keeps its size
        return False  # run only once

    def on_defaults_clicked(self, _button=None):  # gear button: defaults for new tabs
        result = self.settings_dialog("Default settings for new tabs", self.defaults, BUILT_IN_DEFAULTS, "Apply")  # Reset = agreed built-in defaults
        if result is None:  # Cancel
            return  # nothing changes
        old_half = (self.defaults.get("half_screen"), self.defaults.get("half_side"))  # half-screen choice before the change
        self.defaults = result[1]  # new defaults (open tabs keep their own settings)
        save_defaults(self.defaults)  # save to ~/.config/sparkTerminal/settings.conf
        if (self.defaults["half_screen"], self.defaults["half_side"]) != old_half:  # the half-screen choice was changed
            self.place_on_half()  # move and resize the open window at once

    def current_terminal(self):  # the terminal widget of the tab in front, or None
        scroller = self.current_scroller()  # the tab in front
        record = self.tabs.get(scroller) if scroller is not None else None  # its information
        return record["terminal"] if record else None  # its terminal widget

    def copy_text(self, terminal):  # copy the selected text to the clipboard
        if terminal is not None and terminal.get_has_selection():  # only when some text is selected
            terminal.copy_clipboard_format(Vte.Format.TEXT)  # put the selection on the clipboard as plain text

    def paste_text(self, terminal):  # paste the clipboard into the terminal (as if typed)
        if terminal is not None:  # a tab exists
            terminal.paste_clipboard()  # VTE inserts the clipboard text at the prompt

    def on_terminal_clicked(self, terminal, event):  # mouse click inside a terminal
        if event.type != Gdk.EventType.BUTTON_PRESS or event.button != 3:  # only a single right-click
            return False  # left/middle clicks keep their normal behaviour (select, middle-click paste)
        menu = Gtk.Menu()  # small pop-up menu
        copy_item = Gtk.MenuItem(label="Copy (Ctrl+Shift+C)")  # first entry
        copy_item.set_sensitive(terminal.get_has_selection())  # greyed out when nothing is selected
        copy_item.connect("activate", lambda _i: self.copy_text(terminal))  # copies the selection
        paste_item = Gtk.MenuItem(label="Paste (Ctrl+Shift+V)")  # second entry
        paste_item.connect("activate", lambda _i: self.paste_text(terminal))  # pastes the clipboard
        select_item = Gtk.MenuItem(label="Select all")  # third entry
        select_item.connect("activate", lambda _i: terminal.select_all())  # selects all text in this tab
        for item in (copy_item, paste_item, select_item):  # every entry
            menu.append(item)  # add it to the menu
        menu.show_all()  # make the entries visible
        menu.popup_at_pointer(event)  # show the menu where the mouse is
        return True  # click handled (the terminal does not receive it)

    def on_key_press(self, _widget, event):  # keyboard shortcuts of the window
        ctrl_shift = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK  # Ctrl and Shift held together
        if (event.state & ctrl_shift) == ctrl_shift:  # only react when both are held
            key = Gdk.keyval_name(event.keyval).lower()  # name of the pressed key, lower case
            if key == "t":  # Ctrl+Shift+T
                self.on_new_tab_clicked()  # new tab box
                return True  # shortcut handled, not sent to the shell
            if key == "r":  # Ctrl+Shift+R
                self.rename_tab()  # rename the tab in front
                return True  # shortcut handled, not sent to the shell
            if key == "c":  # Ctrl+Shift+C
                self.copy_text(self.current_terminal())  # copy the selection of the tab in front
                return True  # shortcut handled, not sent to the shell
            if key == "v":  # Ctrl+Shift+V
                self.paste_text(self.current_terminal())  # paste into the tab in front
                return True  # shortcut handled, not sent to the shell
            if key == "w":  # Ctrl+Shift+W
                scroller = self.current_scroller()  # the tab in front
                if scroller is not None:  # there is one
                    self.close_tab(scroller)  # close it
                return True  # shortcut handled, not sent to the shell
        return False  # every other key goes to the shell as normal

    def program_running(self, record):  # True when a program (not just the prompt) runs in the tab
        try:  # the terminal may already be closing
            group = os.tcgetpgrp(record["terminal"].get_pty().get_fd())  # process group that currently owns the keyboard of this tab
        except Exception:  # no terminal device any more
            return False  # nothing to protect
        return record["pid"] is not None and group != record["pid"]  # owner is not bash itself, so a program is running

    def close_tab(self, scroller):  # close one tab (x button, right-click menu or Ctrl+Shift+W)
        record = self.tabs.get(scroller)  # this tab's information
        if record is None:  # already closed
            return  # nothing to do
        if self.program_running(record):  # something is still running in it
            dialog = Gtk.MessageDialog(transient_for=self, modal=True, message_type=Gtk.MessageType.WARNING,  # warning box on top of the window
                                       buttons=Gtk.ButtonsType.OK_CANCEL,  # OK and Cancel buttons
                                       text=f"Close tab \"{record['label'].get_text()}\"?")  # question with the tab name
            dialog.format_secondary_text("A program is still running in this tab. Closing the tab stops it.")  # plain-language explanation
            response = dialog.run()  # wait for a button
            dialog.destroy()  # close the box
            if response != Gtk.ResponseType.OK:  # Cancel or closed
                return  # keep the tab
        if record["pid"] is not None:  # bash was started
            try:  # bash may already have ended
                os.kill(record["pid"], signal.SIGHUP)  # same signal a normal terminal sends when a tab is closed
            except OSError:  # process already gone
                pass  # nothing to do
        self.on_shell_exited(None, 0, scroller)  # remove the tab and its private files now

    def on_shell_exited(self, _terminal, _status, scroller):  # called when the shell in a tab ends, or by close_tab
        if scroller not in self.tabs:  # already removed (e.g. closed with the x, then bash reported its end)
            return  # nothing more to do
        record = self.tabs.pop(scroller, None)  # forget the tab
        if record:  # it was known
            for path in (record["prompt_file"], record["rc_file"]):  # its two private files
                try:  # the file may already be gone
                    os.remove(path)  # delete it
                except OSError:  # missing file
                    pass  # nothing to do
        self.notebook.remove_page(self.notebook.page_num(scroller))  # remove that tab
        if self.notebook.get_n_pages() == 0:  # if no tabs are left
            Gtk.main_quit()  # close the program


def main():  # program entry point
    window = SparkTerminalWindow(parse_launch_arguments(sys.argv[1:]))  # build the window (with what another program asked for, if anything)
    window.place_on_half()  # on the left or right half of the screen when that is switched on
    window.show_all()  # show it on screen
    try:  # make sure the private folder is removed however the program ends
        Gtk.main()  # run until the window is closed
    finally:  # always runs
        shutil.rmtree(RUNTIME_DIR, ignore_errors=True)  # delete this run's temporary startup files
    return 0  # normal exit status


if __name__ == "__main__":  # only run when started directly, not when imported
    sys.exit(main())  # start the program and pass its exit status to the system
