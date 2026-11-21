import config
from app_context import AppContext
from languages import LanguageProficiency
from sentence_context_factory import sentence_context_factory, ContextKind
from sentence_generator import SentenceGenerator

if __name__ == "__main__":
    conf = config.get_config()


    # s_ctx = sentence_context_factory(ContextKind.SCREEN_TEXT)

    # generator = SentenceGenerator(
    #         target_lang=conf.get("Language", "target", fallback="Russian"),
    #         proficiency=conf.get("Language", "proficiency", fallback=LanguageProficiency.FRESHY),
    #         max_words=conf.getint("Sentence", "max_words", fallback=10),
    #         gemini_api_key=conf["AI"]["gemini_key"]
    #     )

    # s_ctx = TranscriptSentenceContext("Cześć, jak się pan miewa?")
    # s_ctx = ObjectSentenceContext("Pickle")
    # s_ctx = ScreenTextSentenceContext(["Reloading", "25/100 HP", "Player 1", "AR15"])

    # print(generator.generate(s_ctx))

    # ctx = AppContext()
    # ctx.start()
    # ctx.join()

    config.save_config()
