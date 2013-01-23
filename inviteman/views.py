from django.utils.translation import ugettext as _
from inviteman.models import Invite
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from django.template.loader import get_template, Context
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.core.mail import EmailMessage
import django.forms as forms

class InviteForm(forms.Form):
	email = forms.EmailField(max_length = 200)
	message = forms.CharField(max_length = 200, required = False)

@login_required
def invite(request):
	context = {
		'title': 'Invite someone',
		'invites_left': request.user.get_profile().invites_left,
	}

	if not request.method == 'POST':
		return render_to_response('invite.html', context_instance=RequestContext(request, context))

	# Request method is POST
	form = InviteForm(request.POST, request.FILES)

	if not form.is_valid():
		context['form'] = form
		return render_to_response('invite.html', context_instance=RequestContext(request, context))

	# Check if user has enough invites left
	profile = request.user.get_profile()

	# Since you shouldn't be able to do this unless you do nasty stuff anyways,
	# no need for a pretty error page
	if profile.invites_left < 1:
		return HttpResponse('Sorry, you don\'t have any invites left.')

	mail_template = get_template('mails/invite_friend.txt')

	# Generate the invite
	invite = Invite(generated_by = request.user)
	invite.save()

	# Remove from invites_left field
	profile.invites_left -= 1
	context['invites_left'] = profile.invites_left
	profile.save()

	mail = EmailMessage(
			_('You\'ve been invited to join shortdiary by {}').format(request.user.username),
			mail_template.render(Context({'user': request.user, 'invite': invite})),
			'shortdiary <team@shortdiary.me>',
			['{}'.format(form.cleaned_data['email'])],
		)
	mail.send()
	return render_to_response('invite.html', context_instance=RequestContext(request, context))
