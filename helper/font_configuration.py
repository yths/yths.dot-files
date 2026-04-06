import tkinter

if __name__ == '__main__':
    root = tkinter.Tk()
    root.withdraw()  # Hide the root window
    for font in sorted(set(root.tk.call("font", "families"))):
        print(font)