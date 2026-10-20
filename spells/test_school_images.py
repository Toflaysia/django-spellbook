from io import BytesIO
from tempfile import TemporaryDirectory
from PIL import Image
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from spells.models import MagicSchool

class SchoolImagesTests(TestCase):
    def setUp(self):
        self.user=User.objects.create_user('school-image-admin',is_staff=True)
        self.school=MagicSchool.objects.create(name='Воплощение',description='Текст',color='#ef4050')
        folder=TemporaryDirectory();self.addCleanup(folder.cleanup)
        settings=self.settings(MEDIA_ROOT=folder.name);settings.enable();self.addCleanup(settings.disable)
        self.client.force_login(self.user)
        self.edit=reverse('catalog_edit_page',args=['schools',self.school.pk])
        self.data={'name':self.school.name,'description':'Текст','color':self.school.color}

    def image(self,name='school.png'):
        stream=BytesIO();Image.new('RGB',(32,32),'purple').save(stream,format='PNG')
        return SimpleUploadedFile(name,stream.getvalue(),content_type='image/png')

    def test_create_upload_and_form_picker(self):
        url=reverse('catalog_create_page',args=['schools'])
        response=self.client.get(url)
        self.assertContains(response,'catalog-image-picker')
        self.assertContains(response,'enctype="multipart/form-data"')
        response=self.client.post(url,{**self.data,'name':'Иллюзия','image':self.image()})
        self.assertEqual(response.status_code,302)
        school=MagicSchool.objects.get(name='Иллюзия')
        self.assertTrue(school.image.storage.exists(school.image.name))
        self.assertTrue(school.image.name.startswith('magic_schools/'))

    def test_list_detail_edit_keep_replace_and_clear(self):
        self.assertEqual(self.client.post(self.edit,{**self.data,'image':self.image()}).status_code,302)
        self.school.refresh_from_db();first=self.school.image.name
        for url in (reverse('catalog_list_page',args=['schools']),reverse('catalog_detail_page',args=['schools',self.school.pk]),self.edit):
            response=self.client.get(url)
            self.assertContains(response,self.school.image.url)
            self.assertContains(response,'--school-color:#ef4050')
        self.client.post(self.edit,self.data);self.school.refresh_from_db();self.assertEqual(self.school.image.name,first)
        self.client.post(self.edit,{**self.data,'image':self.image('new.png')});self.school.refresh_from_db();self.assertNotEqual(self.school.image.name,first)
        self.client.post(self.edit,{**self.data,'image-clear':'on'});self.school.refresh_from_db();self.assertFalse(self.school.image)
        self.assertEqual(self.client.get(reverse('catalog_detail_page',args=['schools',self.school.pk])).status_code,200)

    def test_non_admin_cannot_upload_and_anonymous_can_view(self):
        user=User.objects.create_user('school-image-reader');self.client.force_login(user)
        self.assertEqual(self.client.post(self.edit,{**self.data,'image':self.image()}).status_code,403)
        self.school.refresh_from_db();self.assertFalse(self.school.image)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('catalog_detail_page',args=['schools',self.school.pk])).status_code,200)

    def test_invalid_image_not_saved(self):
        response=self.client.post(self.edit,{**self.data,'image':SimpleUploadedFile('fake.png',b'not an image',content_type='image/png')})
        self.assertEqual(response.status_code,200)
        self.assertIn('image',response.context['form'].errors)
        self.school.refresh_from_db();self.assertFalse(self.school.image)
