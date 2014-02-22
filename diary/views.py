# coding: utf-8
import datetime
from django.http import HttpResponse, HttpResponseRedirect, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render_to_response
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext as _
from django.template.context import RequestContext
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from inviteman.models import Invite
import django.contrib.auth
from diary.models import Post, DiaryUser
from diary.forms import PostForm, SignUpForm, LoginForm, AccountSettingsForm
from django.views.decorators.cache import cache_page

def index(request):
	try:
		randompost = Post.objects.filter(public = True).order_by('?')[:1].get()
	except Post.DoesNotExist:
		randompost = None

	if not request.user.is_authenticated():
		context = {
			'title': None,
			'post': randompost,
		}
		return render_to_response('frontpage.html', context_instance=RequestContext(request, context))

	context = {
		'title': None,
		'randompost': randompost,
		'posts': Post.objects.filter(author = request.user, date__gte = datetime.date.today() - datetime.timedelta(days = 6)).order_by('-date', '-created_at'),
	}
	return render_to_response('index.html', context_instance=RequestContext(request, context))

@login_required
def edit_post(request, post_id = None):
	"""
	Edit or add post.

	This view takes one parameter (post_id). It defaults to None, in which case
	a new post will be created.
	"""

	edit_post = None

	# Do we want to edit an existing post? If yes, try to find that post.
	# (And also check if that post was within the last 7 days)
	if post_id:
		edit_post = get_object_or_404(Post,
			id = post_id,
			author = request.user,
		)

		if not edit_post.is_editable():
			raise PermissionDenied

	yesterday = datetime.date.today() - datetime.timedelta(days=1)
	
	if not request.method == 'POST':
		# Check if there are not already posts existing for the last 2 days
		# This is only relevant if we add a new post
		existing_posts = (
			Post.objects.filter(author = request.user, date = yesterday),
			Post.objects.filter(author = request.user, date = datetime.date.today())
		)

		# Pass this information along to the template, which will show an error
		# if posts for both days exist already (Or will hide the day for which
		# a post already exists, if there's only one).
		context = {
			'title': _('Edit post') if edit_post else _('New post'),
			'post_days': (yesterday, datetime.date.today()),
			'existing_posts': existing_posts,
			'form': PostForm(),
			'edit_post': edit_post,
		}

		return render_to_response('edit_post.html', context_instance=RequestContext(request, context))

	# Request method is POST
	form = PostForm(request.POST, request.FILES)
	if not form.is_valid():
		context = {
			'title': _('New post'),
			'post_days': (yesterday, datetime.date.today()),
			'form': form,
			'edit_post': edit_post,
		}

		return render_to_response('edit_post.html', context_instance=RequestContext(request, context))


	if not edit_post:
		# This is a new post, save it
		post = form.save(commit = False)

		if Post.objects.filter(author = request.user, date = post.date).count() > 0:
			return HttpResponse('Sorry, you already have an entry for that day')

		post.author = request.user
		post.save()
	else:
		# This is an edit of an existing post
		edit_post.text = form.cleaned_data['text']		
		edit_post.mood = form.cleaned_data['mood']	
		edit_post.save()	

	return HttpResponseRedirect('/')

def show_post(request, post_id):
	post = get_object_or_404(Post, id = post_id)

	if not post.public and not request.user.is_authenticated():
		return HttpResponseRedirect('/accounts/login/?next={}'.format(request.get_full_path()))

	if not post.public and post.author != request.user:
		context = {
			'title': _('Sorry! :('),
		}
		
		return render_to_response('not_public.html', context_instance=RequestContext(request, context))

	context = {
		'post': post,
		'title': _('Post #{} from {}').format(post.id, post.date),
	}

	if post.author == request.user:
		context['title'] = _('Your post #{}').format(post.get_user_id(), post.date)

	return render_to_response('show_post.html', context_instance=RequestContext(request, context))

def switch_language(request, language):
	request.session['django_language'] = language
	return HttpResponseRedirect('/')


def sign_up(request):
	if not request.method == 'POST':
		context = {
			'title': _('Sign up'),
		}

		return render_to_response('sign_up.html', context_instance=RequestContext(request, context))

	# Request method is POST
	form = SignUpForm(request.POST, request.FILES)
	if not form.is_valid():
		context = {
			'title': _('Sign up'),
			'form': form,
		}
		return render_to_response('sign_up.html', context_instance=RequestContext(request, context))

	# Check invite code
	try:
		invite = Invite.objects.get(code = request.POST.get('invite_code', None))
	except Invite.DoesNotExist:
		context = {
			'title': _('Sign up'),
			'form': form,
			'noinvite': True,
		}
		return render_to_response('sign_up.html', context_instance=RequestContext(request, context))

	# Fixme
	user = form.save()
	user.set_password(request.POST.get('password', None))
	user.invited_by = invite.generated_by
	user.save()

	invite.delete()

	user.send_verification_mail()

	login_user = django.contrib.auth.authenticate(username = user.username, password = request.POST.get('password', None))
	django.contrib.auth.login(request, login_user)
	return HttpResponseRedirect('/')

def mail_verify(request, user_id, hash):
	user = get_object_or_404(DiaryUser, id = user_id)

	if not hash == user.get_verification_hash():
		return HttpResponse('Sorry, invalid hash.')

	user.mail_verified = True
	user.save()
	return HttpResponseRedirect("/")

@login_required
def account_settings(request):
	if not request.method == 'POST':
		context = {
			'title': _('Account settings'),
			'form': AccountSettingsForm(),
		}
		return render_to_response('account_settings.html', context_instance=RequestContext(request, context))

	# Request method is POST
	form = AccountSettingsForm(request.POST, request.FILES)

	if not form.is_valid():
		context = {
			'title': _('Account settings'),
			'form': form,
		}
		return render_to_response('account_settings.html', context_instance=RequestContext(request, context))

	# Save form

	if request.user.email != form.cleaned_data['email']:
		request.user.mail_verified = False
		request.user.email = form.cleaned_data['email']
		request.user.send_verification_mail()

	request.user.geolocation_enabled = form.cleaned_data['geolocation_enabled']
	request.user.save()

	context = {
		'title': _('Account settings'),
		'success': True,
	}
	return render_to_response('account_settings.html', context_instance=RequestContext(request, context))

@api_view(['DELETE'])
def delete_post(request, post_id):
	"""
	Delete a post. This is currently an AJAX only view
	"""

	post = get_object_or_404(Post,
		id = post_id,
		author = request.user,
	)

	if not post.is_editable():
		raise PermissionDenied

	post.delete()
	return Response(status=status.HTTP_204_NO_CONTENT)

@login_required
@cache_page(60 * 60 * 24)
def stats(request):
	try:
		randompost = Post.objects.filter(public = True).order_by('?')[:1].get()
	except Post.DoesNotExist:
		randompost = None

	streak_leaders = DiaryUser.objects.all()
	streak_leaders = sorted(streak_leaders, key = lambda t: t.get_streak(), reverse = True)[:10]
	streak_leaders = filter(lambda t: t.get_streak() > 1, streak_leaders)

	posts_leaders = DiaryUser.objects.all()
	posts_leaders = sorted(posts_leaders, key = lambda t: len(t.post_set.all()), reverse = True)[:10]
	posts_leaders = filter(lambda t: len(t.post_set.all()) > 1, posts_leaders)

	context = {
		'title': 'Stats',
		'randompost': randompost,
		'streak_leaders': streak_leaders,
		'posts_leaders': posts_leaders,
		'posts': Post.objects.filter(author = request.user).order_by('date')
	}
	return render_to_response('stats.html', context_instance=RequestContext(request, context))
