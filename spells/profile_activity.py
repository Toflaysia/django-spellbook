from django.core.cache import cache
from django.utils import timezone
from spells.models import Player


class ProfileActivityMiddleware:
    """Record recent signed-in activity at most once per minute per worker."""
    def __init__(self,get_response):
        self.get_response=get_response

    def __call__(self,request):
        if request.user.is_authenticated and not request.path.startswith(('/static/','/media/')):
            key=f'spellbook.last_seen.{request.user.pk}'
            if cache.add(key,True,timeout=60):
                Player.objects.filter(user_id=request.user.pk,show_activity=True).update(last_seen_at=timezone.now())
        return self.get_response(request)
