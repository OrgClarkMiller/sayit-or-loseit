import config
from app_context import AppContext
from languages import LanguageProficiency
from sentence_context_factory import sentence_context_factory, ContextKind
from sentence_generator import SentenceGenerator

if __name__ == "__main__":
    conf = config.get_config()

    ctx = AppContext()
    ctx.start()
    ctx.join()

    config.save_config()
