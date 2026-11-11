import uuid

from django.db import models


class Site(models.Model):
    """A website that embeds the widget. Each site has its own help articles, look and inbox."""

    slug = models.SlugField(unique=True, help_text="Used in the embed code: data-site=\"this-value\"")
    name = models.CharField(max_length=120, help_text="Shown in the widget header, e.g. the business name")
    greeting = models.CharField(max_length=300, default="Hi! Ask me anything about our products and services.")
    accent = models.CharField(max_length=7, default="#ff7a59", help_text="Widget colour as a hex code")
    allowed_origins = models.TextField(
        blank=True,
        help_text="One origin per line, e.g. https://www.example.com . The widget only works on these sites. "
        "A single * allows any site (for demos only).",
    )
    notify_email = models.EmailField(blank=True, help_text="Where new contact requests are emailed")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name

    def origin_allowed(self, origin: str) -> bool:
        allowed = {line.strip().rstrip("/") for line in self.allowed_origins.splitlines() if line.strip()}
        return "*" in allowed or origin.rstrip("/") in allowed


class Article(models.Model):
    """A help article the assistant may answer from. This is the whole knowledge base."""

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="articles")
    title = models.CharField(max_length=200)
    body = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class Conversation(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Handled by assistant"
        NEEDS_HUMAN = "needs_human", "Waiting for a person"
        DONE = "done", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name="conversations")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OPEN)
    lead_name = models.CharField("name", max_length=120, blank=True)
    lead_email = models.EmailField("email", blank=True)
    lead_note = models.TextField("what they need", blank=True)
    page_url = models.URLField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.lead_email or f"Visitor {str(self.id)[:8]}"


class Message(models.Model):
    class Role(models.TextChoices):
        VISITOR = "user", "Visitor"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        return f"{self.role}: {self.text[:60]}"
