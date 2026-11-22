from google import genai
from abc import ABC, abstractmethod
from languages import LanguageProficiency
from PIL.Image import Image
import base64
import io
import random
from collections import deque
from pydantic import BaseModel, Field

RECENT_SENTENCES = 8  # how many past sentences the model is told not to repeat

class ISentenceContext(ABC):
    def __init__(self):
        super().__init__()

    # Creates a portion of the prompt needed to describe what the text is for
    @abstractmethod
    def build_prompt_context(self) -> tuple[str, Image | None]:
        pass

class ImageSentenceContext(ISentenceContext):
    """A screenshot of the window the user is focused on.

    The screenshot is always of a computer app, so left to itself the model describes
    that ("This is a computer."). The prompt steers it to the content inside the window,
    and a randomly picked focus and sentence style make each round's prompt different:
    asking a model to "be varied" works far less well than varying what it's asked.
    """

    # What to build the sentence around
    FOCUSES = [
        "one specific object, person, animal or place shown in the content",
        "a word, name or short phrase that appears in the visible text",
        "the topic or subject of what the user is reading, watching or working on",
        "something a person might do, want or feel in this situation",
        "a small, easy-to-miss detail in the content",
        "a colour, shape or number that stands out in the content",
    ]

    # What kind of sentence to write
    STYLES = [
        "a question someone might ask about it",
        "a short opinion about it",
        "a statement in the past tense",
        "a suggestion or instruction",
        "a comparison with something else",
        "a statement about the future or a plan",
        "a simple factual statement",
    ]

    def __init__(self, image: Image):
        super().__init__()
        self.image = image

    def build_prompt_context(self):
        focus = random.choice(self.FOCUSES)
        style = random.choice(self.STYLES)
        inject = (
            "inspired by this screenshot of the user's screen. "
            "Base it on the content the user is looking at: the subject of the article, video, picture, "
            "chat, document, game or code in the window. "
            "Do not write about the screen, window, app, browser, website, computer, keyboard or the "
            "screenshot itself, and never write sentences like 'This is a computer' or 'I see a screen'. "
            f"Build the sentence around {focus}, and make it {style}. "
            "Prefer a specific, concrete detail over a general summary, and use real words, names or "
            "topics from the screen when they suit the level. "
            "If the content is too sparse to use (a blank page, an empty desktop), write an everyday "
            "sentence inspired by any small detail you can find, still not about the computer"
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

class GeneratedSentence(BaseModel):
    source_lang: str = Field(description="Sentence in source language")
    target_lang: str = Field(description="Sentence in target language")

# Use gemini api to handle construction of sentences
class SentenceGenerator:
    def __init__(
        self,
        source_lang: str,
        target_lang: str,
        proficiency: LanguageProficiency,
        max_words: int,
        gemini_api_key: str
    ):
        self._source_lang = source_lang
        self._target_lang = target_lang
        self._proficiency = proficiency
        self.max_words    = max_words
        self._client      = genai.Client(api_key=gemini_api_key)
        self._recent: deque[str] = deque(maxlen=RECENT_SENTENCES)  # newest last

    def _build_prompt(self, sentence_context: ISentenceContext) -> tuple[str, Image | None]:
        inject, image = sentence_context.build_prompt_context()

        prompt = (
            f"Write one sentence in {self._target_lang} {inject}. "
            f"Use at most {self.max_words} words, suited to a learner at CEFR level {self._proficiency}. "
            f"Put that sentence in target_lang, and its natural {self._source_lang} translation in source_lang."
        )
        if self._recent:
            recent = "\n".join(f"- {s}" for s in self._recent)
            prompt += (
                "\n\nThe learner has recently practised these sentences. Don't repeat or closely "
                f"paraphrase any of them, and don't reuse their main subject:\n{recent}"
            )
        return prompt, image

    # Takes in a string that may be a sentence, may be a description of some objects on screen, may be the capture of all text on screen
    def generate(self, sentence_context: ISentenceContext) -> GeneratedSentence | None:
        try:
            prompt, image = self._build_prompt(sentence_context)

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
                input=input,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": GeneratedSentence.model_json_schema()
                }
            )

            gen = GeneratedSentence.model_validate_json(interaction.output_text)
            self._recent.append(gen.target_lang)
            return gen
        except:
            print("Failed to generate sentence")
            raise
