# terminal4Spark

A separate terminal window for the NVIDIA DGX Spark (and other Ubuntu desktops with GNOME), with named tabs, a readable coloured prompt for each tab, and an optional switch that copies the result of every command to the clipboard.

The program is called **sparkTerminal**. It does not change GNOME Terminal, its profiles or your `~/.bashrc`: each tab starts `bash`, reads your `~/.bashrc` as usual and then adds that tab's prompt and colours.

It is part of the same family as [sparkToolset](https://github.com/kodati3shrini3/sparkToolset) (start and stop launchers for vLLM, Kubernetes, Grafana and Docker on the DGX Spark), but it is installed on its own.

## What you can do

| Feature | How |
|---|---|
| Named tabs | "+" or Ctrl+Shift+T asks for a name. Double-click the tab or press Ctrl+Shift+R to rename. The x button or Ctrl+Shift+W closes it (it asks first if a program is still running). |
| Settings per tab | Right-click a tab and choose "Tab settings...". You can change the prompt style (7 choices, with or without the user@system prefix), the theme (dark, light or auto), the text colour (green, white, amber or cyan), the prompt colour and the font size (medium or large). A live preview shows the result before you apply it. |
| Readable prompt | The prompt colour is "Automatic" by default: bold and chosen to stand out on the theme and text colour you picked. You can also choose a fixed colour. |
| Readable file lists | Each theme has its own 16-colour palette, so blue directory names in `ls --color` stay visible on a dark background. |
| Defaults for new tabs | The gear button sets the starting settings of every new tab. They are saved in `~/.config/sparkTerminal/settings.conf`. Open tabs keep their own settings. |
| Copy the result of each command | One switch for the whole program, in the gear dialog (see below). |
| Half-screen window | One switch for the whole program, in the gear dialog: "Open the window on half of the screen", with "Left half" or "Right half". The window takes that half of the monitor where your mouse pointer is, when the program starts and at once when you press Apply. It is not offered in the settings of a single tab. |
| Several windows | Each click on the icon opens a new window. All windows share one icon in the dock, and you close them yourself. Right-click the icon and choose "New Window" for another one. If you installed an earlier version, run the installer again to get this. |

## Copy the result of each command

Ticking "Copy the result of each command to the clipboard (all tabs)" in the gear dialog and pressing Apply turns this on in all open tabs at once. It is off by default and is not offered in the settings of a single tab. The setting is saved.

Example: run `ls -l`, switch to a text editor and paste. You get the file list without selecting anything on the screen.

| Detail | Behaviour |
|---|---|
| What is copied | Only the output of the command you just ran. The prompt line is not included. |
| Each new command | Replaces the previous clipboard content. |
| A command with no output | Leaves the clipboard alone. |
| A short notice | "copied N line(s)" appears in the window title for 3 seconds. |
| Size | The history keeps 100,000 lines per tab. One result is limited to 1,000,000 bytes. A longer result is cut at a line end and keeps its beginning. |
| Start and exit | The clipboard is not cleared when the program starts, closes or when you untick the switch. It changes only when the next command produces output. |

Good to know: the result of a command can contain secrets such as tokens or passwords. It stays on the clipboard after you close the program, and some desktops keep a clipboard history. Switch the feature off when you work with sensitive output.

## Install

You need `python3`, `python3-gi`, `gir1.2-gtk-3.0` and `gir1.2-vte-2.91`. The installer checks them and tells you what is missing. It never installs packages and never uses `sudo`.

    git clone https://github.com/kodati3shrini3/terminal4Spark.git
    cd terminal4Spark
    ./installSparkTerminal.sh --dry-run    # shows what would be done, changes nothing
    ./installSparkTerminal.sh              # asks for a folder, copies the program, creates a Desktop icon and a menu entry

The suggested folder is `~/.local/share`, which puts the program in `~/.local/share/sparkTerminal`. An older install in the same place is kept as a backup under `~/.local/state/sparkTerminal`.

To try it without installing, run `python3 sparkTerminal.py` from the cloned folder.

## Remove

    ./uninstallSparkTerminal.sh            # moves the installed files and both launchers to the Trash (settings are kept)

The uninstaller is also copied into the installed folder. Your settings in `~/.config/sparkTerminal` are not touched.

## Tested on

NVIDIA DGX Spark (GB10, ARM64), DGX OS (Ubuntu 24.04), GNOME, VTE 0.76. The graphical parts were tested by hand; there are no automated tests for them.

## Known limitations

| Limitation | Detail |
|---|---|
| Very long output | If one command prints more than 100,000 lines, the copied text may begin with blank lines where the oldest lines scrolled out of the history. |
| Shell | Each tab runs `bash`. Other shells are not supported. |
| Half-screen window | Tested only on X11 with one monitor. On Wayland a program usually cannot place its own window, so the setting may have no effect there. With several monitors the half is taken on the one under the mouse pointer (not tested). |
| A rare crash | Once during testing the program ended with "Segmentation fault". It could not be reproduced in three runs. If it happens to you, start the program with `python3 -X faulthandler ./sparkTerminal.py` and report the output in an issue. |

## License

MIT License, copyright Shrinivas Kodati. See the `LICENSE` file. The software is provided as it is, without warranty.
