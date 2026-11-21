import config
from app_context import AppContext

if __name__ == "__main__":
    conf = config.get_config()

    ctx = AppContext()
    ctx.start()
    ctx.join()

    config.save_config()
