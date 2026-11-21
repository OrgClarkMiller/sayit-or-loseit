from google import genai
from abc import ABC, abstractmethod
from languages import LanguageProficiency

class ISentenceContext(ABC):
    # Creates a portion of the prompt needed to describe what the text is for
    @abstractmethod
    def build_prompt_context(self) -> str:
        pass

class ObjectSentenceContext(ISentenceContext):
    def __init__(self, object_name: str):
        super().__init__()

        self.object_name = object_name

    def build_prompt_context(self):
        return f"about this object {self.object_name} and include its name in the sentence"

class TranscriptSentenceContext(ISentenceContext):
    def __init__(self, sentence: str):
        super().__init__()
        self.sentence = sentence

    def build_prompt_context(self):
        return f"from this transcript: {self.sentence} create either a reply or simply translate if a reply isn't warranted"

class ScreenTextSentenceContext(ISentenceContext):
    def __init__(self, screen_grab: list[str]):
            super().__init__()
            self.screen_grab = str(screen_grab) # Puts into format of [STR_1, STR_2, STR_3]

    def build_prompt_context(self):
        return f"from this list of on-screen text, make the sentence incorporate the most logic text seen: {self.screen_grab}"

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

    def _build_prompt(self, sentence_context: ISentenceContext):
        inject = sentence_context.build_prompt_context()

        return f"Build a sentence in {self._target_lang} {inject}. \
            Keep it to <= {self.max_words} words and to this proficiency level: {self._proficiency}. \
            Just include the final sentence, no other messages."

    # Takes in a string that may be a sentence, may be a description of some objects on screen, may be the capture of all text on screen
    def generate(self, sentence_context: ISentenceContext) -> str | None:
        try:
            prompt = self._build_prompt(sentence_context)
            interaction = self._client.interactions.create(
                model="gemini-3.5-flash-lite",
                input=prompt
            )

            return interaction.output_text
        except:
            print("Failed to generate sentence")
            raise
