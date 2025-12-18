import time
import pylsl

def main():
    print("[Viewer] Looking for BioSignals-Processed stream...")
    streams = pylsl.resolve_byprop("name", "BioSignals-Processed", timeout=10)
    if not streams:
        print("[Viewer] Stream not found!")
        return

    inlet = pylsl.StreamInlet(streams[0])
    info = inlet.info()
    print(f"[Viewer] Connected to {info.name()} ({info.type()})")
    print(f"[Viewer] Channel count: {info.channel_count()}")
    
    # Print channel labels
    labels = []
    ch = info.desc().child("channels").first_child()
    for _ in range(info.channel_count()):
        labels.append(ch.child_value("label"))
        ch = ch.next_sibling()
    print(f"[Viewer] Channels: {labels}")

    print("[Viewer] Streaming data...")
    count = 0
    try:
        while True:
            sample, ts = inlet.pull_sample(timeout=1.0)
            if sample:
                count += 1
                if count % 64 == 0: # Print every ~8th of a second
                    print(f"[{count:05d}] {sample}")
            else:
                print(".")
    except KeyboardInterrupt:
        print("[Viewer] Stopped.")

if __name__ == "__main__":
    main()
