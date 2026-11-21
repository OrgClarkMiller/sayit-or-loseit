import config
from app_context import AppContext

if __name__ == "__main__":
    conf = config.get_config()

    ctx = AppContext()
    ctx.start() # Start all threads managed by context
    ctx.join()  # Join all threads managed by context (finish all jobs and close all windows)

    config.save_config()
