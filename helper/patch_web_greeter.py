import json
import os
import shutil


def patch_web_greeter(configuration):
    theme_state = configuration["state"]["theme"]
    palette = configuration["palette"][theme_state]
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    themes_dir = os.path.join(repo, "configuration", "web-greeter", "themes")
    shared_src = os.path.join(themes_dir, "_shared")

    for theme_name in sorted(os.listdir(themes_dir)):
        if theme_name.startswith("_"):
            continue
        theme_dir = os.path.join(themes_dir, theme_name)
        theme_json_path = os.path.join(theme_dir, "theme.json")
        if not os.path.isfile(theme_json_path):
            continue
        with open(theme_json_path) as fh:
            tj = json.load(fh)

        vars_ = {f"--{role}": palette[key] for role, key in tj["role_map"].items()}
        font = {**configuration["font"], **tj.get("font_overrides", {})}
        vars_["--font-family"] = f'"{font["family"]}"'
        vars_["--font-size"] = f'{font["size"]}px'

        wp_path = os.path.expanduser(configuration["wallpapers"][tj["wallpaper_key"]])
        ext = os.path.splitext(wp_path)[1] or ".png"
        link = os.path.join(theme_dir, f"wallpaper{ext}")
        if os.path.lexists(link):
            os.unlink(link)
        os.symlink(wp_path, link)
        vars_["--wallpaper-url"] = f'url("{os.path.basename(link)}")'

        with open(os.path.join(theme_dir, "theme.css"), "w") as fh:
            fh.write(":root {\n")
            for k, v in vars_.items():
                fh.write(f"    {k}: {v};\n")
            fh.write("}\n")

        shared_dst = os.path.join(theme_dir, "_shared")
        if os.path.lexists(shared_dst):
            if os.path.islink(shared_dst) or os.path.isfile(shared_dst):
                os.unlink(shared_dst)
            else:
                shutil.rmtree(shared_dst)
        shutil.copytree(shared_src, shared_dst)

    print("Patched web-greeter configuration ...")


if __name__ == "__main__":
    with open(os.path.expanduser("~/.config/config.json")) as fh:
        configuration = json.load(fh)
    patch_web_greeter(configuration)
