from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from spells.models import Effect, DamageType


class EffectCatalogTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = User.objects.create_user('effect-admin', is_staff=True)
        cls.fire = DamageType.objects.create(name='Огонь')
        cls.damage = Effect.objects.create(name='Огненный ожог', description='Текст', category='DMG', duration='Одна минута', damage_type=cls.fire)
        cls.buff = Effect.objects.create(name='Огненный щит', description='Текст', category='BUFF', duration='Час')
        cls.empty = Effect.objects.create(name='Неизвестный', description='Текст')

    def setUp(self):
        self.url = reverse('catalog_list_page', args=['effects'])
        self.edit_url = reverse('catalog_edit_page', args=['effects', self.damage.pk])
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        override = self.settings(MEDIA_ROOT=self.directory.name)
        override.enable()
        self.addCleanup(override.disable)

    def image(self):
        stream=BytesIO()
        Image.new('RGB',(32,32),'orange').save(stream,format='PNG')
        return SimpleUploadedFile('effect.png',stream.getvalue(),content_type='image/png')

    def ids(self, **params):
        response=self.client.get(self.url,params)
        self.assertEqual(response.status_code,200)
        return {entry['pk'] for entry in response.context['entries']}

    def test_filters_combine_with_unicode_search_and_duration(self):
        self.assertEqual(self.ids(category='DMG'),{self.damage.pk})
        self.assertEqual(self.ids(damage_type=str(self.fire.pk)),{self.damage.pk})
        self.assertEqual(self.ids(search='огн',category='DMG',damage_type=str(self.fire.pk),duration='МИНУТ'),{self.damage.pk})
        self.assertEqual(self.ids(category='BUFF',damage_type=str(self.fire.pk)),set())

    def test_filter_missing_category_and_damage_type(self):
        self.assertEqual(self.ids(category='none'),{self.empty.pk})
        self.assertEqual(self.ids(damage_type='none'),{self.buff.pk,self.empty.pk})

    def test_invalid_filters_show_errors(self):
        for params in ({'category':'wrong'},{'damage_type':'999999'},{'damage_type':'invalid'}):
            response=self.client.get(self.url,params)
            self.assertTrue(response.context['effect_filters'].errors)
            self.assertEqual(response.context['page'].paginator.count,0)

    def test_pagination_retains_all_filters(self):
        Effect.objects.bulk_create([Effect(name=f'Огненный эффект {i}',description='Текст',category='DMG',duration='Минута',damage_type=self.fire) for i in range(25)])
        response=self.client.get(self.url,{'search':'Огн','category':'DMG','damage_type':str(self.fire.pk),'duration':'минут'})
        for key in ('search=','category=DMG','damage_type=','duration='):
            self.assertIn(key,response.context['page_query'])
        self.assertContains(response,'&amp;page=2')
        self.assertContains(response,'catalog-search-actions')

    def test_upload_replace_keep_and_clear_image(self):
        self.client.force_login(self.staff)
        data={'name':self.damage.name,'description':'Текст','category':'DMG','duration':'Минута','damage_type':self.fire.pk}
        response=self.client.post(self.edit_url,{**data,'image':self.image()})
        self.assertEqual(response.status_code,302)
        self.damage.refresh_from_db()
        first=self.damage.image.name
        self.assertTrue(self.damage.image.storage.exists(first))
        self.client.post(self.edit_url,data)
        self.damage.refresh_from_db()
        self.assertEqual(first,self.damage.image.name)
        self.client.post(self.edit_url,{**data,'image':self.image()})
        self.damage.refresh_from_db()
        self.assertNotEqual(first,self.damage.image.name)
        self.client.logout()
        for url in (self.url,reverse('catalog_detail_page',args=['effects',self.damage.pk])):
            self.assertContains(self.client.get(url),f'src="{self.damage.image.url}"')
        self.client.force_login(self.staff)
        self.client.post(self.edit_url,{**data,'image-clear':'on'})
        self.damage.refresh_from_db()
        self.assertFalse(self.damage.image)

    def test_create_accepts_image(self):
        self.client.force_login(self.staff)
        response=self.client.post(reverse('catalog_create_page',args=['effects']),{'name':'Холод','description':'Текст','image':self.image()})
        item=Effect.objects.get(name='Холод')
        self.assertRedirects(response,self.url)
        self.assertTrue(item.image)

    def test_reject_invalid_image_and_reader_upload(self):
        self.client.force_login(self.staff)
        response=self.client.post(self.edit_url,{'name':self.damage.name,'description':'Текст','image':SimpleUploadedFile('bad.png',b'bad',content_type='image/png')})
        self.assertIn('image',response.context['form'].errors)
        self.client.force_login(User.objects.create_user('effect-reader'))
        self.assertEqual(self.client.post(self.edit_url,{'name':'Холод','image':self.image()}).status_code,403)

    def test_optional_image_and_other_catalogs_unchanged(self):
        self.assertEqual(self.client.get(reverse('catalog_detail_page',args=['effects',self.empty.pk])).status_code,200)
        response=self.client.get(reverse('catalog_list_page',args=['schools']))
        self.assertIsNone(response.context['effect_filters'])

    def test_create_form_has_image_window(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse('catalog_create_page', args=['effects']))
        self.assertContains(response, 'catalog-image-picker')
        self.assertContains(response, 'name="image"')
        self.assertContains(response, 'catalog_image_upload.js')
        self.assertEqual(list(response.context['form'].fields)[:3], ['name', 'image', 'description'])

    def test_edit_form_shows_existing_image_preview(self):
        self.damage.image.save('existing.png', self.image(), save=True)
        self.client.force_login(self.staff)
        response = self.client.get(self.edit_url)
        self.assertContains(response, f'data-image-url="{self.damage.image.url}"')
