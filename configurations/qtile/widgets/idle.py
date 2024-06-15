import os

import libqtile.widget.base


class IdleTextBox(libqtile.widget.base.ThreadPoolText):
    def __init__(self, **config):
        libqtile.widget.base.ThreadPoolText.__init__(self, "", **config)

    def poll(self):
        handle = os.popen("xset q | grep \"Standby:\"")
        s = handle.read()
        handle.close()
        max_idle_time = int(s.strip().split()[1])
        try:
            handle = os.popen("xprintidle")
            r = handle.read()
            handle.close()
            idle_time = int(r) // 1000
        except TypeError:
            return ""
        d = max_idle_time - idle_time
        if d >= 0:
            minutes, seconds = divmod(d, 60)
            return f"{minutes:02d}:{seconds:02d}"
        else:
            return "00:00"

if __name__ == '__main__':
    w = IdleTextBox()
    print(w.poll())