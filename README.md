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
| Run commands from other programs | One switch for the whole program, in the gear dialog under "Default terminal", off by default. While your OS terminal is the default it is shown ticked and greyed out, because the OS terminal runs commands from other programs; sparkTerminal's own saved value is off. Once sparkTerminal is the default, the switch starts off and you can tick it. When it is ticked, a program that asks the terminal to run a command or to open in a folder gets a tab that does it (see "Run commands from other programs" below). |
| Default terminal | In the gear dialog, "Set sparkTerminal as default" (it asks first) sets sparkTerminal as the terminal that programs and the Ctrl+Alt+T shortcut open, for your user only. "Restore OS default" puts the old value back (on a normal setup that is the system's own default terminal) and resets sparkTerminal's own "Run commands from other programs" to off. See "Make it the default terminal" below. |
| Several windows | Each click on the icon opens a new window. All windows share one icon in the dock, and you close them yourself. Right-click the icon and choose "New Window" for another one. If you installed an earlier version, run the installer again to get this. |

## Copy the result of each command

Ticking "Copy command results (all tabs)" in the gear dialog and pressing Apply turns this on in all open tabs at once. It is off by default and is not offered in the settings of a single tab. The setting is saved.

Example: run `ls -l`, switch to a text editor and paste. You get the file list without selecting anything on the screen.

| Detail | Behaviour |
|---|---|
| What is copied | Only the output of the command you just ran. The prompt line is not included. |
| Each new command | Replaces the previous clipboard content. |
| Start and end time | Two options under the switch, both off by default. While the switch is unticked they are shown unticked and greyed out, and your choice comes back when you tick it again. "Add start time (first line)" puts a line such as `Started: 2026-11-14 18:21:05` before the result. "Add end time (last line)" puts a line such as `Finished: 2026-11-14 18:21:09` after it. The times are your computer's local time, with seconds, and are part of the copied text only, not shown in the terminal. |
| A command with no output | Leaves the clipboard alone. |
| A short notice | "copied N line(s)" appears in the window title for 3 seconds. |
| Size | The history keeps 100,000 lines per tab. One result is limited to 1,000,000 bytes. A longer result is cut at a line end and keeps its beginning. |
| Start and exit | The clipboard is not cleared when the program starts, closes or when you untick the switch. It changes only when the next command produces output. |

Good to know: the result of a command can contain secrets such as tokens or passwords. It stays on the clipboard after you close the program, and some desktops keep a clipboard history. Switch the feature off when you work with sensitive output.

## Run commands from other programs

Some programs start a terminal and tell it what to do, for example "run `htop` in a terminal" or "open a terminal in this folder". This is off by default. Tick "Run commands from other programs" in the gear dialog (under "Default terminal") to allow it. While your OS terminal is the default, the box is shown ticked and greyed out (the OS terminal runs commands from other programs); it can be changed once sparkTerminal is the default, and it always starts off then. The choice is saved with Apply like the other settings, or at once if you tick the box in the question that appears when you press "Set sparkTerminal as default".

| Detail | Behaviour |
|---|---|
| What is accepted | `-e command arguments`, `-x command arguments`, `-- command arguments` and `--working-directory FOLDER` (also written `--working-directory=FOLDER`). A single text with spaces after `-e` is split the way a shell would. Other options are ignored. |
| What you see | A tab named after the command, a first line saying which command runs, the command's own output and a last line saying how it ended. The tab then stays open with a normal prompt. |
| Folder only | A tab that starts in that folder. If the folder does not exist, the tab starts in your home folder and the title bar says so. |
| When the switch is off | The program opens as usual (an empty tab in your home folder), and the title bar says for a few seconds that another program asked for a command or a folder. |
| Several windows | Each start of the program is its own window. The command runs in the first tab of that window. |
| Good to know | Any program that can start sparkTerminal can ask it to run any command with your rights, as with any other terminal. Tick the switch only if you want that. |

## Make it the default terminal

This is optional and never happens by itself. Open the gear dialog and press "Set sparkTerminal as default". It asks first, then changes one setting of your user account (`org.gnome.desktop.default-applications.terminal`, key `exec`). The old value is saved in `~/.config/sparkTerminal/previousDefaultTerminal.conf`, and "Restore OS default" puts it back. It also resets sparkTerminal's own "Run commands from other programs" to off; the box is then shown ticked and greyed out, like the OS terminal's behaviour.

| Detail | Behaviour |
|---|---|
| What is changed | Only that one setting of your user, and sparkTerminal's own note of the old value. GNOME Terminal, `/etc`, `/usr`, `~/.bashrc` and other launchers are not touched, and no `sudo` is used. |
| Takes effect | At once, and not as part of Apply or Cancel. |
| Which programs follow it | Programs that read this GNOME setting. Whether the Ctrl+Alt+T shortcut does is checked by trying it. The system-wide `x-terminal-emulator` list is not changed, so programs that use that list still open the old terminal. |
| Commands to run | If "Run commands from other programs" is ticked, a program that asks the terminal to run a command (`-e`) or to open in a folder gets a tab that does it. If it is not ticked, such a program gets an empty sparkTerminal and the title bar says why. |
| Before you remove sparkTerminal | Press "Restore OS default" first. Otherwise the setting points to a program that no longer exists. |

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
| Default terminal | Only the per-user GNOME setting is changed. The system-wide `x-terminal-emulator` list is not. |
| A rare crash | Once during testing the program ended with "Segmentation fault". It could not be reproduced in three runs. If it happens to you, start the program with `python3 -X faulthandler ./sparkTerminal.py` and report the output in an issue. |

## License

MIT License, copyright Shrinivas Kodati. See the `LICENSE` file. The software is provided as it is, without warranty.
