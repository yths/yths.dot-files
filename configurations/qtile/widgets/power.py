import requests
import libqtile.widget.base


class PowerGraphQLTextBox(libqtile.widget.base.ThreadPoolText):
    def __init__(self, url='http://localhost:2106/graphql', highlight_color=['#FF0000', '#00FF00'], **config):
        libqtile.widget.base.ThreadPoolText.__init__(self, "⚫", **config)
        self.url = url
        self.highlight_color = highlight_color
        self.query = """{
  power {
    status
    charge
    charge_full
  }
}"""

    def poll(self):
        response = requests.post(url=self.url, json={"query": self.query})
        data = response.json()['data']['power']
        status = data['status']
        charge = data['charge']
        charge_full = data['charge_full']

        status_icon = ''
        if status == "Discharging":
            status_icon = '◂'
        elif status == "Charging":
            status_icon = '▸'

        if status != "Full":
          i = int(round((charge / charge_full) * 10, 0))
          if i > 1:
            return f'{i * "+ "}{(10 - i) * "- "}{status_icon}'
          else:
            return f'<span color="{self.highlight_color[0]}">{i * "+ "}{(10 - i) * "- "}</span>{status_icon}'
        else:
          return f'<span color="{self.highlight_color[1]}">⚫</span>'

if __name__ == '__main__':
    w = PowerGraphQLTextBox()
    print(w.poll())