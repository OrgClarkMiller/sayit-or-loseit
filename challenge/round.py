import time
from typing import Callable

from audio import phon, recording, speaking
from punishment import FailSeverity, get_fail_severity, punishment_factory
from sentence_generation.sentence_context_factory import sentence_context_factory, ContextKind
from window.overlay_window import OverlayWindow, ProcessingIndicator

from .settings import ChallengeSettings

VOICE_INPUT_MAX_ATTEMPTS = 3
SCORE_SHOW_SECONDS       = 1.5  # pause after a failed attempt so the percent can be read


class ChallengeRound:
    """One round: generate a sentence, play it, record the user, score them, punish them.

    Uses only `settings` (never the live config), so saving new settings mid-round can't
    mix languages or proficiencies.

    still_wanted: False once the round should stop early (quit, challenges turned off,
        or newer settings saved). A round takes a while (Gemini, playback, recording),
        so it's checked between steps.
    """

    def __init__(self, settings: ChallengeSettings, overlay: OverlayWindow, still_wanted: Callable[[], bool]):
        self.settings = settings
        self.overlay = overlay
        self.still_wanted = still_wanted

    def run(self):
        print('ChallengeRound.run()')

        s_ctx = sentence_context_factory(ContextKind.SCREEN_IMAGE)
        if s_ctx is None:
            return

        # 1. Generate the sentence (with the loading status shown)
        with ProcessingIndicator(self.overlay, "Generating Sentence"):
            gen = self.settings.generator.generate(s_ctx)
        if not self.still_wanted():  # the Gemini call can take a few seconds
            return

        # 2. Show it
        self.overlay.set_language_label(self.settings.target_lang, self.settings.proficiency)
        self.overlay.set_source_lang_sentence(gen.source_lang)
        self.overlay.set_target_lang_sentence(gen.target_lang)

        # 3. Phonetics of the generated sentence
        sent_phon = phon.generate(gen.target_lang, self.settings.target_lang)

        # 4. If playback is enabled, say the sentence in the language's voice
        if self.settings.playback:
            speaking.speak(sent_phon, self.settings.voice)
            if not self.still_wanted():  # don't start recording if they turned it off mid-playback
                return

        # 5. How long the sentence should take to say
        est_dur = phon.speak_duration_estimate(sent_phon, self.settings.proficiency)

        # 6. Record the user and compare their phonetics against the sentence's
        fail_severity = self._score_attempts(sent_phon, est_dur)
        if not self.still_wanted():
            return

        # 7. Punish the user if they did a bad job
        if fail_severity > FailSeverity.CLOSE:
            self._punish(fail_severity)

    def _score_attempts(self, sent_phonetics: list[str], estimated_duration: float) -> FailSeverity:
        """Up to VOICE_INPUT_MAX_ATTEMPTS tries; stops at the first good enough one.
        Returns the best attempt's severity."""
        attempts = []

        for attempt_num in range(1, VOICE_INPUT_MAX_ATTEMPTS + 1):
            if not self.still_wanted():
                return FailSeverity.PERFECT  # TODO: Any potential cleanup

            self.overlay.set_attempt(attempt_num, VOICE_INPUT_MAX_ATTEMPTS)
            self.overlay.set_recording(True, estimated_duration)
            wav = recording.record(estimated_duration)
            self.overlay.set_recording(False)

            if not self.still_wanted():  # turned off while recording: no score, no punishment
                return FailSeverity.PERFECT
            resp_phon = phon.generate(wav, self.settings.target_lang)

            percent_similar = phon.similarity(sent_phonetics, resp_phon)
            self.overlay.set_similarity_percent(percent_similar)

            fail_severity = get_fail_severity(percent_similar)
            if fail_severity < FailSeverity.MEDIUM:
                return fail_severity

            attempts.append(fail_severity)
            time.sleep(SCORE_SHOW_SECONDS)

        if not attempts:
            return FailSeverity.PERFECT
        return min(attempts)  # only the best attempt counts

    def _punish(self, fail_severity: FailSeverity):
        pun = punishment_factory(fail_severity)
        if pun is None:
            print("No punishment available")
            return

        self.overlay.set_punishment(pun.get_punishment_name(), fail_severity)
        try:
            pun.punish()
        finally:
            self.overlay.set_punishment()  # clear it even if the punishment fails
