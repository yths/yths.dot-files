import os

import libqtile.widget.base


class IdleTextBox(libqtile.widget.base.ThreadPoolText):
    def __init__(self, highlight_color=['#FF0000', '#00FF00'], **config):
        libqtile.widget.base.ThreadPoolText.__init__(self, "", **config)
        self.highlight_color = highlight_color

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
        q = idle_time / max_idle_time
        if d >= 0:
            if q < 0.9:
                r = int(round(q * 10))
                e = 10 - r
                return f"{''.join(['•'] * e)}<span color='{self.highlight_color[0]}'>{''.join(['•'] * r)}</span>"
            minutes, seconds = divmod(d, 60)
            return f"󰒲 <span color='{self.highlight_color[0]}'>{minutes:02d}:{seconds:02d}</span>"
        else:
            return "00:00"

if __name__ == '__main__':
    w = IdleTextBox()
    print(w.poll())