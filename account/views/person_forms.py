import new
from django.conf import settings
from django import newforms as forms
from ..models import Person, Account, RecurringPayment
from account.lib.payment.errors import PaymentRequestError, PaymentResponseError

class LoginForm(forms.Form):
    
    username = forms.CharField(
        label = 'Username',
    )
    
    password = forms.CharField(
        label = 'Password', 
        widget = forms.PasswordInput,
    )        
    
    remember_me = forms.BooleanField(
        label = 'Remember me on this computer', 
        required = False,
    )        
    
    person = None
    account = None
    
    def clean(self):
        if self._errors: 
            return
        
        self.person = Person.authenticate(
            self.data['username'],
            self.account,
            self.data['password'],
        )
        
        if self.person is None:
            raise forms.ValidationError(
                "Your username and password didn't match. Did you spell them right?",
            )
        return self.cleaned_data
    
    def login(self, request):
        self.account = request.account
        if self.is_valid():
            request.session[
                 settings.PERSISTENT_SESSION_KEY
            ] = self.cleaned_data['remember_me']
                
            self.person.login(request)
            return True
        return False

    
# TODO: Need more elegant solution.    
class ResetPasswordForm(forms.Form):
    username = forms.CharField(
        label = 'Username',
    )
    
    person = None
    account = None
    
    def clean(self):
        if self._errors: 
            return
        try:
            self.person = Person.objects.get(
                username = self.data['username'],
                account = self.account,
            )
        except Person.DoesNotExist:
            raise forms.ValidationError(
                "Your user name wasn't on file. Did you spell it correctly?",
            )
        
    def get_person(self, request):
        self.account = request.account
        if self.is_valid():
            return self.person

        
    
   
class SavesPayment(object):
    def _get_requires_payment(self):
        return  getattr(self, '_requires_payment', True)
    
    def _set_requires_payment(self, value):
        self._requires_payment = value
        
    requires_payment = property(_get_requires_payment, _set_requires_payment)

    def save_payment(self, account, subscription_level, start_date=None, commit=True):
        if not self.requires_payment:
            return None
        try:
            obj = RecurringPayment.create(
                account = account, 
                amount = subscription_level['price'], 
                card_number = self.cleaned_data['card_number'], 
                card_expires = self.cleaned_data['card_expiration'], 
                first_name = self.cleaned_data['first_name'],
                last_name = self.cleaned_data['last_name'],
                start_date = start_date
            )
            if commit:
                obj.save()
            return obj
        
        except PaymentRequestError:
            # The payment gateway rejected our request.
            self._errors['__all__'] = "We were unable to verify your payment info. Did you mistype something?"
            raise    

    def clean_card_expiration(self):
        if not self.requires_payment:
            return None
        from datetime import date
        try:
            if self.cleaned_data['card_expiration'] < date.today():
                raise forms.ValidationError(
                    "Your card expiration can't be before todays date."
                )
        except TypeError:
            raise forms.ValidationError(
                "Your card expiration was not a valid date."
            )
            
        return self.cleaned_data['card_expiration']
    
    def clean_card_type(self):
        if not self.requires_payment:
            return None
        return self.cleaned_data['card_type']
        
    def clean_card_number(self):
        if not self.requires_payment:
            return None
        return self.cleaned_data['card_number']

    
class SignupForm(forms.Form, SavesPayment):
    def __init__(self, requires_payment, *args, **kwargs):
        self.requires_payment = requires_payment
        forms.Form.__init__(self, *args, **kwargs)
        
    first_name = forms.CharField(
        label = "First name",
        min_length = 2,
        max_length = 30,        
    )
    last_name = forms.CharField(
        label = "Last name",
        min_length = 2,
        max_length = 30,        
    )
    email = forms.EmailField(
        label = "Email",
    )
    username = forms.CharField(
        label = "Username",
        help_text = "You'll use this to log in",
        min_length = 4,
        max_length = 30,        
    )
    password = forms.CharField(
        label = "Password",
        min_length = 6,
        max_length = 20,
        widget = forms.PasswordInput()
    )
    password2 = forms.CharField(
        label = "Password again",
        help_text = "Confirm your password by entering it again",
        min_length = 6,
        max_length = 20,
        widget = forms.PasswordInput()
    )
    group = forms.CharField(
        label = "Company / Organization",
        min_length = 2,
        max_length = 30,        
    )
    timezone = forms.ChoiceField(
        label = "Time zone",
        choices = enumerate(settings.ACCOUNT_TIME_ZONES)
    )
    subdomain = forms.CharField(
        min_length = 2,
        max_length = 30,        
    )
    root_domain = forms.ChoiceField(
        choices = enumerate(settings.ACCOUNT_DOMAINS)
    )
            
    #card_type = forms.ChoiceField(
        #label = "Card type",
        #choices = enumerate(['Visa', 'Mastercard', 'AmericanExpress']),
        #required = False,
    #)
    
    card_number = forms.CharField(
        label = "Card number",
        required = False,
    )
    card_expiration = forms.DateField(
        label = "Expiration",
        required = False,
    )

    terms_of_service = forms.BooleanField(
        label = "I agree to the Terms of Service, Refund, and Privacy policies"
    )
        
    def clean_timezone(self):
        try:
            return settings.ACCOUNT_TIME_ZONES[int(self.cleaned_data['timezone'])]
        except ValueError:
            raise form.ValidationError(
                "Invalid Time Zone"
            )
        
    def clean_password2(self):
        if self.cleaned_data['password'] != self.cleaned_data['password2']:
            raise forms.ValidationError(
                "The two passwords didn't match. Please try again."
            )
        return self.cleaned_data['password2']
    
    def clean_subdomain(self):
        if not self.cleaned_data['subdomain'].isalnum():
            raise forms.ValidationError(
                "Your subdomain can only include letters and numbers."
            )
        return self.cleaned_data['subdomain']
    
    
    def clean_terms_of_service(self):
        if not self.cleaned_data['terms_of_service']:
            raise forms.ValidationError(
                "Sorry, but we can't create your account unless you accept the terms of service."
            )
        
    
    def clean(self):
        if self.errors:
            return
        self.cleaned_data['domain'] = '%s.%s' % (
            self.cleaned_data['subdomain'],
            settings.ACCOUNT_DOMAINS[
                int(self.cleaned_data['root_domain'])
            ]
        )
        return self.cleaned_data
        
            
        
        
    def save_account(self, level):
        account = Account(
            domain = self.cleaned_data['domain'],
            timezone = self.cleaned_data['timezone'],
            name = self.cleaned_data['group'],
            subscription_level_id = level,
        )
        if not account.validate():
            account.save()
            return account
        else:
            raise ValueError
        
        
    def save_person(self, account):
        person = Person(
            account = account,
            username = self.cleaned_data['username'],
            first_name = self.cleaned_data['first_name'],
            last_name = self.cleaned_data['last_name'],
            email = self.cleaned_data['email'],
        )
        person.set_password(self.cleaned_data['password'])
        if not person.validate():
            person.save()
            return person
        else:
            raise ValueError
                    

class PaymentForm(forms.Form, SavesPayment):

    first_name = forms.CharField(
        label = "First name",
        min_length = 2,
        max_length = 30,        
    )
    last_name = forms.CharField(
        label = "Last name",
        min_length = 2,
        max_length = 30,        
    )
    card_number = forms.CharField(
        label = "Card number",
    )
    card_expiration = forms.DateField(
        label = "Expiration",
    )
    

class UpgradeForm(forms.Form, SavesPayment):
    #TODO: Fill in first name if available
    first_name = forms.CharField(
        label = "First name",
        min_length = 2,
        max_length = 30,        
        required = False,
    )
    last_name = forms.CharField(
        label = "Last name",
        min_length = 2,
        max_length = 30,        
        required = False,
    )
    card_number = forms.CharField(
        label = "Card number",
        required = False,
    )
    card_expiration = forms.DateField(
        label = "Expiration",
        required = False,
    )
    
    def __init__(self, requires_payment, *args, **kwargs):
        self.requires_payment = requires_payment
        forms.Form.__init__(self, *args, **kwargs)



class AccountForm(forms.Form):
    name = forms.CharField(
        label = "Company / Organization",
        min_length = 2,
        max_length = 30,        
    )
    timezone = forms.ChoiceField(
        label = "Time zone",
        choices = enumerate(settings.ACCOUNT_TIME_ZONES)
    )
    subdomain = forms.CharField(
        min_length = 2,
        max_length = 30,        
    )
    root_domain = forms.ChoiceField(
        choices = enumerate(settings.ACCOUNT_DOMAINS)
    )
            
    def clean_subdomain(self):
        if not self.cleaned_data['subdomain'].isalnum():
            raise forms.ValidationError(
                "Your subdomain can only include letters and numbers."
            )
        return self.cleaned_data['subdomain']
    
    def clean_timezone(self):
        try:
            return settings.ACCOUNT_TIME_ZONES[int(self.cleaned_data['timezone'])]
        except ValueError:
            raise form.ValidationError(
                "Invalid Time Zone"
            )
    
    def clean(self):
        if self.errors:
            return
        self.cleaned_data['domain'] = '%s.%s' % (
            self.cleaned_data['subdomain'],
            settings.ACCOUNT_DOMAINS[
                int(self.cleaned_data['root_domain'])
            ]
        )
        return self.cleaned_data
    
        
    def update_account(self, account):
        for n in ['name', 'domain', 'timezone']:
            setattr(account, n, self.cleaned_data[n])
        if not account.validate():
            account.save()
            return account
        else:
            raise ValueError
        
    



##############################################
# Decorators for generic views
##############################################

def decorate_person_form(form, instance=None):
    """
    Adds a confirmed password field to form.
    """
    form.base_fields['new_password'].widget = forms.PasswordInput()
    form.base_fields['new_password'].initial = ''
    form.base_fields['new_password'].min_length = 6
    form.base_fields['new_password'].max_length = 20
    form.base_fields['new_password_confirm'] = forms.CharField(
        min_length = 6,
        max_length = 20,
        widget = forms.PasswordInput()
    )
    
    form.base_fields['new_password'].required = not instance
    form.base_fields['new_password_confirm'].required = not instance
        
    def clean_new_password_confirm(self):
        if self._errors: 
            return None
        if self.cleaned_data['new_password_confirm'] != self.cleaned_data['new_password']:
            raise forms.ValidationError("Passwords must match")
        return self.cleaned_data['new_password_confirm']
    
    form.clean_new_password_confirm = clean_new_password_confirm
    return form
