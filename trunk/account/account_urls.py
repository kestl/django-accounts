from django.conf.urls.defaults import *

def _sub(method):
    return 'account.views.subscription.' + method

urlpatterns = patterns('',
    (
        r'^upgrade/$', 
        _sub('upgrade'), 
        {
            'meta': {
                'requires_login': True,
            },
        }
    ),
    (
        r'^create/(\d+)/$', 
        _sub('create'), 
        {
            'meta': {
                'requires_account': False,
            },
        }
    ),
)
