from io import BytesIO
from datetime import timedelta
import tempfile
from django.test import TestCase,Client,override_settings
from django.contrib.auth.models import User,AnonymousUser
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from spells.models import Player,Spell,CharacterClass
from spells.profile_forms import ProfileForm


class ProfileTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner=User.objects.create_user('author',email='private@example.test')
        cls.reader=User.objects.create_user('reader')
        cls.profile=Player.objects.create(user=cls.owner,nickname='Автор',bio='О себе')
        Player.objects.create(user=cls.reader)
        cls.spell=Spell.objects.create(name='Публичное заклинание',description='Текст',duration='Миг',is_official=False,is_public=True,created_by=cls.profile)
        Spell.objects.create(name='Скрытое заклинание',description='Текст',duration='Миг',is_official=False,is_public=False,created_by=cls.profile)
        Spell.objects.create(name='Официальная работа',description='Текст',duration='Миг',is_official=True,created_by=cls.profile)
        cls.public_class=CharacterClass.objects.create(name='Публичный класс',is_official=False,is_public=True,created_by=cls.profile)
        CharacterClass.objects.create(name='Скрытый класс',is_official=False,is_public=False,created_by=cls.profile)
    def setUp(self):cache.clear()
    def url(self):return reverse('profile_page',args=[self.owner.pk])
    def test_public_profile_only_published_counts_and_no_email(self):
        response=self.client.get(self.url())
        self.assertContains(response,'Публичное заклинание');self.assertContains(response,'Официальная работа')
        self.assertNotContains(response,'Скрытое заклинание');self.assertNotContains(response,'private@example.test')
        self.assertEqual(response.context['spell_count'],2);self.assertEqual(response.context['class_count'],1)
        self.assertNotContains(response,'Редактировать профиль')
        response=self.client.get(self.url()+'?tab=classes')
        self.assertContains(response,'Публичный класс');self.assertNotContains(response,'Скрытый класс')
    def test_owner_also_gets_public_only_counts(self):
        self.client.force_login(self.owner);response=self.client.get(self.url())
        self.assertContains(response,'Редактировать профиль');self.assertNotContains(response,'Скрытое заклинание')
    def test_edit_only_current_user_and_redirect(self):
        self.client.force_login(self.reader)
        response=self.client.post(reverse('profile_edit_page'),{'nickname':'Читатель','bio':'Текст','table_role':'master','user':self.owner.pk,'id':self.profile.pk,'show_activity':'on'})
        self.assertRedirects(response,reverse('profile_page',args=[self.reader.pk]))
        self.profile.refresh_from_db();self.assertEqual(self.profile.nickname,'Автор')
        self.assertEqual(Player.objects.get(user=self.reader).nickname,'Читатель')
    def test_login_csrf_and_unsupported_methods(self):
        self.assertEqual(self.client.get(reverse('profile_edit_page')).status_code,302)
        client=Client(enforce_csrf_checks=True);client.force_login(self.owner)
        self.assertEqual(client.post(reverse('profile_edit_page'),{'nickname':'X'}).status_code,403)
        self.assertEqual(self.client.post(self.url(),{}).status_code,405)
    def test_activity_online_offline_and_hidden(self):
        Player.objects.filter(pk=self.profile.pk).update(last_seen_at=timezone.now()-timedelta(minutes=2))
        self.assertTrue(self.client.get(self.url()).context['online'])
        Player.objects.filter(pk=self.profile.pk).update(last_seen_at=timezone.now()-timedelta(minutes=8))
        self.assertFalse(self.client.get(self.url()).context['online'])
        Player.objects.filter(pk=self.profile.pk).update(show_activity=False)
        response=self.client.get(self.url());self.assertIsNone(response.context['last_seen']);self.assertContains(response,'Активность скрыта');self.assertNotContains(response,'Последняя активность:')
    def test_signed_in_activity_is_throttled_and_opt_out_stops_updates(self):
        self.client.force_login(self.owner);self.client.get(self.url())
        self.profile.refresh_from_db();stamp=self.profile.last_seen_at;self.assertIsNotNone(stamp)
        self.client.get(self.url());self.profile.refresh_from_db();self.assertEqual(self.profile.last_seen_at,stamp)
        self.profile.show_activity=False;self.profile.save(update_fields=['show_activity']);cache.clear()
        self.client.get(self.url());self.profile.refresh_from_db();self.assertEqual(self.profile.last_seen_at,stamp)
    def test_safe_bio_and_nickname(self):
        self.profile.nickname='<script>bad()</script>';self.profile.bio='<img src=x onerror=bad()>';self.profile.save()
        response=self.client.get(self.url());self.assertNotContains(response,'<script>bad()</script>');self.assertContains(response,'&lt;script&gt;')
        self.assertNotContains(response,'<img src=x')
    def test_users_without_player_and_inactive_accounts(self):
        user=User.objects.create_user('empty')
        before=Player.objects.count();response=self.client.get(reverse('profile_page',args=[user.pk]));self.assertEqual(response.status_code,200)
        self.assertEqual(Player.objects.count(),before)
        user.is_active=False;user.save();self.assertEqual(self.client.get(reverse('profile_page',args=[user.pk])).status_code,404)
    def test_pagination_and_author_links(self):
        for i in range(13):Spell.objects.create(name=f'Работа {i}',description='Текст',duration='Миг',is_official=False,is_public=True,created_by=self.profile)
        response=self.client.get(self.url());self.assertEqual(len(response.context['page_obj']),12)
        response=self.client.get(self.url()+'?page=2');self.assertEqual(len(response.context['page_obj']),3)
        response=self.client.get(reverse('spell_detail_page',args=[self.spell.pk]));self.assertContains(response,f'href="{self.url()}"')
    def test_avatar_validation_and_limits(self):
        for name,content in [('bad.svg',b'<svg xmlns="http://www.w3.org/2000/svg"></svg>'),('bad.png',b'not an image')]:
            form=ProfileForm({'nickname':'N'},files={'avatar':SimpleUploadedFile(name,content)},instance=self.profile)
            self.assertFalse(form.is_valid());self.assertIn('avatar',form.errors)
        output=BytesIO();Image.new('RGB',(2049,1)).save(output,format='PNG')
        form=ProfileForm({'nickname':'N'},files={'avatar':SimpleUploadedFile('big.png',output.getvalue())},instance=self.profile);self.assertFalse(form.is_valid());self.assertIn('avatar',form.errors)
        output=BytesIO();Image.new('RGB',(4,4)).save(output,format='PNG')
        raw=output.getvalue()
        form=ProfileForm({'nickname':'N'},files={'avatar':SimpleUploadedFile('size.png',raw+b' '*(2*1024*1024))},instance=self.profile);self.assertFalse(form.is_valid());self.assertIn('avatar',form.errors)
    def test_valid_avatar_upload_and_clear(self):
        output=BytesIO();Image.new('RGB',(32,32)).save(output,format='PNG')
        with tempfile.TemporaryDirectory() as media,override_settings(MEDIA_ROOT=media):
            self.client.force_login(self.owner)
            response=self.client.post(reverse('profile_edit_page'),{'nickname':'Автор','table_role':'both','avatar':SimpleUploadedFile('avatar.png',output.getvalue(),content_type='image/png')})
            self.assertEqual(response.status_code,302);self.profile.refresh_from_db();self.assertTrue(self.profile.avatar)
            response=self.client.post(reverse('profile_edit_page'),{'nickname':'Автор','avatar-clear':'on'})
            self.assertEqual(response.status_code,302);self.profile.refresh_from_db();self.assertFalse(self.profile.avatar)
    def test_my_profile_link_and_cancel(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get(reverse('my_profile_page')),self.url())
        response=self.client.get(reverse('profile_edit_page'));self.assertContains(response,'Отмена')
