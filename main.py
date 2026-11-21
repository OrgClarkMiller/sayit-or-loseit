from worker import worker_main
from tray import TrayManager
import config

if __name__ == "__main__":
    conf = config.get_config()

    manager = TrayManager(worker_main)
    manager.run()

    config.save_config()
