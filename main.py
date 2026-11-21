import config
from app_context import AppContext
from sentence_generator import SentenceGenerator, TranscriptSentenceContext, ObjectSentenceContext, ScreenTextSentenceContext
from languages import LanguageProficiency


if __name__ == "__main__":
    conf = config.get_config()
    generator = SentenceGenerator(
        target_lang=conf.get("Language", "target", fallback="Russian"),
        proficiency=conf.get("Language", "proficiency", fallback=LanguageProficiency.FRESHY),
        gemini_api_key=conf["AI"]["gemini_key"]
    )

    s_ctx = TranscriptSentenceContext("Cześć, jak się pan miewa?")
    s_ctx = ObjectSentenceContext("Pickle")
    s_ctx = ScreenTextSentenceContext(["Reloading", "25/100 HP", "Player 1", "AR15"])

    sentence = generator.generate(s_ctx)
    print(sentence)

    # ctx = AppContext()
    # ctx.start()
    # ctx.join()

    config.save_config()
