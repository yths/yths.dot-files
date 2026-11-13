render-test: render-test.o $(filter-out helpers/auth_x11-auth_x11.o,$(auth_x11_OBJECTS))
	$(CC) $(CFLAGS) $(LDFLAGS) -o $@ $^ $(auth_x11_LDADD) $(LIBS)
render-test.o: $(srcdir)/render-test.c helpers/auth_x11.c
	$(CC) $(DEFS) $(DEFAULT_INCLUDES) $(INCLUDES) $(auth_x11_CPPFLAGS) $(CPPFLAGS) $(CFLAGS) -UNDEBUG -c -o $@ $<
