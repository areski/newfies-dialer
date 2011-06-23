import plivohelper


REST_API_URL = 'http://127.0.0.1:8088'
API_VERSION = 'v0.1'

# Sid and AuthToken
SID = 'XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX'
AUTH_TOKEN = 'YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY'


def call_plivo(callerid=None, phone_number=None, Gateways=None, GatewayCodecs="'PCMA,PCMU'",
                    GatewayTimeouts="60", GatewayRetries='1', ExtraDialString=None,
                    AnswerUrl=None, HangupUrl=None, TimeLimit="3600"):
    # URL of the Plivo REST service
    
    # Define Channel Variable - http://wiki.freeswitch.org/wiki/Channel_Variables
    extra_dial_string = "bridge_early_media=true,hangup_after_bridge=true"

    #TODO : See if we want to merge ExtraDialString

    # Create a REST object
    plivo = plivohelper.REST(REST_API_URL, SID, AUTH_TOKEN, API_VERSION)

    # Initiate a new outbound call to user/1000 using a HTTP POST
    call_params = {
        'From': callerid, # Caller Id
        'To' : phone_number, # User Number to Call
        'Gateways' : Gateways, # Gateway string to try dialing separated by comma. First in list will be tried first
        'GatewayCodecs' : GatewayCodecs, # Codec string as needed by FS for each gateway separated by comma
        'GatewayTimeouts' : GatewayTimeouts,      # Seconds to timeout in string for each gateway separated by comma
        'GatewayRetries' : GatewayRetries, # Retry String for Gateways separated by comma, on how many times each gateway should be retried
        'ExtraDialString' : extra_dial_string,
        'AnswerUrl' : AnswerUrl,
        'HangupUrl' : HangupUrl,
        'TimeLimit' : TimeLimit,
    }

    #Perform the Call on the Rest API
    try:
        result = plivo.call(call_params)
        if result:
            print "RESULT FROM PLIVO HELPER : " + result['RequestUUID']
            return result
    except Exception, e:
        print e
        raise

    return False