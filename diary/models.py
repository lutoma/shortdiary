# coding: utf-8
from django.utils.translation import ugettext_lazy as _
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.template.loader import get_template, Context
from django.conf import settings
from email_extras.utils import send_mail_template
from django.db.models import Avg
from django.core.cache import cache
import diary.tasks as tasks
import hashlib
import datetime
import gnupg

class DiaryUser(AbstractUser):
	"""
	The extended user
	"""

	invited_by = models.ForeignKey("DiaryUser", related_name = 'user_invited_by', blank = True, null = True, verbose_name = _('invited by'))
	invites_left = models.IntegerField(default = 5, verbose_name = _('invites left'))
	last_seen_at = models.DateTimeField(blank = True, null = True, verbose_name = _('last seen at'))
	mail_verified = models.BooleanField(default = False, verbose_name = _('email verified?'))
	language = models.CharField(default = 'en_US', max_length = 5, verbose_name = _('language'))
	geolocation_enabled = models.BooleanField(verbose_name = _('Post location enabled'), default = True)

	get_verification_hash = lambda self: hashlib.sha256(self.email.encode('utf-8') + settings.SECRET_KEY).hexdigest()

	def send_verification_mail(self):
		mail_template = get_template('mails/verification.txt')
		mail = EmailMessage(
			_('Please verify your email address on shortdiary, {0}'.format(self.username)),
			mail_template.render(Context({'mailuser': self, 'hash': self.get_verification_hash()})),
			'shortdiary <team@shortdiary.me>',
			['{0} <{1}>'.format(self.username, self.email)])
		mail.send()

	def get_streak(self):
		cached_streak = cache.get('diary_{}_streak'.format(self.username))

		if cached_streak:
			return cached_streak

		streak = tasks.update_streak(self)

		# Infinite lifetime since this is invalidated as soon as a new
		# post is written by the user
		cache.set('diary_{}_streak'.format(self.username), streak, None)
		return streak

	def get_year_history(self):
		"""
		Returns the length of posts for a user for the last 356 days.
		"""

		grid = [None] * 365

		for post in Post.objects.filter(author = self, date__year = datetime.date.today().year):
			grid[post.date.timetuple().tm_yday] = post

		return grid

	def get_posts(self):
		return Post.objects.filter(author = self)

	def get_post_characters(self):
		return reduce(lambda x, post: x + len(post.text), self.get_posts(), 0)

	def get_average_post_length(self):
		# Todo replace this with an QuerySet aggregate
		own_posts = self.get_posts().count()
		if own_posts < 1:
			return 0

		return self.get_post_characters() / own_posts

class Post(models.Model):
	"""
	A diary post
	"""

	author = models.ForeignKey(DiaryUser, verbose_name = _('author'))
	date = models.DateField(verbose_name = ('date'))
	text = models.TextField(max_length = 350, verbose_name = _('text'))
	mood = models.IntegerField(verbose_name = _ ('mood'))
	image = models.ImageField(upload_to = 'postimages/%d%m%y/', blank = True, verbose_name = _('image'))
	public = models.BooleanField(verbose_name = _('public'), default = False)
	part_of = models.CharField(blank = True, null = True, max_length = 600, verbose_name = _('part of'))

	created_at = models.DateTimeField(auto_now_add = True, verbose_name = _('created at'))
	last_changed_at = models.DateTimeField(auto_now = True, verbose_name = _('last changed at'))

	sent = models.BooleanField(default = False, verbose_name = _('mail sent?'))

	location_lat = models.DecimalField(max_digits=16, decimal_places=12, blank = True, null = True, verbose_name = _('Location latitude'))
	location_lon = models.DecimalField(max_digits=16, decimal_places=12, blank = True, null = True, verbose_name = _('Location longitude'))
	location_verbose = models.CharField(max_length = 400, blank = True, verbose_name = _('Location name'))

	__unicode__ = lambda self: _('{0} at {1}').format(self.author, self.date)

	class Meta:
		verbose_name = _('post')
		verbose_name_plural = _('posts')

	def get_user_id(self):
		"""
		Get user specific post ID (Aka: The how-manieth post of this user is this?)
		"""
		return len(Post.objects.filter(author = self.author, date__lt = self.date)) + 1

	get_user_id.admin_order_field = 'date'
	get_user_id.boolean = False
	get_user_id.short_description = 'User post ID'

	def is_editable(self):
		"""
		Should this post still be editable by the user?
		"""

		return (self.date > datetime.date.today() - datetime.timedelta(days = 3))

	is_editable.admin_order_field = 'date'
	is_editable.boolean = True
	is_editable.short_description = 'Still editable by user?'


	def get_activity_color(self):
		length = len(self.text)

		if(length <= 50):
			return '#d6e685'

		if(length <= 150):
			return '#8cc665'

		if(length <= 250):
			return '#44a340'

		return '#1e6823'

	def send_mail(self):
		"""
		Sends out the mail for this post
		"""

		#gpg = gnupg.GPG(gnupghome='/tmp/sd-gpg/')
		#gpg.encoding = 'utf-8'

		#data = mail_template.render(Context({'post': self, 'MEDIA_URL': settings.MEDIA_URL}))
		#pgp_signature = gpg.sign(data, keyid = '0x95CAF8BC', detach = True).data
		#data = gpg.encrypt(data, 'hello@lutoma.org', always_trust = True, sign = '0x95CAF8BC').data

		send_mail_template(
			_('A chunk of your past - Here\'s what you did last year ({0})!').format(self.date),
			'post',
			'Shortdiary Robot <team@shortdiary.me>',
			['{0} <{1}>'.format(self.author.username, self.author.email)],
			context = {'post': self}
		)

		self.sent = True
		self.save()

		#if self.image:
		#	message.attach_file(os.path.split(self.image.path))

def update_streak_signal(sender, instance, **kwargs):
	tasks.update_streak.delay(sender)

post_save.connect(update_streak_signal, sender=Post, dispatch_uid="update_streak_signal")