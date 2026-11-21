from window import OverlayWindow
import time

def worker_main(stop_event):
    # TEMP
    wnd = OverlayWindow()
    time.sleep(20)
    wnd.close()

    """Worker loop: runs until the user clicks Quit in the tray."""
    while not stop_event.is_set():
        # TODO: poll / handle system events here
        print("checking for events...")

        # Like sleep(1), but returns immediately when stop_event is set,
        # so Quit doesn't have to wait for the sleep to finish.
        stop_event.wait(1)

    print("worker shutting down")