import base64
import io
import os
import unittest
import wave
from unittest.mock import MagicMock, patch

import httpx

os.environ.setdefault("DB_USER", "test")
os.environ.setdefault("DB_PASSWORD", "test")

from app import audio_service


def fake_wav(seconds: float = 0.5, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\x01\x00" * int(rate * seconds))
    return buffer.getvalue()


def ok_response(wav_bytes: bytes | None = None) -> httpx.Response:
    data = base64.b64encode(wav_bytes or fake_wav()).decode()
    return httpx.Response(
        200,
        json={"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/wav", "data": data}}]}}]},
    )


GEMINI_ENV = {
    "GOOGLE_TTS_MODEL_NAME": "gemini-3.8-flash-tts",
    "GOOGLE_TTS_VOICE_NAME": "Kore",
    "GOOGLE_TTS_STYLE_PROMPT": "",
    "GOOGLE_TTS_GEMINI_LOCATION": "global",
    "GOOGLE_TTS_MAX_ATTEMPTS": "3",
}


class GeminiTTSRoutingTests(unittest.TestCase):
    def test_routes_only_non_cloud_tts_gemini_models_to_gemini_api(self):
        self.assertTrue(audio_service.uses_gemini_api_tts("gemini-3.8-flash-tts"))
        self.assertTrue(audio_service.uses_gemini_api_tts("gemini-3.8-flash-lite-tts"))
        self.assertFalse(audio_service.uses_gemini_api_tts("gemini-2.5-flash-tts"))
        self.assertFalse(audio_service.uses_gemini_api_tts("gemini-2.5-pro-tts"))
        self.assertFalse(audio_service.uses_gemini_api_tts(""))
        self.assertFalse(audio_service.uses_gemini_api_tts(None))

    def test_endpoint_uses_regional_host_outside_global(self):
        self.assertEqual(
            audio_service.gemini_tts_endpoint("gemini-3.8-flash-tts", "proj", "global"),
            "https://aiplatform.googleapis.com/v1/projects/proj/locations/global"
            "/publishers/google/models/gemini-3.8-flash-tts:generateContent",
        )
        self.assertTrue(
            audio_service.gemini_tts_endpoint("gemini-3.8-flash-tts", "proj", "eu").startswith(
                "https://aiplatform.eu.rep.googleapis.com/v1/projects/proj/locations/eu/"
            )
        )

    def test_cloud_tts_models_do_not_call_gemini_api(self):
        with patch.dict(os.environ, {"GOOGLE_TTS_MODEL_NAME": "gemini-2.5-flash-tts"}), patch.object(
            audio_service, "_synthesize_with_gemini_api"
        ) as gemini, patch("google.cloud.texttospeech.TextToSpeechClient") as client_cls:
            client_cls.return_value.synthesize_speech.return_value = MagicMock(audio_content=b"mp3")
            content, content_type = audio_service.synthesize_text("Un vers.")
        gemini.assert_not_called()
        self.assertEqual((content, content_type), (b"mp3", "audio/mpeg"))


class GeminiTTSSynthesisTests(unittest.TestCase):
    def setUp(self):
        access = patch.object(audio_service, "_gemini_api_access", return_value=("token", "proj"))
        sleep = patch.object(audio_service.time, "sleep")
        access.start()
        sleep.start()
        self.addCleanup(access.stop)
        self.addCleanup(sleep.stop)

    def test_synthesizes_mp3_with_voice_and_style(self):
        env = {**GEMINI_ENV, "GOOGLE_TTS_STYLE_PROMPT": "recitare lentă"}
        with patch.dict(os.environ, env), patch("httpx.post", return_value=ok_response()) as post:
            content, content_type = audio_service.synthesize_text("Pe lângă plopii fără soț")

        self.assertEqual(content_type, "audio/mpeg")
        self.assertTrue(content[:3] == b"ID3" or content[0] == 0xFF)
        url = post.call_args.args[0]
        self.assertIn("/models/gemini-3.8-flash-tts:generateContent", url)
        body = post.call_args.kwargs["json"]
        part = body["contents"][0]["parts"][0]
        self.assertEqual(part["text"], "Pe lângă plopii fără soț")
        self.assertEqual(part["speechMetadata"], {"style": "recitare lentă"})
        self.assertEqual(body["generationConfig"]["responseModalities"], ["AUDIO"])
        self.assertEqual(body["generationConfig"]["speechConfig"]["voiceConfig"], {"voice": "Kore"})
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_omits_style_when_not_configured(self):
        with patch.dict(os.environ, GEMINI_ENV), patch("httpx.post", return_value=ok_response()) as post:
            audio_service.synthesize_text("Un vers.")
        self.assertNotIn("speechMetadata", post.call_args.kwargs["json"]["contents"][0]["parts"][0])

    def test_long_text_is_split_and_joined_into_one_mp3(self):
        env = {**GEMINI_ENV, "GOOGLE_TTS_MAX_BYTES": "40", "GOOGLE_TTS_CHUNK_PAUSE_SECONDS": "0.5"}
        text = "Prima strofă are câteva cuvinte.\n\nA doua strofă are alte cuvinte."
        with patch.dict(os.environ, env), patch("httpx.post", return_value=ok_response(fake_wav(1.0))) as post, patch.object(
            audio_service, "encode_pcm_to_mp3", return_value=b"mp3"
        ) as encode:
            content, _ = audio_service.synthesize_text(text)

        self.assertEqual(post.call_count, 2)
        self.assertEqual(content, b"mp3")
        pcm, rate, channels = encode.call_args.args
        self.assertEqual((rate, channels), (24000, 1))
        # two 1.0 s chunks plus one 0.5 s pause, 16-bit mono
        self.assertEqual(len(pcm), int(24000 * 2.5) * 2)

    def test_retries_retryable_status_then_succeeds(self):
        responses = [httpx.Response(503, text="unavailable"), ok_response()]
        with patch.dict(os.environ, GEMINI_ENV), patch("httpx.post", side_effect=responses) as post:
            _, content_type = audio_service.synthesize_text("Un vers.")
        self.assertEqual(post.call_count, 2)
        self.assertEqual(content_type, "audio/mpeg")

    def test_retries_transport_errors_and_gives_up(self):
        with patch.dict(os.environ, GEMINI_ENV), patch(
            "httpx.post", side_effect=httpx.ConnectError("boom")
        ) as post:
            with self.assertRaisesRegex(RuntimeError, "after 3 attempts"):
                audio_service.synthesize_text("Un vers.")
        self.assertEqual(post.call_count, 3)

    def test_client_errors_fail_without_retry(self):
        with patch.dict(os.environ, GEMINI_ENV), patch(
            "httpx.post", return_value=httpx.Response(403, text="permission denied")
        ) as post:
            with self.assertRaisesRegex(RuntimeError, "403"):
                audio_service.synthesize_text("Un vers.")
        self.assertEqual(post.call_count, 1)

    def test_response_without_audio_raises(self):
        blocked = httpx.Response(200, json={"candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}]})
        with patch.dict(os.environ, GEMINI_ENV), patch("httpx.post", return_value=blocked):
            with self.assertRaisesRegex(RuntimeError, "SAFETY"):
                audio_service.synthesize_text("Un vers.")

    def test_encode_pcm_to_mp3_produces_decodable_frames(self):
        pcm = b"\x00\x10" * 24000
        mp3 = audio_service.encode_pcm_to_mp3(pcm, 24000, 1)
        self.assertGreater(len(mp3), 1000)
        self.assertEqual(mp3[0], 0xFF)


if __name__ == "__main__":
    unittest.main()
