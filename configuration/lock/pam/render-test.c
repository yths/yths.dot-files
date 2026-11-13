#define main auth_x11_main
#include "helpers/auth_x11.c"
#undef main

#include <assert.h>
#include <X11/Xutil.h>

#define WIDTH 1280
#define HEIGHT 720

static void clear_parent(void) {
  GC background = XCreateGC(display, parent_window, 0, NULL);
  XSetForeground(display, background, xcolor_background.pixel);
  XFillRectangle(display, parent_window, background, 0, 0, WIDTH, HEIGHT);
  XFreeGC(display, background);
}

static XImage *snapshot(void) {
  XSync(display, False);
  XImage *image = XGetImage(display, parent_window, 0, 0, WIDTH, HEIGHT,
                           AllPlanes, ZPixmap);
  assert(image);
  return image;
}

static void transition(const char *old_title, const char *old_message,
                       const char *title, const char *message) {
  DisplayMessage(old_title, old_message, 0);
  DisplayMessage(title, message, 0);
  XImage *actual = snapshot();
  DestroyPerMonitorWindows(0);
  clear_parent();
  DisplayMessage(title, message, 0);
  XImage *expected = snapshot();
  int different = 0;
  for (int y = 0; y < HEIGHT; ++y)
    for (int x = 0; x < WIDTH; ++x)
      different += XGetPixel(actual, x, y) != XGetPixel(expected, x, y);
  printf("%s -> %s: %d stale pixels\n", old_message, message, different);
  XDestroyImage(actual);
  XDestroyImage(expected);
  assert(different == 0);
}

static void closed_dialog(void) {
  DisplayMessage("", "The account is locked due to 3 failed logins.", 0);
  DestroyPerMonitorWindows(0);
  XImage *image = snapshot();
  for (int y = 0; y < HEIGHT; ++y)
    for (int x = 0; x < WIDTH; ++x)
      assert(XGetPixel(image, x, y) == xcolor_background.pixel);
  XDestroyImage(image);
}

int main(int argc_local, char **argv_local) {
  argc = argc_local;
  argv = argv_local;
  display = XOpenDisplay(NULL);
  assert(display);
  int screen = DefaultScreen(display);
  XColor unused;
  assert(XAllocNamedColor(display, DefaultColormap(display, screen), "black",
                         &xcolor_background, &unused));
  assert(XAllocNamedColor(display, DefaultColormap(display, screen), "white",
                         &xcolor_foreground, &unused));
  xcolor_warning = xcolor_foreground;
  parent_window = XCreateSimpleWindow(display, RootWindow(display, screen),
                                      0, 0, WIDTH, HEIGHT, 0, 0, 0);
  main_window = XCreateSimpleWindow(display, parent_window, 0, 0, WIDTH, HEIGHT,
                                    0, 0, 0);
  XMapWindow(display, parent_window);
  clear_parent();
  // Exposed areas must be erased even when the background does not repaint.
  XSetWindowBackgroundPixmap(display, parent_window, None);
  if (argc > 1 && strcmp(argv[1], "core") == 0) {
    core_font = XLoadQueryFont(display, "fixed");
    assert(core_font);
  } else {
    xft_font = FixedXftFontOpenName(display, screen, "monospace:size=12");
    assert(xft_font);
    XRenderColor white = {65535, 65535, 65535, 65535};
    assert(XftColorAllocValue(display, DefaultVisual(display, screen),
                             DefaultColormap(display, screen), &white,
                             &xft_color_foreground));
    xft_color_warning = xft_color_foreground;
  }
  per_monitor_windows_dirty = 1;
  const char *cursor = "________________|_______________";
  transition("Password:", cursor, "Processing...", "");
  transition("Password:", cursor, "", "Wrong password.");
  transition("", "The account is locked due to 3 failed logins.",
             "Password:", cursor);
  closed_dialog();
  DestroyPerMonitorWindows(0);
  XDestroyWindow(display, parent_window);
  if (core_font)
    XFreeFont(display, core_font);
  else {
    XftColorFree(display, DefaultVisual(display, screen),
                 DefaultColormap(display, screen), &xft_color_foreground);
    XftFontClose(display, xft_font);
  }
  XCloseDisplay(display);
  return 0;
}
