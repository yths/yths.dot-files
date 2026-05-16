import json
import os
import pickle

if __name__ == "__main__":
    repository_folder_path = os.environ.get(
        "DOTFILES_REPOSITORY_PATH",
        os.path.join("~", "repositories", "yths.dot-files"),
    )
    repository_folder_path = os.path.expanduser(repository_folder_path)
    assets_folder_path = os.path.join(repository_folder_path, "assets")

    for theme in os.listdir(assets_folder_path):
        if theme.startswith("theme-"):
            theme_path = os.path.join(assets_folder_path, theme)
            if os.path.isdir(theme_path):
                print(theme_path)
                configuration = json.load(open(os.path.join(theme_path, "config.json")))
                print(json.dumps(configuration, indent=4))
                palette = pickle.load(open(os.path.join(theme_path, "palette.pkl"), "rb"))
                print(json.dumps(palette, indent=4))