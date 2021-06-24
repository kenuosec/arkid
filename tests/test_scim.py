# pylint: disable=too-many-lines
'''
test scim provider endpoint
'''
import json
from unittest import mock, skip
from urllib.parse import urljoin

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from django_scim import constants
from django_scim.schemas import ALL as ALL_SCHEMAS
from django_scim.utils import (
    get_base_scim_location_getter,
    get_group_adapter,
    get_service_provider_config_model,
    get_user_adapter,
    get_group_model,
)

from tenant.models import Tenant


def setUpModule():    # pylint: disable=invalid-name, missing-function-docstring
    # delete admin user
    get_user_model().objects.all().delete()


class LoginMixin:
    '''
    login before making request
    '''
    def setUp(self):    # pylint: disable=invalid-name, missing-function-docstring
        self.user = get_user_model().objects.create(
            first_name='Super',
            last_name='Admin',
            username='superuser',
            password=make_password('password1'),
        )

        self.client = Client()
        self.assertTrue(self.client.login(username='superuser', password='password1'))


class SearchTestCase(LoginMixin, TestCase):
    '''
    test search
    '''
    maxDiff = None
    request = RequestFactory().get('/fake/request')

    def test_search_without_schema(self):
        """
        Test POST /Users/.search/?filter=userName eq ""
        """
        url = reverse('scim:users-search')
        body = json.dumps({
            'schemas': [constants.SchemaURI.NOT_SERACH_REQUEST],
        })
        resp = self.client.post(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 400, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = {
            'detail': u'Invalid schema uri. Must be SearchRequest.',
            'schemas': [constants.SchemaURI.ERROR],
            'status': 400
        }
        self.assertEqual(expected, result)

    def test_search_for_user_with_username_filter_without_value(self):    # pylint: disable=invalid-name
        """
        Test POST /Users/.search/?filter=userName eq ""
        """
        get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )

        url = reverse('scim:users-search')
        body = json.dumps({
            'schemas': [constants.SchemaURI.SERACH_REQUEST],
            'filter': 'userName eq ""',
        })
        resp = self.client.post(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        location = urljoin(get_base_scim_location_getter()(), '/scim/v2/')
        location = urljoin(location, 'Users/.search')
        self.assertEqual(resp['Location'], location)

        result = json.loads(resp.content.decode())
        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 0,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [],
        }
        self.assertEqual(expected, result)

    def test_search_for_user_with_username_filter_with_value(self):    # pylint: disable=invalid-name
        """
        Test POST /Users/.search/?filter=userName eq "rford"
        """
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )
        ford = get_user_adapter()(ford, self.request)

        url = reverse('scim:users-search')
        body = json.dumps({
            'schemas': [constants.SchemaURI.SERACH_REQUEST],
            'filter': 'userName eq "rford"',
        })
        resp = self.client.post(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        location = urljoin(get_base_scim_location_getter()(), '/scim/v2/')
        location = urljoin(location, 'Users/.search')
        self.assertEqual(resp['Location'], location)

        result = json.loads(resp.content.decode())
        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 1,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [
                ford.to_dict(),
            ]
        }
        self.assertEqual(expected, result)


class UserTestCase(LoginMixin, TestCase):
    '''
    test user
    '''
    maxDiff = None
    request = RequestFactory().get('/fake/request')

    def test_get_user_with_username_filter(self):    # pylint: disable=invalid-name
        """
        Test GET /Users?filter=userName eq ""
        """
        url = reverse('scim:users') + '?filter=userName eq ""'
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 0,
            "itemsPerPage": 50,
            "startIndex": 1,
            "Resources": [],
        }
        self.assertEqual(expected, result)

    def test_get_user_by_id(self):
        """
        Test GET /Users/{id}
        """
        # create user
        tenant = Tenant.objects.create(name='first tenant')
        behavior = get_group_model().objects.create(name='Behavior Group', tenant=tenant)

        ford = get_user_model().objects.create(first_name='Robert', last_name='Ford')
        ford.scim_groups.add(behavior)

        ford = get_user_adapter()(ford, self.request)

        url = reverse('scim:users', kwargs={'uuid': ford.id})
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        self.assertEqual(resp['Location'], ford.location)

        result = json.loads(resp.content.decode())
        expected = ford.to_dict()
        self.assertEqual(expected, result)

    @skip('user list result out of order')
    def test_get_all_users(self):
        """
        Test GET /Users
        """
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )
        ford = get_user_adapter()(ford, self.request)
        abernathy = get_user_model().objects.create(
            first_name='Dolores',
            last_name='Abernathy',
            username='dabernathy',
        )
        abernathy = get_user_adapter()(abernathy, self.request)

        url = reverse('scim:users')
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 3,
            "itemsPerPage": 50,
            "startIndex": 1,
            'Resources': [
                get_user_adapter()(self.user, self.request).to_dict(),
                ford.to_dict(),
                abernathy.to_dict(),
            ],
        }
        self.assertEqual(expected, result)

    @skip('user list result out of order')
    @mock.patch('django_scim.views.UsersView.get_extra_filter_kwargs')
    def test_get_all_users_with_extra_model_filter_kwargs(self, func):    # pylint: disable=invalid-name
        """
        Test GET /Users with extra model filters.
        """
        # define kwargs returned by a call to get_extra_filter_kwargs
        func.return_value = {'is_active': True}

        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )
        ford = get_user_adapter()(ford, self.request)
        get_user_model().objects.create(
            first_name='Dolores',
            last_name='Abernathy',
            username='dabernathy',
            is_active=False,
        )

        url = reverse('scim:users')
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        result = json.loads(resp.content.decode())

        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 2,
            "itemsPerPage": 50,
            "startIndex": 1,
            'Resources': [
                get_user_adapter()(self.user, self.request).to_dict(),
                ford.to_dict(),
            ],
        }
        self.assertEqual(expected, result)

    @mock.patch('django_scim.views.UsersView.get_extra_exclude_kwargs')
    def test_get_all_users_with_extra_model_exclude_kwargs(self, func):    # pylint: disable=invalid-name
        """
        Test GET /Users with extra model exclude filters.
        """
        # define kwargs returned by a call to get_extra_exclude_kwargs
        func.return_value = {'is_active': True}

        get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )
        abernathy = get_user_model().objects.create(
            first_name='Dolores',
            last_name='Abernathy',
            username='dabernathy',
            is_active=False,
        )
        abernathy = get_user_adapter()(abernathy, self.request)

        url = reverse('scim:users')
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        result = json.loads(resp.content.decode())

        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 1,
            "itemsPerPage": 50,
            "startIndex": 1,
            'Resources': [
                abernathy.to_dict(),
            ],
        }
        self.assertEqual(expected, result)

    def test_post(self):    # pylint: disable=missing-function-docstring
        url = reverse('scim:users')
        data = {
            'schemas': [
                constants.SchemaURI.USER,
                constants.SchemaURI.ENTERPRISE_USER,
            ],
            'userName': 'ehughes',
            'name': {
                'givenName': 'Elsie',
                'familyName': 'Hughes',
            },
            'password': 'notTooSecret',
            'emails': [{
                'value': 'ehughes@westworld.com',
                'primary': True
            }],
            'externalId': 'Shannon.Woodward',
        }
        body = json.dumps(data)
        resp = self.client.post(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 201, resp.content.decode())

        # test object
        elsie = get_user_model().objects.get(username='ehughes')
        self.assertEqual(elsie.first_name, 'Elsie')
        self.assertEqual(elsie.last_name, 'Hughes')
        self.assertEqual(elsie.email, 'ehughes@westworld.com')

        # self.assertEqual(elsie.scim_id, str(elsie.id))
        self.assertEqual(elsie.scim_username, 'ehughes')
        self.assertEqual(elsie.scim_external_id, 'Shannon.Woodward')

        # test response
        elsie = get_user_adapter()(elsie, self.request)
        result = json.loads(resp.content.decode())
        self.assertEqual(result, elsie.to_dict())
        self.assertEqual(resp['Location'], elsie.location)

    def test_post_invalid_active_value(self):    # pylint: disable=missing-function-docstring
        url = reverse('scim:users')
        data = {
            'schemas': [
                constants.SchemaURI.USER,
                constants.SchemaURI.ENTERPRISE_USER,
            ],
            'userName': 'ehughes',
            'active': 'False',
            'name': {
                'givenName': 'Elsie',
                'familyName': 'Hughes',
            },
            'password': 'notTooSecret',
            'emails': [{
                'value': 'ehughes@westworld.com',
                'primary': True
            }],
            'externalId': 'Shannon.Woodward',
        }
        body = json.dumps(data)
        resp = self.client.post(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 400, resp.content.decode())
        result = json.loads(resp.content.decode())
        self.assertEqual(result['detail'], '"active" should be of type "bool". Got type "str"')

    def test_post_duplicate(self):    # pylint: disable=missing-function-docstring
        get_user_model().objects.create(username='ehughes')

        url = reverse('scim:users')
        data = {
            'schemas': [constants.SchemaURI.USER],
            'userName': 'ehughes',
            'name': {
                'givenName': 'Elsie',
                'familyName': 'Hughes',
            },
            'password': 'notTooSecret',
            'emails': [{
                'value': 'ehughes@westworld.com',
                'primary': True
            }],
        }
        body = json.dumps(data)
        resp = self.client.post(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 409, resp.content.decode())

    def test_put(self):    # pylint: disable=missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        data = get_user_adapter()(ford, self.request).to_dict()
        data['userName'] = 'updatedrford'
        data['name'] = {'givenName': 'Bobby'}
        data['emails'] = [{'value': 'rford@westworld.com', 'primary': True}]
        body = json.dumps(data)
        resp = self.client.put(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        # test object
        ford.refresh_from_db()
        self.assertEqual(ford.first_name, 'Bobby')
        self.assertEqual(ford.last_name, '')
        self.assertEqual(ford.username, 'updatedrford')
        self.assertEqual(ford.email, 'rford@westworld.com')

        # test response
        result = json.loads(resp.content.decode())
        ford = get_user_adapter()(ford, self.request)
        self.assertEqual(result, ford.to_dict())

    def test_put_invalid_active_value(self):    # pylint: disable=missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        data = get_user_adapter()(ford, self.request).to_dict()
        data['active'] = 'False'
        body = json.dumps(data)
        resp = self.client.put(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 400, resp.content.decode())
        result = json.loads(resp.content.decode())
        self.assertEqual(result['detail'], '"active" should be of type "bool". Got type "str"')

    def test_put_empty_body(self):    # pylint: disable=missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        data = '''    '''
        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        resp = self.client.patch(url, data=data, content_type='application/scim+json')
        self.assertEqual(resp.status_code, 400, resp.content.decode())

    def test_patch_replace(self):    # pylint: disable=missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )
        data = {
            'schemas': [constants.SchemaURI.PATCH_OP],
            'Operations': [
                {
                    'op': 'replace',
                    'value': {
                        'familyName': 'Updated Ford'
                    }
                },
            ]
        }
        data = json.dumps(data)

        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        ford.refresh_from_db()
        self.assertEqual(ford.last_name, 'Updated Ford')

    def test_patch_replace_invalid_active_value(self):    # pylint: disable=invalid-name, missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )
        data = {
            'schemas': [constants.SchemaURI.PATCH_OP],
            'Operations': [
                {
                    'op': 'replace',
                    'path': 'active',
                    'value': 'False',
                },
            ]
        }
        data = json.dumps(data)

        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 400, resp.content.decode())
        result = json.loads(resp.content.decode())
        self.assertEqual(result['detail'], '"active" should be of type "bool". Got type "str"')

    def test_patch_replace_with_complex_path_1(self):    # pylint: disable=invalid-name, missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        data = '''
        {
          "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
          ],
          "Operations": [
            {
              "op": "Replace",
              "path": "familyName",
              "value": "updatedFamilyName"
            }
          ]
        }
        '''
        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

    def test_patch_replace_with_complex_path_2(self):    # pylint: disable=invalid-name, missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        data = '''
        {
          "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
          ],
          "Operations": [
            {
              "op": "Replace",
              "path": "name.familyName",
              "value": "updatedFamilyName"
            }
          ]
        }
        '''
        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

    @skip('No support for complex PATCH paths yet')
    def test_patch_replace_with_complex_path_3(self):    # pylint: disable=invalid-name, missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        data = '''
        {
          "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
          ],
          "Operations": [
            {
              "op": "Replace",
              "path": "addresses[type eq \\"work\\"]",
              "value": "Zone 3"
            }
          ]
        }
        '''
        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        with mock.patch('django_scim.adapters.SCIMUser.handle_replace') as handle_replace:
            self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
            handle_replace.assert_called_with()

    @skip('No support for complex PATCH paths yet')
    def test_patch_replace_with_complex_path_4(self):    # pylint: disable=invalid-name, missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        data = '''
        {
          "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
          ],
          "Operations": [
            {
              "op": "Replace",
              "path": "addresses[type eq \\"work\\"].locality",
              "value": "Zone 3"
            }
          ]
        }
        '''
        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        with mock.patch('django_scim.adapters.SCIMUser.handle_replace') as handle_replace:
            self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
            handle_replace.assert_called_with()

    @skip('No support for complex PATCH paths yet')
    def test_patch_replace_with_complex_path_real_example_1(self):    # pylint: disable=invalid-name, missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        data = '''
        {
          "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
          ],
          "Operations": [
            {
              "op": "Add",
              "path": "addresses[type eq \\"work\\"].country",
              "value": "United States"
            },
            {
              "op": "Add",
              "path": "addresses[type eq \\"work\\"].locality",
              "value": "West"
            },
            {
              "op": "Add",
              "path": "addresses[type eq \\"work\\"].postalCode",
              "value": "12345"
            },
            {
              "op": "Add",
              "path": "addresses[type eq \\"work\\"].formatted",
              "value": "Ext. 127"
            },
            {
              "op": "Add",
              "path": "addresses[type eq \\"work\\"].region",
              "value": "WW"
            },
            {
              "op": "Add",
              "path": "addresses[type eq \\"work\\"].streetAddress",
              "value": "123 Wester Lane, Suite 456"
            },
            {
              "op": "Add",
              "path": "phoneNumbers[type eq \\"fax\\"].value",
              "value": "+1 234-456-7890"
            },
            {
              "op": "Add",
              "path": "phoneNumbers[type eq \\"mobile\\"].value",
              "value": "+1 234-456-7890"
            },
            {
              "op": "Add",
              "path": "phoneNumbers[type eq \\"work\\"].value",
              "value": "+1 234-456-7890"
            },
            {
              "op": "Add",
              "path": "urn:ietf:params:scim:schemas:extension:enterprise:2.0:User:department",
              "value": "Administrative"
            }
          ]
        }
        '''
        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        with mock.patch('django_scim.adapters.SCIMUser.handle_add') as handle_add:
            self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
            handle_add.assert_called_with()

    @skip('No support for complex PATCH paths yet')
    def test_patch_replace_with_complex_path_real_example_2(self):    # pylint: disable=invalid-name, missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        data = '''
        {
          "schemas": [
            "urn:ietf:params:scim:api:messages:2.0:PatchOp"
          ],
          "Operations": [
            {
              "op": "Replace",
              "path": "active",
              "value": "False"
            },
            {
              "op": "Replace",
              "path": "emails[type eq \\"work\\"].value",
              "value": "Test.User@ww.com"
            },
            {
              "op": "Replace",
              "path": "userName",
              "value": "8a6bcff856484461976bb4f581453c93Test.User@ww.com"
            }
          ]
        }
        '''
        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        expected_args = [
            (('active', None, None), 'False', {
                'op': 'Replace',
                'path': 'active',
                'value': 'False'
            }),
            (('emails', 'value', None), 'Test.User@ww.com', {
                'op': 'Replace',
                'path': 'emails[type eq "work"].value',
                'value': 'Test.User@ww.com'
            }),
            (('userName', None, None), '8a6bcff856484461976bb4f581453c93Test.User@ww.com', {
                'op': 'Replace',
                'path': 'userName',
                'value': '8a6bcff856484461976bb4f581453c93Test.User@ww.com'
            }),
        ]
        with mock.patch('django_scim.adapters.SCIMUser.handle_replace') as handle_replace:
            self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
            for call, expected_args in zip(handle_replace.mock_calls, expected_args):
                self.assertEqual(call.args, expected_args)

    def test_patch_atomic(self):    # pylint: disable=missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )
        data = {
            'schemas': [constants.SchemaURI.PATCH_OP],
            'Operations': [
                {
                    'op': 'replace',
                    'value': {
                        'familyName': 'Updated Ford'
                    }
                },
        # Adding a non-existent user should cause this PATCH to fail
                {
                    'op': 'replace',
                    'value': {
                        'emails': [{
                            'value': 'not a valid email'
                        }]
                    }
                }
            ]
        }
        data = json.dumps(data)

        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 400, resp.content.decode())

        ford.refresh_from_db()
        self.assertEqual(ford.last_name, 'Ford')
        self.assertEqual(ford.email, 'rford@ww.com')

    def test_delete(self):    # pylint: disable=missing-function-docstring
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
            email='rford@ww.com',
        )

        url = reverse('scim:users', kwargs={'uuid': ford.scim_id})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204, resp.content.decode())

        ford = get_user_model().objects.filter(scim_id=ford.scim_id).first()
        self.assertIsNone(ford)


class GroupTestCase(LoginMixin, TestCase):
    '''
    test group
    '''
    maxDiff = None
    request = RequestFactory().get('/fake/request')

    def test_get_group_by_id(self):
        """
        Test GET /Group/{id}
        """
        tenant = Tenant.objects.create(name='first tenant')
        behavior = get_group_model().objects.create(name='Behavior Group', tenant=tenant)

        ford = get_user_model().objects.create(first_name='Robert', last_name='Ford')
        ford.scim_groups.add(behavior)

        behavior = get_group_adapter()(behavior, self.request)

        url = reverse('scim:groups', kwargs={'uuid': behavior.id})
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        self.assertEqual(resp['Location'], behavior.location)

        result = json.loads(resp.content.decode())
        expected = behavior.to_dict()
        self.assertEqual(expected, result)

    def test_get_all_groups(self):
        """
        Test GET /Groups
        """
        behavior = get_group_model().objects.create(name='Behavior Group', )
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )
        ford.scim_groups.add(behavior)
        behavior = get_group_adapter()(behavior, self.request)

        security = get_group_model().objects.create(name='Security Group', )
        abernathy = get_user_model().objects.create(
            first_name='Dolores',
            last_name='Abernathy',
            username='dabernathy',
        )
        abernathy.scim_groups.add(security)
        security = get_group_adapter()(security, self.request)

        url = reverse('scim:groups')
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 2,
            "itemsPerPage": 50,
            "startIndex": 1,
            'Resources': [
                behavior.to_dict(),
                security.to_dict(),
            ],
        }
        self.assertEqual(expected, result)

    @mock.patch('django_scim.views.GroupsView.get_extra_filter_kwargs')
    def test_get_all_groups_with_extra_model_filter_kwargs(self, func):    # pylint: disable=invalid-name
        """
        Test GET /Users with extra model filters.
        """
        # define kwargs returned by a call to get_extra_filter_kwargs
        func.return_value = {'name': 'Behavior Group'}

        behavior = get_group_model().objects.create(name='Behavior Group', )
        behavior = get_group_adapter()(behavior, self.request)

        get_group_model().objects.create(name='Security Group', )

        url = reverse('scim:groups')
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 1,
            "itemsPerPage": 50,
            "startIndex": 1,
            'Resources': [
                behavior.to_dict(),
            ],
        }
        self.assertEqual(expected, result)

    @mock.patch('django_scim.views.GroupsView.get_extra_exclude_kwargs')
    def test_get_all_groups_with_extra_model_exclude_kwargs(self, func):    # pylint: disable=invalid-name
        """
        Test GET /Users with extra model exclude filters.
        """
        # define kwargs returned by a call to get_extra_exclude_kwargs
        func.return_value = {'name': 'Behavior Group'}

        get_group_model().objects.create(name='Behavior Group', )

        security = get_group_model().objects.create(name='Security Group', )
        security = get_group_adapter()(security, self.request)

        url = reverse('scim:groups')
        resp = self.client.get(url, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = {
            "schemas": [constants.SchemaURI.LIST_RESPONSE],
            "totalResults": 1,
            "itemsPerPage": 50,
            "startIndex": 1,
            'Resources': [
                security.to_dict(),
            ],
        }
        self.assertEqual(expected, result)

    def test_post(self):    # pylint: disable=missing-function-docstring
        url = reverse('scim:groups')
        data = {
            'schemas': [constants.SchemaURI.GROUP],
            'displayName': 'Behavior Group',
        }
        body = json.dumps(data)
        resp = self.client.post(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 201, resp.content.decode())

        # test object exists
        behavior = get_group_model().objects.get(name='Behavior Group')

        # test response
        behavior = get_group_adapter()(behavior, self.request)
        result = json.loads(resp.content.decode())
        self.assertEqual(result, behavior.to_dict())
        self.assertEqual(resp['Location'], behavior.location)

    def test_put(self):    # pylint: disable=missing-function-docstring
        behavior = get_group_model().objects.create(name='Behavior Group', )
        url = reverse('scim:groups', kwargs={'uuid': behavior.id})
        data = get_group_adapter()(behavior, self.request).to_dict()
        data['displayName'] = 'Better Behavior Group'
        body = json.dumps(data)
        resp = self.client.put(url, body, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        # test object
        behavior.refresh_from_db()
        self.assertEqual(behavior.name, 'Better Behavior Group')

        # test response
        result = json.loads(resp.content.decode())
        behavior = get_group_adapter()(behavior, self.request)
        self.assertEqual(result, behavior.to_dict())

    @skip('messing user id with scim_id, to be resolved')
    def test_patch_add(self):    # pylint: disable=missing-function-docstring
        behavior = get_group_model().objects.create(name='Behavior Group', )
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )
        ford.scim_groups.add(behavior)
        abernathy = get_user_model().objects.create(
            first_name='Dolores',
            last_name='Abernathy',
            username='dabernathy',
        )
        scim_abernathy = get_user_adapter()(abernathy, self.request)

        data = {
            'schemas': [constants.SchemaURI.PATCH_OP],
            'Operations': [{
                'op': 'add',
                'path': 'members',
                'value': [{
                    'value': scim_abernathy.id
                }]
            }]
        }
        data = json.dumps(data)

        url = reverse('scim:groups', kwargs={'uuid': behavior.id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = get_group_adapter()(behavior, self.request).to_dict()
        self.assertEqual(expected, result)

        self.assertEqual(behavior.user_set.count(), 2)

    def test_patch_remove(self):    # pylint: disable=missing-function-docstring
        behavior = get_group_model().objects.create(name='Behavior Group', )
        ford = get_user_model().objects.create(
            first_name='Robert',
            last_name='Ford',
            username='rford',
        )
        ford.scim_groups.add(behavior)
        abernathy = get_user_model().objects.create(
            first_name='Dolores',
            last_name='Abernathy',
            username='dabernathy',
        )
        abernathy.scim_groups.add(behavior)

        data = {
            'schemas': [constants.SchemaURI.PATCH_OP],
            'Operations': [{
                'op': 'remove',
                'path': 'members',
                'value': [
                    {
                        'value': ford.id
                    },
                    {
                        'value': abernathy.id
                    },
                ]
            }]
        }
        data = json.dumps(data)

        url = reverse('scim:groups', kwargs={'uuid': behavior.id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        result = json.loads(resp.content.decode())
        expected = get_group_adapter()(behavior, self.request).to_dict()
        self.assertEqual(expected, result)

        self.assertEqual(behavior.user_set.count(), 0)

    def test_patch_replace(self):    # pylint: disable=missing-function-docstring
        behavior = get_group_model().objects.create(name='Behavior Group', )

        data = {
            'schemas': [constants.SchemaURI.PATCH_OP],
            'Operations': [{
                'op': 'replace',
                'path': 'name',
                'value': [{
                    'value': 'Way better Behavior Group Name'
                }]
            }]
        }
        data = json.dumps(data)

        url = reverse('scim:groups', kwargs={'uuid': behavior.id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 200, resp.content.decode())

        behavior.refresh_from_db()

        result = json.loads(resp.content.decode())
        expected = get_group_adapter()(behavior, self.request).to_dict()
        self.assertEqual(expected, result)

        self.assertEqual(behavior.name, 'Way better Behavior Group Name')

    def test_patch_atomic(self):    # pylint: disable=missing-function-docstring
        behavior = get_group_model().objects.create(name='Behavior Group', )
        ids = list(get_user_model().objects.all().values_list('id', flat=True)) or [0]
        max_id = max(ids)

        data = {
            'schemas': [constants.SchemaURI.PATCH_OP],
            'Operations': [
                {
                    'op': 'replace',
                    'path': 'name',
                    'value': [{
                        'value': 'Way better Behavior Group Name'
                    }]
                },
        # Adding a non-existent user should cause this PATCH to fail
                {
                    'op': 'add',
                    'path': 'members',
                    'value': [{
                        'value': max_id + 1
                    }]
                }
            ]
        }
        data = json.dumps(data)

        url = reverse('scim:groups', kwargs={'uuid': behavior.id})
        resp = self.client.patch(url, data=data, content_type=constants.SCIM_CONTENT_TYPE)
        self.assertEqual(resp.status_code, 400, resp.content.decode())

        behavior.refresh_from_db()
        self.assertEqual(behavior.name, 'Behavior Group')

    def test_delete(self):    # pylint: disable=missing-function-docstring
        behavior = get_group_model().objects.create(name='Behavior Group', )

        url = reverse('scim:groups', kwargs={'uuid': behavior.id})
        resp = self.client.delete(url)
        self.assertEqual(resp.status_code, 204, resp.content.decode())

        behavior = get_group_model().objects.filter(id=behavior.id).first()
        self.assertIsNone(behavior)


class ServiceProviderConfigTestCase(LoginMixin, TestCase):
    '''
    test service provider
    '''
    maxDiff = None

    def test_get(self):    # pylint: disable=missing-function-docstring
        url = reverse('scim:service-provider-config')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        config = get_service_provider_config_model()()
        self.assertEqual(config.to_dict(), json.loads(resp.content.decode()))


class ResourceTypesTestCase(LoginMixin, TestCase):
    '''
    test resource types
    '''
    maxDiff = None

    def test_get_all(self):    # pylint: disable=missing-function-docstring
        url = reverse('scim:resource-types')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        user_type = get_user_adapter().resource_type_dict()
        group_type = get_group_adapter().resource_type_dict()
        key = lambda o: o.get('id')    # noqa: 731
        expected = {
            'schemas': [constants.SchemaURI.LIST_RESPONSE],
            'Resources': list(sorted((user_type, group_type), key=key)),
        }
        result = json.loads(resp.content.decode())
        self.assertEqual(expected, result)

    def test_get_single(self):    # pylint: disable=missing-function-docstring
        url = reverse('scim:resource-types', kwargs={'uuid': 'User'})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        expected = get_user_adapter().resource_type_dict()
        result = json.loads(resp.content.decode())
        self.assertEqual(expected, result)


class SchemasTestCase(LoginMixin, TestCase):
    '''
    test schema
    '''
    maxDiff = None

    def test_get_all(self):    # pylint: disable=missing-function-docstring
        url = reverse('scim:schemas')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        key = lambda o: o.get('id')    # noqa: 731
        expected = {
            'schemas': [constants.SchemaURI.LIST_RESPONSE],
            'Resources': list(sorted(ALL_SCHEMAS, key=key)),
        }
        result = json.loads(resp.content.decode())
        self.assertEqual(expected, result)

    def test_get_single(self):    # pylint: disable=missing-function-docstring
        schemas_by_uri = {s['id']: s for s in ALL_SCHEMAS}

        url = reverse('scim:schemas', kwargs={'uuid': constants.SchemaURI.USER})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200, resp.content.decode())
        expected = schemas_by_uri[constants.SchemaURI.USER]
        result = json.loads(resp.content.decode())
        self.assertEqual(expected, result)
