import logging

from django.contrib.auth.models import User
from django.conf.urls.defaults import url

from tastypie.resources import ModelResource, ALL, ALL_WITH_RELATIONS
from django.contrib.auth.models import User
from tastypie.authentication import BasicAuthentication
from tastypie.authorization import DjangoAuthorization
from tastypie.authorization import Authorization
from tastypie.serializers import Serializer
from tastypie.validation import Validation
from tastypie.throttle import BaseThrottle
from tastypie.utils import dict_strip_unicode_keys, trailing_slash
from tastypie.http import HttpCreated
from dialer_campaign.models import Campaign, Phonebook
from tastypie import fields
from dialer_campaign.function_def import user_attached_with_dialer_settings, \
    check_dialer_setting, dialer_setting_limit
from dialer_gateway.models import Gateway
from voip_app.models import VoipApp
import time


log = logging.getLogger(__name__)


def get_value_if_none(x, value):
    """return value if x is None"""
    if x is None:
        return value
    return x

class VoipAppResource(ModelResource):
    class Meta:
        queryset = VoipApp.objects.all()
        resource_name = 'voipapp'


class GatewayResource(ModelResource):
    class Meta:
        queryset = Gateway.objects.all()
        resource_name = 'gateway'


class UserResource(ModelResource):
    class Meta:
        allowed_methods = ['get'] # Don't display or update User
        queryset = User.objects.all()
        resource_name = 'user'
        fields = ['username', 'first_name', 'last_name', 'last_login', 'id']
        filtering = {
            'username': 'exact',
        }
        throttle = BaseThrottle(throttle_at=1000, timeframe=3600) #default 1000 calls / hour

        
class CampaignValidation(Validation):
    """
    Campaign Validation Class
    """
    def is_valid(self, bundle, request=None):
        errors = {}

        startingdate = bundle.data.get('startingdate')
        expirationdate = bundle.data.get('expirationdate')
        if request.method == 'POST':
            startingdate = get_value_if_none(startingdate, time.time())
            # expires in 7 days
            expirationdate = get_value_if_none(expirationdate, time.time() + 86400 * 7)

            bundle.data['startingdate'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                          time.gmtime(float(startingdate)))
            bundle.data['expirationdate'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                            time.gmtime(float(expirationdate)))

        if request.method == 'PUT':
            if startingdate:
                bundle.data['startingdate'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                              time.gmtime(float(startingdate)))
            if expirationdate:
                bundle.data['expirationdate'] = time.strftime('%Y-%m-%d %H:%M:%S',
                                                time.gmtime(float(expirationdate)))
        
        if user_attached_with_dialer_settings(request):
            errors['user_dialer_setting'] = ['Your settings are not \
                        configured properly, Please contact the administrator.']

        if check_dialer_setting(request, check_for="campaign"):
            errors['chk_campaign'] = ["You have too many campaigns. Max allowed %s" \
            % dialer_setting_limit(request, limit_for="campaign")]


        frequency = bundle.data.get('frequency')
        if frequency:
            if check_dialer_setting(request, check_for="frequency",
                                        field_value=int(frequency)):
                errors['chk_frequency'] = ["Maximum Frequency limit of %s exceeded." \
                % dialer_setting_limit(request, limit_for="frequency")]

        callmaxduration = bundle.data.get('callmaxduration')
        if callmaxduration:
            if check_dialer_setting(request,
                                    check_for="duration",
                                    field_value=int(callmaxduration)):
                errors['chk_duration'] = ["Maximum Duration limit of %s exceeded." \
                % dialer_setting_limit(request, limit_for="duration")]

        maxretry = bundle.data.get('maxretry')
        if maxretry:
            if check_dialer_setting(request,
                                    check_for="retry",
                                    field_value=int(maxretry)):
                errors['chk_duration'] = ["Maximum Retries limit of %s exceeded." \
                % dialer_setting_limit(request, limit_for="retry")]

        calltimeout = bundle.data.get('calltimeout')
        if calltimeout:
            if check_dialer_setting(request,
                                    check_for="timeout",
                                    field_value=int(calltimeout)):
                errors['chk_timeout'] = ["Maximum Timeout limit of %s exceeded." \
                % dialer_setting_limit(request, limit_for="timeout")]

        aleg_gateway_id = bundle.data.get('aleg_gateway')
        if aleg_gateway_id:
            try:
                aleg_gateway_id = Gateway.objects.get(id=aleg_gateway_id).id
                bundle.data['aleg_gateway'] = '/api/v1/gateway/%s/' % aleg_gateway_id
            except:
                errors['chk_gateway'] = ["The Gateway ID doesn't exist!"]

        voipapp_id = bundle.data.get('voipapp')
        if voipapp_id:
            try:
                voip_app_id = VoipApp.objects.get(id=voipapp_id).id
                bundle.data['voipapp'] = '/api/v1/voipapp/%s/' % voip_app_id
            except:
                errors['chk_voipapp'] = ["The VoipApp doesn't exist!"]

        try:
            user_id = User.objects.get(username=request.user).id
            bundle.data['user'] = '/api/v1/user/%s/' % user_id
        except:
            errors['chk_user'] = ["The User doesn't exist!"]


        if request.method=='POST':
            name_count = Campaign.objects.filter(name=bundle.data.get('name'),
                                                 user=request.user).count()
            if (name_count!=0):
                errors['chk_campaign_name'] = ["The Campaign name duplicated!"]


        return errors

    
class CampaignResource(ModelResource):
    """
    **Attributes**:

            * ``campaign_code`` - Autogenerate campaign code
            * ``name`` - Name of the Campaign
            * ``description`` - Short description of the Campaign
            * ``callerid`` - Caller ID
            * ``startingdate`` - Start date. Epoch Time, ie 1301414368
            * ``expirationdate`` - Expiry date. Epoch Time, ie 1301414368
            * ``daily_start_time`` - Daily start time, default '00:00:00'
            * ``daily_stop_time`` - Daily stop time, default '23:59:59'
            * ``monday`` - Set to 1 if you want to run this day of the week,\
            default '1'
            * ``tuesday`` - Set to 1 if you want to run this day of the week,\
            default '1'
            * ``wednesday`` - Set to 1 if you want to run this day of the week\
            , default '1'
            * ``thursday`` - Set to 1 if you want to run this day of the week,\
            default '1'
            * ``friday`` - Set to 1 if you want to run this day of the week,\
            default '1'
            * ``saturday`` - Set to 1 if you want to run this day of the week,\
            default '1'
            * ``sunday`` - Set to 1 if you want to run this day of the week,\
            default '1'

        **Campaign Settings**:

            * ``frequency`` - Defines the frequency, speed of the campaign.\
                              This is the number of calls per minute.
            * ``callmaxduration`` - Maximum call duration.
            * ``maxretry`` - Defines the max retries allowed per user.
            * ``intervalretry`` - Defines the time to wait between retries\
                                  in seconds
            * ``calltimeout`` - Defines the number of seconds to timeout on calls

        **Gateways**:

            * ``aleg_gateway`` - Defines the Gateway to use to call the\
                                 subscriber
            * ``voipapp`` - Defines the  application to use when the \
                            call is established on the A-Leg
            * ``extra_data`` - Defines the additional data to pass to the\
                                 application

    **Create**:

        CURL Usage::

            curl -u username:password --dump-header - -H "Content-Type:application/json" -X POST --data '{"name": "mycampaign", "description": "", "callerid": "1239876", "startingdate": "1301392136.0", "expirationdate": "1301332136.0", "frequency": "20", "callmaxduration": "50", "maxretry": "3", "intervalretry": "3000", "calltimeout": "45", "aleg_gateway": "1", "voipapp": "1", "extra_data": "2000"}' http://localhost:8000/api/v1/campaign/

        Response::

            HTTP/1.0 201 CREATED
            Date: Fri, 23 Sep 2011 06:08:34 GMT
            Server: WSGIServer/0.1 Python/2.7.1+
            Vary: Accept-Language, Cookie
            Content-Type: text/html; charset=utf-8
            Location: http://localhost:8000/api/app/campaign/1/
            Content-Language: en-us


    **Read**:

        CURL Usage::

            curl -u username:password -H 'Accept: application/json' http://localhost:8000/api/v1/campaign/?format=json

        Response::

            {
               "meta":{
                  "limit":20,
                  "next":null,
                  "offset":0,
                  "previous":null,
                  "total_count":1
               },
               "objects":[
                  {
                     "callerid":"123987",
                     "callmaxduration":1800,
                     "calltimeout":45,
                     "campaign_code":"XIUER",
                     "created_date":"2011-06-15T00:49:16",
                     "daily_start_time":"00:00:00",
                     "daily_stop_time":"23:59:59",
                     "description":"",
                     "expirationdate":"2011-06-22T00:01:15",
                     "extra_data":"",
                     "frequency":10,
                     "friday":true,
                     "id":"1",
                     "intervalretry":3,
                     "maxretry":3,
                     "monday":true,
                     "name":"Default_Campaign",
                     "resource_uri":"/api/app/campaign/1/",
                     "saturday":true,
                     "startingdate":"2011-06-15T00:01:15",
                     "status":1,
                     "sunday":true,
                     "thursday":true,
                     "tuesday":true,
                     "updated_date":"2011-06-15T00:49:16",
                     "wednesday":true
                  }
               ]
            }

    **Update**:

        CURL Usage::

            curl -u username:password --dump-header - -H "Content-Type: application/json" -X PUT --data '{"name": "mylittlecampaign", "description": "", "callerid": "1239876", "startingdate": "1301392136.0", "expirationdate": "1301332136.0","frequency": "20", "callmaxduration": "50", "maxretry": "3", "intervalretry": "3000", "calltimeout": "60", "aleg_gateway": "1", "voipapp": "1", "extra_data": "2000" }' http://localhost:8000/api/v1/campaign/1/

        Response::

            HTTP/1.0 204 NO CONTENT
            Date: Fri, 23 Sep 2011 06:46:12 GMT
            Server: WSGIServer/0.1 Python/2.7.1+
            Vary: Accept-Language, Cookie
            Content-Length: 0
            Content-Type: text/html; charset=utf-8
            Content-Language: en-us

            
    **Delete**:

        CURL Usage::

            curl -u username:password --dump-header - -H "Content-Type: application/json" -X DELETE  http://localhost:8000/api/v1/campaign/1/

            curl -u username:password --dump-header - -H "Content-Type: application/json" -X DELETE  http://localhost:8000/api/v1/campaign/

        Response::

            HTTP/1.0 204 NO CONTENT
            Date: Fri, 23 Sep 2011 06:48:03 GMT
            Server: WSGIServer/0.1 Python/2.7.1+
            Vary: Accept-Language, Cookie
            Content-Length: 0
            Content-Type: text/html; charset=utf-8
            Content-Language: en-us

    **Search**:

        CURL Usage::

            curl -u username:password -H 'Accept: application/json' http://localhost:8000/api/v1/campaign/?name=mycampaign2

        Response::

            {
               "meta":{
                  "limit":20,
                  "next":null,
                  "offset":0,
                  "previous":null,
                  "total_count":1
               },
               "objects":[
                  {
                     "aleg_gateway":{

                        "created_date":"2011-06-15T00:28:52",
                        "description":"",
                        "id":"1",
                        "maximum_call":null,
                        "name":"Default_Gateway",
                     },
                     "callerid":"1239876",
                     "callmaxduration":50,
                     "calltimeout":45,
                     "campaign_code":"DJZVK",
                     "created_date":"2011-10-13T02:06:22",
                     "daily_start_time":"00:00:00",
                     "daily_stop_time":"23:59:59",
                     "description":"",
                     "expirationdate":"2011-03-28T17:08:56",
                     "extra_data":"2000",
                     "frequency":20,
                     "friday":true,
                     "id":"16",
                     "intervalretry":3000,
                     "maxretry":3,
                     "monday":true,
                     "name":"mycampaign2",
                     "resource_uri":"/api/v1/campaign/16/",
                     "saturday":true,
                     "startingdate":"2011-03-29T09:48:56",
                     "status":2,
                     "sunday":true,
                     "thursday":true,
                     "tuesday":true,
                     "updated_date":"2011-10-13T02:06:22",
                     "user":{
                        "id":"1",
                        "username":"areski"
                     },
                     "voipapp":{
                        "id":"1",
                        "name":"Default_VoIP_App",
                     },
                     "wednesday":true
                  }
               ]
            }
    """
    user = fields.ForeignKey(UserResource, 'user', full=True)
    aleg_gateway = fields.ForeignKey(GatewayResource, 'aleg_gateway', full=True)
    voipapp = fields.ForeignKey(VoipAppResource, 'voipapp', full=True)
    class Meta:
        queryset = Campaign.objects.all()
        resource_name = 'campaign'
        authorization = Authorization()
        authentication = BasicAuthentication()
        validation = CampaignValidation()
        filtering = {
            'name': ALL,
            'status': ALL,
        }
        throttle = BaseThrottle(throttle_at=1000, timeframe=3600) #default 1000 calls / hour


class PhonebookValidation(Validation):
    """
    Phonebook Validation Class
    """
    def is_valid(self, bundle, request=None):
        errors = {}
        campaign_id = bundle.data.get('campaign_id')
        if campaign_id:
            try:
                campaign = Campaign.objects.get(id=campaign_id)
            except:
                errors['chk_campaign'] = ['The Campaign ID does not exist!']

        try:
            user_id = User.objects.get(username=request.user).id
            bundle.data['user'] = '/api/v1/user/%s/' % user_id
        except:
            errors['chk_user'] = ["The User doesn't exist!"]

        return errors


class PhonebookResource(ModelResource):
    """
    **Attributes**:

        * ``name`` - Name of the Phonebook
        * ``description`` - Short description of the Campaign
        * ``campaign_id`` - Campaign ID

    **Create**:

        CURL Usage::

            curl -u username:password --dump-header - -H "Content-Type:application/json" -X POST --data '{"name": "mylittlephonebook", "description": "", "campaign_id": "1"}' http://localhost:8000/api/v1/phonebook/

        Response::

            HTTP/1.0 201 CREATED
            Date: Fri, 23 Sep 2011 06:08:34 GMT
            Server: WSGIServer/0.1 Python/2.7.1+
            Vary: Accept-Language, Cookie
            Content-Type: text/html; charset=utf-8
            Location: http://localhost:8000/api/app/campaign/1/
            Content-Language: en-us


    **Read**:

        CURL Usage::

            curl -u username:password -H 'Accept: application/json' http://localhost:8000/api/v1/phonebook/?format=json

        Response::

            {
               "meta":{
                  "limit":20,
                  "next":null,
                  "offset":0,
                  "previous":null,
                  "total_count":1
               },
               "objects":[
                  {
                     "created_date":"2011-04-08T07:55:05",
                     "description":"This is default phone book",
                     "id":"1",
                     "name":"Default_Phonebook",
                     "resource_uri":"/api/v1/phonebook/1/",
                     "updated_date":"2011-04-08T07:55:05",
                     "user":{                                                                      
                        "first_name":"",
                        "id":"1",
                        "last_login":"2011-10-11T01:03:42",
                        "last_name":"",
                        "resource_uri":"/api/v1/user/1/",
                        "username":"areski"
                     }
                  }
               ]
            }


    **Update**:

        CURL Usage::

            curl -u username:password --dump-header - -H "Content-Type: application/json" -X PUT --data '{"name": "mylittlecampaign", "description": "", "callerid": "1239876", "startingdate": "1301392136.0", "expirationdate": "1301332136.0","frequency": "20", "callmaxduration": "50", "maxretry": "3", "intervalretry": "3000", "calltimeout": "60", "aleg_gateway": "1", "voipapp": "1", "extra_data": "2000" }' http://localhost:8000/api/v1/campaign/1/

        Response::

            HTTP/1.0 204 NO CONTENT
            Date: Fri, 23 Sep 2011 06:46:12 GMT
            Server: WSGIServer/0.1 Python/2.7.1+
            Vary: Accept-Language, Cookie
            Content-Length: 0
            Content-Type: text/html; charset=utf-8
            Content-Language: en-us


    **Delete**:

        CURL Usage::

            curl -u username:password --dump-header - -H "Content-Type: application/json" -X DELETE  http://localhost:8000/api/v1/campaign/1/

            curl -u username:password --dump-header - -H "Content-Type: application/json" -X DELETE  http://localhost:8000/api/v1/campaign/

        Response::

            HTTP/1.0 204 NO CONTENT
            Date: Fri, 23 Sep 2011 06:48:03 GMT
            Server: WSGIServer/0.1 Python/2.7.1+
            Vary: Accept-Language, Cookie
            Content-Length: 0
            Content-Type: text/html; charset=utf-8
            Content-Language: en-us

    **Search**:

        CURL Usage::

            curl -u username:password -H 'Accept: application/json' http://localhost:8000/api/v1/campaign/?name=mycampaign2

        Response::


    """
    user = fields.ForeignKey(UserResource, 'user', full=True)
    class Meta:
        queryset = Phonebook.objects.all()
        resource_name = 'phonebook'
        authorization = Authorization()
        authentication = BasicAuthentication()
        validation = PhonebookValidation()
        filtering = {
            'name': ALL,
        }
        throttle = BaseThrottle(throttle_at=1000, timeframe=3600) #default 1000 calls / hour


class MyCampaignResource(ModelResource):

    user = fields.ForeignKey(UserResource, 'user')    
    rating = fields.FloatField(readonly=True)

    class Meta:
        queryset = Campaign.objects.all()
        resource_name = 'mycampaign'
        authorization = Authorization()
        authentication = BasicAuthentication()
        throttle = BaseThrottle(throttle_at=1000, timeframe=3600) #default 1000 calls / hour

    def dehydrate_rating(self, bundle):
        total_score = 5.0
        
        return total_score

    def dehydrate(self, bundle):
        # Include the request IP in the bundle.
        bundle.data['request_ip'] = bundle.request.META.get('REMOTE_ADDR')
        return bundle
        
        
    
class MyResource(ModelResource):
    # As is, this is just an empty field. Without the ``dehydrate_rating``
    # method, no data would be populated for it.
    rating = fields.FloatField(readonly=True)

    class Meta:
        queryset = Campaign.objects.all()
        resource_name = 'rating'
        authorization = Authorization()
        authentication = BasicAuthentication()

    def dehydrate_rating(self, bundle):
        total_score = 5.0
        
        return total_score

    def dehydrate(self, bundle):
        # Include the request IP in the bundle.
        bundle.data['request_ip'] = bundle.request.META.get('REMOTE_ADDR')
        return bundle
