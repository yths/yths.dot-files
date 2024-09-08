import subprocess
import collections
import functools


if __name__ == "__main__":
    ATTRIBUTES = ["Name", "Version", "Description", "Architecture", "URL", "Licenses", "Groups", "Provides", "Depends On", "Optional Deps", "Required By", "Optional For", "Conflicts With", "Replaces", "Installed Size", "Packager", "Build Date", "Install Date", "Install Reason", "Install Script", "Validated By"]

    packages = collections.defaultdict(functools.partial(collections.defaultdict, list))
    package_name = None
    attribute_name = None
    for line in subprocess.check_output(["yay", "-Qi"]).decode("utf-8").split("\n"):
        line_pieces = list(map(lambda x: x.strip(), line.split(":")))

        if line_pieces[0] == "Name":
            package_name = line_pieces[1]
        else:
            if line_pieces[0] in ATTRIBUTES:
                attribute_name = line_pieces[0]
                packages[package_name][attribute_name] += [":".join(line_pieces[1:])]
            else:
                packages[package_name][attribute_name] += [":".join(line_pieces)]

    for name in packages:
        for attribute in packages[name]:
            packages[name][attribute] = list(filter(bool, packages[name][attribute]))


    for name in packages:
        if packages[name]["Install Reason"][0] == "Explicitly installed":
            print(f"{name:>38}\t{packages[name]["Description"][0]}")