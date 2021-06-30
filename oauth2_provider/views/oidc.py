import json

from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import View
from jwcrypto import jwk

from ..models import get_application_model
from ..settings import oauth2_settings
from .mixins import OAuthLibMixin, OIDCOnlyMixin
from oauth2_provider.models import AccessToken


Application = get_application_model()


class ConnectDiscoveryInfoView(OIDCOnlyMixin, View):
    """
    View used to show oidc provider configuration information
    """

    def get(self, request, tenant, *args, **kwargs):
        print('tenant>>>', tenant)
        issuer_url = oauth2_settings.OIDC_ISS_ENDPOINT

        if not issuer_url:
            issuer_url = oauth2_settings.oidc_issuer(request, tenant)
            authorization_endpoint = request.build_absolute_uri(reverse("api:oauth2_authorization_server:authorize", args=[tenant]))
            token_endpoint = request.build_absolute_uri(reverse("api:oauth2_authorization_server:token", args=[tenant]))
            userinfo_endpoint = oauth2_settings.OIDC_USERINFO_ENDPOINT or request.build_absolute_uri(
                reverse("api:oauth2_authorization_server:user-info", args=[tenant])
            )
            jwks_uri = request.build_absolute_uri(reverse("api:oauth2_authorization_server:jwks-info", args=[tenant]))
        else:
            authorization_endpoint = "{}{}".format(issuer_url, reverse("api:oauth2_authorization_server:authorize"))
            token_endpoint = "{}{}".format(issuer_url, reverse("api:oauth2_authorization_server:token"))
            userinfo_endpoint = oauth2_settings.OIDC_USERINFO_ENDPOINT or "{}{}".format(
                issuer_url, reverse("api:oauth2_authorization_server:user-info")
            )
            jwks_uri = "{}{}".format(issuer_url, reverse("api:oauth2_authorization_server:jwks-info"))
        signing_algorithms = [Application.HS256_ALGORITHM]
        if oauth2_settings.OIDC_RSA_PRIVATE_KEY:
            signing_algorithms = [Application.RS256_ALGORITHM, Application.HS256_ALGORITHM]
        data = {
            "issuer": issuer_url,
            "authorization_endpoint": authorization_endpoint,
            "token_endpoint": token_endpoint,
            "userinfo_endpoint": userinfo_endpoint,
            "jwks_uri": jwks_uri,
            "response_types_supported": oauth2_settings.OIDC_RESPONSE_TYPES_SUPPORTED,
            "subject_types_supported": oauth2_settings.OIDC_SUBJECT_TYPES_SUPPORTED,
            "id_token_signing_alg_values_supported": signing_algorithms,
            "token_endpoint_auth_methods_supported": (
                oauth2_settings.OIDC_TOKEN_ENDPOINT_AUTH_METHODS_SUPPORTED
            ),
        }
        response = JsonResponse(data)
        response["Access-Control-Allow-Origin"] = "*"
        return response


class JwksInfoView(OIDCOnlyMixin, View):
    """
    View used to show oidc json web key set document
    """

    def get(self, request, *args, **kwargs):
        keys = []
        if oauth2_settings.OIDC_RSA_PRIVATE_KEY:
            key = jwk.JWK.from_pem(oauth2_settings.OIDC_RSA_PRIVATE_KEY.encode("utf8"))
            data = {"alg": "RS256", "use": "sig", "kid": key.thumbprint()}
            data.update(json.loads(key.export_public()))
            keys.append(data)
        response = JsonResponse({"keys": keys})
        response["Access-Control-Allow-Origin"] = "*"
        return response


@method_decorator(csrf_exempt, name="dispatch")
class UserInfoView(OIDCOnlyMixin, OAuthLibMixin, View):
    """
    View used to show Claims about the authenticated End-User
    """

    def get(self, request, *args, **kwargs):
        return self._create_userinfo_response(request)

    def post(self, request, *args, **kwargs):
        return self._create_userinfo_response(request)

    def _create_userinfo_response(self, request):
        url, headers, body, status = self.create_userinfo_response(request)
        response = HttpResponse(content=body or "", status=status)
        for k, v in headers.items():
            response[k] = v
        return response


@method_decorator(csrf_exempt, name="dispatch")
class UserInfoExtendView(OIDCOnlyMixin, OAuthLibMixin, View):
    """
    View used to show Claims about the authenticated End-User
    """

    def get(self, request, *args, **kwargs):
        access_token = request.META.get('HTTP_AUTHORIZATION', '')
        return self.get_user(access_token)


    def post(self, request, *args, **kwargs):
        access_token = request.META.get('HTTP_AUTHORIZATION', '')
        return self.get_user(access_token)

    def get_user(self, access_token):
        if access_token:
            access_token = access_token.split(' ')[1]
            access_token = AccessToken.objects.filter(token=access_token).first()
            if access_token:
                user = access_token.user
                return JsonResponse({"id":user.id,"name":user.username,"email":user.email})
            else:
                return JsonResponse({"error": "access_token 不存在"})
        else:
            return JsonResponse({"error": "access_token 不能为空"})
        