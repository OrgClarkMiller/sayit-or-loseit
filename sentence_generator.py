from google import genai
from abc import ABC, abstractmethod
from languages import LanguageProficiency
from PIL.Image import Image
import base64
import io

class ISentenceContext(ABC):
    def __init__(self):
        super().__init__()

    # Creates a portion of the prompt needed to describe what the text is for
    @abstractmethod
    def build_prompt_context(self) -> tuple[str, Image | None]:
        pass

class ImageSentenceContext(ISentenceContext):
    def __init__(self, image: Image):
        super().__init__()
        self.image = image

    def build_prompt_context(self):
        inject = (
            "describing this image. If it shows concrete, recognizable objects (e.g. a cup, a car, a dog), "
            "pick the most prominent one and use its name in the sentence. "
            "If there are no clear objects (e.g. abstract art, plain text, a blank or cluttered UI), "
            "describe the overall scene or mood instead"
        )
        return (inject, self.image)

class TranscriptSentenceContext(ISentenceContext):
    def __init__(self, sentence: str):
        super().__init__()
        self.sentence = sentence

    def build_prompt_context(self):
        return (f"from this transcript: {self.sentence} create either a reply or simply translate if a reply isn't warranted", None)

class ScreenTextSentenceContext(ISentenceContext):
    def __init__(self, screen_grab: list[str]):
            super().__init__()
            self.screen_grab = str(screen_grab) # Puts into format of [STR_1, STR_2, STR_3]

    def build_prompt_context(self):
        return (f"from this list of on-screen text, make the sentence incorporate the most logical text seen and ignore nonsense: {self.screen_grab}", None)

def _image_to_base64_png(image: Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")

# Use gemini api to handle construction of sentences
class SentenceGenerator:
    def __init__(
        self,
        target_lang: str,
        proficiency: LanguageProficiency,
        max_words: int,
        gemini_api_key: str
    ):
        self._target_lang = target_lang
        self._proficiency = proficiency
        self.max_words    = max_words
        self._client      = genai.Client(api_key=gemini_api_key)

    def _build_prompt(self, sentence_context: ISentenceContext) -> tuple[str, Image | None]:
        inject, image = sentence_context.build_prompt_context()

        return (f"Build a sentence in {self._target_lang} {inject}. \
            Keep it to <= {self.max_words} words and to this proficiency level: {self._proficiency}. \
            Just include the final sentence, no other messages.", image)

    # Takes in a string that may be a sentence, may be a description of some objects on screen, may be the capture of all text on screen
    def generate(self, sentence_context: ISentenceContext) -> str | None:
        try:
            prompt, image = self._build_prompt(sentence_context)
            print(prompt)

            input = None

            if image is None:
                input = prompt
            else:
                input = [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image",
                        "data": _image_to_base64_png(image),
                        "mime_type": "image/png"
                    }
                ]

            interaction = self._client.interactions.create(
                model="gemini-3.5-flash-lite",
                input=input
            )

            return interaction.output_text
        except:
            print("Failed to generate sentence")
            raise
