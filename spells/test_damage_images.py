from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from spells.models import DamageType


class DamageImageTests(TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.override = self.settings(MEDIA_ROOT=self.directory.name)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.staff = User.objects.create_user('image-admin', is_staff=True)
        self.client.force_login(self.staff)
        self.item = DamageType.objects.create(name='Огонь', is_magic=True)
        self.edit_url = reverse('catalog_edit_page', args=['damage-types', self.item.pk])

    def image(self):
        stream = BytesIO()
        Image.new('RGB', (32, 32), 'red').save(stream, format='PNG')
        return SimpleUploadedFile('fire.png', stream.getvalue(), content_type='image/png')

    def test_create_upload_returns_to_list_and_shows_image_in_both_places(self):
        response = self.client.post(reverse('catalog_create_page', args=['damage-types']), {
            'name':'Холод', 'is_magic':'on', 'image':self.image(),
        })
        self.assertRedirects(response, reverse('catalog_list_page', args=['damage-types']))
        item = DamageType.objects.get(name='Холод')
        self.assertTrue(item.image.storage.exists(item.image.name))
        self.client.logout()
        for url in (reverse('catalog_list_page', args=['damage-types']), reverse('catalog_detail_page', args=['damage-types', item.pk])):
            self.assertContains(self.client.get(url), f'src="{item.image.url}"')

    def test_edit_upload_keep_and_clear(self):
        response = self.client.post(self.edit_url, {'name':'Огонь', 'image':self.image(), 'is_magic':'on'})
        self.assertEqual(response.status_code, 302)
        self.item.refresh_from_db()
        image_name = self.item.image.name
        self.client.post(self.edit_url, {'name':'Огонь', 'is_magic':'on'})
        self.item.refresh_from_db()
        self.assertEqual(self.item.image.name, image_name)
        self.client.post(self.edit_url, {'name':'Огонь', 'is_magic':'on', 'image-clear':'on'})
        self.item.refresh_from_db()
        self.assertFalse(self.item.image)

    def test_invalid_image_is_rejected(self):
        response = self.client.post(self.edit_url, {
            'name':'Огонь', 'image':SimpleUploadedFile('fake.png', b'not an image', content_type='image/png'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('image', response.context['form'].errors)
        self.item.refresh_from_db()
        self.assertFalse(self.item.image)

    def test_optional_image_and_multipart_form(self):
        response = self.client.get(self.edit_url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'name="image"')
        self.assertEqual(self.client.get(reverse('catalog_detail_page', args=['damage-types', self.item.pk])).status_code, 200)

    def test_reader_cannot_upload(self):
        reader = User.objects.create_user('image-reader')
        self.client.force_login(reader)
        self.assertEqual(self.client.post(self.edit_url, {'name':'Огонь', 'image':self.image()}).status_code, 403)
        self.item.refresh_from_db()
        self.assertFalse(self.item.image)
