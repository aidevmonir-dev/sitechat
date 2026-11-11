import json
from types import SimpleNamespace

from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings

from chat.models import Conversation, Message, Site
from chat.services.bot import record_exchange
from chat.services.knowledge import search

LOCMEM = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


def text(value):
    return SimpleNamespace(type="text", text=value)


def tool_use(name, tool_input, block_id="toolu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=block_id)


def response(content, stop_reason="end_turn"):
    return SimpleNamespace(content=content, stop_reason=stop_reason)


class FakeClient:
    """Plays back scripted responses so tests never call the network."""

    def __init__(self, *responses):
        self.calls = []
        self._responses = list(responses)
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs):
        # Copy the list: the bot keeps appending to the same object between calls.
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses.pop(0)


class KnowledgeTests(TestCase):
    def setUp(self):
        self.articles = list(Site.objects.get(slug="demo").articles.all())

    def test_demo_site_is_seeded(self):
        self.assertEqual(len(self.articles), 11)

    def test_finds_the_right_article(self):
        cases = {
            "How much is shipping to Germany?": "Shipping and delivery",
            "Can I return a bike I have already ridden?": "Returns and refunds",
            "how long does the battery take to charge": "E-bike battery care and range",
            "what size frame for 180 cm": "Choosing the right frame size",
            "are you open on sunday": "Opening hours and location",
        }
        for question, title in cases.items():
            self.assertEqual(search(question, self.articles)[0].title, title, question)

    def test_no_match(self):
        self.assertEqual(search("xylophone lessons", self.articles), [])


class BotTests(TestCase):
    def setUp(self):
        self.site = Site.objects.get(slug="demo")
        self.site.notify_email = "owner@example.com"
        self.site.save()
        self.conversation = Conversation.objects.create(site=self.site)

    def test_plain_answer_uses_articles_and_history(self):
        client = FakeClient(response([text("Shipping to the EU costs 19 CHF.")]))
        reply = record_exchange(self.conversation, "How much is shipping to Germany?", client=client)
        self.assertEqual(reply.text, "Shipping to the EU costs 19 CHF.")
        self.assertFalse(reply.lead_saved)
        call = client.calls[0]
        self.assertIn("Shipping and delivery", call["system"])
        self.assertIn("Alpine Trail Bikes", call["system"])
        self.assertEqual(call["messages"], [{"role": "user", "content": "How much is shipping to Germany?"}])
        self.assertEqual([t["name"] for t in call["tools"]], ["save_contact_details", "request_human"])
        self.assertTrue(all(t["strict"] and t["input_schema"]["additionalProperties"] is False for t in call["tools"]))
        self.assertNotIn("tool_choice", call)
        self.assertEqual(list(self.conversation.messages.values_list("role", flat=True)), ["user", "assistant"])

    def test_lead_capture_runs_the_tool_loop(self):
        lead = {"name": "Anna Keller", "email": "anna@example.com", "request": "Wants a quote for 12 rental bikes."}
        first = response([text("One moment."), tool_use("save_contact_details", lead)], stop_reason="tool_use")
        client = FakeClient(first, response([text("Thanks Anna, the team will email you.")]))
        reply = record_exchange(self.conversation, "I'm Anna Keller, anna@example.com", client=client)

        self.assertTrue(reply.lead_saved)
        self.assertTrue(reply.needs_human)
        self.assertEqual(reply.text, "Thanks Anna, the team will email you.")
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.lead_email, "anna@example.com")
        self.assertEqual(self.conversation.status, Conversation.Status.NEEDS_HUMAN)

        # The second request must carry the assistant turn unchanged, then one tool_result for it.
        second = client.calls[1]["messages"]
        self.assertEqual(second[-2], {"role": "assistant", "content": first.content})
        self.assertEqual(second[-1]["content"][0]["type"], "tool_result")
        self.assertEqual(second[-1]["content"][0]["tool_use_id"], "toolu_1")

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertIn("anna@example.com", mail.outbox[0].body)

    def test_invalid_email_is_returned_to_the_model_as_an_error(self):
        bad = {"name": "Bo", "email": "not-an-email", "request": "x"}
        client = FakeClient(
            response([tool_use("save_contact_details", bad)], stop_reason="tool_use"),
            response([text("Could you check that email address?")]),
        )
        reply = record_exchange(self.conversation, "Bo, not-an-email", client=client)
        self.assertFalse(reply.lead_saved)
        result = client.calls[1]["messages"][-1]["content"][0]
        self.assertTrue(result["is_error"])
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.lead_email, "")

    def test_request_human_flags_the_conversation(self):
        client = FakeClient(
            response([tool_use("request_human", {"reason": "Wants to discuss an order."})], stop_reason="tool_use"),
            response([text("Sure. What is your name and email?")]),
        )
        reply = record_exchange(self.conversation, "I want a person", client=client)
        self.assertTrue(reply.needs_human)
        self.assertFalse(reply.lead_saved)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.lead_note, "Wants to discuss an order.")

    def test_tool_loop_is_bounded(self):
        looping = [response([tool_use("request_human", {"reason": "x"})], stop_reason="tool_use") for _ in range(10)]
        client = FakeClient(*looping)
        reply = record_exchange(self.conversation, "help", client=client)
        self.assertEqual(len(client.calls), 4)
        self.assertTrue(reply.text)

    def test_refusal(self):
        reply = record_exchange(self.conversation, "x", client=FakeClient(response([], stop_reason="refusal")))
        self.assertIn("cannot help", reply.text)

    @override_settings(ANTHROPIC_API_KEY="")
    def test_basic_mode_without_api_key(self):
        answer = record_exchange(self.conversation, "How much is shipping to Germany?")
        self.assertEqual(answer.mode, "basic")
        self.assertIn("19 CHF", answer.text)
        handover = record_exchange(self.conversation, "I want to talk to a person")
        self.assertTrue(handover.needs_human)
        lead = record_exchange(self.conversation, "Anna, anna@example.com")
        self.assertTrue(lead.lead_saved)
        self.conversation.refresh_from_db()
        self.assertEqual(self.conversation.lead_email, "anna@example.com")


@override_settings(CACHES=LOCMEM, ANTHROPIC_API_KEY="")
class ApiTests(TestCase):
    def setUp(self):
        cache.clear()

    def _send(self, body, **headers):
        return self.client.post("/api/sites/demo/messages", json.dumps(body), content_type="application/json", headers=headers)

    def test_pages(self):
        self.assertContains(self.client.get("/"), "SiteChat")
        widget = self.client.get("/widget.js")
        self.assertEqual(widget.status_code, 200)
        self.assertIn("javascript", widget["Content-Type"])
        self.assertEqual(self.client.get("/healthz").json(), {"ok": True, "ai": False})
        self.assertEqual(self.client.get("/api/sites/demo/config").json()["name"], "Alpine Trail Bikes")
        self.assertEqual(self.client.get("/api/sites/nope/config").status_code, 404)

    def test_conversation_flow_and_restore(self):
        first = self._send({"text": "How much is shipping to Germany?"}).json()
        self.assertIn("19 CHF", first["reply"])
        second = self._send({"conversation": first["conversation"], "text": "Anna, anna@example.com"}).json()
        self.assertEqual(second["conversation"], first["conversation"])
        self.assertTrue(second["lead_saved"])
        restored = self.client.get(f"/api/conversations/{first['conversation']}").json()
        self.assertEqual(len(restored["messages"]), 4)
        self.assertEqual(restored["lead"]["email"], "anna@example.com")
        self.assertEqual(restored["status"], "needs_human")

    def test_unknown_conversation_id_starts_a_new_one(self):
        reply = self._send({"conversation": "not-a-uuid", "text": "hello"}).json()
        self.assertEqual(Conversation.objects.count(), 1)
        self.assertEqual(reply["conversation"], str(Conversation.objects.get().id))

    def test_bad_requests(self):
        self.assertEqual(self._send({"text": ""}).status_code, 400)
        self.assertEqual(self._send({"text": "a" * 501}).status_code, 400)
        self.assertEqual(self.client.get("/api/sites/demo/messages").status_code, 405)
        self.assertEqual(self.client.get("/api/conversations/00000000-0000-0000-0000-000000000000").status_code, 404)

    def test_cors_allows_listed_origins_only(self):
        site = Site.objects.get(slug="demo")
        site.allowed_origins = "https://shop.example.com"
        site.save()
        ok = self._send({"text": "hello"}, origin="https://shop.example.com")
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok["Access-Control-Allow-Origin"], "https://shop.example.com")
        self.assertEqual(self._send({"text": "hello"}, origin="https://evil.example.com").status_code, 403)
        preflight = self.client.options("/api/sites/demo/messages", headers={"origin": "https://shop.example.com"})
        self.assertEqual(preflight.status_code, 204)
        self.assertIn("POST", preflight["Access-Control-Allow-Methods"])

    def test_rate_limit_and_length_limit(self):
        from django.conf import settings

        with self.settings(SITECHAT={**settings.SITECHAT, "MESSAGES_PER_IP_PER_DAY": 2}):
            codes = [self._send({"text": "hello"}).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])
        cache.clear()
        with self.settings(SITECHAT={**settings.SITECHAT, "MAX_MESSAGES_PER_CONVERSATION": 2}):
            first = self._send({"text": "hello"}).json()
            again = self._send({"conversation": first["conversation"], "text": "more"})
        self.assertEqual(again.status_code, 429)

    def test_old_conversations_are_purged(self):
        from chat.views import purge_old

        self._send({"text": "hello"})
        Conversation.objects.update(updated_at="2020-01-01T00:00:00Z")
        purge_old()
        self.assertEqual(Conversation.objects.count(), 0)
        self.assertEqual(Message.objects.count(), 0)
