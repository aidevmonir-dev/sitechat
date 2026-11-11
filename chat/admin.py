"""The business's side of SiteChat: edit help articles, read conversations, follow up on contact requests."""
from django.contrib import admin

from .models import Article, Conversation, Message, Site


class ArticleInline(admin.StackedInline):
    model = Article
    extra = 1


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "notify_email", "article_count")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ArticleInline]

    @admin.display(description="Help articles")
    def article_count(self, obj):
        return obj.articles.count()


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    can_delete = False
    readonly_fields = ("role", "text", "created_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("__str__", "site", "status", "lead_name", "lead_note_short", "updated_at")
    list_filter = ("status", "site")
    search_fields = ("lead_name", "lead_email", "lead_note", "messages__text")
    list_editable = ("status",)
    readonly_fields = ("site", "page_url", "created_at", "updated_at")
    inlines = [MessageInline]

    @admin.display(description="What they need")
    def lead_note_short(self, obj):
        return obj.lead_note[:80]
