# pylsl diagnostic - run in the same venv where you run filter_router
import traceback
try:
    import pylsl
    print("pylsl imported from:", pylsl.__file__)
    try:
        ver = pylsl.library_version()
    except Exception as e:
        ver = f"library_version() failed: {e}"
    print("pylsl.library_version():", ver)
    # list of useful attrs
    for attr in ("resolve_streams", "resolve_byprop", "resolve_bypred", "lsl_resolve_all"):
        print(f"hasattr(pylsl, '{attr}') ->", hasattr(pylsl, attr))
    # print the function reprs where possible
    for attr in ("resolve_streams", "resolve_byprop", "resolve_bypred", "lsl_resolve_all"):
        if hasattr(pylsl, attr):
            try:
                print(f"{attr} repr ->", getattr(pylsl, attr))
            except Exception as e:
                print(f"{attr} repr failed: {e}")

    # Try calling resolve_streams with a short timeout
    print("Calling pylsl.resolve_streams(timeout=0.2) if available...")
    try:
        if hasattr(pylsl, "resolve_streams"):
            streams = pylsl.resolve_streams()
            print("resolve_streams() returned", len(streams), "streams")
            for s in streams:
                try:
                    print("  stream name:", s.name(), "uid:", s.uid(), "type:", s.type(), "chans:", s.channel_count())
                except Exception:
                    print("  stream repr fallback:", s)
        else:
            print("resolve_streams not present; trying lsl_resolve_all()")
            if hasattr(pylsl, "lsl_resolve_all"):
                streams = pylsl.lsl_resolve_all()
                print("lsl_resolve_all() returned", len(streams), "streams")
            else:
                print("No resolve API available to list streams.")
    except Exception as e:
        print("resolve_streams call raised exception:")
        traceback.print_exc()
except Exception:
    import traceback
    print("Failed to import pylsl; traceback follows")
    traceback.print_exc()
