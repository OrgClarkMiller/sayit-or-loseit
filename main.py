from worker import worker_main
from tray import TrayManager

if __name__ == "__main__":
    manager = TrayManager(worker_main)
    manager.run()
